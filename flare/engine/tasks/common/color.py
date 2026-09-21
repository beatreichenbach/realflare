from functools import lru_cache

import numpy as np

from flare import ocio
from flare.api import color

from ...base import Array
from .raytracing import LAMBDA_MAX, LAMBDA_MIN


@lru_cache(1)
def get_spectral(illuminant: str, wavelength_count: int) -> Array:
    """
    Return an Image with the CMFs for the wavelengths in render space.

    The CIE 1931 color matching functions are weighted by the illuminant and
    converted from CIE XYZ to the OCIO config's scene-linear space.
    """

    lambdas = np.linspace(LAMBDA_MIN, LAMBDA_MAX, wavelength_count)
    cmfs_variation = 'CIE 2015 2 Degree Standard Observer'
    cmfs = color.get_cmfs(cmfs_variation, lambdas)

    illuminant_values = color.get_illuminant(illuminant, lambdas) * 0.01

    matrix = ocio.get_xyz_to_scene_linear()
    rgb = (cmfs * illuminant_values[:, None]) @ matrix.T

    # Add an alpha channel and turn into 2d texture with 1 px height.
    rgba = np.concatenate((rgb, np.zeros((rgb.shape[0], 1))), axis=-1)
    rgba = rgba[np.newaxis, ...]

    spectral = Array(rgba, args=(illuminant, wavelength_count))
    return spectral
