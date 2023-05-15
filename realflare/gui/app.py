import inspect
import logging
import os
import sys
import webbrowser
from functools import partial
from importlib.metadata import version
from importlib.resources import files
from typing import Any

import pyopencl as cl
from PySide2 import QtCore, QtGui, QtWidgets

from qt_extensions.icons import MaterialIcon
from qt_extensions.logger import LogCache, LogBar, LogViewer
from realflare.gui.lensmodeleditor import LensModelDialog
from realflare.gui.parameters import ProjectEditor
from realflare.update import UpdateDialog
from realflare.api.data import Project, RenderElement, RenderImage
from realflare.api.engine import Engine, clear_cache
from realflare.gui.viewer import ElementViewer
from realflare.utils.storage import Storage, State

from realflare.gui.presetbrowser import PresetBrowser

from qt_extensions.mainwindow import DockWindow, DockWidgetState, SplitterState
from qt_extensions import theme
from qt_extensions.messagebox import MessageBox
from qt_extensions.typeutils import cast, cast_basic
from realflare.utils.timing import timer

# TODO: reconsider slot names, would it make more sense to split up functionality?
#  for example, instead of widget_add it could be store_widget_state.
#  also consider implementing QEvents to handle things such as widget_added etc.

# TODO: send project to engine, make sure only new results get stored in ram cache

# TODO: A quick tip: If all you want to do every 10ms is to draw a new point on a graph
#  (or some similar gui display), then draw to a QImage instead.
#  A QImage is not a gui object, so your worker thread can paint to it.
#  Then in main thread run a timer that calls update() at the update frequency you want.
#  A quarter to half second should be fine for most purposes.
#  In the repaint, just draw the qimage.
#  Or you could do the same thing with an array of points, etc.

# TODO: At the point destroyed() is emitted, the widget isn't a QWidget anymore,
#   just a QObject (as destroyed() is emitted from ~QObject)


logger = logging.getLogger(__name__)


def set_widget_state(widget: QtWidgets.QWidget, state: dict | None) -> None:
    if state is None:
        return
    if hasattr(widget, 'set_state') and inspect.ismethod(widget.set_state):
        widget.set_state(state)


def widget_state(widget: QtWidgets.QWidget) -> dict | None:
    if hasattr(widget, 'state') and inspect.ismethod(widget.state):
        return widget.state()


