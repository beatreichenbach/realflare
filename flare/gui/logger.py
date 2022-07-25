import enum
import logging
import os
from PySide2 import QtWidgets, QtCore, QtGui
from qt_extensions.properties import EnumProperty


class Level(enum.IntFlag):
    CRITICAL = logging.CRITICAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    INFO = logging.INFO
    DEBUG = logging.DEBUG


class Sender(QtCore.QObject):
    log = QtCore.Signal(str)


class Handler(logging.Handler):
    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)

        self.sender = Sender()
        self.log = self.sender.log
        formatter = logging.Formatter('{levelname}: {message}', style='{')
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(('root', 'flare')):
            message = self.format(record)
            self.log.emit(message)


class Logger(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.text_edit = None
        self.text_handler = None
        self.file_handler = None

        self._init_ui()
        self._init_handlers()

        # trigger ui update
        self.level = self.level

    def _init_handlers(self) -> None:
        # text handler
        self.text_handler = Handler()
        self.text_handler.log.connect(self.text_edit.appendPlainText)
        self.logger.addHandler(self.text_handler)

        # # file handler
        # log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'flare.log'))
        # self.file_handler = logging.FileHandler(log_path, mode='w')
        # self.file_handler.setLevel(logging.DEBUG)
        # formatter = logging.Formatter(
        #     '%(asctime)s :: %(levelname)s :: %(module)s :: %(message)s'
        # )
        # self.file_handler.setFormatter(formatter)
        # self.logger.addHandler(self.file_handler)

    def _init_ui(self) -> None:
        self.setLayout(QtWidgets.QVBoxLayout())

        self.level_property = EnumProperty()
        self.level_property.enum = Level
        self.level_property.default = Level.WARNING
        self.level_property.value_changed.connect(self.level_changed)
        self.layout().addWidget(self.level_property)

        clear_btn = QtWidgets.QPushButton('Clear')
        clear_btn.clicked.connect(self.clear)
        self.layout().addWidget(clear_btn)

        self.text_edit = QtWidgets.QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        font = QtGui.QFont('Monospace')
        font.setStyleHint(QtGui.QFont.Monospace)
        self.text_edit.setFont(font)
        self.layout().addWidget(self.text_edit)

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger()

    @property
    def level(self) -> int:
        return self.logger.level

    @level.setter
    def level(self, value: int):
        level = Level(value)
        self.level_property.value = level

    def clear(self) -> None:
        self.text_edit.clear()

    def level_changed(self, level: int) -> None:
        self.logger.setLevel(level)

    def sizeHint(self) -> QtCore.QSize:
        size_hint = super().sizeHint()
        size_hint.setWidth(400)
        return size_hint
