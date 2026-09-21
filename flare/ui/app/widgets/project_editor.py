from qt_parameters import (
    BoolParameter,
    CollapsibleBox,
    ComboParameter,
    EnumParameter,
    FloatParameter,
    IntParameter,
    ParameterEditor,
    ParameterForm,
    ParameterWidget,
    PathParameter,
    PointFParameter,
    PointParameter,
    SizeFParameter,
    SizeParameter,
    TabDataParameter,
)
from qtpy import QtCore, QtWidgets

from flare import api
from flare.api import color
from flare.infrastructure.database import Database

from .base import StateWidget


class ProjectEditor(ParameterEditor, StateWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(name='project', parent=parent)

        self.render_button = None

        self._init_ui()
        self._init_flare()
        self._init_ghost()
        self._init_starburst()
        self._init_diagram()
        self._load()

    def _init_ui(self) -> None:
        self.setWindowTitle('Project Editor')

        # Output
        form = ParameterForm('output')
        self.add_form(form)

        param = EnumParameter('layer')
        param.set_enum(api.Layer)
        param.set_tooltip('Output layer')
        form.add_parameter(param)

        param = PathParameter('path')
        param.set_method(PathParameter.SAVE_FILE)
        param.set_tooltip(
            'Output image path. Use $F4 to replace frame numbers.\n'
            'For example: render.$F4.exr'
        )
        form.add_parameter(param)

        # Render Button
        layout = QtWidgets.QHBoxLayout()
        layout.addStretch()
        self.render_button = QtWidgets.QPushButton('Render to Disk')
        layout.addWidget(self.render_button)
        form.add_layout(layout)

        # Tabs
        self.flare_form = ParameterForm('flare')
        self.ghost_form = ParameterForm('ghost')
        self.starburst_form = ParameterForm('starburst')
        self.diagram_form = ParameterForm('diagram')
        self.add_forms(
            (self.flare_form, self.ghost_form, self.starburst_form, self.diagram_form)
        )

    def _init_flare(self) -> None:
        # Light
        form = ParameterForm('light')
        box = self.flare_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = FloatParameter('intensity')
        param.set_slider_max(1)
        form.add_parameter(param)

        param = ComboParameter('illuminant')
        param.set_items(color.get_illuminants())
        form.add_parameter(param)

        param = PointFParameter('position')
        param.set_decimals(4)
        param.set_tooltip('The position of the light source in NDC space (-1, 1).')
        form.add_parameter(param)

        # Lens
        form = ParameterForm('lens')
        box = self.flare_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = ComboParameter('vendor')
        param.value_changed.connect(self._vendor_changed)
        form.add_parameter(param)

        param = ComboParameter('lens')
        form.add_parameter(param)

        param = ComboParameter('glass')
        form.add_parameter(param)

        coating_form = ParameterForm('coatings')
        coating_form.set_flat(True)
        form.add_form(coating_form)

        param = TabDataParameter('coatings')
        param.set_headers(['Wavelength', 'IOR'])
        param.set_types([int, float])
        param.set_tooltip(
            "Wavelength that each lens element's coating thickness is optimized for. "
            'This controls the colors of the flares.'
        )
        coating_form.add_parameter(param)

        coating_form.add_separator()

        param = PointParameter('wavelength')
        param.set_tooltip(
            'A range in nm for creating random wavelengths in the coating list.'
        )
        coating_form.add_parameter(param)

        param = PointFParameter('ior')
        param.set_label('IOR')
        coating_form.add_parameter(param)

        button = QtWidgets.QPushButton('Randomize')
        button.clicked.connect(self._randomize_coatings)
        coating_form.add_widget(button, column=2)

        param = FloatParameter('abbe_offset')
        param.set_label('Abbe Offset')
        param.set_slider_min(-20)
        param.set_slider_max(20)
        param.set_tooltip(
            'An offset for the abbe number values of the lens elements in the '
            'lens model. This is a experimental way to play around with the quality '
            'of the glass.'
        )
        form.add_parameter(param)

        # Camera
        form = ParameterForm('camera')
        box = self.flare_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = SizeFParameter('sensor_size')
        param.set_ratio_visible(False)
        param.set_tooltip('A larger sensor size will show more of the flare.')
        form.add_parameter(param)

        param = FloatParameter('fstop')
        param.set_line_min(1)
        param.set_slider_min(1)
        param.set_slider_max(22)
        form.add_parameter(param)

        # Raytracing
        form = ParameterForm('raytracing')
        box = self.flare_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = IntParameter('wavelength_count')
        param.set_label('Wavelengths')
        param.set_line_min(1)
        param.set_slider_min(1)
        param.set_tooltip(
            'The amount of wavelengths that get traced through the lens system in a '
            'range of 390nm - 700nm. '
            'Final quality can often be achieved with a value of 5.'
        )
        form.add_parameter(param)

        param = IntParameter('wavelength_sub_count')
        param.set_label('Sub Wavelengths')
        param.set_line_min(1)
        param.set_slider_min(1)
        param.set_tooltip(
            'The amount of sub steps that get rendered between each ray-traced '
            'wavelength. This happens during the rendering stage and interpolates '
            'between the ray-traced wavelengths to generate a smoother transition.'
        )
        form.add_parameter(param)

        param = IntParameter('min_divisions')
        param.set_slider_max(256)
        form.add_parameter(param)

        param = IntParameter('max_divisions')
        param.set_slider_max(256)
        form.add_parameter(param)

        param = FloatParameter('min_area')
        param.set_label('Min. Area')
        param.set_line_min(0)
        param.set_slider_max(1)
        param.set_tooltip(
            'The minimum area of each primitive. The area of the deformed primitives '
            'on the sensor is used to calculate the intensity of the primitive. '
            'Along the edges of fresnel refraction the primitives get very small which '
            'leads to over bright results. '
            'This parameter can be used to creatively lessen some of the artefacts.'
        )
        form.add_parameter(param)

        param = FloatParameter('min_sliver')
        param.set_label('Min. Sliver')
        param.set_line_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('cull_percentage')
        param.set_slider_max(1)
        param.set_line_min(0)
        param.set_line_max(1)
        param.set_tooltip(
            'A percentage for how many of the darkest ghosts to cull. 0.2 means 20% of '
            'the darkest ghosts are culled which speeds up performance.'
        )
        form.add_parameter(param)

        param = BoolParameter('use_aspheric')
        param.set_label('Use Aspheric')
        form.add_parameter(param)

        # Render
        form = ParameterForm('render')
        box = self.flare_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = SizeParameter('resolution')
        param.set_slider_visible(False)
        param.set_ratio_visible(False)
        param.set_tooltip('Resolution of the flare image.')
        form.add_parameter(param)

        param = EnumParameter('supersampling')
        param.set_enum(api.Supersampling)
        param.set_formatter(self._format_supersampling)
        form.add_parameter(param)

        # Debug
        form = ParameterForm('debug')
        box = self.flare_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = IntParameter('ghost')
        param.set_slider_max(100)
        form.add_parameter(param, checkable=True)

        param = BoolParameter('wireframe')
        form.add_parameter(param)

    def _init_ghost(self) -> None:
        # Aperture
        form = ParameterForm('aperture')
        box = self.ghost_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)
        self._init_aperture_form(form)

        # Diffraction
        form = ParameterForm('diffraction')
        box = self.ghost_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = FloatParameter('distance')
        param.set_slider_max(10)
        form.add_parameter(param)

        param = FloatParameter('vignette')
        param.set_slider_max(0.5)
        form.add_parameter(param)

        # Render
        form = ParameterForm('render')
        box = self.ghost_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = IntParameter('resolution')
        param.set_slider_visible(False)
        param.set_line_min(1)
        param.set_tooltip('Resolution of the ghost.')
        form.add_parameter(param)

    def _init_starburst(self) -> None:
        # Aperture
        form = ParameterForm('aperture')
        box = self.starburst_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        self._init_aperture_form(form)

        # Camera
        form = ParameterForm('camera')
        box = self.starburst_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = BoolParameter('scale_with_fstop')
        param.set_tooltip('Scale the starburst pattern with the f-stop of the lens.')
        form.add_parameter(param)

        param = FloatParameter('scale')
        param.set_line_min(0)
        param.set_slider_min(0)
        param.set_slider_max(10)
        param.set_tooltip('Additional multiplier for the starburst pattern size.')
        form.add_parameter(param)

        # param = BoolParameter('occlusion')
        # form.add_parameter(param)

        # Diffraction
        form = ParameterForm('diffraction')
        box = self.starburst_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = FloatParameter('intensity')
        param.set_line_min(0)
        param.set_tooltip('Overall brightness.')
        form.add_parameter(param)

        param = FloatParameter('blur')
        param.set_line_min(0)
        form.add_parameter(param)

        param = FloatParameter('rotation')
        param.set_slider_max(180)
        param.set_tooltip('Rotational blur during sampling.')
        form.add_parameter(param)

        param = FloatParameter('rotation_weight')
        param.set_line_min(0)
        param.set_slider_max(2)
        param.set_tooltip(
            'The weighting for the rotation. '
            'Equal weighted = 1, weighted towards the inside = 0, weighted towards '
            'outside = 2.'
        )
        form.add_parameter(param)

        param = FloatParameter('vignetting')
        param.set_line_min(0)
        param.set_line_max(1)
        form.add_parameter(param)

        # Render
        form = ParameterForm('render')
        box = self.starburst_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = IntParameter('resolution')
        param.set_slider_visible(False)
        param.set_line_min(1)
        param.set_tooltip('Resolution of the starburst pattern.')
        form.add_parameter(param)

        param = IntParameter('samples')
        param.set_slider_visible(False)
        param.set_line_min(0)
        param.set_line_max(12)
        param.set_tooltip(
            'The number of samples. High quality renders might need up to 11 samples.'
        )
        form.add_parameter(param)

    def _init_diagram(self) -> None:
        # Raytracing
        form = ParameterForm('raytracing')
        box = self.diagram_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = IntParameter('ghost')
        param.set_slider_max(100)
        form.add_parameter(param)

        param = IntParameter('divisions')
        param.set_slider_max(128)
        form.add_parameter(param)

        # Render
        form = ParameterForm('render')
        box = self.diagram_form.add_form(form)
        box.set_box_style(CollapsibleBox.Style.BUTTON)

        param = SizeParameter('resolution')
        param.set_slider_visible(False)
        param.set_ratio_visible(False)
        form.add_parameter(param)

    @staticmethod
    def _init_aperture_form(parent: ParameterForm) -> None:
        # Shape
        form = ParameterForm('shape')
        parent.add_form(form)

        param = SizeFParameter('size')
        param.set_slider_min(0)
        param.set_slider_max(1)
        param.set_keep_ratio(True)
        form.add_parameter(param)

        param = IntParameter('blades')
        param.set_line_min(2)
        param.set_slider_min(2)
        param.set_slider_max(12)
        form.add_parameter(param)

        param = FloatParameter('roundness')
        param.set_value(0.1)
        param.set_slider_min(-0.1)
        form.add_parameter(param)

        param = FloatParameter('rotation')
        param.set_slider_min(0)
        param.set_slider_max(360)
        param.set_tooltip('Rotation in degrees.')
        form.add_parameter(param)

        param = FloatParameter('softness')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        # Grating
        form = ParameterForm('grating')
        parent.add_form(form)

        param = FloatParameter('strength')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('density')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('length')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('width')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('softness')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        # Scratches
        form = ParameterForm('scratches')
        parent.add_form(form)

        param = FloatParameter('strength')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('density')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('length')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('width')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('rotation')
        param.set_slider_min(0)
        param.set_slider_max(360)
        form.add_parameter(param)

        param = FloatParameter('rotation_variation')
        param.set_label('Variation')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('softness')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = SizeFParameter('parallax')
        param.set_line_min(0)
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        # Dust
        form = ParameterForm('dust')
        parent.add_form(form)

        param = FloatParameter('strength')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('density')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('radius')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('softness')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = SizeFParameter('parallax')
        param.set_line_min(0)
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        # Image
        form = ParameterForm('image')
        parent.add_form(form)

        param = FloatParameter('strength')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = PathParameter('file')
        param.set_method(PathParameter.Method.OPEN_FILE)
        # param.dir_fallback = storage.decode_path('$APT')
        param.set_tooltip(
            'The path to the image file. Variables such as $APT can be used. '
            'For more information see documentation. (To come...)'
        )
        form.add_parameter(param)

        param = SizeFParameter('size')
        param.set_slider_min(0)
        param.set_slider_max(1)
        param.set_default(QtCore.QSize(1, 1))
        param.set_keep_ratio(True)
        form.add_parameter(param)

        param = FloatParameter('black')
        param.set_slider_min(0)
        param.set_slider_max(1)
        form.add_parameter(param)

        param = FloatParameter('white')
        param.set_slider_min(0)
        param.set_slider_max(1)
        param.set_default(1)
        form.add_parameter(param)

    def get_project(self) -> api.Project:
        """Return the project from the Form's values."""

        values = self.values()

        project = api.Project()
        project = project.model_validate(values)

        return project

    def set_project(self, project: api.Project) -> None:
        """Set the Form's values from a Project."""

        values = project.model_dump()

        self.blockSignals(True)
        self.set_values(values)
        self.blockSignals(False)
        self.parameter_changed.emit(ParameterWidget())

    def _randomize_coatings(self) -> None:
        """Randomize the coatings of a LensModel."""

        project = self.get_project()
        db = Database()
        lens = db.get_lens(project.flare.lens.vendor, project.flare.lens.lens)
        if not lens:
            return

        wavelength_range = (
            project.flare.lens.wavelength.x(),
            project.flare.lens.wavelength.y(),
        )
        ior_range = (
            project.flare.lens.ior.x(),
            project.flare.lens.ior.y(),
        )

        coatings = lens.get_coatings(wavelength_range, ior_range)
        param = self.flare_form.parameter('lens.coatings')
        if isinstance(param, TabDataParameter):
            param.set_value(coatings)

    def _load(self) -> None:
        """Load data for the parameters."""

        db = Database()
        param = self.flare_form.parameter('lens.vendor')
        if isinstance(param, ComboParameter):
            vendors = db.get_lens_vendors()
            param.set_items(vendors)

        param = self.flare_form.parameter('lens.glass')
        if isinstance(param, ComboParameter):
            vendors = db.get_material_vendors()
            param.set_items(vendors)

    def _vendor_changed(self, vendor: str) -> None:
        db = Database()
        lenses = db.get_lenses()
        vendor_lenses = [lens for lens in lenses if lens.vendor == vendor]
        param = self.flare_form.parameter('lens.lens')
        if isinstance(param, ComboParameter):
            names = tuple(lens.name for lens in vendor_lenses)
            param.set_items(names)

    @staticmethod
    def _format_supersampling(member: api.Supersampling) -> str:
        """Return the display label for a supersampling option."""

        labels = {
            api.Supersampling.NONE: 'None',
            api.Supersampling.SSAA_2X: '2x SSAA',
        }
        return labels[member]
