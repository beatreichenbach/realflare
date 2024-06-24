from __future__ import annotations

import argparse
import dataclasses
import logging
import os
from typing import Any

import pyopencl as cl
from PySide2 import QtCore

from realflare.api.data import Project, RenderElement, RealflareError
from realflare.api.engine import Engine
from realflare.storage import Storage
from qt_extensions.typeutils import cast


logger = logging.getLogger(__name__)
storage = Storage()


def apply_animation(obj: Any, animation: dict, index: int):
    for name, value in animation.items():
        if isinstance(value, list):
            try:
                current_value = value[index]
            except IndexError:
                continue

            if dataclasses.is_dataclass(obj):
                fields = {field.name: field.type for field in dataclasses.fields(obj)}
                if name in fields:
                    typ = fields[name]
                    current_value = cast(typ, current_value)
            setattr(obj, name, current_value)
        else:
            try:
                child = getattr(obj, name)
            except AttributeError:
                continue
            apply_animation(child, value, index)


def render(
    project_path: str,
    animation_path: str = '',
    output_path: str = '',
    colorspace: str = '',
    element: str = '',
    frame_start: int = 1,
    frame_end: int = 1,
) -> None:
    # set up project
    if not project_path or not os.path.isfile(project_path):
        raise RealflareError(f'project path not valid: {project_path}')
    try:
        data = storage.read_data(project_path)
    except ValueError as e:
        logger.debug(e)
        raise RealflareError(f'project is not valid: {project_path}') from None

    project = cast(Project, data)

    # update project
    project.output.write = True
    if output_path:
        project.output.path = output_path
    if colorspace:
        project.output.colorspace = colorspace
    if element and element in RenderElement.__members__:
        project.output.element = RenderElement[element]

    # animation
    animation = None
    if animation_path:
        try:
            animation = storage.read_data(animation_path)
        except ValueError as e:
            logger.debug(e)
            raise RealflareError(f'animation is not valid: {animation_path}') from None

    # start engine
    device = project.render.device
    try:
        logger.debug(f'attempting to start engine on device: {device}')
        engine = Engine()
    except (cl.Error, ValueError) as e:
        raise RealflareError('failed to start engine') from e

    engine.set_elements([project.output.element])

    # set values per frame and
    frame_start = frame_start
    frame_end = frame_end + 1

    for i, frame in enumerate(range(frame_start, frame_end)):
        project.output.frame = frame
        if animation:
            apply_animation(project, animation, i)
        result = engine.render(project)
        if not result:
            raise RealflareError('an error occurred while rendering')


def exec_(args: argparse.Namespace) -> None:
    logging.basicConfig(level=args.log)

    # start application
    QtCore.QCoreApplication()

    render(
        args.project,
        args.animation,
        args.output,
        args.colorspace,
        args.element,
        args.frame_start,
        args.frame_end,
    )
