from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from qtpy import QtCore, QtGui, QtWidgets

from .utils import activate_window

if TYPE_CHECKING:
    from .dock_widget import DockWidget

MIME_TYPE = 'application/x-flare-dock-tab'

_active_drag: DockDrag | None = None
logger = logging.getLogger(__name__)


def active_drag() -> DockDrag | None:
    """Return the dock drag that is currently in progress."""

    return _active_drag


def is_dock_drag(mime: QtCore.QMimeData) -> bool:
    """Return whether mime data belongs to a dock drag."""

    return mime.hasFormat(MIME_TYPE)


@dataclasses.dataclass
class DockDrag:
    """A tab being dragged from one dock widget to another or to float."""

    source: DockWidget
    widget: QtWidgets.QWidget
    title: str

    def start(self) -> QtCore.Qt.DropAction:
        """Run the drag, floating the tab if it is not dropped on a dock area."""

        global _active_drag
        _active_drag = self
        dock_window = self.source.dock_window

        try:
            drag = QtGui.QDrag(dock_window)
            mime = QtCore.QMimeData()
            mime.setData(MIME_TYPE, b'')
            drag.setMimeData(mime)
            pixmap = self._pixmap()
            drag.setPixmap(pixmap)
            drag.setHotSpot(pixmap.rect().center())
            action = drag.exec(QtCore.Qt.DropAction.MoveAction)
        finally:
            dock_window.hide_dock_preview()
            _active_drag = None

        if action != QtCore.Qt.DropAction.MoveAction:
            self.float()
        return action

    def drop(self, target: DockWidget, area: QtCore.Qt.DockWidgetArea) -> None:
        """Dock the tab on a target dock widget in an area."""

        no_dock = QtCore.Qt.DockWidgetArea.NoDockWidgetArea
        if target is self.source and area == no_dock:
            return

        self._remove()
        if area == no_dock:
            target.addTab(self.widget, self.title)
            return

        dock_widget = target.__class__(target.dock_window)
        dock_widget.addTab(self.widget, self.title)
        target.add_dock_widget(dock_widget, area)
        dock_widget.show()

    def float(self) -> None:
        """Detach the tab into a new floating window."""

        dock_window = self.source.dock_window
        dock_widget_cls = self.source.__class__

        self._remove()
        dock_widget = dock_widget_cls(dock_window)
        dock_widget.addTab(self.widget, self.title)
        dock_widget.resize(self.widget.size())
        dock_widget.set_floating()
        dock_widget.move(QtGui.QCursor.pos())  # NOTE: Does not work on wayland.
        activate_window(dock_widget)

    def _remove(self) -> None:
        index = self.source.indexOf(self.widget)
        if index != -1:
            self.source.removeTab(index)

    def _pixmap(self) -> QtGui.QPixmap:
        """Return the widget rendered with a palette-colored frame."""

        pixmap = self.widget.grab()
        if pixmap.isNull():
            return pixmap

        color = self.widget.palette().color(QtGui.QPalette.ColorRole.Base)
        painter = QtGui.QPainter(pixmap)
        painter.setPen(QtGui.QPen(color, 1))
        painter.drawRect(pixmap.rect().adjusted(1, 1, -1, -1))
        painter.end()
        return pixmap
