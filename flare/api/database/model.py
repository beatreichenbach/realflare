from __future__ import annotations

import enum
import random

import numpy as np
from pydantic import BaseModel


class HashableModel(BaseModel):
    def __hash__(self) -> int:
        return hash(self.model_dump_json())


class Lens(HashableModel):
    class Surface(HashableModel):
        class SurfaceType(enum.Enum):
            STOP = 'STOP'
            STANDARD = 'STANDARD'
            EVEN_ASPHERIC = 'EVENASPH'
            EXTENDED_ASPHERIC = 'XASPHERE'
            EXTENDED_ODD_ASPHERIC = 'XOSPHERE'
            CYLINDER_X = 'CYLINDER_X'
            CYLINDER_Y = 'CYLINDER_Y'

        type: SurfaceType
        radius: float
        spacing: float
        curvature: float = 0
        ior: float = 1
        abbe: float = 0
        coefficients: tuple[float, ...] = ()
        conic: float = 0

    name: str
    vendor: str = ''
    note: str = ''
    surfaces: tuple[Surface, ...] = ()
    fstop: float = 0.0
    focal_length: float = 0.0

    def get_coatings(
        self, wavelength_range: tuple[int, int], ior_range: tuple[float, float]
    ) -> tuple[tuple[int, float], ...]:
        """
        Return randomized coatings for a Lens.

        https://en.wikipedia.org/wiki/Anti-reflective_coating#Single-layer_interference
        Coating materials have IOR in the ranges of 1.38-2.2. There are materials
        available with refractive indexes as low as 1.12.

        | Material                   | Typical IOR |
        | -------------------------- | ----------- |
        | MgF₂  (Magnesium Fluoride) | ~1.38       |
        | SiO₂  (Silicon Dioxide)    | ~1.45       |
        | Al₂O₃ (Aluminum Oxide)     | ~1.6        |
        | TiO₂  (Titanium Dioxide)   | ~2.4–2.6    |
        | ZrO₂  (Zirconium Dioxide)  | ~2.1–2.2    |
        | Ta₂O₅ (Tantalum Pentoxide) | ~2.1–2.3    |
        | HfO₂  (Hafnium Dioxide)    | ~1.9–2.1    |
        | Nb₂O₅ (Niobium Pentoxide)  | ~2.2        |
        """

        previous_ior = 1
        coatings = []
        for i, surface in enumerate(self.surfaces):

            current_ior = surface.ior

            # No coating for two surfaces of similar IOR
            if (previous_ior > 1) is (current_ior > 1):
                coating = (0, 0)

            # No coating for the aperture
            elif surface.type == Lens.Surface.SurfaceType.STOP:
                coating = (0, 0)

            # No coating for the sensor
            elif i == len(self.surfaces) - 1:
                coating = (0, 0)

            else:
                wavelength = random.randint(*wavelength_range)
                ior = random.uniform(*ior_range)
                coating = (wavelength, ior)

            coatings.append(coating)
            previous_ior = current_ior

        return tuple(coatings)


class Material(HashableModel):
    name: str
    ior: float
    abbe: float
    formula: int
    coefficients: tuple[float, ...]
    vendor: str = ''

    def get_ior(self, wavelength: float) -> float:
        """Return the IOR for a wavelength in nm using the Sellmeier equation."""

        # The sellmeier equation expects lambda to be in micrometer.
        w = wavelength * 1e-3
        w2 = w**2

        if self.formula == 1 and len(self.coefficients) >= 5:
            # n^2 - 1 = A + (B1 * w^2) / (w^2 - C1^2) + (B2 * w^2) / (w^2 - C2^2)

            a, b1, c1, b2, c2 = self.coefficients
            d0 = a
            d1 = (b1 * w2) / (w2 - c1**2)
            d2 = (b2 * w2) / (w2 - c2**2)
            ior = np.sqrt(d0 + d1 + d2 + 1)

        elif self.formula == 2 and len(self.coefficients) >= 7:
            # n^2 - 1 = A + (B1 * w^2) / (w^2 - C1) +
            #               (B2 * w^2) / (w^2 - C2) +
            #               (B3 * w^2) / (w^2 - C3)

            a, b1, c1, b2, c2, b3, c3 = self.coefficients[:7]
            d0 = a
            d1 = (b1 * w2) / (w2 - c1)
            d2 = (b2 * w2) / (w2 - c2)
            d3 = (b3 * w2) / (w2 - c3)
            ior = np.sqrt(d0 + d1 + d2 + d3 + 1)

        elif self.formula == 3 and len(self.coefficients) >= 2:
            # n^2 = A + B*w^C + D*w^E + F*w^G + ...

            a = self.coefficients[0]
            remainder = self.coefficients[1:]
            total = a
            for i in range(len(remainder) // 2):
                b = remainder[i * 2]
                c = remainder[i * 2 + 1]
                total += b * pow(w, c)
            ior = np.sqrt(total)

        else:
            ior = 1.0

        return float(ior)


class Cache(BaseModel):
    materials: tuple[Material, ...]
    lenses: tuple[Lens, ...]
