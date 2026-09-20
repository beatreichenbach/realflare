from __future__ import annotations

import dataclasses
import logging
from collections import OrderedDict
from collections.abc import Sequence
from functools import partial
from typing import Union

from pydantic import BaseModel
from qt_material_icons import MaterialIcon
from qt_pydantic import QRect
from qtpy import QtCore, QtGui, QtWidgets

from flare import utils

logger = logging.getLogger(__name__)


WidgetSource = Union[str, type[QtWidgets.QWidget]]


@dataclasses.dataclass()
class RegisteredWidget:
    cls: type[QtWidgets.QWidget]
    name: str
    unique: bool = False


class DockWidgetState(BaseModel):
    current_index: int
    widgets: tuple[tuple[str, str], ...]
    detachable: bool
    auto_delete: bool
    is_center_widget: bool
    geometry: QRect = QtCore.QRect()
    flags: int = 0


class SplitterState(BaseModel):
    sizes: tuple[int, ...]
    orientation: QtCore.Qt.Orientation
    states: tuple[Union[DockWidgetState, SplitterState], ...]
    geometry: QRect = QtCore.QRect()
    flags: int = 0


class State(BaseModel):
    geometry: QRect = QtCore.QRect()
    states: tuple[Union[DockWidgetState, SplitterState], ...] = ()


class DockTabBar(QtWidgets.QTabBar):
    detach_started: QtCore.Signal = QtCore.Signal(int)
    detach_moved: QtCore.Signal = QtCore.Signal()
    detach_finished: QtCore.Signal = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._drag_index = None
        self._detaching = False

        self.tabBarClicked.connect(self._tab_bar_click)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._detaching:
            # Mouse is pressed down and a tab is detached
            self.detach_moved.emit()
        elif not self.rect().contains(event.pos()) and self._drag_index is not None:
            # A tab is about to be detached
            self.detach_started.emit(self._drag_index)
            self._detaching = True
        else:
            # No tab is detached
            # This must only be called when _detaching == False
            # undocking tabs while mouse move events are being processed leads to
            # crashes because of the tab's QPainter events
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        if self._detaching:
            self.detach_finished.emit()
        self._detaching = False
        self._drag_index = None

    def tabInserted(self, index: int) -> None:
        self._add_tab_close_button(index)

    def _add_tab_close_button(self, index: int) -> None:
        """Add a close button to a tab."""

        button = QtWidgets.QToolButton(self)
        button.setAutoRaise(True)
        size = self.style().pixelMetric(QtWidgets.QStyle.PixelMetric.PM_SmallIconSize)
        button.setMaximumSize(QtCore.QSize(size, size))
        icon = MaterialIcon('close')
        button.setIcon(icon)
        button.clicked.connect(partial(self._request_tab_close, button))
        self.setTabButton(index, QtWidgets.QTabBar.ButtonPosition.RightSide, button)

    def _request_tab_close(self, button: QtWidgets.QToolButton) -> None:
        for i in range(self.count()):
            tab_button = self.tabButton(i, QtWidgets.QTabBar.ButtonPosition.RightSide)
            if tab_button == button:
                self.tabCloseRequested.emit(i)
                return

    def _tab_bar_click(self, index: int) -> None:
        self._drag_index = index


class Splitter(QtWidgets.QSplitter):
    def childEvent(self, event: QtCore.QChildEvent) -> None:
        super().childEvent(event)
        if event.removed() and not self.count():
            self.deleteLater()


