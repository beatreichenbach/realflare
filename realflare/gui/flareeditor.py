import dataclasses
import logging
import os
import random
from functools import partial

from PySide2 import QtWidgets, QtCore, QtGui

from realflare.api.data import Flare, Prescription
from realflare.gui.settings import Settings
from qt_extensions.properties import (
    PropertyEditor,
    IntProperty,
    FloatProperty,
    PathProperty,
    ColorProperty,
    TabDataProperty,
    SizeProperty,
    SizeFProperty,
    PointFProperty,
    StringProperty,
    PropertyWidget,
    BoolProperty,
)
from qt_extensions.box import CollapsibleBox
from qt_extensions.typeutils import cast, cast_json

from realflare.api import data


class FlareEditor(PropertyEditor):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.settings = Settings()
        self.groups = {}

        self._init_editor()
        self._init_actions()

    def _init_editor(self) -> None:
        aperture_dir = self.settings.decode_path('$APT')

        # flare
        flare_group = self.add_group('flare', style=CollapsibleBox.Style.SIMPLE)
        flare_group.create_hierarchy = False
        self.groups[flare_group.name] = flare_group

        # light
        light_group = flare_group.add_group(
            'light', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        light_group.create_hierarchy = False

        prop = FloatProperty(name='light_intensity')
        prop.label = 'Intensity'
        prop.tooltip = 'A multiplier on the overall brightness of the lens flare. Currently not used.'
        prop.setEnabled(False)
        light_group.add_property(prop)

        prop = ColorProperty(name='light_color')
        prop.label = 'Color'
        prop.tooltip = (
            'A global multiplier on the color of the lens flare. Currently not used.'
        )
        prop.setEnabled(False)
        light_group.add_property(prop)

        prop = PointFProperty(name='light_position')
        prop.label = 'Position'
        prop.decimals = 2
        prop.tooltip = 'The position of the light source in NDC space (-1, 1).'
        light_group.add_property(prop)

        # light image
        light_image_group = light_group.add_group(
            'image', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )
        light_image_group.create_hierarchy = False

        prop = PathProperty(name='image_file')
        prop.label = 'File'
        prop.method = PathProperty.Method.OPEN_FILE
        prop.dir_fallback = aperture_dir
        prop.tooltip = (
            "The path to the image file. Variables such as $RES can be used. "
            "For more information see documentation. (To come...)"
        )
        light_image_group.add_property(prop)

        prop = FloatProperty(name='image_threshold')
        prop.label = 'Threshold'
        prop.line_min = 0
        prop.slider_max = 1
        light_image_group.add_property(prop)

        prop = IntProperty(name='image_samples')
        prop.label = 'Samples'
        prop.line_min = 1
        prop.slider_visible = False
        light_image_group.add_property(prop)

        prop = BoolProperty(name='image_show_sample')
        prop.label = 'Show Samples'
        light_image_group.add_property(prop)

        # lens
        lens_group = flare_group.add_group(
            'lens', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        self.groups[lens_group.name] = lens_group

        prop = SizeProperty(name='sensor_size')
        prop.ratio_visible = False
        prop.tooltip = 'The sensor size of the camera. A larger sensor size will show more of the flare.'
        lens_group.add_property(prop)

        prop = StringProperty(name='prescription_path')
        prop.label = 'Lens Model'
        prop.menu = self.settings.load_lens_models()
        prop.tooltip = (
            "The path to the lens model file ('*.json'). Variables such as $MODEL can be used. "
            "For more information see documentation. (To come...)"
        )
        lens_group.add_property(prop)

        prop = StringProperty(name='glasses_path')
        prop.label = 'Glass Make'
        prop.menu = self.settings.load_glass_makes()
        prop.tooltip = (
            'A path to a folder with glass files (\'.yml\'). '
            'The make of the glasses used for lens element lookup. '
            'Each lens element has a refractive index and abbe number that is used to '
            'look up the closest glass in the database. The glass provides a Sellmeier equation '
            'that maps wavelengths to refractive index. The quality of the glass is responsible '
            'for the amount of dispersion. Variables such as $GLASS can be used. '
        )
        lens_group.add_property(prop)

        prop = FloatProperty(name='abbe_nr_adjustment')
        prop.slider_min = -20
        prop.slider_max = 20
        prop.tooltip = (
            'An offset for the abbe number values of the lens elements in the lens model. '
            'This is a experimental way to play around with the quality of the glass.'
        )
        lens_group.add_property(prop)

        prop = FloatProperty(name='min_area')
        prop.line_min = 0
        prop.slider_max = 1
        prop.tooltip = (
            'The minimum area of each primitive. The area of the deformed primitives on the sensor is used '
            'to calculate the intensity of the primitive. Along the edges of fresnel refraction the primitives '
            'get very small which leads to over bright results. This parameter can be used to creatively lessen '
            'some of the artefacts.'
        )
        lens_group.add_property(prop)

        # coating
        coating_group = lens_group.add_group(
            'coating', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )
        coating_group.create_hierarchy = False

        prop = TabDataProperty(name='coating_lens_elements')
        prop.label = 'Lens Elements'
        prop.headers = ['wavelength', 'refractive_index']
        prop.types = [int, float]
        prop.decimals = 2
        prop.tooltip = (
            'Lens Coating for each lens element. A lens coating consists of two parameters, '
            'a wavelength in nm that the coating is optimized for (thickness = lambda / 4) and the '
            'material of the coating (refractive index). The optimal refractive index is n ≈ 1.23. '
            'However materials with such low refractive indices are hard to find or expensive. '
            'A common material is MgF2 with n = 1.38.'
        )
        coating_group.add_property(prop)
        self._coating_tab_data = prop

        coating_group.add_separator()

        prop = SizeProperty(name='random_wavelength_range')
        prop.keep_ratio = False
        prop.ratio_visible = False
        prop.line_min = 390
        prop.line_max = 700
        prop.default = QtCore.QSize(prop.line_min, prop.line_max)
        prop.tooltip = (
            'A range in nm for creating random wavelengths in the coating list.'
        )
        coating_group.add_property(prop)
        self._coating_wavelength_range = prop

        prop = SizeFProperty(name='random_refractive_index_range')
        prop.keep_ratio = False
        prop.ratio_visible = False
        prop.line_min = 1
        prop.line_max = 2
        prop.decimals = 2
        prop.default = QtCore.QSizeF(prop.line_min, prop.line_max)
        prop.tooltip = (
            'A range for creating random refractive indices in the coating list.'
        )
        coating_group.add_property(prop)
        self._coating_refractive_index_range = prop

        randomize_button = QtWidgets.QPushButton('Randomize')
        randomize_button.pressed.connect(lambda: self.randomize_coatings())
        coating_group.add_widget(randomize_button, column=2, column_span=1)

        # starburst
        starburst_group = flare_group.add_group(
            'starburst', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        self.groups[starburst_group.name] = starburst_group

        # starburst aperture
        starburst_aperture_group = starburst_group.add_group(
            'aperture', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        prop = FloatProperty(name='fstop')
        prop.label = 'F-Stop'
        prop.slider_min = 0
        prop.slider_max = 32
        prop.tooltip = (
            'The F-Stop of the aperture. This controls the size of the aperture.'
        )
        starburst_aperture_group.add_property(prop)

        prop = PathProperty(name='file')
        prop.method = PathProperty.Method.OPEN_FILE
        prop.dir_fallback = aperture_dir
        prop.tooltip = (
            "The path to the image file. Variables such as $APT can be used. "
            "For more information see documentation. (To come...)"
        )
        starburst_aperture_group.add_property(prop)

        prop = IntProperty(name='blades')
        prop.slider_min = 1
        prop.slider_max = 12
        prop.line_min = 1
        prop.tooltip = 'Number of blades for the aperture.'
        starburst_aperture_group.add_property(prop)

        prop = FloatProperty(name='rotation')
        prop.slider_min = -180
        prop.slider_max = 180
        prop.tooltip = 'Rotation in degrees of the aperture. Currently not used.'
        prop.setEnabled(False)
        starburst_aperture_group.add_property(prop)

        prop = FloatProperty(name='corner_radius')
        prop.slider_min = 0
        prop.slider_max = 1
        prop.tooltip = 'Corner radius for blades. Currently not used.'
        prop.setEnabled(False)
        starburst_aperture_group.add_property(prop)

        prop = FloatProperty(name='softness')
        prop.slider_min = 0
        prop.slider_max = 1
        prop.tooltip = 'Softness of the aperture.'
        starburst_aperture_group.add_property(prop)

        prop = FloatProperty(name='dust_amount')
        prop.tooltip = 'Amount of dust particles. Currently not used.'
        prop.setEnabled(False)
        starburst_aperture_group.add_property(prop)

        prop = FloatProperty(name='scratches_amount')
        prop.tooltip = 'Amount of scratches. Currently not used.'
        prop.setEnabled(False)
        starburst_aperture_group.add_property(prop)

        prop = FloatProperty(name='grating_amount')
        prop.tooltip = (
            'Amount of grating along the edges of the aperture. '
            'This can be used to generate rainbow circles. Currently not used.'
        )
        prop.setEnabled(False)
        starburst_aperture_group.add_property(prop)

        # starburst

        prop = FloatProperty(name='intensity')
        prop.tooltip = (
            'A multiplier on the overall brightness of the starburst pattern.'
        )
        starburst_group.add_property(prop)

        prop = FloatProperty(name='lens_distance')
        prop.line_min = 0.001
        prop.slider_max = 1
        prop.tooltip = (
            'The distance in mm away from the aperture where the far-field pattern '
            'is being recorded. This changes the perceived size of the starburst.'
        )
        starburst_group.add_property(prop)

        prop = FloatProperty(name='blur')
        prop.tooltip = 'Blur of the starburst.'
        starburst_group.add_property(prop)

        prop = FloatProperty(name='rotation')
        prop.slider_max = 2
        prop.tooltip = 'Random rotation during sampling (in radians?).'
        starburst_group.add_property(prop)

        prop = FloatProperty(name='rotation_weighting')
        prop.slider_max = 4
        prop.tooltip = (
            'The weighting for the rotation. '
            'Equal weighted = 1, weighted towards the inside = 0, weighted towards outside = 2.'
        )
        starburst_group.add_property(prop)

        prop = PointFProperty(name='fadeout')
        prop.tooltip = (
            'A gradient to fade out the starburst towards the edges of the frame. '
            'This prevents visible borders of the starburst frame.'
        )
        starburst_group.add_property(prop)

        prop = SizeFProperty(name='scale')
        prop.tooltip = 'A multiplier on the overall scale of the starburst pattern.'
        starburst_group.add_property(prop)

        # ghost
        ghost_group = flare_group.add_group(
            'ghost', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        self.groups[ghost_group.name] = ghost_group

        # ghost aperture
        ghost_aperture_group = ghost_group.add_group(
            'aperture', collapsible=True, style=CollapsibleBox.Style.SIMPLE
        )

        prop = FloatProperty(name='fstop')
        prop.label = 'F-Stop'
        prop.slider_min = 0
        prop.slider_max = 32
        ghost_aperture_group.add_property(prop)

        prop = PathProperty(name='file')
        prop.method = PathProperty.Method.OPEN_FILE
        prop.dir_fallback = aperture_dir
        ghost_aperture_group.add_property(prop)

        prop = IntProperty(name='blades')
        prop.slider_min = 1
        prop.slider_max = 12
        prop.line_min = 1

        ghost_aperture_group.add_property(prop)

        prop = FloatProperty(name='rotation')
        prop.slider_min = -180
        prop.slider_max = 180
        prop.setEnabled(False)
        ghost_aperture_group.add_property(prop)

        prop = FloatProperty(name='corner_radius')
        prop.slider_min = 0
        prop.slider_max = 1
        prop.setEnabled(False)
        ghost_aperture_group.add_property(prop)

        prop = FloatProperty(name='softness')
        prop.slider_min = 0
        prop.slider_max = 1
        ghost_aperture_group.add_property(prop)

        prop = FloatProperty(name='dust_amount')
        prop.setEnabled(False)
        ghost_aperture_group.add_property(prop)

        prop = FloatProperty(name='scratches_amount')
        prop.setEnabled(False)
        ghost_aperture_group.add_property(prop)

        prop = FloatProperty(name='grating_amount')
        prop.setEnabled(False)
        ghost_aperture_group.add_property(prop)

        # ghost
        prop = FloatProperty(name='fstop')
        prop.slider_min = 0
        prop.slider_max = 32
        prop.tooltip = 'F-Stop that controls the strength of the ringing pattern visible on ghosts.'
        ghost_group.add_property(prop)

        # init defaults
        default_config = data.Flare()
        self.update_widget_values(dataclasses.asdict(default_config), attr='default')

    def _init_actions(self) -> None:
        for name in ('flare', 'starburst', 'ghost'):
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

    def save_preset_as(self, name: str) -> None:
        path = self.settings.decode_path(os.path.join('$PRESET', name))
        file_path, filter_string = QtWidgets.QFileDialog.getSaveFileName(
            parent=self,
            caption='Save Preset As',
            dir=path,
            filter='*.json',
        )
        if file_path:
            config = self.flare_config()
            if name == 'flare':
                pass
            elif name == 'starburst':
                config = config.starburst
            elif name == 'ghost':
                config = config.ghost
            else:
                return
            json_data = cast_json(config)
            self.settings.save_data(json_data, file_path)

    def load_preset(
        self,
        name: str = '',
        config: Flare | Flare.Ghost | Flare.Starburst | None = None,
    ) -> None:
        if name:
            path = self.settings.decode_path(os.path.join('$PRESET', name))
            file_path, filter_string = QtWidgets.QFileDialog.getOpenFileName(
                parent=self,
                caption='Load Preset',
                dir=path,
                filter='*.json',
            )
            if file_path:
                json_data = self.settings.load_data(file_path)
                if name == 'flare':
                    config = cast(data.Flare, json_data)
                elif name == 'starburst':
                    config = cast(data.Flare.Starburst, json_data)
                elif name == 'ghost':
                    config = cast(data.Flare.Ghost, json_data)

        new_config = self.flare_config()
        if isinstance(config, Flare):
            new_config = config
        elif isinstance(config, Flare.Ghost):
            new_config.ghost = config
        elif isinstance(config, Flare.Starburst):
            new_config.starburst = config
        else:
            return

        self.update_editor(new_config)

    def randomize_coatings(self):
        flare = self.flare_config()

        json_data = Settings().load_data(flare.lens.prescription_path)
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

    def reset_config(self, name: str) -> None:
        if name == 'flare':
            widgets = None
        else:
            try:
                widgets = self.widgets()[name]
            except KeyError:
                return
        self.reset(widgets)

    def flare_config(self) -> data.Flare:
        values = self.values()
        config = cast(data.Flare, values)
        return config

    def update_editor(self, config: data.Flare) -> None:
        values = dataclasses.asdict(config)

        self.form.blockSignals(True)
        self.update_widget_values(values)
        self.form.blockSignals(False)
