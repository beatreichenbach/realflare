import logging
import os

import pydantic

from . import model
from .defaults import default_project

logger = logging.getLogger(__name__)


class ProjectIO:
    """Stateless reading and writing of Project files."""

    @staticmethod
    def create() -> model.Project:
        """Return a new Project."""

        return default_project()

    @staticmethod
    def open(path: str) -> model.Project | None:
        """Return the Project from a file, or None if invalid."""

        if not os.path.exists(path):
            logger.warning(f'The file does not exist: {path}')
            return None

        logger.info(f'Opening: {path}')

        try:
            with open(path) as f:
                project = model.Project.model_validate_json(f.read())
        except OSError as e:
            logger.error(f'Could not read file: {path}', exc_info=e)
            return None
        except pydantic.ValidationError as e:
            logger.error(f'Could not load project from file: {path}', exc_info=e)
            return None

        return project

    @staticmethod
    def save(project: model.Project, path: str = '') -> None:
        """Save the Project to a file."""

        logger.info(f'Saving: {path}')

        os.makedirs(os.path.dirname(path), exist_ok=True)

        data = project.model_dump_json(indent=2)
        try:
            with open(path, 'w') as f:
                f.write(data)
        except OSError as e:
            logger.error(f'Could not write file: {path}', exc_info=e)
