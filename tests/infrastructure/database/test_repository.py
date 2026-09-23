import zipfile
from collections.abc import Sequence
from pathlib import Path

from flare.infrastructure.database.providers.repository import extract_repo_archive


def make_zip(path: Path, files: Sequence[str]) -> None:
    """Create a zip archive with empty files."""

    with zipfile.ZipFile(path, 'w') as file:
        for name in files:
            file.writestr(name, '')


def test_extract_single_root(tmp_path: Path) -> None:
    archive = tmp_path / 'archive.zip'
    make_zip(archive, ['one/a.zmx', 'one/b.mtrl'])

    root = Path(extract_repo_archive(archive, tmp_path))

    assert root == tmp_path / 'one'
    assert (root / 'a.zmx').exists()
    assert (root / 'b.mtrl').exists()


def test_extract_multiple_roots(tmp_path: Path) -> None:
    archive = tmp_path / 'archive.zip'
    make_zip(archive, ['one/a.txt', 'two/b.txt'])

    root = Path(extract_repo_archive(archive, tmp_path))

    assert root == tmp_path
    assert (root / 'one/a.txt').exists()
    assert (root / 'two/b.txt').exists()


def test_extract_no_root(tmp_path: Path) -> None:
    archive = tmp_path / 'archive.zip'
    make_zip(archive, ['a.txt', 'b.txt'])

    root = Path(extract_repo_archive(archive, tmp_path))

    assert root == tmp_path
    assert (root / 'a.txt').exists()
    assert (root / 'b.txt').exists()
