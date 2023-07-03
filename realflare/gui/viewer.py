from __future__ import annotations
import logging

import numpy as np
import PyOpenColorIO as OCIO
from PySide2 import QtWidgets, QtCore

from qt_extensions import helper
from realflare.api.data import RenderElement

from qt_extensions.parameters import EnumParameter
from qt_extensions.viewer import Viewer
from realflare.storage import Storage
from realflare.utils import ocio

logger = logging.getLogger(__name__)
storage = Storage()


class ElementViewer(Viewer):
    element_changed: QtCore.Signal = QtCore.Signal(RenderElement)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._element = RenderElement.FLARE

        def formatter(text: str):
            if text == 'FLARE_STARBURST':
                text = 'Flare + Starburst'
            return helper.title(text)

        self.element_parm = EnumParameter('element')
        self.element_parm.set_enum(RenderElement)
        self.element_parm.set_default(self._element)
        self.element_parm.set_formatter(formatter)
        self.element_parm.value_changed.connect(self._change_element)

        exposure_action = self.toolbar.find_action('exposure_toggle')
        self.toolbar.insertWidget(exposure_action, self.element_parm)

        self.view_processor = ocio.view_processor()
        if self.view_processor is not None:
            self.post_processes.append(self._apply_rgb)

    @property
    def element(self) -> RenderElement:
        return self._element

    @element.setter
    def element(self, value: RenderElement) -> None:
        self.element_parm.set_value(value)

    def state(self) -> dict:
        state = super().state()
        state['element'] = self.element
        return state

    def set_state(self, state: dict) -> None:
        values = {'element': RenderElement.FLARE}
        values.update(state)
        super().set_state(values)
        self.element = values['element']

    def _change_element(self, value) -> None:
        self._element = value
        self.element_changed.emit(self._element)

    def _apply_rgb(self, array: np.ndarray) -> None:
        try:
            self.view_processor.applyRGB(array)
        except OCIO.Exception as e:
            logging.debug(e)
