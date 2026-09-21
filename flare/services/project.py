import logging

from qtpy import QtCore

from flare.api import Project
from flare.infrastructure.storage import ProjectIO, StateManager

logger = logging.getLogger(__name__)

MAX_RECENT_PATHS = 10


class ProjectManager(QtCore.QObject):
    """
    Manage the current project session.

    Track the active Project, its file path, whether it has unsaved changes and the
    list of recently opened paths. Loading and saving is delegated to ProjectIO.
    """

    project_changed: QtCore.Signal = QtCore.Signal(Project)
    path_changed: QtCore.Signal = QtCore.Signal(str)
    modified_changed: QtCore.Signal = QtCore.Signal(bool)
    recent_paths_changed: QtCore.Signal = QtCore.Signal(tuple)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

        self._project = ProjectIO.create()
        self._path = ''
        self._saved_hash = hash(self._project)
        self._modified = False
        self._recent_paths = StateManager.get().recent_paths

    def project(self) -> Project:
        """Return the current Project."""

        return self._project

    def path(self) -> str:
        """Return the path of the current Project, or an empty string if untitled."""

        return self._path

    def modified(self) -> bool:
        """Return whether the current Project has unsaved changes."""

        return hash(self._project) != self._saved_hash

    def recent_paths(self) -> tuple[str, ...]:
        """Return the recently opened paths, most recent first."""

        return self._recent_paths

    def new(self) -> None:
        """Replace the current Project with a new one."""

        self.set_project(ProjectIO.create())

    def open(self, path: str) -> bool:
        """Return whether a Project was loaded from a file."""

        if not (project := ProjectIO.open(path)):
            return False

        self.set_project(project, path)
        return True

    def save(self, path: str = '') -> bool:
        """Return whether the current Project was saved."""

        path = path or self._path
        return self.save_as(path)

    def save_as(self, path: str) -> bool:
        """Return whether the current Project was saved to a path."""

        if not path:
            return False

        ProjectIO.save(self._project, path)
        self._saved_hash = hash(self._project)
        self.set_path(path)
        self._refresh_modified()
        return True

    def set_project(self, project: Project, path: str = '') -> None:
        """Replace the current Project and reset its saved state."""

        self._project = project
        self._saved_hash = hash(project)

        self.set_path(path)
        self.project_changed.emit(project)
        self._refresh_modified()

    def update_project(self, project: Project) -> None:
        """Set a modified Project without resetting its saved state."""

        self._project = project
        self.project_changed.emit(project)
        self._refresh_modified()

    def set_light_position(self, position: QtCore.QPointF) -> None:
        """Set the position of the light source and mark the project modified."""

        self._project.flare.light.position = position
        self.update_project(self._project)

    def set_path(self, path: str) -> None:
        """Set the file path and record it in the recent paths."""

        self._path = path
        self.path_changed.emit(path)
        if path:
            self._add_recent(path)

    def _refresh_modified(self) -> None:
        """Emit `modified_changed` when the save state changed."""

        modified = self.modified()
        if modified != self._modified:
            self._modified = modified
            self.modified_changed.emit(modified)

    def _add_recent(self, path: str) -> None:
        """Store a path at the front of the recent paths."""

        paths = (path, *(p for p in self._recent_paths if p != path))
        self._recent_paths = paths[:MAX_RECENT_PATHS]

        state = StateManager.get()
        state.recent_paths = self._recent_paths
        StateManager.set(state)

        self.recent_paths_changed.emit(self._recent_paths)
