import os
from collections.abc import Iterator

import pytest
from qtpy import QtWidgets


@pytest.fixture(scope='session')
def qapp() -> Iterator[QtWidgets.QApplication]:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    yield app

    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    app.processEvents()
