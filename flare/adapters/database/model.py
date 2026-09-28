from pydantic import BaseModel

from flare.api.lens import Lens, Material

CACHE_VERSION = 1


class Cache(BaseModel):
    version: int = 0
    materials: tuple[Material, ...]
    lenses: tuple[Lens, ...]
