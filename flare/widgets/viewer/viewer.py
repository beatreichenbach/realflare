from __future__ import annotations

import logging

import numpy as np
from qt_material_icons import MaterialIcon
from qt_parameters import ComboParameter, EnumParameter, FloatParameter
from qtpy import QtCore, QtGui, QtWidgets

from .data import Channel
from .gl import OpenGLView

logger = logging.getLogger(__name__)

ColorRole = QtGui.QPalette.ColorRole
Mode = QtGui.QIcon.Mode
Policy = QtWidgets.QSizePolicy.Policy
State = QtGui.QIcon.State

EPSILON = 1e-9


class Viewport(QtWidgets.QFrame):
    scale_changed = QtCore.Signal(float)
    position_changed = QtCore.Signal(QtCore.QPoint)
    pixel_position_changed = QtCore.Signal(QtCore.QPoint)
    pixel_color_changed = QtCore.Signal(QtGui.QColor)

    pause_color = QtGui.QColor(217, 33, 33)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._clicked: bool = False
        self._dragging: bool = False
        self._start_position = QtCore.QPointF()
        self._start_offset = QtCore.QPointF()
        self._offset = QtCore.QPointF()
        self._scale = 1.0
        self._paused = False

        # View
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(QtCore.QMargins())
        self.setLayout(layout)
        self.view = OpenGLView()
        self.view.setMouseTracking(True)
        layout.addWidget(self.view)

        # Pause Frame
        self.setFrameShape(QtWidgets.QFrame.Shape.Box)
        self.setLineWidth(0)
        palette = self.palette()
        palette.setColor(ColorRole.WindowText, self.pause_color)
        self.setPalette(palette)

        # Mouse
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        key = event.key()
        if key == QtCore.Qt.Key.Key_F:
            self.fit()
            event.accept()
            return
        if key == QtCore.Qt.Key.Key_Q:
            self.view.set_border(not self.view.border())
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._clicked = True
        elif event.button() == QtCore.Qt.MouseButton.MiddleButton:
            cursor_position = event.position()
            cursor_position.setY(self.height() - cursor_position.y())

            self._dragging = True
            self._start_position = cursor_position
            self._start_offset = self._offset
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._clicked = False

            cursor_position = event.position()
            cursor_position.setY(self.height() - cursor_position.y())
            view_position = (cursor_position - self._offset) * (1 / self._scale)
            pixel_position = view_position.toPoint()
            self.position_changed.emit(pixel_position)
        elif event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        cursor_position = event.position()
        cursor_position.setY(self.height() - cursor_position.y())
        self._scale = max(self._scale, EPSILON)

        if self._dragging:
            self._offset = self._start_offset + (cursor_position - self._start_position)
            self.view.set_offset(self._offset)

        offset = QtCore.QPointF(0.5, 0.5)
        view_position = (cursor_position - self._offset) * (1 / self._scale) - offset
        pixel_position = view_position.toPoint()
        self.pixel_position_changed.emit(pixel_position)

        pixel_color = self.view.color_at(pixel_position)
        self.pixel_color_changed.emit(pixel_color)

        if self._clicked:
            self.position_changed.emit(pixel_position)

        super().mouseMoveEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        # Zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        cursor_position = event.position()
        cursor_position.setY(self.height() - cursor_position.y())
        self._scale = max(self._scale, EPSILON)

        # Preserve the absolute position of the cursor (zoom to cursor).
        view_position = (cursor_position - self._offset) * (1 / self._scale)
        self._scale *= zoom_factor
        self._offset = cursor_position - view_position * self._scale

        self.view.set_scale(self._scale)
        self.view.set_offset(self._offset)
        self.scale_changed.emit(self._scale)

        event.accept()

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        if event.lostFocus():
            self._dragging = False
        super().focusOutEvent(event)

    def offset(self) -> QtCore.QPointF:
        return self._offset

    def set_offset(self, offset: QtCore.QPointF) -> None:
        self._offset = offset
        self.view.set_offset(self._offset)

    def scale(self) -> float:
        return self._scale

    def set_scale(self, scale: float) -> None:
        self._scale = scale
        self.view.set_scale(self._scale)

    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self.setLineWidth(2 * paused)

    def fit(self) -> None:
        """Fit the viewport to the image."""

        array = self.view.array()
        if array is None:
            return

        image_height, image_width = array.shape[:2]
        if not image_height or not image_width:
            logger.warning(f'Invalid image size: {image_width}x{image_height}')
            return

        view_width = self.width()
        view_height = self.height()
        if not view_height or not view_width:
            return

        view_aspect_ratio = view_width / view_height
        image_aspect_ratio = image_width / image_height
        if image_aspect_ratio > view_aspect_ratio:
            self._scale = view_width / image_width
            height = image_height * self._scale
            self._offset = QtCore.QPointF(0, (view_height - height) / 2)
        else:
            self._scale = view_height / image_height
            width = image_width * self._scale
            self._offset = QtCore.QPointF((view_width - width) / 2, 0)

        self.view.set_scale(self._scale)
        self.view.set_offset(self._offset)
        self.scale_changed.emit(self._scale)


