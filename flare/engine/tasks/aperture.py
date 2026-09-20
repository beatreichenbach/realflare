import logging
import os
from functools import lru_cache

import imageio.v3 as iio
import numpy as np
from OpenGL import GL
from qtpy import QtCore, QtGui

from flare import api
from ..base import Array, EngineError

from ..opengl import OpenGLTask
from .constants import TEX, UBO

logger = logging.getLogger(__name__)

params_dtype = np.dtype(
    [
        # Shape
        ('resolution', np.float32, 2),
        ('shape_size', np.float32, 2),
        ('shape_blades', np.uint32),
        ('shape_roundness', np.float32),
        ('shape_rotation', np.float32),
        ('shape_softness', np.float32),
        # Grating
        ('grating_strength', np.float32),
        ('grating_density', np.float32),
        ('grating_length', np.float32),
        ('grating_width', np.float32),
        ('grating_softness', np.float32),
        # Scratches
        ('scratches_strength', np.float32),
        ('scratches_density', np.float32),
        ('scratches_length', np.float32),
        ('scratches_width', np.float32),
        ('scratches_rotation', np.float32),
        ('scratches_rotation_variation', np.float32),
        ('scratches_softness', np.float32),
        ('scratches_parallax', np.float32, 2),
        # Dust
        ('dust_strength', np.float32),
        ('dust_density', np.float32),
        ('dust_radius', np.float32),
        ('dust_softness', np.float32),
        ('dust_parallax', np.float32, 2),
        # Image
        ('image_size', np.float32, 2),
        ('image_strength', np.float32),
        ('image_black', np.float32),
        ('image_white', np.float32),
        ('_pad', np.float32, 3),
    ]
)


