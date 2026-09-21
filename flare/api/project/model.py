import enum

from pydantic import BaseModel, Field
from qt_pydantic import QPoint, QPointF, QSize, QSizeF
from qtpy import QtCore


class HashableModel(BaseModel):
    def __hash__(self) -> int:
        return hash(self.model_dump_json())


class Layer(enum.Enum):
    COMP = 'composite'
    FLARE = 'flare'
    STARBURST = 'starburst'
    STARBURST_APERTURE = 'starburst_aperture'
    GHOST = 'ghost'
    GHOST_APERTURE = 'ghost_aperture'
    DIAGRAM = 'diagram'


class Supersampling(enum.Enum):
    NONE = 'none'
    SSAA_2X = 'ssaa_2x'


class Aperture(HashableModel):
    class Shape(HashableModel):
        size: QSizeF = QtCore.QSizeF(0.75, 0.75)
        blades: int = 6
        roundness: float = 0
        rotation: float = 0
        softness: float = 0

    class Grating(HashableModel):
        strength: float = 0
        density: float = 0.5
        length: float = 0.5
        width: float = 0.25
        softness: float = 0

    class Scratches(HashableModel):
        strength: float = 0
        density: float = 0.5
        length: float = 0.5
        width: float = 0.25
        rotation: float = 0
        rotation_variation: float = 0
        softness: float = 0
        parallax: QSizeF = QtCore.QSizeF(1, 1)

    class Dust(HashableModel):
        strength: float = 0
        density: float = 0.5
        radius: float = 0.5
        softness: float = 0
        parallax: QSizeF = QtCore.QSizeF(1, 1)

    class ApertureImage(HashableModel):
        strength: float = 0
        file: str = ''
        size: QSizeF = QtCore.QSizeF(0.75, 0.75)
        black: float = 0
        white: float = 1

    shape: Shape = Field(default_factory=Shape)
    grating: Grating = Field(default_factory=Grating)
    scratches: Scratches = Field(default_factory=Scratches)
    dust: Dust = Field(default_factory=Dust)
    image: ApertureImage = Field(default_factory=ApertureImage)


class Output(HashableModel):
    layer: Layer = Layer.COMP
    path: str = ''
    write: bool = False
    frame: int = 0


class Flare(HashableModel):
    class Light(HashableModel):
        intensity: float = 1
        illuminant: str = 'D65'
        position: QPointF = QtCore.QPointF(0, 0)

    class Lens(HashableModel):
        vendor: str = ''
        lens: str = ''
        glass: str = 'Schott'
        coatings: tuple[tuple[int, float], ...] = ()
        wavelength: QPoint = QtCore.QPoint(390, 730)
        ior: QPointF = QtCore.QPointF(1.38, 2.2)
        abbe_offset: float = 0

    class Camera(HashableModel):
        sensor_size: QSizeF = QtCore.QSizeF(36, 24)
        fstop: float = 22.0

    class Raytracing(HashableModel):
        wavelength_count: int = 1
        wavelength_sub_count: int = 1
        min_divisions: int = 4
        max_divisions: int = 64
        min_area: float = 0.01
        min_sliver: float = 0
        cull_percentage: float = 0.5
        use_aspheric: bool = True

    class Render(HashableModel):
        resolution: QSize = QtCore.QSize(1920, 1080)
        supersampling: Supersampling = Supersampling.NONE

    class Debug(HashableModel):
        ghost: int = 0
        ghost_enabled: bool = False
        wireframe: bool = False

    light: Light = Field(default_factory=Light)
    lens: Lens = Field(default_factory=Lens)
    camera: Camera = Field(default_factory=Camera)
    raytracing: Raytracing = Field(default_factory=Raytracing)
    render: Render = Field(default_factory=Render)
    debug: Debug = Field(default_factory=Debug)


class Ghost(HashableModel):
    class Diffraction(HashableModel):
        distance: float = 0.05
        vignette: float = 0.1

    class Render(HashableModel):
        resolution: int = 1024

    aperture: Aperture = Field(default_factory=Aperture)
    diffraction: Diffraction = Field(default_factory=Diffraction)
    render: Render = Field(default_factory=Render)


class Starburst(HashableModel):
    class Diffraction(HashableModel):
        intensity: float = 1
        blur: float = 0
        rotation: float = 0
        rotation_weight: float = 1
        vignetting: float = 1

    class Camera(HashableModel):
        scale_with_fstop: bool = False
        scale: float = 1
        occlusion: bool = True

    class Render(HashableModel):
        resolution: int = 1024
        samples: int = 7

    aperture: Aperture = Field(default_factory=Aperture)
    diffraction: Diffraction = Field(default_factory=Diffraction)
    camera: Camera = Field(default_factory=Camera)
    render: Render = Field(default_factory=Render)


class Diagram(HashableModel):
    class Raytracing(HashableModel):
        ghost: int = 0
        divisions: int = 8

    class Render(HashableModel):
        resolution: QSize = QtCore.QSize(2048, 1024)

    raytracing: Raytracing = Field(default_factory=Raytracing)
    render: Render = Field(default_factory=Render)


class Preprocess(HashableModel):
    divisions: int = 64


class Project(HashableModel):
    version: str = ''
    output: Output = Field(default_factory=Output)
    flare: Flare = Field(default_factory=Flare)
    ghost: Ghost = Field(default_factory=Ghost)
    starburst: Starburst = Field(default_factory=Starburst)
    diagram: Diagram = Field(default_factory=Diagram)
    preprocess: Preprocess = Field(default_factory=Preprocess)
