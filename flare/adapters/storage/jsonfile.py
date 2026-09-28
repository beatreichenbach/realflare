import logging
import os
from typing import TypeVar

import pydantic

logger = logging.getLogger(__name__)

M = TypeVar('M', bound=pydantic.BaseModel)


def read_model(model: type[M], path: str) -> M | None:
    """Return the model read from a JSON file, or None if it cannot be read."""

    if not os.path.exists(path):
        return None

    try:
        with open(path) as file:
            return model.model_validate_json(file.read())
    except OSError as e:
        logger.warning(f'Could not read file: {path}', exc_info=e)
        return None
    except (ValueError, pydantic.ValidationError) as e:
        logger.debug(f'Failed to validate data: {path}', exc_info=e)
        logger.warning(f'Could not load data from file: {path}')
        return None


def write_model(model: pydantic.BaseModel, path: str, indent: int | None = 2) -> bool:
    """Write the model as JSON to a path and return whether it succeeded."""

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as file:
            file.write(model.model_dump_json(indent=indent))
    except OSError as e:
        logger.error(f'Could not write file: {path}', exc_info=e)
        return False
    return True
