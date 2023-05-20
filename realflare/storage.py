import json
import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any

from qt_extensions.typeutils import cast, cast_basic

import realflare


logger = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class JSONStorage:
    __metaclass__ = Singleton

    # noinspection PyMethodMayBeStatic
    def read_data(self, path: str) -> dict:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except OSError as e:
            raise ValueError from e

    # noinspection PyMethodMayBeStatic
    def write_data(self, data: Any, path: str) -> None:
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, 'w') as file:
            json.dump(data, file, indent=2)


@dataclass()
class Settings:
    sentry: bool | None = None
    ocio: str = ''


@dataclass()
class State:
    window_state: dict = field(default_factory=dict)
    widget_states: dict[str, dict] = field(default_factory=dict)
    recent_paths: list[str] = field(default_factory=list)


class Storage(JSONStorage):
    def __init__(self) -> None:
        super().__init__()

        # path
        self._path = os.getenv('REALFLARE_PATH')
        if self._path is None:
            self._path = os.path.join(os.path.expanduser('~'), f'.{realflare.__name__}')

        # settings
        self._settings_path = os.path.join(self._path, 'settings.json')
        self._settings = None

        # state
        self._state_path = os.path.join(self._path, 'state.json')
        self._state = None

        # path variables
        self.path_vars = {
            '$RES': os.path.join(self._path, 'resources'),
            '$MODEL': os.path.join(self._path, 'resources', 'model'),
            '$GLASS': os.path.join(self._path, 'resources', 'glass'),
            '$APT': os.path.join(self._path, 'resources', 'aperture'),
            '$PRESET': os.path.join(self._path, 'resources', 'preset'),
        }

        # resources
        self.init_resources()

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            try:
                data = self.read_data(self._settings_path)
            except ValueError:
                data = {}
            self._settings = cast(Settings, data)
        return self._settings

    @settings.setter
    def settings(self, value: Settings) -> None:
        self._settings = value

    @property
    def state(self) -> State:
        if self._state is None:
            try:
                data = self.read_data(self._state_path)
            except ValueError:
                data = {}
            self._state = cast(State, data)
        return self._state

    @state.setter
    def state(self, value: State) -> None:
        self._state = value

    def add_recent_path(self, path: str) -> None:
        if isinstance(self.state, State):
            if path in self.state.recent_paths:
                self.state.recent_paths.remove(path)
                self.state.recent_paths.insert(0, path)
            else:
                self.state.recent_paths.insert(0, path)

            if len(self.state.recent_paths) > 10:
                self.state.recent_paths = self.state.recent_paths[:10]

    def decode_path(self, path: str) -> str:
        path = os.path.normpath(path)
        for var, var_path in self.path_vars.items():
            path = path.replace(var, var_path)
        path = path.replace('\\', '/')
        return path

    def encode_path(self, path: str) -> str:
        path = os.path.normpath(path)
        for var, var_path in self.path_vars.items():
            path = path.replace(var_path, var)
        path = path.replace('\\', '/')
        return path

    def init_resources(self) -> None:
        resource_path = self.path_vars['$RES']
        if os.path.exists(resource_path):
            return
        package_resource_path = str(files('realflare').joinpath('resources'))
        shutil.copytree(package_resource_path, resource_path)

    def save_settings(self) -> bool:
        data = cast_basic(self.settings)
        try:
            self.write_data(data, self._settings_path)
        except ValueError:
            return False
        return True

    def save_state(self) -> bool:
        data = cast_basic(self.state)
        try:
            self.write_data(data, self._state_path)
        except ValueError:
            return False
        return True

    # noinspection PyMethodMayBeStatic
    def parse_output_path(self, path: str, frame: int) -> str:
        if not path:
            # abspath assumes '' as relative path
            return path
        path = re.sub(r'\$F(\d)?', r'{:0\g<1>d}', path)
        path = path.format(frame)
        path = os.path.abspath(path)
        return path
