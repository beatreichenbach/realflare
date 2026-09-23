from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import platformdirs

import flare
from flare import env
from flare.api.lens import Lens, Material
from flare.infrastructure.storage.jsonfile import read_model, write_model

from . import model, parsers, providers

logger = logging.getLogger(__name__)

DEFAULT_URL = 'https://github.com/amegahed/OpticsDatabase/archive/refs/heads/main.zip'
OPTICS_URL = os.environ.get(env.REALFLARE_OPTICS_URL, DEFAULT_URL)
OPTICS_LENS_DIR = 'Optics/Photography'
OPTICS_MATERIAL_DIR = 'Materials'
DEFAULT_LENS_DIR = str(Path(flare.__file__).resolve().parent.parent / 'custom')
CUSTOM_LENS_DIR = os.path.expanduser(
    os.environ.get(env.REALFLARE_LENS_DIR, DEFAULT_LENS_DIR)
)


class Database:
    """Database that provides Lenses and Materials."""

    _instance: Database | None = None

    def __new__(cls: type[Database]) -> Database:
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._init_cache()
            cls._instance = instance
        else:
            instance = cls._instance
        return instance

    def _init_cache(self) -> None:
        """Load the cache from disk and build the lookup indices."""

        cache_dir = platformdirs.user_cache_dir(flare.__name__)
        cache_path = os.path.join(cache_dir, 'optics.json')
        logger.debug(f'Database cache: {cache_path}')

        store = CacheStore(cache_path)
        cache = store.load()
        if cache is None or cache.version != model.CACHE_VERSION:
            logger.info('Building database cache ...')
            cache = self._load_database()
            store.save(cache)

        self._cache = cache
        self._lenses_by_name: dict[tuple[str, str], Lens] = {
            (lens.vendor, lens.name): lens for lens in cache.lenses
        }
        self._materials_by_vendor: dict[str, tuple[Material, ...]] = {}
        self._arrays_by_vendor: dict[str, np.ndarray] = {}
        for vendor in {material.vendor for material in cache.materials}:
            materials = tuple(m for m in cache.materials if m.vendor == vendor)
            self._materials_by_vendor[vendor] = materials
            self._arrays_by_vendor[vendor] = np.array(
                tuple((m.ior, m.abbe) for m in materials)
            )

    @staticmethod
    def _load_database() -> model.Cache:
        """Return a cache built from the database providers."""

        lens_parsers = (parsers.ZemaxParser(),)
        material_parsers = (parsers.MtrlParser(),)
        database_providers = (
            providers.RepositoryProvider(
                url=OPTICS_URL,
                lens_dir=OPTICS_LENS_DIR,
                lens_parsers=lens_parsers,
                material_dir=OPTICS_MATERIAL_DIR,
                material_parsers=material_parsers,
            ),
            providers.FilesystemProvider(
                lens_dir=CUSTOM_LENS_DIR,
                lens_parsers=lens_parsers,
            ),
        )
        lenses: list[Lens] = []
        materials: list[Material] = []
        for provider in database_providers:
            lenses.extend(provider.get_lenses())
            materials.extend(provider.get_materials())

        # Limit vendors to the main glass manufacturers that provide coefficients.
        vendors = ('Cdgm', 'Hikari', 'Hoya', 'Ohara', 'Schott', 'Sumita')
        materials = [m for m in materials if m.vendor in vendors]

        # Sort
        lenses.sort(key=lambda x: (x.vendor, x.name))
        materials.sort(key=lambda x: (x.vendor, x.name))

        return model.Cache(
            version=model.CACHE_VERSION,
            lenses=tuple(lenses),
            materials=tuple(materials),
        )

    def get_lenses(self) -> tuple[Lens, ...]:
        """Return all Lenses from the database."""

        return self._cache.lenses

    def get_lens_vendors(self) -> tuple[str, ...]:
        """Return the vendors for all Lenses."""

        vendors = {vendor for vendor, _ in self._lenses_by_name}
        return tuple(sorted(vendors))

    def get_lens(self, vendor: str, name: str) -> Lens | None:
        """Return a Lens."""

        return self._lenses_by_name.get((vendor, name))

    def get_materials(self) -> tuple[Material, ...]:
        """Return all Materials from the database."""

        return self._cache.materials

    def get_material_vendors(self) -> tuple[str, ...]:
        """Return the vendors for all Materials."""

        return tuple(sorted(self._materials_by_vendor))

    def get_material(self, vendor: str, ior: float, abbe: float) -> Material | None:
        """
        Return a material from a vendor that is closest to the given ior and abbe nr.
        """

        materials = self._materials_by_vendor.get(vendor)
        if not materials:
            return None

        # Use the percentage to account for unit differences
        array = self._arrays_by_vendor[vendor]
        error = 1 - array / np.array((ior, abbe))

        # Use the Euclidean distance to find the closest match
        scores = np.sum(error**2, axis=1)
        index = int(np.argmin(scores))

        return materials[index]


class CacheStore:
    """Persistence for the aggregated database cache."""

    def __init__(self, cache_path: str) -> None:
        self.cache_path = cache_path

    def save(self, cache: model.Cache) -> None:
        """Save the cache to disk."""

        write_model(cache, self.cache_path, indent=None)

    def load(self) -> model.Cache | None:
        """Return the Cache from disk."""

        return read_model(model.Cache, self.cache_path)
