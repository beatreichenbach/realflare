from __future__ import annotations
from collections.abc import Iterable
from functools import lru_cache

import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from qt_extensions.typeutils import cast_basic
from realflare.api.data import Render, Project
from realflare.utils.timing import timer
from realflare.utils.ciexyz import CIEXYZ

from realflare.api.tasks.opencl import (
    OpenCL,
    ray_dtype,
    vertex_dtype,
    LAMBDA_MIN,
    LAMBDA_MAX,
    Buffer,
    Image,
)

BATCH_PRIMITIVE_COUNT = 255


def triangle_vertexes(n) -> list[tuple[int, int, int]]:
    # returns a list of tuples (vertex indexes per triangle)
    # n is the amount of rows of the vertex grid
    # v1, v2, v3 are the vertexes making up a triangle
    indexes = []
    for x in range(n - 1):
        for y in range(n - 1):
            for k in range(2):
                v1 = x * n + y
                v2 = v1 + 1 + k * n
                # v3 = v2 + n * (1 - k) - k
                v3 = v2 - 1 if k else v2 + n

                indexes.append((v1, v2, v3))
    return indexes


def quad_vertexes(n: int) -> list[tuple[int, int, int, int]]:
    # returns a list of tuples (vertex indexes per quad)
    # n is the amount of rows of the vertex grid
    # v1, v2, v3 are the vertexes making up a triangle
    indexes = []
    for x in range(n - 1):
        for y in range(n - 1):
            v1 = x * n + y
            v2 = v1 + 1
            v3 = v2 + n
            v4 = v1 + n

            indexes.append((v1, v2, v3, v4))
    return indexes


