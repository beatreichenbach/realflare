from qtpy import QtCore, QtWidgets


class Splitter(QtWidgets.QSplitter):
    """A splitter that deletes itself when its last child is removed."""

    def childEvent(self, event: QtCore.QChildEvent) -> None:
        super().childEvent(event)
        if event.removed() and not self.count():
            self.deleteLater()
