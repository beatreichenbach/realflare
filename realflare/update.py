import logging
import sys

from PySide2 import QtWidgets, QtGui, QtCore

from qt_extensions.button import Button
from qt_extensions.logger import LogViewer, LogCache
from realflare.utils.processing import Process, popen


class UpdateProcess(Process):
    def run(self) -> None:

        args = [
            sys.executable,
            '-m',
            'pip',
            'install',
            '--upgrade',
            'realflare@https://github.com/beatreichenbach/realflare/archive/refs/heads/main.zip',
        ]
        self.popen(args)


class UpdateDialog(LogViewer):
    started: QtCore.Signal = QtCore.Signal()

    def __init__(
        self, cache: LogCache | None = None, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(cache, parent)

        # force Dialog class
        self.setWindowFlag(QtCore.Qt.Dialog)
        self.setWindowTitle('Update')
        self.resize(QtCore.QSize(800, 600))

        # logger
        self.formatter = logging.Formatter(
            fmt='{message}',
            datefmt='%I:%M:%S%p',
            style='{',
            defaults={'color': ''},
        )
        self.set_levels((logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG))

        # update process
        self.process = UpdateProcess()
        self.process.log_changed.connect(self.update_log)

        self.process_thread = QtCore.QThread()
        self.process_thread.start()
        self.process.moveToThread(self.process_thread)
        self.started.connect(self.process.start)
        self.process.finished.connect(self.finish)

        self.started.emit()

    def _init_ui(self) -> None:
        super()._init_ui()
        self.toolbar.setVisible(False)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        self.layout().addLayout(button_layout)

        self.restart_button = Button('Restart', color='primary')
        self.restart_button.setEnabled(False)
        self.restart_button.pressed.connect(restart)
        button_layout.addWidget(self.restart_button)

        self.close_button = Button('Close')
        self.close_button.setEnabled(False)
        self.close_button.pressed.connect(self.close)
        button_layout.addWidget(self.close_button)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.process_thread.quit()
        self.process_thread.wait()
        super().closeEvent(event)

    def finish(self) -> None:
        self.restart_button.setEnabled(True)
        self.close_button.setEnabled(True)

    def start(self) -> None:
        self.started.emit()

    def update_log(self, record: logging.LogRecord) -> None:
        self.add_record(record)

    def exec_(self):
        self.setWindowModality(QtGui.Qt.ApplicationModal)
        self.show()


def restart() -> None:
    app = QtWidgets.QApplication.instance()
    app.closeAllWindows()
    popen([sys.executable, *sys.argv])
