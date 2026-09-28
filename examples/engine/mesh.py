import logging

from examples import init
from flare.engine.tasks.common import DiscMesh

logger = logging.getLogger(__name__)


def get_neighbors() -> None:
    neighbors = DiscMesh.get_neighbors(2)
    for row in neighbors:
        logger.info(row)


def main() -> None:
    get_neighbors()


if __name__ == '__main__':
    init()
    main()
