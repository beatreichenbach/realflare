import logging
from functools import lru_cache

import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from realflare.api.data import Flare, Project
from realflare.api.tasks.opencl import OpenCL, LAMBDA_MID, LAMBDA_MIN, LAMBDA_MAX, Image
from realflare.utils.ciexyz import CIEXYZ
from realflare.utils.timing import timer

logger = logging.getLogger(__name__)


class StarburstTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)
        self.kernel = None
        self.build()

    def build(self, *args, **kwargs) -> None:
        self.source = f'__constant int LAMBDA_MIN = {LAMBDA_MIN};\n'
        self.source += f'__constant int LAMBDA_MAX = {LAMBDA_MAX};\n'
        self.source += f'__constant int LAMBDA_MID = {LAMBDA_MID};\n'
        self.source += self.read_source_file('noise.cl')
        self.source += self.read_source_file('geometry.cl')
        self.source += self.read_source_file('color.cl')
        self.source += self.read_source_file('starburst.cl')
        super().build()
        self.kernel = cl.Kernel(self.program, 'starburst')

    @lru_cache(1)
    def update_light_spectrum(self) -> Image:
        # extract XYZ data for visible wavelengths only
        xyz = [[x, y, z, 0] for w, x, y, z in CIEXYZ if LAMBDA_MIN <= w < LAMBDA_MAX]
        array = np.array(xyz, np.float32)

        # pyopencl does not handle 1d images so convert to 2d array with 4 channels
        array = np.reshape(array, (1, -1, 4))

        image = Image(self.context, array=array)
        return image

    @lru_cache(1)
    def update_fourier_spectrum(self, aperture: Image, distance: float) -> Image:
        # https://people.mpi-inf.mpg.de/~ritschel/Papers/TemporalGlare.pdf
        # [Ritschel et al. 2009] 4. Wave-Optics Simulation of Light-Scattering
        # To get diffraction pattern and get the incident radiance
        # Li = K * |F|**2
        # K = 1/(lambda * distance)**2
        # F = fft(A * E)
        # A = aperture
        # E = complex exponential = e ^ (i * pi / (lambda * distance)) * (x^2 + y^2))
        # lambda = the wavelength of the light
        # distance = distance between pupil and retina

        # [Ritschel et al. 2009] 5. Implementation
        # The reference wavelength is chosen as the center of the visible spectrum
        wavelength = LAMBDA_MID * 1e-6  # nm to mm

        # zero division error
        distance = max(1e-9, distance * 1e3)  # m to mm

        h, w = aperture.array.shape[:2]
        x = np.linspace(-1, 1, w)
        y = np.linspace(-1, 1, h)
        xv, yv = np.meshgrid(x, y)
        exp = np.exp(1j * np.pi / (wavelength * distance) * (xv**2 + yv**2))

        fft = np.fft.fftshift(np.fft.fft2(aperture.array * exp))

        # avoiding sqrt for optimization
        # don't use K to preserve intensity
        # k = 1 / pow(wavelength * distance, 2)
        power_spectrum_2 = fft.real**2 + fft.imag**2

        array = np.float32(power_spectrum_2)

        image = Image(self.context, array=array, args=(aperture, distance))
        return image

    @lru_cache(1)
    def starburst(
        self,
        config: Flare.Starburst,
        resolution: QtCore.QSize,
        samples: int,
        aperture: Image,
        offset: tuple[float, float],
        scale: tuple[float, float],
    ) -> Image:
        if self.rebuild:
            self.build()

        # args
        if config.vignetting_enabled:
            vignetting = (config.vignetting.x(), config.vignetting.y())
        else:
            vignetting = (np.NAN, np.NAN)
        blur = config.blur / 100
        rotation = np.radians(config.rotation)
        rotation_weight = config.rotation_weight
        intensity = config.intensity * 1e-6
        scale = (scale[0], scale[1] * resolution.width() / resolution.height())
        offset = (offset[0], -offset[1])

        fourier_spectrum = self.update_fourier_spectrum(aperture, config.distance)
        fourier_spectrum.clear_image()

        light_spectrum = self.update_light_spectrum()

        # create output buffer
        starburst = self.update_image(resolution, flags=cl.mem_flags.READ_WRITE)
        starburst.args = (
            resolution,
            fourier_spectrum,
            samples,
            blur,
            rotation,
            rotation_weight,
            vignetting,
            intensity,
            offset,
            scale,
        )

        aperture.clear_image()

        # run program
        self.kernel.set_arg(0, starburst.image)
        self.kernel.set_arg(1, fourier_spectrum.image)
        self.kernel.set_arg(2, light_spectrum.image)
        self.kernel.set_arg(3, np.int32(samples))
        self.kernel.set_arg(4, np.float32(blur))
        self.kernel.set_arg(5, np.float32(rotation))
        self.kernel.set_arg(6, np.float32(rotation_weight))
        self.kernel.set_arg(7, np.float32(vignetting))
        self.kernel.set_arg(8, np.float32(intensity))
        self.kernel.set_arg(9, np.float32(offset))
        self.kernel.set_arg(10, np.float32(scale))

        w, h = resolution.width(), resolution.height()
        global_work_size = (w, h)
        local_work_size = None
        cl.enqueue_nd_range_kernel(
            self.queue, self.kernel, global_work_size, local_work_size
        )
        cl.enqueue_copy(
            self.queue, starburst.array, starburst.image, origin=(0, 0), region=(w, h)
        )

        return starburst

    @timer
    def run(self, project: Project, aperture: Image) -> Image:
        flare = project.flare
        position = flare.light.position.x(), flare.light.position.y()
        scale = flare.starburst.scale.width(), flare.starburst.scale.height()
        image = self.starburst(
            flare.starburst,
            project.render.resolution,
            project.render.starburst.samples,
            aperture,
            position,
            scale,
        )
        return image
