from __future__ import annotations
import os
import random
from functools import partial

from PySide2 import QtWidgets, QtCore

from qt_extensions import helper
from realflare.api.data import LensModel, AntiAliasing, RenderElement, Project
from realflare.api.tasks import opencl, raytracing
from qt_extensions.parameters import (
    ParameterEditor,
    IntParameter,
    FloatParameter,
    PathParameter,
    ColorParameter,
    TabDataParameter,
    SizeParameter,
    SizeFParameter,
    PointFParameter,
    StringParameter,
    BoolParameter,
    EnumParameter,
    ParameterWidget,
    PointParameter,
)
from qt_extensions.box import CollapsibleBox
from qt_extensions.typeutils import cast, cast_basic
from realflare.storage import Storage
from realflare.utils import ocio

storage = Storage()


class ProjectEditor(ParameterEditor):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.groups = {}

        self.render_action = None

        self._init_output_group()
        self._init_tabs()
        self._init_flare_group()
        self._init_rendering_group()
        self._init_diagram_group()
        self._init_debug_group()
        # self._init_actions()

        # init defaults
        default_config = Project()
        values = cast_basic(default_config)
        self.set_values(values, attr='default')

    def _init_tabs(self) -> None:
        tab_widget = self.add_tab_group(
            names=('lens_flare', 'render', 'diagram', 'debug'),
        )
        self.tabs = tab_widget.tabs

    def _init_output_group(self) -> None:
        output_group = self.add_group(
            'output', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        # actions
        action = QtWidgets.QAction('Render to Disk', self)
        button = QtWidgets.QToolButton()
        button.setDefaultAction(action)
        output_group.add_widget(button, column=2)
        # editor does not allow signals
        self.render_to_disk = action

        # parameters
        def formatter(text: str):
            if text == 'FLARE_STARBURST':
                text = 'Flare + Starburst'
            return helper.title(text)

        parm = EnumParameter('element')
        parm.enum = RenderElement
        parm.tooltip = 'Output element'
        parm.formatter = formatter
        output_group.add_parameter(parm)

        parm = PathParameter('path')
        parm.method = PathParameter.Method.SAVE_FILE
        parm.tooltip = (
            'Output image path. Use $F4 to replace frame numbers.\n'
            'For example: render.$F4.exr'
        )
        output_group.add_parameter(parm)

        parm = StringParameter('colorspace')
        parm.menu = ocio.colorspace_names()
        parm.tooltip = 'Colorspace from the OCIO config.\nFor example: ACES - ACEScg'
        output_group.add_parameter(parm)

        parm = BoolParameter('split_files')
        parm.tooltip = (
            'Multilayer exr files are not supported yet. Enabling this '
            'parameter will split different layers into separate files.'
        )
        output_group.add_parameter(parm)

    def _init_flare_group(self) -> None:
        self.tabs['lens_flare'].create_hierarchy = False

        # flare
        flare_group = self.tabs['lens_flare'].add_group(
            'flare', style=CollapsibleBox.Style.SIMPLE
        )
        self.groups[flare_group.name] = flare_group

        # light
        light_group = flare_group.add_group(
            'light', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )

        parm = FloatParameter(name='intensity')
        parm.slider_max = 1
        light_group.add_parameter(parm)

        parm = PointFParameter(name='position')
        parm.decimals = 2
        parm.tooltip = 'The position of the light source in NDC space (-1, 1).'
        light_group.add_parameter(parm)

        parm = PathParameter(name='image_file')
        parm.method = PathParameter.Method.OPEN_FILE
        parm.dir_fallback = storage.decode_path('$RES')
        parm.tooltip = (
            "The path to the image file. Variables such as $RES can be used. "
            "For more information see documentation. (To come...)"
        )
        light_group.add_parameter(parm, checkable=True)
        # partial is needed because of __getattr__ on the editor
        parm.enabled_changed.connect(partial(self._light_image_enabled))

        parm = IntParameter(name='image_sample_resolution')
        parm.line_min = 1
        parm.slider_visible = False
        parm.setEnabled(False)
        light_group.add_parameter(parm)

        parm = IntParameter(name='image_samples')
        parm.line_min = 1
        parm.slider_visible = False
        parm.setEnabled(False)
        light_group.add_parameter(parm)

        # lens
        lens_group = flare_group.add_group(
            'lens', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )

        parm = SizeFParameter(name='sensor_size')
        parm.ratio_visible = False
        parm.tooltip = (
            'The sensor size of the camera. A larger sensor size will show '
            'more of the flare.'
        )
        lens_group.add_parameter(parm)

        parm = FloatParameter(name='fstop')
        parm.label = 'F-Stop'
        parm.slider_max = 32
        lens_group.add_parameter(parm)

        parm = StringParameter(name='lens_model_path')
        parm.label = 'Lens Model'
        parm.menu = lens_models()
        parm.tooltip = (
            'The path to the lens model file (\'*.json\'). Variables such as $MODEL '
            'can be used. For more information see documentation. (To come...)'
        )
        lens_group.add_parameter(parm)

        parm = StringParameter(name='glasses_path')
        parm.label = 'Glass Make'
        parm.menu = glass_makes()
        parm.tooltip = (
            'A path to a folder with glass files (\'.yml\'). '
            'The make of the glasses used for lens element lookup. '
            'Each lens element has a refractive index and abbe number that is used to '
            'look up the closest glass in the database. The glass provides a Sellmeier '
            'equation that maps wavelengths to refractive index. The quality of the '
            'glass is responsible for the amount of dispersion. Variables such as $GLASS '
            'can be used. '
        )
        lens_group.add_parameter(parm)

        parm = FloatParameter(name='abbe_nr_adjustment')
        parm.slider_min = -20
        parm.slider_max = 20
        parm.tooltip = (
            'An offset for the abbe number values of the lens elements in the lens model.'
            ' This is a experimental way to play around with the quality of the glass.'
        )
        lens_group.add_parameter(parm)

        parm = FloatParameter(name='min_area')
        parm.line_min = 0
        parm.slider_max = 1
        parm.tooltip = (
            'The minimum area of each primitive. The area of the deformed primitives on '
            'the sensor is used to calculate the intensity of the primitive. '
            'Along the edges of fresnel refraction the primitives get very small which '
            'leads to over bright results. '
            'This parameter can be used to creatively lessen some of the artefacts.'
        )
        lens_group.add_parameter(parm)

        # coating
        coating_group = lens_group.add_group(
            'coating', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )
        coating_group.create_hierarchy = False

        parm = TabDataParameter(name='coating_lens_elements')
        parm.label = 'Lens Elements'
        parm.headers = ['wavelength', 'refractive_index']
        parm.types = [int, float]
        parm.decimals = 2
        parm.tooltip = (
            'Lens Coating for each lens element. A lens coating consists of two '
            'parameters, a wavelength in nm that the coating is optimized for '
            '(thickness = lambda / 4) and the material of the coating (refractive '
            'index). The optimal refractive index is n ≈ 1.23. '
            'However materials with such low refractive indices are hard to find '
            'or expensive. A common material is MgF2 with n = 1.38.'
        )
        coating_group.add_parameter(parm)
        self._coating_tab_data = parm

        coating_group.add_separator()

        parm = PointParameter(name='random_wavelength_range')
        parm.tooltip = (
            'A range in nm for creating random wavelengths in the coating list.'
        )
        coating_group.add_parameter(parm)
        self._coating_wavelength_range = parm

        parm = PointFParameter(name='random_refractive_index_range')
        parm.line_min = 1
        parm.decimals = 2
        parm.tooltip = (
            'A range for creating random refractive indices in the coating list.'
        )
        coating_group.add_parameter(parm)
        self._coating_refractive_index_range = parm

        action = QtWidgets.QAction('Randomize', self)
        action.triggered.connect(lambda: self.randomize_coatings())
        button = QtWidgets.QToolButton()
        button.setDefaultAction(action)
        coating_group.add_widget(button, column=2)

        # ghost aperture
        ghost_aperture_group = flare_group.add_group(
            'ghost_aperture', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )

        self._init_aperture_group(ghost_aperture_group)

        # ghost
        ghost_group = flare_group.add_group(
            'ghost', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        self.groups[ghost_group.name] = ghost_group

        parm = FloatParameter(name='fstop')
        parm.label = 'F-Stop'
        parm.slider_min = 0
        parm.slider_max = 32
        parm.tooltip = (
            'F-Stop that controls the strength of the ringing pattern visible '
            'on ghosts.'
        )
        ghost_group.add_parameter(parm)

        # starburst aperture
        starburst_aperture_group = flare_group.add_group(
            'starburst_aperture', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )

        self._init_aperture_group(starburst_aperture_group)

        # starburst
        starburst_group = flare_group.add_group(
            'starburst', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        self.groups[starburst_group.name] = starburst_group

        parm = FloatParameter(name='intensity')
        parm.tooltip = (
            'A multiplier on the overall brightness of the starburst pattern.'
        )
        starburst_group.add_parameter(parm)

        parm = FloatParameter(name='distance')
        parm.line_min = 0
        parm.slider_max = 1
        parm.tooltip = (
            'The distance in mm away from the aperture where the far-field pattern '
            'is being recorded. This changes the perceived size of the starburst.'
        )
        starburst_group.add_parameter(parm)

        parm = FloatParameter(name='blur')
        parm.tooltip = 'Blur of the starburst.'
        starburst_group.add_parameter(parm)

        parm = FloatParameter(name='rotation')
        parm.slider_max = 180
        parm.tooltip = 'Random rotation during sampling.'
        starburst_group.add_parameter(parm)

        parm = FloatParameter(name='rotation_weight')
        parm.line_min = 0
        parm.slider_max = 2
        parm.tooltip = (
            'The weighting for the rotation. '
            'Equal weighted = 1, weighted towards the inside = 0, weighted towards '
            'outside = 2.'
        )
        starburst_group.add_parameter(parm)

        parm = PointFParameter(name='vignetting')
        parm.tooltip = (
            'A gradient to fade out the starburst towards the edges of the frame. '
            'This prevents visible borders of the starburst frame.'
        )
        starburst_group.add_parameter(parm, checkable=True)

    def _init_rendering_group(self) -> None:
        # renderer
        renderer_group = self.tabs['render'].add_group(
            'renderer', collapsible=True, style=CollapsibleBox.Style.BUTTON
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
        rays_group = self.tabs['render'].add_group(
            'rays', collapsible=True, style=CollapsibleBox.Style.BUTTON
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
        starburst_group = self.tabs['render'].add_group(
            'starburst', collapsible=True, style=CollapsibleBox.Style.BUTTON
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
        ghost_group = self.tabs['render'].add_group(
            'ghost', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )

        parm = SizeParameter('resolution')
        parm.slider_visible = False
        parm.ratio_visible = False
        parm.tooltip = 'Resolution of the ghost.'
        ghost_group.add_parameter(parm)

        # system
        system_group = self.tabs['render'].add_group(
            'system', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        system_group.create_hierarchy = False

        parm = StringParameter('device')
        parm.menu = opencl.devices()
        system_group.add_parameter(parm)

    def _init_diagram_group(self) -> None:
        diagram_renderer_group = self.tabs['diagram'].add_group(
            'renderer', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        diagram_renderer_group.create_hierarchy = False

        parm = SizeParameter('resolution')
        parm.slider_visible = False
        parm.ratio_visible = False
        diagram_renderer_group.add_parameter(parm)

        diagram_rays_group = self.tabs['diagram'].add_group(
            'rays', collapsible=True, style=CollapsibleBox.Style.BUTTON
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

    def _init_debug_group(self) -> None:
        flare_group = self.tabs['debug'].add_group(
            'flare', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        flare_group.create_hierarchy = False

        parm = BoolParameter('show_image')
        flare_group.add_parameter(parm)

        parm = BoolParameter('disable_starburst')
        flare_group.add_parameter(parm)

        parm = BoolParameter('disable_ghosts')
        flare_group.add_parameter(parm)

        parm = IntParameter('debug_ghost')
        parm.slider_max = 100
        flare_group.add_parameter(parm, checkable=True)

    def _init_aperture_group(self, parent: ParameterEditor):
        # shape
        shape_group = parent.add_group(
            'shape', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        parm = SizeFParameter(name='size')
        parm.slider_min = 0
        parm.slider_max = 1
        parm.keep_ratio = True
        shape_group.add_parameter(parm)

        parm = IntParameter(name='blades')
        parm.line_min = 2
        parm.slider_min = 2
        parm.slider_max = 12
        shape_group.add_parameter(parm)

        parm = FloatParameter(name='roundness')
        parm.slider_min = -0.1
        parm.slider_max = 0.1
        shape_group.add_parameter(parm)

        parm = FloatParameter(name='rotation')
        parm.slider_min = 0
        parm.slider_max = 360
        parm.tooltip = 'Rotation in degrees.'
        shape_group.add_parameter(parm)

        parm = FloatParameter(name='softness')
        parm.slider_min = 0
        parm.slider_max = 1
        shape_group.add_parameter(parm)

        # grating
        grating_group = parent.add_group(
            'grating', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        parm = FloatParameter(name='strength')
        parm.slider_min = 0
        parm.slider_max = 1
        grating_group.add_parameter(parm)

        parm = FloatParameter(name='density')
        parm.slider_min = 0
        parm.slider_max = 1
        grating_group.add_parameter(parm)

        parm = FloatParameter(name='length')
        parm.slider_min = 0
        parm.slider_max = 1
        grating_group.add_parameter(parm)

        parm = FloatParameter(name='width')
        parm.slider_min = 0
        parm.slider_max = 1
        grating_group.add_parameter(parm)

        parm = FloatParameter(name='softness')
        parm.slider_min = 0
        parm.slider_max = 1
        grating_group.add_parameter(parm)

        # scratches
        scratches_group = parent.add_group(
            'scratches', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        parm = FloatParameter(name='strength')
        parm.slider_min = 0
        parm.slider_max = 1
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='density')
        parm.slider_min = 0
        parm.slider_max = 1
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='length')
        parm.slider_min = 0
        parm.slider_max = 1
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='width')
        parm.slider_min = 0
        parm.slider_max = 1
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='rotation')
        parm.slider_min = 0
        parm.slider_max = 360
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='rotation_variation')
        parm.label = 'Variation'
        parm.slider_min = 0
        parm.slider_max = 1
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='softness')
        parm.slider_min = 0
        parm.slider_max = 1
        scratches_group.add_parameter(parm)

        parm = SizeFParameter(name='parallax')
        parm.line_min = 0
        parm.slider_min = 0
        parm.slider_max = 1
        scratches_group.add_parameter(parm)

        # dust
        dust_group = parent.add_group(
            'dust', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        parm = FloatParameter(name='strength')
        parm.slider_min = 0
        parm.slider_max = 1
        dust_group.add_parameter(parm)

        parm = FloatParameter(name='density')
        parm.slider_min = 0
        parm.slider_max = 1
        dust_group.add_parameter(parm)

        parm = FloatParameter(name='radius')
        parm.slider_min = 0
        parm.slider_max = 1
        dust_group.add_parameter(parm)

        parm = FloatParameter(name='softness')
        parm.slider_min = 0
        parm.slider_max = 1
        dust_group.add_parameter(parm)

        parm = SizeFParameter(name='parallax')
        parm.line_min = 0
        parm.slider_min = 0
        parm.slider_max = 1
        dust_group.add_parameter(parm)

        # image
        image_group = parent.add_group(
            'image', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        parm = FloatParameter(name='strength')
        parm.slider_min = 0
        parm.slider_max = 1
        image_group.add_parameter(parm)

        parm = PathParameter(name='file')
        parm.method = PathParameter.Method.OPEN_FILE
        parm.dir_fallback = storage.decode_path('$APT')
        parm.tooltip = (
            "The path to the image file. Variables such as $APT can be used. "
            "For more information see documentation. (To come...)"
        )
        image_group.add_parameter(parm)

        parm = SizeFParameter(name='size')
        parm.slider_min = 0
        parm.slider_max = 1
        parm.default = QtCore.QSize(1, 1)
        parm.keep_ratio = True
        image_group.add_parameter(parm)

        parm = FloatParameter(name='threshold')
        parm.slider_min = 0
        parm.slider_max = 1
        image_group.add_parameter(parm)

    def _init_actions(self) -> None:
        for name in ('flare', 'starburst', 'ghost'):
            group = self.groups[name]
            action = QtWidgets.QAction('Save Preset...', group)
            # action.triggered.connect(partial(self.save_preset_as, name))
            group.addAction(action)
            action = QtWidgets.QAction('Load Preset...', group)
            # action.triggered.connect(partial(self.load_preset, name))
            group.addAction(action)

    # def save_preset_as(self, name: str) -> None:
    #     path = storage.decode_path(os.path.join('$PRESET', name))
    #     file_path, filter_string = QtWidgets.QFileDialog.getSaveFileName(
    #         parent=self,
    #         caption='Save Preset As',
    #         dir=path,
    #         filter='*.json',
    #     )
    #     if file_path:
    #         config = self.flare_config()
    #         if name == 'flare':
    #             pass
    #         elif name == 'starburst':
    #             config = config.starburst
    #         elif name == 'ghost':
    #             config = config.ghost
    #         else:
    #             return
    #         json_data = cast_basic(config)
    #         storage.save_data(json_data, file_path)
    #
    # def load_preset(
    #     self,
    #     name: str = '',
    #     config: Flare | Flare.Ghost | Flare.Starburst | None = None,
    # ) -> None:
    #     if name:
    #         path = storage.decode_path(os.path.join('$PRESET', name))
    #         file_path, filter_string = QtWidgets.QFileDialog.getOpenFileName(
    #             parent=self,
    #             caption='Load Preset',
    #             dir=path,
    #             filter='*.json',
    #         )
    #         if file_path:
    #             json_data = storage.read_data(file_path)
    #             if name == 'flare':
    #                 config = cast(data.Flare, json_data)
    #             elif name == 'starburst':
    #                 config = cast(data.Flare.Starburst, json_data)
    #             elif name == 'ghost':
    #                 config = cast(data.Flare.Ghost, json_data)
    #
    #     new_config = self.flare_config()
    #     if isinstance(config, Flare):
    #         new_config = config
    #     elif isinstance(config, Flare.Ghost):
    #         new_config.ghost = config
    #     elif isinstance(config, Flare.Starburst):
    #         new_config.starburst = config
    #     else:
    #         return
    #
    #     self.update_editor(new_config)

    def project(self) -> Project:
        values = self.values()

        values['render']['grid_count'] = values['render']['grid_subdivisions'] + 1
        values['diagram']['grid_count'] = values['diagram']['grid_subdivisions'] + 1

        project = cast(Project, values)

        return project

    def randomize_coatings(self) -> None:
        project = self.project()

        # TODO: clean up...
        lens_model = raytracing.RaytracingTask.update_lens_model(
            project.flare.lens.lens_model_path
        )
        element_count = len(lens_model.lens_elements)

        # TODO: parameters should return right type
        wavelength_range = cast(QtCore.QPoint, self._coating_wavelength_range.value)
        refractive_range = cast(
            QtCore.QPointF, self._coating_refractive_index_range.value
        )

        coatings = []
        for i in range(element_count):
            coatings.append(
                [
                    random.randint(wavelength_range.x(), wavelength_range.y()),
                    random.uniform(refractive_range.x(), refractive_range.y()),
                ]
            )
        self._coating_tab_data.value = coatings

    def set_project(self, project: Project) -> None:
        values = cast_basic(project)

        values['render']['grid_subdivisions'] = values['render']['grid_count'] - 1
        values['diagram']['grid_subdivisions'] = values['diagram']['grid_count'] - 1

        self.blockSignals(True)
        self.set_values(values)
        self.blockSignals(False)
        self.parameter_changed.emit(ParameterWidget())

    def _light_image_enabled(self, enabled: bool) -> None:
        widgets = self.widgets()

        widgets['flare']['light']['position'].setEnabled(not enabled)
        widgets['flare']['light']['image_sample_resolution'].setEnabled(enabled)
        widgets['flare']['light']['image_samples'].setEnabled(enabled)

    def _starburst_aperture_file_enabled(self, enabled: bool) -> None:
        widgets = self.widgets()

        for name in ('fstop', 'blades', 'softness', 'rotation', 'corner_radius'):
            widget = widgets['flare']['starburst']['aperture'].get(name)
            widget.setEnabled(not enabled)

    def _ghost_aperture_file_enabled(self, enabled: bool) -> None:
        widgets = self.widgets()

        for name in ('fstop', 'blades', 'softness', 'rotation', 'corner_radius'):
            widget = widgets['flare']['ghost']['aperture'].get(name)
            widget.setEnabled(not enabled)


def glass_makes() -> dict:
    glasses_path = storage.path_vars['$GLASS']
    glasses = {}
    for item in os.listdir(glasses_path):
        item_path = os.path.join(glasses_path, item)
        if os.path.isdir(item_path):
            glasses[item] = storage.encode_path(item_path)
    return glasses


def lens_models(path: str = '') -> dict:
    if not path:
        path = storage.path_vars['$MODEL']

    if os.path.isfile(path):
        return dict()

    models = {}
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path):
            if not item.endswith('.json'):
                continue
            try:
                data = storage.read_data(item_path)
            except ValueError:
                continue
            lens_model = cast(LensModel, data)
            models[lens_model.name] = storage.encode_path(item_path)
        elif os.path.isdir(item_path):
            children = lens_models(item_path)
            if children:
                models[item] = children
    return models
