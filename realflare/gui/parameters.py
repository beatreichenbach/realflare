from __future__ import annotations

import random

from PySide2 import QtWidgets, QtCore

from qt_extensions import helper
from qt_extensions.parameters import (
    BoolParameter,
    EnumParameter,
    FloatParameter,
    IntParameter,
    ParameterBox,
    ParameterEditor,
    ParameterWidget,
    PathParameter,
    PointFParameter,
    PointParameter,
    SizeFParameter,
    SizeParameter,
    StringParameter,
    TabDataParameter,
)
from qt_extensions.typeutils import cast, basic
from realflare.api import lens, glass
from realflare.api.data import AntiAliasing, RenderElement, Project, RealflareError
from realflare.api.tasks import opencl
from realflare.storage import Storage
from realflare.utils import ocio

storage = Storage()


class ProjectEditor(ParameterEditor):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.forms = {}

        self.render_action = None

        self._init_output_group()
        self._init_tabs()
        self._init_flare_group()
        self._init_rendering_group()
        self._init_diagram_group()
        # self._init_actions()

        # init defaults
        default_config = Project()
        values = basic(default_config)
        self.set_values(values, attr='default')

    def _init_tabs(self) -> None:
        tab_widget = self.add_tab_group(
            names=('lens_flare', 'render', 'diagram'),
        )
        self.tabs = tab_widget.tabs

    def _init_output_group(self) -> None:
        box = self.add_group('output')
        box.set_box_style(ParameterBox.SIMPLE)
        form = box.form

        # actions
        self.render_to_disk = QtWidgets.QAction('Render to Disk', self)
        button = QtWidgets.QToolButton()
        button.setDefaultAction(self.render_to_disk)
        form.add_widget(button, column=2)

        # parameters
        def formatter(text: str):
            if text == 'FLARE_STARBURST':
                text = 'Flare + Starburst'
            return helper.title(text)

        parm = EnumParameter('element')
        parm.set_enum(RenderElement)
        parm.set_tooltip('Output element')
        parm.set_formatter(formatter)
        form.add_parameter(parm)

        parm = PathParameter('path')
        parm.set_method(PathParameter.SAVE_FILE)
        parm.set_tooltip(
            'Output image path. Use $F4 to replace frame numbers.\n'
            'For example: render.$F4.exr'
        )
        form.add_parameter(parm)

        parm = StringParameter('colorspace')
        parm.set_menu(ocio.colorspace_names())
        parm.set_tooltip('Colorspace from the OCIO config.\nFor example: ACES - ACEScg')
        form.add_parameter(parm)

        parm = BoolParameter('split_files')
        parm.set_tooltip(
            'Multilayer exr files are not supported yet. Enabling this '
            'parameter will split different layers into separate files.'
        )
        form.add_parameter(parm)

    def _init_flare_group(self) -> None:
        self.tabs['lens_flare'].create_hierarchy = False

        # flare
        box = self.tabs['lens_flare'].add_group('flare')
        box.set_box_style(ParameterBox.SIMPLE)
        box.set_collapsible(False)
        form = box.form
        self.forms[form.name] = form

        # light
        box = form.add_group('light')
        box.set_box_style(ParameterBox.BUTTON)
        light_group = box.form

        parm = FloatParameter(name='intensity')
        parm.set_slider_max(1)
        light_group.add_parameter(parm)

        light_group.add_separator()

        parm = PointFParameter(name='position')
        parm.set_decimals(2)
        parm.set_tooltip('The position of the light source in NDC space (-1, 1).')
        light_group.add_parameter(parm)

        parm = PathParameter(name='image_file')
        parm.set_method(PathParameter.Method.OPEN_FILE)
        parm.set_dir_fallback(storage.decode_path('$RES'))
        parm.set_tooltip(
            "The path to the image file. Variables such as $RES can be used. "
            "For more information see documentation. (To come...)"
        )
        light_group.add_parameter(parm, checkable=True)
        parm.enabled_changed.connect(self._light_image_enabled)

        parm = IntParameter(name='image_sample_resolution')
        parm.set_line_min(1)
        parm.set_slider_visible(False)
        parm.setEnabled(False)
        light_group.add_parameter(parm)

        parm = IntParameter(name='image_samples')
        parm.set_line_min(1)
        parm.set_slider_visible(False)
        parm.setEnabled(False)
        light_group.add_parameter(parm)

        parm = BoolParameter('show_image')
        parm.setEnabled(False)
        light_group.add_parameter(parm)

        # lens
        box = form.add_group('lens')
        box.set_box_style(ParameterBox.BUTTON)
        lens_group = box.form

        parm = SizeFParameter(name='sensor_size')
        parm.set_ratio_visible(False)
        parm.set_tooltip(
            'The sensor size of the camera. A larger sensor size will show '
            'more of the flare.'
        )
        lens_group.add_parameter(parm)

        parm = FloatParameter(name='fstop')
        parm.set_label('F-Stop')
        parm.set_slider_max(32)
        lens_group.add_parameter(parm)

        parm = StringParameter(name='lens_model_path')
        parm.set_label('Lens Model')
        parm.set_menu(lens.model_paths())
        parm.set_tooltip(
            'The path to the lens model file (\'*.json\'). Variables such as $MODEL '
            'can be used. For more information see documentation. (To come...)'
        )
        lens_group.add_parameter(parm)

        lens_group.add_separator()

        parm = StringParameter(name='glasses_path')
        parm.set_label('Glass Make')
        parm.set_menu(glass.manufacturers())
        parm.set_tooltip(
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
        parm.set_slider_min(-20)
        parm.set_slider_max(20)
        parm.set_tooltip(
            'An offset for the abbe number values of the lens elements in the lens model.'
            ' This is a experimental way to play around with the quality of the glass.'
        )
        lens_group.add_parameter(parm)

        lens_group.add_separator()

        parm = TabDataParameter(name='coating')
        parm.set_headers(['wavelength'])
        parm.set_types([int])
        parm.set_tooltip(
            'Wavelength that each lens element\'s coating thickness is optimized for. '
            'This controls the colors of the flares.'
        )
        lens_group.add_parameter(parm)
        self._coating_tab_data = parm

        parm = PointParameter(name='coating_range')
        parm.set_tooltip(
            'A range in nm for creating random wavelengths in the coating list.'
        )
        lens_group.add_parameter(parm)
        self._coating_range = parm

        action = QtWidgets.QAction('Randomize', self)
        action.triggered.connect(lambda: self.randomize_coatings())
        button = QtWidgets.QToolButton()
        button.setDefaultAction(action)
        lens_group.add_widget(button, column=2)

        parm = FloatParameter(name='coating_min_ior')
        parm.set_label('Min. Coating IOR')
        parm.set_line_min(1)
        parm.set_slider_max(1)
        parm.set_slider_max(2)
        parm.set_tooltip(
            'The minimum IOR for all lens coatings. '
            'Higher IOR will make coatings less effective and flares more pronounced. '
            'Coatings made from materials with lower IOR are harder '
            'to manufacture and expensive. '
        )
        lens_group.add_parameter(parm)

        lens_group.add_separator()

        parm = FloatParameter(name='min_area')
        parm.set_line_min(0)
        parm.set_slider_max(1)
        parm.set_tooltip(
            'The minimum area of each primitive. The area of the deformed primitives on '
            'the sensor is used to calculate the intensity of the primitive. '
            'Along the edges of fresnel refraction the primitives get very small which '
            'leads to over bright results. '
            'This parameter can be used to creatively lessen some of the artefacts.'
        )
        lens_group.add_parameter(parm)

        # ghost aperture
        box = form.add_group('ghost_aperture')
        box.set_box_style(ParameterBox.BUTTON)
        ghost_aperture_group = box.form

        self._init_aperture_group(ghost_aperture_group)

        # ghost
        box = form.add_group('ghost')
        box.set_box_style(ParameterBox.BUTTON)
        ghost_group = box.form
        self.forms[ghost_group.name] = ghost_group

        parm = FloatParameter(name='fstop')
        parm.set_label('F-Stop')
        parm.set_slider_min(0)
        parm.set_slider_max(32)
        parm.set_tooltip(
            'F-Stop that controls the strength of the ringing pattern visible '
            'on ghosts.'
        )
        ghost_group.add_parameter(parm)

        # starburst aperture
        box = form.add_group('starburst_aperture')
        box.set_box_style(ParameterBox.BUTTON)
        starburst_aperture_group = box.form

        self._init_aperture_group(starburst_aperture_group)

        # starburst
        box = form.add_group('starburst')
        box.set_box_style(ParameterBox.BUTTON)
        starburst_group = box.form
        self.forms[starburst_group.name] = starburst_group

        parm = FloatParameter(name='intensity')
        parm.set_tooltip(
            'A multiplier on the overall brightness of the starburst pattern.'
        )
        starburst_group.add_parameter(parm)

        parm = SizeFParameter(name='scale')
        parm.set_slider_max(2)
        starburst_group.add_parameter(parm)

        parm = FloatParameter(name='distance')
        parm.set_line_min(0)
        parm.set_slider_max(1)
        parm.set_tooltip(
            'The distance in mm away from the aperture where the far-field pattern '
            'is being recorded. This changes the perceived size of the starburst.'
        )
        starburst_group.add_parameter(parm)

        parm = FloatParameter(name='blur')
        parm.set_tooltip('Blur of the starburst.')
        starburst_group.add_parameter(parm)

        parm = FloatParameter(name='rotation')
        parm.set_slider_max(180)
        parm.set_tooltip('Random rotation during sampling.')
        starburst_group.add_parameter(parm)

        parm = FloatParameter(name='rotation_weight')
        parm.set_line_min(0)
        parm.set_slider_max(2)
        parm.set_tooltip(
            'The weighting for the rotation. '
            'Equal weighted = 1, weighted towards the inside = 0, weighted towards '
            'outside = 2.'
        )
        starburst_group.add_parameter(parm)

        parm = PointFParameter(name='vignetting')
        parm.set_tooltip(
            'A gradient to fade out the starburst towards the edges of the frame. '
            'This prevents visible borders of the starburst frame.'
        )
        starburst_group.add_parameter(parm, checkable=True)

    def _init_rendering_group(self) -> None:
        # renderer
        box = self.tabs['render'].add_group('renderer')
        box.set_box_style(ParameterBox.BUTTON)
        renderer_group = box.form
        renderer_group.create_hierarchy = False

        parm = SizeParameter('resolution')
        parm.set_slider_visible(False)
        parm.set_ratio_visible(False)
        parm.set_tooltip('Resolution of the flare image.')
        renderer_group.add_parameter(parm)

        parm = IntParameter('bin_size')
        parm.set_slider_visible(False)
        parm.set_tooltip(
            'Bin size of the renderer. Larger values will require less memory '
            'but increase render time.'
        )
        renderer_group.add_parameter(parm)

        parm = EnumParameter('anti_aliasing')
        parm.set_label('Anti Aliasing')
        parm.set_enum(AntiAliasing)
        parm.set_formatter(AntiAliasing.format)
        parm.set_tooltip('Super sampling multiplier for anti-aliasing.')
        renderer_group.add_parameter(parm)

        # rays
        box = self.tabs['render'].add_group('rays')
        box.set_box_style(ParameterBox.BUTTON)
        rays_group = box.form
        rays_group.create_hierarchy = False

        parm = IntParameter('wavelength_count')
        parm.set_label('Wavelengths')
        parm.set_line_min(1)
        parm.set_slider_min(1)
        parm.set_tooltip(
            'The amount of wavelengths that get traced through the lens system in a '
            'range of 390nm - 700nm. '
            'Final quality can often be achieved with a value of 5.'
        )
        rays_group.add_parameter(parm)

        parm = IntParameter('wavelength_sub_count')
        parm.set_label('Wavelength Substeps')
        parm.set_line_min(1)
        parm.set_slider_min(1)
        parm.set_tooltip(
            'The amount of sub steps that get rendered between each ray-traced '
            'wavelength. This happens during the rendering stage and interpolates '
            'between the ray-traced wavelengths to generate a smoother transition.'
        )
        rays_group.add_parameter(parm)

        parm = IntParameter('grid_subdivisions')
        parm.set_slider_max(256)
        parm.set_tooltip(
            'The subdivisions of the grid that gets traced through the lens system. '
            'The more distortion the lens produces, the more subdivisions are needed. '
            'Good results can be achieved at a range of 64-128 rarely needing values up '
            'to 200.'
        )
        rays_group.add_parameter(parm)

        parm = FloatParameter('grid_length')
        parm.set_slider_max(100)
        parm.set_tooltip(
            'Length in mm of the grid that gets traced through the lens system. '
            'This value is roughly the size of the diameter of the lens. '
            'It\'s best to keep this value as small as possible. Values too small will '
            'lead to cut off shapes in the render.'
        )
        rays_group.add_parameter(parm)

        parm = FloatParameter('cull_percentage')
        parm.set_slider_max(1)
        parm.set_line_min(0)
        parm.set_line_max(1)
        parm.set_tooltip(
            'A percentage for how many of the darkest ghosts to cull. '
            '0.2 means 20% of the darkest ghosts are culled which speeds up performance.'
        )
        rays_group.add_parameter(parm)

        parm = IntParameter('debug_ghost')
        parm.set_slider_max(100)
        rays_group.add_parameter(parm, checkable=True)

        # starburst
        box = self.tabs['render'].add_group('starburst')
        box.set_box_style(ParameterBox.BUTTON)
        starburst_group = box.form

        parm = SizeParameter('resolution')
        parm.set_slider_visible(False)
        parm.set_ratio_visible(False)
        parm.set_tooltip('Resolution of the starburst pattern.')
        starburst_group.add_parameter(parm)

        parm = IntParameter('samples')
        parm.set_slider_visible(False)
        parm.set_tooltip(
            'Number of samples. High quality renders might need up to 2048 samples.'
        )
        starburst_group.add_parameter(parm)

        # ghost
        box = self.tabs['render'].add_group('ghost')
        box.set_box_style(ParameterBox.BUTTON)
        ghost_group = box.form

        parm = SizeParameter('resolution')
        parm.set_slider_visible(False)
        parm.set_ratio_visible(False)
        parm.set_tooltip('Resolution of the ghost.')
        ghost_group.add_parameter(parm)

        # system
        box = self.tabs['render'].add_group('system')
        box.set_box_style(ParameterBox.BUTTON)
        system_group = box.form
        system_group.create_hierarchy = False

        parm = StringParameter('device')
        parm.set_menu(opencl.devices())
        system_group.add_parameter(parm)

    def _init_diagram_group(self) -> None:
        box = self.tabs['diagram'].add_group('renderer')
        box.set_box_style(ParameterBox.BUTTON)
        diagram_renderer_group = box.form
        diagram_renderer_group.create_hierarchy = False

        parm = SizeParameter('resolution')
        parm.set_slider_visible(False)
        parm.set_ratio_visible(False)
        diagram_renderer_group.add_parameter(parm)

        box = self.tabs['diagram'].add_group('rays')
        box.set_box_style(ParameterBox.BUTTON)
        diagram_rays_group = box.form
        diagram_rays_group.create_hierarchy = False

        parm = IntParameter('debug_ghost')
        parm.set_slider_max(100)
        diagram_rays_group.add_parameter(parm)

        parm = FloatParameter('light_position')
        parm.set_slider_min(-1)
        parm.set_slider_max(1)
        diagram_rays_group.add_parameter(parm)

        parm = IntParameter('grid_subdivisions')
        parm.set_slider_max(256)
        diagram_rays_group.add_parameter(parm)

        parm = FloatParameter('grid_length')
        parm.set_slider_max(100)
        diagram_rays_group.add_parameter(parm)

        parm = IntParameter('column_offset')
        parm.set_slider_min(-20)
        parm.set_slider_max(20)
        diagram_rays_group.add_parameter(parm)

    # noinspection PyMethodMayBeStatic
    def _init_aperture_group(self, parent: ParameterEditor):
        # shape
        box = parent.add_group('shape')
        box.set_box_style(ParameterBox.SIMPLE)
        shape_group = box.form

        parm = SizeFParameter(name='size')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        parm.keep_ratio = True
        shape_group.add_parameter(parm)

        parm = IntParameter(name='blades')
        parm.set_line_min(2)
        parm.set_slider_min(2)
        parm.set_slider_max(12)
        shape_group.add_parameter(parm)

        parm = FloatParameter(name='roundness')
        parm.set_value(0.1)
        parm.set_slider_min(-0.1)
        shape_group.add_parameter(parm)

        parm = FloatParameter(name='rotation')
        parm.set_slider_min(0)
        parm.set_slider_max(360)
        parm.set_tooltip('Rotation in degrees.')
        shape_group.add_parameter(parm)

        parm = FloatParameter(name='softness')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        shape_group.add_parameter(parm)

        # grating
        box = parent.add_group('grating')
        box.set_box_style(ParameterBox.SIMPLE)
        grating_group = box.form

        parm = FloatParameter(name='strength')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        grating_group.add_parameter(parm)

        parm = FloatParameter(name='density')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        grating_group.add_parameter(parm)

        parm = FloatParameter(name='length')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        grating_group.add_parameter(parm)

        parm = FloatParameter(name='width')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        grating_group.add_parameter(parm)

        parm = FloatParameter(name='softness')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        grating_group.add_parameter(parm)

        # scratches
        box = parent.add_group('scratches')
        box.set_box_style(ParameterBox.SIMPLE)
        scratches_group = box.form

        parm = FloatParameter(name='strength')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='density')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='length')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='width')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='rotation')
        parm.set_slider_min(0)
        parm.set_slider_max(360)
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='rotation_variation')
        parm.set_label('Variation')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        scratches_group.add_parameter(parm)

        parm = FloatParameter(name='softness')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        scratches_group.add_parameter(parm)

        parm = SizeFParameter(name='parallax')
        parm.set_line_min(0)
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        scratches_group.add_parameter(parm)

        # dust
        box = parent.add_group('dust')
        box.set_box_style(ParameterBox.SIMPLE)
        dust_group = box.form

        parm = FloatParameter(name='strength')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        dust_group.add_parameter(parm)

        parm = FloatParameter(name='density')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        dust_group.add_parameter(parm)

        parm = FloatParameter(name='radius')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        dust_group.add_parameter(parm)

        parm = FloatParameter(name='softness')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        dust_group.add_parameter(parm)

        parm = SizeFParameter(name='parallax')
        parm.set_line_min(0)
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        dust_group.add_parameter(parm)

        # image
        box = parent.add_group('image')
        box.set_box_style(ParameterBox.SIMPLE)
        image_group = box.form

        parm = FloatParameter(name='strength')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        image_group.add_parameter(parm)

        parm = PathParameter(name='file')
        parm.method = PathParameter.Method.OPEN_FILE
        parm.dir_fallback = storage.decode_path('$APT')
        parm.set_tooltip(
            "The path to the image file. Variables such as $APT can be used. "
            "For more information see documentation. (To come...)"
        )
        image_group.add_parameter(parm)

        parm = SizeFParameter(name='size')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        parm.set_default(QtCore.QSize(1, 1))
        parm.set_keep_ratio(True)
        image_group.add_parameter(parm)

        parm = FloatParameter(name='threshold')
        parm.set_slider_min(0)
        parm.set_slider_max(1)
        image_group.add_parameter(parm)

    def _init_actions(self) -> None:
        for name in ('flare', 'starburst', 'ghost'):
            group = self.forms[name]
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

        values['flare']['lens']['coating'] = [
            v[0] for v in values['flare']['lens']['coating']
        ]
        values['render']['grid_count'] = values['render']['grid_subdivisions'] + 1
        values['diagram']['grid_count'] = values['diagram']['grid_subdivisions'] + 1

        project = cast(Project, values)

        return project

    def randomize_coatings(self) -> None:
        project = self.project()
        try:
            model = lens.model_from_path(project.flare.lens.lens_model_path)
        except RealflareError:
            return
        element_count = len(model.lens_elements)

        wavelength_range = self._coating_range.value()

        coatings = []
        for i in range(element_count):
            wavelength = random.randint(wavelength_range.x(), wavelength_range.y())
            coatings.append([wavelength])
        self._coating_tab_data.set_value(coatings)

    def set_project(self, project: Project) -> None:
        values = basic(project)

        values['flare']['lens']['coating'] = [
            (v,) for v in values['flare']['lens']['coating']
        ]
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
        widgets['flare']['light']['show_image'].setEnabled(enabled)

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
