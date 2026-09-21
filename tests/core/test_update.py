import shutil
import zipfile
from pathlib import Path

import pytest

from flare.core.update import manager, updater


def make_archive(root: Path, version: str = '2.0.0') -> Path:
    source = root / 'source'
    (source / 'flare').mkdir(parents=True)
    (source / 'flare' / '__init__.py').write_text(f"__version__ = '{version}'")
    (source / 'pyproject.toml').write_text(f'version = "{version}"')

    archive = root / f'archive-{version}.zip'
    with zipfile.ZipFile(archive, 'w') as file:
        for path in source.rglob('*'):
            file.write(path, path.relative_to(root))
    return archive


def make_install(root: Path, version: str = '1.0.0') -> None:
    (root / 'flare').mkdir(parents=True)
    (root / 'flare' / '__init__.py').write_text(f"__version__ = '{version}'")
    (root / 'pyproject.toml').write_text(f'version = "{version}"')
    (root / '.venv').mkdir()
    (root / '.venv' / 'marker').write_text('keep')
    (root / 'custom').mkdir()
    (root / 'custom' / 'data').write_text('keep')


def test_install_root() -> None:
    root = manager.install_root()
    assert root is not None
    assert (root / 'pyproject.toml').exists()


@pytest.mark.skipif(shutil.which('git') is None, reason='git is not installed')
def test_is_git(tmp_path: Path) -> None:
    assert not manager.is_git(tmp_path)
    (tmp_path / '.git').mkdir()
    assert manager.is_git(tmp_path)


def test_validate_invalid(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        updater.validate(tmp_path)


def test_extract(tmp_path: Path) -> None:
    archive = make_archive(tmp_path)
    destination = tmp_path / 'staging'
    destination.mkdir()

    source = updater.extract(archive, destination)

    assert source.name == 'source'
    updater.validate(source)


def test_overlay_preserves(tmp_path: Path) -> None:
    archive = make_archive(tmp_path)
    staging = tmp_path / 'staging'
    staging.mkdir()
    source = updater.extract(archive, staging)

    root = tmp_path / 'install'
    make_install(root)

    updater.overlay(source, root)

    assert '2.0.0' in (root / 'pyproject.toml').read_text()
    assert (root / '.venv' / 'marker').read_text() == 'keep'
    assert (root / 'custom' / 'data').read_text() == 'keep'


def test_apply_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = make_archive(tmp_path)
    root = tmp_path / 'install'
    make_install(root)

    monkeypatch.setattr(updater, 'download', lambda url: archive)

    updater.apply_zip({'root': str(root), 'zip_url': 'https://example.com/x.zip'})

    assert '2.0.0' in (root / 'flare' / '__init__.py').read_text()
    assert '2.0.0' in (root / 'pyproject.toml').read_text()
    assert (root / '.venv' / 'marker').read_text() == 'keep'
    assert (root / 'custom' / 'data').read_text() == 'keep'
    assert not (root / '.flare-backup').exists()
