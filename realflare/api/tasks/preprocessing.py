import logging
from functools import lru_cache

import cv2
import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from realflare.api.data import Flare, Render
from realflare.api.path import File
from realflare.api.tasks.opencl import OpenCL, Buffer, Image
from realflare.api.tasks.raytracing import RaytracingTask
from qt_extensions.typeutils import hashable_dict
from realflare.gui.settings import Settings


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


class ImageSamplingTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)
        self.settings = Settings()

    @lru_cache(10)
    def update_sample_data(
        self, file: File, resolution: QtCore.QSize, threshold: float
    ) -> np.ndarray:
        file_path = str(file)

        # load array
        array = cv2.imread(file_path, cv2.IMREAD_COLOR | cv2.IMREAD_ANYDEPTH)
        array = cv2.cvtColor(array, cv2.COLOR_BGR2RGB)

        # resize array
        array = cv2.resize(array, (resolution.width(), resolution.height()))

        # convert to float32
        if array.dtype == np.uint8:
            array = np.divide(array, 255)
        array = np.float32(array)

        # apply threshold
        def threshold_func(c):
            intensity = (c[0] + c[1] + c[2]) / 3
            if intensity < threshold:
                return np.zeros((3,))
            return c

        sample_data = np.apply_along_axis(threshold_func, 2, array)

        return sample_data

    def run(self, flare: Flare, render: Render) -> np.ndarray:
        file_path = self.settings.decode_path(flare.image_file)

        # resolution
        width = max(flare.image_samples, 1)
        if width % 2 != 0:
            width += 1
        ratio = render.quality.resolution.height() / render.quality.resolution.width()
        height = width * ratio
        if height % 2 != 0:
            height += 1
        resolution = QtCore.QSize(width, height)

        sample_data = self.update_sample_data(
            File(file_path), resolution, flare.image_threshold
        )
        return sample_data
