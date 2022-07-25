import dataclasses
import os
import logging
import json
import shutil
from importlib.resources import files
from typing import Any

import typing
from PySide2 import QtWidgets, QtCore, QtGui
import flare
from flare.api.data import Project, Prescription
from qt_extensions.mainwindow import DockWidgetState, SplitterState
from qt_extensions.typeutils import cast, cast_json


@dataclasses.dataclass()
class SettingsConfig:
    window_geometry: QtCore.QRect = QtCore.QRect(200, 200, 1280, 720)
    window_states: list[DockWidgetState | SplitterState | None] = dataclasses.field(
        default_factory=list
    )
    widget_states: dict[str, dict] = dataclasses.field(default_factory=dict)
    recent_paths: list[str] = dataclasses.field(default_factory=list)
    sentry: bool | None = None


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Settings(QtCore.QObject):
    __metaclass__ = Singleton

    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.path = os.getenv('REALFLARE_PATH')
        if self.path is None:
            self.path = os.path.join(os.path.expanduser('~'), f'.{flare.__name__}')

        self.var_paths = {
            '$RES': os.path.join(self.path, 'resources'),
            '$MODEL': os.path.join(self.path, 'resources', 'model'),
            '$GLASS': os.path.join(self.path, 'resources', 'glass'),
            '$APT': os.path.join(self.path, 'resources', 'aperture'),
            '$PRESET': os.path.join(self.path, 'resources', 'preset'),
        }

        self._config_path = os.path.join(self.path, 'settings.json')

        self.config: SettingsConfig | None = None

        self._init_resources()

    def _init_resources(self):
        path = self.var_paths['$RES']
        if os.path.exists(path):
            return

        package_library_path = str(files('flare').joinpath('resources'))
        shutil.copytree(package_library_path, path)

    def load(self):
        data = self.load_data(self._config_path)
        self.config = cast(SettingsConfig, data)

    def save(self):
        data = cast_json(self.config)
        self.save_data(data, self._config_path)

    def load_data(self, path: str) -> dict:
        path = self.decode_path(path)
        if os.path.isfile(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                pass
                # logging.exception(e)
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
                json_data = Settings().load_data(item_path)
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
        if path in self.config.recent_paths:
            self.config.recent_paths.remove(path)
            self.config.recent_paths.insert(0, path)
        else:
            self.config.recent_paths.insert(0, path)

        if len(self.config.recent_paths) > 10:
            self.config.recent_paths = self.config.recent_paths[:10]
