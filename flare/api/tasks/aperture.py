import logging
from functools import lru_cache

import cv2
import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from flare.api.data import Render, Aperture
from flare.api.path import File
from flare.api.tasks.opencl import OpenCL, Image
from flare.gui.settings import Settings
from flare.utils.timing import timer


class ApertureTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)
        self.settings = Settings()
        self.kernel = None
        self.build()

    def build(self, *args, **kwargs):
        self.source = self.read_source_file('aperture.cl')
        super().build()
        self.kernel = cl.Kernel(self.program, 'aperture')

    @lru_cache(10)
    def load_file(
        self,
        file: File,
        resolution: QtCore.QSize,
        threshold: float = 1,
    ) -> Image:
        file_path = str(file)

        # load array
        array = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE | cv2.IMREAD_ANYDEPTH)

        # resize array
        array = cv2.resize(array, (resolution.width(), resolution.height()))

        # convert to float32
        if array.dtype == np.uint8:
            array = np.divide(array, 255)
        array = np.float32(array)

        # apply threshold
        if threshold != 1:
            threshold, array = cv2.threshold(array, threshold, 1, cv2.THRESH_BINARY)

        # return image
        args = (file_path, resolution, threshold)
        image = Image(self.context, array=array, args=args)
        return image

    def draw(self, aperture: Image) -> None:
        w, h = aperture.image.shape
        global_work_size = (w, h)
        local_work_size = None
        cl.enqueue_nd_range_kernel(
            self.queue, self.kernel, global_work_size, local_work_size
        )
        cl.enqueue_copy(
            self.queue, aperture.array, aperture.image, origin=(0, 0), region=(w, h)
        )

    @lru_cache(10)
    def aperture(self, aperture_config: Aperture, resolution: QtCore.QSize) -> Image:
        if self.rebuild:
            self.build()

        # args
        aperture = self.update_image(
            resolution, cl.channel_order.INTENSITY, cl.mem_flags.READ_WRITE
        )
        aperture.args = (aperture_config, resolution)

        # run program
        self.kernel.set_arg(0, aperture.image)
        self.kernel.set_arg(1, np.int32(aperture_config.blades))
        self.kernel.set_arg(2, np.float32(aperture_config.softness))
        self.kernel.set_arg(3, np.float32(aperture_config.fstop))
        self.draw(aperture)

        return aperture

    @timer
    def run(
        self,
        aperture_config: Aperture,
        quality_config: Render.Quality.Starburst | Render.Quality.Ghost,
    ) -> Image:
        if aperture_config.file:
            file_path = self.settings.decode_path(aperture_config.file)
            image = self.load_file(File(file_path), quality_config.resolution)
        else:
            image = self.aperture(aperture_config, quality_config.resolution)
        return image
