import subprocess
from functools import partial

import nuke

from .binary import get_flare_bin
from .qt import QtCore
from .renderer import Renderer
from .utils import get_frame_range, get_knob, get_padded_path

GIZMO_CLASS = 'Realflare'
READ_NAME = 'Read1'


def launch() -> None:
    """Launch the app with the project."""

    node = nuke.thisNode()
    project_path = get_knob(node, 'project').value()

    flare_bin = find_flare_bin()
    if flare_bin is None:
        return

    try:
        cmd = [flare_bin, 'gui', '-p', project_path]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as e:
        nuke.error(f'Could not launch Realflare: {e}')


def render() -> None:
    """Render the current node."""

    flare_bin = find_flare_bin()
    if flare_bin is None:
        return

    renderer = Renderer(flare_bin, parent=QtCore.QCoreApplication.instance())
    renderer.start(nuke.thisNode())


def render_selected() -> None:
    """Render the selected nodes."""

    flare_bin = find_flare_bin()
    if flare_bin is None:
        return

    nodes = [node for node in nuke.selectedNodes() if node.Class() == GIZMO_CLASS]
    render_next(flare_bin, nodes)


def render_next(flare_bin: str, nodes: list[nuke.Node], index: int = 0) -> None:
    """Render the next node in the sequence."""

    if index >= len(nodes):
        return

    renderer = Renderer(flare_bin, parent=QtCore.QCoreApplication.instance())
    renderer.finished.connect(partial(render_next, flare_bin, nodes, index + 1))
    renderer.start(nodes[index])


def find_flare_bin() -> str | None:
    """Return the path to the flare binary, or report an error if missing."""

    try:
        return get_flare_bin()
    except OSError as e:
        nuke.error(f'Could not find Realflare binary: {e}')
        return None


def reload(node: nuke.Node | None = None) -> None:
    """Reload the read node."""

    if node is None:
        node = nuke.thisNode()

    with node:  # ty: ignore[invalid-context-manager]
        read_node = nuke.toNode(READ_NAME)
        if read_node is None:
            return

        file_knob = get_knob(read_node, 'file', nuke.File_Knob)
        evaluated_path = file_knob.evaluate()
        path = get_padded_path(evaluated_path)
        first_frame, last_frame = get_frame_range(path)
        get_knob(read_node, 'first').setValue(first_frame)
        get_knob(read_node, 'last').setValue(last_frame)
        get_knob(read_node, 'reload', nuke.Script_Knob).execute()
