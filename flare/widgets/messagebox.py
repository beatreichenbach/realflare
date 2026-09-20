import qt_themes
from qt_material_icons import MaterialIcon
from qtpy import QtGui, QtWidgets

StandardButton = QtWidgets.QMessageBox.StandardButton


class MessageBox(QtWidgets.QMessageBox):
    """Message with Material icons, colors and no icons on buttons."""

    def setStandardButtons(self, buttons: StandardButton) -> None:
        super().setStandardButtons(buttons)
        for button in self.buttons():
            button.setIcon(QtGui.QIcon())

    @staticmethod
    def critical(
        parent: QtWidgets.QWidget | None,
        title: str,
        text: str,
        buttons: StandardButton = StandardButton.Ok,
        defaultButton: StandardButton = StandardButton.NoButton,
    ) -> StandardButton:
        icon = MaterialIcon('error')
        theme = qt_themes.get_theme()
        color = theme.red if theme else QtGui.QColor('#ff1744')
        return MessageBox.message(
            parent, title, text, buttons, defaultButton, icon, color
        )

    @staticmethod
    def information(
        parent: QtWidgets.QWidget | None,
        title: str,
        text: str,
        buttons: StandardButton = StandardButton.Ok,
        defaultButton: StandardButton = StandardButton.NoButton,
    ) -> StandardButton:
        icon = MaterialIcon('info')
        return MessageBox.message(parent, title, text, buttons, defaultButton, icon)

    @staticmethod
    def question(
        parent: QtWidgets.QWidget | None,
        title: str,
        text: str,
        buttons: StandardButton = StandardButton.Yes | StandardButton.No,
        defaultButton: StandardButton = StandardButton.NoButton,
    ) -> StandardButton:
        icon = MaterialIcon('help')
        return MessageBox.message(parent, title, text, buttons, defaultButton, icon)

    @staticmethod
    def warning(
        parent: QtWidgets.QWidget | None,
        title: str,
        text: str,
        buttons: StandardButton = StandardButton.Ok,
        defaultButton: StandardButton = StandardButton.NoButton,
    ) -> StandardButton:
        icon = MaterialIcon('warning')
        return MessageBox.message(parent, title, text, buttons, defaultButton, icon)

    @staticmethod
    def message(
        parent: QtWidgets.QWidget | None,
        title: str,
        text: str,
        buttons: StandardButton = StandardButton.Ok,
        default_button: StandardButton = StandardButton.NoButton,
        icon: MaterialIcon | None = None,
        color: QtGui.QColor | None = None,
    ) -> StandardButton:
        message_box = MessageBox(parent)
        message_box.setWindowTitle(title)
        message_box.setText(text)
        message_box.setStandardButtons(buttons)
        message_box.setDefaultButton(default_button)
        if icon:
            style = QtWidgets.QApplication.style() if parent is None else parent.style()
            size = style.pixelMetric(QtWidgets.QStyle.PixelMetric.PM_MessageBoxIconSize)
            pixmap = icon.pixmap(size, color=color)
            message_box.setIconPixmap(pixmap)
        message_box.exec()
        return StandardButton(message_box.result())
