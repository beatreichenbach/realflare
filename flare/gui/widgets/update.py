from __future__ import annotations

from qtpy import QtWidgets


class UpdateDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
