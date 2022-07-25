from functools import lru_cache

import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from realflare.api.data import Flare, Render
from realflare.api.tasks.opencl import OpenCL, Buffer
from realflare.api.tasks.raytracing import RaytracingTask
from qt_extensions.typeutils import hashable_dict


class PreprocessTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)
        self.raytracing_task = RaytracingTask(queue)

    @lru_cache(10)
    def update_areas(self, rays: Buffer) -> hashable_dict[int, float]:
        # generate a dict of areas where key=path_index and area is the area of the top left quad
        path_count, wavelength_count, ray_count = rays.array.shape
        cl.enqueue_copy(self.queue, rays.array, rays.buffer)

        areas = hashable_dict()
        for path in range(path_count):
            ray = rays.array[path, 0, 0]
            area = np.abs(ray['pos']['x']) * np.abs(ray['pos']['x'])
            areas[path] = area
        return areas

    @lru_cache(10)
    def update_path_indexes(
        self, areas: hashable_dict[int, float], percentage: float
    ) -> tuple[int]:
        sorted_areas = sorted(areas.items(), key=lambda item: item[1])
        index_to_keep = int(len(sorted_areas) * (1 - percentage))
        path_indexes = tuple(int(k) for k, v in sorted_areas[:index_to_keep])
        return path_indexes

    def run(self, flare: Flare, render: Render) -> tuple[int]:
        grid_length = render.quality.grid_length
        rays = self.raytracing_task.raytrace(
            light_position=(0, 0),
            lens=flare.lens,
            grid_count=3,
            grid_length=grid_length * 0.01,
            resolution=QtCore.QSize(100, 100),
            wavelength_count=1,
            store_intersections=False,
        )
        areas = self.update_areas(rays)
        path_indexes = self.update_path_indexes(areas, render.quality.cull_percentage)
        return path_indexes
