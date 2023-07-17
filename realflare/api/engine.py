from __future__ import annotations

import logging
import os
from collections import OrderedDict
from typing import Callable

import cv2
import numpy as np
import pyopencl as cl
from PySide2 import QtCore
from pyopencl import tools

from realflare.api.data import Project, RenderElement, RenderImage, RealflareError
from realflare.api.tasks import opencl
from realflare.api.tasks.aperture import GhostApertureTask, StarburstApertureTask
from realflare.api.tasks.diagram import DiagramTask
from realflare.api.tasks.ghost import GhostTask
from realflare.api.tasks.opencl import Image
from realflare.api.tasks.preprocessing import PreprocessTask, ImageSamplingTask
from realflare.api.tasks.rasterizing import RasterizingTask
from realflare.api.tasks.raytracing import RaytracingTask, IntersectionsTask
from realflare.api.tasks.starburst import StarburstTask
from realflare.storage import Storage
from realflare.utils import ocio
from realflare.utils.timing import timer

logger = logging.getLogger(__name__)
storage = Storage()


class Engine(QtCore.QObject):
    image_rendered: QtCore.Signal = QtCore.Signal(RenderImage)
    progress_changed: QtCore.Signal = QtCore.Signal(float)

    def __init__(self, device: str = '', parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

        self.queue = opencl.command_queue(device)
        logger.debug(f'engine initialized on device: {self.queue.device.name}')

        self._emit_cache = {}
        self._elements = []
        self._init_renderers()
        self._init_tasks()

    def _init_renderers(self) -> None:
        self.renderers: dict[RenderElement, Callable] = OrderedDict()
        self.renderers[RenderElement.STARBURST_APERTURE] = self.starburst_aperture
        self.renderers[RenderElement.GHOST_APERTURE] = self.ghost_aperture
        self.renderers[RenderElement.STARBURST] = self.starburst
        self.renderers[RenderElement.GHOST] = self.ghost
        self.renderers[RenderElement.FLARE] = self.flare
        self.renderers[RenderElement.FLARE_STARBURST] = self.flare_starburst
        self.renderers[RenderElement.DIAGRAM] = self.diagram

    def _init_tasks(self) -> None:
        self.ghost_aperture_task = GhostApertureTask(self.queue)
        self.starburst_aperture_task = StarburstApertureTask(self.queue)
        self.ghost_task = GhostTask(self.queue)
        self.starburst_task = StarburstTask(self.queue)
        self.intersection_task = IntersectionsTask(self.queue)
        self.raytracing_task = RaytracingTask(self.queue)
        self.rasterizing_task = RasterizingTask(self.queue)
        self.diagram_task = DiagramTask(self.queue)
        self.preprocess_task = PreprocessTask(self.queue)
        self.image_sampling_task = ImageSamplingTask(self.queue)

    def elements(self) -> list[RenderElement]:
        return self._elements

    def starburst_aperture(self, project: Project) -> Image:
        image = self.starburst_aperture_task.run(project)
        return image

    def starburst(self, project: Project) -> Image:
        aperture = self.starburst_aperture(project)
        image = self.starburst_task.run(project, aperture)
        return image

    def ghost_aperture(self, project: Project) -> Image:
        image = self.ghost_aperture_task.run(project)
        return image

    def ghost(self, project: Project) -> Image:
        aperture = self.ghost_aperture(project)
        image = self.ghost_task.run(project, aperture)
        return image

    def image_flare(self, project: Project, path_indexes: tuple[int]) -> Image:
        ghost = self.ghost(project)
        sample_data = self.image_sampling_task.run(project)

        if project.flare.light.show_image:
            image = Image(self.queue.context, array=sample_data)
            image.args = (project.flare.light, project.render.resolution)
            return image

        height, width, channels = sample_data.shape
        half_width = int(width / 2)
        half_height = int(height / 2)

        image_shape = (
            project.render.resolution.height(),
            project.render.resolution.width(),
            4,
        )
        image_array = np.zeros(image_shape, np.float32)

        args = []

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
                project.flare.light.position.setX((x + 0.5) / half_width - 1)
                project.flare.light.position.setY(1 - (y + 0.5) / half_height)

                rays = self.raytracing_task.run(project, path_indexes)
                flare = self.rasterizing_task.run(project, rays, ghost)

                args = flare.args
                flare_array = flare.array.copy()
                image_array += values[0] * flare_array
                flare_array = np.flip(flare_array, 0)
                image_array += values[1] * flare_array
                flare_array = np.flip(flare_array, 1)
                image_array += values[2] * flare_array
                flare_array = np.flip(flare_array, 0)
                image_array += values[3] * flare_array

        # normalize
        image_array /= width * height

        image = Image(self.queue.context, array=image_array)
        image.args = (*args, project.flare.light)
        return image

    def flare(self, project: Project) -> Image:
        # pre processing
        if project.render.debug_ghost_enabled:
            path_indexes = (project.render.debug_ghost,)
        else:
            path_indexes = self.preprocess_task.run(project)

        # flare
        if not project.flare.light.image_file_enabled:
            ghost = self.ghost(project)
            rays = self.raytracing_task.run(project, path_indexes)
            image = self.rasterizing_task.run(project, rays, ghost)
        else:
            image = self.image_flare(project, path_indexes)

        return image

    def flare_starburst(self, project: Project) -> Image:
        flare = self.flare(project)
        array = flare.array.copy()
        args = flare.args

        if project.flare.light.image_file_enabled:
            logger.warning('Starburst is not yet supported for image based flares.')
        else:
            starburst = self.starburst(project)
            array += flare.array + starburst.array
            args += starburst.args

        image = Image(self.queue.context, array=array, args=args)
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
            for element in self._elements:
                renderer = self.renderers.get(element)
                if renderer:
                    image = renderer(project)
                    self.emit_image(image, element)
                    self.write_image(image, element, project)
        except RealflareError as e:
            logger.error(e)
        except cl.Error as e:
            logger.exception(e)
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
        self._elements = elements
        # clear cache to force updates to viewers
        self._emit_cache = {}

    def emit_image(self, image: Image, element: RenderElement) -> None:
        # emits image_rendered signal if hash for that element has changed
        # one hash per element is stored, so lru_cache is not used here
        _hash = hash(image)
        if self._emit_cache.get(element) != _hash:
            self._emit_cache[element] = _hash
            render_image = RenderImage(image, element)
            self.image_rendered.emit(render_image)

    def write_image(
        self, image: Image, element: RenderElement, project: Project
    ) -> None:
        if not project.output.write or element != project.output.element:
            return

        filename = storage.parse_output_path(project.output.path, project.output.frame)

        if element == RenderElement.FLARE_STARBURST and project.output.split_files:
            words = os.path.basename(filename).split('.')

            # flare
            flare_words = list(words)
            flare_words.insert(1, 'flare')
            basename = '.'.join(flare_words)
            path = os.path.join(os.path.dirname(filename), basename)
            image = self.flare(project)
            write_array(image.array, path, project.output.colorspace)

            # starburst
            starburst_words = list(words)
            starburst_words.insert(1, 'starburst')
            basename = '.'.join(starburst_words)
            path = os.path.join(os.path.dirname(filename), basename)
            image = self.starburst(project)
            write_array(image.array, path, project.output.colorspace)

        else:
            write_array(image.array, filename, project.output.colorspace)


def clear_cache() -> None:
    cl.tools.clear_first_arg_caches()


def write_array(array: np.ndarray, filename: str, colorspace: str) -> None:
    array = array.copy()

    # colorspace
    processor = ocio.colorspace_processor(colorspace)
    if processor:
        processor.applyRGBA(array)

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
