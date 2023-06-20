from __future__ import annotations
import logging
from functools import lru_cache

import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from realflare.api import glass
from realflare.api.data import Flare, LensModel, Project, RealflareError
from realflare.api.path import File
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
from qt_extensions.typeutils import cast, cast_basic


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
        self.source += f'__constant int LAMBDA_MIN = {LAMBDA_MIN};\n'
        self.source += f'__constant int LAMBDA_MAX = {LAMBDA_MAX};\n'
        self.source += self.read_source_file('raytracing.cl')
        super().build()
        self.kernel = cl.Kernel(self.program, 'raytrace')

    @staticmethod
    @lru_cache(1)
    def build_lens_model(file: File) -> LensModel:
        file_path = str(file)
        data = storage.read_data(file_path)
        lens_model = cast(LensModel, data)
        return lens_model

    @staticmethod
    def update_lens_model(lens_model_path: str) -> LensModel:
        if not lens_model_path:
            raise RealflareError('No Lens Model')

        filename = storage.decode_path(lens_model_path)
        try:
            lens_model_file = File(filename)
            lens_model = RaytracingTask.build_lens_model(lens_model_file)
        except (OSError, ValueError) as e:
            logger.debug(e)
            message = f'Invalid Lens Model: {filename}'
            raise RealflareError(message) from None
        return lens_model

    @lru_cache(1)
    def update_lens_elements(
        self,
        lens_model: LensModel,
        lens: Flare.Lens,
    ) -> Buffer:
        # lens elements
        # make copy of mutable attribute
        lens_elements = list(lens_model.lens_elements)
        # if not lens_elements:
        #     raise ValueError('lens model has no elements')

        # append sensor as element
        sensor_size = lens.sensor_size
        sensor_length = np.linalg.norm((sensor_size.width(), sensor_size.height())) / 2
        lens_elements.append(LensModel.LensElement(height=sensor_length))

        # glasses
        glasses_path = storage.decode_path(lens.glasses_path)
        glasses = glass.glasses_from_path(glasses_path)

        # array
        dtype = self.dtypes['LensElement']
        array = np.zeros(len(lens_elements), dtype)
        if not glasses:
            array[0]['coefficients'][0] = np.NAN

        offset = 0
        for i, lens_element in enumerate(lens_elements):
            array[i]['radius'] = lens_element.radius
            array[i]['distance'] = lens_element.distance
            array[i]['ior'] = lens_element.refractive_index
            array[i]['height'] = lens_element.height
            array[i]['center'] = offset + lens_element.radius

            # TODO: get rid of is_apt and use aperture_index
            array[i]['is_apt'] = i == lens_model.aperture_index

            # TODO: temp, coefficients not set = random memory
            if i < len(lens.coating_lens_elements):
                coating = lens.coating_lens_elements[i]
            else:
                coating = (537, 1.38)
            array[i]['coating'] = coating

            # glass
            glass_type = glass.closest_glass(
                glasses,
                lens_element.refractive_index,
                lens_element.abbe_nr,
                lens.abbe_nr_adjustment,
            )
            if glass_type:
                for j in range(6):
                    array[i]['coefficients'][j] = glass_type.coefficients[j]

            offset += lens_element.distance

        # return buffer
        buffer = Buffer(self.context, array=array, args=(lens_model, lens))
        return buffer

    @lru_cache(10)
    def update_paths(self, lens_model: LensModel, path_indexes: tuple[int]) -> Buffer:
        # create paths that describe possible paths the rays can travel
        # path = (first bounce, 2nd bounce)
        # the ray can only bounce either before or after the aperture
        # the last lens is the sensor. max: lens_elements_count - 1
        paths = []
        lens_elements_count = len(lens_model.lens_elements)
        index_min = 0
        for bounce1 in range(1, lens_elements_count - 1):
            if bounce1 == lens_model.aperture_index:
                index_min = bounce1 + 1
            for bounce2 in range(index_min, bounce1):
                paths.append((bounce1, bounce2))

        # debug / optimization
        if path_indexes:
            paths = [p for i, p in enumerate(paths) if i in path_indexes]

        array = np.array(paths, cl.cltypes.int2)

        # return buffer
        buffer = Buffer(self.context, array=array, args=(lens_model, path_indexes))
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
        intersections_cl = cl.Buffer(
            self.context, cl.mem_flags.READ_WRITE, intersections.nbytes
        )
        # no caching to make sure the buffer is cleared
        cl.enqueue_copy(self.queue, intersections_cl, intersections)
        buffer = Buffer(self.context, array=intersections, buffer=intersections_cl)
        return buffer

    @lru_cache(1)
    def update_wavelengths(self, wavelength_count: int) -> Buffer:
        array = np.int32(wavelength_array(wavelength_count))
        buffer = Buffer(self.context, array=array)
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
        light_position: tuple[float, float],
        lens: Flare.Lens,
        grid_count: int,
        grid_length: float,
        resolution: QtCore.QSize,
        wavelength_count: int,
        path_indexes: tuple[int],
    ) -> Buffer | None:
        # rebuild kernel
        if self.rebuild:
            self.build()

        # lens elements
        lens_model = self.update_lens_model(lens.lens_model_path)
        lens_elements = self.update_lens_elements(lens_model, lens)
        lens_elements.clear_buffer()
        lens_elements_count = len(lens_elements.array)
        paths = self.update_paths(lens_model, path_indexes)
        paths.clear_buffer()

        if lens_elements_count <= 1:
            # no lens elements
            return

        # rays
        path_count = int(paths.array.size)
        ray_count = int(grid_count**2)
        rays_shape = (path_count, wavelength_count, ray_count)
        rays = self.update_rays(rays_shape)
        # rays.args = args
        wavelengths = self.update_wavelengths(wavelength_count)

        # direction
        sensor_size = lens.sensor_size.width(), lens.sensor_size.height()
        focal_length = lens_model.focal_length
        direction = self.update_direction(
            light_position, resolution, sensor_size, focal_length
        )

        self.kernel.set_arg(0, rays.buffer)
        self.kernel.set_arg(1, lens_elements.buffer)
        self.kernel.set_arg(2, np.int32(lens_elements_count))
        self.kernel.set_arg(3, paths.buffer)
        self.kernel.set_arg(4, np.int32(grid_count))
        self.kernel.set_arg(5, np.float32(grid_length))
        self.kernel.set_arg(6, direction)
        self.kernel.set_arg(7, wavelengths.buffer)

        self.trace(rays)

        # copy device buffer to host
        # cl.enqueue_copy(self.queue, rays, rays_cl)
        # rays = np.reshape(rays, rays_shape)
        # for ray in rays[0, 0]:
        #     logging.debug(ray)

        return rays

    @timer
    def run(self, project: Project, path_indexes: tuple[int]) -> Buffer | None:
        # make light_position hashable
        light_position = tuple(cast_basic(project.flare.light.position))
        buffer = self.raytrace(
            light_position,
            project.flare.lens,
            project.render.grid_count,
            project.render.grid_length,
            project.render.resolution,
            project.render.wavelength_count,
            path_indexes,
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
        light_position: tuple[float, float],
        lens: Flare.Lens,
        grid_count: int,
        grid_length: float,
        resolution: QtCore.QSize,
        wavelength_count: int,
        path_indexes: tuple[int],
    ) -> Buffer | None:
        # rebuild kernel
        if self.rebuild:
            self.build()

        # lens elements
        lens_model = self.update_lens_model(lens.lens_model_path)
        lens_elements = self.update_lens_elements(lens_model, lens)
        lens_elements.clear_buffer()
        lens_elements_count = len(lens_elements.array)
        paths = self.update_paths(lens_model, path_indexes)
        paths.clear_buffer()

        if lens_elements_count <= 1:
            # no lens elements
            return

        # rays
        path_count = int(paths.array.size)
        ray_count = int(grid_count**2)
        rays_shape = (path_count, wavelength_count, ray_count)
        rays = self.update_rays(rays_shape)
        # rays.args = args
        wavelengths = self.update_wavelengths(wavelength_count)

        # direction
        sensor_size = lens.sensor_size.width(), lens.sensor_size.height()
        focal_length = lens_model.focal_length
        direction = self.update_direction(
            light_position, resolution, sensor_size, focal_length
        )

        self.kernel.set_arg(0, rays.buffer)
        self.kernel.set_arg(1, lens_elements.buffer)
        self.kernel.set_arg(2, np.int32(lens_elements_count))
        self.kernel.set_arg(3, paths.buffer)
        self.kernel.set_arg(4, np.int32(grid_count))
        self.kernel.set_arg(5, np.float32(grid_length))
        self.kernel.set_arg(6, direction)
        self.kernel.set_arg(7, wavelengths.buffer)

        intersections_count = lens_elements.shape[0] * 3 - 1
        intersections_shape = (*rays.shape, intersections_count)
        intersections = self.update_intersections(intersections_shape)
        self.kernel.set_arg(8, intersections.buffer)
        self.kernel.set_arg(9, np.int32(intersections_count))

        self.trace(rays)

        cl.enqueue_copy(self.queue, intersections.array, intersections.buffer)
        intersections._array = np.reshape(
            intersections.array, (1, wavelength_count, grid_count, grid_count, -1)
        )
        return intersections

    @timer
    def run(self, project: Project, path_indexes: tuple[int]) -> Buffer | None:
        # make light_position hashable
        light_position = (0, project.diagram.light_position)
        buffer = self.raytrace(
            light_position,
            project.flare.lens,
            project.diagram.grid_count,
            project.diagram.grid_length,
            project.diagram.resolution,
            1,
            path_indexes,
        )
        return buffer
