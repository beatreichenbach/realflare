import logging
import os
import shutil
import sys
from pathlib import Path

BIN_NAME = 'flare'
BIN_ENV_VAR = 'REALFLARE_BIN'
VENVS = ('venv', '.venv')

logger = logging.getLogger(__name__)


def get_flare_bin() -> str:
    """
    Return the absolute path to the flare binary.

    Resolution order:

    1. The ``REALFLARE_BIN`` environment variable.
    2. The ``venv`` or ``.venv`` environment in the repository root.
    3. The ``PATH`` environment variable.

    :raises FileNotFoundError: If no flare binary can be found.
    """

    env_path = os.environ.get(BIN_ENV_VAR)
    if env_path:
        logger.debug(f'Looking for {BIN_ENV_VAR} at {env_path}')
        if os.path.exists(env_path):
            return os.path.normpath(env_path)
        raise FileNotFoundError(
            f'{BIN_ENV_VAR} is set to {env_path!r}, but no such file exists'
        )

    if sys.platform == 'win32':
        name = f'{BIN_NAME}.exe'
        bin_dir = 'Scripts'
    else:
        name = BIN_NAME
        bin_dir = 'bin'

    for parent in Path(__file__).resolve().parents:
        for venv in VENVS:
            path = parent / venv / bin_dir / name
            logger.debug(f'Looking for {BIN_NAME} at {path}')
            if path.exists():
                return str(path)

    logger.debug(f'Looking for {BIN_NAME} on PATH')
    path = shutil.which(BIN_NAME)
    if path:
        return path

    raise FileNotFoundError(f'could not find the {BIN_NAME!r} binary')
