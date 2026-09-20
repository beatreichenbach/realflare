import logging
import os

import yaml

from ..model import Material
from .base import Parser
from .common import parse_float

logger = logging.getLogger(__name__)


class MtrlParser(Parser[Material]):
    """Parser for .mtrl material files."""

    supported_extensions: tuple[str, ...] = ('.mtrl',)

    def parse(self, path: str) -> Material | None:
        """Return a Material from a .mtrl file, or None if invalid."""

        filename = os.path.basename(path)
        name, ext = os.path.splitext(filename)
        if ext not in self.supported_extensions:
            logger.warning(f'Unsupported extension: {ext}')
            return None

        try:
            with open(path) as file:
                data = yaml.safe_load(file)
        except OSError as e:
            logger.warning(f'Failed to read file: {path}', exc_info=e)
            return None

        # Specs
        specs = data.get('SPECS')
        if not specs:
            return None

        ior = specs.get('nd') or specs.get('Nd')
        abbe = specs.get('vd') or specs.get('Vd')

        if ior is None or abbe is None:
            return None

        # Formula
        formula = None
        coefficients = None
        for item in data.get('DATA', ()):
            if not isinstance(item, dict):
                continue

            type_text = item.get('type', '')
            coefficients_text = item.get('coefficients', '')
            if type_text == 'formula 1':
                formula = 1
                coefficients = tuple(
                    parse_float(c) for c in coefficients_text.split(' ')
                )
                break
            elif type_text == 'formula 2':
                formula = 2
                coefficients = tuple(
                    parse_float(c) for c in coefficients_text.split(' ')
                )
                break
            elif type_text == 'formula 3':
                formula = 3
                coefficients = tuple(
                    parse_float(c) for c in coefficients_text.split(' ')
                )
                break
        if formula is None or coefficients is None:
            return None

        # Material
        material = Material(
            name=name, ior=ior, abbe=abbe, formula=formula, coefficients=coefficients
        )
        return material
