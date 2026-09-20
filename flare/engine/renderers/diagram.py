from qtpy import QtGui

from flare import api
from flare.utils import profiling

from ..base import Array
from ..tasks import DiagramTask
from ..tasks.common import GhostData, get_paths
from ..base import Renderer


class DiagramRenderer(Renderer):
    def __init__(
        self, context: QtGui.QOpenGLContext, diagram_task: DiagramTask
    ) -> None:
        super().__init__(context)
        self.diagram_task = diagram_task

    @profiling.timer
    def run(self, project: api.Project) -> Array:

        sensor_size = project.flare.camera.sensor_size.toTuple()
        resolution = project.flare.render.resolution.toTuple()
        position = (0, project.flare.light.position.y())
        wavelength_count = 1

        lens_config = project.flare.lens
        divisions = project.diagram.raytracing.divisions
        isolate = project.diagram.raytracing.ghost

        # lens_model = get_lens(lens_config)
        # ghost_datas = get_ghost_datas(
        #     lens=lens_model,
        #     divisions=divisions,
        #     isolate=isolate,
        # )

        # intersections = self.graph.raytrace_task.run_diagram(
        #     lens_config=project.flare.lens,
        #     sensor_size=sensor_size,
        #     position=position,
        #     resolution=resolution,
        #     wavelength_count=wavelength_count,
        #     ghost_datas=ghost_datas,
        # )
        intersections = None

        diagram = self.diagram_task.run(
            vendor=project.flare.lens.vendor,
            lens=project.flare.lens.lens,
            intersections=intersections,
            resolution=project.diagram.render.resolution,
            lens_config=project.flare.lens,
        )
        return diagram


def get_ghost_datas(
    lens: api.Lens, divisions: int, isolate: int
) -> tuple[GhostData, ...]:

    paths = get_paths(lens.surfaces)

    entrance_surface = lens.surfaces[0]

    ghosts = []
    if isolate < len(paths):
        path = paths[isolate]
        ghost = GhostData(
            path=path,
            divisions=divisions,
            radius=entrance_surface.radius,
        )
        ghosts.append(ghost)

    return tuple(ghosts)
