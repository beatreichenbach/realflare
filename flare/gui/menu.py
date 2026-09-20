import copy
import logging
import os
import urllib.parse
from functools import partial

from qt_logging import LogBar, LogViewer
from qt_material_icons import MaterialIcon
from qtpy import QtCore, QtGui, QtWidgets

import flare
from flare import api
from flare.engine.pipeline.worker import Worker
from flare.engine.engine import Render
from flare.api.project import ProjectManager
from flare.core import PreferencesManager, State, StateManager
from flare.gui.widgets.base import StateWidget
from flare.gui.widgets.project_editor import ProjectEditor
from flare.gui.widgets.viewer import LayerViewer
from flare.widgets import DockWindow

logger = logging.getLogger(__name__)


GITHUB_URL = 'https://github.com/beatreichenbach/flare/'


def create_menu_bar(parent: QtWidgets.QWidget) -> None:
    menu_bar = QtWidgets.QMenuBar(parent)

    # File
    file_menu = menu_bar.addMenu('File')

    action = QtWidgets.QAction('New', parent)
    action.setShortcut(QtGui.QKeySequence.StandardKey.New)
    action.triggered.connect(file_new)
    file_menu.addAction(action)

    action = QtWidgets.QAction('Open ...', parent)
    action.setIcon(MaterialIcon('file_open'))
    action.setShortcut(QtGui.QKeySequence.StandardKey.Open)
    action.triggered.connect(file_open)
    file_menu.addAction(action)

    self.recent_menu = file_menu.addMenu('Open Recent ...')

    file_menu.addSeparator()

    action = QtWidgets.QAction('Preferences ...', parent)
    action.setShortcut(QtGui.QKeySequence('Ctrl+Alt+S'))
    action.setIcon(MaterialIcon('settings'))
    action.triggered.connect(file_preferences)
    file_menu.addAction(action)

    file_menu.addSeparator()

    action = QtWidgets.QAction('Save', parent)
    action.setIcon(MaterialIcon('save'))
    action.setShortcut(QtGui.QKeySequence.StandardKey.Save)
    action.triggered.connect(file_save)
    file_menu.addAction(action)
    action = QtWidgets.QAction('Save As ...', parent)
    action.setShortcut(QtGui.QKeySequence('Ctrl+Shift+S'))
    action.triggered.connect(file_save_as)
    file_menu.addAction(action)

    file_menu.addSeparator()

    action = QtWidgets.QAction('Exit', parent)
    action.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
    action.triggered.connect(self.close)
    file_menu.addAction(action)

    # View
    view_menu = menu_bar.addMenu('View')
    action = QtWidgets.QAction('New Viewer', parent)
    action.setIcon(MaterialIcon('preview'))
    action.triggered.connect(partial(self.show_widget, LayerViewer))
    view_menu.addAction(action)
    action = QtWidgets.QAction('Show Parameters', parent)
    action.setIcon(MaterialIcon('tune'))
    action.triggered.connect(partial(self.show_widget, ProjectEditor))
    view_menu.addAction(action)
    action = QtWidgets.QAction('Show Log', parent)
    action.setIcon(MaterialIcon('article'))
    action.triggered.connect(partial(self.show_widget, LogViewer))
    view_menu.addAction(action)
    # view_menu.addSeparator()
    # action = QtWidgets.QAction('Reset', parent)
    # action.triggered.connect(self.reset_window_state)
    # view_menu.addAction(action)

    # Engine
    # view_menu = menu_bar.addMenu('Engine')
    # action = QtWidgets.QAction('Restart', parent)
    # action.setIcon(MaterialIcon('restart_alt'))
    # action.triggered.connect(self.restart)
    # view_menu.addAction(action)

    # Help
    help_menu = menu_bar.addMenu('Help')
    action = QtWidgets.QAction('Documentation', parent)
    action.setIcon(MaterialIcon('question_mark'))
    action.triggered.connect(help_documentation)
    help_menu.addAction(action)

    action = QtWidgets.QAction('Report an Issue', parent)
    action.setIcon(MaterialIcon('bug_report'))
    action.triggered.connect(help_report_bug)
    help_menu.addAction(action)

    help_menu.addSeparator()
    action = QtWidgets.QAction('Check for Updates', parent)
    action.setIcon(MaterialIcon('update'))
    action.triggered.connect(help_update)
    help_menu.addAction(action)
    action = QtWidgets.QAction('About', parent)
    action.triggered.connect(help_about)
    help_menu.addAction(action)

    return menu_bar


def file_new(self) -> None:
    project = ProjectManager.create()
    self.set_project(project)
    self.set_project_path('')


def file_save(self) -> None:
    if self._project_path:
        path = self._project_path
    else:
        path, filters = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save Project', self._get_recent_dir(), '*.json'
        )
    if path:
        ProjectManager.save(self._project, path)
        self.set_project_path(path)


def file_save_as(self) -> None:
    path, filters = QtWidgets.QFileDialog.getSaveFileName(
        self, 'Save Project As', self._get_recent_dir(), '*.json'
    )
    if path:
        ProjectManager.save(self._project, path)
        self.set_project_path(path)


def file_open(self) -> None:
    path, filters = QtWidgets.QFileDialog.getOpenFileName(
        self, 'Open Project', self._get_recent_dir(), '*.json'
    )
    if path:
        if project := ProjectManager.open(path):
            self.set_project(project)
            self.set_project_path(path)


def file_preferences(self) -> None:
    from flare.gui.widgets.preferences import PreferencesDialog

    dialog = PreferencesDialog(parent=self)
    dialog.show()


def help_documentation() -> None:
    import webbrowser

    webbrowser.open(GITHUB_URL)


def help_report_bug() -> None:
    import webbrowser

    url = urllib.parse.urljoin(GITHUB_URL, 'issues/new')
    webbrowser.open(url)


def help_update(window: QtWidgets.QWidget) -> None:
    from flare.gui.widgets.update import UpdateDialog

    dialog = UpdateDialog(parent=window)
    dialog.show()


def help_about(window: QtWidgets.QWidget) -> None:
    from flare.gui.widgets.about import AboutDialog

    dialog = AboutDialog(parent=window)
    dialog.show()
