import logging

from qtpy import QtGui

from flare import api
from ..base import Array
from flare.utils import profiling
from ..base import Renderer
from ..tasks import ApertureTask

logger = logging.getLogger(__name__)


class GhostApertureRenderer(Renderer):
    def __init__(
        self, context: QtGui.QOpenGLContext, aperture_task: ApertureTask
    ) -> None:
        super().__init__(context)
        self.aperture_task = aperture_task

    @profiling.timer
    def run(self, project: api.Project) -> Array:
        image = self.aperture_task.run(
            aperture=project.ghost.aperture,
            resolution=project.ghost.render.resolution,
        )
        return image


class StarburstApertureRenderer(Renderer):
    def __init__(
        self, context: QtGui.QOpenGLContext, aperture_task: ApertureTask
    ) -> None:
        super().__init__(context)
        self.aperture_task = aperture_task

    @profiling.timer
    def run(self, project: api.Project) -> Array:
        if project.flare.light.position is not None:
            x, y = project.flare.light.position.x(), project.flare.light.position.y()
            parallax = project.starburst.aperture.scratches.parallax
            scratches_parallax = (x * parallax.width(), y * parallax.height())
            parallax = project.starburst.aperture.dust.parallax
            dust_parallax = (x * parallax.width(), y * parallax.height())
        else:
            scratches_parallax = (0, 0)
            dust_parallax = (0, 0)

        image = self.aperture_task.run(
            aperture=project.starburst.aperture,
            resolution=project.starburst.render.resolution,
            scratches_parallax=scratches_parallax,
            dust_parallax=dust_parallax,
        )
        return image
