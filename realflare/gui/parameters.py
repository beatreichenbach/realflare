import random
import enum
from functools import partial

from PySide2 import QtWidgets

from realflare.api.data import Prescription, AntiAliasing, RenderElement, Project
from realflare.api.tasks import opencl
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
from realflare.utils.storage import Storage


class LightSource(enum.Enum):
    POSITION = enum.auto()
    IMAGE = enum.auto()


class ProjectEditor(ParameterEditor):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.storage = Storage()
        self.groups = {}

        self.render_action = None

        self._init_output_group()
        self._init_tabs()
        self._init_flare_group()
        self._init_rendering_group()
        self._init_diagram_group()
        self._init_debug_group()
        self._init_actions()

        # init defaults
        default_config = Project()
        values = cast_basic(default_config)
        self.set_values(values, attr='default')

    def _init_tabs(self) -> None:
        tab_widget = self.add_tab_group(
            names=('lens_flare', 'render', 'diagram', 'debug'),
        )
        self.tabs = tab_widget.tabs

    def _init_output_group(self):
        output_group = self.add_group(
            'output', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        # actions
        action = QtWidgets.QAction('Render to Disk', self)
        # action.triggered.connect(self.render_requested.emit)
        button = QtWidgets.QToolButton()
        button.setDefaultAction(action)
        output_group.add_widget(button, column=2)

        # parameters
        parm = EnumParameter('element')
        parm.enum = RenderElement
        parm.tooltip = 'Output element'
        output_group.add_parameter(parm)

        parm = PathParameter('output_path')
        parm.method = PathParameter.Method.SAVE_FILE
        parm.tooltip = (
            'Output image path. Use $F4 to replace frame numbers.\n'
            'For example: render.$F4.exr'
        )
        output_group.add_parameter(parm)

        parm = StringParameter('colorspace')
        parm.tooltip = 'Colorspace from the OCIO config.\nFor example: ACES - ACEScg'
        output_group.add_parameter(parm)

    def _init_flare_group(self):
        self.tabs['lens_flare'].create_hierarchy = False

        aperture_dir = self.storage.decode_path('$APT')

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
        parm.tooltip = (
            'A multiplier on the overall brightness of the lens flare. '
            'Currently not used.'
        )
        # light_group.add_parameter(parm)

        parm = ColorParameter(name='color')
        parm.tooltip = (
            'A global multiplier on the color of the lens flare. Currently not used.'
        )
        # light_group.add_parameter(parm)

        parm = PointFParameter(name='position')
        parm.decimals = 2
        parm.tooltip = 'The position of the light source in NDC space (-1, 1).'
        light_group.add_parameter(parm)

        parm = PathParameter(name='image_file')
        parm.method = PathParameter.Method.OPEN_FILE
        parm.dir_fallback = aperture_dir
        parm.tooltip = (
            "The path to the image file. Variables such as $RES can be used. "
            "For more information see documentation. (To come...)"
        )
        light_group.add_parameter(parm, checkable=True)
        # partial is needed because of __getattr__ on the editor
        parm.enabled_changed.connect(partial(self._light_image_enable))

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

        parm = SizeParameter(name='sensor_size')
        parm.ratio_visible = False
        parm.tooltip = (
            'The sensor size of the camera. A larger sensor size will show '
            'more of the flare.'
        )
        lens_group.add_parameter(parm)

        parm = StringParameter(name='prescription_path')
        parm.label = 'Lens Model'
        parm.menu = self.storage.load_lens_models()
        parm.tooltip = (
            'The path to the lens model file (\'*.json\'). Variables such as $MODEL '
            'can be used. For more information see documentation. (To come...)'
        )
        lens_group.add_parameter(parm)

        parm = StringParameter(name='glasses_path')
        parm.label = 'Glass Make'
        parm.menu = self.storage.load_glass_makes()
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

        # starburst
        starburst_group = flare_group.add_group(
            'starburst', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        self.groups[starburst_group.name] = starburst_group

        # starburst aperture
        starburst_aperture_group = starburst_group.add_group(
            'aperture', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        parm = FloatParameter(name='fstop')
        parm.label = 'F-Stop'
        parm.slider_min = 0
        parm.slider_max = 32
        parm.tooltip = (
            'The F-Stop of the aperture. This controls the size of the aperture.'
        )
        starburst_aperture_group.add_parameter(parm)

        parm = PathParameter(name='file')
        parm.method = PathParameter.Method.OPEN_FILE
        parm.dir_fallback = aperture_dir
        parm.tooltip = (
            "The path to the image file. Variables such as $APT can be used. "
            "For more information see documentation. (To come...)"
        )
        starburst_aperture_group.add_parameter(parm)

        parm = IntParameter(name='blades')
        parm.slider_min = 1
        parm.slider_max = 12
        parm.line_min = 1
        parm.tooltip = 'Number of blades for the aperture.'
        starburst_aperture_group.add_parameter(parm)

        parm = FloatParameter(name='rotation')
        parm.slider_min = -180
        parm.slider_max = 180
        parm.tooltip = 'Rotation in degrees of the aperture. Currently not used.'
        # starburst_aperture_group.add_parameter(parm)

        parm = FloatParameter(name='corner_radius')
        parm.slider_min = 0
        parm.slider_max = 1
        parm.tooltip = 'Corner radius for blades. Currently not used.'
        # starburst_aperture_group.add_parameter(parm)

        parm = FloatParameter(name='softness')
        parm.slider_min = 0
        parm.slider_max = 1
        parm.tooltip = 'Softness of the aperture.'
        starburst_aperture_group.add_parameter(parm)

        parm = FloatParameter(name='dust_amount')
        parm.tooltip = 'Amount of dust particles. Currently not used.'
        # starburst_aperture_group.add_parameter(parm)

        parm = FloatParameter(name='scratches_amount')
        parm.tooltip = 'Amount of scratches. Currently not used.'
        # starburst_aperture_group.add_parameter(parm)

        parm = FloatParameter(name='grating_amount')
        parm.tooltip = (
            'Amount of grating along the edges of the aperture. '
            'This can be used to generate rainbow circles. Currently not used.'
        )
        # starburst_aperture_group.add_parameter(parm)

        # starburst

        parm = FloatParameter(name='intensity')
        parm.tooltip = (
            'A multiplier on the overall brightness of the starburst pattern.'
        )
        starburst_group.add_parameter(parm)

        parm = FloatParameter(name='lens_distance')
        parm.line_min = 0.001
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
        parm.slider_max = 2
        parm.tooltip = 'Random rotation during sampling (in radians?).'
        starburst_group.add_parameter(parm)

        parm = FloatParameter(name='rotation_weighting')
        parm.slider_max = 4
        parm.tooltip = (
            'The weighting for the rotation. '
            'Equal weighted = 1, weighted towards the inside = 0, weighted towards '
            'outside = 2.'
        )
        starburst_group.add_parameter(parm)

        parm = PointFParameter(name='fadeout')
        parm.tooltip = (
            'A gradient to fade out the starburst towards the edges of the frame. '
            'This prevents visible borders of the starburst frame.'
        )
        starburst_group.add_parameter(parm)

        parm = SizeFParameter(name='scale')
        parm.tooltip = 'A multiplier on the overall scale of the starburst pattern.'
        starburst_group.add_parameter(parm)

        # ghost
        ghost_group = flare_group.add_group(
            'ghost', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        self.groups[ghost_group.name] = ghost_group

        # ghost aperture
        ghost_aperture_group = ghost_group.add_group(
            'aperture', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        parm = FloatParameter(name='fstop')
        parm.label = 'F-Stop'
        parm.slider_min = 0
        parm.slider_max = 32
        ghost_aperture_group.add_parameter(parm)

        parm = PathParameter(name='file')
        parm.method = PathParameter.Method.OPEN_FILE
        parm.dir_fallback = aperture_dir
        ghost_aperture_group.add_parameter(parm)

        parm = IntParameter(name='blades')
        parm.slider_min = 1
        parm.slider_max = 12
        parm.line_min = 1
        ghost_aperture_group.add_parameter(parm)

        parm = FloatParameter(name='rotation')
        parm.slider_min = -180
        parm.slider_max = 180
        # ghost_aperture_group.add_parameter(parm)

        parm = FloatParameter(name='corner_radius')
        parm.slider_min = 0
        parm.slider_max = 1
        # ghost_aperture_group.add_parameter(parm)

        parm = FloatParameter(name='softness')
        parm.slider_min = 0
        parm.slider_max = 1
        ghost_aperture_group.add_parameter(parm)

        # parm = FloatParameter(name='dust_amount')
        # ghost_aperture_group.add_parameter(parm)

        # parm = FloatParameter(name='scratches_amount')
        # ghost_aperture_group.add_parameter(parm)

        # parm = FloatParameter(name='grating_amount')
        # ghost_aperture_group.add_parameter(parm)

        # ghost
        parm = FloatParameter(name='fstop')
        parm.slider_min = 0
        parm.slider_max = 32
        parm.tooltip = (
            'F-Stop that controls the strength of the ringing pattern visible '
            'on ghosts.'
        )
        ghost_group.add_parameter(parm)

    def _init_rendering_group(self):
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

        parm = StringParameter('device')
        parm.menu = opencl.devices()
        system_group.add_parameter(parm)

    def _init_diagram_group(self):
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

    def _init_debug_group(self):
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

        debug_ghosts_parm = BoolParameter('debug_ghosts')
        debug_ghosts_parm.label = ''
        debug_ghosts_parm.setVisible(False)
        flare_group.add_parameter(debug_ghosts_parm)

        parm = IntParameter('debug_ghost')
        parm.slider_max = 100
        flare_group.add_parameter(parm, checkable=True)
        parm.enabled_changed.connect(
            lambda enabled: setattr(debug_ghosts_parm, 'value', enabled)
        )

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
    #     path = self.storage.decode_path(os.path.join('$PRESET', name))
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
    #         self.storage.save_data(json_data, file_path)
    #
    # def load_preset(
    #     self,
    #     name: str = '',
    #     config: Flare | Flare.Ghost | Flare.Starburst | None = None,
    # ) -> None:
    #     if name:
    #         path = self.storage.decode_path(os.path.join('$PRESET', name))
    #         file_path, filter_string = QtWidgets.QFileDialog.getOpenFileName(
    #             parent=self,
    #             caption='Load Preset',
    #             dir=path,
    #             filter='*.json',
    #         )
    #         if file_path:
    #             json_data = self.storage.load_data(file_path)
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

    def project(self):
        values = self.values()

        values['render']['grid_count'] = values['render']['grid_subdivisions'] + 1
        values['diagram']['grid_count'] = values['diagram']['grid_subdivisions'] + 1

        project = cast(Project, values)

        return project

    def randomize_coatings(self):
        flare = self.flare_config()

        json_data = self.storage.load_data(flare.lens.prescription_path)
        prescription = cast(Prescription, json_data)
        element_count = len(prescription.lens_elements)

        wavelength_range = self._coating_wavelength_range.value
        refractive_range = self._coating_refractive_index_range.value

        coatings = []
        for i in range(element_count):
            coatings.append(
                [
                    random.randint(wavelength_range.width(), wavelength_range.height()),
                    random.uniform(refractive_range.width(), refractive_range.height()),
                ]
            )
        self._coating_tab_data.value = coatings

    def set_project(self, project: Project) -> None:
        values = cast_basic(project)

        values['render']['grid_subdivisions'] = values['render']['grid_count'] - 1
        values['diagram']['grid_subdivisions'] = values['diagram']['grid_count'] - 1

        self.form.blockSignals(True)
        self.set_values(values)
        self.form.blockSignals(False)
        self.parameter_changed.emit(ParameterWidget())

    def _light_image_enable(self, enabled: bool) -> None:
        widgets = self.widgets()

        widgets['flare']['light']['position'].setEnabled(not enabled)
        widgets['flare']['light']['image_sample_resolution'].setEnabled(enabled)
        widgets['flare']['light']['image_samples'].setEnabled(enabled)
