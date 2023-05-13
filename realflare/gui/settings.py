from PySide2 import QtWidgets, QtGui

from qt_extensions.button import Button
from qt_extensions.messagebox import MessageBox
from qt_extensions.parameters import (
    PathParameter,
    ParameterEditor,
    BoolParameter,
)
from qt_extensions.box import CollapsibleBox
from qt_extensions.typeutils import cast_basic, cast
from realflare.utils.settings import Settings, SettingsConfig


class SettingsEditor(ParameterEditor):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._init_editor()

    def _init_editor(self) -> None:
        # color
        color_group = self.add_group(
            'Color', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        color_group.create_hierarchy = False

        prop = PathParameter('ocio')
        prop.label = 'OCIO Config'
        prop.method = PathParameter.Method.SAVE_FILE
        prop.tooltip = (
            'Path to the config.ocio file. '
            'Currently a ACES config is required. '
            'If no path is set here, the system will fall back to '
            'the environment variable \'OCIO\''
        )
        color_group.add_parameter(prop)

        # crash reporting
        crash_group = self.add_group(
            'Crash Reporting', collapsible=True, style=CollapsibleBox.Style.BUTTON
        )
        crash_group.create_hierarchy = False

        prop = BoolParameter('sentry')
        prop.label = 'Automated Crash Reporting'
        prop.tooltip = (
            'Automatically upload crash reports using Sentry.io. '
            'Crash reports don\'t include any personal information.'
        )
        crash_group.add_parameter(prop)

    def config(self) -> SettingsConfig:
        values = self.values()
        config = cast(SettingsConfig, values)
        return config

    def set_config(self, config: SettingsConfig) -> None:
        self.blockSignals(True)
        self.set_values(cast_basic(config))
        self.blockSignals(False)


class SettingsDialog(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        self.settings = Settings()
        self.settings.load()

        self.cached_config = self.settings.config

        self._init_ui()
        self.setWindowTitle('Settings')

    def _init_ui(self):
        self.setLayout(QtWidgets.QVBoxLayout())

        # editor
        self.editor = SettingsEditor()
        self.editor.set_values(cast_basic(self.cached_config), attr='default')
        self.editor.parameter_changed.connect(self._settings_change)

        self.layout().addWidget(self.editor)

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
        if self.cached_config:
            self.editor.set_config(self.cached_config)
        self.button_box.hide()

    def check_save(self) -> bool:
        # returns true if program can continue, false if action should be cancelled

        if not self.cached_config:
            return True

        config = self.editor.config()
        if self.cached_config == config:
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
        self.settings.config = self.editor.config()
        result = self.settings.save()
        if result:
            self.button_box.hide()
        return result

    def _settings_change(self) -> None:
        # TODO: current self.editor.config() does not represent the whole config,
        #  but only the settings editable in gui
        config = self.editor.config()
        if self.cached_config and self.cached_config != config:
            self.button_box.show()
        else:
            self.button_box.hide()
