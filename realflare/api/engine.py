import logging
import os
import re
from collections import OrderedDict

import cv2
import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from realflare.api.tasks import opencl
from realflare.api.tasks.diagram import DiagramTask
from realflare.api.tasks.preprocessing import PreprocessTask
from realflare.utils import color

from realflare.api import data
from realflare.api.tasks.aperture import ApertureTask
from realflare.api.tasks.ghost import GhostTask
from realflare.api.tasks.starburst import StarburstTask
from realflare.api.tasks.raytracing import RaytracingTask
from realflare.api.tasks.rasterizing import RasterizingTask
from realflare.api.tasks.compositing import CompositingTask

from realflare.api.data import Project, RenderElement, Aperture
from realflare.api.tasks.opencl import Image, ImageArray
from realflare.utils.timing import timer


# TODO: check speed for sending large amounts of data through signal
# TODO: figure out a way to only pass arguments that matter so that more things
#       can get cached and tasks don't get run if there won't be a change
# TODO: can update_element be called inside the run task so that it can only be called when there's an update?


# def load_devices():
#     devices = []
#     for platform in cl.get_platforms():
#         devices.extend(platform.get_devices())
#     return devices


class Engine(QtCore.QObject):
    task_started: QtCore.Signal = QtCore.Signal()
    element_changed: QtCore.Signal = QtCore.Signal(RenderElement)
    render_finished: QtCore.Signal = QtCore.Signal()

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

        self.project: Project | None = None
        self.images: dict[RenderElement.Type, Image] = {}
        self.queue = None

        self._init_opencl()

    def _init_opencl(self):
        self.clear_cache()
        self.queue = opencl.queue()
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

    def _init_renderers(self):
        self.renderers = OrderedDict()
        self.renderers[RenderElement.Type.STARBURST_APERTURE] = self.starburst_aperture
        self.renderers[RenderElement.Type.STARBURST] = self.starburst
        self.renderers[RenderElement.Type.GHOST_APERTURE] = self.ghost_aperture
        self.renderers[RenderElement.Type.GHOST] = self.ghost
        self.renderers[RenderElement.Type.FLARE] = self.flare
        self.renderers[RenderElement.Type.DIAGRAM] = self.diagram

    def starburst_aperture(self, project: Project) -> None:
        aperture_config = project.flare.starburst.aperture
        quality_config = project.render.quality.starburst

        image = self.aperture_task.run(aperture_config, quality_config)
        element = RenderElement(RenderElement.Type.STARBURST_APERTURE, image)
        self._update_element(element)

    def starburst(self, project: Project) -> None:
        aperture = self.images[RenderElement.Type.STARBURST_APERTURE]
        image = self.starburst_task.run(project.flare, project.render, aperture)
        element = RenderElement(RenderElement.Type.STARBURST, image)
        self._update_element(element)

    def ghost_aperture(self, project: Project) -> None:
        aperture_config = project.flare.ghost.aperture
        quality_config = project.render.quality.ghost

        image = self.aperture_task.run(aperture_config, quality_config)
        element = RenderElement(RenderElement.Type.GHOST_APERTURE, image)
        self._update_element(element)

    def ghost(self, project: Project) -> None:
        aperture = self.image(RenderElement.Type.GHOST_APERTURE)
        image = self.ghost_task.run(project.flare, project.render, aperture)
        element = RenderElement(RenderElement.Type.GHOST, image)
        self._update_element(element)

    def flare(self, project: Project) -> None:
        if project.render.debug_ghosts:
            path_indexes = (project.render.debug_ghost,)
        else:
            path_indexes = self.preprocess_task.run(project.flare, project.render)

        # logging.debug(path_indexes)
        rays = self.raytracing_task.run(project.flare, project.render, path_indexes)
        ghost = self.image(RenderElement.Type.GHOST)
        image = self.rasterizing_task.run(project.flare, project.render, rays, ghost)
        # image, image_cl = self.compositing_task.run(
        #     flare_cl, self.starburst_cl, flare_config, render_config
        # )
        element = RenderElement(RenderElement.Type.FLARE, image)
        self._update_element(element)

    def diagram(self, project: Project) -> None:
        project.flare.light_position.setY(project.render.diagram.light_position)
        project.flare.light_position.setX(0)
        project.render.quality.wavelength_count = 1
        project.render.quality.resolution = project.render.diagram.resolution
        project.render.quality.grid_count = project.render.diagram.grid_count
        project.render.quality.grid_length = project.render.diagram.grid_length
        project.render.debug_ghost = project.render.diagram.debug_ghost
        project.render.debug_ghosts = True

        intersections = self.intersection_task.run(project.flare, project.render)
        image = self.diagram_task.run(project.flare.lens, project.render, intersections)
        element = RenderElement(RenderElement.Type.DIAGRAM, image)
        self._update_element(element)

    def image(self, element_type: RenderElement.Type) -> Image | ImageArray:
        try:
            return self.images[element_type]
        except KeyError:
            raise KeyError(f'no image stored for render element: {element_type.name}')

    @timer
    def render(self, project: data.Project):
        self.project = project

        # build task queue, a list of all required tasks for the requested outputs
        queue = set(project.elements)
        if RenderElement.Type.FLARE in queue:
            queue.update((RenderElement.Type.GHOST, RenderElement.Type.STARBURST))
        if RenderElement.Type.STARBURST in queue:
            queue.add(RenderElement.Type.STARBURST_APERTURE)
        if RenderElement.Type.GHOST in queue:
            queue.add(RenderElement.Type.GHOST_APERTURE)

        try:
            for element_type, render_func in self.renderers.items():
                if element_type in queue:
                    render_func(project)
                    if self.thread().isInterruptionRequested():
                        raise InterruptedError
        except InterruptedError:
            logging.debug('render interrupted by user')
        except Exception as e:
            logging.exception(e)
        finally:
            self.project = None
            self.render_finished.emit()

    def write_image(
        self,
        output_path: str,
        image: Image | None = None,
        array: np.ndarray | None = None,
        colorspace: str = 'ACES - ACEScg',
    ) -> None:
        # TODO: clean up, image/array etc
        if array is None:
            if image is None:
                try:
                    image = self.images[RenderElement.Type.FLARE]
                except KeyError:
                    raise ValueError(
                        'RenderElement \'FLARE\' has not been rendered yet'
                    )
            array = image.array

        if not output_path:
            raise ValueError('output_path cannot be empty')

        if not os.path.isdir(os.path.dirname(output_path)):
            os.makedirs(os.path.dirname(output_path))

        array = array.copy()
        array = color.colorspace(array, 'Utility - XYZ - D60', colorspace)

        img_output = cv2.cvtColor(array, cv2.COLOR_RGBA2BGR)
        cv2.imwrite(output_path, img_output)
        logging.info('Output written: {}'.format(output_path))

    @staticmethod
    def parse_output_path(path: str, frame: int) -> str:
        path = re.sub(r'\$F(\d)?', r'{:0\g<1>d}', path)
        path = path.format(frame)
        path = os.path.abspath(path)
        return path

    @staticmethod
    def clear_cache():
        cl.tools.clear_first_arg_caches()

    def _update_element(self, element: RenderElement) -> None:
        self.images[element.type] = element.image
        if element.type in self.project.elements:
            self.element_changed.emit(element)
