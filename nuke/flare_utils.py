import glob
import json
import os
import re
import subprocess
import sys
import tempfile
from functools import partial
from typing import Callable

import nuke

try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets


GIZMO_CLASS = 'Realflare'
BIN_NAME = 'flare'
READ_NAME = 'Read1'


def get_flare_bin() -> str:
    """Return the absolute path to the binary."""

    # TODO: Remove assumptions about installation method. See README.md
    root = os.path.dirname(os.path.dirname(__file__))
    for venv in ('venv', '.venv'):
        venv_dir = os.path.join(root, venv)
        if sys.platform == 'win32':
            path = os.path.join(venv_dir, 'Scripts', f'{BIN_NAME}.exe')
        else:
            path = os.path.join(venv_dir, 'bin', BIN_NAME)
        if os.path.exists(path):
            return os.path.normpath(path)

    return BIN_NAME


def get_animation_data(node: nuke.Node) -> dict:
    """Return the animation from a node for a given frame range."""

    frame_start = int(node.knob('frame_start').value())
    frame_end = int(node.knob('frame_end').value())
    width = int(node.knob('width').value())
    height = int(node.knob('height').value())
    layer = node.knob('layer').value()
    with node:
        input_node = nuke.toNode('Input1')
        input_width = input_node.width()
        input_height = input_node.height()
    position_knob = node.knob('position')
    intensity_knob = node.knob('intensity')

    positions = {}
    intensities = {}
    for frame in range(frame_start, frame_end + 1):
        position = position_knob.getValueAt(frame)
        x = (position[0] / input_width) * 2.0 - 1.0
        y = (position[1] / input_height) * 2.0 - 1.0
        positions[frame] = (x, y)

        intensity = intensity_knob.getValueAt(frame)
        intensities[frame] = intensity

    data = {
        'layer': layer,
        'position': positions,
        'intensity': intensities,
        'resolution': (width, height),
    }
    return data


def export_data(data: dict) -> str:
    """Export the animation data and return the path."""

    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as file:
        json.dump(data, file, indent=2)
    return file.name


def reload_module() -> None:
    import flare_utils
    from importlib import reload

    reload(flare_utils)


def render() -> None:
    """Render the current node."""

    # TODO: Remove once out of debug hell
    reload_module()

    node = nuke.thisNode()
    render_node(node)


def render_node(node: nuke.Node, callback: Callable | None = None, *_args) -> None:
    """Render the node."""

    app = QtCore.QCoreApplication.instance()
    renderer = Renderer(parent=app)
    renderer.start(node, callback)


def render_selected() -> None:
    """Render the selected nodes."""

    reload_module()

    nodes = nuke.selectedNodes()
    callback = None
    for node in nodes:
        if node.Class() != GIZMO_CLASS:
            continue

        callback = partial(render_node, node, callback)

    if callback:
        callback()


def launch() -> None:
    """Launch the app with the project."""

    node = nuke.thisNode()

    project_path = node.knob('project').value()

    flare_bin = get_flare_bin()
    cmd = [flare_bin, 'gui', '-p', project_path]
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def reload(node: nuke.Node | None = None) -> None:
    """Reload the read node."""

    if node is None:
        node = nuke.thisNode()

    with node:
        read_node = nuke.toNode(READ_NAME)
        if not read_node:
            return

        evaluated_path = read_node.knob('file').evaluate()
        path = get_padded_path(evaluated_path)
        first_frame, last_frame = get_frame_range(path)
        read_node.knob('first').setValue(first_frame)
        read_node.knob('last').setValue(last_frame)
        read_node.knob('reload').execute()


def get_frame_range(path: str) -> tuple[int, int]:
    """Return the frame range of a node's files."""

    clean_path = path.replace('\\', '/')
    glob_pattern = re.sub(r'(#+)|(%\d*d)', '*', clean_path, re.IGNORECASE)
    files = glob.glob(glob_pattern)
    files.sort()
    if not files:
        return 1, 1

    pattern = re.sub(r'\*', r'(\\d+)', glob_pattern)
    first_match = re.search(pattern, files[0].replace('\\', '/'))
    last_match = re.search(pattern, files[-1].replace('\\', '/'))
    if first_match and first_match.groups() and last_match and last_match.groups():
        first_frame = int(first_match.group(1))
        last_frame = int(last_match.group(1))
        return first_frame, last_frame
    else:
        return 1, 1


