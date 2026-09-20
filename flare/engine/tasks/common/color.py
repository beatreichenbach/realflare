from functools import lru_cache

import numpy as np

from flare.api import color
from ...base import Array

from .raytracing import LAMBDA_MAX, LAMBDA_MIN

XYZ_TO_ACESCG = np.array(
    [
        [1.6410233797, -0.3248032942, -0.2364246952],
        [-0.6636628587, 1.6153315917, 0.0167563477],
        [0.0117218943, -0.0082844420, 0.9883948585],
    ]
)


@lru_cache(1)
def get_spectral(illuminant: str, wavelength_count: int) -> Array:
    """Return an Image with the CMFS for the wavelengths in render space."""

    lambdas = np.linspace(LAMBDA_MIN, LAMBDA_MAX, wavelength_count)
    cmfs_variation = 'CIE 2015 2 Degree Standard Observer'
    cmfs = color.get_cmfs(cmfs_variation, lambdas)

    illuminant_values = color.get_illuminant(illuminant, lambdas) * 0.01

    # TODO: Remove hard coded render space.
    # Convert CIE-XYZ to ACEScg
    # rgb = cmfs @ XYZ_TO_ACESCG.T
    rgb = (cmfs * illuminant_values[:, None]) @ XYZ_TO_ACESCG.T

    # Add an alpha channel and turn into 2d texture with 1 px height.
    rgba = np.concatenate((rgb, np.zeros((rgb.shape[0], 1))), axis=-1)
    rgba = rgba[np.newaxis, ...]

    spectral = Array(rgba, args=(illuminant, wavelength_count))
    return spectral
