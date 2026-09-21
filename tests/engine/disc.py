from OpenGL import GL
from qtpy import QtCore, QtGui

import tests
from flare.engine.base import Array
from flare.engine.opengl import OpenGLTask, create_context_surface
from flare.engine.tasks.common import DiscMesh
from flare.ui import application
from flare.ui.widgets import Viewer

RESOLUTION = QtCore.QSize(512, 512)

VERTEX_SHADER = """
#version 430 core

layout (location = 0) in vec3 position;
void main() {
    gl_Position = vec4(position.xy, 0.0, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 430 core

out vec4 rgba;
void main() {
    rgba = vec4(1.0);
}
"""


class DiscTask(OpenGLTask):
    """Draw a DiscMesh as a wireframe."""

    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        super().__init__(context)

        vertex_shader = self.load_shader(VERTEX_SHADER, GL.GL_VERTEX_SHADER)
        fragment_shader = self.load_shader(FRAGMENT_SHADER, GL.GL_FRAGMENT_SHADER)

        self._program = self.create_program(shaders=(vertex_shader, fragment_shader))
        self._texture = self.create_texture(
            clamp_to_border=True, resolution=RESOLUTION.toTuple()
        )
        self._fbo = self.create_fbo(self._texture)
        self._vbo = self.create_buffer()
        self._vao = self.create_vao()

    def run(self, radius: float = 0.8, resolution: int = 8) -> Array:
        """Return the rendered DiscMesh wireframe."""

        vertices = DiscMesh.get_triangles(radius=radius, resolution=resolution)
        self.update_vbo(self._vbo, vertices)
        self.setup_vao(self._vao, self._vbo, location=0, components=3)
        self.bind_vao(self._vao)

        GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, self._fbo)
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glViewport(0, 0, RESOLUTION.width(), RESOLUTION.height())
        GL.glUseProgram(self._program)
        GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, len(vertices))
        GL.glFinish()

        array = self.read_texture(self._texture, RESOLUTION)
        return Array(array=array, args=(self._fbo,))


def main() -> None:
    with application():
        context, _ = create_context_surface()

        image = DiscTask(context).run()

        viewer = Viewer()
        viewer.show()
        viewer.set_array(image.array)


if __name__ == '__main__':
    tests.init()
    main()
