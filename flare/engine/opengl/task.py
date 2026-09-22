from functools import lru_cache
from typing import ClassVar, TypeVar

from OpenGL import GL
from OpenGL.constant import Constant
from qtpy import QtCore, QtGui

from ..base import Array, Task
from .resources import BindingManager, ResourceManager

T = TypeVar('T', bound='OpenGLTask')


class OpenGLTask(Task, ResourceManager, BindingManager):
    _instances: ClassVar[dict[QtGui.QOpenGLContext, dict[type, 'OpenGLTask']]] = {}

    def __new__(
        cls: type[T], context: QtGui.QOpenGLContext, *args: object, **kwargs: object
    ) -> T:
        # NOTE: Tasks bind resources to slots that are constants per context.
        # Multiple instances per context would access the same slots, so only one
        # instance per task class and context is allowed.
        instances = OpenGLTask._instances.setdefault(context, {})
        if cls in instances:
            raise RuntimeError(f'cannot instance {cls.__name__} multiple times')
        instance = super().__new__(cls)
        instances[cls] = instance
        return instance

    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        super().__init__()

        self.context = context

    def release(self) -> None:
        """Delete the task resources and allow re-instantiation for the context."""

        self.delete_resources()

        # Clear the cached methods using lru_cache so they release the reference to
        # this instance.
        for name in dir(type(self)):
            cache_clear = getattr(getattr(type(self), name, None), 'cache_clear', None)
            if callable(cache_clear):
                cache_clear()

        instances = OpenGLTask._instances.get(self.context)
        if instances is not None:
            instances.pop(type(self), None)
            if not instances:
                OpenGLTask._instances.pop(self.context, None)

    @lru_cache(1)  # noqa: B019
    def cached_update_ssbo(
        self,
        buffer: int,
        array: Array,
        usage: int | Constant = GL.GL_DYNAMIC_DRAW,
    ) -> None:
        self.update_ssbo(buffer, array.array, usage)

    @lru_cache(1)  # noqa: B019
    def cached_update_texture(self, texture: int, array: Array) -> None:
        self.update_texture(texture, array.array)

    @lru_cache(1)  # noqa: B019
    def cached_update_mipmap_texture(self, texture: int, array: Array) -> None:
        self.update_texture(texture, array.array)
        self.generate_mipmap(texture)

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
