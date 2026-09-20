import contextlib
import inspect
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeVar

import numpy as np
from OpenGL import GL
from OpenGL.constant import Constant
from qtpy import QtCore, QtGui

from .base import Task

T = TypeVar('T', bound='OpenGLTask')


class ResourceManager:
    @classmethod
    def load_source(cls, filename: str) -> str:
        """Return the shader source loaded relative to the subclass location."""

        # Try shaders relative to the subclass file location.
        try:
            cls_file = inspect.getfile(cls)
            candidate = Path(cls_file).parent / 'shaders' / filename
            if candidate.is_file():
                path = candidate
            else:
                # Fallback: when called on ResourceManager/OpenGLTask defined in engine/
                # shaders live in engine/tasks/shaders
                fallback = Path(__file__).parent / 'tasks' / 'shaders' / filename
                path = fallback if fallback.is_file() else candidate
        except (TypeError, OSError):
            path = Path(__file__).parent / 'tasks' / 'shaders' / filename

        with open(path) as file:
            source = file.read()
        return source

    @classmethod
    def load_sources(cls, *filenames: str) -> str:
        """Return the merged shader sources with deduplicated version and defines."""

        version = ''
        defines = ''
        code = ''

        for file in filenames:
            source = cls.load_source(file)
            for line in source.splitlines():
                if line.startswith('#version'):
                    if not version:
                        version = line + '\n'
                elif line.startswith('#define'):
                    defines += line + '\n'
                else:
                    code += line + '\n'
        merged_source = f'{version}\n{defines}\n{code}'
        return merged_source

    @staticmethod
    def read_buffer(buffer: int, array: np.ndarray) -> np.ndarray:
        """Return the data read from a buffer as an array matching `array`."""

        GL.glBindBuffer(GL.GL_SHADER_STORAGE_BUFFER, buffer)
        data = GL.glGetBufferSubData(GL.GL_SHADER_STORAGE_BUFFER, 0, array.nbytes)
        GL.glBindBuffer(GL.GL_SHADER_STORAGE_BUFFER, 0)

        buffer_array = np.frombuffer(data, dtype=array.dtype)
        buffer_array = np.reshape(buffer_array, array.shape)
        return buffer_array

    @staticmethod
    def read_texture(
        texture: int, resolution: QtCore.QSize, unit: int = 0
    ) -> np.ndarray:
        """Return the data read from a texture."""

        GL.glActiveTexture(GL.GL_TEXTURE0 + unit)  # ty: ignore[unsupported-operator]
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        data = GL.glGetTexImage(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, GL.GL_FLOAT)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE0)

        h = resolution.height()
        w = resolution.width()
        array = np.frombuffer(data, dtype=np.float32).reshape((h, w, 4))
        return array

    @staticmethod
    def blit_fbos(
        source: int,
        destination: int,
        source_resolution: QtCore.QSize,
        destination_resolution: QtCore.QSize,
    ) -> None:
        """Resolve a multisample FBO into a single-sample FBO."""

        sw, sh = source_resolution.toTuple()
        dw, dh = destination_resolution.toTuple()
        mask = GL.GL_COLOR_BUFFER_BIT
        GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, source)
        GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0)
        GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, destination)
        GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0)
        GL.glBlitFramebuffer(0, 0, sw, sh, 0, 0, dw, dh, mask, GL.GL_LINEAR)
        # Restore default binding for subsequent reads
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, destination)

    @staticmethod
    def create_buffer() -> int:
        buffer = GL.glGenBuffers(1)
        return buffer

    @staticmethod
    def create_vao() -> int:
        array = GL.glGenVertexArrays(1)
        return array

    @staticmethod
    def create_texture(
        tex_filter: int | Constant = GL.GL_LINEAR,
        clamp_to_border: bool = False,
        resolution: tuple[int, int] | None = None,
        fmt: int | Constant = GL.GL_RGBA32F,
    ) -> int:
        texture = GL.glGenTextures(1)

        target = GL.GL_TEXTURE_2D
        GL.glBindTexture(target, texture)
        if tex_filter > -1:  # ty: ignore[unsupported-operator]
            GL.glTexParameteri(target, GL.GL_TEXTURE_MIN_FILTER, tex_filter)
            GL.glTexParameteri(target, GL.GL_TEXTURE_MAG_FILTER, tex_filter)
        if clamp_to_border:
            GL.glTexParameteri(target, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_BORDER)
            GL.glTexParameteri(target, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_BORDER)
            GL.glTexParameterfv(target, GL.GL_TEXTURE_BORDER_COLOR, np.zeros(4))
        if resolution is not None:
            GL.glTexStorage2D(target, 1, fmt, resolution[0], resolution[1])
        GL.glBindTexture(target, 0)
        return texture

    @staticmethod
    def create_fbo(texture: int = -1, multisample: bool = False) -> int:
        buffer = GL.glGenFramebuffers(1)

        if texture > -1:
            target = GL.GL_FRAMEBUFFER
            attachment = GL.GL_COLOR_ATTACHMENT0
            tex_target = GL.GL_TEXTURE_2D
            if multisample:
                tex_target = GL.GL_TEXTURE_2D_MULTISAMPLE

            GL.glBindFramebuffer(target, buffer)
            GL.glFramebufferTexture2D(target, attachment, tex_target, texture, 0)
            GL.glBindFramebuffer(target, 0)
        return buffer

    @staticmethod
    def create_program(shaders: Sequence[int] = ()) -> int:
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

    @staticmethod
    def update_ssbo(
        buffer: int,
        array: np.ndarray,
        usage: int | Constant = GL.GL_DYNAMIC_DRAW,
    ) -> None:
        array = np.ascontiguousarray(array)
        GL.glBindBuffer(GL.GL_SHADER_STORAGE_BUFFER, buffer)
        GL.glBufferData(GL.GL_SHADER_STORAGE_BUFFER, array.nbytes, array, usage)
        GL.glBindBuffer(GL.GL_SHADER_STORAGE_BUFFER, 0)

    @staticmethod
    def update_ubo(
        buffer: int,
        array: np.ndarray,
        usage: int | Constant = GL.GL_DYNAMIC_DRAW,
    ) -> None:
        array = np.ascontiguousarray(array)
        GL.glBindBuffer(GL.GL_UNIFORM_BUFFER, buffer)
        GL.glBufferData(GL.GL_UNIFORM_BUFFER, array.nbytes, array, usage)
        GL.glBindBuffer(GL.GL_UNIFORM_BUFFER, 0)

    @staticmethod
    def update_vbo(
        buffer: int,
        array: np.ndarray,
        usage: int | Constant = GL.GL_STATIC_DRAW,
    ) -> None:
        array = np.ascontiguousarray(array)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, buffer)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, array.nbytes, array, usage)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)

    @staticmethod
    def update_ebo(
        buffer: int,
        array: np.ndarray,
        usage: int | Constant = GL.GL_STATIC_DRAW,
    ) -> None:
        array = np.ascontiguousarray(array)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, buffer)
        GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, array.nbytes, array, usage)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, 0)

    @staticmethod
    def update_fbo(buffer: int, texture: int) -> None:
        target = GL.GL_FRAMEBUFFER
        attachment = GL.GL_COLOR_ATTACHMENT0
        tex_target = GL.GL_TEXTURE_2D

        GL.glBindFramebuffer(target, buffer)
        GL.glFramebufferTexture2D(target, attachment, tex_target, texture, 0)
        GL.glBindFramebuffer(target, 0)

    @staticmethod
    def update_texture(texture: int, array: np.ndarray) -> None:
        """
        Update the texture with an array.

        Supported arrays shapes:
        (h, w)    -> GL_RED
        (h, w, 1) -> GL_RED
        (h, w, 3) -> GL_RGB
        (h, w, 4) -> GL_RGBA

        :raises ValueError: if the array has invalid shape.
        :raises ValueError: if the channel count is invalid.
        """

        formats = {
            1: (GL.GL_R32F, GL.GL_RED),
            3: (GL.GL_RGB32F, GL.GL_RGB),
            4: (GL.GL_RGBA32F, GL.GL_RGBA),
        }

        if len(array.shape) == 2:
            h, w = array.shape
            channels = 1
        elif len(array.shape) == 3:
            h, w, channels = array.shape
        else:
            raise ValueError(f'invalid array shape: {array.shape}')
        if channels not in formats:
            raise ValueError(f'invalid channel count: {channels}')

        target = GL.GL_TEXTURE_2D
        internal_fmt, fmt = formats[channels]
        data = np.ascontiguousarray(np.flipud(array))
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(target, texture)
        GL.glTexImage2D(target, 0, internal_fmt, w, h, 0, fmt, GL.GL_FLOAT, data)
        GL.glBindTexture(target, 0)

    @staticmethod
    def delete(
        programs: Sequence[int] = (),
        textures: Sequence[int] = (),
        render_buffers: Sequence[int] = (),
        vertex_arrays: Sequence[int] = (),
        buffers: Sequence[int] = (),
    ) -> None:
        """Delete resources from the current context."""

        for program in programs:
            with contextlib.suppress(GL.error.GLError):
                GL.glDeleteProgram(program)

        GL.glDeleteTextures(len(textures), textures)
        GL.glDeleteRenderbuffers(len(render_buffers), render_buffers)
        GL.glDeleteVertexArrays(len(vertex_arrays), vertex_arrays)
        GL.glDeleteBuffers(len(buffers), buffers)


