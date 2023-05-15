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
from realflare.api.data import Project, RenderElement, Flare, Render, RenderImage
from realflare.api.engine import Engine, clear_cache
from realflare.gui.viewer import ElementViewer
from realflare.utils.settings import Settings
from realflare.gui.flareeditor import FlareEditor
from realflare.gui.rendereditor import RenderEditor

from realflare.gui.presetbrowser import PresetBrowser

from qt_extensions.mainwindow import DockWindow, DockWidgetState, SplitterState
from qt_extensions import theme
from qt_extensions.messagebox import MessageBox
from qt_extensions.typeutils import cast, cast_basic
from realflare.utils.timing import timer


# TODO: send project to engine, make sure only new results get stored in ram cache


class MainWindow(DockWindow):
    render_requested: QtCore.Signal = QtCore.Signal(Project)
    stop_requested: QtCore.Signal = QtCore.Signal()
    elements_changed: QtCore.Signal = QtCore.Signal(list)

    def __init__(self, splash_screen, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.splash_screen = splash_screen

        self.api_thread: QtCore.QThread | None = None
        self.rendering: bool = False
        self.settings = Settings()
        self.project = Project()
        self.elements = []

        self.project_path = ''
        self.recent_dir = os.path.expanduser('~')

        self._project_queue: Project | None = None
        self._project_path = ''
        self._project_hash = hash(self.project)
        self._project_changed = False
        self._device = ''

        # logging
        self.log_cache = LogCache()
        self.log_cache.connect_logger(logging.getLogger())

        # status bar
        self.log_bar = LogBar(self.log_cache)
        self.log_bar.open_viewer = lambda: self.show_widget(LogViewer)
        self.log_bar.names = ['root', 'realflare']
        self.log_bar.level = logging.INFO
        self.layout().addWidget(self.log_bar)

        self._init_widgets()
        self._init_menu()
        self.load_settings()

        self._init_engine()

    def _init_engine(self):
        self.splash_screen.showMessage(
            'Loading Engine...',
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeft,
            QtGui.QColor('white'),
        )
        self.api_thread = QtCore.QThread()
        device = self.project.render.device
        self.engine = Engine(device)
        if self.engine.queue is None:
            return
        self.engine.moveToThread(self.api_thread)
        self.api_thread.start()

        self.engine.image_changed.connect(self._render_element_change)
        self.engine.render_finished.connect(self._render_finish)
        self.elements_changed.connect(self.engine.set_elements)
        self.render_requested.connect(self.engine.render)

    def _init_widgets(self):
        self.splash_screen.showMessage(
            'Loading Widgets...',
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeft,
            QtGui.QColor('white'),
        )
        self.register_widget(ElementViewer, 'Viewer', unique=False)
        self.register_widget(ProjectEditor, 'Parameters')
        # self.register_widget(RenderEditor)
        self.register_widget(LogViewer, 'Log')
        self.register_widget(PresetBrowser)
        self.register_widget(LensModelDialog, 'Lens Model Editor')

        # connect signals when new widgets are added
        self.widget_added.connect(self._widget_add)

    def _init_menu(self) -> None:
        self.splash_screen.showMessage(
            'Loading Menus...',
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeft,
            QtGui.QColor('white'),
        )
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
        action.triggered.connect(self.reset_view)
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
        filename = os.path.basename(self._project_path)
        title = filename if filename else 'untitled'
        self.setWindowTitle(title)

    def closeEvent(self, event):
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

        if self.api_thread is not None:
            self.api_thread.quit()
        self.save_settings()
        super().closeEvent(event)

    def file_new(self) -> None:
        self._update_project(Project())
        self.project_path = ''

    def file_open(self, filename: str | None = None) -> None:
        if filename is None:
            filename, filters = QtWidgets.QFileDialog.getOpenFileName(
                self, 'Open Project', self.recent_dir, '*.json'
            )
            if os.path.exists(os.path.dirname(filename)):
                self.recent_dir = os.path.dirname(filename)
        if os.path.exists(filename):
            data = self.settings.load_data(filename)
            project = cast(Project, data)
            self._update_project(project)
            self.project_path = filename
            self.settings.update_recent_paths(filename)
            self._update_recent_menu()

    def file_save(self, prompt: bool = False) -> bool:
        if not self.project_path or prompt:
            path, filters = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save Project', self.recent_dir, '*.json'
            )
            if not path:
                return False
            self.project_path = path
        data = cast_basic(self.project)
        self.settings.update_recent_paths(self.project_path)
        self._update_recent_menu()
        result = self.settings.save_data(data, self.project_path)

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
        self.settings.load()

        settings_config = self.settings.config

        if settings_config.window_state:
            self.set_state(settings_config.window_state)
        else:
            self.reset_view()

        # for title, state in settings_config.widget_states.items():
        #     widget = self._widgets.get(title)
        #     if hasattr(widget, 'set_state'):
        #         widget.set_state(state)

        self._update_recent_menu()

        if self.settings.config.recent_paths:
            self.file_open(self.settings.config.recent_paths[0])

    @timer
    def refresh(self) -> None:
        self._update_elements()
        self.try_render(self.project)

    def reset_view(self) -> None:
        # reset the view to default window states
        # window_states = [
        #     SplitterState(
        #         sizes=[1, 1],
        #         orientation=QtCore.Qt.Horizontal,
        #         states=[
        #             DockWidgetState(
        #                 current_index=0,
        #                 widgets=[
        #                     ('Viewer 1', ElementViewer.__name__),
        #                 ],
        #                 detachable=True,
        #                 auto_delete=False,
        #                 is_center_widget=True,
        #             ),
        #             DockWidgetState(
        #                 current_index=0,
        #                 widgets=[
        #                     ('Flare Editor', FlareEditor.__name__),
        #                     ('Render Editor', RenderEditor.__name__),
        #                 ],
        #                 detachable=True,
        #                 auto_delete=True,
        #                 is_center_widget=False,
        #             ),
        #         ],
        #     )
        # ]
        self.set_state({})

    def restart(self):
        if self.api_thread is not None:
            self.api_thread.quit()
        clear_cache()
        self._init_engine()
        self._render_finish()

    def save_settings(self):
        self.settings.project = self.project

        self.settings.config.window_state = self.state()

        # widget_states = {}
        # for title, widget in self._widgets.items():
        #     if hasattr(widget, 'state'):
        #         widget_states[title] = widget.state()
        # self.settings.config.widget_states = widget_states

        self.settings.save()

    def save_output(self):
        # TODO: This is just temporary
        output_path = self.project.render.output_path
        colorspace = self.project.render.colorspace
        if not output_path:
            return
        for widget in self._widgets.values():
            if isinstance(widget, ElementViewer):
                array = widget.item.array
                self.engine.write_image(output_path, array=array, colorspace=colorspace)
                return

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

    def try_render(
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

    def _load_preset(self, config: Any):
        if isinstance(config, (Flare, Flare.Ghost, Flare.Starburst)):
            cls = FlareEditor
        elif isinstance(config, Render.Quality):
            cls = RenderEditor
        else:
            return

        for widget in self._widgets.values():
            if isinstance(widget, cls):
                widget.load_preset(config=config)

    def _render_element_change(self, element: RenderImage) -> None:
        for widget in self._widgets.values():
            if isinstance(widget, ElementViewer) and widget.element == element.type:
                widget.update_image(element.image.array)

    def _render_finish(self):
        self.rendering = False
        self.try_render()

    def _test_changes(self, quick: bool = True) -> None:
        # checks whether project has changed

        if quick and self._project_changed:
            # don't perform hash comparisons for performance
            return

        if hash(self.project) != self._project_hash:
            self._project_changed = True
            title = self.windowTitle().strip('*').strip()
            self.setWindowTitle(f'{title} *')
        else:
            self._project_changed = False
            title = self.windowTitle().strip('*').strip()
            self.setWindowTitle(title)

    def _update_elements(self):
        self.elements = []
        for dock_widget in self.dock_widgets():
            widget = dock_widget.currentWidget()
            if isinstance(widget, ElementViewer) and not widget.paused:
                self.elements.append(widget.element)
        self.elements_changed.emit(self.elements)
        self.try_render()

    def _update_flare_config(self, editor: FlareEditor):
        self.project.flare = editor.flare_config()
        self._test_changes()
        self.try_render()

    def _update_render_config(self, editor: RenderEditor):
        self.project.render = editor.render_config()

        if self.project.render.system.device != self._device:
            self._device = self.project.render.system.device
            self.restart()

        self._test_changes()
        self.try_render()

    def _update_recent_menu(self):
        self.recent_menu.clear()
        for filename in self.settings.config.recent_paths:
            action = QtWidgets.QAction(filename, self)
            action.triggered.connect(partial(self.file_open, filename))
            self.recent_menu.addAction(action)

    def _update_project(self, project: Project):
        self.project = project
        self._project_hash = hash(self.project)
        for title, widget in self._widgets.items():
            if isinstance(widget, FlareEditor):
                widget.update_editor(self.project.flare)
            elif isinstance(widget, RenderEditor):
                widget.update_editor(self.project.render)

    def _update_position(self, viewer: ElementViewer, position: QtCore.QPoint) -> None:
        # set the position of the light when clicking on a viewer

        if viewer.element != RenderElement.FLARE:
            return

        # update project
        self.project.flare.light_position = viewer.relative_position(position)
        self._test_changes()
        self.try_render()

        # update flare editor
        for widget in self._widgets.values():
            if isinstance(widget, FlareEditor):
                widgets = widget.widgets()
                position_parameter = widgets['light_position']
                position_parameter.blockSignals(True)
                position_parameter.value = viewer.relative_position(position)
                position_parameter.blockSignals(False)
                break

    def _widget_add(self, widget: QtWidgets.QWidget) -> None:
        # restore state
        for title, w in self._widgets.items():
            if widget == w and hasattr(widget, 'state'):
                state = self.settings.config.widget_states.get(title)
                if state is not None:
                    widget.state = state

        # reconnect signals
        if isinstance(widget, ElementViewer):
            widget.position_changed.connect(partial(self._update_position, widget))
            widget.element_changed.connect(lambda: self._update_elements())
            widget.pause_changed.connect(lambda: self._update_elements())
            widget.refreshed.connect(self.refresh)
        elif isinstance(widget, FlareEditor):
            widget.update_editor(self.project.flare)
            widget.parameter_changed.connect(lambda: self._update_flare_config(widget))
        elif isinstance(widget, RenderEditor):
            widget.update_editor(self.project.render)
            widget.parameter_changed.connect(lambda: self._update_render_config(widget))
            widget.save_action.triggered.connect(lambda: self.save_output())
        elif isinstance(widget, PresetBrowser):
            widget.load_requested.connect(self._load_preset)
        elif isinstance(widget, LogViewer):
            widget.set_cache(self.log_cache)


def exec_():
    app = QtWidgets.QApplication(sys.argv)

    app.setApplicationName('realflare')
    app.setApplicationVersion(version('realflare'))
    app.setApplicationDisplayName('Realflare')
    icon_path = files('realflare').joinpath('assets').joinpath('icon.png')
    icon = QtGui.QIcon(str(icon_path))
    app.setWindowIcon(icon)

    theme.apply_theme(theme.monokai)

    splash_path = files('realflare').joinpath('assets').joinpath('splash.png')
    splash_pixmap = QtGui.QPixmap(str(splash_path))
    splash_pixmap = splash_pixmap.scaled(
        QtCore.QSize(800, 500), QtCore.Qt.KeepAspectRatio
    )
    splash_screen = QtWidgets.QSplashScreen(splash_pixmap)
    splash_screen.show()
    splash_screen.showMessage(
        'Loading Flares...',
        QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeft,
        QtGui.QColor('white'),
    )
    app.processEvents()

    window = MainWindow(splash_screen)
    window.show()
    splash_screen.finish(window)
    window.refresh()
    logging.warning('hello')

    return app.exec_()


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    exec_()
