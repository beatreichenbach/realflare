from qtpy import QtCore, QtWidgets


class Splitter(QtWidgets.QSplitter):
    def childEvent(self, event: QtCore.QChildEvent) -> None:
        super().childEvent(event)
        if event.removed() and not self.count():
            self.deleteLater()
