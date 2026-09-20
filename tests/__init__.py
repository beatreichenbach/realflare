import logging

import flare
from flare import utils


def init() -> None:
    utils.init_logging()
    utils.init_rich()
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger(flare.__name__).setLevel(logging.DEBUG)
