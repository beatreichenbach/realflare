from typing import Annotated, Literal

from pydantic import BaseModel, Field
from qt_pydantic import QRect
from qtpy import QtCore


class BaseNodeState(BaseModel):
    geometry: QRect = QtCore.QRect()
    flags: QtCore.Qt.WindowType = QtCore.Qt.WindowType(0)


class SplitterState(BaseNodeState):
    kind: Literal['splitter'] = 'splitter'
    sizes: tuple[int, ...]
    orientation: QtCore.Qt.Orientation
    states: tuple['NodeState', ...] = ()


class DockWidgetState(BaseNodeState):
    kind: Literal['dock'] = 'dock'
    current_index: int
    widgets: tuple[tuple[str, str], ...]
    detachable: bool
    auto_delete: bool
    is_center_widget: bool


NodeState = Annotated[SplitterState | DockWidgetState, Field(discriminator='kind')]


SplitterState.model_rebuild()


class WindowState(BaseModel):
    geometry: QRect = QtCore.QRect()
    states: tuple[NodeState, ...] = ()
