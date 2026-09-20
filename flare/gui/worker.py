import logging
from collections.abc import Sequence

from qtpy import QtCore

from flare import api
from ..engine.base import EngineError
from flare.engine.engine import Render, Engine

logger = logging.getLogger(__name__)


class Worker(QtCore.QObject):
    rendered = QtCore.Signal(Render)
    progress_changed = QtCore.Signal(float)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

        self._layers = ()
        self._image_hashes: dict[api.Layer, int] = {}

        # Tasks
        self.engine = Engine()
        # self.destroyed.connect(self.engine.cleanup)

    def layers(self) -> tuple[api.Layer, ...]:
        return self._layers

    def set_layers(self, layers: Sequence[api.Layer]) -> None:
        self._image_hashes = {}
        self._layers = layers

    def render(self, project: api.Project) -> None:
        """Render the project."""

        self.progress_changed.emit(-1)
        try:
            # The Viewer has another context that is current.
            self.engine.context.makeCurrent(self.engine.surface)

            for layer in self._layers:
                render = self.engine.render(project, layer)
                self.engine.output(render, project)
                self.emit_render(render)
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
            self.progress_changed.emit(1)

    def emit_render(self, render: Render) -> None:
        """Emit a signal if a Render has changed."""

        image_hash = hash(render.image)
        if self._image_hashes.get(render.layer) != image_hash:
            self._image_hashes[render.layer] = image_hash
            self.rendered.emit(render)
