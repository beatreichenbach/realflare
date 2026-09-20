import logging
from functools import lru_cache

import numpy as np
from OpenGL import GL
from qtpy import QtCore, QtGui

from flare import api

from ..base import Array
from ..opengl import OpenGLTask
from .common import LAMBDA_MAX, LAMBDA_MID, LAMBDA_MIN, get_screen_scale, get_spectral
from .constants import TEX, UBO

logger = logging.getLogger(__name__)


params_dtype = np.dtype(
    [
        ('resolution', np.float32, 2),
        ('position', np.float32, 2),
        ('blur', np.float32),
        ('rotation', np.float32),
        ('rotation_weight', np.float32),
        ('intensity', np.float32),
        ('vignetting', np.float32),
        ('fft_radius', np.float32),
        ('samples', np.uint32),
        ('_pad', np.uint32),
    ]
)


class StarburstTask(OpenGLTask):
    """
    This task creates the starburst around a bright source using the Fraunhofer
    approximation.

    The pupil truncates the incoming wavefront, so each open point of the aperture
    acts as a secondary source. In the far field their interference is the Fourier
    transform of the aperture image, and the visible glare is its power spectrum.
    Blade edges become spikes, while scratches, dust, and grating add streaks and
    halos.

    Steps:
    1. Fourier transform the aperture image and take the power spectrum, assuming
       uniform collimated incident light and a real-valued transmission function
       (Hecht 2001). Fraunhofer is used instead of Fresnel because the sensor sits
       at the focal plane, where the Fresnel phase reduces to a Fourier transform.
    2. Scale the pattern to the sensor: its radius is normalized to the sensor
       radius, so it grows with wavelength and f-number.
    3. Sample wavelengths from 390 to 730 nm. Each lookup is re-scaled by its own
       wavelength, so short wavelengths sit closer to the source and the spikes fan
       out into chromatic fringes. Samples are weighted by the illuminant spectrum
       times the CIE 2015 2-degree observer curves, converted to render space, and
       dimmed by (LAMDA_MID / wavelength)^2 so every wavelength carries equal energy
       despite spreading over different areas (Kakimoto et al. 2005, Eq. 2).
    4. Apply artistic controls:
       - Blur and rotation jitter the per-wavelength lookups, approximating relative
         motion between aperture and sensor during exposure.
       - Vignetting fades the FFT texture borders to hide edge artifacts.

    References:
    Kakimoto et al. 2005, Sec. 3.1 and 3.2, Eq. 5.
    Ritschel et al. 2009, Sec. 4 and 5.
    Hullin et al. 2011.
    Hecht 2001.
    https://github.com/TomCrypto/fraunhofer
    """

    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        super().__init__(context)

        vertex_source = self.load_source('screen.vert')
        vertex_shader = self.load_shader(vertex_source, GL.GL_VERTEX_SHADER)
        sources = ('geometry.glsl', 'noise.glsl', 'starburst.frag')
        fragment_source = self.load_sources(*sources)
        fragment_shader = self.load_shader(fragment_source, GL.GL_FRAGMENT_SHADER)

        self._program = self.create_program(shaders=(vertex_shader, fragment_shader))
        self._fbo_texture = self.create_texture(clamp_to_border=True)
        self._fbo = self.create_fbo(self._fbo_texture)
        self._vao = self.create_vao()
        self._ubo = self.create_buffer()
        self._fft_image = self.create_texture(clamp_to_border=True)
        self._spectral_image = self.create_texture()

        self.bind_ubo(self._ubo, UBO.STARBURST)
        self.bind_texture(self._fft_image, TEX.STARBURST_FFT)
        self.bind_texture(self._spectral_image, TEX.STARBURST_SPECTRAL)

        self.bind_ubo_block(self._program, 'Params', UBO.STARBURST)
        self.bind_texture_loc(self._program, 'fft_image', TEX.STARBURST_FFT)
        self.bind_texture_loc(self._program, 'spectral_image', TEX.STARBURST_SPECTRAL)

    def cleanup(self) -> None:
        self.delete(
            programs=(self._program,),
            textures=(self._fbo_texture, self._fft_image, self._spectral_image),
            render_buffers=(self._fbo,),
            vertex_arrays=(self._vao,),
            buffers=(self._ubo,),
        )
        self.update_fbo_resolution.cache_clear()
        self.run.cache_clear()

    @lru_cache(1)  # noqa: B019
    def update_fbo_resolution(self, resolution: QtCore.QSize) -> None:
        self._fbo_texture = self.create_texture(
            clamp_to_border=True, resolution=resolution.toTuple()
        )
        self.update_fbo(self._fbo, self._fbo_texture)

    @lru_cache(1)  # noqa: B019
    def run(
        self,
        aperture: Array,
        config: api.Starburst,
        sensor_size: tuple[float, float],
        position: tuple[float, float],
        fstop: float,
        resolution: QtCore.QSize,
        illuminant: str,
    ) -> Array:
        """Return the starburst around a bright source."""

        # Check if the light reaches the aperture
        # if config.camera.occlusion:
        #     occluded = get_occlusion(resolution, sensor_size, position)
        #     if occluded:
        #         array = np.zeros((resolution.height(), resolution.width(), 4))
        #         image = Array(array=array, args=args)
        #         return image

        # Parameters
        blur = config.diffraction.blur / 100
        rotation = np.radians(config.diffraction.rotation)
        aperture_resolution = aperture.array.shape[0]
        fft_radius = get_fft_radius(sensor_size, fstop, aperture_resolution, resolution)

        params = np.zeros((), dtype=params_dtype)
        params['resolution'] = (resolution.width(), resolution.height())
        params['position'] = (position[0], position[1])
        params['blur'] = blur
        params['rotation'] = rotation
        params['rotation_weight'] = config.diffraction.rotation_weight
        params['intensity'] = config.diffraction.intensity
        params['vignetting'] = config.diffraction.vignetting
        params['fft_radius'] = fft_radius
        params['samples'] = config.render.samples
        self.update_ubo(self._ubo, params)

        # FFT Image
        fft = get_fft(aperture)
        cached_update_texture(self._fft_image, fft)

        # Spectral Image
        wavelength_count = LAMBDA_MAX - LAMBDA_MIN + 1
        spectral = get_spectral(illuminant, wavelength_count)
        cached_update_texture(self._spectral_image, spectral)

        # Render
        self.update_fbo_resolution(resolution)
        self.bind_vao(self._vao)
        self.render(self._program, self._fbo, resolution)

        array = self.read_texture(self._fbo_texture, resolution)
        args = (aperture, config, sensor_size, position, fstop, illuminant)
        image = Array(array=array, args=args)
        return image


