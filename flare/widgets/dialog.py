from qtpy import QtGui, QtWidgets


class DialogButtonBox(QtWidgets.QDialogButtonBox):
    """QDialogButtonBox without the default icons."""

    def setStandardButtons(
        self, buttons: QtWidgets.QDialogButtonBox.StandardButton
    ) -> None:
        super().setStandardButtons(buttons)
        for button in self.buttons():
            button.setIcon(QtGui.QIcon())

    def addButton(self, *args, **kwargs) -> QtWidgets.QPushButton:
        # Handle all overloaded methods
        button = super().addButton(*args, **kwargs)  # noqa
        if isinstance(button, QtWidgets.QPushButton):
            button.setIcon(QtGui.QIcon())
        return button
