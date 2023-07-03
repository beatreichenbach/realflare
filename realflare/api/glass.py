from __future__ import annotations

import logging
import math
import os
from functools import lru_cache

import numpy as np
import yaml

from realflare.api.data import Glass
from realflare.storage import Storage

# https://refractiveindex.info/
# https://en.wikipedia.org/wiki/Sellmeier_equation
# https://en.wikipedia.org/wiki/Abbe_number

logger = logging.getLogger(__name__)
storage = Storage()


def manufacturers() -> dict:
    glasses_path = storage.path_vars['$GLASS']
    glasses = {}
    for item in os.listdir(glasses_path):
        item_path = os.path.join(glasses_path, item)
        if os.path.isdir(item_path):
            glasses[item] = storage.encode_path(item_path)
    return glasses


def glasses_from_path(dir_path: str) -> list[Glass]:
    glasses = []

    if not os.path.isdir(dir_path):
        return glasses

    for file_name in os.listdir(dir_path):
        file_path = os.path.join(dir_path, file_name)
        if not os.path.isfile(file_path):
            continue
        if not file_name.endswith(('.yml', '.yaml')):
            continue

        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        try:
            coefficients = []
            for item in data['DATA']:
                if item['type'] == 'formula 2':
                    coefficients = item['coefficients'].split(' ')
                    coefficients = list(map(float, coefficients[1:]))
                    break
            if not coefficients:
                continue

            nd = data['SPECS'].get('nd') or data['SPECS'].get('Nd')
            vd = data['SPECS'].get('vd') or data['SPECS'].get('Vd')
            if not nd or not vd:
                continue
        except KeyError:
            continue

        manufacturer = os.path.basename(dir_path)
        name, ext = os.path.splitext(file_name)
        g = Glass(name, manufacturer, nd, vd, coefficients)

        glasses.append(g)
    return glasses


@lru_cache(10)
def closest_glass(
    glasses: tuple[Glass, ...], n: float, v: float, v_offset: float = 0
) -> Glass | None:
    if n == 0 or v == 0 or not glasses:
        return

    glass_array = np.array([(glass.n, glass.v) for glass in glasses])
    # use percentage to account for unit differences
    differences = 1 - glass_array / np.array((n, v + v_offset))
    # use euclidean distance to find the closest match
    lengths = np.sum(np.power(differences, 2), axis=1)
    index = int(np.argmin(lengths))

    return glasses[index]


def sellmeier(coefficients: list[float], wavelength: float) -> float:
    # sellmeier equation requires lambda in micrometer
    wavelength *= 1e-3

    l2 = wavelength * wavelength
    d0 = (coefficients[0] * l2) / (l2 - coefficients[1])
    d1 = (coefficients[2] * l2) / (l2 - coefficients[3])
    d2 = (coefficients[4] * l2) / (l2 - coefficients[5])
    refractive_index = math.sqrt(1 + d0 + d1 + d2)
    return refractive_index
