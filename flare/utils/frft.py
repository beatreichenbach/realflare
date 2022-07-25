# Original code from https://github.com/siddharth-maddali/frft/blob/main/frft.py
import logging
from functools import lru_cache

import numpy as np
from numpy.fft import fftshift, fftn, ifftn


@lru_cache(maxsize=10)
def chirp(shape: tuple[int, ...]) -> complex:
    # logging.debug('recalculating chirp')
    indices = tuple(slice(-size // 2, size // 2) for size in shape)
    grid = np.mgrid[indices]

    if len(shape) == 1:
        grid = tuple(grid)
    array = (fftshift(array) ** 2 / array.shape[i] for i, array in enumerate(grid))
    chirp_arg = 1.0j * np.pi * np.sum(array)
    return chirp_arg


def normalize(array: np.ndarray, alpha: float) -> tuple[np.ndarray, float]:
    # OZAKTAS et al 1996
    # III. Methods of Computing the Continuous Fractional Fourier Transform

    rel_alpha = alpha % 4
    if rel_alpha < 0.5:
        alpha = rel_alpha + 1
        array = ifftn(array, norm='ortho')
    elif rel_alpha < 1.5:
        alpha = rel_alpha
        array = array
    elif rel_alpha < 2.5:
        alpha = rel_alpha - 1
        array = fftn(array, norm='ortho')
    elif rel_alpha < 3.5:
        alpha = rel_alpha - 2
        array = np.flip(array)
    else:
        alpha = rel_alpha - 3
        array = ifftn(array, norm='ortho')
    return array, alpha


def frft(array: np.ndarray, alpha: float) -> np.ndarray:
    array, alpha = normalize(array, alpha)

    phi = alpha * np.pi / 2.0
    cotan_phi = 1.0 / np.tan(phi)
    sq_cotan_phi = np.sqrt(1.0 + cotan_phi**2)

    scale = np.sqrt(1.0 - 1.0j * cotan_phi) / np.sqrt(np.prod(array.shape))

    chirp_arg = chirp(array.shape)
    chirp1 = np.exp(chirp_arg * (cotan_phi - sq_cotan_phi))
    chirp2 = np.exp(chirp_arg * sq_cotan_phi)

    fft1 = fftn(chirp2, norm='ortho')
    fft2 = fftn(chirp1 * array, norm='ortho')

    # a scaled and chirp modulated version of fourier transforms of array
    array = scale * chirp1 * ifftn(fft1 * fft2, norm='ortho')

    return array
