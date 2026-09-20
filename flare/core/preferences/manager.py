from __future__ import annotations

import logging
import os
from abc import ABC
from functools import lru_cache
from typing import TypeVar

import platformdirs
import pydantic

import flare
from .model import Preferences, State

logger = logging.getLogger(__name__)

M = TypeVar('M', bound=pydantic.BaseModel)


class JSONManager(ABC):
    filename: str

    @classmethod
    def get(cls) -> M:
        return cls._get(pydantic.BaseModel)

    @classmethod
    def _get(cls, model: type[M]) -> M:
        path = cls.path()
        logger.info(f'Loading {model.__name__}: {path}')

        if not os.path.exists(path):
            return model()

        try:
            with open(path, 'r') as f:
                instance = model.model_validate_json(f.read())
            return instance
        except OSError as e:
            logger.warning(f'Could not read file: {path}', exc_info=e)
            return model()
        except (ValueError, pydantic.ValidationError) as e:
            logger.warning(f'Could not load data from file: {path}', exc_info=e)
            return model()

    @classmethod
    def set(cls, model: pydantic.BaseModel) -> None:
        path = cls.path()
        logger.info(f'Saving {model.__class__.__name__}: {path}')

        os.makedirs(os.path.dirname(path), exist_ok=True)

        data = model.model_dump_json(indent=2)
        try:
            with open(path, 'w') as f:
                f.write(data)
        except OSError as e:
            logger.error(f'Could not write file: {path}', exc_info=e)

    @classmethod
    def reset(cls) -> None:
        path = cls.path()
        if os.path.exists(path):
            os.remove(path)

    @classmethod
    def path(cls) -> str:
        filename = cls.filename
        config_dir = platformdirs.user_config_dir(flare.__name__)
        path = os.path.join(config_dir, filename)
        return path


class PreferencesManager(JSONManager):
    filename = 'preferences.json'

    @classmethod
    @lru_cache(1)
    def get(cls) -> Preferences:
        return cls._get(Preferences)

    @classmethod
    def set(cls, preferences: Preferences) -> None:
        cls.get.clear_cache()
        return super().set(preferences)


class StateManager(JSONManager):
    filename = 'state.json'

    @classmethod
    def get(cls) -> State:
        return cls._get(State)

    @classmethod
    def set(cls, state: State) -> None:
        return super().set(state)
