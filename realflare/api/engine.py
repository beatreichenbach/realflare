from __future__ import annotations
import logging
import os
from collections import OrderedDict
from functools import lru_cache
from typing import Callable

import cv2
import numpy as np
import pyopencl as cl
import PyOpenColorIO as OCIO
from PySide2 import QtCore

from realflare.api.tasks import opencl
from realflare.api.tasks.diagram import DiagramTask
from realflare.api.tasks.preprocessing import PreprocessTask, ImageSamplingTask
from realflare.storage import Storage

from realflare.api.tasks.aperture import ApertureTask
from realflare.api.tasks.ghost import GhostTask
from realflare.api.tasks.starburst import StarburstTask
from realflare.api.tasks.raytracing import RaytracingTask, IntersectionsTask
from realflare.api.tasks.rasterizing import RasterizingTask
from realflare.api.tasks.compositing import CompositingTask

from realflare.api.data import Project, RenderElement, RenderImage, RealflareError
from realflare.api.tasks.opencl import Image
from realflare.utils.timing import timer

logger = logging.getLogger(__name__)
storage = Storage()

STARBURST_APERTURE = RenderElement.STARBURST_APERTURE
STARBURST = RenderElement.STARBURST
GHOST_APERTURE = RenderElement.GHOST_APERTURE
GHOST = RenderElement.GHOST
FLARE = RenderElement.FLARE
DIAGRAM = RenderElement.DIAGRAM

RENDER_SPACE = 'ACES - ACEScg'


class Engine(QtCore.QObject):
    image_rendered: QtCore.Signal = QtCore.Signal(RenderImage)
    progress_changed: QtCore.Signal = QtCore.Signal(float)

    def __init__(self, device: str = '', parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

        self.queue = opencl.command_queue(device)
        logger.debug(f'engine initialized on device: {self.queue.device.name}')

        self._colorspace_processors = {}
        self.elements = []
        self._init_renderers()
        self._init_tasks()

    def _init_renderers(self) -> None:
        self.renderers: dict[RenderElement, Callable] = OrderedDict()
        self.renderers[STARBURST_APERTURE] = self.starburst_aperture
        self.renderers[GHOST_APERTURE] = self.ghost_aperture
        self.renderers[STARBURST] = self.starburst
        self.renderers[GHOST] = self.ghost
        self.renderers[FLARE] = self.flare
        self.renderers[DIAGRAM] = self.diagram

    def _init_tasks(self) -> None:
        self.aperture_task = ApertureTask(self.queue)
        self.ghost_task = GhostTask(self.queue)
        self.starburst_task = StarburstTask(self.queue)
        self.intersection_task = IntersectionsTask(self.queue)
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
        if project.debug.debug_ghost_enabled:
            path_indexes = (project.debug.debug_ghost,)
        else:
            path_indexes = self.preprocess_task.run(project)
        ghost = self.ghost(project)
        if not project.flare.light.image_file_enabled:
            rays = self.raytracing_task.run(project, path_indexes)
            image = self.rasterizing_task.run(project, rays, ghost)
        else:
            # TODO: extract the logic for image sampling
            sample_data = self.image_sampling_task.run(project)

            if project.debug.show_image:
                image = Image(self.queue.context, array=sample_data)
                return image

            height, width, channels = sample_data.shape
            half_width = int(width / 2)
            half_height = int(height / 2)

            image_shape = (
                project.render.resolution.height(),
                project.render.resolution.width(),
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

                    flare = self.rasterizing_task.run(project, rays, ghost)
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

        # image, image_cl = self.compositing_task.run(
        #     flare_cl, self.starburst_cl, flare_config, render_config
        # )
        return image

    def diagram(self, project: Project) -> Image:
        path_indexes = (project.diagram.debug_ghost,)
        intersections = self.intersection_task.run(project, path_indexes)
        image = self.diagram_task.run(project, intersections)
        return image

    @timer
    def render(self, project: Project) -> bool:
        self.progress_changed.emit(0)
        try:
            for element, renderer in self.renderers.items():
                if element in self.elements:
                    image = renderer(project)
                    self.emit_image(image, element)
                    self.write_image(image, element, project)
        except RealflareError as e:
            logger.error(e)
        except cl.Error as e:
            logger.debug(e)
            logger.error(
                'Render failed. This is most likely because the GPU ran out of memory. '
                'Consider lowering the settings and restarting the engine.'
            )
        except InterruptedError:
            logger.warning('Render interrupted by user')
            return False
        except Exception as e:
            logger.exception(e)
            return False
        finally:
            self.progress_changed.emit(1)
        return True

    def set_elements(self, elements: list[RenderElement]) -> None:
        self.elements = elements
        # clear cache to force updates to viewers
        self.emit_image.cache_clear()

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

        processor = self.colorspace_processor(project.output.colorspace)
        array = image.array.copy()
        if processor:
            processor.applyRGBA(array)

        filename = storage.parse_output_path(project.output.path, project.output.frame)
        try:
            if not os.path.isdir(os.path.dirname(filename)):
                os.makedirs(os.path.dirname(filename))
            image_bgr = cv2.cvtColor(array, cv2.COLOR_RGBA2BGR)
            cv2.imwrite(filename, image_bgr)
            logger.info('image written: {}'.format(filename))
        except (OSError, ValueError, cv2.error) as e:
            logger.debug(e)
            message = f'Error writing file: {filename}'
            raise RealflareError(message) from None

    def colorspace_processor(self, colorspace: str) -> OCIO.CPUProcessor | None:
        cpu_processor = self._colorspace_processors.get(colorspace)
        if cpu_processor is None and colorspace != RENDER_SPACE:
            try:
                config = OCIO.GetCurrentConfig()
                src_colorspace = config.getColorSpace(RENDER_SPACE)
                dst_colorspace = config.getColorSpace(colorspace)
                processor = config.getProcessor(src_colorspace, dst_colorspace)
                cpu_processor = processor.getDefaultCPUProcessor()
                self._colorspace_processors[colorspace] = cpu_processor
            except OCIO.Exception as e:
                logging.debug(e)
                logging.warning(
                    'Failed to initialize color conversion processor.'
                    'The color in the written image will not be accurate.'
                )
        return cpu_processor


def clear_cache() -> None:
    cl.tools.clear_first_arg_caches()
