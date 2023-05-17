import logging
import os
from collections import OrderedDict
from functools import lru_cache
from typing import Callable

import cv2
import pyopencl as cl
from PySide2 import QtCore

from realflare.api.tasks import opencl
from realflare.api.tasks.diagram import DiagramTask
from realflare.api.tasks.preprocessing import PreprocessTask, ImageSamplingTask
from realflare.storage import Storage
from realflare.utils import color

from realflare.api.tasks.aperture import ApertureTask
from realflare.api.tasks.ghost import GhostTask
from realflare.api.tasks.starburst import StarburstTask
from realflare.api.tasks.raytracing import RaytracingTask
from realflare.api.tasks.rasterizing import RasterizingTask
from realflare.api.tasks.compositing import CompositingTask

from realflare.api.data import Project, RenderElement, RenderImage
from realflare.api.tasks.opencl import Image


logger = logging.getLogger(__name__)
storage = Storage()

STARBURST_APERTURE = RenderElement.STARBURST_APERTURE
STARBURST = RenderElement.STARBURST
GHOST_APERTURE = RenderElement.GHOST_APERTURE
GHOST = RenderElement.GHOST
FLARE = RenderElement.FLARE
DIAGRAM = RenderElement.DIAGRAM

RENDER_SPACE = 'Utility - XYZ - D60'


