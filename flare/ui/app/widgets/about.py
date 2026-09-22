import importlib.resources

from qt_material_icons import MaterialIcon
from qtpy import QtCore, QtGui, QtWidgets

import flare
from flare import constants
from flare.services import environment_report


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle('About')
        self.resize(720, 560)

        self._icon_copy = MaterialIcon('content_copy')
        self._icon_check = MaterialIcon('check')

        layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QHBoxLayout()
        layout.addLayout(header)

        icon_path = (
            importlib.resources.files(flare.__name__)
            .joinpath('assets')
            .joinpath('icon.png')
        )
        pixmap = QtGui.QPixmap(str(icon_path))
        scaled_pixmap = pixmap.scaled(
            48,
            48,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        icon = QtWidgets.QLabel()
        icon.setPixmap(scaled_pixmap)
        icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        header.addWidget(icon)

        title = QtWidgets.QLabel(f'{constants.NAME} {flare.__version__}')
        font = title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 4)
        title.setFont(font)
        title.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft
        )
        header.addWidget(title)
        header.addStretch()

        # Report
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setFont(
            QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        )
        self.text.setPlainText(environment_report())
        layout.addWidget(self.text, 1)

        # Buttons
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        layout.addLayout(buttons)

        self.copy_button = QtWidgets.QPushButton('Copy')
        self.copy_button.setIcon(self._icon_copy)
        self.copy_button.setToolTip('Copy the report to the clipboard')
        self.copy_button.clicked.connect(self._copy)
        buttons.addWidget(self.copy_button)

        close_button = QtWidgets.QPushButton('Close')
        close_button.setDefault(True)
        close_button.clicked.connect(self.close)
        buttons.addWidget(close_button)

    def _copy(self) -> None:
        """Copy the report to the clipboard and confirm it on the button."""

        QtWidgets.QApplication.clipboard().setText(self.text.toPlainText())
        self.copy_button.setIcon(self._icon_check)
        QtCore.QTimer.singleShot(2000, self._reset_copy_icon)

    def _reset_copy_icon(self) -> None:
        self.copy_button.setIcon(self._icon_copy)
