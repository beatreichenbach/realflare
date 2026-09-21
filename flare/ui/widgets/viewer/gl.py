import logging
import os
from typing import Any

import numpy as np
import PyOpenColorIO as OCIO
from OpenGL import GL
from qtpy import QtCore, QtGui, QtWidgets

from .data import Channel

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

        self._array = None

        self._program = None
        self._vao = None
        self._ubo = None
        self._image = None

        self._channel = Channel.RGBA.value
        self._exposure = 0
        self._gain = 1
        self._offset = (0, 0)
        self._scale = 1
        self._border = True
        self._resolution = (0, 0)
        self._image_size = (0, 0)

        self._update_requested = True

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.cleanup()
        super().closeEvent(event)

    def array(self) -> np.ndarray | None:
        return self._array

    def set_array(self, array: np.ndarray) -> None:
        if array.ndim != 3:
            raise ValueError(f'expected 3 dimensions, got {array.ndim}')

        if array.shape[2] != 4:
            raise ValueError(f'expected 4 channels, got {array.shape[2]}')

        self._array = array

        self.makeCurrent()
        if self._image is not None:
            GL.glDeleteTextures([self._image])
        self._image = create_texture(array)

        height, width = self._array.shape[:2]
        self._image_size = (width, height)
        self.update()

    def channel(self) -> Channel:
        return Channel(self._channel)

    def set_channel(self, channel: Channel) -> None:
        self._channel = channel.value
        self.update()

    def exposure(self) -> float:
        return self._exposure

    def set_exposure(self, exposure: float) -> None:
        self._exposure = exposure
        self._gain = pow(2, exposure)
        self.update()

    def offset(self) -> tuple[float, float]:
        return self._offset

    def set_offset(self, offset: QtCore.QPointF) -> None:
        self._offset = offset.toTuple()
        self.update()

    def scale(self) -> float:
        return self._scale

    def set_scale(self, scale: float) -> None:
        self._scale = scale
        self.update()

    def border(self) -> bool:
        return self._border

    def set_border(self, border: bool) -> None:
        self._border = border
        self.update()

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
                r, g, b, a = self._array[y, x]
                color = QtGui.QColor.fromRgbF(r, g, b)
        return color

    def initializeGL(self) -> None:
        try:
            self._vao = GL.glGenVertexArrays(1)
            GL.glBindVertexArray(self._vao)
            self._ubo = create_ubo(slot=0, size=params_dtype.itemsize)
            self._program = create_program()

        except Exception as e:
            logger.exception(e)

    def paintGL(self) -> None:
        try:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.defaultFramebufferObject())
            GL.glClearColor(0.0, 0.0, 0.0, 1.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            GL.glUseProgram(self._program)
            if self._update_requested:
                self._update()
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        except Exception as e:
            logger.exception(e)

    def resizeGL(self, width: int, height: int) -> None:
        if self._program is None:
            return
        try:
            GL.glViewport(0, 0, width, height)
            self._resolution = (width, height)
            self._update_requested = True
            if self._image is not None:
                GL.glBindTexture(GL.GL_TEXTURE_2D, self._image)
        except Exception as e:
            logger.exception(e)

    def update(self) -> None:
        self._update_requested = True
        super().update()

    def _update(self) -> None:
        """Update the UBO."""

        params = np.zeros(1, dtype=params_dtype)
        params[0]['image_size'] = self._image_size
        params[0]['resolution'] = self._resolution
        params[0]['offset'] = self._offset
        params[0]['scale'] = self._scale
        params[0]['gain'] = self._gain
        params[0]['channel'] = self._channel
        params[0]['border'] = self._border

        GL.glBindBuffer(GL.GL_UNIFORM_BUFFER, self._ubo)
        GL.glBufferData(GL.GL_UNIFORM_BUFFER, params.nbytes, params, GL.GL_DYNAMIC_DRAW)
        self._update_requested = False

    def cleanup(self) -> None:
        """Clean up OpenGL resources."""

        if self._program is not None:
            GL.glDeleteProgram(self._program)
            self._program = None

        if self._image is not None:
            GL.glDeleteTextures([self._image])
            self._image = None

        if self._vao is not None:
            GL.glDeleteVertexArrays([self._vao])
            self._vao = None

        if self._ubo is not None:
            GL.glDeleteBuffers([self._ubo])
            self._ubo = None


def create_program() -> int:
    vertex_source = load_source('viewer.vert')
    vertex_shader = load_shader(vertex_source, GL.GL_VERTEX_SHADER)

    definition = '#version 430 core'
    ocio_source = create_ocio_source()
    fragment_source = load_source('viewer.frag')
    source = '\n\n'.join((definition, ocio_source, fragment_source))
    fragment_shader = load_shader(source, GL.GL_FRAGMENT_SHADER)

    logger.debug('Create program')
    program = GL.glCreateProgram()
    GL.glAttachShader(program, vertex_shader)
    GL.glAttachShader(program, fragment_shader)
    GL.glLinkProgram(program)

    GL.glDeleteShader(vertex_shader)
    GL.glDeleteShader(fragment_shader)

    logger.debug('Program created')

    if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
        raise RuntimeError(GL.glGetProgramInfoLog(program).decode())

    return program


def create_texture(array: np.ndarray) -> int:
    h, w = array.shape[:2]
    image = GL.glGenTextures(1)
    GL.glActiveTexture(GL.GL_TEXTURE0)
    GL.glBindTexture(GL.GL_TEXTURE_2D, image)
    GL.glTexImage2D(
        GL.GL_TEXTURE_2D, 0, GL.GL_RGBA32F, w, h, 0, GL.GL_RGBA, GL.GL_FLOAT, array
    )

    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_BORDER)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_BORDER)
    GL.glTexParameterfv(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_BORDER_COLOR, np.zeros(4))

    return image


