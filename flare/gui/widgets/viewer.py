import logging

from qt_parameters import EnumParameter
from qtpy import QtCore, QtWidgets

from flare import api
from flare.widgets import Viewer
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
        return layer

    def set_layer(self, layer: api.Layer) -> None:
        self.layer_parm.set_value(layer)

    def state(self) -> dict:
        state = super().state()
        state['layer'] = self.layer()
        return state

    def set_state(self, state: dict) -> None:
        super().set_state(state)
        if layer := state.get('layer'):
            self.set_layer(layer)
