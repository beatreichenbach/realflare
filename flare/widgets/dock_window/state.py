from collections.abc import Sequence
from typing import Annotated, Literal, NamedTuple

from pydantic import BaseModel, Field
from qt_pydantic import QRect
from qtpy import QtCore, QtWidgets

from .dock_widget import DockWidget
from .dock_window import DockWindow
from .splitter import Splitter


class TabState(NamedTuple):
    title: str
    cls_name: str


class BaseWidgetState(BaseModel):
    geometry: QRect = QtCore.QRect()
    flags: QtCore.Qt.WindowType = QtCore.Qt.WindowType(0)


class SplitterState(BaseWidgetState):
    kind: Literal['splitter'] = 'splitter'
    sizes: tuple[int, ...]
    orientation: QtCore.Qt.Orientation
    states: tuple['WidgetState', ...] = ()


class DockWidgetState(BaseWidgetState):
    kind: Literal['dock'] = 'dock'
    current_index: int
    widgets: tuple[TabState, ...]
    detachable: bool
    auto_delete: bool
    is_center_widget: bool


WidgetState = Annotated[SplitterState | DockWidgetState, Field(discriminator='kind')]


# NOTE: SplitterState is defined before WidgetState but references it in its
# `states` field, so the model is incomplete until rebuilt with WidgetState defined.
SplitterState.model_rebuild()


class WindowState(BaseModel):
    geometry: QRect = QtCore.QRect()
    states: tuple[WidgetState, ...] = ()


class StateDockWindow(DockWindow):
    """A dock window that can save and restore its layout state."""

    def window_state(self) -> WindowState:
        """Return the state of the window with its nested splitters and docks."""

        return WindowState(
            geometry=self.geometry(),
            states=self._child_states(),
        )

    def set_window_state(self, state: WindowState) -> None:
        """Apply a state to the window, creating and reparenting its widgets."""

        geometry = state.geometry
        if geometry.width() > 0 and geometry.height() > 0:
            self.setGeometry(geometry)

        # Unparent all widgets to clean up layout
        for widget in self._widgets.values():
            widget.setParent(None)
            widget.close()

        widgets = dict(self._widgets)
        self._set_child_states(state.states, widgets)

        # Remove unused widgets
        for widget in widgets.values():
            widget.deleteLater()

    def _child_state(self, widget: QtWidgets.QWidget) -> WidgetState | None:
        """Return the state of a widget in the window."""

        if isinstance(widget, Splitter):
            state: BaseWidgetState = SplitterState(
                sizes=tuple(widget.sizes()),
                orientation=widget.orientation(),
                states=self._child_states(widget),
            )
        elif isinstance(widget, DockWidget):
            state = DockWidgetState(
                current_index=widget.currentIndex(),
                widgets=tab_states(widget),
                detachable=widget.detachable,
                auto_delete=widget.auto_delete,
                is_center_widget=(widget == self.center_widget),
            )
        else:
            return None

        if widget.isWindow():
            state.geometry = widget.geometry()
            state.flags = widget.windowFlags()
        return state

    def _child_states(
        self, parent: QtWidgets.QWidget | None = None
    ) -> tuple[WidgetState, ...]:
        """Return the states of all widgets in the window."""

        if parent is None:
            children = (self.center_splitter,)
        elif isinstance(parent, (Splitter, DockWidget)):
            children = (parent.widget(i) for i in range(parent.count()))
        else:
            return ()

        states = []
        for child in children:
            if isinstance(child, QtWidgets.QWidget):
                state = self._child_state(child)
                if state is not None:
                    states.append(state)
        return tuple(states)

    def _set_child_states(
        self,
        states: Sequence[WidgetState],
        widgets: dict[str, QtWidgets.QWidget],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """
        Set the States where `widgets` is a dictionary of existing widgets. Widgets
        used from this dictionary are removed to keep track of which ones have been
        re-parented.
        """

        if parent is None:
            parent = self

        for i, state in enumerate(states):
            widget = self._create_widget(state, widgets, parent)
            if widget is None:
                continue
            self._place_widget(parent, widget, i)
            self._apply_window_state(widget, state)

    def _create_widget(
        self,
        state: WidgetState,
        widgets: dict[str, QtWidgets.QWidget],
        parent: QtWidgets.QWidget,
    ) -> QtWidgets.QWidget | None:
        """Create the widget for a state and return it."""

        if isinstance(state, SplitterState):
            if parent == self:
                splitter = self.center_splitter
                splitter.setOrientation(state.orientation)
            else:
                splitter = Splitter(state.orientation)
            self._set_child_states(state.states, widgets, splitter)
            splitter.setSizes(state.sizes)
            return splitter

        if isinstance(state, DockWidgetState):
            return self._create_dock_widget(state, widgets)

        return None

    def _create_dock_widget(
        self,
        state: DockWidgetState,
        widgets: dict[str, QtWidgets.QWidget],
    ) -> DockWidget:
        """Create a dock widget with its tabs from a state."""

        if state.is_center_widget:
            dock_widget = self.center_widget
        else:
            dock_widget = DockWidget(self)
            dock_widget.detachable = state.detachable
            dock_widget.auto_delete = state.auto_delete

        for tab in state.widgets:
            widget = self._create_tab_widget(tab.title, tab.cls_name, widgets)
            if widget is None:
                continue
            unique_title = self._add_widget(widget, tab.title)
            dock_widget.addTab(widget, unique_title)

        dock_widget.setCurrentIndex(min(state.current_index, dock_widget.count() - 1))
        return dock_widget

    def _create_tab_widget(
        self,
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

        registered_widget = self._get_registered_widget(cls_name)
        if not registered_widget:
            return None

        if registered_widget.unique:
            values = self._widgets.values()
            if any(isinstance(value, registered_widget.cls) for value in values):
                return None

        return registered_widget.cls()

    @staticmethod
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

    @staticmethod
    def _apply_window_state(widget: QtWidgets.QWidget, state: WidgetState) -> None:
        """Restore floating geometry and window flags."""

        if state.flags:
            widget.setWindowFlags(state.flags)
            widget.setGeometry(state.geometry)
            widget.show()


def tab_states(widget: QtWidgets.QTabWidget) -> tuple[TabState, ...]:
    """Return the title and widget class name of each tab of a QTabWidget."""

    return tuple(
        TabState(widget.tabText(i), type(widget.widget(i)).__name__)
        for i in range(widget.count())
    )
