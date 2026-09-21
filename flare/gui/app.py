from __future__ import annotations

import logging
import os
from functools import partial
from typing import TYPE_CHECKING, Any

from qt_logging import LogBar, LogViewer
from qt_material_icons import MaterialIcon
from qtpy import QtCore, QtGui, QtWidgets

import flare
from flare import api
from flare.core import PreferencesManager, ProjectManager, StateManager
from flare.gui.render import RenderController
from flare.gui.widgets.base import StateWidget
from flare.gui.widgets.project_editor import ProjectEditor
from flare.gui.widgets.viewer import LayerViewer
from flare.widgets import MessageBox, StateDockWindow, WindowState

if TYPE_CHECKING:
    from flare.engine.engine import Render

logger = logging.getLogger(__name__)

StandardButton = QtWidgets.QMessageBox.StandardButton


class FlareDockWindow(StateDockWindow):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.manager = ProjectManager(self)
        self.renderer = RenderController(self.manager, self)

        self._syncing = False

        self.project_editor: ProjectEditor | None = None
        self.widget_added.connect(self._update_widget)

        self._init_window()
        self._init_menu()
        self._init_signals()
        self.load_state()
        self._refresh_window_title()

    def _init_window(self) -> None:
        self.setWindowTitle('Flare')
        self.resize(1920, 1080)

        self.log_bar = LogBar()
        self.log_bar.names = {'root', flare.__name__}
        self.log_bar.level = logging.WARNING
        self._layout.addWidget(self.log_bar)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.log_bar.add_widget(self.progress_bar)

        self.register_widget(LayerViewer, name='Viewer')
        self.register_widget(ProjectEditor, name='Parameters', unique=True)
        self.register_widget(LogViewer, name='Log', unique=True)

    def _init_menu(self) -> None:
        self.menu_bar = QtWidgets.QMenuBar(self)
        self._layout.insertWidget(0, self.menu_bar)

        # File
        file_menu = self.menu_bar.addMenu('File')

        action = QtWidgets.QAction('New', self)
        action.setShortcut(QtGui.QKeySequence.StandardKey.New)
        action.triggered.connect(self._file_new)
        file_menu.addAction(action)
        action = QtWidgets.QAction('Open ...', self)
        action.setIcon(MaterialIcon('file_open'))
        action.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        action.triggered.connect(self._file_open)
        file_menu.addAction(action)
        self.recent_menu = file_menu.addMenu('Open Recent ...')
        file_menu.addSeparator()

        action = QtWidgets.QAction('Preferences ...', self)
        action.setShortcut(QtGui.QKeySequence('Ctrl+Alt+S'))
        action.setIcon(MaterialIcon('settings'))
        action.triggered.connect(self._file_preferences)
        file_menu.addAction(action)
        file_menu.addSeparator()

        action = QtWidgets.QAction('Save', self)
        action.setIcon(MaterialIcon('save'))
        action.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        action.triggered.connect(self._file_save)
        file_menu.addAction(action)
        action = QtWidgets.QAction('Save As ...', self)
        action.setShortcut(QtGui.QKeySequence('Ctrl+Shift+S'))
        action.triggered.connect(self._file_save_as)
        file_menu.addAction(action)
        file_menu.addSeparator()

        action = QtWidgets.QAction('Exit', self)
        action.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
        action.triggered.connect(self.close)
        file_menu.addAction(action)

        # View
        view_menu = self.menu_bar.addMenu('View')
        action = QtWidgets.QAction('New Viewer', self)
        action.setIcon(MaterialIcon('preview'))
        action.triggered.connect(partial(self.show_widget, LayerViewer))
        view_menu.addAction(action)
        action = QtWidgets.QAction('Show Parameters', self)
        action.setIcon(MaterialIcon('tune'))
        action.triggered.connect(partial(self.show_widget, ProjectEditor))
        view_menu.addAction(action)
        action = QtWidgets.QAction('Show Log', self)
        action.setIcon(MaterialIcon('article'))
        action.triggered.connect(partial(self.show_widget, LogViewer))
        view_menu.addAction(action)

        # Help
        help_menu = self.menu_bar.addMenu('Help')
        action = QtWidgets.QAction('Documentation', self)
        action.setIcon(MaterialIcon('question_mark'))
        action.triggered.connect(self._help_documentation)
        help_menu.addAction(action)
        action = QtWidgets.QAction('Report an Issue', self)
        action.setIcon(MaterialIcon('bug_report'))
        action.triggered.connect(self._help_report_bug)
        help_menu.addAction(action)
        help_menu.addSeparator()
        action = QtWidgets.QAction('Check for Updates', self)
        action.setIcon(MaterialIcon('update'))
        action.triggered.connect(self._help_update)
        help_menu.addAction(action)
        action = QtWidgets.QAction('About', self)
        action.triggered.connect(self._help_about)
        help_menu.addAction(action)

    def _init_signals(self) -> None:
        self.manager.project_changed.connect(self._project_changed)
        self.manager.project_changed.connect(self.renderer.set_project)
        self.manager.path_changed.connect(self._refresh_window_title)
        self.manager.modified_changed.connect(self._refresh_window_title)
        self.manager.recent_paths_changed.connect(self._refresh_recent_menu)

        self.renderer.rendered.connect(self._update_viewers)
        self.renderer.progress_changed.connect(self._progress_changed)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)

        QtCore.QTimer.singleShot(500, self.refresh)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self._maybe_save():
            event.ignore()
            return

        self.save_state()
        super().closeEvent(event)

    def refresh(self) -> None:
        """Update the layers and refresh the Viewers."""

        self._update_layers()
        self.renderer.set_project(self.manager.project())

    def request_disk_render(self) -> None:
        """Request a render and save the output to disk."""

        self.renderer.render_to_disk()

    def save_state(self) -> None:
        """Save the state of the window."""

        state = StateManager.get()
        state.main_window = self.window_state().model_dump()
        state.widgets = self._widget_states()
        StateManager.set(state)

    def load_state(self) -> None:
        """Load the state of the window."""

        state = StateManager.get()
        self.set_window_state(WindowState.model_validate(state.main_window))
        self._set_widget_states(state.widgets)

    def _widget_states(self) -> dict[str, Any]:
        """Return the state of all StateWidgets in the window."""

        states = {}
        for title, widget in self._widgets.items():
            if isinstance(widget, StateWidget):
                widget: StateWidget
                states[title] = widget.state()
        return states

    def _set_widget_states(self, states: dict[str, Any]) -> None:
        """Set the state of all StateWidgets in the window."""

        for title, widget in self._widgets.items():
            state = states.get(title)
            if state and isinstance(widget, StateWidget):
                widget: StateWidget
                widget.set_state(state)

    def _progress_changed(self, value: float) -> None:
        """Handle the changing of the progress for the LogBar."""

        if value < 0:
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(0)
        else:
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(int(value * 100))

        if value <= 0:
            preferences = PreferencesManager.get()
            if preferences.clear_log_on_render:
                cache = self.log_bar.cache()
                if cache is not None:
                    cache.clear()
        if value >= 1:
            self.progress_bar.setValue(0)

    def _project_changed(self, project: api.Project) -> None:
        """Update the ProjectEditor with a changed project."""

        if self.project_editor is not None and not self._syncing:
            self._syncing = True
            try:
                self.project_editor.set_project(project)
            finally:
                self._syncing = False
        self._refresh_window_title()

    def _project_editor_changed(self) -> None:
        """Handle the changing of the ProjectEditor."""

        if self.project_editor is None or self._syncing:
            return

        self._syncing = True
        try:
            self.manager.update_project(self.project_editor.get_project())
        finally:
            self._syncing = False

    def _position_changed(self, viewer: LayerViewer, position: QtCore.QPoint) -> None:
        """Handle the changing of position from a Viewer by updating the api.Project."""

        # Not every Viewer updates the project.
        if viewer.layer() not in (api.Layer.FLARE, api.Layer.STARBURST, api.Layer.COMP):
            return

        project = self.manager.project()
        project = self.manager.project()
        ndc_position = QtCore.QPointF(
            (position.x() / viewer.resolution().width() * 2.0) - 1.0,
            (position.y() / viewer.resolution().height() * 2.0) - 1.0,
        )

        self._syncing = True
        try:
            self.manager.set_light_position(ndc_position)
        finally:
            self._syncing = False

        # Update the ProjectEditor
        if self.project_editor is not None:
            param = self.project_editor.parameter('flare.light.position')
            if param is not None:
                param.blockSignals(True)
                param.set_value(ndc_position)
                param.blockSignals(False)

    def _update_layers(self) -> None:
        """Update the layers in the engine that should be rendered."""

        layers = []
        for dock_widget in self.dock_widgets():
            widget = dock_widget.currentWidget()
            if (
                isinstance(widget, LayerViewer)
                and not widget.paused()
                and (layer := widget.layer())
            ):
                layers.append(layer)
        self.renderer.set_layers(tuple(layers))

    def _update_viewers(self, render: Render) -> None:
        """Update the LayerViewers with a new Render."""

        for widget in self._widgets.values():
            if isinstance(widget, LayerViewer) and widget.layer() == render.layer:
                try:
                    widget.set_array(render.image.array)
                except RuntimeError:
                    # Widget has been removed
                    logger.error('Widget already removed.')

    def _update_widget(self, widget: QtWidgets.QWidget) -> None:
        """Update a widget when it's added to the window."""

        # Restore state
        state = StateManager.get()
        for title, window_widget in self._widgets.items():
            if window_widget == widget:
                widget_state = state.widgets.get(title)
                if widget_state and isinstance(widget, StateWidget):
                    widget.set_state(widget_state)

        # Reconnect signals
        if isinstance(widget, LayerViewer):
            widget.position_changed.connect(partial(self._position_changed, widget))
            widget.layer_changed.connect(self.refresh)
            widget.pause_changed.connect(self.refresh)
            widget.refreshed.connect(self.refresh)

        elif isinstance(widget, ProjectEditor):
            widget.set_project(self.manager.project())
            widget.parameter_changed.connect(self._project_editor_changed)
            if widget.render_button is not None:
                widget.render_button.clicked.connect(self.request_disk_render)
            self.project_editor = widget

        elif isinstance(widget, LogViewer):
            cache = self.log_bar.cache()
            if cache is not None:
                widget.set_cache(cache)

    def _refresh_window_title(self, *_args: object) -> None:
        """Refresh the window title depending on the save status of the project."""

        filename = os.path.basename(self.manager.path())
        title = filename if filename else 'untitled'
        if self.manager.modified():
            title = f'{title} *'
        self.setWindowTitle(title)

    def _refresh_recent_menu(self, *_args: object) -> None:
        """Refresh the recent menu with the paths from the manager."""

        self.recent_menu.clear()
        for filename in self.manager.recent_paths():
            action = QtWidgets.QAction(filename, self)
            action.triggered.connect(partial(self._open_recent, filename))
            self.recent_menu.addAction(action)

    def _maybe_save(self) -> bool:
        """Return whether it is safe to discard the current project."""

        if not self.manager.modified():
            return True

        result = MessageBox.question(
            self,
            'Unsaved Changes',
            'Save changes to the current project before continuing?',
            buttons=(
                StandardButton.Save | StandardButton.Discard | StandardButton.Cancel
            ),
            defaultButton=StandardButton.Save,
        )
        if result == StandardButton.Save:
            self._file_save()
            return not self.manager.modified()
        return result == StandardButton.Discard

    # Menu

    def _file_new(self) -> None:
        if self._maybe_save():
            self.manager.new()

    def _file_save(self) -> None:
        path = self.manager.path()
        if not path:
            path, _filters = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Project', self._get_recent_dir(), '*.json'
            )
        if path:
            self.manager.save(path)

    def _file_save_as(self) -> None:
        path, _filters = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save Project As', self._get_recent_dir(), '*.json'
        )
        if path:
            self.manager.save_as(path)

    def _file_open(self) -> None:
        if not self._maybe_save():
            return

        path, _filters = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open Project', self._get_recent_dir(), '*.json'
        )
        if path:
            self.manager.open(path)

    def _open_recent(self, path: str) -> None:
        if self._maybe_save():
            self.manager.open(path)

    def _file_preferences(self) -> None:
        from flare.gui.widgets.preferences import PreferencesDialog

        dialog = PreferencesDialog(parent=self)
        dialog.show()

    @staticmethod
    def _help_documentation() -> None:
        import webbrowser

        webbrowser.open('https://beatreichenbach.github.io/realflare/reference/flare/')

    @staticmethod
    def _help_report_bug() -> None:
        import webbrowser

        webbrowser.open('https://github.com/beatreichenbach/realflare/issues/new')

    def _help_update(self) -> None:
        from flare.gui.widgets.update import UpdateDialog

        dialog = UpdateDialog(parent=self)
        dialog.show()

    def _help_about(self) -> None:
        from flare.gui.widgets.about import AboutDialog

        dialog = AboutDialog(parent=self)
        dialog.show()

    def _get_recent_dir(self) -> str:
        """Return the recent dir."""

        recent_dirs = (os.path.dirname(p) for p in self.manager.recent_paths())
        return next(recent_dirs, os.path.expanduser('~'))
