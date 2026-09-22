from qtpy import QtGui

from flare import api
from flare.utils import profiling

from ..base import MultiArray, Renderer
from ..tasks import StarburstTask
from .aperture import StarburstApertureRenderer


class StarburstRenderer(Renderer):
    def __init__(
        self,
        context: QtGui.QOpenGLContext,
        aperture_renderer: StarburstApertureRenderer,
        starburst_task: StarburstTask,
    ) -> None:
        super().__init__(context)
        self.aperture_renderer = aperture_renderer
        self.starburst_task = starburst_task

    @profiling.timer
    def run(self, project: api.Project) -> MultiArray:
        aperture = self.aperture_renderer.run(project)

        sensor_size = (
            project.flare.camera.sensor_size.width(),
            project.flare.camera.sensor_size.height(),
        )
        position = project.flare.light.position.x(), project.flare.light.position.y()

        image = self.starburst_task.run(
            aperture=aperture,
            config=project.starburst,
            sensor_size=sensor_size,
            position=position,
            fstop=project.flare.camera.fstop,
            resolution=project.flare.render.resolution,
            illuminant=project.flare.light.illuminant,
        )
        return MultiArray(image.array, image.args)
