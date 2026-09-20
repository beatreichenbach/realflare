import glob
import os
import re
from typing import TypeVar, overload

import nuke

T = TypeVar('T', bound=nuke.Knob)


@overload
def get_knob(node: nuke.Node, name: str) -> nuke.Knob: ...


@overload
def get_knob(node: nuke.Node, name: str, cls: type[T]) -> T: ...


def get_knob(node: nuke.Node, name: str, cls: type[nuke.Knob] = nuke.Knob) -> nuke.Knob:
    """
    Return the knob with a name, checked against a knob class.

    :raises ValueError: If the node has no knob with the name, or the knob is
        not an instance of the given class.
    """

    knob = node.knob(name)
    if knob is None:
        raise ValueError(f'node {node.name()!r} has no knob {name!r}')
    if not isinstance(knob, cls):
        raise ValueError(f'knob {name!r} is not a {cls.__name__}')
    return knob


def get_frame_range(path: str) -> tuple[int, int]:
    """Return the frame range of a node's files."""

    clean_path = path.replace('\\', '/')
    glob_pattern = re.sub(r'(#+)|(%\d*d)', '*', clean_path, flags=re.IGNORECASE)
    files = glob.glob(glob_pattern)
    files.sort()
    if files:
        pattern = re.sub(r'\*', r'(\\d+)', glob_pattern)
        first_match = re.search(pattern, files[0].replace('\\', '/'))
        last_match = re.search(pattern, files[-1].replace('\\', '/'))
        if first_match and first_match.groups() and last_match and last_match.groups():
            first_frame = int(first_match.group(1))
            last_frame = int(last_match.group(1))
            return first_frame, last_frame
    return 1, 1


def get_padded_path(path: str) -> str:
    """Return the best guess for what a path with frame padding might be."""

    # Replace first occurrence only, in case second one is a tile.
    filename = os.path.basename(path)
    pad_char = '#'
    padded_filename = re.sub(
        r'\.(\d+)\.',
        lambda m: f'.{pad_char * len(m.group(1))}.',
        filename,
        count=1,
    )
    padded_path = os.path.join(os.path.dirname(path), padded_filename)

    return padded_path
