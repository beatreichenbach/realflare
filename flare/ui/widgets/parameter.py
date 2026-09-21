from typing import Any

from qt_parameters import ParameterWidget
from qtpy import QtGui, QtWidgets


class MenuComboBox(QtWidgets.QComboBox):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.menu = QtWidgets.QMenu(self)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self.menu.setMinimumWidth(self.width())
        self.menu.exec(pos)
        event.accept()


class MenuParameter(ParameterWidget):
    _data: dict[str, Any] | None = None

    def _init_ui(self) -> None:
        self.combo = MenuComboBox()
        self.combo.menu.triggered.connect(self._action_triggered)
        self._layout.addWidget(self.combo)

    def set_value(self, value: Any) -> None:
        if self._data:
            texts = get_flat_keys(self._data)
            text = texts.get(value)
        else:
            text = None
        if text is None:
            raise ValueError(f'{value!r} not in data')

        super().set_value(value)
        self.combo.clear()
        self.combo.addItem(text)

    def data(self) -> dict[str, Any] | None:
        return self._data

    def set_data(self, data: dict[str, Any]) -> None:
        self._data = data
        self._refresh_menu()

    def _refresh_menu(self) -> None:
        """Refresh the menu with the data."""

        self.combo.menu.clear()
        if self._data is not None:
            self._add_items(self.combo.menu, self._data)

    def _add_items(self, menu: QtWidgets.QMenu, data: dict[str, Any]) -> None:
        """Add the items from data to the menu."""

        for key, value in data.items():
            if isinstance(value, dict):
                submenu = QtWidgets.QMenu(menu)
                submenu.setTitle(key)
                menu.addMenu(submenu)
                self._add_items(submenu, value)
            else:
                action = QtGui.QAction(self)
                action.setText(key)
                action.setData(value)
                menu.addAction(action)

    def _action_triggered(self, action: QtGui.QAction) -> None:
        """Handle the triggering of a menu Action."""

        super().set_value(action.data())
        text = action.text()
        self.combo.clear()
        self.combo.addItem(text)


def get_flat_keys(data: dict[str, Any]) -> dict[Any, str]:
    """Return the keys of the data in a flat dict."""

    keys = {}
    for key, value in data.items():
        if isinstance(value, dict):
            keys.update(get_flat_keys(value))
        else:
            keys[value] = key
    return keys
