from collections.abc import Iterator
from pathlib import Path

import PyOpenColorIO as OCIO
import pytest

from flare import ocio


@pytest.fixture(autouse=True)
def clear_cache() -> Iterator[None]:
    ocio.get_config.cache_clear()
    yield
    ocio.get_config.cache_clear()


def test_get_config_fallback() -> None:
    config = ocio.get_config()

    display = config.getDefaultDisplay()
    assert display == 'sRGB - Display'
    assert config.getDefaultView(display) == 'ACES 1.0 - SDR Video'
    assert config.getRoleColorSpace('scene_linear') == 'ACEScg'


def test_get_config_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    name = 'studio-config-v2.2.0_aces-v1.3_ocio-v2.4'
    builtin = OCIO.Config.CreateFromBuiltinConfig(name)
    path = tmp_path / 'config.ocio'
    path.write_text(builtin.serialize())
    monkeypatch.setenv('OCIO', str(path))

    config = ocio.get_config()

    assert config.getName() == name


def test_create_shader_source() -> None:
    source = ocio.create_shader_source()

    assert 'OCIOMain' in source