class Engine(QtCore.QObject):
    image_rendered: QtCore.Signal = QtCore.Signal(RenderImage)
    progress_changed: QtCore.Signal = QtCore.Signal(float)

    def __init__(self, device: str = '', parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

        self.queue = opencl.command_queue(device)
        logger.debug(f'engine initialized on device: {self.queue.device.name}')

        self.elements = []
        self._init_renderers()
        self._init_tasks()

    def _init_renderers(self):
        self.renderers: dict[RenderElement, Callable] = OrderedDict()
        self.renderers[STARBURST_APERTURE] = self.starburst_aperture
        self.renderers[GHOST_APERTURE] = self.ghost_aperture
        self.renderers[STARBURST] = self.starburst
        self.renderers[GHOST] = self.ghost
        self.renderers[FLARE] = self.flare
        self.renderers[DIAGRAM] = self.diagram

    def _init_tasks(self):
        self.aperture_task = ApertureTask(self.queue)
        self.ghost_task = GhostTask(self.queue)
        self.starburst_task = StarburstTask(self.queue)
        self.intersection_task = RaytracingTask(self.queue, store_intersections=True)
        self.raytracing_task = RaytracingTask(self.queue)
        self.rasterizing_task = RasterizingTask(self.queue)
        self.compositing_task = CompositingTask(self.queue)
        self.diagram_task = DiagramTask(self.queue)
        self.preprocess_task = PreprocessTask(self.queue)
        self.image_sampling_task = ImageSamplingTask(self.queue)

    def starburst_aperture(self, project: Project) -> Image:
        aperture = project.flare.starburst.aperture
        render = project.render.starburst
        image = self.aperture_task.run(aperture, render)
        return image

    def starburst(self, project: Project) -> Image:
        aperture = self.starburst_aperture(project)
        image = self.starburst_task.run(project, aperture)
        return image

    def ghost_aperture(self, project: Project) -> Image:
        aperture = project.flare.ghost.aperture
        render = project.render.ghost
        image = self.aperture_task.run(aperture, render)
        return image

    def ghost(self, project: Project) -> Image:
        aperture = self.ghost_aperture(project)
        image = self.ghost_task.run(project, aperture)
        return image

    def flare(self, project: Project) -> Image:
        if project.debug.debug_ghosts:
            path_indexes = (project.debug.debug_ghost,)
        else:
            path_indexes = self.preprocess_task.run(project)
        ghost = self.ghost(project)
        rays = self.raytracing_task.run(project, path_indexes)
        image = self.rasterizing_task.run(project, rays, ghost)
        # image, image_cl = self.compositing_task.run(
        #     flare_cl, self.starburst_cl, flare_config, render_config
        # )
        return image

    def diagram(self, project: Project) -> Image:
        # TODO: copy project since it's mutable

        project.flare.light_position.setY(project.render.diagram.light_position)
        project.flare.light_position.setX(0)
        project.render.wavelength_count = 1
        project.render.resolution = project.render.diagram.resolution
        project.render.grid_count = project.render.diagram.grid_count
        project.render.grid_length = project.render.diagram.grid_length
        path_indexes = (project.render.diagram.debug_ghost,)

        intersections = self.intersection_task.run(project, path_indexes)
        image = self.diagram_task.run(project, intersections)
        return image

    def render(self, project: Project) -> bool:
        self.progress_changed.emit(0)
        try:
            for element, renderer in self.renderers.items():
                if element in self.elements:
                    image = renderer(project)
                    self.emit_image(image, element)
                    self.write_image(image, element, project)
        except InterruptedError:
            logger.warning('render interrupted by user')
            return False
        except Exception as e:
            logger.exception(e)
            return False
        finally:
            self.progress_changed.emit(100)
        return True

    def set_elements(self, elements: list[RenderElement]) -> None:
        self.elements = elements

    @lru_cache(10)
    def emit_image(self, image: Image, element: RenderElement) -> None:
        render_image = RenderImage(image, element)
        self.image_rendered.emit(render_image)

    # noinspection PyMethodMayBeStatic
    def write_image(
        self, image: Image, element: RenderElement, project: Project, force=False
    ) -> None:
        if not project.output.write:
            return
        if element != project.output.element and not force:
            return

        filename = storage.parse_output_path(project.output.path, project.output.frame)
        if not os.path.isdir(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        array = image.array.copy()
        array = color.colorspace(array, RENDER_SPACE, project.output.colorspace)

        image_bgr = cv2.cvtColor(array, cv2.COLOR_RGBA2BGR)
        cv2.imwrite(filename, image_bgr)
        logger.info('image written: {}'.format(filename))


def clear_cache():
    cl.tools.clear_first_arg_caches()


# if project.flare.image_file:
#     sample_data = self.image_sampling_task.run(project.flare, project.render)
#
#     if project.flare.image_show_sample:
#         image = Image(self.queue.context, array=sample_data)
#         element = RenderImage(RenderElement.FLARE, image)
#         self._update_element(element)
#         return
#
#     height, width, channels = sample_data.shape
#     half_width = int(width / 2)
#     half_height = int(height / 2)
#
#     image_shape = (
#         project.render.resolution.height(),
#         project.render.resolution.width(),
#         3,
#     )
#     image_array = np.zeros(image_shape, np.float32)
#
#     for y in range(half_height):
#         for x in range(half_width):
#             values = np.float32(
#                 [
#                     sample_data[y, x],
#                     sample_data[height - y - 1, x],
#                     sample_data[height - y - 1, width - x - 1],
#                     sample_data[y, width - x - 1],
#                 ]
#             )
#             if np.sum(values) == 0:
#                 continue
#
#             # get position of center of sample
#             position = QtCore.QPointF(
#                 (x + 0.5) / half_width - 1,
#                 1 - (y + 0.5) / half_height,
#             )
#             project.flare.light_position = position
#             rays = self.raytracing_task.run(
#                 project.flare, project.render, path_indexes
#             )
#
#             flare = self.rasterizing_task.run(
#                 project.flare, project.render, rays, ghost
#             )
#             flare_array = flare.array[:, :, :3]
#             image_array += values[0] * flare_array
#             flare_array = np.flip(flare_array, 0)
#             image_array += values[1] * flare_array
#             flare_array = np.flip(flare_array, 1)
#             image_array += values[2] * flare_array
#             flare_array = np.flip(flare_array, 0)
#             image_array += values[3] * flare_array
#     image_array /= width * height
#
#     image = Image(self.queue.context, array=image_array)