@lru_cache(1)
def cached_update_texture(texture: int, array: Array) -> None:
    OpenGLTask.update_texture(texture, array.array)


def get_fraunhofer_diffraction(aperture: np.ndarray) -> np.ndarray:
    """Return the far-field diffraction pattern using the Fraunhofer approximation."""

    h, w = aperture.shape
    dimension = int(min(h, w))
    fft = np.fft.fftshift(np.fft.fft2(aperture))
    intensity = np.abs(fft) ** 2
    intensity /= dimension**2
    intensity = intensity.astype(np.float32)
    return intensity


@lru_cache(1)
def get_fft(aperture: Array) -> Array:
    """Return a point spread function (PSF) for an aperture."""

    array = aperture.array[:, :, 0]
    intensity = get_fraunhofer_diffraction(array)
    fft = Array(intensity, args=(aperture,))

    return fft


@lru_cache(1)
def get_fft_radius(
    sensor_size: tuple[float, float],
    fstop: float,
    aperture_resolution: int,
    resolution: QtCore.QSize,
) -> float:
    """
    Return the radius relative to the sensor.

    The physical pattern radius grows with wavelength and f-number:
    pattern_radius = wavelength * fstop * aperture_resolution / 2.
    The image is fit into the sensor with letterboxing or pillarboxing.
    """

    # All units in mm
    wavelength = LAMBDA_MID * 1e-6
    sensor_aspect = sensor_size[0] / sensor_size[1]
    resolution_aspect = resolution.width() / resolution.height()
    if resolution_aspect > sensor_aspect:
        # Fit to width
        effective_size = (sensor_size[0], sensor_size[0] / resolution_aspect)
    else:
        # Fit to height
        effective_size = (sensor_size[1] * resolution_aspect, sensor_size[1])
    sensor_radius = np.hypot(*effective_size) / 2
    pattern_radius = wavelength * fstop * aperture_resolution / 2
    fft_radius = pattern_radius / sensor_radius

    return fft_radius


@lru_cache(1)
def get_occlusion(
    resolution: QtCore.QSize,
    sensor_size: tuple[float, float],
    position: tuple[float, float],
) -> bool:
    """
    Return whether the light source is occluded by the lens housing.
    This assumes that the diameter of the sensor is the diameter of the image pupil.
    """

    screen_scale = get_screen_scale(sensor_size, resolution)

    # Get sensor radius in pixels
    sensor_width = resolution.width()
    sensor_height = sensor_width / sensor_size[0] * sensor_size[1]
    sensor_radius = np.hypot(sensor_width, sensor_height) / 2

    # Get the radius of the light
    light_radius = np.hypot(
        position[0] * resolution.width() / 2,
        position[1] * resolution.height() / 2,
    )

    occluded = light_radius > sensor_radius

    return occluded
