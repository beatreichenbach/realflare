import dataclasses
import logging
import os
import shutil

from PySide2 import QtWidgets, QtCore, QtGui
from slugify import slugify

from qt_extensions.button import Button
from qt_extensions.filebrowser import FileBrowser, FileElement

from realflare.api.data import Prescription
from realflare.gui.settings import Settings
from qt_extensions.box import CollapsibleBox
from qt_extensions.elementbrowser import Field
from qt_extensions.helper import unique_path
from qt_extensions.icons import MaterialIcon
from qt_extensions.messagebox import MessageBox
from qt_extensions.properties import (
    TabDataProperty,
    IntProperty,
    FloatProperty,
    StringProperty,
    PropertyEditor,
)
from qt_extensions.typeutils import cast, cast_basic


class ContentWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.widgets = []
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(QtCore.QMargins())
        self.layout().setSpacing(0)

    def add_widget(self, widget: QtWidgets.QWidget) -> None:
        if widget not in self.widgets:
            self.widgets.append(widget)
            self.layout().addWidget(widget)
            widget.hide()

    def remove_widget(self, widget: QtWidgets.QWidget) -> None:
        if widget in self.widgets:
            self.widgets.remove(widget)
            self.layout().removeWidget(widget)
            self.show_widget()

    def show_widget(self, widget: QtWidgets.QWidget | None = None) -> None:
        for widget_ in self.widgets:
            widget_.hide()

        if widget in self.widgets:
            widget.show()

    def sizeHint(self) -> QtCore.QSize:
        size = super().sizeHint()
        for widget in self.widgets:
            size.setWidth(max(size.width(), widget.sizeHint().width()))
            size.setHeight(max(size.height(), widget.sizeHint().height()))
        return size


class GroupEditor(PropertyEditor):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        group = self.add_group('Group', style=CollapsibleBox.Style.SIMPLE)
        group.create_hierarchy = False
        prop = StringProperty('name')

        regex = QtCore.QRegularExpression(r'[\w\d\.-]+')
        prop.text.setValidator(QtGui.QRegularExpressionValidator(regex, prop))

        group.add_property(prop)

    def update_editor(self, name: str) -> None:
        self.form.blockSignals(True)
        self.update_widget_values({'name': name})
        self.form.blockSignals(False)

    def name(self) -> str:
        return self.values().get('name', '')


