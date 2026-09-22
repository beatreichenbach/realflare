from pathlib import Path

import numpy as np
import OpenEXR  # ty: ignore[unresolved-import]

from flare.engine.outputs.exr import write_multi_part, write_single_part


def test_write_single_part(tmp_path: Path) -> None:
    height, width = 4, 5
    rgba = np.zeros((height, width, 4), np.float32)
    rgba[..., 3] = 1
    flare = np.full((height, width, 4), 0.25, np.float32)

    path = tmp_path / 'image.exr'
    write_single_part({'rgba': rgba, 'flare': flare}, str(path))

    channels = OpenEXR.File(str(path), separate_channels=True).channels()

    assert set(channels) == {
        'rgba.R',
        'rgba.G',
        'rgba.B',
        'rgba.A',
        'flare.R',
        'flare.G',
        'flare.B',
        'flare.A',
    }
    assert channels['flare.R'].pixels.shape == (height, width)
    assert np.allclose(channels['flare.R'].pixels, 0.25)
    assert np.allclose(channels['rgba.A'].pixels, 1.0)


def test_write_multi_part(tmp_path: Path) -> None:
    height, width = 4, 5
    rgba = np.zeros((height, width, 4), np.float32)
    rgba[..., 3] = 1
    flare = np.full((height, width, 4), 0.25, np.float32)

    path = tmp_path / 'parts.exr'
    write_multi_part({'rgba': rgba, 'flare': flare}, str(path))

    parts = {part.name(): part for part in OpenEXR.File(str(path)).parts}

    assert set(parts) == {'rgba', 'flare'}
    pixels = parts['flare'].channels['RGBA'].pixels
    assert pixels.shape == (height, width, 4)
    assert np.allclose(pixels[..., 0], 0.25)
