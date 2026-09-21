from __future__ import annotations

import dataclasses
import logging
from collections import OrderedDict
from functools import partial

from qtpy import QtCore, QtGui, QtWidgets

from flare import utils

from .dock_widget import DockWidget
from .splitter import Splitter

logger = logging.getLogger(__name__)

WidgetSource = str | type[QtWidgets.QWidget]


@dataclasses.dataclass()
class RegisteredWidget:
    cls: type[QtWidgets.QWidget]
    name: str
    unique: bool = False


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

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Close floating dock widgets when the window closes."""

        for dock_widget in self.dock_widgets():
            if dock_widget.isWindow():
                dock_widget.close()
        super().closeEvent(event)

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

    def _add_widget(self, widget: QtWidgets.QWidget, title: str) -> str:
        """Add a widget to this window and return its unique title."""

        # Remove existing entries
        if widget in self._widgets.values():
            self._widgets = {t: w for t, w in self._widgets.items() if w is not widget}
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
            widget.destroyed.connect(partial(self._object_destroyed, widget))
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

    def _object_destroyed(self, widget: QtWidgets.QWidget, _obj: object = None) -> None:
        """
        Remove a destroyed widget from the registry.

        The widget is captured by the connection because the `destroyed` signal
        passes a different wrapper for the same object.
        """

        self._widgets = {t: w for t, w in self._widgets.items() if w is not widget}

    def _dock_rects(
        self,
    ) -> OrderedDict[DockWidget, dict[QtCore.Qt.DockWidgetArea, QtCore.QRect]]:
        rects = OrderedDict()
        widgets = self.dock_widgets()
        for widget in widgets:
            rects[widget] = widget.dock_rects()
        return rects


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
