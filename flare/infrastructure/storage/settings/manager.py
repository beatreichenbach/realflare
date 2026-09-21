import logging
import os
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Generic, TypeVar

import platformdirs
import pydantic

import flare

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

        if not os.path.exists(path):
            return model()

        try:
            with open(path) as file:
                instance = model.model_validate_json(file.read())
            return instance
        except OSError as e:
            logger.warning(f'Could not read file: {path}', exc_info=e)
            return model()
        except (ValueError, pydantic.ValidationError) as e:
            logger.warning(f'Could not load data from file: {path}', exc_info=e)
            return model()

    @classmethod
    def set(cls, model: M) -> None:
        path = cls.path()
        logger.info(f'Saving {model.__class__.__name__}: {path}')

        os.makedirs(os.path.dirname(path), exist_ok=True)

        data = model.model_dump_json(indent=2)
        try:
            with open(path, 'w') as file:
                file.write(data)
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
