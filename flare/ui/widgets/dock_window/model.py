from typing import Annotated, Literal, NamedTuple

from pydantic import BaseModel, Field
from qt_pydantic import QRect
from qtpy import QtCore


class TabState(NamedTuple):
    title: str
    cls_name: str


class BaseWidgetState(BaseModel):
    geometry: QRect = QtCore.QRect()
    flags: QtCore.Qt.WindowType = QtCore.Qt.WindowType(0)


class SplitterState(BaseWidgetState):
    kind: Literal['splitter'] = 'splitter'
    sizes: tuple[int, ...] = ()
    orientation: QtCore.Qt.Orientation = QtCore.Qt.Orientation.Horizontal
    states: tuple['WidgetState', ...] = ()


class DockWidgetState(BaseWidgetState):
    kind: Literal['dock'] = 'dock'
    current_index: int = 0
    widgets: tuple[TabState, ...] = ()
    detachable: bool = True
    auto_delete: bool = True
    is_center_widget: bool = False


WidgetState = Annotated[SplitterState | DockWidgetState, Field(discriminator='kind')]


# NOTE: SplitterState is defined before WidgetState but references it in its
# `states` field, so the model is incomplete until rebuilt with WidgetState defined.
SplitterState.model_rebuild()


class WindowState(BaseModel):
    geometry: QRect = QtCore.QRect()
    states: tuple[WidgetState, ...] = ()
