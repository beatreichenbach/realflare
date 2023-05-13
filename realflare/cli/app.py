import dataclasses
import json
import logging
import os
import sys
import typing
from argparse import ArgumentParser, Namespace

from PySide2 import QtCore

from realflare.api.data import Project, RenderElement
from realflare.api.engine import Engine
from realflare.utils.settings import Settings
from qt_extensions.typeutils import cast


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


def exec_(parser: ArgumentParser):
    args = parser.parse_args(sys.argv[1:])

    # set up project
    if not args.project or not os.path.isfile(args.project):
        parser.error(f'project path not valid: {args.project}')
    project_dict = Settings().load_data(args.project)
    project = cast(Project, project_dict)
    project.elements = [RenderElement.Type.FLARE]

    if args.output:
        project.render.output_path = args.output
    if args.colorspace:
        project.render.colorspace = args.colorspace

    kwargs = parse_project_args(args)

    # start application
    QtCore.QCoreApplication()

    # start engine
    device = project.render.system.device
    engine = Engine(device)

    # set values per frame and
    frame_start = args.frame_start
    frame_end = args.frame_end + 1

    try:
        for frame in range(frame_start, frame_end):
            frame_time = (frame - frame_start) / max(frame_end - 1 - frame_start, 1)
            update_project(project, kwargs, frame_time)
            if not engine.render(project):
                continue
            output_path = engine.parse_output_path(project.render.output_path, frame)
            engine.write_image(output_path, colorspace=project.render.colorspace)
    except KeyboardInterrupt:
        parser.error('render interrupted by the user')
