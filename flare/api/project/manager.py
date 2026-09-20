from __future__ import annotations

import logging
import os

import pydantic

from flare import api

logger = logging.getLogger(__name__)


class ProjectManager:
    @staticmethod
    def create() -> api.Project:
        """Create a new Project."""

        project = api.Project()
        return project

    @staticmethod
    def open(path: str) -> api.Project | None:
        """Open a file and load the Project if it is valid."""

        if not os.path.exists(path):
            logger.warning(f'The file does not exist: {path}')
            return None

        logger.info(f'Opening: {path}')

        try:
            with open(path, 'r') as f:
                project = api.Project.model_validate_json(f.read())
        except OSError as e:
            logger.error(f'Could not read file: {path}', exc_info=e)
        except pydantic.ValidationError as e:
            logger.error(f'Could not load project from file: {path}', exc_info=e)
            return None

        return project

    @staticmethod
    def save(project: api.Project, path: str = '') -> None:
        """Save the Project to a file."""

        logger.info(f'Saving: {path}')

        os.makedirs(os.path.dirname(path), exist_ok=True)

        data = project.model_dump_json(indent=2)
        try:
            with open(path, 'w') as f:
                f.write(data)
        except OSError as e:
            logger.error(f'Could not write file: {path}', exc_info=e)