class DockWidget(QtWidgets.QTabWidget):
    dock_areas = (
        QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
        QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
        QtCore.Qt.DockWidgetArea.TopDockWidgetArea,
        QtCore.Qt.DockWidgetArea.BottomDockWidgetArea,
        QtCore.Qt.DockWidgetArea.NoDockWidgetArea,
    )

    def __init__(
        self, dock_window: DockWindow, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent or dock_window)

        self.dock_window = dock_window
        self.detachable = True
        self.auto_delete = True

        self._drag_widget = None
        self._hidden = False

        self._init_ui()

    def _init_ui(self) -> None:
        tab_bar = DockTabBar()
        self.setTabBar(tab_bar)
        self.setMovable(True)
        self.setTabsClosable(True)

        tab_bar.detach_started.connect(self._detach_start)
        tab_bar.detach_moved.connect(self._detach_move)
        tab_bar.detach_finished.connect(self._detach_finish)

        self.tabCloseRequested.connect(self.close_tab)
        self.currentChanged.connect(self.update_window_title)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # Since widgets are stored in window._widgets, trigger garbage collection
        for widget in self.widgets().values():
            widget.deleteLater()
        super().closeEvent(event)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        if self.isWindow():
            self.center()
        super().showEvent(event)

    def tabRemoved(self, index: int) -> None:
        self.try_delete()

    def center(self) -> None:
        """Center the widget in the middle of the window."""

        if not self.dock_window:
            return

        center = self.dock_window.geometry().center()
        x = center.x() - (self.width() // 2)
        y = center.y() - (self.height() // 2)
        self.move(x, y)

    def set_floating(self) -> None:
        self.setWindowFlag(QtCore.Qt.WindowType.Tool, True)

    def try_delete(self) -> None:
        """
        Attempt to delete the widget. If the widget is in a DragEvent, it gets hidden
        instead.
        """

        if self.auto_delete and not self.count():
            self._hidden = True
            if self._drag_widget:
                self._hide_recursively(self)
            else:
                self.deleteLater()

    def add_dock_widget(
        self, widget: QtWidgets.QTabWidget, area: QtCore.Qt.DockWidgetArea
    ) -> None:
        """Add a QTabWidget to an area with a Splitter."""

        if area == QtCore.Qt.DockWidgetArea.NoDockWidgetArea:
            first = widget.widget(0)
            if first is not None:
                self.addTab(first, widget.tabText(0))
        else:
            parent = self.parent()
            if not isinstance(parent, QtWidgets.QWidget):
                return

            if self.isWindow() or not isinstance(parent, QtWidgets.QSplitter):
                splitter = Splitter(QtCore.Qt.Orientation.Vertical)
                layout = parent.layout()
                if self.isWindow():
                    splitter.setParent(parent)
                    splitter.setWindowFlags(self.windowFlags())
                    splitter.show()
                elif isinstance(parent, QtWidgets.QScrollArea):
                    parent.setWidget(splitter)
                elif isinstance(layout, QtWidgets.QLayout):
                    layout.replaceWidget(self, splitter)
                    splitter.setParent(parent)
                else:
                    # For other parents it's unknown on how to replace a widget
                    splitter.deleteLater()
                    return

                splitter.setGeometry(self.geometry())
                splitter.addWidget(self)
                parent = splitter

            orientation = area_orientation(area)
            index = parent.indexOf(self)
            if orientation != parent.orientation():
                if parent.count() == 1:
                    parent.setOrientation(orientation)
                else:
                    splitter = Splitter(orientation)
                    parent.insertWidget(index, splitter)
                    splitter.setParent(parent)
                    splitter.addWidget(self)
                    parent = splitter
                    index = 0

            if area in (
                QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
                QtCore.Qt.DockWidgetArea.TopDockWidgetArea,
            ):
                parent.insertWidget(index, widget)
            elif area in (
                QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
                QtCore.Qt.DockWidgetArea.BottomDockWidgetArea,
            ):
                parent.insertWidget(index + 1, widget)

    def close_tab(self, index: int) -> None:
        widget = self.widget(index)
        self.removeTab(index)
        # Since widgets are stored in window._widgets, trigger garbage collection
        if widget is not None:
            widget.deleteLater()

    def detach(self, index: int, interactive: bool = False) -> None:
        if index not in range(self.count()) or not self.detachable:
            return

        geometry = self.geometry()

        if not self.isWindow():
            parent = self.parent()
            if isinstance(parent, QtWidgets.QWidget):
                top_left = parent.mapToGlobal(geometry.topLeft())
                geometry.moveTopLeft(top_left)

        title = self.tabText(index)
        widget = self.widget(index)
        if widget is None:
            return

        self._drag_widget = self.__class__(self.dock_window)
        self._drag_widget.setParent(self.dock_window)
        # Setting WindowFlags after parenting creates a window
        self._drag_widget.set_floating()
        # Adding a tab after setting the WindowFlags triggers window title update
        self._drag_widget.addTab(widget, title)
        self._drag_widget.setGeometry(geometry)
        if interactive:
            self._drag_widget.setWindowOpacity(0.5)
        self._drag_widget.raise_()
        self._drag_widget.show()
        self._drag_widget.activateWindow()

    def update_window_title(self, index: int) -> None:
        if self.window() != self.dock_window:
            self.window().setWindowTitle(self.tabText(index))

    def dock_rects(self) -> dict[QtCore.Qt.DockWidgetArea, QtCore.QRect]:
        if not self._hidden:
            rects = {area: self._dock_rect(area) for area in self.dock_areas}
        else:
            rects = {}
        return rects

    def dock_preview_rect(self, area: QtCore.Qt.DockWidgetArea) -> QtCore.QRect:
        return self._dock_rect(area, 0.5)

    def widgets(self) -> OrderedDict[str, QtWidgets.QWidget]:
        widgets = OrderedDict()
        for i in range(self.count()):
            widgets[self.tabText(i)] = self.widget(i)
        return widgets

    def _detach_start(self, index: int) -> None:
        self.detach(index, interactive=True)

    def _detach_move(self) -> None:
        if self._drag_widget:
            position = QtGui.QCursor().pos()
            height = self.style().pixelMetric(
                QtWidgets.QStyle.PixelMetric.PM_TitleBarHeight
            )
            offset = position - QtCore.QPoint(int(height / 2), int(height / 2))
            self._drag_widget.move(offset)
            self.dock_window.add_dock_widget(self._drag_widget, position, True)

    def _detach_finish(self) -> None:
        if self._drag_widget:
            self._drag_widget.setWindowOpacity(1)
            position = QtGui.QCursor().pos()
            self.dock_window.add_dock_widget(self._drag_widget, position)
        self._drag_widget = None
        self.try_delete()

    def _dock_rect(
        self, area: QtCore.Qt.DockWidgetArea, scale: float = 0.2
    ) -> QtCore.QRect:
        """Return a scaled QRect for an area."""

        size = self.size() * scale
        rect = self.rect()
        if area == QtCore.Qt.DockWidgetArea.LeftDockWidgetArea:
            rect.setWidth(size.width())
            return rect
        elif area == QtCore.Qt.DockWidgetArea.RightDockWidgetArea:
            right = rect.right()
            rect.setWidth(size.width())
            rect.moveRight(right)
            return rect
        elif area == QtCore.Qt.DockWidgetArea.TopDockWidgetArea:
            rect.setHeight(size.height())
            return rect
        elif area == QtCore.Qt.DockWidgetArea.BottomDockWidgetArea:
            bottom = rect.bottom()
            rect.setHeight(size.height())
            rect.moveBottom(bottom)
            return rect
        elif area == QtCore.Qt.DockWidgetArea.NoDockWidgetArea:
            return rect
        return rect

    def _hide_recursively(self, widget: QtWidgets.QWidget) -> None:
        """Hide the top most widget without deleting it."""

        if widget.isWindow():
            widget.setWindowOpacity(0)
        else:
            parent = widget.parent()
            if isinstance(parent, Splitter) and parent.count() == 1:
                # If the Splitter's only child is self, make it invisible
                self._hide_recursively(parent)
            elif parent:
                # If there are other children, it's safe to hide the Splitter won't
                # auto delete.
                widget.hide()


class DockWindow(QtWidgets.QWidget):
    """
    Provides a customizable, dockable window for organizing QWidgets.
    - The layout of the window consists of nested Splitters.
    - Each Splitter can have multiple DockWidgets.
    - Each DockWidget can have multiple tabs with any QWidgets.
    Any widget class can be registered with the DockWindow to allow creation of those
    widgets.
    """

    widget_added: QtCore.Signal = QtCore.Signal(QtWidgets.QWidget)
    dock_widget_added: QtCore.Signal = QtCore.Signal(DockWidget)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._registered_widgets: list[RegisteredWidget] = []
        self._widgets: dict[str, QtWidgets.QWidget] = {}

        self._init_placeholder()
        self._init_ui()

    def _init_placeholder(self) -> None:
        self._placeholder = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Shape.Rectangle)
        self._placeholder.setParent(self)
        self._placeholder.destroyed.connect(self._init_placeholder)

    def _init_ui(self) -> None:
        self._layout = QtWidgets.QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(QtCore.QMargins())
        self._layout.setSpacing(0)

        # Add a protected DockWidget as the center widget
        self.center_widget = DockWidget(self, self)
        self.center_widget.auto_delete = False
        self.center_splitter = Splitter(QtCore.Qt.Orientation.Vertical)
        self.center_splitter.addWidget(self.center_widget)
        self.center_splitter.setCollapsible(self.center_splitter.count() - 1, False)
        self._layout.addWidget(self.center_splitter)

        self._layout.setStretch(0, 1)

    def register_widget(
        self, cls: type[QtWidgets.QWidget], name: str = '', unique: bool = False
    ) -> RegisteredWidget:
        """
        Register a widget class and return it. If `unique` is true, only one widget of
        this class can exist in the window.

        :raises ValueError: If a widget with `name` is already registered.
        """

        name = name or cls.__name__

        if name in (w.name for w in self._registered_widgets):
            raise ValueError(f'widget {name!r} is already registered')

        registered_widget = RegisteredWidget(cls=cls, name=name, unique=unique)
        self._registered_widgets.append(registered_widget)
        return registered_widget

    def unregister_widget(self, source: WidgetSource) -> None:
        """Unregister the widget class."""

        if registered_widget := self._get_registered_widget(source):
            self._registered_widgets.remove(registered_widget)

    def registered_widgets(self) -> tuple[RegisteredWidget, ...]:
        return tuple(self._registered_widgets)

    def show_widget(self, source: WidgetSource) -> None:
        """Show a DockWidget. If necessary, create a DockWidget."""

        registered_widget = self._get_registered_widget(source)

        if not registered_widget:
            logger.warning(f'{source!r} is not a registered widget.')
            return

        if registered_widget.unique:
            for widget in self._widgets.values():
                if isinstance(widget, registered_widget.cls):
                    focus_widget(widget)
                    return

        # Create the widget
        widget = registered_widget.cls()
        title = self._add_widget(widget, registered_widget.name)

        # Create the DockWidget
        dock_widget = DockWidget(dock_window=self)
        dock_widget.addTab(widget, title)
        dock_widget.resize(widget.size())
        dock_widget.set_floating()
        dock_widget.show()
        self.dock_widget_added.emit(dock_widget)

    def add_dock_widget(
        self, dock_widget: DockWidget, position: QtCore.QPoint, simulate: bool = False
    ) -> None:
        """
        Add a DockWidget at a global position. If `simulate` is true, a placeholder
        is shown where the widget would get docked.
        """

        dock_rects = self._dock_rects()

        for target, rects in dock_rects.items():
            if target == dock_widget:
                continue
            target_position = target.mapFromGlobal(position)
            if not target.rect().contains(target_position):
                self._placeholder.hide()
                continue

            for area, rect in rects.items():
                if rect.contains(target_position):
                    if simulate:
                        preview_rect = target.dock_preview_rect(area)
                        self._placeholder.setParent(target)
                        self._placeholder.setGeometry(preview_rect)
                        self._placeholder.show()
                    else:
                        self._placeholder.hide()
                        target.add_dock_widget(dock_widget, area)
                    return
                else:
                    self._placeholder.hide()

    def dock_widgets(self) -> tuple[DockWidget, ...]:
        """
        Return all DockWidgets of this window. They are sorted in a manner that
        makes sense for checking dock areas.
        - Floating widgets are always in front
        - List deepest nested children first
        """

        children = self.findChildren(DockWidget)
        children = sorted(children, key=lambda w: w.isWindow())
        children = reversed(children)
        return tuple(children)

    def state(self) -> dict:
        state = State(
            geometry=self.geometry(),
            states=self._child_states(),
        )
        data = state.model_dump()
        return data

    def set_state(self, state: dict) -> None:
        window_state = State.model_validate(state)

        geometry = window_state.geometry
        if geometry.width() > 0 and geometry.height() > 0:
            self.setGeometry(geometry)

        # Unparent all widgets to clean up layout
        for widget in self._widgets.values():
            widget.setParent(None)
            widget.close()

        widgets = dict(self._widgets)
        self._set_child_states(window_state.states, widgets)

        # Remove unused widgets
        for title, widget in widgets.items():
            widget.deleteLater()

    def _child_state(
        self, widget: QtWidgets.QWidget
    ) -> SplitterState | DockWidgetState | None:
        """Return the state of a widget in the window."""

        if isinstance(widget, Splitter):
            state = SplitterState(
                sizes=tuple(widget.sizes()),
                orientation=widget.orientation(),
                states=self._child_states(widget),
            )
        elif isinstance(widget, DockWidget):
            widgets = tab_widget_classes(widget)
            state = DockWidgetState(
                current_index=widget.currentIndex(),
                widgets=widgets,
                detachable=widget.detachable,
                auto_delete=widget.auto_delete,
                is_center_widget=(widget == self.center_widget),
            )
        else:
            return None

        if widget.isWindow():
            state.geometry = widget.geometry()
            state.flags = int(widget.windowFlags())
        return state

    def _child_states(
        self, parent: QtWidgets.QWidget | None = None
    ) -> tuple[SplitterState | DockWidgetState, ...]:
        """Return the states of all widgets in the window."""

        if parent is None:
            children = self.children()
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
        states: Sequence[SplitterState | DockWidgetState],
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
            # Create widget
            if isinstance(state, SplitterState):
                if parent == self:
                    splitter = self.center_splitter
                    splitter.setOrientation(state.orientation)
                else:
                    splitter = Splitter(state.orientation)
                self._set_child_states(
                    states=state.states, widgets=widgets, parent=splitter
                )
                splitter.setSizes(state.sizes)
                widget = splitter

            elif isinstance(state, DockWidgetState):
                if state.is_center_widget:
                    dock_widget = self.center_widget
                else:
                    dock_widget = DockWidget(self)
                    dock_widget.detachable = state.detachable
                    dock_widget.auto_delete = state.auto_delete

                for title, cls_name in state.widgets:
                    widget = widgets.pop(title, None)
                    if widget is None:
                        # Silently skip unregistered widgets
                        registered_widget = self._get_registered_widget(cls_name)
                        if not registered_widget:
                            continue
                        # Silently duplicate unique widgets
                        if registered_widget.unique:
                            widget_values = self._widgets.values()
                            if widget in widget_values:
                                continue
                        widget = registered_widget.cls()

                    unique_title = self._add_widget(widget, title)
                    dock_widget.addTab(widget, unique_title)

                dock_widget.setCurrentIndex(state.current_index)

                widget = dock_widget
            else:
                continue

            # Parent widget
            if isinstance(parent, Splitter):
                if parent.widget(i) is not None:
                    # Not replacing the widget with itself prevents warnings
                    if parent.widget(i) != widget:
                        parent.replaceWidget(i, widget)
                        widget.setParent(parent)
                        widget.show()
                else:
                    parent.addWidget(widget)
            else:
                widget.show()

            # Set window
            if state.flags:
                flags = QtCore.Qt.WindowType(state.flags)
                widget.setWindowFlags(flags)
                widget.setGeometry(state.geometry)
                widget.show()

    def _add_widget(self, widget: QtWidgets.QWidget, title: str) -> str:
        """Add a widget to this window and return its unique title."""

        # Remove existing entries
        if widget in self._widgets.values():
            self._widgets = {t: w for t, w in self._widgets.items() if w != widget}
            new = False
        else:
            new = True

        # Get a unique title
        titles = list(self._widgets.keys())
        title = utils.unique_name(title, titles)

        # Add widget
        self._widgets[title] = widget

        # Emit the signal after the widget has been added.
        if new:
            widget.destroyed.connect(self._object_destroyed)
            self.widget_added.emit(widget)

        return title

    def _get_registered_widget(self, source: WidgetSource) -> RegisteredWidget | None:
        """Return the RegisteredWidget for a source."""

        for registered_widget in self._registered_widgets:
            if source in (
                registered_widget.name,
                registered_widget.cls,
                registered_widget.cls.__name__,
            ):
                return registered_widget
        return None

    def _object_destroyed(self, obj: QtCore.QObject) -> None:
        """
        Handle destroyed widgets.
        The destroyed signal is emitted from the QObject when `obj` is no longer a
        QWidget.
        """

        self._widgets = {t: w for t, w in self._widgets.items() if w != obj}

    def _dock_rects(
        self,
    ) -> OrderedDict[DockWidget, dict[QtCore.Qt.DockWidgetArea, QtCore.QRect]]:
        rects = OrderedDict()
        widgets = self.dock_widgets()
        for widget in widgets:
            rects[widget] = widget.dock_rects()
        return rects


def area_orientation(area: QtCore.Qt.DockWidgetArea) -> QtCore.Qt.Orientation:
    """Return an Orientation based on the DockWidgetArea."""

    if area in (
        QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
        QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
    ):
        return QtCore.Qt.Orientation.Horizontal
    else:
        return QtCore.Qt.Orientation.Vertical


def tab_widget_classes(widget: QtWidgets.QTabWidget) -> tuple[tuple[str, str], ...]:
    """Return a tuple (title, class name) for QTabWidgets."""

    widgets = []
    for i in range(widget.count()):
        widgets.append((widget.tabText(i), type(widget.widget(i)).__name__))
    return tuple(widgets)


def focus_widget(widget: QtWidgets.QWidget) -> None:
    """Focus and bring a widget to the front."""

    # Switch to the tab
    parent = widget.parent()
    while parent is not None:
        if isinstance(parent, QtWidgets.QTabWidget):
            index = parent.indexOf(widget)
            parent.setCurrentIndex(index)
            break
        parent = parent.parent()

    # Bring the window to the front
    window = widget.window()
    if window.windowState() & QtCore.Qt.WindowState.WindowMinimized:
        window.setWindowState(QtCore.Qt.WindowState.WindowActive)
    window.raise_()  # for macOS
    window.activateWindow()  # for Windows
