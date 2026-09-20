import dataclasses
from functools import lru_cache

from flare import api

LAMBDA_MIN = 390
LAMBDA_MAX = 730
LAMBDA_MID = (LAMBDA_MIN + LAMBDA_MAX) / 2


@dataclasses.dataclass
class GhostData:
    path: tuple[int, int]
    divisions: int
    radius: float
    center: float = 0
    culled: bool = False

    def __hash__(self) -> int:
        return hash((self.path, self.divisions, self.radius, self.center, self.culled))

    @property
    def ray_count(self) -> int:
        return get_ray_count(self.divisions)

    @property
    def tri_count(self) -> int:
        return get_tri_count(self.divisions)


@lru_cache(64)
def get_ray_count(divisions: int) -> int:
    return 1 + (3 * divisions * (divisions + 1))


@lru_cache(64)
def get_tri_count(divisions: int) -> int:
    return divisions**2 * 6


def get_paths(surfaces: tuple[api.Lens.Surface, ...]) -> tuple[tuple[int, int], ...]:
    """
    Return paths a ray can travel. Each path is a tuple of two surface indices where a
    ray bounces.
    """

    index_min = 0
    index_max = len(surfaces) - 1
    paths = []
    for bounce1 in range(1, index_max):
        if surfaces[bounce1].type == api.Lens.Surface.SurfaceType.STOP:
            index_min = bounce1 + 1
        for bounce2 in range(index_min, bounce1):
            paths.append((bounce1, bounce2))

    # Append a path that doesn't bounce for debugging
    # paths.append((-1, -1))

    return tuple(paths)
