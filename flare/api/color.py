import numpy as np

from . import data


def xy_to_xyy(xy: np.ndarray, y: float = 1) -> np.ndarray:
    xyy = np.hstack((xy, y))
    return xyy


def xyy_to_xyz(xyy: np.ndarray) -> np.ndarray:
    xyz = np.array(
        (
            xyy[0] * xyy[2] / xyy[1],
            xyy[2],
            (1 - xyy[0] - xyy[1]) * xyy[2] / xyy[1],
        )
    )
    return xyz


def xyz_to_xyy(xyz: np.ndarray) -> np.ndarray:
    xyy = np.array(
        (
            xyz[0] / np.sum(xyz),
            xyz[1] / np.sum(xyz),
            xyz[1],
        )
    )
    return xyy


def xyy_to_xy(xyy: np.ndarray) -> np.ndarray:
    return xyy[:2]


def xyz_to_xy(xyz: np.ndarray) -> np.ndarray:
    return xyy_to_xy(xyz_to_xyy(xyz))


def xyz_to_lab(xyz: np.ndarray, whitepoint: np.ndarray) -> np.ndarray:
    x = xyz[0]
    y = xyz[1]
    z = xyz[2]

    xn = whitepoint[0]
    yn = whitepoint[1]
    zn = whitepoint[2]

    def f(t: float) -> float:
        delta = 6 / 29
        if t > delta * delta * delta:
            return np.cbrt(t)
        else:
            return t / (delta * delta * 3) + (4 / 29)

    fx = f(x / xn)
    fy = f(y / yn)
    fz = f(z / zn)

    l = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)
    lab = np.array((l, a, b))
    return lab


def get_cmfs(variation: str, lambdas: np.ndarray) -> np.ndarray:
    cmfs_data = data.CMFS[variation]
    cmfs_keys = np.array(list(cmfs_data.keys()))
    cmfs_values = np.array(list(cmfs_data.values()))
    cmfs = np.column_stack(
        [np.interp(lambdas, cmfs_keys, cmfs_values[:, i]) for i in range(3)]
    )
    return cmfs


def get_illuminant(standard_illuminant: str, lambdas: np.ndarray) -> np.ndarray:
    illuminant_data = data.ILLUMINANTS_CIE[standard_illuminant]
    illuminant_keys = np.array(list(illuminant_data.keys()))
    illuminant_values = np.array(list(illuminant_data.values()))
    illuminant = np.interp(lambdas, illuminant_keys, illuminant_values)
    return illuminant


def get_illuminants() -> tuple[str, ...]:
    return tuple(data.ILLUMINANTS_CIE.keys())


def get_whitepoint(standard_illuminant: str) -> np.ndarray:
    coordinated = np.array(data.COORDS[standard_illuminant])
    whitepoint = xyy_to_xyz(xy_to_xyy(coordinated))
    return whitepoint
