import logging
import os
import tempfile
import urllib.parse
import zipfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

import requests

from flare.api.lens import Lens, Material

from ..parsers import Parser
from .base import Provider
from .common import load_files

logger = logging.getLogger(__name__)


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

        with tempfile.TemporaryDirectory(prefix='flare_optics_') as temp_dir:
            directory = Path(temp_dir)
            archive = download(self._url, directory)
            root_dir = extract_repo_archive(archive, directory)

            if self._lens_dir and self._lens_parsers:
                lens_dir = root_dir / self._lens_dir
                self._lenses = load_files(str(lens_dir), self._lens_parsers)
            if self._material_dir and self._material_parsers:
                material_dir = root_dir / self._material_dir
                self._materials = load_files(str(material_dir), self._material_parsers)

    def get_lenses(self) -> tuple[Lens, ...]:
        return self._lenses

    def get_materials(self) -> tuple[Material, ...]:
        return self._materials


def download(url: str, dest: os.PathLike[str]) -> Path:
    """
    Download a file into dest and return its local path.

    :raises HTTPError: If one occurred.
    """

    logger.debug(f'Downloading: {url}')

    result = requests.get(url, stream=True, timeout=30)
    result.raise_for_status()

    filename = PurePosixPath(urllib.parse.urlparse(url).path).name or 'archive.zip'
    path = Path(dest) / filename
    with path.open('wb') as file:
        for chunk in result.iter_content(chunk_size=8192):
            file.write(chunk)

    logger.debug(f'Downloaded: {path}')
    return path


def extract_repo_archive(path: os.PathLike[str], dest: os.PathLike[str]) -> Path:
    """Extract a repository archive to dest and return its root directory."""

    path = Path(path)
    destination = Path(dest)

    logger.debug(f'Extracting: {path!r}')

    with zipfile.ZipFile(path, 'r') as file:
        names = file.namelist()
        file.extractall(destination)

    # The root directory is the first directory in the archive.
    tops = {name.split('/', 1)[0] for name in names if name and name != '/'}
    if len(tops) == 1:
        (top,) = tops
        candidate = destination / top
        if candidate.is_dir():
            return candidate
    return destination
