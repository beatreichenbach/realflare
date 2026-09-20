from __future__ import annotations

import logging
from collections.abc import Sequence

from ..model import Lens, Material
from ..parsers import Parser
from .base import Provider
from .common import load_files

logger = logging.getLogger(__name__)


class FilesystemProvider(Provider):
    """
    Provider that scans a filesystem tree for files.
    Expected layout: ``dir/<vendor>/**/*.*``
    """

    def __init__(
        self,
        lens_dir: str = '',
        lens_parsers: Sequence[Parser[Lens]] = (),
        material_dir: str = '',
        material_parsers: Sequence[Parser[Material]] = (),
    ) -> None:
        self._lens_dir = lens_dir
        self._lens_parsers = lens_parsers
        self._lenses: tuple[Lens, ...] = ()

        self._material_dir = material_dir
        self._material_parsers = material_parsers
        self._materials: tuple[Material, ...] = ()

        self.load()

    def load(self) -> None:
        """Load files from disk."""

        if self._lens_dir and self._lens_parsers:
            self._lenses = load_files(self._lens_dir, self._lens_parsers)
        if self._material_dir and self._material_parsers:
            self._materials = load_files(self._material_dir, self._material_parsers)

    def get_lenses(self) -> tuple[Lens, ...]:
        return self._lenses

    def get_materials(self) -> tuple[Material, ...]:
        return self._materials