class BindingManager:
    @staticmethod
    def bind_ssbo(buffer: int, slot: int) -> None:
        GL.glBindBufferBase(GL.GL_SHADER_STORAGE_BUFFER, slot, buffer)

    @staticmethod
    def bind_ssbo_block(program: int, name: str, slot: int) -> None:
        index = GL.glGetProgramResourceIndex(program, GL.GL_SHADER_STORAGE_BLOCK, name)
        GL.glShaderStorageBlockBinding(program, index, slot)

    @staticmethod
    def bind_ubo(buffer: int, slot: int) -> None:
        GL.glBindBufferBase(GL.GL_UNIFORM_BUFFER, slot, buffer)

    @staticmethod
    def bind_ubo_block(program: int, name: str, slot: int) -> None:
        index = GL.glGetUniformBlockIndex(program, name)
        GL.glUniformBlockBinding(program, index, slot)

    @staticmethod
    def bind_texture(texture: int, unit: int) -> None:
        GL.glActiveTexture(GL.GL_TEXTURE0 + unit)  # ty: ignore[unsupported-operator]
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glActiveTexture(GL.GL_TEXTURE0)

    @staticmethod
    def bind_texture_loc(program: int, name: str, unit: int) -> None:
        GL.glUseProgram(program)
        loc = GL.glGetUniformLocation(program, name)
        GL.glUniform1i(loc, unit)
        GL.glUseProgram(0)

    @staticmethod
    def bind_fbo(buffer: int) -> None:
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, buffer)

    @staticmethod
    def bind_vbo(buffer: int) -> None:
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, buffer)

    @staticmethod
    def bind_vao(buffer: int) -> None:
        GL.glBindVertexArray(buffer)

    @staticmethod
    def setup_vao(
        vao: int,
        vbo: int,
        location: int = 0,
        components: int = 3,
        dtype: int | Constant = GL.GL_FLOAT,
    ) -> None:
        """Configure how a VAO reads attributes from a VBO."""

        GL.glBindVertexArray(vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)

        GL.glEnableVertexAttribArray(location)
        int_types = (GL.GL_INT, GL.GL_UNSIGNED_INT, GL.GL_SHORT, GL.GL_UNSIGNED_SHORT)
        if dtype in int_types:
            GL.glVertexAttribIPointer(location, components, dtype, 0, None)
        else:
            GL.glVertexAttribPointer(location, components, dtype, GL.GL_FALSE, 0, None)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glBindVertexArray(0)


