from functools import lru_cache

import numpy as np
from PySide2 import QtCore

from realflare.api.data import Project
from realflare.api.tasks.opencl import OpenCL, Image, ImageArray
from realflare.api.tasks.raytracing import wavelength_array
from realflare.utils import frft
from realflare.utils.timing import timer


class GhostTask(OpenCL):
    @lru_cache(10)
    def ghost(
        self,
        aperture: Image,
        fstop: float,
        resolution: QtCore.QSize,
        wavelength_count: int,
    ) -> ImageArray:
        height, width = aperture.array.shape
        shape = (height, width, wavelength_count)
        array = np.zeros(shape, np.float32)

        # [Ritschel et al. 2009] 3.3. Ringing pattern
        # alpha = 0.15 * (lambda / 400nm) * (f-stop / 18)
        for i, wavelength in enumerate(wavelength_array(wavelength_count)):
            alpha = 0.15 * (wavelength / 400) * (fstop / 18)
            spectrum = np.fft.fftshift(aperture.array)
            spectrum = frft.frft(spectrum, alpha)
            spectrum = np.fft.fftshift(spectrum)
            array[:, :, i] = np.abs(spectrum)

        array *= np.sqrt(resolution.width() * resolution.height())

        # return image array
        args = (aperture, fstop, resolution, wavelength_count)
        image = ImageArray(
            self.context,
            array=array,
            args=args,
        )
        return image

    @timer
    def run(self, project: Project, aperture: Image) -> ImageArray:
        fstop = project.flare.ghost.fstop
        resolution = project.render.ghost.resolution
        wavelength_count = project.render.wavelength_count
        image = self.ghost(aperture, fstop, resolution, wavelength_count)
        return image
