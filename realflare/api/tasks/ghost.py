from functools import lru_cache

import numpy as np
from PySide2 import QtCore

from realflare.api.data import Project
from realflare.api.tasks.opencl import OpenCL, Image, LAMBDA_MID
from realflare.utils import frft
from realflare.utils.timing import timer


class GhostTask(OpenCL):
    @lru_cache(1)
    def ghost(self, aperture: Image, fstop: float, resolution: QtCore.QSize) -> Image:
        # [Ritschel et al. 2009] 3.3. Ringing pattern
        # alpha = 0.15 * (lambda / 400nm) * (f-stop / 18)

        # only assume one wavelength for performance optimization
        # alternative one ghost per wavelength can be calculated with:
        # raytracing.wavelength_array(wavelength_count)
        # and stored in an ImageArray:
        # array[:, :, i] = np.abs(spectrum)

        wavelength = LAMBDA_MID

        alpha = 0.15 * (wavelength / 400) * (fstop / 18)
        spectrum = np.fft.fftshift(aperture.array)
        spectrum = frft.frft(spectrum, alpha)
        spectrum = np.fft.fftshift(spectrum)
        array = np.float32(np.abs(spectrum))
        array *= np.sqrt(resolution.width() * resolution.height())

        # return image array
        args = (aperture, fstop, resolution)
        image = Image(self.context, array=array, args=args)
        return image

    @timer
    def run(self, project: Project, aperture: Image) -> Image:
        fstop = project.flare.ghost.fstop
        resolution = project.render.ghost.resolution
        image = self.ghost(aperture, fstop, resolution)
        return image