class OpenGLTask(Task, ResourceManager, BindingManager):
    _instance: 'OpenGLTask | None' = None

    def __new__(cls: type[T], *args: Any, **kwargs: Any) -> T:
        # NOTE: Tasks bind resources to slots that are constants. Multiple instances
        # would access the same slots, so only one instance is allowed.
        if cls._instance is not None:
            raise RuntimeError(f'cannot instance {cls.__name__} multiple times')
        cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        super().__init__()

        self.context = context

    @staticmethod
    def load_shader(source: str, shader_type: int | Constant) -> int:
        shader = GL.glCreateShader(shader_type)
        GL.glShaderSource(shader, source)
        GL.glCompileShader(shader)

        if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
            log = GL.glGetShaderInfoLog(shader)
            raise RuntimeError(log.decode('utf-8', errors='replace'))
        return shader

    @staticmethod
    def render(program: int, fbo: int, resolution: QtCore.QSize) -> None:
        """Render the program for the screen vertex shader to the framebuffer."""

        GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, fbo)
        GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0)
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glViewport(0, 0, resolution.width(), resolution.height())

        GL.glUseProgram(program)

        # Reset program
        GL.glDisableVertexAttribArray(0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glBindBuffer(GL.GL_DRAW_INDIRECT_BUFFER, 0)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, 0)

        GL.glDisable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnable(GL.GL_DEPTH_TEST)

        # Render
        # NOTE: Use a triangle that spans the whole screen.
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)

        GL.glFinish()


