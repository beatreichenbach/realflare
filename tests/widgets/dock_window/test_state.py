import pytest
from pydantic import ValidationError
from qtpy import QtCore, QtWidgets

from flare.widgets.dock_window import StateDockWindow, WindowState


class WidgetA(QtWidgets.QWidget):
    pass


class WidgetB(QtWidgets.QWidget):
    pass


def _dock(current_index: int, widgets: list[list[str]]) -> dict:
    return {
        'kind': 'dock',
        'current_index': current_index,
        'widgets': widgets,
        'detachable': True,
        'auto_delete': True,
        'is_center_widget': False,
    }


def _splitter(states: list[dict], sizes: list[int]) -> dict:
    return {
        'kind': 'splitter',
        'sizes': sizes,
        'orientation': QtCore.Qt.Orientation.Horizontal,
        'states': states,
    }


def _window() -> StateDockWindow:
    window = StateDockWindow()
    window.register_widget(WidgetA, name='A', unique=True)
    window.register_widget(WidgetB, name='B')
    return window


def _set_state(window: StateDockWindow, data: dict) -> None:
    window.set_window_state(WindowState.model_validate(data))


def test_state_round_trip(qapp: QtWidgets.QApplication) -> None:
    window = _window()
    _set_state(
        window,
        {
            'states': [
                _splitter(
                    [_dock(0, [['A', 'WidgetA']]), _dock(0, [['B', 'WidgetB']])],
                    [200, 200],
                ),
            ],
        },
    )

    state = window.window_state().model_dump()
    docks = state['states'][0]['states']
    titles = [title for dock in docks for title, _ in dock['widgets']]
    assert 'A' in titles
    assert 'B' in titles


def test_unique_widget_not_duplicated(qapp: QtWidgets.QApplication) -> None:
    window = _window()
    _set_state(
        window,
        {
            'states': [
                _splitter(
                    [_dock(0, [['A', 'WidgetA']]), _dock(0, [['A', 'WidgetA']])],
                    [200, 200],
                ),
            ],
        },
    )

    count = sum(isinstance(widget, WidgetA) for widget in window._widgets.values())
    assert count == 1


def test_close_does_not_delete_widgets(qapp: QtWidgets.QApplication) -> None:
    window = _window()
    window.show_widget('A')
    dock = window.dock_widgets()[0]
    dock.close()

    assert any(isinstance(w, WidgetA) for w in window._widgets.values())


def test_close_closes_floating_docks(qapp: QtWidgets.QApplication) -> None:
    window = _window()
    window.show()
    window.show_widget('A')
    dock = window.dock_widgets()[0]
    assert dock.isVisible()

    window.close()
    assert not dock.isVisible()


def test_invalid_kind_raises(qapp: QtWidgets.QApplication) -> None:
    window = _window()
    with pytest.raises(ValidationError):
        _set_state(window, {'states': [{'kind': 'nope'}]})


def test_window_state_round_trip() -> None:
    state = WindowState.model_validate(
        {
            'states': [
                _splitter([_dock(0, [['A', 'WidgetA']])], [100]),
            ],
        }
    )
    dumped = state.model_dump()
    assert dumped['states'][0]['kind'] == 'splitter'
    assert dumped['states'][0]['states'][0]['kind'] == 'dock'


def _process_deletions() -> None:
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


def test_set_state_removes_unused_docks(qapp: QtWidgets.QApplication) -> None:
    window = _window()

    center = _dock(0, [['A', 'WidgetA']])
    center['is_center_widget'] = True
    center['auto_delete'] = False

    _set_state(
        window,
        {
            'states': [
                _splitter([center, _dock(0, [['B', 'WidgetB']])], [100, 100]),
            ],
        },
    )
    _set_state(
        window,
        {
            'states': [
                _splitter([center], [100]),
            ],
        },
    )
    _process_deletions()

    unused = [d for d in window.dock_widgets() if d is not window.center_widget]
    assert unused == []


def test_close_tab_deletes_widget(qapp: QtWidgets.QApplication) -> None:
    window = _window()
    window.show_widget('A')
    dock = window.dock_widgets()[0]
    widget = dock.widget(0)
    assert widget is not None

    dock.close_tab(0)
    _process_deletions()

    assert not any(w is widget for w in window._widgets.values())
