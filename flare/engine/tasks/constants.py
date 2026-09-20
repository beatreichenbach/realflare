from enum import IntEnum, auto


class UBO(IntEnum):
    """UBO Slot ids that are defined and used across tasks."""

    APERTURE = auto()
    STARBURST = auto()
    RAYTRACING = auto()
    PRIM = auto()
    FLARE = auto()
    DIAGRAM_LENS = auto()
    DIAGRAM_RAYS = auto()
    PREPROCESS = auto()


class SSBO(IntEnum):
    """SSBO Slot ids that are defined and used across tasks."""

    SURFACES = auto()
    IORS = auto()
    WAVELENGTHS = auto()
    GHOSTS = auto()
    RAYS = auto()
    INTERSECTIONS = auto()
    INTENSITIES = auto()
    INDICES = auto()
    COUNTS = auto()
    MESH = auto()
    NEIGHBORS = auto()
    AREAS = auto()
    COMMANDS = auto()
    FLARE_GHOSTS = auto()
    FLARE_VBO = auto()
    FLARE_EBO = auto()
    DIAGRAM_INTERSECTIONS = auto()
    DIAGRAM_RAY_IDS = auto()
    PRE_MESH = auto()
    PRE_AREAS = auto()
    PRE_INTENSITIES = auto()


class TEX(IntEnum):
    """Texture Units that are defined and used across tasks."""

    ACTIVE = auto()
    APERTURE_IMAGE = auto()
    STARBURST_FFT = auto()
    STARBURST_SPECTRAL = auto()
    FLARE_GHOST = auto()
    FLARE_SPECTRAL = auto()
