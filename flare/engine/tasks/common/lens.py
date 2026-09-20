from functools import lru_cache

import numpy as np

from flare import api
from ...base import Array, EngineError

surface_dtype = np.dtype(
    [
        ('type', np.uint32),
        ('center', np.float32),
        ('radius', np.float32),
        ('height', np.float32),
        ('coefficients', np.float32, 4),
        ('conic', np.float32),
        ('coating_wavelength', np.float32),
        ('coating_ior', np.float32),
        ('_pad', np.float32),
    ]
)


def get_lens(lens_config: api.Flare.Lens) -> api.Lens:
    """
    Return a lens from the database.

    :raise EngineError: If the lens cannot be found or loaded.
    """
    db = api.Database()
    vendor = lens_config.vendor
    name = lens_config.lens
    lens = db.get_lens(vendor=vendor, name=name)
    if not lens:
        raise EngineError(
            f'invalid lens: vendor {vendor!r}, name {name!r}',
            log=f'Could not load the lens (vendor {vendor!r}, name {name!r}).',
        )
    return lens


@lru_cache(1)
def get_surfaces(lens: api.Lens, coatings: tuple[tuple[int, float], ...]) -> Array:
    """Return an Array with all surfaces of a lens."""

    array = np.zeros(len(lens.surfaces), surface_dtype)

    offset = 0
    for i, surface in enumerate(lens.surfaces):
        surface_type = list(api.Lens.Surface.SurfaceType).index(surface.type)

        try:
            radius = 1 / surface.curvature
        except ZeroDivisionError:
            radius = 0

        if i < len(coatings):
            wavelength, ior = coatings[i]
        else:
            wavelength, ior = (0, 0)

        array[i]['type'] = surface_type
        array[i]['center'] = offset + radius
        array[i]['radius'] = radius
        array[i]['height'] = surface.radius
        array[i]['conic'] = surface.conic
        for j in range(4):
            if j < len(surface.coefficients):
                array[i]['coefficients'][j] = surface.coefficients[j]
        array[i]['coating_wavelength'] = wavelength
        array[i]['coating_ior'] = ior

        offset += surface.spacing

    surfaces = Array(array=array, args=(lens, coatings))
    return surfaces
