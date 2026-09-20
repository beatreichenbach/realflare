import logging
from functools import lru_cache

import numpy as np
from OpenGL import GL
from qtpy import QtCore, QtGui

from flare import api
from flare.api import color

from ..base import Array
from ..opengl import OpenGLTask
from .common import LAMBDA_MAX, LAMBDA_MID, LAMBDA_MIN, get_screen_scale
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
        ('fft_width', np.float32),
        ('samples', np.uint32),
        ('_pad', np.uint32),
    ]
)


class StarburstTask(OpenGLTask):
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
    ) -> Array:
        """
        Return a starburst image by rendering the fraunhofer diffraction of an aperture.
        """

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
        fft_width = get_fft_width(sensor_size, fstop, aperture_resolution, resolution)

        params = np.zeros((), dtype=params_dtype)
        params['resolution'] = (resolution.width(), resolution.height())
        params['position'] = (position[0], position[1])
        params['blur'] = blur
        params['rotation'] = rotation
        params['rotation_weight'] = config.diffraction.rotation_weight
        params['intensity'] = config.diffraction.intensity
        params['vignetting'] = config.diffraction.vignetting
        params['fft_width'] = fft_width
        params['samples'] = config.render.samples
        self.update_ubo(self._ubo, params)

        # FFT Image
        fft = get_fft(aperture)
        cached_update_texture(self._fft_image, fft)

        # Spectral Image
        wavelength_count = LAMBDA_MAX - LAMBDA_MIN + 1
        spectral = get_spectral(wavelength_count)
        cached_update_texture(self._spectral_image, spectral)

        # Render
        self.update_fbo_resolution(resolution)
        self.bind_vao(self._vao)
        self.render(self._program, self._fbo, resolution)

        array = self.read_texture(self._fbo_texture, resolution)
        args = (aperture, config, sensor_size, position, fstop)
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
    """Return a point spread function (PSD) for an aperture."""

    array = aperture.array[:, :, 0]
    intensity = get_fraunhofer_diffraction(array)
    fft = Array(intensity, args=(aperture,))

    return fft


@lru_cache(1)
def get_spectral(wavelength_count: int) -> Array:
    """Return an Image with the CMFS for the wavelengths."""

    lambdas = np.linspace(LAMBDA_MIN, LAMBDA_MAX, wavelength_count)
    cmfs_variation = 'CIE 2015 2 Degree Standard Observer'
    cmfs = color.get_cmfs(cmfs_variation, lambdas)

    # Add an alpha channel and turn into 2d texture with 1 px height.
    rgba = np.concatenate((cmfs, np.zeros((cmfs.shape[0], 1))), axis=-1)
    rgba = rgba[np.newaxis, ...]

    spectral = Array(rgba, args=(wavelength_count,))
    return spectral


@lru_cache(1)
def get_fft_width(
    sensor_size: tuple[float, float],
    fstop: float,
    aperture_resolution: int,
    resolution: QtCore.QSize,
) -> float:
    """
    Return the width in pixels of the fft on the image plane.

    Calculate FFT width:
    fft_width = x_max / pixel_width

    Where:
    aperture_size = focal_length / fstop
    f_max = 1 / (aperture_size / aperture_resolution)
    x_max = focal_length * wavelength * f_max
    pixel_width = sensor_size / resolution

    This simplifies to:
    fft_width = wavelength * fstop * aperture_resolution * resolution / sensor_size
    """

    # All units in mm
    wavelength = LAMBDA_MID * 1e-6
    sensor_width = sensor_size[0]
    fft_width = (
        wavelength * fstop * aperture_resolution * resolution.width() / sensor_width
    )

    return fft_width


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
