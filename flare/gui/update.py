from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime, timedelta
from importlib.metadata import version as package_version

from qtpy import QtCore, QtWidgets

from flare.core import PreferencesManager, StateManager
from flare.core.update import Release, build_plan, has_update, latest_release, spawn
from flare.gui.widgets.update import UpdateDialog
from flare.widgets import MessageBox

logger = logging.getLogger(__name__)

CHECK_INTERVAL = timedelta(days=1)


class UpdateController(QtCore.QObject):
    """Check for and apply application updates."""

    available: QtCore.Signal = QtCore.Signal(object)
    up_to_date: QtCore.Signal = QtCore.Signal()
    failed: QtCore.Signal = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self._parent = parent
        self._manual = False
        self._thread: CheckThread | None = None

    def check(self, manual: bool = False) -> None:
        """Check for updates, throttled unless the check is manual."""

        if self._thread is not None and self._thread.isRunning():
            return
        if not manual and not self._should_check():
            return

        self._manual = manual

        thread = CheckThread(self)
        thread.checked.connect(self._on_checked)
        thread.finished.connect(self._on_finished)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    def apply(self, release: Release) -> None:
        """Apply an update and restart the application."""

        plan = build_plan(release)
        if plan is None:
            MessageBox.warning(
                self._parent,
                'Updates',
                'This installation cannot be updated automatically.',
            )
            return

        if not self._parent.close():
            return

        spawn(plan, sys.argv[1:])
        QtWidgets.QApplication.quit()

    def _on_finished(self) -> None:
        self._thread = None

    def _on_checked(self, release: Release | None) -> None:
        self._record_check()

        if release is None:
            logger.error('Could not check for updates.')
            if self._manual:
                MessageBox.warning(
                    self._parent, 'Updates', 'Could not check for updates.'
                )
            self.failed.emit('Could not check for updates.')
            return

        version = package_version('flare')
        if not has_update(version, release):
            if self._manual:
                MessageBox.information(
                    self._parent, 'Updates', f'Flare {version} is up to date.'
                )
            self.up_to_date.emit()
            return

        dialog = UpdateDialog(release, version, self._parent)
        self.available.emit(release)
        if dialog.exec() and dialog.update_requested:
            self.apply(release)

    def _should_check(self) -> bool:
        if not PreferencesManager.get().check_updates:
            return False

        last = StateManager.get().last_update_check
        if not last:
            return True

        try:
            checked = datetime.fromisoformat(last)
        except ValueError:
            return True

        return datetime.now(UTC) - checked > CHECK_INTERVAL

    def _record_check(self) -> None:
        state = StateManager.get()
        state.last_update_check = datetime.now(UTC).isoformat()
        StateManager.set(state)


class CheckThread(QtCore.QThread):
    checked: QtCore.Signal = QtCore.Signal(object)

    def run(self) -> None:
        self.checked.emit(latest_release())
