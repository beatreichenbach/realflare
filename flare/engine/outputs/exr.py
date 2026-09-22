import logging
import os.path

import numpy as np
import OpenEXR  # ty: ignore[unresolved-import]

from flare import api
from flare.api import PathParser

from ..base import EngineError, MultiArray, Output

logger = logging.getLogger(__name__)


class EXROutput(Output):
    """Image output for .exr files using OpenEXR."""

    def write(self, image: MultiArray, project: api.Project) -> str:
        path = PathParser.format_path(project.output.path, project.output.frame)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        layers = {'rgba': image.array}
        for layer, array in image.layers.items():
            layers[layer.value] = array

        try:
            write_multi_part(layers, path)
        except (ValueError, OpenEXR.error) as e:
            raise EngineError(log='Could not write EXR file.') from e

        logger.info(f'Image written to: {path}')
        return path


def write_single_part(layers: dict[str, np.ndarray], path: str) -> None:
    """
    Write RGBA layers to a single-part EXR file.

    :raises ValueError: if a layer is not RGBA or its shape differs.
    :raises OpenEXR.error: if there is an error while writing the file.
    """

    channels = {}
    planes = _get_image_planes(layers)
    for layer, plane_channels in planes.items():
        for channel, array in plane_channels.items():
            channels[f'{layer}.{channel}'] = array

    if not channels:
        logger.debug('Got no layers, skipping writing file.')
        return

    channels_list = ', '.join(layers)
    logger.debug(f'Writing channels: {channels_list}')

    header = {'compression': OpenEXR.Compression.ZIP_COMPRESSION}
    file = OpenEXR.File(header, channels)
    file.write(path)


def write_multi_part(layers: dict[str, np.ndarray], path: str) -> None:
    """
    Write RGBA layers to a multi-part EXR file, one part per layer.

    :raises ValueError: if a layer is not RGBA or its shape differs.
    :raises OpenEXR.error: if there is an error while writing the file.
    """

    parts = []
    planes = _get_image_planes(layers)
    for layer, plane_channels in planes.items():
        # Each part needs its own header, OpenEXR.Part writes the name into it.
        header = {'compression': OpenEXR.Compression.ZIP_COMPRESSION}
        parts.append(OpenEXR.Part(header, plane_channels, layer))

    if not parts:
        logger.debug('Got no layers, skipping writing file.')
        return

    parts_list = ', '.join(layers)
    logger.debug(f'Writing parts: {parts_list}')

    file = OpenEXR.File(parts)
    file.write(path)


def _get_image_planes(
    layers: dict[str, np.ndarray],
) -> dict[str, dict[str, np.ndarray]]:
    """
    Return each layer split into flipped, contiguous RGBA channel arrays.

    :raises ValueError: if a layer is not RGBA or its shape differs.
    """

    shape = None
    planes = {}
    for layer, array in layers.items():
        # Flip vertically and ensure float32.
        array = np.asarray(array, dtype=np.float32)[::-1, ...]
        if shape is None:
            if array.ndim != 3 or array.shape[2] != 4:
                raise ValueError(f'expected an RGBA array, got shape {array.shape}')
            shape = array.shape
        elif array.shape != shape:
            raise ValueError(
                f'expected layer {layer!r} to match {shape}, got {array.shape}'
            )

        channels = {}
        for i, channel in enumerate('RGBA'):
            channels[channel] = np.ascontiguousarray(array[:, :, i])
        planes[layer] = channels

    return planes
