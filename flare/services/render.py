import copy
import logging
from functools import cached_property
from typing import NamedTuple

from qtpy import QtCore

from flare import api
from flare.engine.base import EngineError
from flare.engine.engine import Engine, Render

logger = logging.getLogger(__name__)


class RenderRequest(NamedTuple):
    """A render request of layers for a project."""

    project: api.Project
    layers: tuple[api.Layer, ...]


class RenderController(QtCore.QObject):
    """
    Drive rendering of the current project.

    Queue render requests, run them through the Engine and emit the resulting
    Renders.
    """

    rendered: QtCore.Signal = QtCore.Signal(Render)
    progress_changed: QtCore.Signal = QtCore.Signal(float)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

        self._layers: tuple[api.Layer, ...] = ()
        self._image_hashes: dict[api.Layer, int] = {}
        self._queue: RenderRequest | None = None
        self._rendering = False

    @cached_property
    def engine(self) -> Engine:
        """The render engine, created on first use."""

        return Engine()

    def request(self, request: RenderRequest) -> None:
        """Queue a render request and render until the queue is empty."""

        if request.layers != self._layers:
            self._layers = request.layers
            self._image_hashes = {}

        self._queue = request
        if self._rendering:
            return

        while self._queue is not None:
            request = self._queue
            self._queue = None
            self._render(request)

    def render_to_disk(self, request: RenderRequest) -> None:
        """Render a request and write the output to disk."""

        project = copy.deepcopy(request.project)
        project.output.write = True
        self.request(RenderRequest(project, (project.output.layer,)))

    def _render(self, request: RenderRequest) -> None:
        """Render the layers of a request and emit the results."""

        self._rendering = True
        self.progress_changed.emit(-1)
        try:
            for layer in request.layers:
                render = self.engine.render(request.project, layer)
                self.engine.output(render, request.project)
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