class ApertureTask(OpenGLTask):
    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        super().__init__(context)

        vertex_source = self.load_source('screen.vert')
        vertex_shader = self.load_shader(vertex_source, GL.GL_VERTEX_SHADER)
        sources = ('geometry.glsl', 'noise.glsl', 'aperture.frag')
        fragment_source = self.load_sources(*sources)
        fragment_shader = self.load_shader(fragment_source, GL.GL_FRAGMENT_SHADER)

        self._program = self.create_program(shaders=(vertex_shader, fragment_shader))
        self._fbo_texture = self.create_texture(clamp_to_border=True)
        self._fbo = self.create_fbo(self._fbo_texture)
        self._vao = self.create_vao()
        self._ubo = self.create_buffer()
        self._image = self.create_texture(clamp_to_border=True)

        self.bind_ubo(self._ubo, UBO.APERTURE)
        self.bind_texture(self._image, TEX.APERTURE_IMAGE)

        self.bind_ubo_block(self._program, 'Params', UBO.APERTURE)
        self.bind_texture_loc(self._program, 'image_texture', TEX.APERTURE_IMAGE)

        logger.debug(f'Initialized {self.__class__.__name__}')

    def cleanup(self) -> None:
        self.delete(
            programs=(self._program,),
            textures=(self._fbo_texture, self._image),
            render_buffers=(self._fbo,),
            vertex_arrays=(self._vao,),
            buffers=(self._ubo,),
        )
        self.update_fbo_resolution.cache_clear()
        self.run.cache_clear()

    @lru_cache(1)  # noqa: B019
    def update_fbo_resolution(self, resolution: QtCore.QSize) -> None:
        """Update the fbo with a new resolution."""

        self._fbo_texture = self.create_texture(
            clamp_to_border=True, resolution=resolution.toTuple()
        )
        self.update_fbo(self._fbo, self._fbo_texture)

    @lru_cache(1)  # noqa: B019
    def run(
        self,
        aperture: api.Aperture,
        resolution: int,
        scratches_parallax: tuple[float, float] = (0, 0),
        dust_parallax: tuple[float, float] = (0, 0),
    ) -> Array:
        # Params
        params = np.zeros((), dtype=params_dtype)
        # Shape
        size = (aperture.shape.size.width(), aperture.shape.size.height())
        params['resolution'] = (resolution, resolution)
        params['shape_size'] = size
        params['shape_blades'] = aperture.shape.blades
        params['shape_roundness'] = aperture.shape.roundness
        params['shape_rotation'] = np.radians(aperture.shape.rotation)
        params['shape_softness'] = aperture.shape.softness / 10
        # Grating
        params['grating_strength'] = aperture.grating.strength
        params['grating_density'] = aperture.grating.density
        params['grating_length'] = aperture.grating.length
        params['grating_width'] = aperture.grating.width * 0.1
        params['grating_softness'] = aperture.grating.softness / 10
        # Scratches
        params['scratches_strength'] = aperture.scratches.strength
        params['scratches_density'] = aperture.scratches.density
        params['scratches_length'] = aperture.scratches.length
        params['scratches_width'] = aperture.scratches.width * 0.1
        params['scratches_rotation'] = np.radians(aperture.scratches.rotation)
        params['scratches_rotation_variation'] = aperture.scratches.rotation_variation
        params['scratches_softness'] = aperture.scratches.softness / 10
        params['scratches_parallax'] = scratches_parallax
        # Dust
        params['dust_strength'] = aperture.dust.strength
        params['dust_density'] = aperture.dust.density
        params['dust_radius'] = aperture.dust.radius * 0.1
        params['dust_softness'] = aperture.dust.softness / 10
        params['dust_parallax'] = dust_parallax
        # Image
        image_size = (aperture.image.size.width(), aperture.image.size.height())
        params['image_size'] = image_size
        params['image_strength'] = aperture.image.strength
        params['image_black'] = aperture.image.black
        params['image_white'] = aperture.image.white

        self.update_ubo(self._ubo, params)

        # Image
        file = api.File(aperture.image.file)
        update_image(self._image, file)

        # Render
        render_resolution = QtCore.QSize(resolution, resolution)
        self.update_fbo_resolution(render_resolution)
        self.bind_vao(self._vao)
        self.render(self._program, self._fbo, render_resolution)

        array = self.read_texture(self._fbo_texture, render_resolution)
        args = (aperture, resolution, scratches_parallax, dust_parallax)
        image = Array(array=array, args=args)

        return image


def load_image(filename: str) -> np.ndarray:
    """
    Return a numpy array from a filename. Convert the image to np.float32 RGB.

    :raises EngineError: If the file cannot be loaded.
    """

    image = iio.imread(filename)

    # Convert to RGB
    if image.ndim == 3:
        pass
    elif image.ndim == 2:
        # Convert grayscale
        image = np.stack((image, image, image), axis=-1)
    else:
        raise EngineError(
            f'expected 2 or 3 dimensions, got {image.ndim}',
            log=f'Could not load image with {image.ndim} dimensions: {filename}',
        )

    # Convert to RGB
    channels = image.shape[-1]
    if channels == 3:
        pass
    elif channels == 4:
        # Discard alpha
        image = image[..., :3]
    else:
        raise EngineError(
            f'expected 3 or 4 dimensions, got {channels}',
            log=f'Could not load image with {channels} channels: {filename}',
        )

    # Convert to float
    if image.dtype == np.float32:
        pass
    elif image.dtype == np.float64:
        image = image.astype(np.float32)
    else:
        image = image.astype(np.float32) / 255

    return image


@lru_cache(1)
def update_image(texture: int, file: api.File) -> None:
    """
    Load a file used as the texture and return an OpenGL texture.

    :raises EngineError: If the file cannot be found or cannot be loaded.
    """

    filename = str(file)
    if not filename:
        return

    if not os.path.exists(filename):
        raise EngineError(
            f'file does not exist: {filename}',
            log=f'The file does not exist: {filename}',
        )

    array = load_image(filename)
    array = np.flipud(array)

    ApertureTask.update_texture(texture, array)

    logger.debug(f'Updated image: {filename}')
