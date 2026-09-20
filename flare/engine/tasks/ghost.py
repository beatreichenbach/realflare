import logging
from functools import lru_cache

import numpy as np

from ..base import Array, Task
from .common import LAMBDA_MID

logger = logging.getLogger(__name__)


class GhostTask(Task):
    @staticmethod
    def run(aperture: Array, distance: float, vignette: float) -> Array:
        """Return a ghost image by rendering the fresnel diffraction of an aperture."""

        return diffract_aperture(aperture, distance, vignette)


@lru_cache(1)
def diffract_aperture(aperture: Array, distance: float, vignette: float) -> Array:
    """Return a ghost image by rendering the fresnel diffraction of an aperture."""

    # All parameters need to be in the same unit
    wavelength = LAMBDA_MID * 1e-9
    size = 0.1
    aperture_array = aperture.array[:, :, 0]

    intensity = fresnel_diffraction(aperture_array, wavelength, distance, size)

    if vignette > 0:
        shape = aperture.array.shape[:2]
        mask = fade_mask(shape, vignette)
        intensity *= mask

    array = np.empty((*intensity.shape, 4), dtype=intensity.dtype)
    array[..., :3] = intensity[..., np.newaxis]
    array[..., 3] = 1

    args = (aperture, distance, vignette)
    image = Array(array=array, args=args)
    return image


def fresnel_diffraction(
    aperture: np.ndarray, wavelength: float, distance: float, size: float
) -> np.ndarray:
    """
    Return the near-field Fresnel diffraction using the Angular Spectrum Method.

    The aperture is an array with shape (h, w). Wavelength, distance, and
    size must all use the same unit.
    """

    height, width = aperture.shape

    # Calculate spatial frequencies (kx, ky)
    # The maximum spatial frequency is 1 / (2 * pixel_size)
    # The step in frequency space is 1 / (N * pixel_size)
    sx = size / width
    sy = size / height
    kx = 2 * np.pi * np.fft.fftshift(np.fft.fftfreq(width, d=sx))
    ky = 2 * np.pi * np.fft.fftshift(np.fft.fftfreq(height, d=sy))
    kxm, kym = np.meshgrid(kx, ky)

    # Wavenumber k
    k = 2 * np.pi / wavelength

    # Calculate the transfer function H for propagation
    # H = exp(j * z * sqrt(k^2 - kx^2 - ky^2))
    # The sqrt term can become negative (evanescent waves) so separate it and clamp it.
    real_term = np.sqrt(np.maximum(0, k**2 - kxm**2 - kym**2))
    imag_term = np.sqrt(np.maximum(0, kxm**2 + kym**2 - k**2))
    transfer = np.exp(1j * distance * real_term - distance * imag_term)

    aperture_fft = np.fft.fftshift(np.fft.fft2(aperture))
    propagated_fft = aperture_fft * transfer
    observation = np.fft.ifft2(np.fft.ifftshift(propagated_fft))

    # The intensity is the magnitude squared of the complex field.
    intensity = np.abs(observation) ** 2

    # Normalize the intensity to preserve 0..1 space
    intensity = intensity / np.max(intensity)

    return intensity


def fade_mask(shape: tuple[int, int], margin: float) -> np.ndarray:
    """Return a circularly faded edge mask."""

    height, width = shape
    yy, xx = np.mgrid[0:height, 0:width]
    center_x = width / 2.0
    center_y = height / 2.0
    radius = min(height, width) / 2.0
    dist = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)

    mask = remap(
        value=dist / radius,
        in_min=1 - margin,
        in_max=1,
        out_min=1,
        out_max=0,
    )
    mask = np.clip(mask, 0.0, 1.0)

    return mask


def remap(
    value: np.ndarray, in_min: float, in_max: float, out_min: float, out_max: float
) -> np.ndarray:
    """Return remapped array values from an input range to an output range."""

    return out_min + (value - in_min) * (out_max - out_min) / (in_max - in_min)
