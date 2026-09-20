import dataclasses

from qtpy import QtWidgets

WidgetSource = str | type[QtWidgets.QWidget]


@dataclasses.dataclass()
class RegisteredWidget:
    cls: type[QtWidgets.QWidget]
    name: str
    unique: bool = False
