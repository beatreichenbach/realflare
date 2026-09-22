import logging

from qtpy import QtGui

from flare import api
from flare.utils import profiling

from ..base import MultiArray, Renderer
from ..tasks import FlareTask, PreprocessTask, RaytraceTask
from .ghost import GhostRenderer

logger = logging.getLogger(__name__)


class FlareRenderer(Renderer):
    def __init__(
        self,
        context: QtGui.QOpenGLContext,
        raytrace_task: RaytraceTask,
        preprocess_task: PreprocessTask,
        flare_task: FlareTask,
        ghost_renderer: GhostRenderer,
    ) -> None:
        super().__init__(context)
        self.raytrace_task = raytrace_task
        self.preprocess_task = preprocess_task
        self.flare_task = flare_task
        self.ghost_renderer = ghost_renderer

    @profiling.timer
    def run(self, project: api.Project) -> MultiArray:
        # Preprocess
        position = project.flare.light.position.toTuple()
        sensor_size = project.flare.camera.sensor_size.toTuple()
        resolution = project.flare.render.resolution.toTuple()
        divisions = 16
        wavelength_count = 1

        rays = self.raytrace_task.run_preprocess(
            lens_config=project.flare.lens,
            sensor_size=sensor_size,
            position=position,
            resolution=resolution,
            wavelength_count=wavelength_count,
            divisions=divisions,
            use_aspheric=project.flare.raytracing.use_aspheric,
        )

        debug = project.flare.debug
        isolate_ghost = debug.ghost if debug.ghost_enabled else None

        ghost_datas = self.preprocess_task.run(
            rays=rays,
            lens_config=project.flare.lens,
            divisions=divisions,
            fstop=project.flare.camera.fstop,
            cull_percentage=project.flare.raytracing.cull_percentage,
            min_divisions=project.flare.raytracing.min_divisions,
            max_divisions=project.flare.raytracing.max_divisions,
            isolate_ghost=isolate_ghost,
        )

        # Raytracing
        rays = self.raytrace_task.run_flare(
            lens_config=project.flare.lens,
            sensor_size=sensor_size,
            position=position,
            resolution=resolution,
            wavelength_count=project.flare.raytracing.wavelength_count,
            ghost_datas=ghost_datas,
            use_aspheric=project.flare.raytracing.use_aspheric,
        )

        # Ghost
        ghost = self.ghost_renderer.run(project)

        # Flare
        output = self.flare_task.run(
            camera=project.flare.camera,
            raytracing=project.flare.raytracing,
            render=project.flare.render,
            intensity=project.flare.light.intensity,
            illuminant=project.flare.light.illuminant,
            ghost_datas=ghost_datas,
            rays=rays,
            ghost=ghost,
            wireframe=project.flare.debug.wireframe,
        )

        return MultiArray(output.array, output.args)
