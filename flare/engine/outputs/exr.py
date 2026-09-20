import logging
import os.path

import imageio.v3 as iio

from flare import api
from flare.core import PathParser

from ..base import Array, Output

logger = logging.getLogger(__name__)


# TODO: https://imageio.readthedocs.io/en/stable/_autosummary/imageio.plugins.freeimage.html
class EXROutput(Output):
    def write(self, image: Array, project: api.Project) -> str:
        path = PathParser.format_path(project.output.path, project.output.frame)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        array = image.array[::-1, ...]
        iio.imwrite(uri=path, image=array)
        logger.info(f'Image written to: {path}')
        return path