class Footer(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)

        palette = self.palette()
        palette.setColor(ColorRole.Window, QtGui.QColorConstants.Black)
        palette.setColor(ColorRole.WindowText, QtGui.QColorConstants.White)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        self.resolution_lbl = QtWidgets.QLabel('resolution')
        layout.addWidget(self.resolution_lbl)

        layout.addStretch()

        self.coordinates_lbl = QtWidgets.QLabel('coordinates')
        layout.addWidget(self.coordinates_lbl)

        self.rgb_lbl = QtWidgets.QLabel('rgb')
        layout.addWidget(self.rgb_lbl)

        self.hsv_lbl = QtWidgets.QLabel('hsv')
        layout.addWidget(self.hsv_lbl)

    def set_pixel_color(self, color: QtGui.QColor | None) -> None:
        if color.isValid():
            r, g, b, a = color.getRgbF()
            rgb = (
                f'<font color="#ff2222">{r:.4f}</font> '
                f'<font color="#00ff22">{g:.4f}</font> '
                f'<font color="#0088ff">{b:.4f}</font>'
            )
            h, s, v, a = color.getHsvF()
            h = max(h, 0)
        else:
            rgb = ''
            h, s, v = 0, 0, 0
        hsv = f'H: {h:.2f} S: {s:.2f} V: {v:.2f}'

        self.rgb_lbl.setText(rgb)
        self.hsv_lbl.setText(hsv)

    def set_pixel_position(self, position: QtCore.QPoint | None) -> None:
        if position is not None:
            coordinates = f'x={position.x()} y={position.y()}'
        else:
            coordinates = ''
        self.coordinates_lbl.setText(coordinates)

    def set_resolution(self, resolution: QtCore.QSize) -> None:
        text = f'{resolution.width():.0f}x{resolution.height():.0f}'
        self.resolution_lbl.setText(text)


