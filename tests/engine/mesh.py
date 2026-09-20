import logging

import tests
from flare.engine.tasks.common import DiscMesh

logger = logging.getLogger(__name__)


def test_get_neighbors() -> None:
    neighbors = DiscMesh.get_neighbors(2)
    for row in neighbors:
        logger.info(row)


if __name__ == '__main__':
    tests.init()
    test_get_neighbors()
