from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from realflare.api import lens as api_lens
from realflare.api.data import LensModel, Project
from realflare.api.tasks.opencl import (
    OpenCL,
    ray_dtype,
    lens_element_dtype,
    intersection_dtype,
    LAMBDA_MIN,
    LAMBDA_MAX,
    Buffer,
)
from realflare.storage import Storage
from realflare.utils.timing import timer

logger = logging.getLogger(__name__)
storage = Storage()


def wavelength_array(wavelength_count: int) -> list[int]:
    array = []
    for i in range(wavelength_count):
        step = (i + 0.5) / wavelength_count
        wavelength = LAMBDA_MIN + step * (LAMBDA_MAX - LAMBDA_MIN)
        array.append(wavelength)
    return array


class RaytracingTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)
        self.kernel = None
        self.build()

    def build(self, *args, **kwargs) -> None:
        self.source = ''
        self.register_dtype('Ray', ray_dtype)
        self.register_dtype('LensElement', lens_element_dtype)
        self.register_dtype('Intersection', intersection_dtype)
        self.source += f'const int LAMBDA_MIN = {LAMBDA_MIN};\n'
        self.source += f'const int LAMBDA_MAX = {LAMBDA_MAX};\n'
        self.source += self.read_source_file('raytracing.cl')
        super().build()
        self.kernel = cl.Kernel(self.program, 'raytrace')

    @lru_cache(1)
    def update_lens_elements(
        self,
        lens_model: LensModel,
        sensor_size: tuple[float, float],
        glasses_path: str,
        abbe_nr_adjustment: float,
        coating: tuple[int, ...],
    ) -> Buffer:
        dtype = self.dtypes['LensElement']
        array = api_lens.elements(
            lens_model, sensor_size, glasses_path, abbe_nr_adjustment, coating, dtype
        )

        buffer = Buffer(
            self.context,
            array=array,
            args=(lens_model, sensor_size, glasses_path, abbe_nr_adjustment, coating),
        )
        return buffer

    @lru_cache(10)
    def update_paths(
        self,
        lens_model: LensModel,
        path_indexes: tuple[int, ...],
    ) -> Buffer:
        paths = api_lens.ray_paths(lens_model, path_indexes)
        array = np.array(paths, cl.cltypes.int2)

        # return buffer
        buffer = Buffer(
            self.context,
            array=array,
            args=(lens_model, path_indexes),
        )
        return buffer

    @lru_cache(10)
    def update_direction(
        self,
        position: tuple[float, float],
        resolution: QtCore.QSize,
        sensor_size: tuple[float, float],
        focal_length: float,
    ) -> np.ndarray:
        sensor_length = sensor_size[0] / 2
        ratio = resolution.height() / resolution.width()
        direction = np.array((1, 1, 1, 1), cl.cltypes.float4)
        direction['x'] = position[0] * sensor_length
        direction['y'] = position[1] * ratio * sensor_length
        direction['z'] = focal_length
        return direction

    def update_rays(self, rays_shape: tuple[int, ...]) -> Buffer:
        dtype = self.dtypes['Ray']
        rays = np.zeros(rays_shape, dtype)
        rays_cl = cl.Buffer(self.context, cl.mem_flags.READ_WRITE, rays.nbytes)
        buffer = Buffer(self.context, array=rays, buffer=rays_cl)
        return buffer

    def update_intersections(self, intersections_shape: tuple[int, ...]) -> Buffer:
        dtype = self.dtypes['Intersection']
        intersections = np.zeros(intersections_shape, dtype)
        size = intersections.nbytes
        intersections_cl = cl.Buffer(self.context, cl.mem_flags.READ_WRITE, size)
        # no caching to make sure the buffer is cleared
        cl.enqueue_copy(self.queue, intersections_cl, intersections)
        buffer = Buffer(self.context, array=intersections, buffer=intersections_cl)
        return buffer

    @lru_cache(1)
    def update_wavelengths(self, wavelength_count: int) -> Buffer:
        array = np.int32(wavelength_array(wavelength_count))
        buffer = Buffer(self.context, array=array, args=wavelength_count)
        return buffer

    def trace(self, rays: Buffer) -> cl.Event:
        global_work_size = rays.array.shape
        local_work_size = None
        raytracing_event = cl.enqueue_nd_range_kernel(
            self.queue, self.kernel, global_work_size, local_work_size
        )
        raytracing_event.wait()
        return raytracing_event

    @lru_cache(1)
    def raytrace(
        self,
        lens_model: LensModel,
        sensor_size: tuple[float, float],
        glasses_path: str,
        abbe_nr_adjustment: float,
        coating: tuple[int, ...],
        coating_min_ior: float,
        grid_count: int,
        grid_length: float,
        light_position: tuple[float, float],
        resolution: QtCore.QSize,
        wavelength_count: int,
        path_indexes: tuple[int, ...],
    ) -> Buffer | None:
        # lens elements
        lens_elements = self.update_lens_elements(
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

        paths = self.update_paths(lens_model, path_indexes)
        wavelengths = self.update_wavelengths(wavelength_count)

        # direction
        direction = self.update_direction(
            light_position, resolution, sensor_size, lens_model.focal_length
        )

        # args
        lens_elements_count = len(lens_elements.array)

        # rays
        path_count = int(paths.array.size)
        ray_count = int(grid_count**2)
        wavelength_count = wavelengths.shape[0]
        rays_shape = (path_count, wavelength_count, ray_count)
        rays = self.update_rays(rays_shape)
        rays.args = (
            lens_elements,
            paths,
            wavelengths,
            lens_model.aperture_index,
            coating_min_ior,
            grid_count,
            grid_length,
            direction.tolist(),
        )

        lens_elements.clear_buffer()
        paths.clear_buffer()
        wavelengths.clear_buffer()

        self.kernel.set_arg(0, rays.buffer)
        self.kernel.set_arg(1, lens_elements.buffer)
        self.kernel.set_arg(2, np.int32(lens_elements_count))
        self.kernel.set_arg(3, paths.buffer)
        self.kernel.set_arg(4, wavelengths.buffer)
        self.kernel.set_arg(5, np.int32(lens_model.aperture_index))
        self.kernel.set_arg(6, np.float32(coating_min_ior))
        self.kernel.set_arg(7, np.int32(grid_count))
        self.kernel.set_arg(8, np.float32(grid_length))
        self.kernel.set_arg(9, direction)

        self.trace(rays)

        # copy device buffer to host
        # cl.enqueue_copy(self.queue, rays, rays_cl)
        # rays = np.reshape(rays, rays_shape)
        # for ray in rays[0, 0]:
        #     logging.debug(ray)

        return rays

    @timer
    def run(self, project: Project, path_indexes: tuple[int, ...]) -> Buffer | None:
        lens = project.flare.lens
        sensor_size = lens.sensor_size.width(), lens.sensor_size.height()

        light = project.flare.light
        light_position = light.position.x(), light.position.y()

        lens_model = api_lens.model_from_path(lens.lens_model_path)

        buffer = self.raytrace(
            lens_model=lens_model,
            sensor_size=sensor_size,
            glasses_path=lens.glasses_path,
            abbe_nr_adjustment=lens.abbe_nr_adjustment,
            coating=tuple(lens.coating),
            coating_min_ior=lens.coating_min_ior,
            grid_count=project.render.grid_count,
            grid_length=project.render.grid_length,
            light_position=light_position,
            resolution=project.render.resolution,
            wavelength_count=project.render.wavelength_count,
            path_indexes=path_indexes,
        )
        return buffer


class IntersectionsTask(RaytracingTask):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)
        self.kernel = None
        self.build()

    def build(self, *args, **kwargs) -> None:
        self.source = ''
        self.register_dtype('Ray', ray_dtype)
        self.register_dtype('LensElement', lens_element_dtype)
        self.register_dtype('Intersection', intersection_dtype)
        self.source += '#define STORE_INTERSECTIONS\n'
        self.source += f'__constant int LAMBDA_MIN = {LAMBDA_MIN};\n'
        self.source += f'__constant int LAMBDA_MAX = {LAMBDA_MAX};\n'
        self.source += self.read_source_file('raytracing.cl')
        OpenCL.build(self, *args, **kwargs)
        self.kernel = cl.Kernel(self.program, 'raytrace')

    @lru_cache(1)
    def raytrace(
        self,
        lens_model: LensModel,
        sensor_size: tuple[float, float],
        glasses_path: str,
        abbe_nr_adjustment: float,
        coating: tuple[int, ...],
        coating_min_ior: float,
        grid_count: int,
        grid_length: float,
        light_position: tuple[float, float],
        resolution: QtCore.QSize,
        wavelength_count: int,
        path_indexes: tuple[int, ...],
    ) -> Buffer | None:
        # lens elements
        lens_elements = self.update_lens_elements(
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

        paths = self.update_paths(lens_model, path_indexes)
        wavelengths = self.update_wavelengths(wavelength_count)

        # direction
        direction = self.update_direction(
            light_position, resolution, sensor_size, lens_model.focal_length
        )

        # args
        lens_elements_count = len(lens_elements.array)

        # rays
        path_count = int(paths.array.size)
        ray_count = int(grid_count**2)
        wavelength_count = wavelengths.shape[0]
        rays_shape = (path_count, wavelength_count, ray_count)
        rays = self.update_rays(rays_shape)
        rays.args = (
            lens_elements,
            paths,
            wavelengths,
            lens_model.aperture_index,
            coating_min_ior,
            grid_count,
            grid_length,
            direction.tolist(),
        )

        # intersections
        intersections_count = lens_elements.shape[0] * 3 - 1
        intersections_shape = (*rays.shape, intersections_count)
        intersections = self.update_intersections(intersections_shape)
        intersections.args = rays.args

        lens_elements.clear_buffer()
        paths.clear_buffer()
        wavelengths.clear_buffer()

        self.kernel.set_arg(0, rays.buffer)
        self.kernel.set_arg(1, lens_elements.buffer)
        self.kernel.set_arg(2, np.int32(lens_elements_count))
        self.kernel.set_arg(3, paths.buffer)
        self.kernel.set_arg(4, wavelengths.buffer)
        self.kernel.set_arg(5, np.int32(lens_model.aperture_index))
        self.kernel.set_arg(6, np.float32(coating_min_ior))
        self.kernel.set_arg(7, np.int32(grid_count))
        self.kernel.set_arg(8, np.float32(grid_length))
        self.kernel.set_arg(9, direction)
        self.kernel.set_arg(10, intersections.buffer)
        self.kernel.set_arg(11, np.int32(intersections_count))

        self.trace(rays)

        cl.enqueue_copy(self.queue, intersections.array, intersections.buffer)
        intersections._array = np.reshape(
            intersections.array, (1, wavelength_count, grid_count, grid_count, -1)
        )
        return intersections

    @timer
    def run(self, project: Project, path_indexes: tuple[int, ...]) -> Buffer | None:
        lens = project.flare.lens
        sensor_size = lens.sensor_size.width(), lens.sensor_size.height()

        light_position = (0, project.diagram.light_position)

        lens_model = api_lens.model_from_path(lens.lens_model_path)

        buffer = self.raytrace(
            lens_model=lens_model,
            sensor_size=sensor_size,
            glasses_path=lens.glasses_path,
            abbe_nr_adjustment=lens.abbe_nr_adjustment,
            coating=tuple(lens.coating),
            coating_min_ior=lens.coating_min_ior,
            grid_count=project.diagram.grid_count,
            grid_length=project.diagram.grid_length,
            light_position=light_position,
            resolution=project.diagram.resolution,
            wavelength_count=1,
            path_indexes=path_indexes,
        )
        return buffer
