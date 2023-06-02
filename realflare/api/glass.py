from __future__ import annotations
import os
import yaml

# https://refractiveindex.info/
# https://en.wikipedia.org/wiki/Sellmeier_equation
# https://en.wikipedia.org/wiki/Abbe_number

from realflare.api.data import Glass


def vendors_from_path(path):
    if not os.path.isdir(path):
        return

    glasses = []
    for vendor in os.listdir(path):
        dir_path = os.path.join(path, vendor)
        if not os.path.isdir(dir_path):
            continue
        glasses.append(glasses_from_path(dir_path))
    return glasses


def glasses_from_path(dir_path):
    if not os.path.isdir(dir_path):
        return

    glasses = []
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

        vendor = os.path.basename(dir_path)
        name, ext = os.path.splitext(file_name)
        g = Glass(name, vendor, nd, vd, coefficients)

        glasses.append(g)
    return glasses


def closest_glass(
    glasses: list[Glass] | tuple[Glass], n: float, v: float, v_offset: float = 0
) -> Glass | None:
    """
    Returns the glass for the given refractive index (n) and Abbe number (v)
    Uses percentage to account for unit differences and euclidean distance to find closest match
    """
    # TODO: handle None returns
    # can default return something that is essential n = 1 for all lambda?
    if n == 0 or v == 0:
        return

    v += v_offset
    differences = []
    for glass in glasses:
        n_diff = 1 - glass.n / n
        v_diff = 1 - glass.v / v
        differences.append(n_diff**2 + v_diff**2)
    if not differences:
        return
    smallest_diff_index = differences.index(min(differences))
    return glasses[smallest_diff_index]


def sellmeier(coefficients, wavelength):
    import math

    # sellmeier equation requires lambda in micrometer
    wavelength *= 1e-3

    l2 = wavelength * wavelength
    d0 = (coefficients[0] * pow(wavelength, 2)) / (l2 - coefficients[1])
    d1 = (coefficients[2] * l2) / (l2 - coefficients[3])
    d2 = (coefficients[4] * l2) / (l2 - coefficients[5])
    return math.sqrt(1 + d0 + d1 + d2)
