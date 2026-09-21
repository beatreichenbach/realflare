from qtpy import QtCore, QtWidgets

from flare.ui.widgets import (
    DockWidgetState,
    StateDockWindow,
    TabState,
    WindowState,
)
from flare.ui.widgets.dock_window.drag import DockDrag


class WidgetA(QtWidgets.QWidget): ...


def _window() -> StateDockWindow:
    window = StateDockWindow()
    window.register_widget(WidgetA, 'A')
    return window


def _dock_with(window: StateDockWindow, title: str) -> QtWidgets.QWidget | None:
    for dock in window.dock_widgets():
        titles = [dock.tabText(i) for i in range(dock.count())]
        if title in titles:
            return dock
    return None


def _source(window: StateDockWindow) -> tuple[QtWidgets.QWidget, DockDrag]:
    window.show_widget('A')
    dock = _dock_with(window, 'A')
    assert dock is not None
    drag = DockDrag(source=dock, widget=dock.widget(0), title='A')
    return dock, drag


def test_dock_area_at(qapp: QtWidgets.QApplication) -> None:
    window = _window()
    dock = window.center_widget
    dock.resize(100, 100)

    areas = QtCore.Qt.DockWidgetArea
    assert dock.dock_area_at(QtCore.QPoint(5, 50)) == areas.LeftDockWidgetArea
    assert dock.dock_area_at(QtCore.QPoint(95, 50)) == areas.RightDockWidgetArea
    assert dock.dock_area_at(QtCore.QPoint(50, 5)) == areas.TopDockWidgetArea
    assert dock.dock_area_at(QtCore.QPoint(50, 95)) == areas.BottomDockWidgetArea
    assert dock.dock_area_at(QtCore.QPoint(50, 50)) == areas.NoDockWidgetArea


def test_drop_adds_tab(qapp: QtWidgets.QApplication) -> None:
    window = _window()
    source, drag = _source(window)

    drag.drop(window.center_widget, QtCore.Qt.DockWidgetArea.NoDockWidgetArea)

    assert _dock_with(window, 'A') is window.center_widget
    assert source.count() == 0


def test_drop_creates_dock(qapp: QtWidgets.QApplication) -> None:
    window = _window()
    source, drag = _source(window)

    drag.drop(window.center_widget, QtCore.Qt.DockWidgetArea.LeftDockWidgetArea)

    dock = _dock_with(window, 'A')
    assert dock is not None
    assert dock is not window.center_widget
    assert dock is not source


def test_float_creates_window(qapp: QtWidgets.QApplication) -> None:
    window = _window()
    source, drag = _source(window)

    drag.float()

    dock = _dock_with(window, 'A')
    assert dock is not None
    assert dock is not source
    assert dock.isWindow()


def test_drop_splits_own_dock(qapp: QtWidgets.QApplication) -> None:
    window = _window()
    window.set_window_state(
        WindowState(
            states=(
                DockWidgetState(
                    current_index=0,
                    widgets=(TabState('One', 'A'), TabState('Two', 'A')),
                    detachable=True,
                    auto_delete=False,
                    is_center_widget=True,
                ),
            ),
        )
    )
    source = window.center_widget
    drag = DockDrag(source=source, widget=source.widget(0), title='One')

    drag.drop(source, QtCore.Qt.DockWidgetArea.LeftDockWidgetArea)

    assert window.center_splitter.count() == 2
    assert source.count() == 1
    assert _dock_with(window, 'One') is not source
