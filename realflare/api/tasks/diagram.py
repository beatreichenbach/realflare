import logging
from functools import lru_cache

import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from realflare.api import lens as api_lens
from realflare.api.data import Project, LensModel
from realflare.api.tasks.opencl import (
    OpenCL,
    ray_dtype,
    Buffer,
    Image,
    lens_element_dtype,
    intersection_dtype,
)
from realflare.api.tasks.raytracing import RaytracingTask
from realflare.utils.timing import timer

logger = logging.getLogger(__name__)


class DiagramTask(OpenCL):
    def __init__(self, queue) -> None:
        super().__init__(queue)
        self.raytracing_task = RaytracingTask(queue)
        self.kernels = {}
        self.scale = 1
        self.build()

    def build(self, *args, **kwargs) -> None:
        self.source = ''
        self.register_dtype('Ray', ray_dtype)
        self.register_dtype('LensElement', lens_element_dtype)
        self.register_dtype('Intersection', intersection_dtype)
        self.source += self.read_source_file('geometry.cl')
        self.source += self.read_source_file('diagram.cl')
        super().build(*args, **kwargs)
        self.kernels = {
            'intersections': cl.Kernel(self.program, 'intersections'),
            'lenses': cl.Kernel(self.program, 'lenses'),
        }

    @lru_cache(1)
    def update_scale(
        self, resolution: QtCore.QSize, lens_elements: tuple[LensModel.LensElement, ...]
    ) -> float:
        padding = 10  # extra pixels at the end
        distance = 0
        for lens_element in lens_elements:
            distance += lens_element.distance
        if distance == 0:
            scale = 1
        else:
            scale = (resolution.width() - padding) / distance
        return scale

    @lru_cache(1)
    def update_intersection_slice(
        self, intersections: Buffer, column_offset: int
    ) -> Buffer:
        column_count = intersections.array.shape[3]
        column = int((column_count - 1) / 2) + column_offset

        # shape = (path, wavelength, ray.row, ray.column, intersection)
        array = np.ascontiguousarray(
            intersections.array[:, :, :, column : column + 1, :]
        )
        intersection_slice = Buffer(
            self.context, array=array, args=(intersections, column_offset)
        )
        return intersection_slice

    @timer
    @lru_cache(1)
    def intersections(
        self,
        diagram_image: Image,
        intersections: Buffer,
        column_offset: int,
        scale: float,
    ) -> None:
        # rebuild kernel
        if self.rebuild:
            self.build()

        intersection_slice = self.update_intersection_slice(
            intersections, column_offset
        )

        # intersections count
        ray_count = (
            intersection_slice.array.shape[2] * intersection_slice.array.shape[3]
        )
        intersections_count = intersection_slice.array.shape[4]
        # logging.debug(f'{intersections_count:=}')

        # run program
        self.kernels['intersections'].set_arg(0, diagram_image.image)
        self.kernels['intersections'].set_arg(1, intersection_slice.buffer)
        self.kernels['intersections'].set_arg(2, np.int32(intersections_count))
        self.kernels['intersections'].set_arg(3, np.int32(ray_count))
        self.kernels['intersections'].set_arg(4, np.float32(scale))

        h, w = diagram_image.array.shape[:2]
        global_work_size = (w, h)
        local_work_size = None
        cl.enqueue_nd_range_kernel(
            self.queue, self.kernels['intersections'], global_work_size, local_work_size
        )
        # copy device buffer to host
        cl.enqueue_copy(
            self.queue,
            diagram_image.array,
            diagram_image.image,
            origin=(0, 0),
            region=(w, h),
        )

    @lru_cache(1)
    def lenses(
        self,
        diagram_image: Image,
        lens_model: LensModel,
        sensor_size: tuple[float, float],
        glasses_path: str,
        abbe_nr_adjustment: float,
        coating: tuple[int, ...],
        scale: float,
    ):
        # lens elements
        lens_elements = self.raytracing_task.update_lens_elements(
            lens_model,
            sensor_size,
            glasses_path,
            abbe_nr_adjustment,
            coating,
        )
        if len(lens_elements.array) <= 1:
            return

        if self.rebuild:
            self.build()

        # args
        lens_elements_count = len(lens_elements.array)

        # run program
        self.kernels['lenses'].set_arg(0, diagram_image.image)
        self.kernels['lenses'].set_arg(1, lens_elements.buffer)
        self.kernels['lenses'].set_arg(2, np.int32(lens_elements_count))
        self.kernels['lenses'].set_arg(3, np.int32(lens_model.aperture_index))
        self.kernels['lenses'].set_arg(4, np.float32(scale))

        h, w = diagram_image.array.shape[:2]
        global_work_size = (w, h)
        local_work_size = None
        cl.enqueue_nd_range_kernel(
            self.queue,
            self.kernels['lenses'],
            global_work_size,
            local_work_size,
        )

        # copy device buffer to host
        cl.enqueue_copy(
            self.queue,
            diagram_image.array,
            diagram_image.image,
            origin=(0, 0),
            region=(w, h),
        )

    @lru_cache(1)
    def update_image(
        self,
        resolution: QtCore.QSize,
        channel_order: cl.channel_order = cl.channel_order.RGBA,
        flags: cl.mem_flags = cl.mem_flags.WRITE_ONLY,
    ) -> Image:
        return super().update_image(resolution, channel_order, flags)

    @timer
    @lru_cache(1)
    def diagram(
        self,
        resolution: QtCore.QSize,
        lens_model: LensModel,
        sensor_size: tuple[float, float],
        glasses_path: str,
        abbe_nr_adjustment: float,
        coating: tuple[int, ...],
        intersections: Buffer,
        column_offset: int,
    ) -> Image:
        diagram_image = self.update_image(resolution, flags=cl.mem_flags.READ_WRITE)

        diagram_image.args = (
            resolution,
            lens_model,
            sensor_size,
            glasses_path,
            abbe_nr_adjustment,
            coating,
            intersections,
            column_offset,
        )

        scale = self.update_scale(resolution, tuple(lens_model.lens_elements))

        self.lenses(
            diagram_image,
            lens_model,
            sensor_size,
            glasses_path,
            abbe_nr_adjustment,
            coating,
            scale,
        )

        if intersections is not None:
            self.intersections(diagram_image, intersections, column_offset, scale)

        return diagram_image

    def run(self, project: Project, intersections: Buffer) -> Image:
        lens = project.flare.lens
        sensor_size = lens.sensor_size.width(), lens.sensor_size.height()
        lens_model = api_lens.model_from_path(lens.lens_model_path)

        image = self.diagram(
            resolution=project.diagram.resolution,
            lens_model=lens_model,
            sensor_size=sensor_size,
            glasses_path=lens.glasses_path,
            abbe_nr_adjustment=lens.abbe_nr_adjustment,
            coating=lens.coating,
            intersections=intersections,
            column_offset=project.diagram.column_offset,
        )
        return image
