import logging
import os
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Generic, TypeVar

import platformdirs
import pydantic

import flare

from ..jsonfile import read_model, write_model
from .model import Preferences, State

logger = logging.getLogger(__name__)

M = TypeVar('M', bound=pydantic.BaseModel)


class JSONManager(ABC, Generic[M]):
    filename: str

    @classmethod
    @abstractmethod
    def get(cls) -> M:
        raise NotImplementedError

    @classmethod
    def _get(cls, model: type[M]) -> M:
        path = cls.path()
        logger.info(f'Loading {model.__name__}: {path}')

        instance = read_model(model, path)
        if instance is not None:
            return instance
        return model()

    @classmethod
    def set(cls, model: M) -> None:
        path = cls.path()
        logger.info(f'Saving {model.__class__.__name__}: {path}')
        write_model(model, path)

    @classmethod
    def reset(cls) -> None:
        path = cls.path()
        if os.path.exists(path):
            os.remove(path)

    @classmethod
    def path(cls) -> str:
        config_dir = platformdirs.user_config_dir(flare.__name__)
        path = os.path.join(config_dir, cls.filename)
        return path


class PreferencesManager(JSONManager[Preferences]):
    filename = 'preferences.json'

    @classmethod
    @lru_cache(1)
    def get(cls) -> Preferences:
        return cls._get(Preferences)

    @classmethod
    def set(cls, model: Preferences) -> None:
        cls.get.cache_clear()
        return super().set(model)


class StateManager(JSONManager[State]):
    filename = 'state.json'

    @classmethod
    def get(cls) -> State:
        return cls._get(State)

    @classmethod
    def set(cls, model: State) -> None:
        return super().set(model)
