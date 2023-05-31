import logging

import numpy as np
from PySide2 import QtWidgets, QtCore
import PyOpenColorIO as OCIO

from realflare.api.data import RenderElement

from qt_extensions.parameters import EnumParameter
from qt_extensions.viewer import Viewer


class ElementViewer(Viewer):
    element_changed: QtCore.Signal = QtCore.Signal(RenderElement)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._element = RenderElement.FLARE

        self.element_property = EnumParameter('element')
        self.element_property.enum = RenderElement
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

            # gpu = processor.getDefaultGPUProcessor()
            # shader_desc = OCIO.GpuShaderDesc.CreateShaderDesc()
            # shader_desc.setLanguage(OCIO.GPU_LANGUAGE_GLSL_1_3)
            # shader_desc.setFunctionName("OCIODisplay")
            # shader_desc.setResourcePrefix("ocio_")
            #
            # gpu.extractGpuShaderInfo(shader_desc)
            # print(shader_desc.getShaderText())

            self.post_processes.append(self._apply_colorspace)
        except OCIO.Exception as e:
            logging.debug(e)
            logging.warning(
                'Failed to initialize color conversion processor.'
                'The color in the viewer will not be accurate.'
            )

    @property
    def element(self) -> RenderElement:
        return self._element

    @element.setter
    def element(self, value: RenderElement) -> None:
        self.element_property.value = value

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

    def _apply_colorspace(self, array: np.ndarray) -> np.ndarray:
        try:
            self.colorspace_processor.applyRGB(array)
        except OCIO.Exception as e:
            logging.debug(e)
        finally:
            return array
