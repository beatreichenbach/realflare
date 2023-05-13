import dataclasses
import logging

import numpy as np
from PySide2 import QtWidgets, QtCore
import PyOpenColorIO as OCIO

from realflare.api.data import RenderElement

from realflare.utils.timing import timer
from qt_extensions.parameters import EnumParameter
from qt_extensions.typeutils import cast
from qt_extensions.viewer import Viewer


class ElementViewer(Viewer):
    element_changed: QtCore.Signal = QtCore.Signal(RenderElement.Type)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._element = RenderElement.Type.STARBURST_APERTURE

        self.element_property = EnumParameter()
        self.element_property.enum = RenderElement.Type
        self.element_property.default = self._element
        self.element_property.value_changed.connect(self._change_element)

        exposure_action = self.toolbar.find_action('exposure_toggle')
        self.toolbar.insertWidget(exposure_action, self.element_property)

        self.colorspace_processor = None
        try:
            config = OCIO.GetCurrentConfig()
            src_colorspace = 'Utility - XYZ - D60'
            display = 'ACES'
            view = 'sRGB'
            processor = config.getProcessor(
                src_colorspace,
                display,
                view,
                OCIO.TransformDirection.TRANSFORM_DIR_FORWARD,
            )
            self.colorspace_processor = processor.getDefaultCPUProcessor()
        except OCIO.Exception as e:
            logging.error(e)

        self.item.post_processes.append(self._apply_colorspace)

    @property
    def element(self) -> RenderElement.Type:
        return self._element

    @element.setter
    def element(self, value: RenderElement.Type) -> None:
        self.element_property.value = value

    def state(self) -> dict:
        state = super().state()
        state['element'] = self.element
        return state

    def set_state(self, state: dict) -> None:
        values = {'element': RenderElement.Type.FLARE}
        values.update(state)
        super().set_state(values)
        self.element = values['element']

    def _change_element(self, value: str) -> None:
        self._element = RenderElement.Type(value)
        self.element_changed.emit(self._element)

    def _apply_colorspace(self, array: np.ndarray) -> np.ndarray:
        try:
            self.colorspace_processor.applyRGB(array)
        except OCIO.Exception as e:
            logging.debug(e)
        finally:
            return array
