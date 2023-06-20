from __future__ import annotations
import dataclasses
import logging
import os
import sys
from argparse import ArgumentParser
from typing import Any

import pyopencl as cl
from PySide2 import QtCore

from realflare.api.data import Project, RenderElement
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


def exec_(parser: ArgumentParser) -> None:
    args = parser.parse_args(sys.argv[1:])

    logging.basicConfig(level=args.log)

    # set up project
    if not args.project or not os.path.isfile(args.project):
        parser.error(f'project path not valid: {args.project}')
        return
    try:
        data = storage.read_data(args.project)
    except ValueError as e:
        logger.debug(e)
        parser.error(f'project is not valid: {args.project}')
        return

    project = cast(Project, data)

    # update project
    project.output.write = True
    if args.output:
        project.output.path = args.output
    if args.colorspace:
        project.output.colorspace = args.colorspace
    if args.element and args.element in RenderElement.__members__:
        project.output.element = RenderElement[args.element]

    # animation
    animation = None
    if args.animation:
        try:
            animation = storage.read_data(args.animation)
        except ValueError as e:
            logger.debug(e)
            parser.error(f'project is not valid: {args.project}')
            return

    # start application
    QtCore.QCoreApplication()

    # start engine
    device = project.render.device
    try:
        engine = Engine(device)
    except (cl.Error, ValueError) as e:
        parser.error(e)
        return

    engine.set_elements([project.output.element])

    # set values per frame and
    frame_start = args.frame_start
    frame_end = args.frame_end + 1

    for i, frame in enumerate(range(frame_start, frame_end)):
        project.output.frame = frame
        if animation:
            apply_animation(project, animation, i)
        result = engine.render(project)
        if not result:
            parser.error('an error occurred while rendering')
