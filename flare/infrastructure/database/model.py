from pydantic import BaseModel

from flare.api.lens import Lens, Material


class Cache(BaseModel):
    materials: tuple[Material, ...]
    lenses: tuple[Lens, ...]
