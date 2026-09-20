from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from typing import Any

import pydantic

from ..model import Lens
from .base import Parser
from .common import parse_float

logger = logging.getLogger(__name__)


class ZemaxParser(Parser[Lens]):
    """Parser for Zemax .zmx files."""

    supported_extensions: tuple[str, ...] = ('.zmx',)

    def parse(self, path: str) -> Lens | None:
        """Return a Lens from a .zmx file, or None if invalid."""

        filename = os.path.basename(path)
        name, ext = os.path.splitext(filename)
        if ext not in self.supported_extensions:
            logger.warning(f'Unsupported extension: {ext}')
            return None
        try:
            with open(path, encoding='utf-8') as file:
                lines = file.readlines()
        except OSError as e:
            logger.warning(f'Failed to read file: {path}', exc_info=e)
            return None

        # Camera
        kwargs: dict[str, Any] = {
            'name': name,
            'fstop': self._get_fstop(name),
            'focal_length': self._get_focal_length(name),
        }
        for line in lines:
            if not line.strip():
                continue

            parts = line.strip().split(maxsplit=1)
            key = parts[0]
            text = parts[1] if len(parts) == 2 else ''

            if key == 'NOTE':
                kwargs['note'] = text.strip('0 ')
            elif key == 'FNUM':
                parts = text.split()
                kwargs['fstop'] = parse_float(parts[0])

        # Surfaces
        surfaces = self._get_surfaces(lines)
        if not surfaces:
            return None
        kwargs['surfaces'] = surfaces

        # Lens
        try:
            lens = Lens.model_validate(kwargs)
        except pydantic.ValidationError as e:
            logger.warning(f'ValidationError: {path}', exc_info=e)
            return None

        return lens

    @staticmethod
    def _get_surfaces(lines: Sequence[str]) -> tuple[dict[str, Any], ...]:
        """Return a tuple of surface dictionaries from the file."""

        surfaces: list[dict[str, Any]] = []

        surface: dict[str, Any] | None = None
        for line in lines:
            if not line.strip():
                continue

            # Append the surface
            if isinstance(surface, dict) and not line.startswith(' '):
                surfaces.append(surface)
                surface = None

            parts = line.strip().split(maxsplit=1)
            key = parts[0]
            text = parts[1] if len(parts) == 2 else ''

            if key == 'SURF':
                surface = {}
                continue

            if surface is None:
                continue

            if key == 'TYPE':
                # NOTE: Zemax types: (STANDARD, EVENASPH, XASPHERE, XOSPHERE )
                #       Custom types: (STOP, CYLINDER_X, CYLINDER_Y)

                if surface.get('type'):
                    continue
                try:
                    value = Lens.Surface.SurfaceType(text)
                except ValueError:
                    logger.debug(f'Invalid Surface Type {text!r}.')
                    continue
                surface['type'] = value

            elif key == 'STOP':
                # NOTE: STOP = 1 marks the current surface as the aperture.

                surface['type'] = Lens.Surface.SurfaceType.STOP

            elif key == 'CURV':
                # NOTE: CURV is 1 / radius of the spherical surface.

                parts = text.split()
                surface['curvature'] = parse_float(parts[0])

            elif key == 'DISZ':
                # NOTE: DISZ is the spacing in Z axis to the next surface.

                surface['spacing'] = parse_float(text)

            elif key == 'GLAS':
                # NOTE: GLAS is a material with format: "___BLANK 1 0 {IOR} {ABBE} ..."

                parts = text.split()
                if len(parts) < 4:
                    logger.debug(f'Invalid glass format {text!r}.')
                    continue
                elif len(parts) < 5:
                    abbe = 60
                else:
                    abbe = parse_float(parts[4])
                ior = parse_float(parts[3])

                surface['ior'] = ior
                surface['abbe'] = abbe

            elif key == 'DIAM':
                # NOTE: DIAM is the Clear Diameter.
                parts = text.split()
                surface['radius'] = parse_float(parts[0])

            elif key == 'CONI':
                # NOTE: CONI is the Conic Constant (k)

                parts = text.split()
                surface['conic'] = parse_float(parts[0])

            elif key == 'PARM':
                # NOTE: PARM are the polynomial coefficients for even aspheric surfaces.

                parts = text.split()
                if len(parts) < 3:
                    continue

                index = int(parse_float(parts[0]))
                value = parse_float(parts[1])

                if index < 1 or index > 8:
                    continue

                coefficients = surface.get('coefficients', [0.0] * 8)
                coefficients[index - 1] = value
                surface['coefficients'] = coefficients

            elif key == 'XDAT':
                # NOTE: XDAT is extra data for extended aspheric surfaces.
                #       XDAT 1 is the max order. This is inferred from the tuple length.
                #       XDAT 2 is the norm radius mode. This is ignored.

                parts = text.split()
                if len(parts) < 3:
                    continue

                index = int(parse_float(parts[0]))
                value = parse_float(parts[1])

                if index < 1:
                    continue

                if surface.get('type') == Lens.Surface.SurfaceType.EXTENDED_ASPHERIC:
                    # NOTE: XDAT 3 is the term mode. 0 = Even powers, 1 = All powers.
                    #       XDAT 4+ are polynomial coefficients where 4 is a1

                    start = 4

                elif (
                    surface.get('type')
                    == Lens.Surface.SurfaceType.EXTENDED_ODD_ASPHERIC
                ):
                    # Note: XDAT 3+ are polynomial coefficients where 3 is A1

                    start = 3
                else:
                    continue

                if index >= start:
                    coefficients = surface.get('coefficients', [])
                    # Pad to max length with 0.
                    max_length = max(0, (index - start + 1) - len(coefficients))
                    coefficients += [0.0] * max_length
                    coefficients[index - start] = value
                    surface['coefficients'] = coefficients

        # Append surface in case file ends on last surface.
        if isinstance(surface, dict):
            surfaces.append(surface)

        # Only keep relevant surfaces.
        surfaces = [s for s in surfaces if s.get('spacing') != float('inf')]

        return tuple(surfaces)

    @staticmethod
    def _get_focal_length(name: str) -> float:
        """Return the best guess for the focal length from a name."""

        if match := re.search(r'(:?([\d.]+)-)?([\d.]+)mm', name.lower()):
            if text := match.group(1):
                try:
                    return float(text)
                except ValueError:
                    pass
            if text := match.group(2):
                try:
                    return float(text)
                except ValueError:
                    pass

        # NOTE: Fall back to finding the most likely number.
        texts = re.findall(r'[\d.]+', name.lower())
        for text in texts:
            try:
                number = float(text)
                if number > 10:
                    return number
            except ValueError:
                pass

        return 0

    @staticmethod
    def _get_fstop(name: str) -> float:
        """Return the best guess for the fstop from a name."""

        if match := re.search(r'\sf([\d.]+)', name.lower()):
            try:
                return float(match.group(1))
            except ValueError:
                pass

        # NOTE: Fall back to finding the most likely number.
        texts = re.findall(r'[\d.]+', name)
        for text in texts:
            try:
                number = float(text)
                if number < 10:
                    return number
            except ValueError:
                pass

        return 0
