import functools
import json
import logging
import os
import re
import typing

from PySide2 import QtCore, QtWidgets

from realflare.api.data import Project, RenderElement
from realflare.api.engine import Engine
from realflare.gui.settings import Settings
from qt_extensions.typeutils import cast


def rsetattr(obj: object, name: str, value: typing.Any) -> None:
    pre, _, post = name.rpartition('.')
    return setattr(rgetattr(obj, pre) if pre else obj, post, value)


def rgetattr(obj: object, name: str, *args) -> typing.Any:
    def _getattr(obj: object, name: str) -> typing.Any:
        return getattr(obj, name, *args)

    return functools.reduce(_getattr, [obj] + name.split('.'))


def parse_arg_value(value: typing.Any) -> typing.Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value.strip()


def lerp(a: float, b: float, t: float) -> float:
    return (1 - t) * a + t * b


def output_change(self, name, output):
    if output is not None and name == 'flare':
        self.write_output(output)


def exec_(parser):
    # set up project
    if not parser.project or not os.path.isfile(parser.project):
        raise FileNotFoundError(f'project path not valid: {parser.project}')
    project_dict = Settings().load_data(parser.project)
    project = cast(Project, project_dict)

    if parser.output:
        project_dict['render']['output_path'] = parser.output
    if parser.colorspace:
        project_dict['render']['colorspace'] = parser.colorspace

    # parse args
    kwargs = {}
    args = parser.arg or []
    for arg in args:
        try:
            key, value_start, value_end = arg.split(' ')
        except ValueError:
            logging.warning(f'failed to parse argument {repr(arg)}')
            continue

        try:
            # check if attributes exist
            obj = project
            for attr in key.split('.'):
                obj = getattr(obj, attr)

            kwargs[key] = (parse_arg_value(value_start), parse_arg_value(value_end))
        except AttributeError:
            logging.warning(f'project has no argument with name {repr(key)}')

    # start engine
    QtCore.QCoreApplication()
    engine = Engine()

    # set values per frame and
    frame_start = parser.frame_start
    frame_end = parser.frame_end + 1
    for frame in range(frame_start, frame_end):
        frame_time = (frame - frame_start) / max(frame_end - 1 - frame_start, 1)
        for key, (value_start, value_end) in kwargs.items():
            # interpolate values
            if isinstance(value_start, list):
                value = [
                    lerp(value_start[i], value_end[i], frame_time)
                    for i, _ in enumerate(value_start)
                ]
            else:
                value = lerp(value_start, value_end, frame_time)

            # set dict values
            parent_dict = project_dict
            attrs = key.split('.')
            name = attrs.pop()
            for attr in attrs:
                parent_dict = parent_dict[attr]
            parent_dict[name] = value

        # cast to project
        project = cast(Project, project_dict)
        project.elements = [RenderElement.Type.FLARE]
        engine.render(project)
        output_path = engine.parse_output_path(project.render.output_path, frame)
        engine.write_image(output_path, colorspace=project.render.colorspace)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
