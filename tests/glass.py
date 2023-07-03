import os

from realflare.api.data import Glass
from realflare.api.glass import manufacturers, glasses_from_path, closest_glass


def test_manufacturers():
    assert list(manufacturers().keys()) == ['schott']


def test_glasses_from_path():
    path = os.path.join(
        os.path.dirname(__file__), '..', 'realflare', 'resources', 'glass', 'schott'
    )
    glasses = glasses_from_path(path)
    glass = Glass(
        name='BAFN6',
        manufacturer='schott',
        n=1.589,
        v=48.45,
        coefficients=[
            1.36719201,
            0.00882820704,
            0.10907994,
            0.0438731646,
            1.02108011,
            113.58602,
        ],
    )
    assert glasses[0] == glass


def test_closest_glass():
    path = os.path.join(
        os.path.dirname(__file__), '..', 'realflare', 'resources', 'glass', 'schott'
    )
    glasses = tuple(glasses_from_path(path))
    closest = closest_glass(glasses, n=1.5, v=80, v_offset=0)
    glass = Glass(
        name='N-PK52A',
        manufacturer='schott',
        n=1.497,
        v=81.61,
        coefficients=[
            1.029607,
            0.00516800155,
            0.1880506,
            0.0166658798,
            0.736488165,
            138.964129,
        ],
    )
    assert closest == glass
