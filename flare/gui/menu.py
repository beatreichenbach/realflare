from __future__ import annotations

import os
from functools import partial
from typing import TYPE_CHECKING

from qt_logging import LogViewer
from qt_material_icons import MaterialIcon
from qtpy import QtGui, QtWidgets

from flare.gui.widgets.project_editor import ProjectEditor
from flare.gui.widgets.viewer import LayerViewer
from flare.widgets import MessageBox

if TYPE_CHECKING:
    from flare.core import ProjectManager
    from flare.gui.app import FlareDockWindow

StandardButton = QtWidgets.QMessageBox.StandardButton

DOCUMENTATION_URL = 'https://beatreichenbach.github.io/realflare/reference/flare/'
ISSUE_URL = 'https://github.com/beatreichenbach/realflare/issues/new'


class FlareMenuBar(QtWidgets.QMenuBar):
    """Menu bar for the main window, wired to the project manager and actions."""

    def __init__(
        self,
        window: FlareDockWindow,
        manager: ProjectManager,
        actions: ProjectActions,
    ) -> None:
        super().__init__(window)

        self._window = window
        self._manager = manager
        self._actions = actions

        self._add_file_menu()
        self._add_view_menu()
        self._add_help_menu()

        manager.recent_paths_changed.connect(self.refresh_recent)
        self.refresh_recent()

    def refresh_recent(self, *_args: object) -> None:
        """Rebuild the recent menu from the project manager."""

        self._recent_menu.clear()
        for path in self._manager.recent_paths():
            action = QtWidgets.QAction(path, self)
            action.triggered.connect(partial(self._actions.open_recent, path))
            self._recent_menu.addAction(action)

    def _add_file_menu(self) -> None:
        file_menu = self.addMenu('File')

        action = QtWidgets.QAction('New', self._window)
        action.setShortcut(QtGui.QKeySequence.StandardKey.New)
        action.triggered.connect(self._actions.new)
        file_menu.addAction(action)

        action = QtWidgets.QAction('Open ...', self._window)
        action.setIcon(MaterialIcon('file_open'))
        action.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        action.triggered.connect(self._actions.open)
        file_menu.addAction(action)

        self._recent_menu = file_menu.addMenu('Open Recent ...')
        file_menu.addSeparator()

        action = QtWidgets.QAction('Preferences ...', self._window)
        action.setShortcut(QtGui.QKeySequence('Ctrl+Alt+S'))
        action.setIcon(MaterialIcon('settings'))
        action.triggered.connect(partial(show_preferences, self._window))
        file_menu.addAction(action)
        file_menu.addSeparator()

        action = QtWidgets.QAction('Save', self._window)
        action.setIcon(MaterialIcon('save'))
        action.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        action.triggered.connect(self._actions.save)
        file_menu.addAction(action)

        action = QtWidgets.QAction('Save As ...', self._window)
        action.setShortcut(QtGui.QKeySequence('Ctrl+Shift+S'))
        action.triggered.connect(self._actions.save_as)
        file_menu.addAction(action)
        file_menu.addSeparator()

        action = QtWidgets.QAction('Exit', self._window)
        action.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
        action.triggered.connect(self._window.close)
        file_menu.addAction(action)

    def _add_view_menu(self) -> None:
        view_menu = self.addMenu('View')

        action = QtWidgets.QAction('New Viewer', self._window)
        action.setIcon(MaterialIcon('preview'))
        action.triggered.connect(partial(self._window.show_widget, LayerViewer))
        view_menu.addAction(action)

        action = QtWidgets.QAction('Show Parameters', self._window)
        action.setIcon(MaterialIcon('tune'))
        action.triggered.connect(partial(self._window.show_widget, ProjectEditor))
        view_menu.addAction(action)

        action = QtWidgets.QAction('Show Log', self._window)
        action.setIcon(MaterialIcon('article'))
        action.triggered.connect(partial(self._window.show_widget, LogViewer))
        view_menu.addAction(action)

    def _add_help_menu(self) -> None:
        help_menu = self.addMenu('Help')

        action = QtWidgets.QAction('Documentation', self._window)
        action.setIcon(MaterialIcon('question_mark'))
        action.triggered.connect(partial(open_url, DOCUMENTATION_URL))
        help_menu.addAction(action)

        action = QtWidgets.QAction('Report an Issue', self._window)
        action.setIcon(MaterialIcon('bug_report'))
        action.triggered.connect(partial(open_url, ISSUE_URL))
        help_menu.addAction(action)
        help_menu.addSeparator()

        action = QtWidgets.QAction('Check for Updates', self._window)
        action.setIcon(MaterialIcon('update'))
        action.triggered.connect(partial(show_update, self._window))
        help_menu.addAction(action)

        action = QtWidgets.QAction('About', self._window)
        action.triggered.connect(partial(show_about, self._window))
        help_menu.addAction(action)


class ProjectActions:
    """Project file actions with dialogs and unsaved-change prompts."""

    def __init__(self, manager: ProjectManager, parent: QtWidgets.QWidget) -> None:
        self._manager = manager
        self._parent = parent

    def new(self) -> None:
        """Replace the current project with a new one."""

        if self.maybe_save():
            self._manager.new()

    def open(self) -> None:
        """Open a project from a file."""

        if not self.maybe_save():
            return

        path, _filters = QtWidgets.QFileDialog.getOpenFileName(
            self._parent, 'Open Project', self.recent_dir(), '*.json'
        )
        if path:
            self._manager.open(path)

    def save(self) -> bool:
        """Return whether the current project was saved."""

        path = self._manager.path()
        if not path:
            path, _filters = QtWidgets.QFileDialog.getSaveFileName(
                self._parent, 'Save Project', self.recent_dir(), '*.json'
            )
        if path:
            return self._manager.save(path)
        return False

    def save_as(self) -> bool:
        """Return whether the current project was saved to a new path."""

        path, _filters = QtWidgets.QFileDialog.getSaveFileName(
            self._parent, 'Save Project As', self.recent_dir(), '*.json'
        )
        if path:
            return self._manager.save_as(path)
        return False

    def open_recent(self, path: str) -> None:
        """Open a project from the recent paths."""

        if self.maybe_save():
            self._manager.open(path)

    def maybe_save(self) -> bool:
        """Return whether it is safe to discard the current project."""

        if not self._manager.modified():
            return True

        result = MessageBox.question(
            self._parent,
            'Unsaved Changes',
            'Save changes to the current project before continuing?',
            buttons=(
                StandardButton.Save | StandardButton.Discard | StandardButton.Cancel
            ),
            defaultButton=StandardButton.Save,
        )
        if result == StandardButton.Save:
            self.save()
            return not self._manager.modified()
        return result == StandardButton.Discard

    def recent_dir(self) -> str:
        """Return the directory of the most recent project."""

        recent_dirs = (os.path.dirname(p) for p in self._manager.recent_paths())
        return next(recent_dirs, os.path.expanduser('~'))


def open_url(url: str) -> None:
    """Open a URL in the web browser."""

    import webbrowser

    webbrowser.open(url)


def show_preferences(window: FlareDockWindow) -> None:
    """Show the preferences dialog."""

    from flare.gui.widgets.preferences import PreferencesDialog

    dialog = PreferencesDialog(parent=window)
    dialog.show()


def show_update(window: FlareDockWindow) -> None:
    """Check for updates."""

    window.updates.check(manual=True)


def show_about(window: FlareDockWindow) -> None:
    """Show the about dialog."""

    from flare.gui.widgets.about import AboutDialog

    dialog = AboutDialog(parent=window)
    dialog.show()
