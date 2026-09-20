from __future__ import annotations

import OpenGL
from OpenGL import GL
import importlib.resources
from qt_parameters import ParameterForm, StringParameter
from qtpy import QtCore, QtGui, QtWidgets

import flare


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle('About')
        self.resize(640, 240)

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)

        # Icon
        icon_path = (
            importlib.resources.files(flare.__name__)
            .joinpath('assets')
            .joinpath('icon.png')
        )
        pixmap = QtGui.QPixmap(str(icon_path))
        label = QtWidgets.QLabel()
        label.setPixmap(pixmap)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        layout.addWidget(label)

        # Data
        form = ParameterForm()
        layout.addWidget(form)
        layout.setStretch(1, 1)

        python_form = ParameterForm('python')
        form.add_form(python_form)

        param = StringParameter(flare.__name__)
        param.set_label(param.name())
        param.set_value(flare.__version__)
        param.text.setReadOnly(True)
        python_form.add_parameter(param)

        param = StringParameter(OpenGL.__name__)
        param.set_label(param.name())
        param.set_value(OpenGL.__version__)
        param.text.setReadOnly(True)
        python_form.add_parameter(param)

        python_form = ParameterForm('open_gl')
        box = form.add_form(python_form)
        box.set_title('OpenGL')
        box.set_collapsed(True)

        context = QtGui.QOpenGLContext()
        context.create()
        surface = QtGui.QOffscreenSurface()
        surface.create()
        context.makeCurrent(surface)

        param = StringParameter('GL_VERSION')
        param.set_label(param.name())
        param.set_value(GL.glGetString(GL.GL_VERSION).decode('utf-8'))
        param.text.setReadOnly(True)
        python_form.add_parameter(param)

        max_work_group_size = (
            int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_SIZE, 0)[0]),
            int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_SIZE, 1)[0]),
            int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_SIZE, 2)[0]),
        )
        param = StringParameter('GL_MAX_COMPUTE_WORK_GROUP_SIZE')
        param.set_label(param.name())
        param.set_value(f'{max_work_group_size}')
        param.text.setReadOnly(True)
        python_form.add_parameter(param)

        max_work_group_count = (
            int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_COUNT, 0)[0]),
            int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_COUNT, 1)[0]),
            int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_COUNT, 2)[0]),
        )
        param = StringParameter('GL_MAX_COMPUTE_WORK_GROUP_COUNT')
        param.set_label(param.name())
        param.set_value(f'{max_work_group_count}')
        param.text.setReadOnly(True)
        python_form.add_parameter(param)

        max_invocations = GL.glGetInteger(GL.GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS)
        param = StringParameter('GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS')
        param.set_label(param.name())
        param.set_value(f'{max_invocations}')
        param.text.setReadOnly(True)
        python_form.add_parameter(param)
