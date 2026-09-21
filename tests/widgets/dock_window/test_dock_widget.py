from qtpy import QtCore, QtWidgets

from flare.widgets.dock_window import DockWidget, DockWindow


def test_dock_rect_areas(qapp: QtWidgets.QApplication) -> None:
    window = DockWindow()
    dock = DockWidget(dock_window=window)
    dock.resize(100, 100)

    areas = QtCore.Qt.DockWidgetArea
    assert dock._dock_rect(areas.LeftDockWidgetArea) == QtCore.QRect(0, 0, 20, 100)
    assert dock._dock_rect(areas.RightDockWidgetArea) == QtCore.QRect(80, 0, 20, 100)
    assert dock._dock_rect(areas.TopDockWidgetArea) == QtCore.QRect(0, 0, 100, 20)
    assert dock._dock_rect(areas.BottomDockWidgetArea) == QtCore.QRect(0, 80, 100, 20)
    assert dock._dock_rect(areas.NoDockWidgetArea) == QtCore.QRect(0, 0, 100, 100)
