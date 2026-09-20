from __future__ import annotations

from abc import ABC

from .. import model


class Provider(ABC):
    """Provide lenses and materials."""

    def get_lenses(self) -> tuple[model.Lens, ...]:
        return ()

    def get_materials(self) -> tuple[model.Material, ...]:
        return ()
