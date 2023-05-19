from functools import lru_cache

import numpy as np
import pyopencl as cl

from realflare.api.data import Flare, Render, Project
from realflare.api.tasks.opencl import OpenCL, LAMBDA_MID, LAMBDA_MIN, LAMBDA_MAX, Image
from realflare.utils.ciexyz import CIEXYZ
from realflare.utils.timing import timer


class StarburstTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)
        self.kernel = None
        self.build()

    def build(self, *args, **kwargs):
        self.source = f'__constant int LAMBDA_MIN = {LAMBDA_MIN};\n'
        self.source += f'__constant int LAMBDA_MAX = {LAMBDA_MAX};\n'
        self.source += f'__constant int LAMBDA_MID = {LAMBDA_MID};\n'
        self.source += self.read_source_file('starburst.cl')
        super().build()
        self.kernel = cl.Kernel(self.program, 'sample_simple')

    @lru_cache(1)
    def update_light_spectrum(self) -> Image:
        # extract XYZ data for visible wavelengths only
        xyz = [[x, y, z, 0] for w, x, y, z in CIEXYZ if LAMBDA_MIN <= w < LAMBDA_MAX]
        array = np.array(xyz, np.float32)

        # pyopencl does not handle 1d images so convert to 2d array with 4 channels
        array = np.reshape(array, (1, -1, 4))

        image = Image(self.context, array=array)
        return image

    @lru_cache(10)
    def update_fourier_spectrum(self, aperture: Image, lens_distance: float) -> Image:
        # https://people.mpi-inf.mpg.de/~ritschel/Papers/TemporalGlare.pdf
        # [Ritschel et al. 2009] 4. Wave-Optics Simulation of Light-Scattering
        # To get diffraction pattern and get the incident radiance
        # Li = K * |F|**2
        # K = 1/(lambda * distance)**2
        # F = Fourier transform
        # lambda = the wavelength of the light
        # distance = distance between pupil and retina

        fft = np.fft.fft2(aperture.array)
        fft = np.fft.fftshift(fft)

        # The magnitude is sqrt(real**2 + imaginary**2)
        # To calculate K we need the squared magnitude of F
        # By avoiding sqrt we save computation power
        power_spectrum = fft.real**2 + fft.imag**2

        # [Ritschel et al. 2009] 5. Implementation
        # The reference wavelength is chosen as the center of the visible spectrum
        d = max(0.001, lens_distance)  # zero division error
        k = 1 / (LAMBDA_MID * d) ** 2

        array = np.float32(power_spectrum * k)

        image = Image(self.context, array=array, args=(aperture, lens_distance))
        return image

    def sample(self, starburst: Image) -> None:
        w, h = starburst.image.shape
        global_work_size = (w, h)
        local_work_size = None
        cl.enqueue_nd_range_kernel(
            self.queue, self.kernel, global_work_size, local_work_size
        )
        cl.enqueue_copy(
            self.queue, starburst.array, starburst.image, origin=(0, 0), region=(w, h)
        )

    @lru_cache(10)
    def starburst(
        self,
        config: Flare.Starburst,
        render: Render.Starburst,
        aperture: Image,
    ) -> Image:
        # rebuild kernel
        self.__init__(self.queue)

        # args
        resolution = render.resolution
        samples = render.samples
        fadeout = [config.fadeout.x(), config.fadeout.y()]

        # clear_image is used to ensure cache from the host is used
        aperture.clear_image()
        fourier_spectrum = self.update_fourier_spectrum(aperture, config.lens_distance)
        fourier_spectrum.clear_image()
        light_spectrum = self.update_light_spectrum()

        # create output buffer
        starburst = self.update_image(resolution)
        starburst.args = (config, render, aperture)

        # run program
        self.kernel.set_arg(0, starburst.image)
        self.kernel.set_arg(1, fourier_spectrum.image)
        self.kernel.set_arg(2, light_spectrum.image)
        self.kernel.set_arg(3, np.int32(samples))
        self.kernel.set_arg(4, np.float32(config.blur))
        self.kernel.set_arg(5, np.float32(config.rotation))
        self.kernel.set_arg(6, np.float32(config.rotation_weighting))
        self.kernel.set_arg(7, np.float32(fadeout))
        self.kernel.set_arg(8, np.float32(config.intensity))

        self.sample(starburst)

        return starburst

    @timer
    def run(self, project: Project, aperture: Image) -> Image:
        return self.starburst(
            project.flare.starburst, project.render.starburst, aperture
        )
