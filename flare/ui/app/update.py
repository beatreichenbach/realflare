from __future__ import annotations

from importlib.metadata import version as package_version
from typing import TYPE_CHECKING

from qtpy import QtCore, QtWidgets

from flare.services.update.release import Release
from flare.ui.app.widgets.update import UpdateDialog
from flare.ui.widgets import MessageBox

if TYPE_CHECKING:
    from flare.services.update.controller import UpdateController
    from flare.ui.app.app import FlareDockWindow


class UpdatePresenter(QtCore.QObject):
    """Present update results and start the updater from the UI."""

    def __init__(self, window: FlareDockWindow, controller: UpdateController) -> None:
        super().__init__(window)

        self._window = window
        self._controller = controller

        controller.available.connect(self._on_available)
        controller.up_to_date.connect(self._on_up_to_date)
        controller.failed.connect(self._on_failed)

    def _on_available(self, release: Release) -> None:
        version = package_version('flare')
        dialog = UpdateDialog(release, version, self._window)
        if not (dialog.exec() and dialog.update_requested):
            return

        if not self._window.project_actions.prompt_unsaved():
            return

        if not self._controller.apply(release):
            MessageBox.warning(
                self._window,
                'Updates',
                'This installation cannot be updated automatically.',
            )
            return

        self._window.close()
        QtWidgets.QApplication.quit()

    def _on_up_to_date(self, manual: bool) -> None:
        if manual:
            version = package_version('flare')
            MessageBox.information(
                self._window, 'Updates', f'Flare {version} is up to date.'
            )

    def _on_failed(self, manual: bool) -> None:
        if manual:
            MessageBox.warning(self._window, 'Updates', 'Could not check for updates.')
