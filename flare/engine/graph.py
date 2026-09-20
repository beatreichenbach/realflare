import logging

from qtpy import QtGui

from flare import api

from . import outputs, renderers, tasks

logger = logging.getLogger(__name__)


class RenderGraph:
    """
    The RenderGraph stores all tasks and Renderers per QOpenGLContext and handles
    dependencies.
    """

    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        # Tasks
        aperture_task = tasks.ApertureTask(context)
        starburst_task = tasks.StarburstTask(context)
        ghost_task = tasks.GhostTask()
        raytrace_task = tasks.RaytraceTask(context)
        preprocess_task = tasks.PreprocessTask(context)
        flare_task = tasks.FlareTask(context)
        comp_task = tasks.CompTask()
        diagram_task = tasks.DiagramTask(context)

        # Renderers
        starburst_aperture_renderer = renderers.StarburstApertureRenderer(
            context,
            aperture_task,
        )
        starburst_renderer = renderers.StarburstRenderer(
            context, starburst_aperture_renderer, starburst_task
        )
        ghost_aperture_renderer = renderers.GhostApertureRenderer(
            context, aperture_task
        )
        ghost_renderer = renderers.GhostRenderer(
            context, ghost_aperture_renderer, ghost_task
        )
        flare_renderer = renderers.FlareRenderer(
            context, raytrace_task, preprocess_task, flare_task, ghost_renderer
        )
        comp_renderer = renderers.CompRenderer(
            context,
            flare_renderer,
            starburst_renderer,
            comp_task,
        )
        diagram_renderer = renderers.DiagramRenderer(context, diagram_task)

        self.renderers: dict[api.Layer, renderers.Renderer] = {
            api.Layer.STARBURST_APERTURE: starburst_aperture_renderer,
            api.Layer.STARBURST: starburst_renderer,
            api.Layer.GHOST_APERTURE: ghost_aperture_renderer,
            api.Layer.GHOST: ghost_renderer,
            api.Layer.FLARE: flare_renderer,
            api.Layer.COMP: comp_renderer,
            api.Layer.DIAGRAM: diagram_renderer,
        }

        # Outputs
        self.exr_output = outputs.EXROutput()

    def get_renderer(self, layer: api.Layer) -> renderers.Renderer:
        """Return the renderer for a layer."""

        renderer = self.renderers.get(layer)
        if renderer is None:
            raise ValueError(f'no renderer for layer: {layer.value}')
        return renderer
