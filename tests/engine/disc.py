import numpy as np
from OpenGL import GL
from qtpy import QtCore, QtGui

from flare.engine.base import Array
from flare.engine.opengl import OpenGLTask
from flare.engine.tasks.common import DiscMesh
from flare.ui import application
from flare.ui.widgets.viewer import Viewer

VERTEX_SHADER = """
#version 430 core

layout (location = 0) in vec2 position;
void main() {
    gl_Position = vec4(position, 0.0, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 430 core

out vec4 FragColor;
void main() {
    FragColor = vec4(1.0);
}
"""


class GridTask(OpenGLTask):
    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        super().__init__(context)

        vertex_shader = self.load_shader(VERTEX_SHADER, GL.GL_VERTEX_SHADER)
        fragment_shader = self.load_shader(FRAGMENT_SHADER, GL.GL_FRAGMENT_SHADER)

        self._program = self.create_program(shaders=(vertex_shader, fragment_shader))
        self._fbo_texture = self.create_texture(clamp_to_border=True)
        self._fbo = self.create_fbo(self._fbo_texture)
        self._vbo = self.create_buffer()
        self._vao = self.create_vao()

    def run(self) -> Array:
        width, height = 512, 512

        vertices = DiscMesh.get_triangles(radius=0.8, resolution=8)
        direction = (1, 0)
        direction /= np.linalg.norm(direction)
        rotation = np.array(
            ((direction[0], -direction[1]), (direction[1], direction[0]))
        )
        vertices[:, :2] = vertices[:, :2] @ rotation
        self.update_vbo(self._vbo, vertices)

        resolution = QtCore.QSize(width, height)
        self._fbo_texture = self.create_texture(
            clamp_to_border=True, resolution=resolution.toTuple()
        )
        self.update_fbo(self._fbo, self._fbo_texture)

        # Render
        GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, self._fbo)
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glViewport(0, 0, resolution.width(), resolution.height())

        GL.glUseProgram(self._program)

        GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, vertices.size)
        GL.glFinish()

        # Copy buffer
        data = GL.glReadPixels(0, 0, width, height, GL.GL_RGBA, GL.GL_FLOAT)
        array = np.frombuffer(data, dtype=np.float32).reshape((height, width, 4))
        array = np.flipud(array)

        image = Array(array=array, args=(self._fbo,))
        return image


def main() -> None:
    with application():
        context = QtGui.QOpenGLContext()
        context.create()
        surface = QtGui.QOffscreenSurface()
        surface.create()
        context.makeCurrent(surface)

        task = GridTask(context)
        image = task.run()

        viewer = Viewer()
        viewer.show()
        viewer.set_array(image.array)


if __name__ == '__main__':
    main()