class LensModelEditor(PropertyEditor):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._init_editor()

    def _init_editor(self):
        # prescription
        model_group = self.add_group('model', style=CollapsibleBox.Style.SIMPLE)
        model_group.create_hierarchy = False

        # model
        prop = StringProperty('name')
        prop.tooltip = 'The name of the lens. Only for reference.'
        self.name_property = model_group.add_property(prop)

        prop = IntProperty('year')
        prop.slider_visible = False
        prop.line_min = 0
        prop.line_max = 9999
        prop.tooltip = 'The year of the lens / patent. Only for reference.'
        model_group.add_property(prop)

        prop = StringProperty('patent_number')
        prop.tooltip = (
            'Patent number if the lens is based on a patent. Only for reference.'
        )
        model_group.add_property(prop)

        prop = StringProperty('notes')
        prop.tooltip = 'Additional information for the lens. Only for reference.'
        prop.area = True
        model_group.add_property(prop)

        # specs
        specs_group = self.add_group(
            'specs', collapsible=False, style=CollapsibleBox.Style.SIMPLE
        )
        specs_group.create_hierarchy = False

        # expand collapsible boxes
        for group in self.boxes().values():
            for box in group.keys():
                box.collapsed = False

        prop = FloatProperty('focal_length')
        prop.slider_min = 10
        prop.slider_max = 100
        prop.slider_visible = False
        prop.tooltip = 'Focal Length in mm of the lens. Used for mapping the light source to the ray direction.'
        specs_group.add_property(prop)

        prop = FloatProperty('fstop')
        prop.label = 'Minimum F-Stop'
        prop.slider_min = 1
        prop.slider_max = 32
        prop.slider_visible = False
        prop.tooltip = 'Minimum possible F-Stop of the lens. Not currently used.'
        specs_group.add_property(prop)

        prop = IntProperty('aperture_index')
        prop.line_min = 0
        prop.slider_visible = False
        prop.tooltip = (
            'The number of the entry in the lens elements that is the aperture. '
            'Make sure to include a lens element with radius 0, refractive index 1 and correct '
            'height for the aperture. The height is currently not automatically calculated.'
        )
        specs_group.add_property(prop)

        prop = TabDataProperty('lens_elements')
        fields = dataclasses.fields(Prescription.LensElement)
        prop.headers = [field.name for field in fields]
        prop.types = [field.type for field in fields]
        prop.tooltip = (
            "A list of all the lens elements including the aperture. In patents the usual "
            "labels are: radius 'r', distance 'd', refractive index 'n', abbe number 'v'. "
            "The height is rarely given and can be dialed in by comparing the diagram with the render."
        )
        specs_group.add_property(prop)

        # optimization
        # optimization_group = prescription_group.add_group(
        #     'optimization', collapsible=True, style=CollapsibleBox.Style.BUTTON
        # )
        # optimization_group.create_hierarchy = False
        #
        # prop = StringProperty('cull_ghosts')
        # optimization_group.add_property(prop)

        # init defaults
        default_config = Prescription()
        values = dataclasses.asdict(default_config)
        # values['cull_ghosts'] = ', '.join(values['cull_ghosts'])
        self.update_widget_values(values, attr='default')

    def prescription_config(self) -> Prescription:
        values = self.values()

        # # match dataclass configuration
        # cull_ghosts = [
        #     int(c) for c in values['cull_ghosts'].split(',') if c.strip().isdigit()
        # ]
        # values['cull_ghosts'] = cull_ghosts

        config = cast(Prescription, values)
        return config

    def update_editor(self, config: Prescription) -> None:
        values = dataclasses.asdict(config)

        # # match editor configuration
        # values['cull_ghosts'] = ', '.join(values['cull_ghosts'])

        self.form.blockSignals(True)
        self.update_widget_values(values)
        self.form.blockSignals(False)


@dataclasses.dataclass
class LensModelFileElement(FileElement):
    prescription: Prescription | None = None


