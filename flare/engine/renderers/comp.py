import logging

from qtpy import QtGui

from flare import api
from flare.utils import profiling

from ..base import MultiArray, Renderer
from ..tasks import CompTask
from .flare import FlareRenderer
from .starburst import StarburstRenderer

logger = logging.getLogger(__name__)


class CompRenderer(Renderer):
    def __init__(
        self,
        context: QtGui.QOpenGLContext,
        flare_renderer: FlareRenderer,
        starburst_renderer: StarburstRenderer,
        comp_task: CompTask,
    ) -> None:
        super().__init__(context)
        self.flare_renderer = flare_renderer
        self.starburst_renderer = starburst_renderer
        self.comp_task = comp_task

    @profiling.timer
    def run(self, project: api.Project) -> MultiArray:
        flare = self.flare_renderer.run(project)
        starburst = self.starburst_renderer.run(project)
        image = self.comp_task.run(flare, starburst)
        layers = {api.Layer.FLARE: flare.array, api.Layer.STARBURST: starburst.array}
        return MultiArray(image.array, image.args, layers)
