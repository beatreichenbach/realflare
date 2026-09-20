from qtpy import QtCore, QtGui, QtWidgets

# Platform plugins that implement window opacity. Others, such as wayland and
# offscreen, print a warning and ignore the request.
OPACITY_PLATFORMS = ('cocoa', 'windows', 'xcb')


def supports_window_opacity() -> bool:
    """Return whether the platform supports window opacity."""

    return QtGui.QGuiApplication.platformName() in OPACITY_PLATFORMS


def set_window_opacity(widget: QtWidgets.QWidget, opacity: float) -> None:
    """Set the opacity of a window where the platform supports it."""

    if supports_window_opacity():
        widget.setWindowOpacity(opacity)


def area_orientation(area: QtCore.Qt.DockWidgetArea) -> QtCore.Qt.Orientation:
    """Return an Orientation based on the DockWidgetArea."""

    if area in (
        QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
        QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
    ):
        return QtCore.Qt.Orientation.Horizontal
    else:
        return QtCore.Qt.Orientation.Vertical


def tab_widget_classes(widget: QtWidgets.QTabWidget) -> tuple[tuple[str, str], ...]:
    """Return a tuple (title, class name) for QTabWidgets."""

    widgets = []
    for i in range(widget.count()):
        widgets.append((widget.tabText(i), type(widget.widget(i)).__name__))
    return tuple(widgets)


def focus_widget(widget: QtWidgets.QWidget) -> None:
    """Focus and bring a widget to the front."""

    # Switch to the tab
    parent = widget.parent()
    while parent is not None:
        if isinstance(parent, QtWidgets.QTabWidget):
            index = parent.indexOf(widget)
            parent.setCurrentIndex(index)
            break
        parent = parent.parent()

    # Bring the window to the front
    window = widget.window()
    if window.windowState() & QtCore.Qt.WindowState.WindowMinimized:
        window.setWindowState(QtCore.Qt.WindowState.WindowActive)
    window.raise_()  # for macOS
    window.activateWindow()  # for Windows
