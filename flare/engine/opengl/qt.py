from qtpy import QtGui

from ..base import EngineError


def create_context_surface() -> tuple[QtGui.QOpenGLContext, QtGui.QOffscreenSurface]:
    """
    Return a current OpenGL 4.3 core context and its offscreen surface.

    :raises EngineError: if the surface or context cannot be created.
    """

    # Format
    fmt = QtGui.QSurfaceFormat()
    fmt.setProfile(QtGui.QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    # NOTE: Set both RenderableType and Version, otherwise a mismatch happens.
    fmt.setRenderableType(QtGui.QSurfaceFormat.RenderableType.OpenGL)
    fmt.setVersion(4, 3)

    # Surface
    surface = QtGui.QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid():
        raise EngineError('invalid QOffscreenSurface')

    # Context
    context = QtGui.QOpenGLContext()
    context.setFormat(fmt)
    context.create()
    if not context.isValid():
        raise EngineError('invalid QOpenGLContext')

    # Make current
    if not context.makeCurrent(surface):
        raise EngineError('failed to make the context current')

    # Version
    actual_fmt = context.format()
    major, minor = actual_fmt.version()
    if (major, minor) < (4, 3):
        raise EngineError(f'required OpenGL 4.3, got OpenGL {major}.{minor}')

    return context, surface
