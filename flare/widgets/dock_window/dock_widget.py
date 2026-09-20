from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

from qtpy import QtCore, QtGui, QtWidgets

from .splitter import Splitter
from .tab_bar import DockTabBar
from .utils import area_orientation, set_window_opacity, supports_window_opacity

if TYPE_CHECKING:
    from .dock_window import DockWindow


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
            return

        container = self._dock_container()
        if container is None:
            return

        container, index = self._orient_container(container, area)

        if area in (
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
            QtCore.Qt.DockWidgetArea.TopDockWidgetArea,
        ):
            container.insertWidget(index, widget)
        elif area in (
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea,
        ):
            container.insertWidget(index + 1, widget)

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
            set_window_opacity(self._drag_widget, 0.5)
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
            set_window_opacity(self._drag_widget, 1)
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
            if supports_window_opacity():
                widget.setWindowOpacity(0)
            else:
                # TODO: unsupported opacity might be a problem because the splitter will
                #  auto delete
                widget.hide()
        else:
            parent = widget.parent()
            if isinstance(parent, Splitter) and parent.count() == 1:
                # If the Splitter's only child is self, make it invisible
                self._hide_recursively(parent)
            elif parent:
                # If there are other children, it's safe to hide the Splitter won't
                # auto delete.
                widget.hide()
