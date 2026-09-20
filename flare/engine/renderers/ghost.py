import logging

from qtpy import QtGui

from flare import api
from flare.utils import profiling

from ..base import Array, Renderer
from ..tasks import GhostTask
from .aperture import GhostApertureRenderer

logger = logging.getLogger(__name__)


class GhostRenderer(Renderer):
    def __init__(
        self,
        context: QtGui.QOpenGLContext,
        aperture_renderer: GhostApertureRenderer,
        ghost_task: GhostTask,
    ) -> None:
        super().__init__(context)
        self.aperture_renderer = aperture_renderer
        self.ghost_task = ghost_task

    @profiling.timer
    def run(self, project: api.Project) -> Array:
        aperture = self.aperture_renderer.run(project)
        image = self.ghost_task.run(
            aperture=aperture,
            distance=project.ghost.diffraction.distance,
            vignette=project.ghost.diffraction.vignette,
        )
        return image
