from flare.gui.app import FlareDockWindow
from flare.utils.gui import application

dialog = None


def run_gui(project_path: str = '') -> None:
    """Show the main window, optionally loading a project."""

    with application():
        global dialog
        dialog = FlareDockWindow()

        if project_path:
            dialog.load_project(project_path)
        elif recent := dialog.manager.recent_paths():
            dialog.load_project(recent[0])

        dialog.show()