# TODO: implement ocio properly
def create_ocio_source() -> str:
    ocio = os.path.join(
        os.path.dirname(__file__),
        'ocio',
        'fn-nuke_cg-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio',
    )
    os.environ['OCIO'] = ocio

    config = OCIO.GetCurrentConfig()  # ty: ignore[unresolved-attribute]

    display = config.getDefaultDisplay()
    view = config.getDefaultView(display)

    transform = OCIO.DisplayViewTransform()  # ty: ignore[unresolved-attribute]
    transform.setSrc(OCIO.ROLE_SCENE_LINEAR)  # ty: ignore[unresolved-attribute]
    transform.setDisplay(display)
    transform.setView(view)

    processor = config.getProcessor(transform)
    gpu = processor.getDefaultGPUProcessor()

    shader_desc = OCIO.GpuShaderDesc.CreateShaderDesc(OCIO.GPU_LANGUAGE_GLSL_4_0)  # ty: ignore[unresolved-attribute]
    gpu.extractGpuShaderInfo(shader_desc)
    source = shader_desc.getShaderText()

    return source


def create_ubo(slot: int, size: int = 0) -> int:
    buffer = GL.glGenBuffers(1)
    GL.glBindBuffer(GL.GL_UNIFORM_BUFFER, buffer)
    GL.glBindBufferBase(GL.GL_UNIFORM_BUFFER, slot, buffer)
    if size:
        GL.glBufferData(GL.GL_UNIFORM_BUFFER, size, None, GL.GL_DYNAMIC_DRAW)
    return buffer


def load_source(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), 'shaders', filename)
    with open(path) as file:
        source = file.read()
    return source


def load_shader(source: str, shader_type: Any) -> int:
    shader = GL.glCreateShader(shader_type)
    GL.glShaderSource(shader, source)
    GL.glCompileShader(shader)

    if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
        raise RuntimeError(GL.glGetShaderInfoLog(shader).decode())
    return shader
