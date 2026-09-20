from functools import lru_cache

from qtpy import QtCore


@lru_cache(1)
def get_screen_scale(
    sensor_size: tuple[float, float], resolution: QtCore.QSize
) -> tuple[float, float]:
    """
    Return the screen scale to scale positions from mm to ndc. Fit the output into
    the sensor using either letterboxing or pillarboxing.
    """

    scale_x = 2 / sensor_size[0]
    scale_y = 2 / sensor_size[1]
    sensor_aspect = sensor_size[0] / sensor_size[1]
    resolution_aspect = resolution.width() / resolution.height()
    if resolution_aspect > sensor_aspect:
        # Fit to width
        scale_y *= resolution_aspect / sensor_aspect
    else:
        # Fit to height
        scale_x *= sensor_aspect / resolution_aspect
    return scale_x, scale_y


def get_ghost_scale(fstop: float) -> float:
    """Return the scale for a ghost base on the fstop of the lens."""

    # NOTE: While the minimum fstop is different per lens and could be used, it doesn't
    # make sense to adjust the ProjectEditor parameters every time the lens changes.
    # Instead, a default of f1 is used.
    min_fstop = 1

    ghost_scale = min_fstop / fstop
    return ghost_scale
