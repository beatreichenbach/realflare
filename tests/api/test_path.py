from pathlib import Path

import pytest

from flare import env
from flare.api import PathParser


def test_format_path_frame(tmp_path: Path) -> None:
    path = PathParser.format_path(str(tmp_path / 'render.$F4.exr'), 12)

    assert path == str(tmp_path / 'render.0012.exr')


def test_format_path_project_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(env.RFP, str(tmp_path))

    path = PathParser.format_path('$RFP/render.$F4.exr', 1)

    assert path == str(tmp_path / 'render.0001.exr')


def test_format_path_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv('MY_OUTPUT', str(tmp_path))

    path = PathParser.format_path('$MY_OUTPUT/image.exr', 1)

    assert path == str(tmp_path / 'image.exr')


def test_format_path_empty() -> None:
    assert PathParser.format_path('', 1) == ''
