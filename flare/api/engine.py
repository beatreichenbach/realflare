import logging
import os
import re
from collections import OrderedDict

import cv2
import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from flare.api.tasks.diagram import DiagramTask
from flare.utils import color

from flare.api import data
from flare.api.tasks.aperture import ApertureTask
from flare.api.tasks.ghost import GhostTask
from flare.api.tasks.starburst import StarburstTask
from flare.api.tasks.raytracing import RaytracingTask
from flare.api.tasks.rasterizing import RasterizingTask
from flare.api.tasks.compositing import CompositingTask

from flare.api.data import Project, RenderElement, Aperture
from flare.api.tasks.opencl import Image
from flare.utils.timing import timer


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

        try:
            self.context = cl.create_some_context(interactive=False)
            self.queue = cl.CommandQueue(self.context)
        except cl.Error as e:
            logging.error(e)
            return

        device = self.queue.device
        if device.type != cl.device_type.GPU:
            e = ValueError(f'realflare is not supported on this device: {device.name}')
            logging.error(e)
            self.queue = None
            return

        # info = cl.device_info
        # logging.debug(f'int.size: {cl.cltypes.int().itemsize}')
        # logging.debug(f'int2.size: {cl.cltypes.int2.itemsize}')
        # logging.debug(f'float.size: {cl.cltypes.float().itemsize}')
        # logging.debug(f'float2.size: {cl.cltypes.float2.itemsize}')
        # logging.debug(f'ulong4.size: {cl.cltypes.ulong4.itemsize}')

        # logging.debug(('MAX_COMPUTE_UNITS', device.get_info(info.MAX_COMPUTE_UNITS)))
        # logging.debug(('MAX_WORK_GROUP_SIZE', device.get_info(info.MAX_WORK_GROUP_SIZE)))
        # logging.debug(('LOCAL_MEM_SIZE', device.get_info(info.LOCAL_MEM_SIZE)))
        # logging.debug(('MAX_MEM_ALLOC_SIZE', device.get_info(info.MAX_MEM_ALLOC_SIZE)))
        # logging.debug(('GLOBAL_MEM_SIZE', device.get_info(info.GLOBAL_MEM_SIZE)))
        # logging.debug(('MAX_CONSTANT_BUFFER_SIZE', device.get_info(info.MAX_CONSTANT_BUFFER_SIZE)))
        # logging.debug(
        #     ('CL_DEVICE_OPENCL_C_VERSION', device.get_info(info.OPENCL_C_VERSION))
        # )

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
        rays = self.raytracing_task.run(project.flare, project.render)

        ghost = self.image(RenderElement.Type.GHOST)
        image = self.rasterizing_task.run(
            rays, ghost, project.flare, project.render.quality
        )
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

    def image(self, element_type: RenderElement.Type) -> Image:
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
