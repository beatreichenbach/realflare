import enum
from dataclasses import field

from PySide2 import QtCore

from qt_extensions.typeutils import hashable_dataclass, deep_field
from realflare.api.tasks.opencl import Image


class RealflareError(ValueError):
    pass


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
    FLARE_STARBURST = enum.auto()
    DIAGRAM = enum.auto()


@hashable_dataclass
class RenderImage:
    image: Image
    element: RenderElement


@hashable_dataclass
class Glass:
    name: str
    manufacturer: str
    n: float
    v: float
    coefficients: list[float] = field(repr=False)


@hashable_dataclass
class LensModel:
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
    @hashable_dataclass
    class Shape:
        size: QtCore.QSizeF = deep_field(QtCore.QSizeF(0.75, 0.75))
        blades: int = 6
        roundness: float = 0
        rotation: float = 0
        softness: float = 0

    @hashable_dataclass
    class Grating:
        strength: float = 0
        density: float = 0.5
        length: float = 0.5
        width: float = 0.25
        softness: float = 0

    @hashable_dataclass
    class Scratches:
        strength: float = 0
        density: float = 0.5
        length: float = 0.5
        width: float = 0.25
        rotation: float = 0
        rotation_variation: float = 0
        softness: float = 0
        parallax: QtCore.QSizeF = deep_field(QtCore.QSizeF(0, 0))

    @hashable_dataclass
    class Dust:
        strength: float = 0
        density: float = 0.5
        radius: float = 0.5
        softness: float = 0
        parallax: QtCore.QSizeF = deep_field(QtCore.QSizeF(0, 0))

    @hashable_dataclass
    class ApertureImage:
        strength: float = 0
        file: str = ''
        size: QtCore.QSizeF = deep_field(QtCore.QSizeF(0.75, 0.75))
        threshold: float = 1

    shape: Shape = field(default_factory=Shape)
    grating: Grating = field(default_factory=Grating)
    scratches: Scratches = field(default_factory=Scratches)
    dust: Dust = field(default_factory=Dust)
    image: ApertureImage = field(default_factory=ApertureImage)


@hashable_dataclass
class Flare:
    @hashable_dataclass
    class Light:
        # light
        intensity: float = 1
        position: QtCore.QPointF = deep_field(QtCore.QPointF(0, 0))

        # image
        image_file_enabled: bool = False
        image_file: str = ''
        image_sample_resolution: int = 256
        image_samples: int = 8
        show_image: bool = False

    @hashable_dataclass
    class Lens:
        # lens
        sensor_size: QtCore.QSizeF = deep_field(QtCore.QSizeF(36, 24))
        fstop: float = 0
        lens_model_path: str = ''
        glasses_path: str = ''
        abbe_nr_adjustment: float = 0
        coating: tuple[int, ...] = field(default_factory=tuple)
        coating_range: QtCore.QPoint = deep_field(QtCore.QPoint(390, 730))
        coating_min_ior: float = 1.38
        min_area: float = 0.01

    @hashable_dataclass
    class Starburst:
        # technical
        intensity: float = 1
        scale: QtCore.QSizeF = deep_field(QtCore.QSizeF(1, 1))
        distance: float = 1
        blur: float = 0
        rotation: float = 0
        rotation_weight: float = 1

        # comp
        vignetting_enabled: bool = False
        vignetting: QtCore.QPointF = deep_field(QtCore.QPointF(0.75, 1))

    @hashable_dataclass
    class Ghost:
        fstop: float = 0

    light: Light = field(default_factory=Light)
    lens: Lens = field(default_factory=Lens)
    starburst_aperture: Aperture = field(default_factory=Aperture)
    starburst: Starburst = field(default_factory=Starburst)
    ghost_aperture: Aperture = field(default_factory=Aperture)
    ghost: Ghost = field(default_factory=Ghost)


@hashable_dataclass
class Output:
    element: RenderElement = RenderElement.FLARE
    path: str = ''
    colorspace: str = 'ACES - ACEScg'
    split_files: bool = True
    write: bool = False
    frame: int = 0


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
    debug_ghost_enabled: bool = False
    debug_ghost: int = 0

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
