import dataclasses

from flare import api

from . import graph
from .base import Array
from .opengl import create_context_surface


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
        self.context.makeCurrent(self.surface)

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

    def release(self) -> None:
        for task in self.graph.tasks:
            task.release()
