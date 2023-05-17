from functools import lru_cache

import pyopencl as cl
import numpy as np
from PySide2 import QtCore

from realflare.api.data import Flare, Project
from realflare.api.path import File
from realflare.api.tasks.opencl import (
    OpenCL,
    ray_dtype,
    Buffer,
    Image,
    lens_element_dtype,
    intersection_dtype,
)
from realflare.api.tasks.raytracing import RaytracingTask
from realflare.storage import Storage
from realflare.utils.timing import timer


storage = Storage()


class DiagramTask(OpenCL):
    def __init__(self, queue):
        super().__init__(queue)
        self.raytracing_task = RaytracingTask(queue)
        self.kernels = {}
        self.scale = 1
        self.build()

    def build(self, *args, **kwargs):
        self.source = ''
        self.register_dtype('Ray', ray_dtype)
        self.register_dtype('LensElement', lens_element_dtype)
        self.register_dtype('Intersection', intersection_dtype)

        self.source += self.read_source_file('diagram.cl')
        super().build(*args, **kwargs)

        self.kernels = {
            'intersections': cl.Kernel(self.program, 'intersections'),
            'lenses': cl.Kernel(self.program, 'lenses'),
        }

    @lru_cache(1)
    def update_scale(self, resolution: QtCore.QSize, lens_elements: Buffer) -> float:
        padding = 10  # extra pixels at the end
        distance = 0
        for lens_element in lens_elements.array:
            distance += lens_element['distance']
        scale = (resolution.width() - padding) / distance
        return scale

    @timer
    def lenses(self, image: Image, lens: Flare.Lens) -> None:
        # rebuild kernel
        if self.rebuild:
            self.build()

        resolution = QtCore.QSize(*reversed(image.array.shape[:2]))

        # lens elements
        prescription_path = storage.decode_path(lens.prescription_path)
        prescription = self.raytracing_task.update_prescription(File(prescription_path))
        lens_elements = self.raytracing_task.update_lens_elements(prescription, lens)
        lens_elements_count = len(lens_elements.array)
        # logging.debug(f'lens_elements_count: {lens_elements_count}')

        # scale
        self.scale = self.update_scale(resolution, lens_elements)

        # run program
        self.kernels['lenses'].set_arg(0, image.image)
        self.kernels['lenses'].set_arg(1, lens_elements.buffer)
        self.kernels['lenses'].set_arg(2, np.int32(lens_elements_count))
        self.kernels['lenses'].set_arg(3, np.float32(self.scale))

        h, w = image.array.shape[:2]
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
            image.array,
            image.image,
            origin=(0, 0),
            region=(w, h),
        )

    @timer
    def intersections(self, image: Image, intersections: Buffer, column_offset: int):
        # rebuild kernel
        if self.rebuild:
            self.build()

        resolution = QtCore.QSize(*reversed(image.array.shape[:2]))

        # load intersections
        column_count = intersections.array.shape[3]
        column = int((column_count - 1) / 2) + column_offset

        # shape = (path, wavelength, ray.row, ray.column, intersection)
        rays = np.ascontiguousarray(
            intersections.array[:, :, :, column : column + 1, :]
        )
        flags = cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR
        rays_cl = cl.Buffer(self.context, flags, hostbuf=rays)

        # intersections count
        ray_count = rays.shape[2] * rays.shape[3]
        intersections_count = rays.shape[4]
        # logging.debug(f'intersections_count: {intersections_count}')

        # run program
        self.kernels['intersections'].set_arg(0, image.image)
        self.kernels['intersections'].set_arg(1, np.int32(ray_count))
        self.kernels['intersections'].set_arg(2, rays_cl)
        self.kernels['intersections'].set_arg(3, np.int32(intersections_count))
        self.kernels['intersections'].set_arg(4, np.float32(self.scale))
        self.kernels['intersections'].set_arg(5, image.image)

        w, h = resolution.width(), resolution.height()
        global_work_size = (w, h)
        local_work_size = None
        cl.enqueue_nd_range_kernel(
            self.queue, self.kernels['intersections'], global_work_size, local_work_size
        )

        # copy device buffer to host
        cl.enqueue_copy(
            self.queue,
            image.array,
            image.image,
            origin=(0, 0),
            region=(w, h),
        )

    def run(self, project: Project, intersections: Buffer):
        # lenses
        resolution = project.render.diagram.resolution
        image = self.update_image(resolution, flags=cl.mem_flags.READ_WRITE)
        lens = project.flare.lens
        self.lenses(image, lens)

        # rays
        if intersections is not None:
            offset = project.render.diagram.column_offset
            self.intersections(image, intersections, offset)

        return image
