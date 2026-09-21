import json
import logging
import os.path

from qtpy import QtCore, QtWidgets

from flare import api
from flare.core import PathParser
from flare.engine.engine import Engine

logger = logging.getLogger(__name__)


def run_render(project_path: str, animation_path: str, output: str) -> None:
    """
    Render the frames of an animation to disk.

    :raises FileNotFoundError: If the project or animation file does not exist.
    :raises ValueError: If the project cannot be loaded.
    """

    QtWidgets.QApplication()

    if not os.path.exists(project_path):
        raise FileNotFoundError(f'the project file does not exist: {project_path}')

    if not os.path.exists(animation_path):
        raise FileNotFoundError(f'the animation file does not exist: {animation_path}')

    with open(animation_path) as file:
        animation = json.load(file)

    project = api.ProjectIO.open(project_path)
    if project is None:
        raise ValueError(f'could not load project: {project_path}')

    try:
        layer_name = animation['layer']
        layer = api.Layer(layer_name.lower())
    except (ValueError, KeyError):
        layer = api.Layer.FLARE

    project.output.layer = layer
    project.output.write = True

    resolution = animation.get('resolution')
    if resolution:
        project.flare.render.resolution = QtCore.QSize(*resolution)

    positions = animation['position']
    intensities = animation.get('intensity')

    engine = Engine()

    frames = positions.keys()
    total_frames = len(frames)
    for i, frame in enumerate(frames):
        position = positions[frame]
        project.output.path = PathParser.format_path(output, int(frame))
        project.flare.light.position = QtCore.QPointF(*position)

        if intensities:
            intensity = intensities[frame]
            project.flare.light.intensity = intensity

        image_render = engine.render(project, layer)
        engine.output(image_render, project)

        # Update Progress
        processed_frames = i + 1
        logger.info(f'Rendered Frame {frame} ({processed_frames} / {total_frames})')
