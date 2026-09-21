import logging

from OpenGL import GL
from qtpy import QtOpenGLWidgets, QtWidgets

import tests

logger = logging.getLogger(__name__)


class GLWidget(QtOpenGLWidgets.QOpenGLWidget):
    """Temporary widget to initialize an OpenGL context."""

    def __init__(self):
        super().__init__()
        self.showMinimized()

    def log_system_info(self):
        self.makeCurrent()

        logger.info('--- OpenGL Version & Device ---')
        constants = (
            GL.GL_VENDOR,
            GL.GL_RENDERER,
            GL.GL_VERSION,
            GL.GL_SHADING_LANGUAGE_VERSION,
        )
        for constant in constants:
            value = GL.glGetString(constant)
            logger.info(f'{constant.name:<48}{value.decode()}')
        logger.info('')

        logger.info('--- Hardware Limits & VRAM ---')
        constants = (GL.GL_MAX_UNIFORM_BLOCK_SIZE,)
        for constant in constants:
            value = GL.glGetIntegerv(constant)
            logger.info(f'{constant.name:<48}{value}')

        # Nvidia
        try:
            from OpenGL.GL.NVX.gpu_memory_info import (
                GL_GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX,
                GL_GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX,
            )

            total_memory = GL.glGetIntegerv(
                GL_GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX
            )
            current_memory = GL.glGetIntegerv(
                GL_GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX
            )
            logger.info(
                f'{"NVIDIA TOTAL_AVAILABLE_MEMORY":<48}{total_memory / 1024:.2f} MB'
            )
            logger.info(
                f'{"NVIDIA CURRENT_AVAILABLE_VIDMEM":<48}{current_memory / 1024:.2f} MB'
            )
        except ImportError, AttributeError:
            pass
        logger.info('')

        logger.info('--- Shader Limits ---')
        constants = (
            GL.GL_MAX_COMPUTE_ATOMIC_COUNTERS,
            GL.GL_MAX_COMPUTE_ATOMIC_COUNTER_BUFFERS,
            GL.GL_MAX_COMPUTE_IMAGE_UNIFORMS,
            GL.GL_MAX_COMPUTE_SHARED_MEMORY_SIZE,
            GL.GL_MAX_COMPUTE_TEXTURE_IMAGE_UNITS,
            GL.GL_MAX_COMPUTE_UNIFORM_BLOCKS,
            GL.GL_MAX_COMPUTE_UNIFORM_COMPONENTS,
            GL.GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS,
        )
        for constant in constants:
            value = GL.glGetIntegerv(constant)
            logger.info(f'{constant.name:<48}{value}')

        constants = (
            GL.GL_MAX_COMPUTE_WORK_GROUP_COUNT,
            GL.GL_MAX_COMPUTE_WORK_GROUP_SIZE,
        )
        for constant in constants:
            values = [
                int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_COUNT, i)[0])
                for i in range(3)
            ]

            logger.info(f'{constant.name:<48}{values}')
        logger.info('')

        self.doneCurrent()


def log_system_info():
    app = QtWidgets.QApplication()

    widget = GLWidget()
    widget.log_system_info()

    app.quit()


if __name__ == '__main__':
    tests.init()
    log_system_info()
