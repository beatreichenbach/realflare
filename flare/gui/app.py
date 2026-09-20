import copy
import logging
import os
from functools import partial
from typing import Any

from qt_logging import LogBar, LogViewer
from qt_material_icons import MaterialIcon
from qtpy import QtCore, QtGui, QtWidgets

import flare
from flare import api
from flare.api.project import ProjectManager
from flare.core import PreferencesManager, State, StateManager
from flare.engine.engine import Render
from flare.gui.widgets.base import StateWidget
from flare.gui.widgets.project_editor import ProjectEditor
from flare.gui.widgets.viewer import LayerViewer
from flare.widgets import DockWindow

from .worker import Worker

logger = logging.getLogger(__name__)

QueuedConnection = QtCore.Qt.ConnectionType.QueuedConnection


class FlareDockWindow(DockWindow):
    render_requested = QtCore.Signal(api.Project)
    stop_requested = QtCore.Signal()
    layers_changed = QtCore.Signal(tuple)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        # -----------
        self._project = api.Project()
        self._project.flare.light.intensity = 100
        self._project.flare.light.position = QtCore.QPointF(0.66, 0.0)

        self._project.flare.lens.vendor = 'Fujifilm'
        self._project.flare.lens.lens = 'Fujifilm Fujinon XF27mm F2.8'

        self._project.flare.raytracing.wavelength_count = 5
        self._project.flare.raytracing.wavelength_sub_count = 8
        self._project.flare.raytracing.min_divisions = 16
        self._project.flare.raytracing.max_divisions = 128
        self._project.flare.raytracing.cull_percentage = 0.5
        self._project.flare.raytracing.min_sliver = 0.1

        self._project.flare.camera.fstop = 2.8

        self._project.ghost.aperture.shape.blades = 64

        self._project.flare.debug.ghost_enabled = False
        self._project.flare.debug.ghost = 295
        self._project.flare.debug.wireframe = False

        self._project.diagram.raytracing.ghost = -1
        self._project.diagram.raytracing.divisions = 16

        self._project.output.layer = api.Layer.FLARE
        self._project.output.path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '../../render/render2.exr')
        )
        # -----------

        self._project_path = ''
        self._project_hash = 0
        self._project_saved = False
        self._project_queue: api.Project | None = None

        self._rendering = False

        self.project_editor: ProjectEditor | None = None
        self.widget_added.connect(self._update_widget)

        self._init_engine()
        self._init_window()
        self._init_menu()
        self.load_state()

    def _init_engine(self) -> None:
        self.engine = Worker()

        # TODO: Remove QueuedConnection
        self.render_requested.connect(self.engine.render, QueuedConnection)
        self.layers_changed.connect(self.engine.set_layers, QueuedConnection)
        self.engine.rendered.connect(self._update_viewers, QueuedConnection)
        self.engine.progress_changed.connect(self._progress_changed, QueuedConnection)

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
        # view_menu.addSeparator()
        # action = QtWidgets.QAction('Reset', self)
        # action.triggered.connect(self.reset_window_state)
        # view_menu.addAction(action)

        # Engine
        # view_menu = self.menu_bar.addMenu('Engine')
        # action = QtWidgets.QAction('Restart', self)
        # action.setIcon(MaterialIcon('restart_alt'))
        # action.triggered.connect(self.restart)
        # view_menu.addAction(action)

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

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)

        QtCore.QTimer.singleShot(500, self.refresh)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.save_state()
        # self.engine.cleanup()
        super().closeEvent(event)

    def project(self) -> api.Project:
        """Return the project."""

        return self._project

    def set_project(self, project: api.Project) -> None:
        """Set the project. This updates the project_saved status."""

        self._project = project
        self._refresh_project_saved()
        if self.project_editor:
            self.project_editor.set_project(project)

    def project_path(self) -> str:
        """Return the project path."""

        return self._project_path

    def set_project_path(self, project_path: str) -> None:
        """Set the project path. This updates the project_saved status."""

        self._project_path = project_path
        self._project_hash = hash(self._project)
        self._refresh_project_saved()
        self._refresh_recent_paths()
        self._refresh_recent_menu()

    def save_state(self) -> None:
        """Save the state of the window."""

        state = State(
            main_window=self.state(),
            widgets=self._widget_states(),
        )
        StateManager.set(state)

    def load_state(self) -> None:
        """Load the state of the window."""

        state = StateManager.get()
        self.set_state(state.main_window)
        self._set_widget_states(state.widgets)
        if state.recent_paths:
            path = state.recent_paths[0]
            if project := ProjectManager.open(path):
                self.set_project(project)
                self.set_project_path(path)

    def load_project(self, path: str) -> None:
        """Load a project from the path."""

        if project := ProjectManager.open(path):
            self.set_project(project)
            self.set_project_path(path)

    def request_render(self, project: api.Project | None = None) -> None:
        """
        Request to render a project. If the engine is rendering, store the project in
        the queue instead.
        """

        if project is not None:
            self._project_queue = project

        if self._rendering:
            self.stop_requested.emit()
        elif self._project_queue is not None:  # and self._api_thread.isRunning():
            self._rendering = True
            self.render_requested.emit(self._project_queue)
            self._project_queue = None

    def request_disk_render(self) -> None:
        """Request a render and save the output to disk."""

        project = copy.deepcopy(self._project)
        project.output.write = True
        self.request_render(project)

    def refresh(self) -> None:
        """Refresh the Viewers."""

        self._update_layers()
        self.request_render(self._project)

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
            self._rendering = False
            self.request_render()

    def _project_editor_changed(self) -> None:
        """Handle the changing of the ProjectEditor."""

        if self.project_editor:
            self._project = self.project_editor.get_project()
            self._refresh_project_saved()
            self.request_render(self._project)

    def _position_changed(self, viewer: LayerViewer, position: QtCore.QPoint) -> None:
        """Handle the changing of position from a Viewer by updating the api.Project."""

        # Not every Viewer updates the project.
        if viewer.layer() not in (api.Layer.FLARE, api.Layer.STARBURST, api.Layer.COMP):
            return

        # Update project
        if self.project():
            ndc_position = QtCore.QPointF(
                (position.x() / viewer.resolution().width() * 2.0) - 1.0,
                (position.y() / viewer.resolution().height() * 2.0) - 1.0,
            )
            self._project.flare.light.position = ndc_position
            self._refresh_project_saved()

        # Update the ProjectEditor
        if self.project_editor:
            param = self.project_editor.parameter('flare.light.position')
            if param is not None:
                param.blockSignals(True)
                param.set_value(self._project.flare.light.position)
                param.blockSignals(False)

        self.request_render(self._project)

    def _update_layers(self) -> None:
        """Update the layers in the engine that should be rendered."""

        layers = []
        for dock_widget in self.dock_widgets():
            widget = dock_widget.currentWidget()
            if isinstance(widget, LayerViewer) and not widget.paused():
                layers.append(widget.layer())
        self.layers_changed.emit(tuple(layers))

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
            widget.layer_changed.connect(lambda: self.refresh())
            widget.pause_changed.connect(lambda: self.refresh())
            widget.refreshed.connect(self.refresh)

        elif isinstance(widget, ProjectEditor):
            widget.set_project(self._project)
            widget.parameter_changed.connect(self._project_editor_changed)
            if widget.render_button is not None:
                widget.render_button.clicked.connect(self.request_disk_render)
            self.project_editor = widget

        elif isinstance(widget, LogViewer):
            cache = self.log_bar.cache()
            if cache is not None:
                widget.set_cache(cache)

    def _refresh_project_saved(self) -> None:
        """Refresh the save status of a project by checking if it has changed."""

        # if quick and self._project_saved:
        #     # don't perform hash comparisons for performance
        #     return

        self._project_saved = hash(self._project) != self._project_hash
        self._refresh_window_title()

    def _refresh_window_title(self) -> None:
        """Refresh the window title depending on the save status of the project."""

        filename = os.path.basename(self._project_path)
        title = filename if filename else 'untitled'
        if self._project_saved:
            title = f'{title} *'
        self.setWindowTitle(title)

    def _refresh_recent_paths(self) -> None:
        """Refresh the recent paths and store them in the State."""

        if self._project_path:
            state = StateManager.get()
            paths = (p for p in state.recent_paths if p != self._project_path)
            state.recent_paths = tuple((self._project_path, *paths)[:10])
            StateManager.set(state)

    def _refresh_recent_menu(self) -> None:
        """Refresh the recent menu with the paths from the State."""

        self.recent_menu.clear()
        state = StateManager.get()
        for filename in state.recent_paths:
            action = QtWidgets.QAction(filename, self)
            action.triggered.connect(partial(ProjectManager.open, filename))
            self.recent_menu.addAction(action)

    # Menu

    def _file_new(self) -> None:
        project = ProjectManager.create()
        self.set_project(project)
        self.set_project_path('')

    def _file_save(self) -> None:
        if self._project_path:
            path = self._project_path
        else:
            path, filters = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Project', self._get_recent_dir(), '*.json'
            )
        if path:
            ProjectManager.save(self._project, path)
            self.set_project_path(path)

    def _file_save_as(self) -> None:
        path, filters = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save Project As', self._get_recent_dir(), '*.json'
        )
        if path:
            ProjectManager.save(self._project, path)
            self.set_project_path(path)

    def _file_open(self) -> None:
        path, filters = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open Project', self._get_recent_dir(), '*.json'
        )
        if path:
            if project := ProjectManager.open(path):
                self.set_project(project)
                self.set_project_path(path)

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

    @staticmethod
    def _get_recent_dir() -> str:
        """Return the recent dir."""

        state = StateManager.get()
        recent_dirs = (os.path.dirname(p) for p in state.recent_paths)

        return next(recent_dirs, os.path.expanduser('~'))
