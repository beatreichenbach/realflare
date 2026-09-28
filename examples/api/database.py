import logging

from examples import init
from flare.infrastructure.database import database

logger = logging.getLogger(__name__)


def get_lenses() -> None:
    db = database.Database()
    lenses = db.get_lenses()
    logger.info(f'{len(lenses)} Lenses')


def get_lens() -> None:
    db = database.Database()
    lens = db.get_lens(vendor='Hasselblad', name='Hasselblad XCD 2.8 65')
    assert lens
    logger.info(f'{lens.vendor=}')
    logger.info(f'{lens.name=}')
    logger.info(f'{lens.focal_length=}')
    logger.info(f'{lens.fstop=}')


def get_coatings() -> None:
    db = database.Database()
    lenses = db.get_lenses()
    lens = lenses[0]
    coatings = lens.get_coatings(wavelength_range=(370, 790), ior_range=(1.2, 2.2))
    logger.debug(coatings)


def get_materials() -> None:
    db = database.Database()
    materials = db.get_materials()
    logger.info(f'{len(materials)} Materials')

    vendors = db.get_material_vendors()
    logger.info(vendors)


def get_material() -> None:
    db = database.Database()
    material = db.get_material('Hoya', ior=1.568, abbe=56.04)
    assert material
    assert material.name == 'BAC4'


def get_ior() -> None:
    db = database.Database()
    material = db.get_material('Schott', ior=1.622, abbe=58.2)
    assert material
    logger.info(f'{material=}')
    ior = material.get_ior(wavelength=550)
    logger.info(f'{ior=}')

    materials = db.get_materials()
    logger.info(f'Number of materials: {len(materials)}')
    for material in materials:
        material.get_ior(wavelength=600)


def main() -> None:
    get_lenses()
    get_lens()
    get_coatings()
    get_materials()
    get_material()
    get_ior()


if __name__ == '__main__':
    init()
    main()
