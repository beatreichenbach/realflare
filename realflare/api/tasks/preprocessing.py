from functools import lru_cache

import cv2
import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from realflare.api.data import Project
from realflare.api.path import File
from realflare.api.tasks.opencl import OpenCL, Buffer
from realflare.api.tasks.raytracing import RaytracingTask
from qt_extensions.typeutils import HashableDict

from realflare.storage import Storage


storage = Storage()


def apply_threshold(array: np.ndarray, threshold: float) -> np.ndarray:
    # flatten the array to a 1-dimensional array
    intensity_array = np.mean(array, axis=2, keepdims=True)
    intensity_array = intensity_array.ravel()

    # determine the index that corresponds to the nth percentile
    index = np.percentile(intensity_array, threshold * 100)

    # create a boolean mask that selects all values greater than the value at the index
    mask = intensity_array > index
    # mask = np.broadcast_to(mask, (mask.shape[0], mask., 3))

    # ise the boolean mask to create a new array where the lowest values are set to 0
    masked_array = np.reshape(array.copy(), (-1, 3))

    masked_array[~mask] = np.zeros((3,), np.float32)

    masked_array = masked_array.reshape(array.shape)
    return masked_array


class PreprocessTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)
        self.raytracing_task = RaytracingTask(queue)

    @lru_cache(10)
    def update_areas(self, rays: Buffer) -> HashableDict[int, float]:
        # generate a dict of areas where key=path_index and area is the area
        # of the top left quad
        path_count, wavelength_count, ray_count = rays.array.shape
        cl.enqueue_copy(self.queue, rays.array, rays.buffer)

        areas = HashableDict()
        for path in range(path_count):
            ray = rays.array[path, 0, 0]
            area = np.abs(ray['pos']['x']) * np.abs(ray['pos']['x'])
            areas[path] = area
        return areas

    @lru_cache(10)
    def update_path_indexes(
        self, areas: HashableDict[int, float], percentage: float
    ) -> tuple[int]:
        sorted_areas = sorted(areas.items(), key=lambda item: item[1])
        index_to_keep = int(len(sorted_areas) * (1 - percentage))
        path_indexes = tuple(int(k) for k, v in sorted_areas[:index_to_keep])
        return path_indexes

    def run(self, project: Project) -> tuple[int]:
        grid_length = project.render.grid_length
        rays = self.raytracing_task.raytrace(
            light_position=(0, 0),
            lens=project.flare.lens,
            grid_count=3,
            grid_length=grid_length * 0.01,
            resolution=QtCore.QSize(100, 100),
            wavelength_count=1,
            store_intersections=False,
        )
        if rays is None:
            return tuple()
        areas = self.update_areas(rays)
        cull_percentage = project.render.cull_percentage
        path_indexes = self.update_path_indexes(areas, cull_percentage)
        return path_indexes


class ImageSamplingTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)

    @lru_cache(10)
    def update_sample_data(
        self, file: File, resolution: QtCore.QSize, samples: int
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
        # TODO: don't need threshold anymore
        threshold = 1 - (samples / resolution.width() * resolution.height())
        sample_data = apply_threshold(array, threshold)

        return sample_data

    def run(self, project: Project) -> np.ndarray:
        file_path = storage.decode_path(project.flare.image_file)

        # resolution
        width = max(project.flare.light.image_sample_resolution, 1)
        if width % 2 != 0:
            width += 1

        resolution = project.render.resolution
        ratio = resolution.height() / resolution.width()
        height = width * ratio
        if height % 2 != 0:
            height += 1
        sample_resolution = QtCore.QSize(width, height)

        sample_data = self.update_sample_data(
            File(file_path), sample_resolution, project.flare.light.image_samples
        )
        return sample_data
