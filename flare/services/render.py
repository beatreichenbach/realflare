import copy
import logging
from collections.abc import Sequence

from qtpy import QtCore

from flare import api
from flare.engine.base import EngineError
from flare.engine.engine import Engine, Render

logger = logging.getLogger(__name__)


class RenderController(QtCore.QObject):
    """
    Drive rendering of the current project.

    Queue render requests, run them through the Engine and emit the resulting
    Renders. Setting a new project requests a render of it.
    """

    rendered: QtCore.Signal = QtCore.Signal(Render)
    progress_changed: QtCore.Signal = QtCore.Signal(float)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

        self._project: api.Project | None = None
        self._layers: tuple[api.Layer, ...] = ()
        self._image_hashes: dict[api.Layer, int] = {}
        self._queue: api.Project | None = None
        self._rendering = False

        self.engine = Engine()

    def layers(self) -> tuple[api.Layer, ...]:
        """Return the layers that are rendered."""

        return self._layers

    def set_layers(self, layers: Sequence[api.Layer]) -> None:
        """Set the layers that are rendered."""

        self._image_hashes = {}
        self._layers = tuple(layers)

    def set_project(self, project: api.Project) -> None:
        """Set the current project and request a render."""

        self._project = project
        self._enqueue(project)

    def request(self) -> None:
        """Request a render of the current project."""

        if self._project is not None:
            self._enqueue(self._project)

    def render_to_disk(self) -> None:
        """Render the current project and write the output to disk."""

        if self._project is None:
            return

        project = copy.deepcopy(self._project)
        project.output.write = True
        self._enqueue(project)

    def _enqueue(self, project: api.Project) -> None:
        """Queue a project and render until the queue is empty."""

        self._queue = project
        if self._rendering:
            return

        while self._queue is not None:
            project = self._queue
            self._queue = None
            self._render(project)

    def _render(self, project: api.Project) -> None:
        """Render the layers of a project and emit the results."""

        self._rendering = True
        self.progress_changed.emit(-1)
        try:
            # The Viewer has another context that is current.
            self.engine.context.makeCurrent(self.engine.surface)

            for layer in self._layers:
                render = self.engine.render(project, layer)
                self.engine.output(render, project)
                self._emit_render(render)
        except EngineError as e:
            if e.log:
                logger.error(e.log)
            else:
                logger.error(e)
        except InterruptedError:
            logger.warning('Render interrupted by user')
        except Exception as e:
            logger.exception(e)
        finally:
            self._rendering = False
            self.progress_changed.emit(1)

    def _emit_render(self, render: Render) -> None:
        """Emit a signal if a Render has changed."""

        image_hash = hash(render.image)
        if self._image_hashes.get(render.layer) != image_hash:
            self._image_hashes[render.layer] = image_hash
            self.rendered.emit(render)