class RasterizingTask(OpenCL):
    bin_size = 32

    def __init__(self, queue) -> None:
        super().__init__(queue)
        self.kernels = {}
        self.build()

    def build(self, *args, **kwargs) -> None:
        self.source = ''
        self.register_dtype('Ray', ray_dtype)
        self.register_dtype('Vertex', vertex_dtype)
        self.source += f'__constant int BIN_SIZE = {self.bin_size};\n'
        self.source += f'__constant int LAMBDA_MIN = {LAMBDA_MIN};\n'
        self.source += f'__constant int LAMBDA_MAX = {LAMBDA_MAX};\n'
        self.source += self.read_source_file('color.cl')
        self.source += self.read_source_file('rasterizing.cl')

        super().build()

        self.kernels = {
            'prim_shader': cl.Kernel(self.program, 'prim_shader'),
            'vertex_shader': cl.Kernel(self.program, 'vertex_shader'),
            'binner': cl.Kernel(self.program, 'binner'),
            'rasterizer': cl.Kernel(self.program, 'rasterizer'),
        }

        # device = self.queue.get_info(cl.command_queue_info.DEVICE)
        # kernel_work_group_size = self.kernels['rasterizer'].get_work_group_info(
        #     cl.kernel_work_group_info.WORK_GROUP_SIZE, device
        # )
        # private_mem_size = self.kernels['rasterizer'].get_work_group_info(
        #     cl.kernel_work_group_info.PRIVATE_MEM_SIZE, device
        # )
        # logging.debug(f'private_mem_size: {private_mem_size}')
        # logging.debug(f'kernel_work_group_size: {kernel_work_group_size}')

    @lru_cache(1)
    def update_quads(self, grid_count: int) -> Buffer:
        vertex_indexes = quad_vertexes(grid_count)
        quad_count = len(vertex_indexes)
        quads = np.zeros(quad_count, cl.cltypes.int4)
        for i, indexes in enumerate(vertex_indexes):
            for j, index in enumerate(indexes):
                quads[i][j] = index

        buffer = Buffer(self.context, array=quads, args=grid_count)
        return buffer

    @lru_cache(1)
    def update_areas(self, prims_shape: tuple[int, ...]) -> Buffer:
        areas = np.zeros(prims_shape, cl.cltypes.float)
        flags = cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR
        areas_cl = cl.Buffer(self.context, flags, hostbuf=areas)

        buffer = Buffer(self.context, array=areas, buffer=areas_cl, args=prims_shape)
        return buffer

    def update_bounds(self, prims_shape: tuple[int, ...]) -> Buffer:
        # no caching to reset
        bounds = np.zeros(prims_shape, cl.cltypes.float4)
        flags = cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR
        bounds_cl = cl.Buffer(self.context, flags, hostbuf=bounds)
        buffer = Buffer(self.context, array=bounds, buffer=bounds_cl, args=prims_shape)
        return buffer

    def update_vertexes(self, vertex_shape: tuple[int, ...]) -> Buffer:
        # no caching to reset
        vertexes = np.zeros(vertex_shape, self.dtypes['Vertex'])
        vertexes_cl = cl.Buffer(self.context, cl.mem_flags.WRITE_ONLY, vertexes.nbytes)
        buffer = Buffer(self.context, array=vertexes, buffer=vertexes_cl)
        return buffer

    @lru_cache(10)
    def update_area_orig(self, grid_count, grid_length) -> float:
        quad_length = grid_length / (grid_count - 1)
        area_orig = quad_length**2
        return area_orig

    @lru_cache(10)
    def update_sensor(
        self, resolution: QtCore.QSize, sensor_size: tuple[float, float]
    ) -> float:
        sensor_length = np.linalg.norm((sensor_size[0], sensor_size[1])) / 2
        screen_transform = resolution.width() / sensor_length
        return screen_transform

    @lru_cache(1)
    def update_light_spectrum(self) -> Image:
        # extract XYZ data for visible wavelengths only
        xyz = [[x, y, z, 0] for w, x, y, z in CIEXYZ if LAMBDA_MIN <= w < LAMBDA_MAX]
        array = np.array(xyz, np.float32)

        # pyopencl does not handle 1d images so convert to 2d array with 4 channels
        array = np.reshape(array, (1, -1, 4))

        image = Image(self.context, array=array)
        return image

    @lru_cache(4)
    def update_sub_offsets(self, sub_steps: int) -> Buffer:
        # sample offsets for y coordinate based on n-rook pattern.
        # https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_standard_multisample_quality_levels
        # x, y for enumerate(offsets)
        sub_offsets_dict = {
            1: [0],
            2: [1, 0],
            4: [1, 2, 0, 3],
            8: [4, 1, 6, 2, 5, 0, 3, 7],
        }
        sub_offsets = np.array(sub_offsets_dict[sub_steps], cl.cltypes.char)
        buffer = Buffer(self.context, array=sub_offsets, args=sub_steps)
        return buffer

    @lru_cache(10)
    def update_bin_dims(self, bin_size: int, resolution: QtCore.QSize) -> np.ndarray:
        array = np.array((1, 1), cl.cltypes.int2)
        array['x'] = np.ceil(resolution.width() / bin_size)
        array['y'] = np.ceil(resolution.height() / bin_size)
        return array

    @lru_cache(10)
    def update_resolution(self, resolution: QtCore.QSize) -> np.ndarray:
        array = np.array((1, 1), cl.cltypes.int2)
        array['x'] = resolution.width()
        array['y'] = resolution.height()
        return array

    @lru_cache(1)
    def update_counter(self) -> cl.Buffer:
        flags = cl.mem_flags.READ_WRITE
        size = np.int32(1).nbytes
        bin_distribution_counter_cl = cl.Buffer(self.context, flags=flags, size=size)
        return bin_distribution_counter_cl

    @lru_cache(1)
    def update_bin_queues(self, bin_count: int, batch_count: int) -> Buffer:
        # one bin queue per bin, per wavelength

        # add 1 for header (list empty)
        queue_size = bin_count * (batch_count * (BATCH_PRIMITIVE_COUNT + 1))
        # size = wavelength_count * queue_size
        size = queue_size
        # logging.debug(f'bin_queues.size: {size}')

        flags = cl.mem_flags.READ_WRITE
        bin_queues_cl = cl.Buffer(self.context, flags=flags, size=size)
        # logging.debug(f'bin_queues_cl_size: {size}')

        # need a buffer to store bit mask, int64 = 64 bits
        # bin_queues = np.zeros((wavelength_count, int(queue_size / 64)), np.int64)
        bin_queues = np.zeros(int(queue_size / 64), np.int64)
        # logging.debug(f'bin_queues_size: {bin_queues.nbytes}')

        buffer = Buffer(self.context, array=bin_queues, buffer=bin_queues_cl)
        return buffer

    @timer
    def prim_shader(self, shape: tuple[int, ...]) -> cl.Event:
        global_work_size = shape
        local_work_size = None
        prim_event = cl.enqueue_nd_range_kernel(
            self.queue, self.kernels['prim_shader'], global_work_size, local_work_size
        )
        prim_event.wait()
        return prim_event

    @timer
    def vertex_shader(self, vertexes: Buffer, wait_for: Iterable[cl.Event]) -> cl.Event:
        global_work_size = vertexes.array.shape
        local_work_size = None
        vertex_event = cl.enqueue_nd_range_kernel(
            self.queue,
            self.kernels['vertex_shader'],
            global_work_size,
            local_work_size,
            wait_for=wait_for,
        )
        vertex_event.wait()
        return vertex_event

    @timer
    def binner(
        self, wavelength_count: int, batch_count: int, wait_for: Iterable[cl.Event]
    ) -> cl.Event:
        device = self.queue.get_info(cl.command_queue_info.DEVICE)
        # compute_units = device.get_info(cl.device_info.MAX_COMPUTE_UNITS)
        work_group_size = device.get_info(cl.device_info.MAX_WORK_GROUP_SIZE)

        global_work_size = (batch_count * work_group_size,)
        local_work_size = (work_group_size,)
        binner_event = cl.enqueue_nd_range_kernel(
            self.queue,
            self.kernels['binner'],
            global_work_size,
            local_work_size,
            wait_for=wait_for,
        )
        binner_event.wait()
        return binner_event

    @timer
    def rasterizer(
        self, flare_image: Image, bin_count: int, wait_for: Iterable[cl.Event]
    ) -> cl.Event:
        h, w = flare_image.array.shape[:2]
        global_work_size = (w, h)
        local_work_size = None
        # global_work_size = (int(np.ceil(w / 8) * 8), int(np.ceil(h / 8) * 8))
        # local_work_size = (8, 8)

        # device = self.queue.get_info(cl.command_queue_info.DEVICE)
        # # compute_units = device.get_info(cl.device_info.MAX_COMPUTE_UNITS)
        # work_group_size = device.get_info(cl.device_info.MAX_WORK_GROUP_SIZE)
        # work_group_size = 256
        # global_work_size = (bin_count * work_group_size, )
        # local_work_size = (work_group_size, )

        event = cl.enqueue_nd_range_kernel(
            self.queue,
            self.kernels['rasterizer'],
            global_work_size,
            local_work_size,
            wait_for=wait_for,
        )

        cl.enqueue_copy(
            self.queue,
            flare_image.array,
            flare_image.image,
            origin=(0, 0),
            region=(w, h),
        )
        return event

    def rasterize(
        self,
        render: Render,
        rays: Buffer,
        ghost: Image,
        sensor_size: tuple[float, float],
        min_area: float,
        intensity: float,
        fstop: float,
    ) -> Image:
        resolution = render.resolution

        # rebuild kernel
        bin_size_changed = render.bin_size != self.bin_size
        if bin_size_changed:
            self.bin_size = render.bin_size
        if self.rebuild or bin_size_changed:
            self.build()

        # image
        flare_image = self.update_image(resolution, flags=cl.mem_flags.READ_WRITE)
        flare_image.args = (
            rays,
            ghost,
            render,
            min_area,
            intensity,
            sensor_size,
            fstop,
        )

        if rays is None:
            return flare_image

        # prim shader
        path_count, wavelength_count, ray_count = rays.array.shape
        # quads = self.update_quads(render.grid_count)
        # quad_count = quads.array.size
        quad_count = (render.grid_count - 1) ** 2
        # swapping wavelength and path axis. rasterization requires grouping by wavelength
        areas_shape = (path_count, quad_count, wavelength_count)
        bounds_shape = (path_count, quad_count)

        areas = self.update_areas(areas_shape)
        areas.args = (rays, render, min_area)
        bounds = self.update_bounds(bounds_shape)
        bounds.args = (rays, render)
        area_orig = self.update_area_orig(render.grid_count, render.grid_length)
        rel_min_area = min_area * area_orig

        self.kernels['prim_shader'].set_arg(0, bounds.buffer)
        self.kernels['prim_shader'].set_arg(1, areas.buffer)
        self.kernels['prim_shader'].set_arg(2, rays.buffer)
        self.kernels['prim_shader'].set_arg(3, np.int32(render.grid_count))
        self.kernels['prim_shader'].set_arg(4, np.int32(ray_count))
        self.kernels['prim_shader'].set_arg(5, np.int32(wavelength_count))
        self.kernels['prim_shader'].set_arg(6, np.float32(rel_min_area))

        prim_event = self.prim_shader(bounds_shape)
        # cl.enqueue_copy(self.queue, areas, areas_cl)
        # cl.enqueue_copy(self.queue, bounds, bounds_cl)
        # logging.debug(f'bounds {[0, 518]}: {bounds[0, 518]}')
        # logging.debug(f'bounds {[0, 519]}: {bounds[0, 519]}')

        # vertex shader
        vertex_shape = (path_count, ray_count, wavelength_count)
        vertexes = self.update_vertexes(vertex_shape)
        vertexes.args = (rays, render, min_area, sensor_size)
        resolution_buffer = self.update_resolution(resolution)
        screen_transform = self.update_sensor(resolution, sensor_size)

        self.kernels['vertex_shader'].set_arg(0, vertexes.buffer)
        self.kernels['vertex_shader'].set_arg(1, areas.buffer)
        self.kernels['vertex_shader'].set_arg(2, rays.buffer)
        self.kernels['vertex_shader'].set_arg(3, np.int32(render.grid_count))
        self.kernels['vertex_shader'].set_arg(4, np.float32(area_orig))
        self.kernels['vertex_shader'].set_arg(5, np.float32(screen_transform))
        self.kernels['vertex_shader'].set_arg(6, resolution_buffer)

        wait_for = [prim_event]
        vertex_event = self.vertex_shader(vertexes, wait_for)
        # cl.enqueue_copy(self.queue, vertexes.array, vertexes.buffer)
        # logging.debug(f'vertex_shape: {vertex_shape}')
        # logging.debug(f'vertexes: {vertexes}')
        # logging.debug(f'vertex 120: {vertexes[0, 120, 0]}')
        # logging.debug(f'vertex 120: {vertexes[0, 120, 1]}')
        # logging.debug(f'vertexes.nbytes: {vertexes.nbytes}')

        # binner
        bin_dims = self.update_bin_dims(render.bin_size, resolution)
        bin_distribution_counter_cl = self.update_counter()
        bin_count = int(bin_dims['x'] * bin_dims['y'])
        # logging.debug(f'bin_dims: {array}')
        # logging.debug(f'bin_count: {bin_count}')
        # primitive_count = prims_shape[1] * prims_shape[2]
        primitive_count = bounds.array.size
        # logging.debug(f'primitive_count: {primitive_count}')
        batch_count = int(np.ceil(primitive_count / BATCH_PRIMITIVE_COUNT))
        # logging.debug(f'batch_count: {batch_count}')
        bin_queues = self.update_bin_queues(bin_count, batch_count)
        bin_queues.args = (rays, render)

        # TODO: check convert int/float, as those conversions can be slow
        self.kernels['binner'].set_arg(0, bin_queues.buffer)
        self.kernels['binner'].set_arg(1, bin_dims)
        self.kernels['binner'].set_arg(2, np.int32(bin_count))
        self.kernels['binner'].set_arg(3, bounds.buffer)
        self.kernels['binner'].set_arg(4, np.int32(primitive_count))
        self.kernels['binner'].set_arg(5, bin_distribution_counter_cl)
        self.kernels['binner'].set_arg(6, np.float32(screen_transform))
        self.kernels['binner'].set_arg(7, resolution_buffer)

        wait_for = [vertex_event]
        bin_event = self.binner(wavelength_count, batch_count, wait_for)

        # return flare_image
        # cl.enqueue_copy(self.queue, bin_queues.array, bin_queues.buffer)
        # bin_queues_shape = (bin_dims['y'], bin_dims['x'], -1)
        # logging.debug(f'bin_queues_shape: {bin_queues_shape}')
        # bin_queues = np.reshape(bin_queues.array, bin_queues_shape)
        # for y in range(bin_queues_shape[0]):
        #     for x in range(bin_queues_shape[1]):
        #         if x != 0 or y != 15:
        #             continue
        #         for i in bin_queues[y, x]:
        #             logging.debug(f'bin_queues {[y, x]}: {np.binary_repr(i, width=64)}, {i}')

        # rasterizer
        light_spectrum = self.update_light_spectrum()
        sub_steps = render.anti_aliasing
        sub_offsets = self.update_sub_offsets(sub_steps)
        wavelength_sub_count = (
            render.wavelength_sub_count if wavelength_count > 1 else 1
        )
        try:
            scale = 1 - 32 / fstop
        except ZeroDivisionError:
            scale = 1

        # device = self.queue.get_info(cl.command_queue_info.DEVICE)
        # logging.debug(f'COMPILE_WORK_GROUP_SIZE: {self.kernels["rasterizer"].get_work_group_info(cl.kernel_work_group_info.COMPILE_WORK_GROUP_SIZE, device)}')
        # logging.debug(f'LOCAL_MEM_SIZE: {self.kernels["rasterizer"].get_work_group_info(cl.kernel_work_group_info.LOCAL_MEM_SIZE, device)}')
        # logging.debug(f'PREFERRED_WORK_GROUP_SIZE_MULTIPLE: {self.kernels["rasterizer"].get_work_group_info(cl.kernel_work_group_info.PREFERRED_WORK_GROUP_SIZE_MULTIPLE, device)}')
        # logging.debug(f'PRIVATE_MEM_SIZE: {self.kernels["rasterizer"].get_work_group_info(cl.kernel_work_group_info.PRIVATE_MEM_SIZE, device)}')
        # logging.debug(f'WORK_GROUP_SIZE: {self.kernels["rasterizer"].get_work_group_info(cl.kernel_work_group_info.WORK_GROUP_SIZE, device)}')

        # TODO: can if statements be removed? (wavelength_count != 1). Less branching is better

        self.kernels['rasterizer'].set_arg(0, flare_image.image)
        self.kernels['rasterizer'].set_arg(1, ghost.image)
        self.kernels['rasterizer'].set_arg(2, light_spectrum.image)
        self.kernels['rasterizer'].set_arg(3, vertexes.buffer)
        self.kernels['rasterizer'].set_arg(4, bin_queues.buffer)
        self.kernels['rasterizer'].set_arg(5, np.int32(batch_count))
        self.kernels['rasterizer'].set_arg(6, np.int32(path_count))
        self.kernels['rasterizer'].set_arg(7, np.int32(wavelength_count))
        self.kernels['rasterizer'].set_arg(8, np.int32(wavelength_sub_count))
        self.kernels['rasterizer'].set_arg(9, np.int32(render.grid_count))
        self.kernels['rasterizer'].set_arg(10, np.int32(sub_steps))
        self.kernels['rasterizer'].set_arg(11, sub_offsets.buffer)
        self.kernels['rasterizer'].set_arg(12, np.float32(intensity * 1e3))
        self.kernels['rasterizer'].set_arg(13, np.float32(scale))

        # clear image
        w, h = resolution.width(), resolution.height()
        black = np.zeros((4,), np.float32)
        clear_event = cl.enqueue_fill_image(
            self.queue, flare_image.image, black, origin=(0, 0), region=(w, h)
        )

        wait_for = [vertex_event, clear_event, bin_event]
        self.rasterizer(flare_image, bin_count, wait_for)

        # return image
        return flare_image

    def run(
        self,
        project: Project,
        rays: Buffer,
        ghost: Image,
    ) -> Image:
        sensor_size = tuple(cast_basic(project.flare.lens.sensor_size))
        output = self.rasterize(
            project.render,
            rays,
            ghost,
            sensor_size,
            project.flare.lens.min_area,
            project.flare.light.intensity,
            project.flare.lens.fstop,
        )
        return output
