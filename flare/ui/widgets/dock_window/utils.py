from qtpy import QtCore, QtWidgets


def activate_window(widget: QtWidgets.QWidget) -> None:
    """Show, raise and activate the window that contains a widget."""

    window = widget.window()
    window.show()
    if window.windowState() & QtCore.Qt.WindowState.WindowMinimized:
        window.setWindowState(QtCore.Qt.WindowState.WindowActive)
    window.raise_()  # bring to front (macOS)
    window.activateWindow()  # give focus (Windows)
