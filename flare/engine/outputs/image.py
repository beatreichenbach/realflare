import logging
import os.path

import imageio.v3 as iio
import numpy as np
from PIL import Image

from flare import api
from flare.api import PathParser

from ..base import Array, EngineError, Output

logger = logging.getLogger(__name__)


class ImageOutput(Output):
    """Image output for regular formats using imageio."""

    def write(self, image: Array, project: api.Project) -> str:
        path = PathParser.format_path(project.output.path, project.output.frame)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.check_extension(path)
        write_image(path, image.array[::-1, ...])
        logger.info(f'Image written to: {path}')
        return path

    @staticmethod
    def check_extension(path: str) -> None:
        """
        Check that the file extension is supported by Pillow.

        :raises EngineError: If the file extension is not supported.
        """

        extension = os.path.splitext(path)[1].casefold()
        if extension not in Image.registered_extensions():
            raise EngineError(
                f'unsupported image extension: {extension}',
                log=f'Cannot write image with extension {extension}: {path}',
            )


def write_image(path: str, array: np.ndarray) -> None:
    """
    Write an array to an image file using imageio.

    Float arrays are clipped to 0..1 and scaled to uint8, which imageio
    cannot do itself for RGBA data. Alpha is dropped for JPEG, which has
    no alpha channel.

    :raises ValueError: If the array dtype is not supported.
    """

    extension = os.path.splitext(path)[1].casefold()
    if np.issubdtype(array.dtype, np.floating):
        array = (np.clip(array, 0, 1) * 255).astype(np.uint8)
    elif array.dtype != np.uint8 and array.dtype != np.uint16:
        raise ValueError(f'unsupported dtype for image output: {array.dtype}')

    if array.ndim == 3 and array.shape[2] == 4 and extension in ('.jpg', '.jpeg'):
        array = array[:, :, :3]

    iio.imwrite(uri=path, image=array)
