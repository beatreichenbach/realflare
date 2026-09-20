import contextlib
import sys
from typing import Generator

import qt_themes
from importlib.resources import files
from qtpy import QtCore, QtGui, QtWidgets


@contextlib.contextmanager
def application() -> Generator[QtCore.QCoreApplication, None, None]:
    app = QtWidgets.QApplication(sys.argv)

    qt_themes.set_theme('one_dark_two')

    icon_path = files('flare').joinpath('assets').joinpath('icon.png')
    icon = QtGui.QIcon(str(icon_path))
    app.setWindowIcon(icon)

    yield app

    app.exec_()
