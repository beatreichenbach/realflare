import dataclasses
import logging

from flare import api

from . import graph
from .base import Array
from .opengl import create_context_surface

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Render:
    image: Array
    layer: api.Layer

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.layer.value!r})'


class Engine:
    def __init__(self) -> None:
        self.context, self.surface = create_context_surface()
        self.graph = graph.RenderGraph(self.context)

    def render(self, project: api.Project, layer: api.Layer) -> Render:
        renderer = self.graph.get_renderer(layer)
        image = renderer.run(project)
        render = Render(image, layer)
        return render

    def output(self, render: Render, project: api.Project) -> str | None:
        if project.output.layer == render.layer and project.output.write:
            if project.output.path.lower().endswith('.exr'):
                path = self.graph.exr_output.write(render.image, project)
            else:
                path = self.graph.image_output.write(render.image, project)
            return path
        return None

    def cleanup(self) -> None:
        logger.debug('Cleaning up ...')

        # TODO: handle cleanup
        # for task in (
        #     self.starburst_aperture_task,
        #     self.starburst_task,
        #     self.ghost_aperture_task,
        #     self.ghost_task,
        #     self.preprocess_task,
        #     self.raytracing_task,
        #     self.flare_task,
        #     self.comp_task,
        #     self.diagram_raytracing_task,
        #     self.diagram_task,
        # ):
        #     task.cleanup()
