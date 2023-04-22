import dataclasses
import json
import logging
import os
from functools import partial

from PySide2 import QtWidgets, QtCore

from flare.api import data, engine
from flare.api.data import Render, AntiAliasing
from flare.gui.settings import Settings
from qt_extensions.properties import (
    IntProperty,
    FloatProperty,
    StringProperty,
    PathProperty,
    PropertyEditor,
    SizeProperty,
    BoolProperty,
    EnumProperty,
    PropertyWidget,
)
from qt_extensions.box import CollapsibleBox
from qt_extensions.typeutils import cast, cast_basic, cast_json


class RenderEditor(PropertyEditor):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.groups = {}

        self._init_editor()
        self._init_actions()

    def _init_editor(self) -> None:
        # # device
        # prop = StringProperty(name='device')
        # devices = [device.name for device in engine.load_devices()]
        # prop.menu = devices
        # self.add_property(prop)

        # output
        output_group = self.add_group(
            'output', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        output_group.create_hierarchy = False

        prop = PathProperty('output_path')
        prop.method = PathProperty.Method.SAVE_FILE
        prop.tooltip = 'Output image path. Use $F4 to replace frame numbers. For example: render.$F4.exr'
        output_group.add_property(prop)

        prop = StringProperty('colorspace')
        prop.tooltip = 'Colorspace of the OCIO config. For example: \'ACES - ACEScg\''
        output_group.add_property(prop)

        layout = output_group.layout()
        row = layout.rowCount()

        self.save_action = QtWidgets.QAction('Save to Disk')
        button = QtWidgets.QToolButton()
        button.setDefaultAction(self.save_action)
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(button)
        button_layout.addStretch()
        layout.addLayout(button_layout, row, 2)

        # quality
        quality_group = self.add_group(
            'quality', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        self.groups[quality_group.name] = quality_group

        # renderer
        renderer_group = quality_group.add_group(
            'renderer', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )
        renderer_group.create_hierarchy = False
        prop = SizeProperty('resolution')
        prop.slider_visible = False
        prop.ratio_visible = False
        prop.tooltip = 'Resolution of the flare image.'
        renderer_group.add_property(prop)

        prop = IntProperty('bin_size')
        prop.slider_visible = False
        prop.tooltip = 'Bin size of the renderer. Larger values will require less memory but increase render time.'
        renderer_group.add_property(prop)

        prop = EnumProperty('anti_aliasing')
        prop.label = 'Anti Aliasing'
        prop.enum = AntiAliasing
        prop.formatter = AntiAliasing.format
        prop.tooltip = 'Super sampling multiplier for anti-aliasing.'
        renderer_group.add_property(prop)

        # rays
        rays_group = quality_group.add_group(
            'rays', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )
        rays_group.create_hierarchy = False

        prop = IntProperty('wavelength_count')
        prop.label = 'Wavelengths'
        prop.tooltip = (
            'The amount of wavelengths that get traced through the lens system in a range of 390nm - 700nm. '
            'Final quality can often be achieved with a value of 5.'
        )
        rays_group.add_property(prop)

        prop = IntProperty('wavelength_sub_count')
        prop.label = 'Wavelength Substeps'
        prop.tooltip = (
            'The amount of sub steps that get rendered between each ray-traced wavelength. '
            'This happens during the rendering stage and interpolates between '
            'the ray-traced wavelengths to generate a smoother transition.'
        )
        rays_group.add_property(prop)

        prop = IntProperty('grid_subdivisions')
        prop.label = 'subdivisions'
        prop.slider_max = 256
        prop.tooltip = (
            'The subdivisions of the grid that gets traced through the lens system. '
            'The more distortion the lens produces, the more subdivisions are needed. '
            'Good results can be achieved at a range of 64-128 rarely needing values up to 200.'
        )
        rays_group.add_property(prop)

        prop = FloatProperty('grid_length')
        prop.slider_max = 100
        prop.tooltip = (
            ')Length in mm of the grid that gets traced through the lens system. '
            'This value is roughly the size of the diameter of the lens. '
            'It\'s best to keep this value as small as possible. Values too small will '
            'lead to cut off shapes in the render.'
        )
        rays_group.add_property(prop)

        # starburst
        starburst_group = quality_group.add_group(
            'starburst', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        prop = SizeProperty('resolution')
        prop.slider_visible = False
        prop.ratio_visible = False
        prop.tooltip = 'Resolution of the starburst pattern.'
        starburst_group.add_property(prop)

        prop = IntProperty('samples')
        prop.slider_visible = False
        prop.tooltip = (
            'Number of samples. High quality renders might need up to 2048 samples.'
        )
        starburst_group.add_property(prop)

        # ghost
        ghost_group = quality_group.add_group(
            'ghost', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        prop = SizeProperty('resolution')
        prop.slider_visible = False
        prop.ratio_visible = False
        prop.tooltip = 'Resolution of the ghost.'
        ghost_group.add_property(prop)

        # debug
        debug_group = self.add_group(
            'debug', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        debug_group.create_hierarchy = False

        prop = BoolProperty('disable_starburst')
        debug_group.add_property(prop)

        prop = BoolProperty('disable_ghosts')
        debug_group.add_property(prop)

        prop = BoolProperty('debug_ghosts')
        debug_group.add_property(prop)

        prop = IntProperty('debug_ghost')
        prop.slider_max = 100
        debug_group.add_property(prop)

        # diagram
        diagram_group = self.add_group(
            'diagram', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )

        diagram_renderer_group = diagram_group.add_group(
            'renderer', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )
        diagram_renderer_group.create_hierarchy = False

        prop = SizeProperty('resolution')
        prop.slider_visible = False
        prop.ratio_visible = False
        diagram_renderer_group.add_property(prop)

        diagram_rays_group = diagram_group.add_group(
            'rays', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )
        diagram_rays_group.create_hierarchy = False

        prop = IntProperty('debug_ghost')
        prop.slider_max = 100
        diagram_rays_group.add_property(prop)

        prop = FloatProperty('light_position')
        prop.slider_min = -1
        prop.slider_max = 1
        diagram_rays_group.add_property(prop)

        prop = IntProperty('grid_subdivisions')
        prop.slider_max = 256
        diagram_rays_group.add_property(prop)

        prop = FloatProperty('grid_length')
        prop.slider_max = 100
        diagram_rays_group.add_property(prop)

        prop = IntProperty('column_offset')
        prop.slider_min = -20
        prop.slider_max = 20
        diagram_rays_group.add_property(prop)

        # init defaults
        default_config = data.Render()
        self.update_widget_values(dataclasses.asdict(default_config), attr='default')

    def _init_actions(self) -> None:
        for name in ('quality',):
            group = self.groups[name]
            action = QtWidgets.QAction('Save Preset...', group)
            action.triggered.connect(partial(self.save_preset_as, name))
            group.addAction(action)
            action = QtWidgets.QAction('Load Preset...', group)
            action.triggered.connect(partial(self.load_preset, name))
            group.addAction(action)
            action = QtWidgets.QAction('Reset', group)
            action.triggered.connect(partial(self.reset_config, name))
            group.addAction(action)

    def render_config(self) -> data.Render:
        values = self.values()

        # match dataclass configuration
        values['quality']['grid_count'] = values['quality']['grid_subdivisions'] + 1
        values['diagram']['grid_count'] = values['diagram']['grid_subdivisions'] + 1
        # values['diagram_resolution'] = values['diagram']['resolution']
        # values['diagram_debug_ghost'] = values['diagram']['debug_ghost']
        # values['diagram_light_position'] = values['diagram'][
        #     'light_position'
        # ]
        # values['diagram_grid_count'] = values['diagram']['grid_count']
        # values['diagram_grid_length'] = values['diagram']['grid_length']
        # values['diagram_column_offset'] = values['diagram']['column_offset']

        config = cast(data.Render, values)
        return config

    def update_editor(self, config: data.Render) -> None:
        values = dataclasses.asdict(config)

        # match editor configuration
        # values['diagram'] = {
        #     'resolution': values['diagram_resolution'],
        #     'debug_ghost': values['diagram_debug_ghost'],
        #     'light_position': values['diagram_light_position'],
        #     'grid_count': values['diagram_grid_count'],
        #     'grid_length': values['diagram_grid_length'],
        #     'column_offset': values['diagram_column_offset'],
        # }
        values['quality']['grid_subdivisions'] = values['quality']['grid_count'] - 1
        values['diagram']['grid_subdivisions'] = values['diagram']['grid_count'] - 1

        self.form.blockSignals(True)
        self.update_widget_values(values)
        self.form.blockSignals(False)
        self.property_changed.emit(PropertyWidget())

    def save_to_disk(self):
        pass

    def save_preset_as(self, name: str) -> None:
        settings = Settings()
        path = settings.decode_path(os.path.join('$PRESET', name))
        file_path, filter_string = QtWidgets.QFileDialog.getSaveFileName(
            parent=self,
            caption='Save Preset As',
            dir=path,
            filter='*.json',
        )
        if file_path:
            config = self.render_config()
            if name == 'quality':
                config = config.quality
            else:
                return
            json_data = cast_json(config)
            settings.save_data(json_data, file_path)

    def load_preset(
        self,
        name: str = '',
        config: Render.Quality | None = None,
    ) -> None:
        if name:
            settings = Settings()
            path = settings.decode_path(os.path.join('$PRESET', name))
            file_path, filter_string = QtWidgets.QFileDialog.getOpenFileName(
                parent=self,
                caption='Load Preset',
                dir=path,
                filter='*.json',
            )
            if file_path:
                json_data = settings.load_data(file_path)
                if name == 'quality':
                    config = cast(Render.Quality, json_data)

        new_config = self.render_config()
        if isinstance(config, Render.Quality):
            new_config.quality = config
        else:
            return
        self.update_editor(new_config)

    def reset_config(self, name: str) -> None:
        if name == 'render':
            widgets = None
        else:
            try:
                widgets = self.widgets()[name]
            except KeyError:
                return
        self.reset(widgets)