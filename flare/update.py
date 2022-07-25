import logging
import sys

from PySide2 import QtWidgets, QtGui, QtCore

from flare.utils.processing import Process, popen


class UpdateProcess(Process):
    def run(self) -> None:
        args = [
            'pip',
            'install',
            '--upgrade',
            'flare@https://github.com/beatreichenbach/realflare/archive/refs/heads/main.zip',
        ]
        self.popen(args)


class UpdateDialog(QtWidgets.QDialog):
    started: QtCore.Signal = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle('Update')

        self._init_ui()

        self.process = UpdateProcess()
        self.process.log_changed.connect(self.update_log)

        self.process_thread = QtCore.QThread()
        self.process_thread.start()
        self.process.moveToThread(self.process_thread)
        self.started.connect(self.process.start)
        self.process.finished.connect(self.finish)

        self.started.emit()

    def _init_ui(self) -> None:
        self.setLayout(QtWidgets.QVBoxLayout())

        self.text_edit = QtWidgets.QTextEdit()
        self.text_edit.setReadOnly(True)
        font = QtGui.QFont('Monospace')
        font.setStyleHint(QtGui.QFont.Monospace)
        self.text_edit.setFont(font)
        self.layout().addWidget(self.text_edit)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        self.layout().addLayout(button_layout)

        self.restart_button = QtWidgets.QPushButton('Restart')
        self.restart_button.setEnabled(False)
        self.restart_button.pressed.connect(self.restart)
        button_layout.addWidget(self.restart_button)

        self.close_button = QtWidgets.QPushButton('Close')
        self.close_button.setEnabled(False)
        self.close_button.pressed.connect(self.close)
        button_layout.addWidget(self.close_button)

        self.window_text_color = self.text_edit.palette().color(
            QtGui.QPalette.WindowText
        )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.process_thread.quit()
        self.process_thread.wait()
        super().closeEvent(event)

    def finish(self) -> None:
        self.restart_button.setEnabled(True)
        self.close_button.setEnabled(True)

    def restart(self) -> None:
        app = QtWidgets.QApplication.instance()
        app.closeAllWindows()
        popen([sys.executable, *sys.argv])

    def start(self) -> None:
        self.started.emit()

    def update_log(self, record: logging.LogRecord) -> None:
        if record.levelno > logging.INFO:
            self.text_edit.setTextColor(QtGui.QColor('red'))
        self.text_edit.insertPlainText(record.getMessage().strip() + '\n')
        self.text_edit.setTextColor(self.window_text_color)
        self.text_edit.ensureCursorVisible()


def main():
    app = QtWidgets.QApplication(sys.argv)

    dialog = UpdateDialog()
    dialog.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    main()
