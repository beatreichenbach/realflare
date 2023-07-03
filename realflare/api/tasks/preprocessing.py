import logging
from functools import lru_cache

import cv2
import numpy as np
import pyopencl as cl
from PySide2 import QtCore

from qt_extensions.typeutils import HashableDict
from realflare.api import lens as api_lens
from realflare.api.data import Project, RealflareError, LensModel
from realflare.api.path import File
from realflare.api.tasks.opencl import OpenCL, Buffer
from realflare.api.tasks.raytracing import RaytracingTask
from realflare.storage import Storage
from realflare.utils.timing import timer

logger = logging.getLogger(__name__)
storage = Storage()


class PreprocessTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)
        self.raytracing_task = RaytracingTask(queue)

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

    @lru_cache(1)
    def preprocess(
        self,
        lens_model: LensModel,
        sensor_size: tuple[float, float],
        glasses_path: str,
        abbe_nr_adjustment: float,
        coating: tuple[int, ...],
        coating_min_ior: float,
        grid_length: float,
        cull_percentage: float,
    ) -> tuple[int, ...]:
        # args
        grid_count = 3
        grid_length = grid_length * 0.01
        resolution = QtCore.QSize(100, 100)
        light_position = (0, 0)
        wavelength_count = 1
        path_indexes = tuple()

        rays = self.raytracing_task.raytrace(
            lens_model=lens_model,
            sensor_size=sensor_size,
            glasses_path=glasses_path,
            abbe_nr_adjustment=abbe_nr_adjustment,
            coating=coating,
            coating_min_ior=coating_min_ior,
            grid_count=grid_count,
            grid_length=grid_length,
            light_position=light_position,
            resolution=resolution,
            wavelength_count=wavelength_count,
            path_indexes=path_indexes,
        )

        if rays is None:
            return tuple()

        areas = self.update_areas(rays)

        # cull path_indexes up to cull_percentage
        sorted_areas = sorted(areas.items(), key=lambda item: item[1])
        index_to_keep = int(len(sorted_areas) * (1 - cull_percentage))
        path_indexes = tuple(int(k) for k, v in sorted_areas[:index_to_keep])

        return path_indexes

    @timer
    def run(self, project: Project) -> tuple[int, ...]:
        lens = project.flare.lens
        sensor_size = lens.sensor_size.width(), lens.sensor_size.height()
        lens_model = api_lens.model_from_path(lens.lens_model_path)

        path_indexes = self.preprocess(
            lens_model=lens_model,
            sensor_size=sensor_size,
            glasses_path=lens.glasses_path,
            abbe_nr_adjustment=lens.abbe_nr_adjustment,
            coating=lens.coating,
            coating_min_ior=lens.coating_min_ior,
            grid_length=project.render.grid_length,
            cull_percentage=project.render.cull_percentage,
        )
        return path_indexes


class ImageSamplingTask(OpenCL):
    def __init__(self, queue: cl.CommandQueue) -> None:
        super().__init__(queue)

    @lru_cache(1)
    def load_file(self, file: File) -> np.ndarray:
        # load array
        file_path = str(file)
        try:
            array = cv2.imread(file_path, cv2.IMREAD_COLOR | cv2.IMREAD_ANYDEPTH)
            array = cv2.cvtColor(array, cv2.COLOR_BGR2RGB)
        except ValueError as e:
            logger.debug(e)
            message = f'Invalid Image path for flare light: {file_path}'
            raise RealflareError(message) from None

        # convert to float32
        if array.dtype == np.uint8:
            array = np.divide(array, 255)
        array = np.float32(array)

        return array

    @lru_cache(1)
    def update_sample_data(
        self, file: File, resolution: QtCore.QSize, samples: int
    ) -> np.ndarray:
        array = self.load_file(file)

        # resize array
        array = cv2.resize(array, (resolution.width(), resolution.height()))

        # flatten the array to a 1-dimensional array
        intensity_array = np.mean(array, axis=2, keepdims=True)
        intensity_array = intensity_array.ravel()

        # percentile
        try:
            threshold = 1 - (samples / len(intensity_array))
        except ZeroDivisionError:
            threshold = 0
        threshold = np.clip(threshold * 100, 0, 100)
        percentile = np.percentile(intensity_array, threshold)

        # create a boolean mask of all values greater than the percentile
        mask = intensity_array > percentile

        # use the boolean mask to create a new array where the lowest values are set to 0
        masked_array = np.reshape(array.copy(), (-1, 3))
        masked_array[~mask] = np.zeros((3,), np.float32)
        masked_array = masked_array.reshape(array.shape)

        rgba = np.dstack((masked_array, np.zeros(masked_array.shape[:-1])))

        return rgba

    @timer
    def run(self, project: Project) -> np.ndarray:
        # file
        file_path = storage.decode_path(project.flare.light.image_file)
        file = File(file_path)

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

        # samples
        samples = project.flare.light.image_samples

        sample_data = self.update_sample_data(file, sample_resolution, samples)

        return sample_data