class LensModelBrowser(FileBrowser):
    file_name = 'Unnamed.json'
    file_filter = '.json'

    def __init__(
        self,
        path: str,
        fields: list[Field] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(path, fields, parent)

    def _append_dir(self, path: str, parent: QtCore.QModelIndex):
        name = os.path.basename(path)
        element = LensModelFileElement(name=name, path=path)
        icon = MaterialIcon('folder')
        self.model.append_element(element, icon=icon, parent=parent)

    def _append_file(self, path: str, parent: QtCore.QModelIndex):
        data = Settings().load_data(path)
        prescription = cast(Prescription, data)
        name = prescription.name
        element = LensModelFileElement(name=name, path=path, prescription=prescription)
        self.model.append_element(element, no_children=True, parent=parent)


class LensModelDialog(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        self.current_element = None
        # self.setWindowTitle('Lens Models')

        self._init_ui()

        self.change_content()

    def _init_ui(self):
        self.setLayout(QtWidgets.QVBoxLayout())

        content_layout = QtWidgets.QHBoxLayout()
        self.layout().addLayout(content_layout)

        # browser
        path = Settings().decode_path('$MODEL')
        # fields = [Field('name', editable=True)]
        self.browser = LensModelBrowser(path)
        self.browser.selection_changed.connect(self._selection_change)
        self.browser.layout().setContentsMargins(QtCore.QMargins())
        content_layout.addWidget(self.browser)

        # editor
        self.lens_editor = LensModelEditor()
        self.lens_editor.property_changed.connect(self._prescription_change)
        self.group_editor = GroupEditor()
        self.group_editor.property_changed.connect(self._group_change)
        self.content_widget = ContentWidget()
        self.content_widget.add_widget(self.lens_editor)
        self.content_widget.add_widget(self.group_editor)
        content_layout.addWidget(self.content_widget)
        content_layout.setStretch(1, 1)

        self.button_box = QtWidgets.QDialogButtonBox()
        size_policy = self.button_box.sizePolicy()
        size_policy.setRetainSizeWhenHidden(True)
        self.button_box.setSizePolicy(size_policy)
        self.layout().addWidget(self.button_box)

        save_button = Button('Save', style=Button.Style.PRIMARY)
        save_button.pressed.connect(self.save)
        self.button_box.addButton(save_button, QtWidgets.QDialogButtonBox.ApplyRole)

        cancel_button = Button('Cancel')
        cancel_button.pressed.connect(self.cancel)
        self.button_box.addButton(cancel_button, QtWidgets.QDialogButtonBox.RejectRole)

        self.button_box.hide()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.check_save():
            super().closeEvent(event)

    def cancel(self) -> None:
        if self.current_element:
            if self.current_element.name:
                self.group_editor.update_editor(self.current_element.name)
            if self.current_element.prescription:
                self.lens_editor.update_editor(self.current_element.prescription)

        self.button_box.hide()

    def change_content(self) -> None:
        widget = None
        if self.current_element:
            if self.current_element.prescription:
                self.lens_editor.update_editor(self.current_element.prescription)
                widget = self.lens_editor
            else:
                self.group_editor.update_editor(self.current_element.name)
                widget = self.group_editor
        self.content_widget.show_widget(widget)

    def check_save(self) -> bool:
        # returns true if program can continue, false if action should be cancelled

        if not self.current_element:
            return True

        if self.current_element.prescription:
            # lens model
            prescription = self.lens_editor.prescription_config()
            if self.current_element.prescription == prescription:
                return True
        else:
            # group
            if self.current_element.name == self.group_editor.name():
                return True

        buttons = (
            QtWidgets.QMessageBox.StandardButton.Save
            | QtWidgets.QMessageBox.StandardButton.Cancel
            | QtWidgets.QMessageBox.StandardButton.Discard
        )

        result = MessageBox.message(
            parent=self,
            title='Unsaved Changes',
            text='You have unsaved changes that will be lost. Do you want to save them?',
            buttons=buttons,
        )

        if result == QtWidgets.QMessageBox.StandardButton.Save:
            return self.save()
        elif result == QtWidgets.QMessageBox.StandardButton.Cancel:
            return False
        else:
            return True

    def save(self) -> bool:
        if not self.current_element:
            return True
        if self.current_element.prescription:
            result = self.save_prescription()
        else:
            result = self.save_group()
        if result:
            self.button_box.hide()
        return result

    def save_group(self) -> bool:
        source_path = self.current_element.path
        parent_path = os.path.dirname(self.current_element.path)
        name = self.group_editor.name()
        destination_path = unique_path(os.path.join(parent_path, name))
        try:
            shutil.move(source_path, destination_path)
            self.current_element.name = os.path.basename(destination_path)
            self.current_element.path = destination_path
        except OSError as e:
            logging.exception(e)

        self.browser.refresh()
        return True

    def save_prescription(self) -> bool:
        indexes = self.browser.model.find_indexes(self.current_element)

        name, ext = os.path.splitext(os.path.basename(self.current_element.path))
        prescription = self.lens_editor.prescription_config()
        filename = slugify(prescription.name, separator='_') + ext
        path = os.path.join(os.path.dirname(self.current_element.path), filename)
        if self.current_element.path != path:
            path = unique_path(path)
            try:
                shutil.move(self.current_element.path, path)
            except OSError:
                pass

        json_data = cast_basic(prescription)
        Settings().save_data(json_data, path)

        logging.debug(f'File saved: {path}')

        self.current_element.prescription = prescription
        self.current_element.name = prescription.name
        self.current_element.path = path

        for index in indexes:
            self.browser.model.refresh_index(index)
        return True

    def _group_change(self) -> None:
        name = self.group_editor.name()
        if self.current_element and self.current_element.name != name:
            self.button_box.show()
        else:
            self.button_box.hide()

    def _prescription_change(self) -> None:
        prescription = self.lens_editor.prescription_config()
        if self.current_element and self.current_element.prescription != prescription:
            self.button_box.show()
        else:
            self.button_box.hide()

    def _selection_change(self) -> None:
        selected_elements = self.browser.selected_elements()
        if self.check_save():
            if selected_elements:
                self.current_element = selected_elements[0]
            else:
                self.current_element = None
            self.change_content()
        else:
            self.browser.blockSignals(True)
            self.browser.select_elements([self.current_element])
            self.browser.blockSignals(False)
