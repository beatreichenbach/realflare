import ctypes
import importlib.metadata
import importlib.resources
import logging
import os
import platform
import sys

import platformdirs
import PyOpenColorIO as OCIO
import qtpy
from qt_material_icons import MaterialIcon
from qtpy import QtCore, QtGui, QtWidgets

import flare
from flare import constants, env, ocio
from flare.engine import opengl
from flare.services.update import manager

logger = logging.getLogger(__name__)

PACKAGES = (
    'numpy',
    'PyOpenGL',
    'OpenEXR',
    'opencolorio',
    'pydantic',
    'platformdirs',
    'PySide6',
    'qtpy',
    'packaging',
)


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle('About')
        self.resize(720, 560)

        layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QHBoxLayout()
        layout.addLayout(header)

        icon_path = (
            importlib.resources.files(flare.__name__)
            .joinpath('assets')
            .joinpath('icon.png')
        )
        pixmap = QtGui.QPixmap(str(icon_path)).scaled(
            48,
            48,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        icon = QtWidgets.QLabel()
        icon.setPixmap(pixmap)
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
        self.copy_button.setIcon(MaterialIcon('content_copy'))
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
        self.copy_button.setIcon(MaterialIcon('check'))
        QtCore.QTimer.singleShot(2000, self._reset_copy_icon)

    def _reset_copy_icon(self) -> None:
        self.copy_button.setIcon(MaterialIcon('content_copy'))


def environment_report() -> str:
    """Return a plain text report of the environment for bug reports."""

    sections = (
        ('Flare', _flare_info),
        ('Python', _python_info),
        ('Platform', _platform_info),
        ('Qt', _qt_info),
        ('Hardware', _hardware_info),
        ('OCIO', _ocio_info),
        ('Packages', _packages_info),
        ('OpenGL', _opengl_info),
    )

    blocks = []
    for title, gather in sections:
        lines = [title]
        try:
            lines.extend(f'  {key:<22}{value}' for key, value in gather())
        except Exception as e:
            logger.debug(f'Could not gather {title} info: {e}', exc_info=e)
            lines.append('  unavailable')
        blocks.append('\n'.join(lines))

    return '\n\n'.join(blocks) + '\n'


def _flare_info() -> list[tuple[str, str]]:
    root = manager.install_root()
    if root is None:
        install = 'installed package'
    else:
        kind = 'editable git' if manager.is_git(root) else 'editable'
        install = f'{kind} ({root})'

    return [
        ('version', flare.__version__),
        ('path', str(flare.__file__)),
        ('install', install),
        ('config', platformdirs.user_config_dir(flare.__name__)),
    ]


def _python_info() -> list[tuple[str, str]]:
    return [
        ('version', platform.python_version()),
        ('implementation', platform.python_implementation()),
        ('executable', sys.executable),
    ]


def _platform_info() -> list[tuple[str, str]]:
    return [
        ('system', platform.platform()),
        ('QT_QPA_PLATFORM', os.environ.get('QT_QPA_PLATFORM', '')),
        ('PYOPENGL_PLATFORM', os.environ.get('PYOPENGL_PLATFORM', '')),
        ('OCIO', os.environ.get(env.OCIO, '(built-in)')),
    ]


def _qt_info() -> list[tuple[str, str]]:
    platform_name = QtGui.QGuiApplication.platformName()
    if not isinstance(platform_name, str):
        platform_name = 'unavailable'
    return [
        ('binding', str(qtpy.API_NAME)),
        ('version', str(qtpy.QT_VERSION)),
        ('platform', str(platform_name)),
    ]


def _hardware_info() -> list[tuple[str, str]]:
    cores = os.cpu_count()
    return [
        ('cpu', _cpu_name()),
        ('cores', str(cores) if cores else 'unavailable'),
        ('arch', platform.machine()),
        ('memory', _memory_info()),
    ]


def _cpu_name() -> str:
    if sys.platform.startswith('linux'):
        try:
            with open('/proc/cpuinfo') as file:
                for line in file:
                    if line.startswith('model name'):
                        return line.split(':', 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or 'unavailable'


def _memory_info() -> str:
    if sys.platform.startswith('linux'):
        return _linux_memory()
    if sys.platform == 'win32':
        return _windows_memory()
    return 'unavailable'


def _linux_memory() -> str:
    try:
        values = {}
        with open('/proc/meminfo') as file:
            for line in file:
                key, _, value = line.partition(':')
                if key in ('MemTotal', 'MemAvailable'):
                    values[key] = int(value.split()[0])
    except (OSError, ValueError):
        return 'unavailable'

    if 'MemTotal' not in values:
        return 'unavailable'

    total = values['MemTotal'] / 1024**2
    available = values.get('MemAvailable', 0) / 1024**2
    return f'{total:.1f} GB total, {available:.1f} GB available'


def _windows_memory() -> str:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ('length', ctypes.c_ulong),
            ('load', ctypes.c_ulong),
            ('total', ctypes.c_ulonglong),
            ('available', ctypes.c_ulonglong),
            ('total_page_file', ctypes.c_ulonglong),
            ('available_page_file', ctypes.c_ulonglong),
            ('total_virtual', ctypes.c_ulonglong),
            ('available_virtual', ctypes.c_ulonglong),
            ('available_extended_virtual', ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    try:
        windll = ctypes.windll  # ty: ignore[unresolved-attribute]
        windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    except (AttributeError, OSError):
        return 'unavailable'

    total = status.total / 1024**3
    available = status.available / 1024**3
    return f'{total:.1f} GB total, {available:.1f} GB available'


def _ocio_info() -> list[tuple[str, str]]:
    config = ocio.get_config()
    display = config.getDefaultDisplay()
    return [
        ('version', _package_version('opencolorio')),
        ('source', os.environ.get(env.OCIO, f'built-in ({ocio.DEFAULT_CONFIG})')),
        ('config', config.getName() or 'unnamed'),
        ('display', display),
        ('view', config.getDefaultView(display)),
        ('scene-linear', config.getRoleColorSpace(OCIO.ROLE_SCENE_LINEAR)),  # ty: ignore[unresolved-attribute]
    ]


def _packages_info() -> list[tuple[str, str]]:
    return [(name, _package_version(name)) for name in PACKAGES]


def _opengl_info() -> list[tuple[str, str]]:
    context, _ = opengl.create_context_surface()
    try:
        return opengl.get_gpu_info()
    finally:
        context.doneCurrent()


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return 'unavailable'
