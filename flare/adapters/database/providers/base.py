from abc import ABC

from flare.api.lens import Lens, Material


class Provider(ABC):
    """Provide lenses and materials."""

    def get_lenses(self) -> tuple[Lens, ...]:
        return ()

    def get_materials(self) -> tuple[Material, ...]:
        return ()
