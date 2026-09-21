import logging
import os.path

import Imath
import numpy as np
import OpenEXR  # ty: ignore[unresolved-import]

from flare import api
from flare.api import PathParser

from ..base import Array, Output

logger = logging.getLogger(__name__)


class EXROutput(Output):
    """Image output for .exr files using OpenEXR."""

    def write(self, image: Array, project: api.Project) -> str:
        path = PathParser.format_path(project.output.path, project.output.frame)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_image(path, image.array[::-1, ...])
        logger.info(f'Image written to: {path}')
        return path


def write_image(path: str, array: np.ndarray) -> None:
    """
    Write an RGBA float array to a single-part EXR file.

    :raises ValueError: If the array is not RGBA float.
    """

    array = np.ascontiguousarray(array, dtype=np.float32)
    if array.ndim != 3 or array.shape[2] != 4:
        raise ValueError(f'expected an RGBA array, got shape {array.shape}')

    height, width, _ = array.shape
    box = Imath.Box2i(Imath.V2i(0, 0), Imath.V2i(width - 1, height - 1))
    header = {
        'compression': Imath.Compression(Imath.Compression.ZIP_COMPRESSION),
        'dataWindow': box,
        'displayWindow': box,
        'channels': {
            name: Imath.Channel(Imath.PixelType(Imath.PixelType.FLOAT))
            for name in ('R', 'G', 'B', 'A')
        },
    }
    pixels = {name: array[:, :, i].tobytes() for i, name in enumerate('RGBA')}

    output = OpenEXR.OutputFile(path, header)
    output.writePixels(pixels)
    output.close()
