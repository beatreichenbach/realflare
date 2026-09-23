import json
import os
import re
import subprocess
import tempfile
from typing import IO, Any, NamedTuple

import nuke

from .qt import QtCore
from .utils import get_knob, get_padded_path


class RenderPaths(NamedTuple):
    project: str
    animation: str
    output: str


def export_data(data: dict[str, Any]) -> str:
    """Export the animation data and return the path."""

    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as file:
        json.dump(data, file, indent=2)
    return file.name


def export_render_paths(node: nuke.Node) -> RenderPaths:
    """Return the project, animation and output paths for a node."""

    project_path = get_knob(node, 'project').value()
    file_knob = get_knob(node, 'file', nuke.File_Knob)
    output_path_value = file_knob.evaluate() or ''
    output_path = get_padded_path(output_path_value)
    animation_path = export_data(get_animation_data(node))

    return RenderPaths(project_path, animation_path, output_path)


def get_animation_data(node: nuke.Node) -> dict[str, Any]:
    """Return the animation from a node for a given frame range."""

    frame_start = int(get_knob(node, 'frame_start').value())
    frame_end = int(get_knob(node, 'frame_end').value())
    width = int(get_knob(node, 'width').value())
    height = int(get_knob(node, 'height').value())
    layer_name = get_knob(node, 'layer').value()
    layer = layer_name.lower().replace(' ', '_')
    with node:  # ty: ignore[invalid-context-manager]
        input_node = nuke.toNode('Input1')
        if input_node is None:
            raise ValueError(f'node {node.name()!r} has no input')
        input_width = input_node.width()
        input_height = input_node.height()
    position_knob = get_knob(node, 'position')
    intensity_enabled = bool(get_knob(node, 'intensity_enabled').value())

    positions: dict[int, tuple[float, float]] = {}
    for frame in range(frame_start, frame_end + 1):
        position = position_knob.getValueAt(frame)
        x = (position[0] / input_width) * 2.0 - 1.0
        y = (position[1] / input_height) * 2.0 - 1.0
        positions[frame] = (x, y)

    data: dict[str, Any] = {
        'layer': layer,
        'position': positions,
        'resolution': (width, height),
    }

    if intensity_enabled:
        intensity_knob = get_knob(node, 'intensity')
        intensities: dict[int, float] = {}
        for frame in range(frame_start, frame_end + 1):
            intensities[frame] = intensity_knob.getValueAt(frame)
        data['intensity'] = intensities

    return data


class Worker(QtCore.QThread):
    """
    Background worker thread that runs the CLI command and emits progress signals.
    """

    progress_changed = QtCore.Signal(float)
    message_changed = QtCore.Signal(str)
    finished = QtCore.Signal(int)
    frame_pattern = re.compile(r'frame\s*(\d+)\s*\((\d+) / (\d+)\)', re.IGNORECASE)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

        self.cmd: list[str] = []
        self._process: subprocess.Popen[str] | None = None
        self._is_cancelled = False
        self._animation_path = ''

    def init(self, flare_bin: str, paths: RenderPaths) -> None:
        """Initialize the command."""

        self.cmd = [
            *(flare_bin, '-v', 'render'),
            *('-p', paths.project),
            *('-a', paths.animation),
            *('-o', paths.output),
        ]
        self._animation_path = paths.animation

    def run(self) -> None:
        """Run the render command."""

        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        process = subprocess.Popen(
            self.cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        self._process = process

        try:
            self._handle_stdout(process.stdout)
            process.wait()
        finally:
            if process.stdout:
                process.stdout.close()

        if os.path.exists(self._animation_path):
            os.remove(self._animation_path)

        returncode = process.returncode if not self._is_cancelled else -1
        self.finished.emit(returncode or -1)

    def cancel(self) -> None:
        """Terminate the running process safely."""

        self._is_cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def _handle_stdout(self, stdout: IO[str] | None) -> None:
        """Handle the stdout of the process. Update the message and progress."""

        if stdout is None:
            return

        for line in iter(stdout.readline, ''):
            if self._is_cancelled or not line:
                return

            match = self.frame_pattern.search(line.strip())
            if match is None:
                print(line)
                continue

            frame = int(match.group(1))
            processed_frame = int(match.group(2))
            total_frames = int(match.group(3))

            if total_frames > 0:
                progress = min(max(processed_frame / total_frames, 0), 1)
                self.progress_changed.emit(progress)

            message = f'Frame {frame} ({processed_frame} of {total_frames})'
            self.message_changed.emit(message)


class Renderer(QtCore.QObject):
    finished = QtCore.Signal()
    errored = QtCore.Signal(int)
    canceled = QtCore.Signal()

    def __init__(self, flare_bin: str, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent=parent)

        self.flare_bin = flare_bin
        self.task: nuke.ProgressTask | None = None
        self.worker: Worker | None = None
        self.cancel_timer: QtCore.QTimer | None = None
        self.node: nuke.Node | None = None
        self._cancelled = False

    def start(self, node: nuke.Node) -> None:
        """Start the render task."""

        self.node = node
        self.task = nuke.ProgressTask('Rendering Flare')
        self.task.setMessage('Exporting animation')

        try:
            paths = export_render_paths(node)
        except (OSError, ValueError) as e:
            nuke.error(f'Could not render Realflare: {e}')
            self.task = None
            self.deleteLater()
            return

        self.task.setMessage('Rendering')

        self.cancel_timer = QtCore.QTimer(self)
        self.cancel_timer.setInterval(200)
        self.cancel_timer.timeout.connect(self.check_cancelled)
        self.cancel_timer.start()

        self.worker = Worker()
        self.worker.progress_changed.connect(self.on_progress)
        self.worker.message_changed.connect(self.on_message)
        self.worker.finished.connect(self.on_finished)
        self.worker.init(self.flare_bin, paths)
        self.worker.start()

    def check_cancelled(self) -> None:
        """Poll ProgressTask for cancellation."""

        if self.task and self.task.isCancelled():
            self._cancelled = True
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

        if self._cancelled:
            self.canceled.emit()
        elif exit_code > 0:
            nuke.error(f'Task failed with exit code {exit_code}.')
            self.errored.emit(exit_code)
        else:
            from .gizmo import reload

            reload(self.node)
            self.finished.emit()

        self.deleteLater()
