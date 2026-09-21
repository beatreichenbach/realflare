import logging
from typing import Any

from qt_parameters import EnumParameter
from qtpy import QtCore, QtWidgets

from flare import api
from flare.ui.widgets import Viewer

from .base import StateWidget

logger = logging.getLogger(__name__)

Policy = QtWidgets.QSizePolicy.Policy


class LayerViewer(Viewer, StateWidget):
    layer_changed: QtCore.Signal = QtCore.Signal(api.Layer)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.layer_parm = EnumParameter()
        self.layer_parm.set_enum(api.Layer)
        self.layer_parm.combo.setSizePolicy(Policy.Minimum, Policy.Fixed)
        self.layer_parm.value_changed.connect(self.layer_changed)

        self.toolbar.insertWidget(self.toolbar.actions()[0], self.layer_parm)

    def layer(self) -> api.Layer | None:
        layer = self.layer_parm.value()
        if isinstance(layer, api.Layer):
            return layer
        return None

    def set_layer(self, layer: api.Layer) -> None:
        self.layer_parm.set_value(layer)

    def state(self) -> dict[str, Any]:
        state = super().state()
        state['layer'] = self.layer()
        return state

    def set_state(self, state: dict[str, Any]) -> None:
        super().set_state(state)
        if isinstance(layer := state.get('layer'), api.Layer):
            self.set_layer(layer)
