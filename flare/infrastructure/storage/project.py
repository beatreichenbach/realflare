import logging
import os

import flare
from flare.api.project import model
from flare.api.project.default import default_project

from .jsonfile import read_model, write_model

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
        return read_model(model.Project, path)

    @staticmethod
    def save(project: model.Project, path: str = '') -> None:
        """Save the Project to a file."""

        logger.info(f'Saving: {path}')

        # Insert project version tag to allow for version migration later
        project.version = flare.__version__

        write_model(project, path)
