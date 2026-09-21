import logging

from qt_parameters import BoolParameter, ParameterForm
from qtpy import QtGui, QtWidgets

from flare.infrastructure.storage.settings import Preferences, PreferencesManager
from flare.ui.widgets import DialogButtonBox

logger = logging.getLogger(__name__)

ButtonRole = QtWidgets.QDialogButtonBox.ButtonRole
StandardButton = QtWidgets.QMessageBox.StandardButton


class PreferencesDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle('Preferences')
        self.resize(640, 320)

        self._layout = QtWidgets.QVBoxLayout()
        self.setLayout(self._layout)

        self.form = ParameterForm()
        self._layout.addWidget(self.form)

        # Logging
        form = ParameterForm('logging')
        self.form.add_form(form)
        form.set_flat(True)

        parm = BoolParameter('clear_log_on_render')
        parm.set_tooltip('Clear the log on every render.')
        form.add_parameter(parm)

        # Updates
        form = ParameterForm('updates')
        self.form.add_form(form)
        form.set_flat(True)

        parm = BoolParameter('check_updates')
        parm.set_label('Check for updates on startup')
        form.add_parameter(parm)

        # Buttons
        self.button_box = DialogButtonBox()
        size_policy = self.button_box.sizePolicy()
        size_policy.setRetainSizeWhenHidden(True)
        self.button_box.setSizePolicy(size_policy)
        self._layout.addWidget(self.button_box)

        cancel_button = QtWidgets.QPushButton('Cancel')
        cancel_button.pressed.connect(self.close)
        self.button_box.addButton(cancel_button, ButtonRole.RejectRole)

        save_button = QtWidgets.QPushButton('Save')
        save_button.setDefault(True)
        save_button.pressed.connect(self.save)
        self.button_box.addButton(save_button, ButtonRole.ApplyRole)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        self.load_preferences()
        super().showEvent(event)

    def save_preferences(self) -> None:
        values = self.form.values()
        preferences = PreferencesManager.get()
        preferences = preferences.model_validate(values)
        PreferencesManager.set(preferences)

    def load_preferences(self) -> None:
        PreferencesManager.get.cache_clear()
        preferences = PreferencesManager.get()
        values = preferences.model_dump()
        self.form.set_defaults(values)

    def save(self) -> None:
        self.save_preferences()
        self.close()

    def preferences(self) -> Preferences:
        values = self.form.values()
        preferences = Preferences.model_validate(values)
        return preferences
