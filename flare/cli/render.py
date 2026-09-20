import json
import logging
import os.path
from typing import Annotated

import typer
from qtpy import QtCore, QtWidgets

from flare import api
from flare.core import PathParser
from flare.engine.engine import Engine

logger = logging.getLogger(__name__)


def render(
    project_path: Annotated[str, typer.Option('--project', '-p')],
    animation_path: Annotated[str, typer.Option('--animation', '-a')],
    output: Annotated[str, typer.Option('--output', '-o')],
) -> None:
    QtWidgets.QApplication()

    if not os.path.exists(project_path):
        logger.error(f'The project file does not exist: {project_path}')
        raise typer.Exit()

    if not os.path.exists(animation_path):
        logger.error(f'The animation file does not exist: {animation_path}')
        raise typer.Exit()

    with open(animation_path, 'r') as file:
        animation = json.load(file)

    project = api.ProjectManager.open(project_path)
    if project is None:
        raise typer.Exit()

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
    processed_frames = 0
    for frame in frames:
        position = positions[frame]
        project.output.path = PathParser.format_path(output, int(frame))
        project.flare.light.position = QtCore.QPointF(*position)

        if intensities:
            intensity = intensities[frame]
            project.flare.light.intensity = intensity

        image_render = engine.render(project, layer)
        engine.output(image_render, project)

        # Update Progress
        processed_frames += 1
        logger.info(f'Rendered Frame {frame} ({processed_frames} / {total_frames})')
