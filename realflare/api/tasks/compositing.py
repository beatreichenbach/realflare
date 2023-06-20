from functools import lru_cache

import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from qt_extensions.typeutils import cast_basic
from realflare.api.data import Project
from realflare.api.tasks.opencl import OpenCL, Image
from realflare.utils.timing import timer


class CompositingTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)
        self.kernel = None
        self.build()

    def build(self, *args, **kwargs) -> None:
        self.source = self.read_source_file('geometry.cl')
        self.source += self.read_source_file('compositing.cl')
        super().build()
        self.kernel = cl.Kernel(self.program, 'composite')

    @lru_cache(1)
    def composite(
        self,
        flare: Image,
        starburst: Image,
        light_position: tuple[float, float],
    ) -> Image:
        if self.rebuild:
            self.build()

        w, h = flare.image.shape
        resolution = QtCore.QSize(w, h)

        # args
        composite = self.update_image(resolution)
        composite.args = (flare, starburst, light_position)

        position = np.array((1, 1), cl.cltypes.float2)
        position['x'] = light_position[0]
        position['y'] = light_position[1]

        # kernels
        global_work_size = (w, h)
        local_work_size = None

        self.kernel.set_arg(0, composite.image)
        self.kernel.set_arg(1, flare.image)
        self.kernel.set_arg(2, starburst.image)
        self.kernel.set_arg(3, position)
        cl.enqueue_nd_range_kernel(
            self.queue, self.kernel, global_work_size, local_work_size
        )
        cl.enqueue_copy(
            self.queue,
            composite.array,
            composite.image,
            origin=(0, 0),
            region=(w, h),
        )

        return composite

    @timer
    def run(self, project: Project, flare: Image, starburst: Image) -> Image:
        position = tuple(cast_basic(project.flare.light.position))
        return self.composite(flare, starburst, position)
