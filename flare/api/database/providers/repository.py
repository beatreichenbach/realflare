import logging
import os
import shutil
import tempfile
import urllib.parse
import zipfile
from collections.abc import Sequence

import requests

from ..model import Lens, Material
from ..parsers import Parser
from .base import Provider
from .common import load_files

logger = logging.getLogger(__name__)

DEFAULT_URL = 'https://github.com/amegahed/OpticsDatabase/archive/refs/heads/main.zip'
DEFAULT_LENS_SUBDIR = 'Optics/Photography'
DEFAULT_MATERIAL_SUBDIR = 'Materials'
DEFAULT_MATERIAL_VENDORS = ('Cdgm', 'Hikari', 'Hoya', 'Ohara', 'Schott', 'Sumita')


class RepositoryProvider(Provider):
    """Provider that downloads a repository to scan for files."""

    def __init__(
        self,
        url: str,
        lens_dir: str,
        lens_parsers: Sequence[Parser[Lens]],
        material_dir: str,
        material_parsers: Sequence[Parser[Material]],
    ) -> None:
        self._url = url
        self._lens_dir = lens_dir
        self._lens_parsers = lens_parsers
        self._material_dir = material_dir
        self._material_parsers = material_parsers
        self._lenses: tuple[Lens, ...] = ()
        self._materials: tuple[Material, ...] = ()

        self.load()

    def load(self) -> None:
        """Download the repository and load the files from disk."""

        # Download the Repository
        temp_file = download(self._url)
        temp_dir = tempfile.gettempdir()
        extract(temp_file, temp_dir)

        # Load files from disk
        root_dir = None
        for entry in os.listdir(temp_dir):
            path = os.path.join(temp_dir, entry)
            if os.path.isdir(path):
                root_dir = path
                break

        if root_dir:
            if self._lens_dir and self._lens_parsers:
                lens_dir = os.path.join(root_dir, self._lens_dir)
                self._lenses = load_files(lens_dir, self._lens_parsers)
            if self._material_dir and self._material_parsers:
                material_dir = os.path.join(root_dir, self._material_dir)
                self._materials = load_files(material_dir, self._material_parsers)

        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

    def get_lenses(self) -> tuple[Lens, ...]:
        return self._lenses

    def get_materials(self) -> tuple[Material, ...]:
        return self._materials


def download(url: str) -> str:
    """
    Return the local path of a downloaded file.

    :raises HTTPError: If one occurred.
    """

    logger.debug(f'Downloading: {url}')

    result = requests.get(url, stream=True, timeout=30)
    result.raise_for_status()

    path = urllib.parse.urlparse(url).path
    name, ext = os.path.splitext(path)

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    with open(temp_file.name, 'wb') as file:
        for chunk in result.iter_content(chunk_size=8192):
            file.write(chunk)

    logger.debug(f'Downloaded: {temp_file.name}')
    return temp_file.name


def extract(path: str, dest: str) -> None:
    """Extract a zip file to dest."""

    logger.debug(f'Extracting: {path}')

    with zipfile.ZipFile(path, 'r') as file:
        file.extractall(dest)

    logger.debug(f'Extracted: {dest}')
