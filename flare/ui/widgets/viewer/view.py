import logging

import numpy as np
from OpenGL import GL
from qtpy import QtCore, QtGui, QtWidgets

from flare import ocio

from . import opengl
from .model import Channel

logger = logging.getLogger(__name__)


params_dtype = np.dtype(
    [
        ('image_size', np.float32, 2),
        ('resolution', np.float32, 2),
        ('offset', np.float32, 2),
        ('scale', np.float32),
        ('gain', np.float32),
        ('channel', np.uint32),
        ('border', np.uint32),
    ]
)


class OpenGLView(QtWidgets.QOpenGLWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._array: np.ndarray | None = None

        self._program: int | None = None
        self._vao: int | None = None
        self._ubo: int | None = None
        self._image: int | None = None

        self._channel: int = Channel.RGBA.value
        self._exposure: float = 0
        self._gain: float = 1
        self._offset: tuple[float, float] = (0, 0)
        self._scale: float = 1
        self._border: bool = True
        self._resolution: tuple[int, int] = (0, 0)
        self._image_size: tuple[int, int] = (0, 0)

        self._texture_dirty: bool = False
        self._ubo_dirty: bool = True

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.cleanup()
        super().closeEvent(event)

    def initializeGL(self) -> None:
        try:
            self._vao = GL.glGenVertexArrays(1)
            GL.glBindVertexArray(self._vao)
            self._ubo = self._create_ubo()
            self._program = self._create_program()

        except Exception as e:
            logger.exception(e)

    def paintGL(self) -> None:
        if self._program is None:
            return

        try:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.defaultFramebufferObject())
            GL.glClearColor(0.0, 0.0, 0.0, 1.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            GL.glUseProgram(self._program)
            if self._texture_dirty:
                self._update_texture()
            if self._ubo_dirty:
                self._update_ubo()
            if self._image is not None:
                GL.glActiveTexture(GL.GL_TEXTURE0)
                GL.glBindTexture(GL.GL_TEXTURE_2D, self._image)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        except Exception as e:
            logger.exception(e)

    def resizeGL(self, width: int, height: int) -> None:
        if self._program is None:
            return

        try:
            GL.glViewport(0, 0, width, height)
            self._resolution = (width, height)
            self._ubo_dirty = True
        except Exception as e:
            logger.exception(e)

    def array(self) -> np.ndarray | None:
        return self._array

    def set_array(self, array: np.ndarray) -> None:
        if array.ndim != 3:
            raise ValueError(f'expected 3 dimensions, got {array.ndim}')

        if array.shape[2] != 4:
            raise ValueError(f'expected 4 channels, got {array.shape[2]}')

        self._array = array
        self._texture_dirty = True
        self._request_update()

    def channel(self) -> Channel:
        return Channel(self._channel)

    def set_channel(self, channel: Channel) -> None:
        self._channel = channel.value
        self._request_update()

    def exposure(self) -> float:
        return self._exposure

    def set_exposure(self, exposure: float) -> None:
        self._exposure = exposure
        self._gain = pow(2, exposure)
        self._request_update()

    def offset(self) -> tuple[float, float]:
        return self._offset

    def set_offset(self, offset: QtCore.QPointF) -> None:
        self._offset = offset.toTuple()
        self._request_update()

    def scale(self) -> float:
        return self._scale

    def set_scale(self, scale: float) -> None:
        self._scale = scale
        self._request_update()

    def border(self) -> bool:
        return self._border

    def set_border(self, border: bool) -> None:
        self._border = border
        self._request_update()

    def color_at(self, position: QtCore.QPoint) -> QtGui.QColor:
        """
        Return the color at the position, or an invalid color if outside the array.
        """

        color = QtGui.QColor()
        if self._array is not None:
            height, width = self._array.shape[:2]
            x = position.x()
            y = position.y()
            if 0 <= x < width and 0 <= y < height:
                r, g, b, _ = self._array[y, x]
                color = QtGui.QColor.fromRgbF(r, g, b)
        return color

    def cleanup(self) -> None:
        """Clean up OpenGL resources."""

        context = self.context()
        if context is None or not context.isValid():
            return

        self.makeCurrent()
        try:
            programs = (self._program,) if self._program is not None else ()
            textures = (self._image,) if self._image is not None else ()
            vertex_arrays = (self._vao,) if self._vao is not None else ()
            buffers = (self._ubo,) if self._ubo is not None else ()
            opengl.delete(programs, textures, vertex_arrays, buffers)

            self._program = None
            self._image = None
            self._vao = None
            self._ubo = None
        finally:
            self.doneCurrent()

    def _update_texture(self) -> None:
        """Upload the array to the GPU texture, reusing the texture object."""

        if self._array is not None:
            height, width = self._array.shape[:2]
            if self._image is None:
                self._image = opengl.create_texture()
                opengl.update_texture(self._image, self._array)
            elif (width, height) == self._image_size:
                opengl.update_texture_subimage(self._image, self._array)
            else:
                opengl.update_texture(self._image, self._array)
            self._image_size = (width, height)

        self._texture_dirty = False

    def _update_ubo(self) -> None:
        """Update the uniform buffer with the view parameters."""

        if self._ubo is None:
            return

        params = np.zeros(1, dtype=params_dtype)
        params[0]['image_size'] = self._image_size
        params[0]['resolution'] = self._resolution
        params[0]['offset'] = self._offset
        params[0]['scale'] = self._scale
        params[0]['gain'] = self._gain
        params[0]['channel'] = self._channel
        params[0]['border'] = self._border

        opengl.update_ubo(self._ubo, params)
        self._ubo_dirty = False

    def _request_update(self) -> None:
        self._ubo_dirty = True
        super().update()

    @staticmethod
    def _create_ubo() -> int:
        """Return the uniform buffer bound to slot 0 for the view parameters."""

        buffer = GL.glGenBuffers(1)
        GL.glBindBufferBase(GL.GL_UNIFORM_BUFFER, 0, buffer)
        opengl.update_ubo(buffer, np.zeros(1, dtype=params_dtype))
        return buffer

    @staticmethod
    def _create_program() -> int:
        """Return the viewer program with the OCIO transform baked in."""

        vertex_source = opengl.load_source('viewer.vert')
        vertex_shader = opengl.load_shader(vertex_source, GL.GL_VERTEX_SHADER)

        definition = '#version 430 core'
        fragment = (
            definition,
            ocio.create_shader_source(),
            opengl.load_source('viewer.frag'),
        )
        fragment_source = '\n\n'.join(fragment)
        fragment_shader = opengl.load_shader(fragment_source, GL.GL_FRAGMENT_SHADER)

        program = opengl.create_program((vertex_shader, fragment_shader))

        return program
