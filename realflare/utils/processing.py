from __future__ import annotations
import logging
import os
import subprocess
import typing
from io import StringIO

from PySide2 import QtCore


def popen(args: list[str]) -> subprocess.Popen:
    # hide console window on windows
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        startupinfo=startupinfo,
        text=True,
    )

    return process


class Process(QtCore.QObject):
    started: QtCore.Signal = QtCore.Signal()
    finished: QtCore.Signal = QtCore.Signal()
    log_changed: QtCore.Signal = QtCore.Signal(logging.LogRecord)

    def __init__(self) -> None:
        super().__init__()

        self.logger = logging.getLogger(str(hash(self)))
        self.logger.propagate = False
        self.log_handler = ProcessStreamHandler(self, StringIO())
        self.log_handler.setFormatter(
            logging.Formatter(fmt='%(levelname)s: %(message)s')
        )
        self.logger.addHandler(self.log_handler)

    def popen(self, args: list[str]) -> int:
        process = popen(args)

        while process.poll() is None:
            line = process.stdout.readline().strip()
            self.logger.info(line)
        process.stdout.close()
        return_code = process.returncode

        if return_code:
            self.logger.error(subprocess.CalledProcessError(return_code, args))

        return return_code

    def start(self) -> None:
        self.started.emit()
        self.run()
        self.finished.emit()

    def run(self) -> None:
        return


class ProcessStreamHandler(logging.StreamHandler):
    def __init__(self, process: Process, stream: typing.IO | None = None) -> None:
        super().__init__(stream)
        self.process = process

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.process.log_changed.emit(record)