class ToolBar(QtWidgets.QToolBar):
    refreshed = QtCore.Signal()
    paused = QtCore.Signal(bool)
    zoom_changed = QtCore.Signal(float)
    channel_changed = QtCore.Signal(Channel)
    exposure_changed = QtCore.Signal(float)

    pause_color = QtGui.QColor(217, 33, 33)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._zoom = 0
        self._exposure = 0
        self._exposure_cache = 0

        self._init_actions()

    def _init_actions(self) -> None:
        size = self.style().pixelMetric(QtWidgets.QStyle.PixelMetric.PM_SmallIconSize)
        self.setIconSize(QtCore.QSize(size, size))

        # Channel
        self.channel_parm = EnumParameter()
        self.channel_parm.set_enum(Channel)
        self.channel_parm.set_formatter(lambda e: e.name.lower())
        self.channel_parm.combo.keyPressEvent = lambda event: event.ignore()
        self.channel_parm.combo.setSizePolicy(Policy.Minimum, Policy.Fixed)
        self.channel_parm.value_changed.connect(self.channel_changed)

        channel_action = QtWidgets.QWidgetAction(self)
        channel_action.setText('channel')
        channel_action.setDefaultWidget(self.channel_parm)
        self.addAction(channel_action)

        # Exposure toggle
        icon = MaterialIcon('toggle_on')
        icon_off = MaterialIcon('toggle_off')
        palette = self.palette()
        color = palette.color(ColorRole.Highlight)
        pixmap = icon_off.pixmap(0, Mode.Active, State.On, color)
        icon.addPixmap(pixmap, Mode.Active, State.On)

        self.exposure_toggle_action = QtWidgets.QAction(icon, 'exposure_toggle', self)
        self.exposure_toggle_action.setCheckable(True)
        self.exposure_toggle_action.toggled.connect(self._exposure_toggled)
        self.addAction(self.exposure_toggle_action)

        # Exposure slider
        self.exposure_slider = FloatParameter(parent=self)
        self.exposure_slider.set_slider_min(-10)
        self.exposure_slider.set_slider_max(10)
        self.exposure_slider.value_changed.connect(self._exposure_changed)
        palette = self.exposure_slider.slider.palette()
        color = palette.color(ColorRole.Base)
        palette.setColor(ColorRole.Highlight, color)
        self.exposure_slider.slider.setPalette(palette)

        exposure_action = QtWidgets.QWidgetAction(self)
        exposure_action.setText('exposure')
        exposure_action.setDefaultWidget(self.exposure_slider)
        self.addAction(exposure_action)

        # Refresh
        icon = MaterialIcon('refresh')
        refresh_action = QtWidgets.QAction(icon, 'refresh', self)
        refresh_action.triggered.connect(self.refreshed.emit)
        self.addAction(refresh_action)

        # Pause
        icon = MaterialIcon('pause')
        color = self.pause_color
        pixmap = icon.pixmap(0, Mode.Active, State.On, color)
        icon.addPixmap(pixmap, Mode.Active, State.On)
        pause_action = QtWidgets.QAction(icon, 'pause', self)
        pause_action.setCheckable(True)
        pause_action.toggled.connect(self.paused.emit)
        self.addAction(pause_action)

        # Zoom
        items = [('fit', 0)]
        factors = [0.10, 0.25, 0.33, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
        for factor in reversed(factors):
            items.append((f'{factor:2.0%}', factor))

        self.zoom_param = ComboParameter()
        self.zoom_param.set_items(items)
        self.zoom_param.combo.setMaxVisibleItems(len(items))
        self.zoom_param.value_changed.connect(self._zoom_changed)
        self.zoom_param.combo.setSizePolicy(Policy.Minimum, Policy.Fixed)

        zoom_action = QtWidgets.QWidgetAction(self)
        zoom_action.setText('zoom')
        zoom_action.setDefaultWidget(self.zoom_param)
        self.addAction(zoom_action)

    def channel(self) -> Channel | None:
        channel = self.channel_parm.value()
        return channel

    def set_channel(self, channel: Channel) -> None:
        self.channel_parm.set_value(channel)

    def exposure(self) -> float:
        return self._exposure

    def set_exposure(self, exposure: float) -> None:
        self._exposure = exposure
        self.exposure_slider.set_value(exposure)

    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        # Round the zoom value to match item values.
        zoom = int(zoom * 1000) / 1000
        for text, factor in self.zoom_param.items():
            if zoom == factor:
                zoom = factor
                break

        self._zoom = zoom
        self.zoom_param.set_value(zoom)
        if self.zoom_param.value() is None:
            self.zoom_param.combo.setPlaceholderText(f'{zoom:2.1%}')

    def _exposure_changed(self, value: float) -> None:
        self.exposure_toggle_action.blockSignals(True)
        self.exposure_toggle_action.setChecked(value != 0)
        self.exposure_toggle_action.blockSignals(False)

        self._exposure = value
        if value != 0:
            self._exposure_cache = value
        self.exposure_changed.emit(value)

    def _exposure_toggled(self) -> None:
        exposure = self._exposure_cache if self.exposure() == 0 else 0
        self.set_exposure(exposure)

    def _zoom_changed(self, zoom: float | None) -> None:
        if zoom is not None:
            self._zoom = zoom
            self.zoom_changed.emit(self._zoom)


class Viewer(QtWidgets.QWidget):
    refreshed = QtCore.Signal()
    pause_changed = QtCore.Signal(bool)
    position_changed = QtCore.Signal(QtCore.QPoint)
    channel_changed = QtCore.Signal(Channel)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._array = None
        self._resolution = QtCore.QSize()
        self._channel = Channel.RGBA
        self._exposure = 0
        self._paused = False

        self._init_ui()

    def _init_ui(self) -> None:
        self.resize(1280, 720)

        self._layout = QtWidgets.QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # Toolbar
        self.toolbar = ToolBar()
        self.toolbar.refreshed.connect(self.refresh)
        self.toolbar.paused.connect(self.set_paused)
        self._layout.addWidget(self.toolbar)

        # OpenGLView
        self.viewport = Viewport()
        self.view = self.viewport.view

        self._layout.addWidget(self.viewport)
        self._layout.setStretch(1, 1)

        # Footer
        self.footer = Footer()
        self._layout.addWidget(self.footer)

        # Signals
        self.viewport.scale_changed.connect(self.toolbar.set_zoom)
        self.viewport.pixel_position_changed.connect(self.footer.set_pixel_position)
        self.viewport.pixel_color_changed.connect(self.footer.set_pixel_color)
        self.viewport.position_changed.connect(self.position_changed.emit)
        self.toolbar.zoom_changed.connect(self._zoom_changed)
        self.toolbar.channel_changed.connect(self.set_channel)
        self.toolbar.exposure_changed.connect(self.set_exposure)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        channels = {
            QtCore.Qt.Key.Key_R: Channel.RED,
            QtCore.Qt.Key.Key_G: Channel.GREEN,
            QtCore.Qt.Key.Key_B: Channel.BLUE,
            QtCore.Qt.Key.Key_A: Channel.ALPHA,
        }
        key = event.key()
        if channel := channels.get(key):
            if channel == self._channel:
                channel = Channel.RGBA
            self.set_channel(channel)
            event.accept()
            return
        super().keyPressEvent(event)

    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool = True) -> None:
        self._paused = paused
        self.viewport.set_paused(paused)
        self.pause_changed.emit(paused)

    def array(self) -> np.ndarray | None:
        return self._array

    def set_array(self, array: np.ndarray) -> None:
        self._array = array
        self.view.set_array(array)
        height, width = array.shape[:2]
        self._refresh_resolution(QtCore.QSize(width, height))

    def channel(self) -> Channel:
        return self._channel

    def set_channel(self, channel: Channel) -> None:
        self._channel = channel
        self.toolbar.set_channel(channel)
        self.view.set_channel(channel)

    def exposure(self) -> float:
        return self._exposure

    def set_exposure(self, exposure: float) -> None:
        self._exposure = exposure
        self.toolbar.set_exposure(exposure)
        self.view.set_exposure(exposure)

    def state(self) -> dict:
        state = {'exposure': self.exposure()}
        return state

    def set_state(self, state: dict) -> None:
        values = {'exposure': 0}
        values.update(state)

        self.set_exposure(values['exposure'])

    def resolution(self) -> QtCore.QSize:
        return self._resolution

    def refresh(self) -> None:
        self.refreshed.emit()

    def _zoom_changed(self, zoom: float) -> None:
        if zoom > 0:
            self.viewport.set_scale(zoom)
        else:
            self.viewport.fit()

    def _refresh_resolution(self, resolution: QtCore.QSize) -> None:
        if self._resolution != resolution:
            self._resolution = resolution
            self.footer.set_resolution(resolution)
            self.viewport.fit()