class MainWindow(DockWindow):
    render_requested: QtCore.Signal = QtCore.Signal(Project)
    stop_requested: QtCore.Signal = QtCore.Signal()
    elements_changed: QtCore.Signal = QtCore.Signal(list)

    default_state = {
        'widgets': [
            SplitterState(
                sizes=[1, 1],
                orientation=QtCore.Qt.Horizontal,
                states=[
                    DockWidgetState(
                        current_index=0,
                        widgets=[('Viewer 1', ElementViewer.__name__)],
                        detachable=True,
                        auto_delete=False,
                        is_center_widget=True,
                    ),
                    DockWidgetState(
                        current_index=0,
                        widgets=[('Parameters', ProjectEditor.__name__)],
                        detachable=True,
                        auto_delete=True,
                        is_center_widget=False,
                    ),
                ],
            )
        ]
    }

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.storage = Storage()
        self.project = Project()
        self.recent_dir = os.path.expanduser('~')
        self.elements = []
        self.rendering = False
        self.splash_screen = None

        self._project_queue = None
        self._project_path = ''
        self._project_hash = hash(self.project)
        self._project_changed = False
        self._device = ''

        self.show_splash_message('Loading User Interface...')
        self._init_log()
        self._init_widgets()
        self.show_splash_message('Loading Menu...')
        self._init_menu()
        self.show_splash_message('Loading Engine...')
        self._init_engine()
        self.show_splash_message('Loading Settings...')
        self.load_settings()

    def _init_log(self):
        # logging
        self.log_cache = LogCache()
        self.log_cache.connect_logger(logging.getLogger())

        # status bar
        self.log_bar = LogBar(self.log_cache)
        self.log_bar.open_viewer = lambda: self.show_widget(LogViewer)
        self.log_bar.names = ['root', 'realflare']
        self.log_bar.level = logging.INFO
        self.layout().addWidget(self.log_bar)

    def _init_engine(self):
        self.api_thread = QtCore.QThread()
        self.rendering = False
        self.engine = Engine(self.project.render.device)
        if self.engine.queue is None:
            return
        self.engine.moveToThread(self.api_thread)
        self.api_thread.start()

        self.engine.image_changed.connect(self._render_image_changed)
        # self.engine.render_finished.connect(self._render_finish)
        self.elements_changed.connect(self.engine.set_elements)
        self.render_requested.connect(self.engine.render)

    def _init_widgets(self):
        self.register_widget(ElementViewer, 'Viewer', unique=False)
        self.register_widget(ProjectEditor, 'Parameters')
        self.register_widget(LogViewer, 'Log')
        self.register_widget(PresetBrowser)
        self.register_widget(LensModelDialog, 'Lens Model Editor')

        # connect signals when new widgets are added
        self.widget_added.connect(self._widget_added)

    def _init_menu(self) -> None:
        menu_bar = QtWidgets.QMenuBar(self)
        self.layout().insertWidget(0, menu_bar)

        # file
        file_menu = menu_bar.addMenu('File')

        action = QtWidgets.QAction('New', self)
        action.setShortcut(QtGui.QKeySequence.New)
        action.triggered.connect(self.file_new)
        file_menu.addAction(action)
        action = QtWidgets.QAction('Open...', self)
        action.setIcon(MaterialIcon('file_open'))
        action.setShortcut(QtGui.QKeySequence.Open)
        action.triggered.connect(lambda: self.file_open())
        file_menu.addAction(action)
        self.recent_menu = file_menu.addMenu('Open Recent...')
        file_menu.addSeparator()

        action = QtWidgets.QAction('Settings...', self)
        action.setShortcut(QtGui.QKeySequence('Ctrl+Alt+S'))
        action.setIcon(MaterialIcon('settings'))
        action.triggered.connect(lambda: self.settings_open())
        file_menu.addAction(action)
        file_menu.addSeparator()

        action = QtWidgets.QAction('Save', self)
        action.setIcon(MaterialIcon('save'))
        action.setShortcut(QtGui.QKeySequence.Save)
        action.triggered.connect(self.file_save)
        file_menu.addAction(action)
        action = QtWidgets.QAction('Save As...', self)
        action.setShortcut(QtGui.QKeySequence('Ctrl+Shift+S'))
        action.triggered.connect(self.file_save_as)
        file_menu.addAction(action)
        file_menu.addSeparator()

        action = QtWidgets.QAction('Exit', self)
        action.setShortcut(QtGui.QKeySequence.Quit)
        action.triggered.connect(self.close)
        file_menu.addAction(action)

        # view
        view_menu = menu_bar.addMenu('View')
        action = QtWidgets.QAction('New Viewer', self)
        action.setIcon(MaterialIcon('preview'))
        action.triggered.connect(partial(self.show_widget, ElementViewer))
        view_menu.addAction(action)
        action = QtWidgets.QAction('Show Parameters', self)
        action.setIcon(MaterialIcon('tune'))
        action.triggered.connect(partial(self.show_widget, ProjectEditor))
        view_menu.addAction(action)
        action = QtWidgets.QAction('Show Preset Browser', self)
        action.setIcon(MaterialIcon('perm_media'))
        action.triggered.connect(partial(self.show_widget, PresetBrowser))
        view_menu.addAction(action)
        action = QtWidgets.QAction('Show Log', self)
        action.setIcon(MaterialIcon('article'))
        action.triggered.connect(partial(self.show_widget, LogViewer))
        view_menu.addAction(action)
        action = QtWidgets.QAction('Show Lens Model Editor', self)
        action.setIcon(MaterialIcon('camera'))
        action.triggered.connect(partial(self.show_widget, LensModelDialog))
        view_menu.addAction(action)
        view_menu.addSeparator()
        action = QtWidgets.QAction('Reset', self)
        action.triggered.connect(self.reset_state)
        view_menu.addAction(action)

        # engine
        view_menu = menu_bar.addMenu('Engine')
        action = QtWidgets.QAction('Restart', self)
        action.setIcon(MaterialIcon('restart_alt'))
        action.triggered.connect(self.restart)
        view_menu.addAction(action)

        # help
        help_menu = menu_bar.addMenu('Help')
        action = QtWidgets.QAction('Documentation', self)
        action.setIcon(MaterialIcon('question_mark'))
        action.triggered.connect(self.help_documentation)
        help_menu.addAction(action)
        action = QtWidgets.QAction('Report an Issue', self)
        action.setIcon(MaterialIcon('bug_report'))
        action.triggered.connect(self.help_report_bug)
        help_menu.addAction(action)
        help_menu.addSeparator()
        action = QtWidgets.QAction('Check for Updates', self)
        action.setIcon(MaterialIcon('update'))
        action.triggered.connect(self.help_update)
        help_menu.addAction(action)
        action = QtWidgets.QAction('About', self)
        action.triggered.connect(self.help_about)
        help_menu.addAction(action)

    @property
    def project_path(self) -> str:
        return self._project_path

    @project_path.setter
    def project_path(self, value: str) -> None:
        self._project_path = value
        self.update_window_title()

    def closeEvent(self, event):
        # project
        self._test_changes(quick=False)
        if self._project_changed:
            result = QtWidgets.QMessageBox.warning(
                self,
                'Save Changes?',
                'Project has been modified, save changes?',
                QtWidgets.QMessageBox.Yes
                | QtWidgets.QMessageBox.No
                | QtWidgets.QMessageBox.Cancel,
            )
            if result == QtWidgets.QMessageBox.Yes:
                if not self.file_save():
                    event.ignore()
                    return
            elif result == QtWidgets.QMessageBox.No:
                pass
            else:
                event.ignore()
                return

        # engine
        if self.api_thread is not None:
            self.api_thread.quit()

        # state
        self.save_settings()

        super().closeEvent(event)

    def file_new(self) -> None:
        self.set_project(Project())
        self.project_path = ''

    def file_open(self, filename: str | None = None) -> None:
        if filename is None:
            filename, filters = QtWidgets.QFileDialog.getOpenFileName(
                self, 'Open Project', self.recent_dir, '*.json'
            )
            if os.path.exists(os.path.dirname(filename)):
                self.recent_dir = os.path.dirname(filename)
        if os.path.exists(filename):
            self.project_path = filename
            self.storage.update_recent_paths(filename)
            self._update_recent_menu()
            data = self.storage.load_data(filename)
            project = cast(Project, data)
            self.set_project(project)

    def file_save(self, prompt: bool = False) -> bool:
        if not self.project_path or prompt:
            filename, filters = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Project', self.recent_dir, '*.json'
            )
            if not filename:
                return False
            self.project_path = filename
        self.storage.update_recent_paths(self.project_path)
        self._update_recent_menu()

        data = cast_basic(self.project)
        result = self.storage.save_data(data, self.project_path)

        if result:
            self._project_hash = hash(self.project)
            self._test_changes(quick=False)
        return result

    def file_save_as(self) -> None:
        self.file_save(prompt=True)

    def help_about(self) -> None:
        message_box = QtWidgets.QMessageBox(self)
        message_box.setWindowTitle('About')
        message_box.setText('Realflare')

        # text
        package_version = version('realflare')
        platforms = cl.get_platforms()
        if platforms:
            cl_version = platforms[0].version
        else:
            cl_version = 'No CL Platforms found'
        pyside_version = version('PySide2')
        text = (
            f'Realflare version: {package_version}\n'
            f'OpenCL version: {cl_version}\n'
            f'PySide version: {pyside_version}\n'
            '\n'
            'Copyright © Beat Reichenbach'
        )
        message_box.setInformativeText(text)

        # icon
        icon_path = files('realflare').joinpath('assets').joinpath('icon.png')
        pixmap = QtGui.QPixmap(str(icon_path))
        message_box.setIconPixmap(pixmap)

        message_box.exec_()

    # noinspection PyMethodMayBeStatic
    def help_documentation(self) -> None:
        webbrowser.open('https://beatreichenbach.github.io/realflare/reference/flare/')

    # noinspection PyMethodMayBeStatic
    def help_report_bug(self) -> None:
        webbrowser.open('https://github.com/beatreichenbach/realflare/issues/new')

    def help_update(self) -> None:
        dialog = UpdateDialog(self)
        dialog.exec_()

    def load_settings(self):
        # state
        self.storage.load_state()
        if self.storage.state.window_state:
            self.set_state(self.storage.state.window_state)
        else:
            self.reset_state()

        for title, state in self.storage.state.widget_states.items():
            widget = self._widgets.get(title)
            set_widget_state(widget, state)

        # settings
        self.storage.load_settings()
        self._update_recent_menu()

        if self.storage.settings.recent_paths:
            self.file_open(self.storage.settings.recent_paths[0])
        else:
            self.update_window_title()

    @timer
    def refresh(self) -> None:
        self._update_elements()
        self.request_render(self.project)

    def reset_state(self) -> None:
        self.set_state(self.default_state)

    def restart(self):
        if self.api_thread is not None:
            self.api_thread.quit()
        clear_cache()
        self._init_engine()
        self._render_finish()

    def save_settings(self):
        self.storage.state.window_state = self.state()

        for title, widget in self._widgets.items():
            state = widget_state(widget)
            if state is not None:
                self.storage.state.widget_states[title] = state

        self.storage.save_state()

    # def save_output(self):
    #     # TODO: This is just temporary
    #     output_path = self.project.render.output_path
    #     colorspace = self.project.render.colorspace
    #     if not output_path:
    #         return
    #     for widget in self._widgets.values():
    #         if isinstance(widget, ElementViewer):
    #             array = widget.item.array
    #             self.engine.write_image(output_path, array=array, colorspace=colorspace)
    #             return

    def set_project(self, project: Project):
        self.project = project
        self._project_hash = hash(self.project)
        for title, widget in self._widgets.items():
            if isinstance(widget, ProjectEditor):
                widget.set_project(self.project)

    def show_widget(self, cls: type[QtWidgets.QWidget]) -> None:
        try:
            dock_widget = self.create_dock_widget(cls)
            dock_widget.float()
            dock_widget.show()
        except ValueError:
            # widget already exists
            for widget in self._widgets.values():
                if isinstance(widget, cls):
                    self.focus_widget(widget)
                    break

    def show_splash_message(self, message: str) -> None:
        if isinstance(self.splash_screen, QtWidgets.QSplashScreen):
            self.splash_screen.showMessage(
                message,
                QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeft,
                QtGui.QColor('white'),
            )

    def update_window_title(self):
        filename = os.path.basename(self._project_path)
        title = filename if filename else 'untitled'
        if self._project_changed:
            title = f'{title} *'
        self.setWindowTitle(title)

    def request_render(
        self,
        project: Project | None = None,
    ) -> None:
        # try starting a render, if the engine is rendering,
        # store the project in the queue instead
        if project is not None:
            self._project_queue = project

        if self.rendering:
            self.stop_requested.emit()
        elif (
            self._project_queue is not None
            and self.api_thread is not None
            and self.api_thread.isRunning()
        ):
            self._project_queue = None
            self.rendering = True
            self.log_cache.clear()
            # self.render_requested.emit(self._project_queue)

    # def _load_preset(self, config: Any):
    #     if isinstance(config, (Flare, Flare.Ghost, Flare.Starburst)):
    #         cls = FlareEditor
    #     elif isinstance(config, Render.Quality):
    #         cls = RenderEditor
    #     else:
    #         return
    #
    #     for widget in self._widgets.values():
    #         if isinstance(widget, cls):
    #             widget.load_preset(config=config)

    def _position_changed(self, viewer: ElementViewer, position: QtCore.QPoint) -> None:
        # set the position of the light in the editor when clicking on a viewer

        if viewer.element != RenderElement.FLARE:
            return

        # update project
        self.project.flare.light.position = viewer.relative_position(position)
        self._test_changes()
        self.request_render()

        # update flare editor
        for widget in self._widgets.values():
            if isinstance(widget, ProjectEditor):
                widgets = widget.widgets()
                position_parameter = widgets['flare']['light']['position']
                position_parameter.blockSignals(True)
                position_parameter.value = self.project.flare.light.position
                position_parameter.blockSignals(False)
                break

    def _project_editor_changed(self, editor: ProjectEditor) -> None:
        self.project = editor.project()
        self._test_changes()
        self.request_render()

    def _render_image_changed(self, image: RenderImage) -> None:
        for widget in self._widgets.values():
            if isinstance(widget, ElementViewer) and widget.element == image.type:
                widget.update_image(image.image.array)

    # def _render_finish(self):
    #     self.rendering = False
    #     self.try_render()

    def _test_changes(self, quick: bool = True) -> None:
        # checks whether project has changed

        if self.project.render.device != self._device:
            self._device = self.project.render.device
            self.restart()

        if quick and self._project_changed:
            # don't perform hash comparisons for performance
            return

        self._project_changed = hash(self.project) != self._project_hash
        self.update_window_title()

    def _update_elements(self):
        self.elements = []
        for dock_widget in self.dock_widgets():
            widget = dock_widget.currentWidget()
            if isinstance(widget, ElementViewer) and not widget.paused:
                self.elements.append(widget.element)
        self.elements_changed.emit(self.elements)
        self.request_render()

    def _update_recent_menu(self):
        self.recent_menu.clear()
        for filename in self.storage.settings.recent_paths:
            action = QtWidgets.QAction(filename, self)
            action.triggered.connect(partial(self.file_open, filename))
            self.recent_menu.addAction(action)

    def _widget_added(self, widget: QtWidgets.QWidget) -> None:
        # restore state
        title = self.widget_title(widget)
        if title is not None:
            state = self.storage.state.widget_states.get(title)
            set_widget_state(widget, state)

        # reconnect signals
        if isinstance(widget, ElementViewer):
            widget.position_changed.connect(partial(self._position_changed, widget))
            widget.element_changed.connect(lambda: self._update_elements())
            widget.pause_changed.connect(lambda: self._update_elements())
            widget.refreshed.connect(self.refresh)
        elif isinstance(widget, ProjectEditor):
            widget.set_project(self.project)
            widget.parameter_changed.connect(
                lambda: self._project_editor_changed(widget)
            )
            # widget.save_action.triggered.connect(lambda: self.save_output())
        elif isinstance(widget, PresetBrowser):
            widget.load_requested.connect(self._load_preset)
        elif isinstance(widget, LogViewer):
            widget.set_cache(self.log_cache)

    # def _widget_remove(self, widget: QtWidgets.QWidget):
    #     # store the widget state for unique registered widgets
    #     logging.debug(widget)
    #     cls = type(widget)
    #     registered_widget = self.registered_widgets.get(cls.__name__)
    #     if registered_widget is not None and registered_widget.unique:
    #         title = self.widget_title(widget)
    #         if title is not None:
    #             state = widget_state(widget)
    #             if state is not None:
    #                 logging.debug(state)
    #                 self.settings.state.widget_states[title] = state


def exec_():
    # set application
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('realflare')
    app.setApplicationDisplayName('Realflare')
    app.setApplicationVersion(version('realflare'))
    icon_path = files('realflare').joinpath('assets').joinpath('icon.png')
    icon = QtGui.QIcon(str(icon_path))
    app.setWindowIcon(icon)

    # theme
    theme.apply_theme(theme.monokai)

    # splash screen
    splash_path = files('realflare').joinpath('assets').joinpath('splash.png')
    splash_pixmap = QtGui.QPixmap(str(splash_path))
    splash_size = QtCore.QSize(800, 500)
    splash_pixmap = splash_pixmap.scaled(splash_size, QtCore.Qt.KeepAspectRatio)
    splash_screen = QtWidgets.QSplashScreen(splash_pixmap)
    splash_screen.show()

    # main window
    window = MainWindow()
    window.splash_screen = splash_screen
    window.show()
    splash_screen.finish(window)

    # render
    window.refresh()

    return app.exec_()


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    logging.getLogger().setLevel(logging.DEBUG)
    logger.debug(__name__)
    logging.debug('root')
    exec_()
