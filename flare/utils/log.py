import logging
import os


def init_logging() -> None:
    """Initialize logging for the package."""

    fmt = '[{asctime}][{levelname: <8}] {message}'
    logging.basicConfig(format=fmt, datefmt='%I:%M:%S%p', style='{', force=True)


def init_rich() -> None:
    """Initialize rich logging for the package."""

    try:
        from rich.logging import RichHandler

        os.environ.setdefault('COLUMNS', '200')
        logging.basicConfig(
            format='%(message)s',
            datefmt='[%X]',
            handlers=[RichHandler()],
            force=True,
        )
    except ImportError:
        pass
