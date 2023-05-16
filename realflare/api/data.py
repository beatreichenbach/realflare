import enum
from dataclasses import field

from PySide2 import QtGui, QtCore

from realflare.api.tasks.opencl import Image
from qt_extensions.typeutils import hashable_dataclass, deep_field


class AntiAliasing(enum.Enum):
    ONE = 1
    TWO = 2
    FOUR = 4
    EIGHT = 8

    @staticmethod
    def format(value: int) -> str:
        if value == AntiAliasing.ONE.name:
            return '1x'
        if value == AntiAliasing.TWO.name:
            return '2x'
        if value == AntiAliasing.FOUR.name:
            return '4x'
        if value == AntiAliasing.EIGHT.name:
            return '8x'


@enum.unique
class RenderElement(enum.Enum):
    STARBURST_APERTURE = enum.auto()
    STARBURST = enum.auto()
    GHOST_APERTURE = enum.auto()
    GHOST = enum.auto()
    FLARE = enum.auto()
    DIAGRAM = enum.auto()


@hashable_dataclass
class RenderImage:
    element: RenderElement
    image: Image


@hashable_dataclass
class Glass:
    name: str
    manufacturer: str
    n: float
    v: float
    coefficients: list[float] = field(repr=False)


@hashable_dataclass
class Prescription:
    @hashable_dataclass
    class LensElement:
        radius: float = 0
        distance: float = 0
        refractive_index: float = 1
        abbe_nr: float = 0
        height: float = 0

    # model
    name: str = 'New Model'
    year: int = 0
    patent_number: str = ''
    notes: str = ''

    # specs
    focal_length: int = 0
    fstop: float = 0
    aperture_index: int = 0
    lens_elements: list[LensElement] = field(default_factory=list)


@hashable_dataclass
class Aperture:
    fstop: float = 8
    file: str = ''
    blades: int = 64
    softness: float = 0


@hashable_dataclass
class Flare:
    @hashable_dataclass
    class Light:
        # light
        intensity: float = 1
        color: QtGui.QColor = deep_field(QtGui.QColor(1, 1, 1))
        position: QtCore.QPointF = deep_field(QtCore.QPointF(0, 0))

        # image
        image_file: str = ''
        image_sample_resolution: int = 256
        image_samples: int = 8

    @hashable_dataclass
    class Lens:
        # lens
        sensor_size: QtCore.QSize = deep_field(QtCore.QSize(36, 24))
        prescription_path: str = ''
        glasses_path: str = ''
        abbe_nr_adjustment: float = 0
        min_area: float = 0.01
        coating_lens_elements: list[tuple[int, float]] = field(default_factory=list)
        random_wavelength_range: QtCore.QPoint = deep_field(QtCore.QPoint(390, 700))
        random_refractive_index_range: QtCore.QPointF = deep_field(
            QtCore.QPointF(1.21, 1.38)
        )

    @hashable_dataclass
    class Starburst:
        # aperture
        aperture: Aperture = field(default_factory=Aperture)

        # technical
        intensity: float = 1
        lens_distance: float = 0.1
        blur: float = 0
        rotation: float = 0
        rotation_weighting: float = 1

        # comp
        fadeout: QtCore.QPointF = deep_field(QtCore.QPointF(0.75, 1))
        scale: QtCore.QSizeF = deep_field(QtCore.QSizeF(1, 1))

    @hashable_dataclass
    class Ghost:
        # aperture
        aperture: Aperture = field(default_factory=Aperture)

        # technical
        fstop: float = 8

    light: Light = field(default_factory=Light)
    lens: Lens = field(default_factory=Lens)
    starburst: Starburst = field(default_factory=Starburst)
    ghost: Ghost = field(default_factory=Ghost)


@hashable_dataclass
class Output:
    element: RenderElement = RenderElement.FLARE
    path: str = ''
    colorspace: str = 'ACES - ACEScg'
    write: bool = False


@hashable_dataclass
class Diagram:
    # renderer
    resolution: QtCore.QSize = deep_field(QtCore.QSize(2048, 1024))

    # rays
    debug_ghost: int = 0
    light_position: float = 0
    grid_count: int = 8
    grid_length: float = 50
    column_offset: int = 0


@hashable_dataclass
class Debug:
    show_image: bool = False
    disable_starburst: bool = False
    disable_ghosts: bool = False
    debug_ghosts: bool = False
    debug_ghost: int = 0


@hashable_dataclass
class Render:
    @hashable_dataclass
    class Starburst:
        resolution: QtCore.QSize = deep_field(QtCore.QSize(256, 256))
        samples: int = 100

    @hashable_dataclass
    class Ghost:
        resolution: QtCore.QSize = deep_field(QtCore.QSize(256, 256))

    # renderer
    resolution: QtCore.QSize = deep_field(QtCore.QSize(512, 512))
    bin_size: int = 64
    anti_aliasing: int = 1

    # rays
    wavelength_count: int = 1
    wavelength_sub_count: int = 1
    grid_count: int = 33
    grid_length: float = 50
    cull_percentage: float = 0

    # starburst
    starburst: Starburst = field(default_factory=Starburst)

    # ghost
    ghost: Ghost = field(default_factory=Ghost)

    # system
    device: str = ''


@hashable_dataclass
class Project:
    output: Output = field(default_factory=Output)
    flare: Flare = field(default_factory=Flare)
    render: Render = field(default_factory=Render)
    diagram: Diagram = field(default_factory=Diagram)
    debug: Debug = field(default_factory=Debug)
