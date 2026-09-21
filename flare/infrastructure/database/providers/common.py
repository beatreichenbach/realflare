import logging
import os
from collections.abc import Sequence
from typing import TypeVar

from ..parsers import Parser

logger = logging.getLogger(__name__)

T = TypeVar('T')


def load_files(root_dir: str, parsers: Sequence[Parser[T]]) -> tuple[T, ...]:
    """Return objects found by parsing files in the directory."""

    if not root_dir or not os.path.isdir(root_dir):
        logger.warning(f'Invalid directory path: {root_dir!r}')
        return ()

    supported_parsers: dict[str, Parser] = {}
    for parser in parsers:
        for ext in parser.supported_extensions:
            supported_parsers[ext.casefold()] = parser

    objects: list[T] = []
    for vendor in os.listdir(root_dir):
        vendor_dir = os.path.join(root_dir, vendor)
        if not os.path.isdir(vendor_dir):
            continue

        for root, directories, filenames in os.walk(vendor_dir):
            for filename in filenames:
                path = os.path.join(root, filename)
                name, ext = os.path.splitext(filename)
                parser = supported_parsers.get(ext)
                if parser is not None:
                    obj = parser.parse(path)
                    if obj is not None:
                        obj.vendor = vendor
                        objects.append(obj)
    return tuple(objects)
