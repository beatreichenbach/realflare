from functools import partial

from qt_material_icons import MaterialIcon
from qtpy import QtCore, QtGui, QtWidgets


class DockTabBar(QtWidgets.QTabBar):
    """A tab bar with close buttons that emits signals when a tab is dragged out."""

    detach_started: QtCore.Signal = QtCore.Signal(int)
    detach_moved: QtCore.Signal = QtCore.Signal()
    detach_finished: QtCore.Signal = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._drag_index: int | None = None
        self._detaching: bool = False

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
