import logging
import os
from functools import lru_cache

import numpy as np

from qt_extensions.typeutils import cast
from realflare.api import glass
from realflare.api.data import LensModel, RealflareError
from realflare.api.path import File
from realflare.storage import Storage

logger = logging.getLogger(__name__)
storage = Storage()


@lru_cache(1)
def model(file: File) -> LensModel:
    file_path = str(file)
    data = storage.read_data(file_path)
    lens_model = cast(LensModel, data)
    return lens_model


def model_from_path(lens_model_path: str) -> LensModel:
    if not lens_model_path:
        raise RealflareError('No Lens Model')

    filename = storage.decode_path(lens_model_path)
    try:
        lens_model_file = File(filename)
        lens_model = model(lens_model_file)
    except (OSError, ValueError) as e:
        logger.debug(e)
        message = f'Invalid Lens Model: {filename}'
        raise RealflareError(message) from None
    return lens_model


def elements(
    lens_model: LensModel,
    sensor_size: tuple[float, float],
    glasses_path: str,
    abbe_nr_adjustment: float,
    coating: tuple[int, ...],
    dtype: np.dtype,
) -> np.ndarray:
    # make copy of mutable attribute
    lens_elements = list(lens_model.lens_elements)

    # append sensor as element
    sensor_length = np.linalg.norm(sensor_size) / 2
    lens_elements.append(LensModel.LensElement(height=sensor_length))

    # glasses
    path = storage.decode_path(glasses_path)
    glasses = tuple(glass.glasses_from_path(path))

    # array
    array = np.zeros(len(lens_elements), dtype)
    if not glasses:
        array[0]['coefficients'][0] = np.NAN

    offset = 0
    for i, lens_element in enumerate(lens_elements):
        array[i]['radius'] = lens_element.radius
        array[i]['ior'] = lens_element.refractive_index
        array[i]['height'] = lens_element.height
        array[i]['center'] = offset + lens_element.radius

        if i < len(coating):
            array[i]['coating'] = coating[i]

        # glass
        closest_glass = glass.closest_glass(
            glasses,
            lens_element.refractive_index,
            lens_element.abbe_nr,
            abbe_nr_adjustment,
        )
        if closest_glass:
            for j in range(6):
                array[i]['coefficients'][j] = closest_glass.coefficients[j]
        offset += lens_element.distance

    return array


def ray_paths(
    lens_model: LensModel, path_indexes: tuple[int, ...]
) -> list[tuple[int, int]]:
    # create paths that describe possible paths the rays can travel
    # path = (first bounce, 2nd bounce)
    # the ray can only bounce either before or after the aperture
    # the last lens is the sensor. max: lens_elements_count - 1
    paths = []
    lens_elements_count = len(lens_model.lens_elements)
    index_min = 0
    for bounce1 in range(1, lens_elements_count - 1):
        if bounce1 == lens_model.aperture_index:
            index_min = bounce1 + 1
        for bounce2 in range(index_min, bounce1):
            paths.append((bounce1, bounce2))

    # debug / optimization
    if path_indexes:
        paths = [p for i, p in enumerate(paths) if i in path_indexes]

    if path_indexes == (-1,):
        # no bounces
        paths = [(-1, -1)]

    return paths


def model_paths(path: str = '') -> dict:
    if not path:
        path = storage.path_vars['$MODEL']

    models = {}
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path):
            if not item.endswith('.json'):
                continue
            try:
                data = storage.read_data(item_path)
            except ValueError:
                continue
            lens_model = cast(LensModel, data)
            models[lens_model.name] = storage.encode_path(item_path)
        elif os.path.isdir(item_path):
            children = model_paths(item_path)
            if children:
                models[item] = children
    return models
