from functools import partial

from qt_material_icons import MaterialIcon
from qtpy import QtCore, QtGui, QtWidgets


class DockTabBar(QtWidgets.QTabBar):
    """A tab bar with close buttons that emits a signal when a tab is dragged out."""

    detach_started: QtCore.Signal = QtCore.Signal(QtWidgets.QWidget)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._drag_index: int | None = None
        self._drag_widget: QtWidgets.QWidget | None = None

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_index = self.tabAt(event.position().toPoint())
        self._drag_widget = self._widget_at(self._drag_index)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        position = event.position().toPoint()
        if self._drag_widget is not None and not self.rect().contains(position):
            widget = self._drag_widget
            self._drag_index = None
            self._drag_widget = None
            # Finish the tab bar's own move so it does not get stuck when the
            # external drag takes over the mouse.
            self._finish_move(event)
            self.detach_started.emit(widget)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_index = None
        self._drag_widget = None
        super().mouseReleaseEvent(event)

    def tabInserted(self, index: int) -> None:
        self._add_tab_close_button(index)

    def _finish_move(self, event: QtGui.QMouseEvent) -> None:
        """Finish the tab bar's internal move with a synthetic release."""

        release = QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseButtonRelease,
            event.position(),
            event.globalPosition(),
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.MouseButton.NoButton,
            event.modifiers(),
        )
        super().mouseReleaseEvent(release)

    def _widget_at(self, index: int) -> QtWidgets.QWidget | None:
        parent = self.parentWidget()
        if isinstance(parent, QtWidgets.QTabWidget) and index >= 0:
            return parent.widget(index)
        return None

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
