import dataclasses
import os
import logging
import json
import shutil
from importlib.resources import files
from typing import Any

import realflare
from realflare.api.data import Prescription
from qt_extensions.typeutils import cast, cast_basic


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


@dataclasses.dataclass()
class Settings:
    recent_paths: list[str] = dataclasses.field(default_factory=list)
    sentry: bool | None = None
    ocio: str = ''


@dataclasses.dataclass()
class State:
    window_state: dict = dataclasses.field(default_factory=dict)
    widget_states: dict[str, dict] = dataclasses.field(default_factory=dict)


# TODO: state should not be in here, app.py should register state and
#  settings should be set up in __main__ since it's used by both cli and gui


class Storage:
    __metaclass__ = Singleton

    def __init__(self):
        self.path = os.getenv('REALFLARE_PATH')

        if self.path is None:
            self.path = os.path.join(os.path.expanduser('~'), f'.{realflare.__name__}')

        self.var_paths = {
            '$RES': os.path.join(self.path, 'resources'),
            '$MODEL': os.path.join(self.path, 'resources', 'model'),
            '$GLASS': os.path.join(self.path, 'resources', 'glass'),
            '$APT': os.path.join(self.path, 'resources', 'aperture'),
            '$PRESET': os.path.join(self.path, 'resources', 'preset'),
        }

        self._settings_path = os.path.join(self.path, 'settings.json')
        self._state_path = os.path.join(self.path, 'state.json')

        self.settings: Settings | None = None
        self.state: State | None = None

        self._init_resources()

    def _init_resources(self):
        path = self.var_paths['$RES']
        if os.path.exists(path):
            return

        package_library_path = str(files('realflare').joinpath('resources'))
        shutil.copytree(package_library_path, path)

    def load_settings(self, force=False):
        if self.settings is None or force:
            data = self.load_data(self._settings_path)
            self.settings = cast(Settings, data)

    def save_settings(self) -> bool:
        data = cast_basic(self.settings)
        return self.save_data(data, self._settings_path)

    def load_state(self, force=False):
        if self.state is None or force:
            data = self.load_data(self._state_path)
            self.state = cast(State, data)

    def save_state(self) -> bool:
        data = cast_basic(self.state)
        return self.save_data(data, self._state_path)

    def load_data(self, path: str) -> dict:
        path = self.decode_path(path)
        if os.path.isfile(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                pass
                # logging.exception(e)
                # TODO: error!
        return dict()

    def save_data(self, data: Any, path: str) -> bool:
        path = self.decode_path(path)
        try:
            if not os.path.exists(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            with open(path, 'w') as file:
                json.dump(data, file, indent=2)
            return True
        except FileNotFoundError as exception:
            logging.exception(exception)
        #     TODO: handle error
        return False

    def encode_path(self, path: str) -> str:
        path = os.path.normpath(path)
        for var, var_path in self.var_paths.items():
            path = path.replace(var_path, var)
        path = path.replace('\\', '/')
        return path

    def decode_path(self, path: str) -> str:
        path = os.path.normpath(path)
        for var, var_path in self.var_paths.items():
            path = path.replace(var, var_path)
        path = path.replace('\\', '/')
        return path

    def load_glass_makes(self):
        glasses_path = self.var_paths['$GLASS']
        glass_makes = {}

        for item in os.listdir(glasses_path):
            item_path = os.path.join(glasses_path, item)
            if os.path.isdir(item_path):
                glass_makes[item] = self.encode_path(item_path)
        return glass_makes

    def load_lens_models(self, path: str = '') -> dict | None:
        models_path = self.var_paths['$MODEL']
        if not path:
            path = models_path

        if os.path.isfile(path):
            return

        lens_models = {}
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                if not item.endswith('.json'):
                    continue
                json_data = self.load_data(item_path)
                if not json_data:
                    continue
                prescription = cast(Prescription, json_data)
                lens_models[prescription.name] = self.encode_path(item_path)
            elif os.path.isdir(item_path):
                children = self.load_lens_models(item_path)
                if children:
                    lens_models[item] = children
        return lens_models

    def update_recent_paths(self, path: str) -> None:
        if isinstance(self.settings, Settings):
            if path in self.settings.recent_paths:
                self.settings.recent_paths.remove(path)
                self.settings.recent_paths.insert(0, path)
            else:
                self.settings.recent_paths.insert(0, path)

            if len(self.settings.recent_paths) > 10:
                self.settings.recent_paths = self.settings.recent_paths[:10]
