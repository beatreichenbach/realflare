import dataclasses
import json
import logging
import os
from functools import partial

from PySide2 import QtWidgets

from realflare.api import data
from realflare.api.data import Render, AntiAliasing
from realflare.api.tasks import opencl
from realflare.utils.settings import Settings
from qt_extensions.parameters import (
    IntParameter,
    FloatParameter,
    StringParameter,
    PathParameter,
    ParameterEditor,
    SizeParameter,
    BoolParameter,
    EnumParameter,
    ParameterWidget,
)
from qt_extensions.box import CollapsibleBox
from qt_extensions.typeutils import cast, cast_basic


class RenderEditor(ParameterEditor):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.groups = {}

        self._init_editor()
        self._init_actions()

    def _init_editor(self) -> None:
        # output
        output_group = self.add_group(
            'output', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        output_group.create_hierarchy = False

        parm = PathParameter('output_path')
        parm.method = PathParameter.Method.SAVE_FILE
        parm.tooltip = (
            'Output image path. Use $F4 to replace frame numbers. '
            'For example: render.$F4.exr'
        )
        output_group.add_parameter(parm)

        parm = StringParameter('colorspace')
        parm.tooltip = 'Colorspace of the OCIO config. For example: \'ACES - ACEScg\''
        output_group.add_parameter(parm)

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
        parm = SizeParameter('resolution')
        parm.slider_visible = False
        parm.ratio_visible = False
        parm.tooltip = 'Resolution of the flare image.'
        renderer_group.add_parameter(parm)

        parm = IntParameter('bin_size')
        parm.slider_visible = False
        parm.tooltip = (
            'Bin size of the renderer. Larger values will require less memory '
            'but increase render time.'
        )
        renderer_group.add_parameter(parm)

        parm = EnumParameter('anti_aliasing')
        parm.label = 'Anti Aliasing'
        parm.enum = AntiAliasing
        parm.formatter = AntiAliasing.format
        parm.tooltip = 'Super sampling multiplier for anti-aliasing.'
        renderer_group.add_parameter(parm)

        # rays
        rays_group = quality_group.add_group(
            'rays', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )
        rays_group.create_hierarchy = False

        parm = IntParameter('wavelength_count')
        parm.label = 'Wavelengths'
        parm.line_min = 1
        parm.slider_min = 1
        parm.tooltip = (
            'The amount of wavelengths that get traced through the lens system in a '
            'range of 390nm - 700nm. '
            'Final quality can often be achieved with a value of 5.'
        )
        rays_group.add_parameter(parm)

        parm = IntParameter('wavelength_sub_count')
        parm.label = 'Wavelength Substeps'
        parm.line_min = 1
        parm.slider_min = 1
        parm.tooltip = (
            'The amount of sub steps that get rendered between each ray-traced '
            'wavelength. This happens during the rendering stage and interpolates '
            'between the ray-traced wavelengths to generate a smoother transition.'
        )
        rays_group.add_parameter(parm)

        parm = IntParameter('grid_subdivisions')
        parm.slider_max = 256
        parm.tooltip = (
            'The subdivisions of the grid that gets traced through the lens system. '
            'The more distortion the lens produces, the more subdivisions are needed. '
            'Good results can be achieved at a range of 64-128 rarely needing values up '
            'to 200.'
        )
        rays_group.add_parameter(parm)

        parm = FloatParameter('grid_length')
        parm.slider_max = 100
        parm.tooltip = (
            'Length in mm of the grid that gets traced through the lens system. '
            'This value is roughly the size of the diameter of the lens. '
            'It\'s best to keep this value as small as possible. Values too small will '
            'lead to cut off shapes in the render.'
        )
        rays_group.add_parameter(parm)

        parm = FloatParameter('cull_percentage')
        parm.slider_max = 1
        parm.line_min = 0
        parm.line_max = 1
        parm.tooltip = (
            'A percentage for how many of the darkest ghosts to cull. '
            '0.2 means 20% of the darkest ghosts are culled which speeds up performance.'
        )
        rays_group.add_parameter(parm)

        # starburst
        starburst_group = quality_group.add_group(
            'starburst', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        parm = SizeParameter('resolution')
        parm.slider_visible = False
        parm.ratio_visible = False
        parm.tooltip = 'Resolution of the starburst pattern.'
        starburst_group.add_parameter(parm)

        parm = IntParameter('samples')
        parm.slider_visible = False
        parm.tooltip = (
            'Number of samples. High quality renders might need up to 2048 samples.'
        )
        starburst_group.add_parameter(parm)

        # ghost
        ghost_group = quality_group.add_group(
            'ghost', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        parm = SizeParameter('resolution')
        parm.slider_visible = False
        parm.ratio_visible = False
        parm.tooltip = 'Resolution of the ghost.'
        ghost_group.add_parameter(parm)

        # system
        system_group = self.add_group(
            'system', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )

        parm = StringParameter('device')
        parm.menu = opencl.devices()
        system_group.add_parameter(parm)

        # debug
        debug_group = self.add_group(
            'debug', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        debug_group.create_hierarchy = False

        parm = BoolParameter('disable_starburst')
        debug_group.add_parameter(parm)

        parm = BoolParameter('disable_ghosts')
        debug_group.add_parameter(parm)

        parm = BoolParameter('debug_ghosts')
        debug_group.add_parameter(parm)

        parm = IntParameter('debug_ghost')
        parm.slider_max = 100
        debug_group.add_parameter(parm)

        # diagram
        diagram_group = self.add_group(
            'diagram', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )

        diagram_renderer_group = diagram_group.add_group(
            'renderer', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )
        diagram_renderer_group.create_hierarchy = False

        parm = SizeParameter('resolution')
        parm.slider_visible = False
        parm.ratio_visible = False
        diagram_renderer_group.add_parameter(parm)

        diagram_rays_group = diagram_group.add_group(
            'rays', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )
        diagram_rays_group.create_hierarchy = False

        parm = IntParameter('debug_ghost')
        parm.slider_max = 100
        diagram_rays_group.add_parameter(parm)

        parm = FloatParameter('light_position')
        parm.slider_min = -1
        parm.slider_max = 1
        diagram_rays_group.add_parameter(parm)

        parm = IntParameter('grid_subdivisions')
        parm.slider_max = 256
        diagram_rays_group.add_parameter(parm)

        parm = FloatParameter('grid_length')
        parm.slider_max = 100
        diagram_rays_group.add_parameter(parm)

        parm = IntParameter('column_offset')
        parm.slider_min = -20
        parm.slider_max = 20
        diagram_rays_group.add_parameter(parm)

        # init defaults
        default_config = data.Render()
        self.set_values(dataclasses.asdict(default_config), attr='default')

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
        self.set_values(values)
        self.form.blockSignals(False)
        self.parameter_changed.emit(ParameterWidget())

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
            json_data = cast_basic(config)
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
