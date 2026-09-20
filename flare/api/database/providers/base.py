from __future__ import annotations

from abc import ABC

from .. import model


class Provider(ABC):
    """Provides Lenses and Materials"""

    def get_lenses(self) -> tuple[model.Lens, ...]:
        return ()

    def get_materials(self) -> tuple[model.Material, ...]:
        return ()
