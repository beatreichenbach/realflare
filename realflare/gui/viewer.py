import dataclasses
import logging

import numpy as np
from PySide2 import QtWidgets
import PyOpenColorIO as OCIO

from realflare.api.data import RenderElement

from realflare.utils.timing import timer
from qt_extensions.properties import EnumProperty
from qt_extensions.typeutils import cast
from qt_extensions.viewer import Viewer, ViewerState


@dataclasses.dataclass()
class ViewerState(ViewerState):
    exposure: float = 0
    element: RenderElement.Type = RenderElement.Type.FLARE


class ElementViewer(Viewer):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._element = RenderElement.Type.STARBURST_APERTURE

        self.element_property = EnumProperty()
        self.element_property.enum = RenderElement.Type
        self.element_property.default = self._element
        self.element_property.value_changed.connect(self._change_element_type)

        render_element_action = QtWidgets.QWidgetAction(self)
        render_element_action.setDefaultWidget(self.element_property)
        render_element_action.setText('output')
        exposure_action = self.toolbar.find_action('exposure')
        self.toolbar.insertAction(exposure_action, render_element_action)

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

    @property
    def state(self) -> ViewerState:
        state = ViewerState(exposure=self.exposure, element=self.element)
        return state

    @state.setter
    def state(self, value: dict) -> None:
        state = cast(ViewerState, value)
        self.exposure = state.exposure
        self.element = state.element

    def _change_element_type(self, value: str) -> None:
        self._element = RenderElement.Type(value)
        self.refresh()

    def _apply_colorspace(self, array: np.ndarray) -> np.ndarray:
        try:
            self.colorspace_processor.applyRGB(array)
        except OCIO.Exception as e:
            logging.debug(e)
        finally:
            return array