def get_padded_path(path: str) -> str:
    """Return the best guess for what a path with frame padding might be."""

    # Replace first occurrence, in case second one is a tile.
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


class Worker(QtCore.QThread):
    """
    Background worker thread that runs the CLI command and emits progress signals.
    """

    progress_changed = QtCore.Signal(float)
    message_changed = QtCore.Signal(str)
    finished = QtCore.Signal(int)
    frame_pattern = re.compile(r'frame\s*(\d+)\s*\((\d+) / (\d+)\)', re.IGNORECASE)

    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent)

        self.cmd = None
        self._process = None
        self._is_cancelled = False
        self._animation_path = ''

    def init(self, project_path: str, animation_path: str, output_path: str) -> None:
        """Initialize the command."""

        flare_bin = get_flare_bin()
        self.cmd = [
            *(flare_bin, '-v', 'render'),
            *('-p', project_path),
            *('-a', animation_path),
            *('-o', output_path),
        ]
        self._animation_path = animation_path

    def run(self):
        """Run the render command."""

        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        self._process = subprocess.Popen(
            self.cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )

        try:
            stdout = self._process.stdout
            if stdout:
                for line in iter(self._process.stdout.readline, ''):
                    if self._is_cancelled or not line:
                        break

                    match = self.frame_pattern.search(line.strip())
                    if match:
                        frame = int(match.group(1))
                        processed_frame = int(match.group(2))
                        total_frames = int(match.group(3))
                        if total_frames > 0:
                            progress = min(max(processed_frame / total_frames, 0), 1)
                            self.progress_changed.emit(progress)
                        message = f'Frame {frame} ({processed_frame} of {total_frames})'
                        self.message_changed.emit(message)
                    else:
                        print(line)
            self._process.wait()
        finally:
            if self._process and self._process.stdout:
                self._process.stdout.close()

        if os.path.exists(self._animation_path):
            os.remove(self._animation_path)

        exit_code = self._process.returncode if not self._is_cancelled else -1
        self.finished.emit(exit_code)

    def cancel(self):
        """Terminates the running process safely."""

        self._is_cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()


class Renderer(QtCore.QObject):
    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)

        self.task = None
        self.worker = None
        self.cancel_timer = None
        self.node = None

    def start(self, node: nuke.Node, callback: Callable | None = None) -> None:
        """Start the render task."""

        self.node = node
        self.task = nuke.ProgressTask('Rendering Flare')
        self.task.setMessage('Exporting animation')

        # Parameters
        project_path = node.knob('project').value()
        evaluated_path = node.knob('file').evaluate()
        output_path = get_padded_path(evaluated_path)

        # Export animation data
        data = get_animation_data(node)
        animation_path = export_data(data)

        # Render
        self.task.setMessage('Rendering')

        self.cancel_timer = QtCore.QTimer(self)
        self.cancel_timer.setInterval(200)
        self.cancel_timer.timeout.connect(self.check_cancelled)
        self.cancel_timer.start()

        self.worker = Worker()
        self.worker.progress_changed.connect(self.on_progress)
        self.worker.message_changed.connect(self.on_message)
        self.worker.finished.connect(self.on_finished)
        self.worker.init(project_path, animation_path, output_path)
        self.worker.start()

        if callback:
            self.worker.finished.connect(callback)

    def check_cancelled(self) -> None:
        """Poll ProgressTask for cancellation."""

        if self.task and self.task.isCancelled():
            if self.cancel_timer:
                self.cancel_timer.stop()
            if self.worker:
                self.worker.cancel()

    def on_message(self, message: str) -> None:
        """Handle message update."""

        if self.task:
            self.task.setMessage(message)

    def on_progress(self, percent: float) -> None:
        """Handle progress update."""

        if self.task and percent >= 0:
            progress = int(percent * 100)
            self.task.setProgress(progress)

    def on_finished(self, exit_code: int) -> None:
        """Handle worker being finished."""

        if self.cancel_timer:
            self.cancel_timer.stop()
        if self.worker:
            self.worker.deleteLater()

        self.task = None

        if exit_code > 0:
            nuke.error(f'Task failed with exit code {exit_code}.')

        reload(self.node)

        self.deleteLater()
