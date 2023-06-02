from __future__ import annotations
import dataclasses
import json
import logging
import os
import sys
import typing
from argparse import ArgumentParser, Namespace

import pyopencl as cl
from PySide2 import QtCore

from realflare.api.data import Project, RenderElement
from realflare.api.engine import Engine
from qt_extensions.typeutils import cast
from realflare.storage import Storage


logger = logging.getLogger(__name__)


def lerp(
    a: float | list[float], b: float | list[float], t: float
) -> float | list[float]:
    if isinstance(a, list) and isinstance(b, list):
        return [lerp(i, j, t) for i, j in zip(a, b)]
    return (1 - t) * a + t * b


def parse_arg_value(value: typing.Any) -> typing.Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value.strip()


def parse_project_args(args: Namespace) -> dict:
    kwargs = {}
    project_args = args.arg or []
    for arg in project_args:
        try:
            key, value_start, value_end = arg.split(' ')
        except ValueError:
            logging.warning(f'failed to parse argument {repr(arg)}')
            continue
        kwargs[key] = (parse_arg_value(value_start), parse_arg_value(value_end))

    return kwargs


def update_project(project: Project, kwargs: dict, frame_time: float):
    for key, (value_start, value_end) in kwargs.items():
        value = lerp(value_start, value_end, frame_time)

        try:
            obj = project
            attrs = key.split('.')
            name = attrs.pop()
            for attr in attrs:
                obj = getattr(obj, attr)

            if dataclasses.is_dataclass(obj):
                fields = {field.name: field.type for field in dataclasses.fields(obj)}
                if name in fields:
                    typ = fields[name]
                    value = cast(typ, value)
            setattr(obj, name, value)
        except AttributeError:
            logging.warning(f'project has no argument with name {repr(key)}')
        except IndexError:
            continue

    return project


def exec_(parser: ArgumentParser) -> None:
    args = parser.parse_args(sys.argv[1:])

    logging.basicConfig(level=args.log)

    # set up project
    if not args.project or not os.path.isfile(args.project):
        parser.error(f'project path not valid: {args.project}')
        return
    storage = Storage()
    try:
        data = storage.read_data(args.project)
    except ValueError as e:
        logger.debug(e)
        parser.error(f'project is not valid: {args.project}')
        return
    project = cast(Project, data)

    project.output.write = True
    if args.output:
        project.output.path = args.output
    if args.colorspace:
        project.output.colorspace = args.colorspace

    kwargs = parse_project_args(args)

    # start application
    QtCore.QCoreApplication()

    # start engine
    device = project.render.device
    try:
        engine = Engine(device)
    except (cl.Error, ValueError) as e:
        parser.error(e)
        return

    engine.set_elements([RenderElement.FLARE])

    # set values per frame and
    frame_start = args.frame_start
    frame_end = args.frame_end + 1

    for frame in range(frame_start, frame_end):
        frame_time = (frame - frame_start) / max(frame_end - 1 - frame_start, 1)
        update_project(project, kwargs, frame_time)
        engine.render(project)
