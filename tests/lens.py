from dataclasses import dataclass
from typing import List, Tuple
import json
import numpy as np
import logging

from realflare.api import glass


def sellmeier_equation(wavelength, coefficients):
    wavelength *= 1e-3  # nanometer to micrometer
    l2 = wavelength * wavelength
    d0 = (coefficients[0] * l2) / (l2 - coefficients[1])
    d1 = (coefficients[2] * l2) / (l2 - coefficients[3])
    d2 = (coefficients[4] * l2) / (l2 - coefficients[5])
    return np.sqrt(1 + d0 + d1 + d2)


def fresnel_ar(theta0, wavelength, d1, n0, n1, n2):
    # refraction angles in coating and the 2n dmedium
    theta1 = np.arcsin(np.sin(theta0) * n0 / n1)
    theta2 = np.arcsin(np.sin(theta0) * n0 / n2)

    # amplitude for outer refl. / transmission on topmost interface
    rs01 = -np.sin(theta0 - theta1) / np.sin(theta0 + theta1)
    rp01 = np.tan(theta0 - theta1) / np.tan(theta0 + theta1)
    ts01 = 2 * np.sin(theta1) * np.cos(theta0) / np.sin(theta0 + theta1)
    tp01 = ts01 * np.cos(theta0 - theta1)

    # amplitude for inner reflection
    rs12 = -np.sin(theta1 - theta2) / np.sin(theta1 + theta2)
    rp12 = np.tan(theta1 - theta2) / np.tan(theta1 + theta2)

    # after passing through first surface twice:
    # 2 transmissions and 1 reflection
    ris = ts01 * ts01 * rs12
    rip = tp01 * tp01 * rp12

    # phase difference between outer and inner reflections
    dy = d1 * n1
    dx = np.tan(theta1) * dy
    delay = np.sqrt(dx * dx + dy * dy)
    relPhase = 4 * np.pi / wavelength * (delay - dx * np.sin(theta0))

    # Add up sines of different phase and amplitude
    out_s2 = rs01 * rs01 + ris * ris + 2 * rs01 * ris * np.cos(relPhase)
    out_p2 = rp01 * rp01 + rip * rip + 2 * rp01 * rip * np.cos(relPhase)
    reflectiviy = (out_s2 + out_p2) / 2

    return reflectiviy


def main():
    import os

    logging.getLogger().setLevel(logging.DEBUG)

    presets_abs_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../presets')
    )
    # lens_file = 'tronnier_color-heliar.json'
    # lens_file = 'canon_ef70-200mm-f2.8l-usm.json'
    lens_file = 'nikon_28-70mm.json'
    lens_path = os.path.join(presets_abs_path, lens_file)
    lenses = lenses_from_json(lens_path)
    # for l in lenses:
    #     logging.debug(l)

    for lens in lenses:
        glass = lens.glass
        if glass:
            logging.debug(glass)
            wavelength = 589.3
            wavelength = 545

            # refractive index
            logging.debug(f'lens n: {lens.refractive_index}, v: {lens.v}')
            n_sellmeier = sellmeier_equation(wavelength, glass.coefficients)
            logging.debug(f'glass n: {n_sellmeier}')

            # # fresnel
            # nc = 1.38
            # lambda0 = 537

            # # unit scale doesn't make a difference
            # # lambda0 *= 1e-9
            # # wavelength *= 1e-9

            # d1 = lambda0 / (4 * nc)
            # theta0 = np.radians(30)
            # logging.debug(f'theta0: {theta0}')

            # n0 = 1.53024
            # n2 = 1
            # logging.debug(f'n0 / nc: {n0 / nc}')
            # logging.debug(f'n0 / n2: {n0 / n2}')
            # fresnel = fresnel_ar(theta0, wavelength, d1, n0, nc, n2)
            # logging.debug(f'fresnel: {fresnel}')


if __name__ == '__main__':
    main()
