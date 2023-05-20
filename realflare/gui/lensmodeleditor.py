import dataclasses
import logging
import os
import shutil

from PySide2 import QtWidgets, QtCore, QtGui
from slugify import slugify

from qt_extensions.button import Button
from qt_extensions.filebrowser import FileBrowser, FileElement

from realflare.api.data import LensModel
from realflare.storage import Storage
from qt_extensions.box import CollapsibleBox
from qt_extensions.elementbrowser import Field
from qt_extensions.helper import unique_path
from qt_extensions.icons import MaterialIcon
from qt_extensions.messagebox import MessageBox
from qt_extensions.parameters import (
    TabDataParameter,
    IntParameter,
    FloatParameter,
    StringParameter,
    ParameterEditor,
)
from qt_extensions.typeutils import cast, cast_basic


logger = logging.getLogger(__name__)
storage = Storage()


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


class GroupEditor(ParameterEditor):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        group = self.add_group('Group', style=CollapsibleBox.Style.SIMPLE)
        group.create_hierarchy = False
        parm = StringParameter('name')

        regex = QtCore.QRegularExpression(r'[\w\d\.-]+')
        parm.text.setValidator(QtGui.QRegularExpressionValidator(regex, parm))

        group.add_parameter(parm)

    def update_editor(self, name: str) -> None:
        self.blockSignals(True)
        self.set_values({'name': name})
        self.blockSignals(False)

    def name(self) -> str:
        return self.values().get('name', '')


class LensModelEditor(ParameterEditor):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._init_editor()

    def _init_editor(self):
        # lens model
        model_group = self.add_group('model', style=CollapsibleBox.Style.SIMPLE)
        model_group.create_hierarchy = False

        # model
        parm = StringParameter('name')
        parm.tooltip = 'The name of the lens. Only for reference.'
        self.name_parameter = model_group.add_parameter(parm)

        parm = IntParameter('year')
        parm.slider_visible = False
        parm.line_min = 0
        parm.line_max = 9999
        parm.tooltip = 'The year of the lens / patent. Only for reference.'
        model_group.add_parameter(parm)

        parm = StringParameter('patent_number')
        parm.tooltip = (
            'Patent number if the lens is based on a patent. Only for reference.'
        )
        model_group.add_parameter(parm)

        parm = StringParameter('notes')
        parm.tooltip = 'Additional information for the lens. Only for reference.'
        parm.area = True
        model_group.add_parameter(parm)

        # specs
        specs_group = self.add_group(
            'specs', collapsible=False, style=CollapsibleBox.Style.SIMPLE
        )
        specs_group.create_hierarchy = False

        # expand collapsible boxes
        for group in self.boxes().values():
            for box in group.keys():
                box.collapsed = False

        parm = FloatParameter('focal_length')
        parm.slider_min = 10
        parm.slider_max = 100
        parm.slider_visible = False
        parm.tooltip = (
            'Focal Length in mm of the lens. Used for mapping the light source '
            'to the ray direction.'
        )
        specs_group.add_parameter(parm)

        parm = FloatParameter('fstop')
        parm.label = 'Minimum F-Stop'
        parm.slider_min = 1
        parm.slider_max = 32
        parm.slider_visible = False
        parm.tooltip = 'Minimum possible F-Stop of the lens. Not currently used.'
        specs_group.add_parameter(parm)

        parm = IntParameter('aperture_index')
        parm.line_min = 0
        parm.slider_visible = False
        parm.tooltip = (
            'The number of the entry in the lens elements that is the aperture. '
            'Make sure to include a lens element with radius 0, refractive index 1 '
            'and correct height for the aperture. The height is currently not '
            'automatically calculated.'
        )
        specs_group.add_parameter(parm)

        parm = TabDataParameter('lens_elements')
        fields = dataclasses.fields(LensModel.LensElement)
        parm.headers = [field.name for field in fields]
        parm.types = [field.type for field in fields]
        parm.tooltip = (
            'A list of all the lens elements including the aperture. '
            'In patents the usual labels are: radius \'r\', distance \'d\', '
            'refractive index \'n\', abbe number \'v\'. The height is rarely given '
            'and can be dialed in by comparing the diagram with the render.'
        )
        specs_group.add_parameter(parm)

        # init defaults
        values = cast_basic(LensModel())
        self.set_values(values, attr='default')

    def lens_model_config(self) -> LensModel:
        values = self.values()
        config = cast(LensModel, values)
        return config

    def update_editor(self, config: LensModel) -> None:
        values = cast_basic(config)

        self.blockSignals(True)
        self.set_values(values)
        self.blockSignals(False)


@dataclasses.dataclass
class LensModelFileElement(FileElement):
    lens_model: LensModel | None = None


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
        try:
            data = storage.read_data(path)
        except ValueError:
            return
        lens_model = cast(LensModel, data)
        name = lens_model.name
        element = LensModelFileElement(name=name, path=path, lens_model=lens_model)
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
        path = Storage().decode_path('$MODEL')
        # fields = [Field('name', editable=True)]
        self.browser = LensModelBrowser(path)
        self.browser.selection_changed.connect(self._selection_change)
        self.browser.layout().setContentsMargins(QtCore.QMargins())
        content_layout.addWidget(self.browser)

        # editor
        self.lens_editor = LensModelEditor()
        self.lens_editor.parameter_changed.connect(self._lens_model_change)
        self.group_editor = GroupEditor()
        self.group_editor.parameter_changed.connect(self._group_change)
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

        save_button = Button('Save', color='primary')
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
            if self.current_element.lens_model:
                self.lens_editor.update_editor(self.current_element.lens_model)

        self.button_box.hide()

    def change_content(self) -> None:
        widget = None
        if self.current_element:
            if self.current_element.lens_model:
                self.lens_editor.update_editor(self.current_element.lens_model)
                widget = self.lens_editor
            else:
                self.group_editor.update_editor(self.current_element.name)
                widget = self.group_editor
        self.content_widget.show_widget(widget)

    def check_save(self) -> bool:
        # returns true if program can continue, false if action should be cancelled

        if not self.current_element:
            return True

        if self.current_element.lens_model:
            # lens model
            lens_model = self.lens_editor.lens_model_config()
            if self.current_element.lens_model == lens_model:
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
        if self.current_element.lens_model:
            result = self.save_lens_model()
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
            logger.debug(e)
            logger.error(f'Could not save group: {name}')

        self.browser.refresh()
        return True

    def save_lens_model(self) -> bool:
        indexes = self.browser.model.find_indexes(self.current_element)

        name, ext = os.path.splitext(os.path.basename(self.current_element.path))
        lens_model = self.lens_editor.lens_model_config()
        filename = slugify(lens_model.name, separator='_') + ext
        path = os.path.join(os.path.dirname(self.current_element.path), filename)
        if self.current_element.path != path:
            path = unique_path(path)
            try:
                shutil.move(self.current_element.path, path)
            except OSError:
                pass

        data = cast_basic(lens_model)
        try:
            storage.write_data(data, path)
        except ValueError:
            message = f'Could not save project file: {self.project_path}'
            logger.error(message)
            return False

        logger.info(f'Lens Model saved: {path}')

        self.current_element.lens_model = lens_model
        self.current_element.name = lens_model.name
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

    def _lens_model_change(self) -> None:
        lens_model = self.lens_editor.lens_model_config()
        if self.current_element and self.current_element.lens_model != lens_model:
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
