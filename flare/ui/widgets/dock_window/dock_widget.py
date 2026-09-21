from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

from qtpy import QtCore, QtGui, QtWidgets

from .drag import DockDrag, active_drag, is_dock_drag
from .splitter import Splitter
from .tab_bar import DockTabBar

if TYPE_CHECKING:
    from .dock_window import DockWindow


def area_orientation(area: QtCore.Qt.DockWidgetArea) -> QtCore.Qt.Orientation:
    """Return an Orientation based on the DockWidgetArea."""

    if area in (
        QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
        QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
    ):
        return QtCore.Qt.Orientation.Horizontal
    else:
        return QtCore.Qt.Orientation.Vertical


class DockWidget(QtWidgets.QTabWidget):
    """A tabbed dock that can be docked, floated and detached by dragging."""

    dock_areas = (
        QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
        QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
        QtCore.Qt.DockWidgetArea.TopDockWidgetArea,
        QtCore.Qt.DockWidgetArea.BottomDockWidgetArea,
        QtCore.Qt.DockWidgetArea.NoDockWidgetArea,
    )

    def __init__(
        self, window: DockWindow, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent or window)

        self.dock_window: DockWindow = window
        self.detachable: bool = True
        self.auto_delete: bool = True

        self._init_ui()

    def _init_ui(self) -> None:
        tab_bar = DockTabBar()
        self.setTabBar(tab_bar)
        self.setMovable(True)
        self.setTabsClosable(True)
        self.setAcceptDrops(True)

        tab_bar.detach_started.connect(self._start_drag)

        self.tabCloseRequested.connect(self.close_tab)
        self.currentChanged.connect(self.update_window_title)

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
        self.move(x, y)  # NOTE: Does not work on wayland.

    def set_floating(self) -> None:
        """Make the widget a floating tool window."""

        self.setWindowFlag(QtCore.Qt.WindowType.Tool, True)

    def try_delete(self) -> None:
        """Delete the widget when it is empty and auto delete is enabled."""

        if self.auto_delete and not self.count():
            self.deleteLater()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if is_dock_drag(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if not is_dock_drag(event.mimeData()):
            event.ignore()
            return

        area = self.dock_area_at(event.position().toPoint())
        if area is None:
            self.dock_window.hide_dock_preview()
            event.ignore()
            return

        self.dock_window.show_dock_preview(self, area)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent) -> None:
        self.dock_window.hide_dock_preview()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        drag = active_drag()
        self.dock_window.hide_dock_preview()

        if drag is None:
            event.ignore()
            return

        area = self.dock_area_at(event.position().toPoint())
        if area is None:
            event.ignore()
            return

        event.acceptProposedAction()
        drag.drop(self, area)

    def add_dock_widget(
        self, dock_widget: DockWidget, area: QtCore.Qt.DockWidgetArea
    ) -> None:
        """Add a DockWidget to an area with a Splitter."""

        if area == QtCore.Qt.DockWidgetArea.NoDockWidgetArea:
            first = dock_widget.widget(0)
            if first is not None:
                self.addTab(first, dock_widget.tabText(0))
            return

        container = self._dock_container()
        if container is None:
            return

        container, index = self._orient_container(container, area)

        if area in (
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
            QtCore.Qt.DockWidgetArea.TopDockWidgetArea,
        ):
            container.insertWidget(index, dock_widget)
        elif area in (
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea,
        ):
            container.insertWidget(index + 1, dock_widget)

        # self._split_evenly(container, dock_widget)

    def _split_evenly(
        self, container: QtWidgets.QSplitter, dock_widget: DockWidget
    ) -> None:
        """Give this widget and a sibling an equal share of the splitter."""

        index = container.indexOf(self)
        other = container.indexOf(dock_widget)
        if index == -1 or other == -1:
            return

        sizes = container.sizes()
        total = sizes[index] + sizes[other]
        sizes[index] = total - total // 2
        sizes[other] = total // 2
        container.setSizes(sizes)

    def _dock_container(self) -> QtWidgets.QSplitter | None:
        """
        Return a Splitter that contains this widget, wrapping it in a new Splitter
        if it is not already inside one.
        """

        parent = self.parent()
        if not isinstance(parent, QtWidgets.QWidget):
            return None

        if not self.isWindow() and isinstance(parent, QtWidgets.QSplitter):
            return parent

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
            return None

        splitter.setGeometry(self.geometry())
        splitter.addWidget(self)
        return splitter

    def _orient_container(
        self, container: QtWidgets.QSplitter, area: QtCore.Qt.DockWidgetArea
    ) -> tuple[QtWidgets.QSplitter, int]:
        """
        Return a Splitter with an orientation that matches the area, wrapping this
        widget in a new Splitter if the orientation differs.
        """

        orientation = area_orientation(area)
        index = container.indexOf(self)
        if orientation != container.orientation():
            if container.count() == 1:
                container.setOrientation(orientation)
            else:
                splitter = Splitter(orientation)
                container.insertWidget(index, splitter)
                splitter.setParent(container)
                splitter.addWidget(self)
                container = splitter
                index = 0
        return container, index

    def close_tab(self, index: int) -> None:
        """Close the tab at an index and delete its widget."""

        widget = self.widget(index)
        self.removeTab(index)
        # Since widgets are stored in window._widgets, trigger garbage collection
        if widget is not None:
            widget.deleteLater()

    def update_window_title(self, index: int) -> None:
        """Update a floating window's title to the current tab."""

        if self.window() != self.dock_window:
            self.window().setWindowTitle(self.tabText(index))

    def dock_rects(self) -> dict[QtCore.Qt.DockWidgetArea, QtCore.QRect]:
        """Return the rect of each dock area."""

        return {area: self._dock_rect(area) for area in self.dock_areas}

    def dock_area_at(self, position: QtCore.QPoint) -> QtCore.Qt.DockWidgetArea | None:
        """Return the dock area at a local position, or None."""

        for area, rect in self.dock_rects().items():
            if rect.contains(position):
                return area
        return None

    def dock_preview_rect(self, area: QtCore.Qt.DockWidgetArea) -> QtCore.QRect:
        """Return the preview rect for a dock area while dragging."""

        return self._dock_rect(area, 0.5)

    def widgets(self) -> OrderedDict[str, QtWidgets.QWidget]:
        """Return a mapping of tab titles to their widgets."""

        widgets = OrderedDict()
        for i in range(self.count()):
            widgets[self.tabText(i)] = self.widget(i)
        return widgets

    def _start_drag(self, widget: QtWidgets.QWidget) -> None:
        """Start dragging a tab's widget."""

        index = self.indexOf(widget)
        if not self.detachable or index == -1:
            return

        drag = DockDrag(source=self, widget=widget, title=self.tabText(index))
        drag.start()

    def _dock_rect(
        self, area: QtCore.Qt.DockWidgetArea, scale: float = 0.2
    ) -> QtCore.QRect:
        """Return a scaled QRect for a dock area."""

        size = self.size() * scale
        rect = self.rect()
        if area in (
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
        ):
            rect.setWidth(size.width())
            if area == QtCore.Qt.DockWidgetArea.RightDockWidgetArea:
                rect.moveRight(self.rect().right())
        elif area in (
            QtCore.Qt.DockWidgetArea.TopDockWidgetArea,
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea,
        ):
            rect.setHeight(size.height())
            if area == QtCore.Qt.DockWidgetArea.BottomDockWidgetArea:
                rect.moveBottom(self.rect().bottom())
        return rect
