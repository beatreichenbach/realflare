from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from qt_extensions.typeutils import basic
from realflare.api.data import Render, Project
from realflare.api.tasks.opencl import (
    OpenCL,
    ray_dtype,
    vertex_dtype,
    LAMBDA_MIN,
    LAMBDA_MAX,
    Buffer,
    Image,
)
from realflare.utils.ciexyz import CIEXYZ
from realflare.utils.timing import timer

logger = logging.getLogger(__name__)

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
        self.source += f'#define BATCH_PRIMITIVE_COUNT {BATCH_PRIMITIVE_COUNT}\n'

        self.register_dtype('Ray', ray_dtype)
        self.register_dtype('Vertex', vertex_dtype)

        # sample offsets for y coordinate based on n-rook pattern.
        # https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_standard_multisample_quality_levels
        sub_offsets = []
        sub_offsets.extend([0])
        sub_offsets.extend([1, 0])
        sub_offsets.extend([1, 2, 0, 3])
        sub_offsets.extend([4, 1, 6, 2, 5, 0, 3, 7])
        # append all values into an array
        array_str = ', '.join(map(str, sub_offsets))
        self.source += (
            f'__constant uchar sub_offsets[{len(sub_offsets)}] = {{{array_str}}};\n'
        )
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
        # logger.debug(f'{private_mem_size:=}')
        # logger.debug(f'{kernel_work_group_size:=}')

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
    def update_intensities(self, prims_shape: tuple[int, ...]) -> Buffer:
        intensities = np.zeros(prims_shape, cl.cltypes.float)
        flags = cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR
        intensities_cl = cl.Buffer(self.context, flags, hostbuf=intensities)

        buffer = Buffer(self.context, array=intensities, buffer=intensities_cl)
        return buffer

    @lru_cache(1)
    def update_bounds(self, prims_shape: tuple[int, ...]) -> Buffer:
        # no caching to reset
        bounds = np.zeros(prims_shape, cl.cltypes.float4)
        flags = cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR
        bounds_cl = cl.Buffer(self.context, flags, hostbuf=bounds)
        buffer = Buffer(self.context, array=bounds, buffer=bounds_cl)
        return buffer

    @lru_cache(1)
    def update_vertexes(self, vertex_shape: tuple[int, ...]) -> Buffer:
        # no caching to reset
        vertexes = np.zeros(vertex_shape, self.dtypes['Vertex'])
        vertexes_cl = cl.Buffer(self.context, cl.mem_flags.WRITE_ONLY, vertexes.nbytes)
        buffer = Buffer(self.context, array=vertexes, buffer=vertexes_cl)
        return buffer

    @lru_cache(10)
    def update_area_orig(self, grid_count, grid_length) -> float:
        grid_count = max(1, grid_count)
        quad_length = grid_length / (grid_count - 1)
        area_orig = quad_length**2
        return area_orig

    @lru_cache(10)
    def update_screen_transform(
        self, resolution: QtCore.QSize, sensor_size: tuple[float, float]
    ) -> float:
        sensor_length = np.linalg.norm((sensor_size[0], sensor_size[1])) / 2
        try:
            screen_transform = resolution.width() / sensor_length
        except ZeroDivisionError:
            screen_transform = 0
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

    @lru_cache(10)
    def update_bin_dims(
        self, bin_size: int, resolution: QtCore.QSize
    ) -> tuple[int, int]:
        bin_size = max(bin_size, 1)
        x = np.ceil(resolution.width() / bin_size)
        y = np.ceil(resolution.height() / bin_size)
        return x, y

    @lru_cache(1)
    def update_bin_queues(self, bin_count: int, batch_count: int) -> Buffer:
        # one bin queue per bin, per wavelength

        # add 1 for header (list empty)
        queue_size = bin_count * (batch_count * (BATCH_PRIMITIVE_COUNT + 1))

        flags = cl.mem_flags.READ_WRITE
        bin_queues_cl = cl.Buffer(self.context, flags=flags, size=queue_size)

        # need a buffer to store bit mask, int64 = 64 bits
        bin_queues = np.zeros(int(queue_size / 64), np.int64)

        # logger.debug(f'{queue_size:=}')
        # bin_queues_bytes = bin_queues.nbytes
        # logger.debug(f'{bin_queues_bytes:=}')

        buffer = Buffer(self.context, array=bin_queues, buffer=bin_queues_cl)
        return buffer

    @timer
    @lru_cache(1)
    def prim_shader(self, bounds: Buffer, _intensities: Buffer) -> cl.Event:
        # intensities used for lru_cache

        global_work_size = bounds.shape
        local_work_size = None
        prim_event = cl.enqueue_nd_range_kernel(
            self.queue, self.kernels['prim_shader'], global_work_size, local_work_size
        )
        prim_event.wait()
        return prim_event

    @timer
    @lru_cache(1)
    def vertex_shader(self, vertexes: Buffer) -> cl.Event:
        global_work_size = vertexes.array.shape
        local_work_size = None
        vertex_event = cl.enqueue_nd_range_kernel(
            self.queue,
            self.kernels['vertex_shader'],
            global_work_size,
            local_work_size,
        )
        vertex_event.wait()
        return vertex_event

    @timer
    @lru_cache(1)
    def binner(self, _bin_queues: Buffer, batch_count: int) -> cl.Event:
        # bin_queues used for lru_cache

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
        )
        binner_event.wait()
        return binner_event

    @timer
    @lru_cache(1)
    def rasterizer(self, flare_image: Image) -> cl.Event:
        h, w = flare_image.array.shape[:2]

        # clear image
        black = np.zeros((4,), np.float32)
        clear_event = cl.enqueue_fill_image(
            self.queue, flare_image.image, black, origin=(0, 0), region=(w, h)
        )

        global_work_size = (w, h)
        local_work_size = None
        event = cl.enqueue_nd_range_kernel(
            self.queue,
            self.kernels['rasterizer'],
            global_work_size,
            local_work_size,
            wait_for=[clear_event],
        )

        cl.enqueue_copy(
            self.queue,
            flare_image.array,
            flare_image.image,
            origin=(0, 0),
            region=(w, h),
        )
        return event

    @lru_cache(1)
    def update_image(
        self,
        resolution: QtCore.QSize,
        channel_order: cl.channel_order = cl.channel_order.RGBA,
        flags: cl.mem_flags = cl.mem_flags.WRITE_ONLY,
    ) -> Image:
        return super().update_image(resolution, channel_order, flags)

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
        # rebuild kernel
        bin_size_changed = render.bin_size != self.bin_size
        if bin_size_changed:
            self.bin_size = render.bin_size
        if self.rebuild or bin_size_changed:
            self.build()

        # image
        flare_image = self.update_image(
            render.resolution, flags=cl.mem_flags.READ_WRITE
        )

        if rays is None:
            return flare_image

        # prim shader
        path_count, wavelength_count, ray_count = rays.array.shape
        quad_count = (render.grid_count - 1) ** 2
        # swapping wavelength and path axis. rasterization requires grouping by wavelength
        intensities_shape = (path_count, quad_count, wavelength_count)
        bounds_shape = (path_count, quad_count)

        area_orig = self.update_area_orig(render.grid_count, render.grid_length)
        rel_min_area = min_area * area_orig
        bounds = self.update_bounds(bounds_shape)
        bounds.args = (rays, rel_min_area)
        intensities = self.update_intensities(intensities_shape)
        intensities.args = (rays, area_orig, rel_min_area)

        self.kernels['prim_shader'].set_arg(0, bounds.buffer)
        self.kernels['prim_shader'].set_arg(1, intensities.buffer)
        self.kernels['prim_shader'].set_arg(2, rays.buffer)
        self.kernels['prim_shader'].set_arg(3, np.int32(render.grid_count))
        self.kernels['prim_shader'].set_arg(4, np.int32(ray_count))
        self.kernels['prim_shader'].set_arg(5, np.int32(wavelength_count))
        self.kernels['prim_shader'].set_arg(6, np.float32(area_orig))
        self.kernels['prim_shader'].set_arg(7, np.float32(rel_min_area))

        self.prim_shader(bounds, intensities)
        # cl.enqueue_copy(self.queue, bounds, bounds_cl)
        # logger.debug(f'{bounds[0, 518]:=}')

        # vertex shader
        vertex_shape = (path_count, ray_count, wavelength_count)
        resolution = render.resolution.width(), render.resolution.height()
        screen_transform = self.update_screen_transform(render.resolution, sensor_size)
        vertexes = self.update_vertexes(vertex_shape)
        vertexes.args = (rays, intensities, screen_transform, resolution)

        self.kernels['vertex_shader'].set_arg(0, vertexes.buffer)
        self.kernels['vertex_shader'].set_arg(1, intensities.buffer)
        self.kernels['vertex_shader'].set_arg(2, rays.buffer)
        self.kernels['vertex_shader'].set_arg(3, np.int32(render.grid_count))
        self.kernels['vertex_shader'].set_arg(4, np.float32(screen_transform))
        self.kernels['vertex_shader'].set_arg(5, np.int32(resolution))

        self.vertex_shader(vertexes)
        # cl.enqueue_copy(self.queue, vertexes.array, vertexes.buffer)
        # logger.debug(f'{vertexes[0, 120, 0]:=}')

        # binner
        bin_dims = self.update_bin_dims(render.bin_size, render.resolution)
        bin_count = int(bin_dims[0] * bin_dims[1])
        primitive_count = bounds.array.size
        batch_count = int(np.ceil(primitive_count / BATCH_PRIMITIVE_COUNT))
        bin_queues = self.update_bin_queues(bin_count, batch_count)
        bin_queues.args = (bin_dims, bounds)
        # logger.debug(f'{bin_count:=}')
        # logger.debug(f'{primitive_count:=}')
        # logger.debug(f'{batch_count:=}')

        self.kernels['binner'].set_arg(0, bin_queues.buffer)
        self.kernels['binner'].set_arg(1, np.int32(bin_dims))
        self.kernels['binner'].set_arg(2, np.int32(bin_count))
        self.kernels['binner'].set_arg(3, bounds.buffer)
        self.kernels['binner'].set_arg(4, np.int32(primitive_count))
        self.kernels['binner'].set_arg(5, np.float32(screen_transform))
        self.kernels['binner'].set_arg(6, np.int32(resolution))

        self.binner(bin_queues, batch_count)

        # rasterizer
        light_spectrum = self.update_light_spectrum()
        sub_steps = render.anti_aliasing
        wavelength_sub_count = (
            render.wavelength_sub_count if wavelength_count > 1 else 1
        )
        ghost_scale = 1 - fstop / 32
        flare_image.args = (
            ghost,
            vertexes,
            bin_queues,
            wavelength_sub_count,
            sub_steps,
            intensity,
            ghost_scale,
        )

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
        self.kernels['rasterizer'].set_arg(11, np.float32(intensity * 1e3))
        self.kernels['rasterizer'].set_arg(12, np.float32(ghost_scale))

        self.rasterizer(flare_image)

        # return image
        return flare_image

    def run(
        self,
        project: Project,
        rays: Buffer,
        ghost: Image,
    ) -> Image:
        sensor_size = tuple(basic(project.flare.lens.sensor_size))
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
