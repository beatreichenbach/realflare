from __future__ import annotations

import logging
import os
from functools import lru_cache

import numpy as np
import platformdirs
import pydantic

import flare
from . import model, parsers, providers

logger = logging.getLogger(__name__)

OPTICS_URL = 'https://github.com/amegahed/OpticsDatabase/archive/refs/heads/main.zip'
OPTICS_LENS_DIR = 'Optics/Photography'
OPTICS_MATERIAL_DIR = 'Materials'
CUSTOM_LENS_DIR = os.path.expanduser('~/dev/flare/custom')


class Database:
    """Database that provides Lenses and Materials."""

    _instance: Database | None = None

    def __new__(cls) -> Database:
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._init_cache()
            cls._instance = instance
        else:
            instance = cls._instance
        return instance

    def _init_cache(self) -> None:
        """Initialize the Cache."""

        cache_dir = platformdirs.user_cache_dir(flare.__name__)
        cache_path = os.path.join(cache_dir, 'optics.json')
        logger.debug(f'Database cache: {cache_path}')

        store = CacheStore(cache_path)
        cache = store.load()
        if cache:
            self._cache = cache
            return

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
        lenses: list[model.Lens] = []
        materials: list[model.Material] = []
        for provider in database_providers:
            lenses.extend(provider.get_lenses())
            materials.extend(provider.get_materials())

        # Limit vendors to the main glass manufacturers that provide coefficients.
        vendors = ('Cdgm', 'Hikari', 'Hoya', 'Ohara', 'Schott', 'Sumita')
        materials = [m for m in materials if m.vendor in vendors]

        # Sort
        lenses.sort(key=lambda x: (x.vendor, x.name))
        materials.sort(key=lambda x: (x.vendor, x.name))

        cache = model.Cache(lenses=tuple(lenses), materials=tuple(materials))

        store.save(cache)
        self._cache = cache

    # @classmethod
    # def instance(cls) -> Database:
    #     if cls._instance is None:
    #         cls._instance = Database()
    #     return cls._instance

    def get_lenses(self) -> tuple[model.Lens, ...]:
        """Return all Lenses from the database."""

        return self._cache.lenses

    def get_lens_vendors(self) -> tuple[str, ...]:
        """Return the vendors for all Lenses."""

        vendors = set(lens.vendor for lens in self._cache.lenses)
        return tuple(sorted(vendors))

    @lru_cache(1)
    def get_lens(self, vendor: str, name: str) -> model.Lens | None:
        """Return a Lens."""

        for lens in self._cache.lenses:
            if lens.vendor == vendor and lens.name == name:
                return lens
        return None

    def get_materials(self) -> tuple[model.Material, ...]:
        """Return all Materials from the database."""

        return self._cache.materials

    def get_material_vendors(self) -> tuple[str, ...]:
        """Return the vendors for all Materials."""

        vendors = set(material.vendor for material in self._cache.materials)
        return tuple(sorted(vendors))

    @lru_cache(100)
    def get_material(
        self, vendor: str, ior: float, abbe: float
    ) -> model.Material | None:
        """
        Return a material from a vendor that is closest to the given ior and abbe nr.
        """

        materials = self._get_materials(vendor)
        array = self._get_material_array(vendor)
        if not materials:
            return None

        # Use the percentage to account for unit differences
        error = 1 - array / np.array((ior, abbe))

        # Use the Euclidean distance to find the closest match
        scores = np.sum(error**2, axis=1)
        index = int(np.argmin(scores))

        return materials[index]

    @lru_cache(1)
    def _get_materials(self, vendor: str) -> tuple[model.Material, ...]:
        """Return all Materials from a vendor."""

        materials = tuple(m for m in self._cache.materials if m.vendor == vendor)
        return materials

    @lru_cache(1)
    def _get_material_array(self, vendor: str) -> np.ndarray:
        """Return an array (ior, abbe) for Materials."""

        array = np.array(tuple((m.ior, m.abbe) for m in self._get_materials(vendor)))
        return array


class CacheStore:
    """Persistence for the aggregated database cache."""

    def __init__(self, cache_path: str) -> None:
        self.cache_path = cache_path

    def save(self, cache: model.Cache) -> None:
        """Save the cache to disk."""

        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)

        data = cache.model_dump_json()
        try:
            with open(self.cache_path, 'w') as f:
                f.write(data)
        except OSError as e:
            logger.error(f'Failed to write cache: {self.cache_path}', exc_info=e)

    def load(self) -> model.Cache | None:
        """Return the Cache from disk."""

        if not os.path.exists(self.cache_path):
            return None

        try:
            with open(self.cache_path, 'r') as f:
                cache = model.Cache.model_validate_json(f.read())
            return cache
        except (OSError, ValueError, pydantic.ValidationError) as e:
            logger.error(f'Failed to read cache: {self.cache_path}', exc_info=e)
            return None
