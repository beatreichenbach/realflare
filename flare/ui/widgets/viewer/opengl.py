import os
from collections.abc import Sequence

import numpy as np
from OpenGL import GL
from OpenGL.constant import Constant


def create_texture(
    texture_filter: int | Constant = GL.GL_NEAREST,
    clamp_to_border: bool = True,
) -> int:
    """Return a new 2D texture with the given filtering and wrapping."""

    texture = GL.glGenTextures(1)

    target = GL.GL_TEXTURE_2D
    GL.glBindTexture(target, texture)
    GL.glTexParameteri(target, GL.GL_TEXTURE_MIN_FILTER, texture_filter)
    GL.glTexParameteri(target, GL.GL_TEXTURE_MAG_FILTER, texture_filter)
    if clamp_to_border:
        GL.glTexParameteri(target, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_BORDER)
        GL.glTexParameteri(target, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_BORDER)
        GL.glTexParameterfv(target, GL.GL_TEXTURE_BORDER_COLOR, np.zeros(4))
    GL.glBindTexture(target, 0)

    return texture


def create_program(shaders: Sequence[int] = ()) -> int:
    """
    Return a linked program and delete the compiled shaders.

    :raises RuntimeError: if the program fails to link.
    """

    program = GL.glCreateProgram()
    for shader in shaders:
        GL.glAttachShader(program, shader)

    GL.glLinkProgram(program)
    if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
        log = GL.glGetProgramInfoLog(program)
        raise RuntimeError(log.decode('utf-8', errors='replace'))

    for shader in shaders:
        GL.glDeleteShader(shader)

    return program


def update_texture(texture: int, array: np.ndarray) -> None:
    """Allocate the texture storage and upload an RGBA float array."""

    height, width = array.shape[:2]
    data = np.ascontiguousarray(array)

    target = GL.GL_TEXTURE_2D
    GL.glActiveTexture(GL.GL_TEXTURE0)
    GL.glBindTexture(target, texture)
    GL.glTexImage2D(
        target, 0, GL.GL_RGBA32F, width, height, 0, GL.GL_RGBA, GL.GL_FLOAT, data
    )
    GL.glBindTexture(target, 0)


def update_texture_subimage(texture: int, array: np.ndarray) -> None:
    """Upload an RGBA float array to a texture of the same size."""

    height, width = array.shape[:2]
    data = np.ascontiguousarray(array)

    target = GL.GL_TEXTURE_2D
    GL.glActiveTexture(GL.GL_TEXTURE0)
    GL.glBindTexture(target, texture)
    GL.glTexSubImage2D(target, 0, 0, 0, width, height, GL.GL_RGBA, GL.GL_FLOAT, data)
    GL.glBindTexture(target, 0)


def update_ubo(buffer: int, array: np.ndarray) -> None:
    """Upload the array to the uniform buffer."""

    data = np.ascontiguousarray(array)

    GL.glBindBuffer(GL.GL_UNIFORM_BUFFER, buffer)
    GL.glBufferData(GL.GL_UNIFORM_BUFFER, data.nbytes, data, GL.GL_DYNAMIC_DRAW)
    GL.glBindBuffer(GL.GL_UNIFORM_BUFFER, 0)


def delete(
    programs: Sequence[int] = (),
    textures: Sequence[int] = (),
    vertex_arrays: Sequence[int] = (),
    buffers: Sequence[int] = (),
) -> None:
    """Delete OpenGL resources from the current context."""

    for program in programs:
        GL.glDeleteProgram(program)

    GL.glDeleteTextures(len(textures), textures)
    GL.glDeleteVertexArrays(len(vertex_arrays), vertex_arrays)
    GL.glDeleteBuffers(len(buffers), buffers)


def load_source(filename: str) -> str:
    """Return the shader source loaded from the 'shaders' directory."""

    path = os.path.join(os.path.dirname(__file__), 'shaders', filename)
    with open(path) as file:
        source = file.read()
    return source


def load_shader(source: str, shader_type: int | Constant) -> int:
    """
    Return a compiled shader.

    :raises RuntimeError: if the shader fails to compile.
    """

    shader = GL.glCreateShader(shader_type)
    GL.glShaderSource(shader, source)
    GL.glCompileShader(shader)

    if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
        log = GL.glGetShaderInfoLog(shader)
        raise RuntimeError(log.decode('utf-8', errors='replace'))
    return shader
