from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from qtpy import QtWidgets

from .dock_widget import DockWidget
from .splitter import Splitter
from .state import (
    BaseNodeState,
    DockWidgetState,
    NodeState,
    SplitterState,
    WindowState,
)
from .utils import tab_widget_classes

if TYPE_CHECKING:
    from .dock_window import DockWindow


def capture(window: DockWindow) -> WindowState:
    """Return the state of a dock window."""

    return WindowState(
        geometry=window.geometry(),
        states=_child_states(window),
    )


def restore(window: DockWindow, state: WindowState) -> None:
    """Apply a state to a dock window."""

    geometry = state.geometry
    if geometry.width() > 0 and geometry.height() > 0:
        window.setGeometry(geometry)

    # Unparent all widgets to clean up layout
    for widget in window._widgets.values():
        widget.setParent(None)
        widget.close()

    widgets = dict(window._widgets)
    _set_child_states(window, state.states, widgets)

    # Remove unused widgets
    for widget in widgets.values():
        widget.deleteLater()


def _child_state(window: DockWindow, widget: QtWidgets.QWidget) -> NodeState | None:
    """Return the state of a widget in the window."""

    if isinstance(widget, Splitter):
        state: BaseNodeState = SplitterState(
            sizes=tuple(widget.sizes()),
            orientation=widget.orientation(),
            states=_child_states(window, widget),
        )
    elif isinstance(widget, DockWidget):
        widgets = tab_widget_classes(widget)
        state = DockWidgetState(
            current_index=widget.currentIndex(),
            widgets=widgets,
            detachable=widget.detachable,
            auto_delete=widget.auto_delete,
            is_center_widget=(widget == window.center_widget),
        )
    else:
        return None

    if widget.isWindow():
        state.geometry = widget.geometry()
        state.flags = widget.windowFlags()
    return state


def _child_states(
    window: DockWindow, parent: QtWidgets.QWidget | None = None
) -> tuple[NodeState, ...]:
    """Return the states of all widgets in the window."""

    if parent is None:
        children = (window.center_splitter,)
    elif isinstance(parent, (Splitter, DockWidget)):
        children = (parent.widget(i) for i in range(parent.count()))
    else:
        return ()

    states = []
    for child in children:
        if isinstance(child, QtWidgets.QWidget):
            state = _child_state(window, child)
            if state is not None:
                states.append(state)
    return tuple(states)


def _set_child_states(
    window: DockWindow,
    states: Sequence[NodeState],
    widgets: dict[str, QtWidgets.QWidget],
    parent: QtWidgets.QWidget | None = None,
) -> None:
    """
    Set the States where `widgets` is a dictionary of existing widgets. Widgets
    used from this dictionary are removed to keep track of which ones have been
    re-parented.
    """

    if parent is None:
        parent = window

    for i, state in enumerate(states):
        widget = _create_widget(window, state, widgets, parent)
        if widget is None:
            continue
        _place_widget(parent, widget, i)
        _apply_window_state(widget, state)


def _create_widget(
    window: DockWindow,
    state: NodeState,
    widgets: dict[str, QtWidgets.QWidget],
    parent: QtWidgets.QWidget,
) -> QtWidgets.QWidget | None:
    """Create the widget for a state and return it."""

    if isinstance(state, SplitterState):
        if parent == window:
            splitter = window.center_splitter
            splitter.setOrientation(state.orientation)
        else:
            splitter = Splitter(state.orientation)
        _set_child_states(window, state.states, widgets, splitter)
        splitter.setSizes(state.sizes)
        return splitter

    if isinstance(state, DockWidgetState):
        return _create_dock_widget(window, state, widgets)

    return None


def _create_dock_widget(
    window: DockWindow,
    state: DockWidgetState,
    widgets: dict[str, QtWidgets.QWidget],
) -> DockWidget:
    """Create a dock widget with its tabs from a state."""

    if state.is_center_widget:
        dock_widget = window.center_widget
    else:
        dock_widget = DockWidget(window)
        dock_widget.detachable = state.detachable
        dock_widget.auto_delete = state.auto_delete

    for title, cls_name in state.widgets:
        widget = _create_tab_widget(window, title, cls_name, widgets)
        if widget is None:
            continue
        unique_title = window._add_widget(widget, title)
        dock_widget.addTab(widget, unique_title)

    dock_widget.setCurrentIndex(min(state.current_index, dock_widget.count() - 1))
    return dock_widget


def _create_tab_widget(
    window: DockWindow,
    title: str,
    cls_name: str,
    widgets: dict[str, QtWidgets.QWidget],
) -> QtWidgets.QWidget | None:
    """
    Return a widget for a tab, taking it from `widgets` if it exists. Return None
    to skip unregistered or duplicate unique widgets.
    """

    widget = widgets.pop(title, None)
    if widget is not None:
        return widget

    registered_widget = window._get_registered_widget(cls_name)
    if not registered_widget:
        return None

    if registered_widget.unique:
        values = window._widgets.values()
        if any(isinstance(value, registered_widget.cls) for value in values):
            return None

    return registered_widget.cls()


def _place_widget(
    parent: QtWidgets.QWidget, widget: QtWidgets.QWidget, index: int
) -> None:
    """Parent a widget at an index of its parent."""

    if isinstance(parent, Splitter):
        if parent.widget(index) is not None:
            # Not replacing the widget with itself prevents warnings
            if parent.widget(index) != widget:
                parent.replaceWidget(index, widget)
                widget.setParent(parent)
                widget.show()
        else:
            parent.addWidget(widget)
    else:
        widget.show()


def _apply_window_state(widget: QtWidgets.QWidget, state: NodeState) -> None:
    """Restore floating geometry and window flags."""

    if state.flags:
        widget.setWindowFlags(state.flags)
        widget.setGeometry(state.geometry)
        widget.show()
