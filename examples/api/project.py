import logging

from examples import init
from flare.api import Project
from flare.utils import profiling

logger = logging.getLogger(__name__)


def hash_project() -> None:
    with profiling.Timer('Initialize project'):
        project = Project()

    with profiling.Timer('Initial hash'):
        logger.debug(project.__hash__())

    with profiling.Timer('Second hash'):
        logger.debug(project.__hash__())


def main() -> None:
    logging.getLogger().setLevel(logging.DEBUG)
    hash_project()


if __name__ == '__main__':
    init()
    main()
