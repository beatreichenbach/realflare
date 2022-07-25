import logging

import numpy as np
import pyopencl as cl

from flare.api import data
from flare.api.tasks.opencl import OpenCL
from flare.utils.timing import timer


class CompositingTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)

        self.source += self.read_source_file('compositing.cl')
        self.build()
        self.kernel = cl.Kernel(self.program, 'composite')

    def composite(self, image: np.ndarray, image_cl: cl.Image) -> cl.Event:
        w, h = image_cl.shape
        global_work_size = (w, h)
        local_work_size = None

        event = cl.enqueue_nd_range_kernel(
            self.queue,
            self.kernel,
            global_work_size,
            local_work_size,
        )

        cl.enqueue_copy(self.queue, image, image_cl, origin=(0, 0), region=(w, h))
        return event

    @timer
    def run(
        self,
        flare_cl: cl.Image,
        starburst_cl: cl.Image,
        flare_config: data.Flare,
        render_config: data.Render,
    ) -> tuple[np.ndarray, cl.Image]:
        resolution = render_config.quality.resolution
        w, h = resolution.width(), resolution.height()

        image, image_cl = self.update_image(resolution)

        if not render_config.disable_starburst and not render_config.disable_ghosts:
            return image, image_cl
        else:
            starburst_scale = flare_config.starburst.scale
            starburst_resolution = render_config.quality.starburst_resolution
            factor = resolution.width() / starburst_resolution.width()
            scale = starburst_scale * factor
            light_position = flare_config.light_position

            # TODO: remove temp: rebuild kernel
            if True:
                self.__init__(self.queue)

            if render_config.disable_starburst:
                image_cl = flare_cl
            else:
                self.kernel.set_arg(0, flare_cl)
                self.kernel.set_arg(1, flare_cl)
                self.kernel.set_arg(2, starburst_cl)
                self.kernel.set_arg(3, np.float32(data.to_basic_type(light_position)))
                self.kernel.set_arg(4, np.float32(data.to_basic_type(scale)))

                self.composite(image, image_cl)

            cl.enqueue_copy(self.queue, image, image_cl, origin=(0, 0), region=(w, h))
            return image, image_cl
