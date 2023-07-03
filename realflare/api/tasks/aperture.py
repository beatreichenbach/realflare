from __future__ import annotations

import logging
from functools import lru_cache

import cv2
import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from realflare.api.data import Aperture, RealflareError, Project
from realflare.api.path import File
from realflare.api.tasks.opencl import OpenCL, Image
from realflare.storage import Storage
from realflare.utils.timing import timer

logger = logging.getLogger(__name__)
storage = Storage()


class ApertureTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)
        self.kernels = {}
        self.build()

    def build(self, *args, **kwargs) -> None:
        self.source = self.read_source_file('noise.cl')
        self.source += self.read_source_file('geometry.cl')
        self.source += self.read_source_file('aperture.cl')
        super().build()
        self.kernels['shape'] = cl.Kernel(self.program, 'aperture_shape')
        self.kernels['grating'] = cl.Kernel(self.program, 'aperture_grating')
        self.kernels['scratches'] = cl.Kernel(self.program, 'aperture_scratches')
        self.kernels['dust'] = cl.Kernel(self.program, 'aperture_dust')
        self.kernels['image'] = cl.Kernel(self.program, 'aperture_image')

    @lru_cache(1)
    def load_file(
        self, file: File, resolution: QtCore.QSize, threshold: float
    ) -> Image:
        filename = str(file)

        # load array
        array = cv2.imread(filename, cv2.IMREAD_GRAYSCALE | cv2.IMREAD_ANYDEPTH)

        # convert to float32
        if array.dtype == np.uint8:
            array = np.divide(array, 255)
        array = np.float32(array)

        # resize array
        array = cv2.resize(array, (resolution.width(), resolution.height()))

        # apply threshold
        if threshold != 1:
            threshold, array = cv2.threshold(array, threshold, 1, cv2.THRESH_BINARY)

        # return image
        image = Image(self.context, array=array, args=filename)
        return image

    @lru_cache(1)
    def aperture(
        self,
        aperture: Aperture,
        resolution: QtCore.QSize,
        scratches_parallax: tuple[float, float] = (0, 0),
        dust_parallax: tuple[float, float] = (0, 0),
    ) -> Image:
        if self.rebuild:
            self.build()

        # args
        aperture_image = self.update_image(
            resolution, cl.channel_order.INTENSITY, cl.mem_flags.READ_WRITE
        )
        aperture_image.args = (aperture, resolution, scratches_parallax, dust_parallax)

        size = np.array((1, 1), cl.cltypes.float2)
        size['x'] = aperture.shape.size.width()
        size['y'] = aperture.shape.size.height()
        rotation = np.radians(aperture.shape.rotation)

        # kernels
        w, h = resolution.width(), resolution.height()
        global_work_size = (w, h)
        local_work_size = None

        # shape
        self.kernels['shape'].set_arg(0, aperture_image.image)
        self.kernels['shape'].set_arg(1, size)
        self.kernels['shape'].set_arg(2, np.int32(aperture.shape.blades))
        self.kernels['shape'].set_arg(3, np.float32(rotation))
        self.kernels['shape'].set_arg(4, np.float32(aperture.shape.roundness))
        self.kernels['shape'].set_arg(5, np.float32(aperture.shape.softness / 10))
        cl.enqueue_nd_range_kernel(
            self.queue, self.kernels['shape'], global_work_size, local_work_size
        )

        # grating
        if aperture.grating.strength > 0:
            width = aperture.grating.width * 0.1
            self.kernels['grating'].set_arg(0, aperture_image.image)
            self.kernels['grating'].set_arg(1, size)
            self.kernels['grating'].set_arg(2, np.float32(aperture.grating.strength))
            self.kernels['grating'].set_arg(3, np.float32(aperture.grating.density))
            self.kernels['grating'].set_arg(4, np.float32(aperture.grating.length))
            self.kernels['grating'].set_arg(5, np.float32(width))
            self.kernels['grating'].set_arg(
                6, np.float32(aperture.grating.softness / 10)
            )
            cl.enqueue_nd_range_kernel(
                self.queue, self.kernels['grating'], global_work_size, local_work_size
            )

        # scratches
        if aperture.scratches.strength > 0:
            length = aperture.scratches.length
            rotation = np.radians(aperture.scratches.rotation)
            rotation_variation = aperture.scratches.rotation_variation
            width = aperture.scratches.width * 0.1
            self.kernels['scratches'].set_arg(0, aperture_image.image)
            self.kernels['scratches'].set_arg(1, size)
            self.kernels['scratches'].set_arg(
                2, np.float32(aperture.scratches.strength)
            )
            self.kernels['scratches'].set_arg(3, np.float32(aperture.scratches.density))
            self.kernels['scratches'].set_arg(4, np.float32(length))
            self.kernels['scratches'].set_arg(5, np.float32(rotation))
            self.kernels['scratches'].set_arg(6, np.float32(rotation_variation))
            self.kernels['scratches'].set_arg(7, np.float32(width))
            self.kernels['scratches'].set_arg(8, np.float32(scratches_parallax))
            self.kernels['scratches'].set_arg(
                9, np.float32(aperture.scratches.softness / 10)
            )
            cl.enqueue_nd_range_kernel(
                self.queue, self.kernels['scratches'], global_work_size, local_work_size
            )

        # dust
        if aperture.dust.strength > 0:
            radius = aperture.dust.radius * 0.1
            self.kernels['dust'].set_arg(0, aperture_image.image)
            self.kernels['dust'].set_arg(1, size)
            self.kernels['dust'].set_arg(2, np.float32(aperture.dust.strength))
            self.kernels['dust'].set_arg(3, np.float32(aperture.dust.density))
            self.kernels['dust'].set_arg(4, np.float32(radius))
            self.kernels['dust'].set_arg(5, np.float32(dust_parallax))
            self.kernels['dust'].set_arg(6, np.float32(aperture.dust.softness / 10))
            cl.enqueue_nd_range_kernel(
                self.queue, self.kernels['dust'], global_work_size, local_work_size
            )

        # image
        if aperture.image.strength > 0 and aperture.image.file:
            texture_size = np.array((1, 1), cl.cltypes.float2)
            texture_size['x'] = aperture.image.size.width()
            texture_size['y'] = aperture.image.size.height()
            texture_path = storage.decode_path(aperture.image.file)

            try:
                file = File(texture_path)
                texture = self.load_file(file, resolution, aperture.image.threshold)
            except (OSError, ValueError, cv2.Error) as e:
                logger.debug(e)
                raise RealflareError(f'Failed to load image: {texture_path}') from None

            self.kernels['image'].set_arg(0, aperture_image.image)
            self.kernels['image'].set_arg(1, size)
            self.kernels['image'].set_arg(2, np.float32(aperture.image.strength))
            self.kernels['image'].set_arg(3, texture.image)
            self.kernels['image'].set_arg(4, texture_size)
            cl.enqueue_nd_range_kernel(
                self.queue, self.kernels['image'], global_work_size, local_work_size
            )

        cl.enqueue_copy(
            self.queue,
            aperture_image.array,
            aperture_image.image,
            origin=(0, 0),
            region=(w, h),
        )

        return aperture_image


class GhostApertureTask(ApertureTask):
    @timer
    def run(self, project: Project) -> Image:
        image = self.aperture(
            project.flare.ghost_aperture, project.render.ghost.resolution
        )
        return image


class StarburstApertureTask(ApertureTask):
    @timer
    def run(self, project: Project) -> Image:
        position = project.flare.light.position
        parallax = project.flare.starburst_aperture.scratches.parallax
        scratches_parallax = (
            position.x() * parallax.width(),
            position.y() * parallax.height(),
        )
        parallax = project.flare.starburst_aperture.dust.parallax
        dust_parallax = (
            position.x() * parallax.width(),
            position.y() * parallax.height(),
        )

        image = self.aperture(
            project.flare.starburst_aperture,
            project.render.starburst.resolution,
            scratches_parallax,
            dust_parallax,
        )
        return image
