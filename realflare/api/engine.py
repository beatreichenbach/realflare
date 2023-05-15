import logging
import os
import re
import warnings
from collections import OrderedDict

import cv2
import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from realflare.api.tasks import opencl
from realflare.api.tasks.diagram import DiagramTask
from realflare.api.tasks.preprocessing import PreprocessTask, ImageSamplingTask
from realflare.utils import color

from realflare.api import data
from realflare.api.tasks.aperture import ApertureTask
from realflare.api.tasks.ghost import GhostTask
from realflare.api.tasks.starburst import StarburstTask
from realflare.api.tasks.raytracing import RaytracingTask
from realflare.api.tasks.rasterizing import RasterizingTask
from realflare.api.tasks.compositing import CompositingTask

from realflare.api.data import Project, RenderElement, RenderImage
from realflare.api.tasks.opencl import Image, ImageArray
from realflare.utils.timing import timer


# TODO: check speed for sending large amounts of data through signal
# TODO: can update_element be called inside the task so that it can only be
#  called when there's an update? Right now every result (even if cached) will
#  trigger a signal


logger = logging.getLogger(__name__)


class Engine(QtCore.QObject):
    task_started: QtCore.Signal = QtCore.Signal()
    image_changed: QtCore.Signal = QtCore.Signal(RenderImage)
    render_finished: QtCore.Signal = QtCore.Signal()

    def __init__(self, device: str = '', parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

        self.project: Project | None = None
        self.elements = list[RenderElement]
        self.images: dict[RenderElement, Image] = {}
        self.queue = None

        try:
            self.queue = opencl.queue(device)
            logger.debug(f'Engine initialized on: {self.queue.device.name}')
        except (cl.Error, ValueError) as e:
            logger.error(e)
            return
        self._init_tasks()
        self._init_renderers()

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

    def _init_renderers(self):
        self.renderers = OrderedDict()
        self.renderers[RenderElement.STARBURST_APERTURE] = self.starburst_aperture
        self.renderers[RenderElement.STARBURST] = self.starburst
        self.renderers[RenderElement.GHOST_APERTURE] = self.ghost_aperture
        self.renderers[RenderElement.GHOST] = self.ghost
        self.renderers[RenderElement.FLARE] = self.flare
        self.renderers[RenderElement.DIAGRAM] = self.diagram

    def starburst_aperture(self, project: Project) -> None:
        aperture_config = project.flare.starburst.aperture
        quality_config = project.render.quality.starburst

        image = self.aperture_task.run(aperture_config, quality_config)
        element = RenderImage(RenderElement.STARBURST_APERTURE, image)
        self._update_element(element)

    def starburst(self, project: Project) -> None:
        aperture = self.images[RenderElement.STARBURST_APERTURE]
        image = self.starburst_task.run(project.flare, project.render, aperture)
        element = RenderImage(RenderElement.STARBURST, image)
        self._update_element(element)

    def ghost_aperture(self, project: Project) -> None:
        aperture_config = project.flare.ghost.aperture
        quality_config = project.render.quality.ghost

        image = self.aperture_task.run(aperture_config, quality_config)
        element = RenderImage(RenderElement.GHOST_APERTURE, image)
        self._update_element(element)

    def ghost(self, project: Project) -> None:
        aperture = self.image(RenderElement.GHOST_APERTURE)
        image = self.ghost_task.run(project.flare, project.render, aperture)
        element = RenderImage(RenderElement.GHOST, image)
        self._update_element(element)

    def flare(self, project: Project) -> None:
        if project.render.debug_ghosts:
            path_indexes = (project.render.debug_ghost,)
        else:
            path_indexes = self.preprocess_task.run(project.flare, project.render)

        ghost = self.image(RenderElement.GHOST)

        if project.flare.image_file:
            sample_data = self.image_sampling_task.run(project.flare, project.render)

            if project.flare.image_show_sample:
                image = Image(self.queue.context, array=sample_data)
                element = RenderImage(RenderElement.FLARE, image)
                self._update_element(element)
                return

            height, width, channels = sample_data.shape
            half_width = int(width / 2)
            half_height = int(height / 2)

            image_shape = (
                project.render.quality.resolution.height(),
                project.render.quality.resolution.width(),
                3,
            )
            image_array = np.zeros(image_shape, np.float32)

            for y in range(half_height):
                for x in range(half_width):
                    values = np.float32(
                        [
                            sample_data[y, x],
                            sample_data[height - y - 1, x],
                            sample_data[height - y - 1, width - x - 1],
                            sample_data[y, width - x - 1],
                        ]
                    )
                    if np.sum(values) == 0:
                        continue

                    # get position of center of sample
                    position = QtCore.QPointF(
                        (x + 0.5) / half_width - 1,
                        1 - (y + 0.5) / half_height,
                    )
                    project.flare.light_position = position
                    rays = self.raytracing_task.run(
                        project.flare, project.render, path_indexes
                    )

                    flare = self.rasterizing_task.run(
                        project.flare, project.render, rays, ghost
                    )
                    flare_array = flare.array[:, :, :3]
                    image_array += values[0] * flare_array
                    flare_array = np.flip(flare_array, 0)
                    image_array += values[1] * flare_array
                    flare_array = np.flip(flare_array, 1)
                    image_array += values[2] * flare_array
                    flare_array = np.flip(flare_array, 0)
                    image_array += values[3] * flare_array
            image_array /= width * height

            image = Image(self.queue.context, array=image_array)
        else:
            rays = self.raytracing_task.run(project.flare, project.render, path_indexes)

            image = self.rasterizing_task.run(
                project.flare, project.render, rays, ghost
            )
            # image, image_cl = self.compositing_task.run(
            #     flare_cl, self.starburst_cl, flare_config, render_config
            # )
        element = RenderImage(RenderElement.FLARE, image)
        self._update_element(element)

    def diagram(self, project: Project) -> None:
        project.flare.light_position.setY(project.render.diagram.light_position)
        project.flare.light_position.setX(0)
        project.render.quality.wavelength_count = 1
        project.render.quality.resolution = project.render.diagram.resolution
        project.render.quality.grid_count = project.render.diagram.grid_count
        project.render.quality.grid_length = project.render.diagram.grid_length
        path_indexes = (project.render.diagram.debug_ghost,)

        intersections = self.intersection_task.run(
            project.flare, project.render, path_indexes
        )
        image = self.diagram_task.run(project.flare.lens, project.render, intersections)
        element = RenderImage(RenderElement.DIAGRAM, image)
        self._update_element(element)

    def image(self, element_type: RenderElement) -> Image | ImageArray:
        try:
            return self.images[element_type]
        except KeyError:
            raise KeyError(f'no image stored for render element: {element_type.name}')

    @timer
    def render(self, project: data.Project) -> bool:
        # returns True on success
        # TODO: give feedback with different messages, render_finished when success,
        #  different statuses etc, render_failed if error etc.
        #  this can actually be accomplished with logging messages now.
        #  any output should just be logger.info so it shows up in the logbar

        self.project = project

        # build task queue, a list of all required tasks for the requested outputs
        queue = set(self.elements)
        if RenderElement.FLARE in queue:
            queue.update((RenderElement.GHOST, RenderElement.STARBURST))
        if RenderElement.STARBURST in queue:
            queue.add(RenderElement.STARBURST_APERTURE)
        if RenderElement.GHOST in queue:
            queue.add(RenderElement.GHOST_APERTURE)

        try:
            for element_type, render_func in self.renderers.items():
                if element_type in queue:
                    render_func(project)
        except InterruptedError:
            logger.warning('render interrupted by user')
            return False
        except Exception as e:
            logger.exception(e)
            return False
        except UserWarning as e:
            logger.warning(e)
        finally:
            self.project = None
            self.render_finished.emit()
        return True

    def set_elements(self, elements: list[RenderImage]) -> None:
        self.elements = elements

    def write_image(
        self,
        output_path: str,
        image: Image | None = None,
        array: np.ndarray | None = None,
        colorspace: str = 'ACES - ACEScg',
    ) -> None:
        if not output_path:
            logger.warning('no output path specified')
            return

        # TODO: clean up, image/array etc
        if array is None:
            if image is None:
                try:
                    image = self.images[RenderElement.FLARE]
                except KeyError:
                    logger.warning('RenderElement \'FLARE\' has not been rendered yet')
                    return
            array = image.array

        if not os.path.isdir(os.path.dirname(output_path)):
            os.makedirs(os.path.dirname(output_path))

        array = array.copy()
        array = color.colorspace(array, 'Utility - XYZ - D60', colorspace)

        img_output = cv2.cvtColor(array, cv2.COLOR_RGBA2BGR)
        cv2.imwrite(output_path, img_output)
        logger.info('Output written: {}'.format(output_path))

    @staticmethod
    def parse_output_path(path: str, frame: int) -> str:
        if not path:
            # abspath assumes '' as relative path
            return path
        path = re.sub(r'\$F(\d)?', r'{:0\g<1>d}', path)
        path = path.format(frame)
        path = os.path.abspath(path)
        return path

    def _update_element(self, element: RenderImage) -> None:
        self.images[element.type] = element.image
        if element.type in self.elements:
            self.image_changed.emit(element)


def clear_cache():
    cl.tools.clear_first_arg_caches()
