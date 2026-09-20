import logging

import tests
from flare.api import Project
from flare.utils import profiling

logger = logging.getLogger(__name__)


def test_hash_project() -> None:
    with profiling.Timer('Initialize project'):
        project = Project()

    with profiling.Timer('Initial hash'):
        logger.debug(project.__hash__())

    with profiling.Timer('Second hash'):
        logger.debug(project.__hash__())


if __name__ == '__main__':
    tests.init()
    logging.getLogger().setLevel(logging.DEBUG)
    test_hash_project()