def _as_int(value: Any) -> int | None:
    """Return the int extracted from a glGet result."""

    if value is None:
        return None
    try:
        # numpy array or sequence
        if hasattr(value, '__len__') and not isinstance(value, (str, bytes)):
            if len(value) == 0:
                return None
            value = value[0]
        return int(value)
    except Exception:
        return None


def get_vram_info() -> dict[str, int | None]:
    """
    Return VRAM usage in KB.

    Keys: total_kb, available_kb, used_kb
    Values are int in KB or None if unsupported/unavailable.
    Works across vendors: NVIDIA (NVX), ATI/AMD (ATI_meminfo).
    Requires a current OpenGL context; otherwise returns all None.
    """

    total_kb: int | None = None
    available_kb: int | None = None

    # NVIDIA: GL_NVX_gpu_memory_info
    try:
        from OpenGL.GL.NVX.gpu_memory_info import (
            GL_GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX,
            GL_GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX,
        )

        total_val = GL.glGetIntegerv(GL_GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX)
        avail_val = GL.glGetIntegerv(GL_GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX)
        total_kb = _as_int(total_val)
        available_kb = _as_int(avail_val)
        # Treat 0 as unavailable (no context or unsupported)
        if total_kb == 0:
            total_kb = None
        if available_kb == 0 and total_kb is None:
            available_kb = None
    except Exception:
        pass

    # ATI / AMD: GL_ATI_meminfo (GL_TEXTURE_FREE_MEMORY_ATI = 0x87FC)
    # Returns 4 ints: [total free, largest block, aux free, largest aux] in KB.
    # No total dedicated, so only available can be queried.
    if available_kb is None:
        try:
            GL_TEXTURE_FREE_MEMORY_ATI = 0x87FC
            # Try to get via glGetIntegerv; may need to check extension.
            # Some implementations expose as vec4, others via glGetIntegerv with count.
            # We try generic call and parse first element.
            val = GL.glGetIntegerv(GL_TEXTURE_FREE_MEMORY_ATI)
            # In PyOpenGL, this returns a tuple/list of 4 ints if successful.
            if val is not None:
                if hasattr(val, '__len__') and len(val) >= 1:
                    available_kb = _as_int(val[0])
                else:
                    available_kb = _as_int(val)
                # Some drivers return 0 on failure, treat as unavailable
                if available_kb == 0:
                    available_kb = None
        except Exception:
            pass

    # Fallback for Renderbuffer free memory (same values)
    if available_kb is None:
        try:
            GL_RENDERBUFFER_FREE_MEMORY_ATI = 0x87FD
            val = GL.glGetIntegerv(GL_RENDERBUFFER_FREE_MEMORY_ATI)
            if val is not None and hasattr(val, '__len__') and len(val) >= 1:
                available_kb = _as_int(val[0])
            else:
                available_kb = _as_int(val)
            if available_kb == 0:
                available_kb = None
        except Exception:
            pass

    used_kb: int | None = None
    if total_kb is not None and available_kb is not None:
        try:
            used_kb = total_kb - available_kb
        except Exception:
            used_kb = None

    return {'total_kb': total_kb, 'available_kb': available_kb, 'used_kb': used_kb}


def get_total_vram_kb() -> int | None:
    """Return total VRAM in KB or None if unavailable."""

    return get_vram_info()['total_kb']


def get_available_vram_kb() -> int | None:
    """Return currently available VRAM in KB or None if unavailable."""

    return get_vram_info()['available_kb']


def get_used_vram_kb() -> int | None:
    """Return currently used VRAM in KB or None if unavailable."""

    return get_vram_info()['used_kb']
