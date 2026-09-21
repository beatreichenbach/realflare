from flare.ui import application
from flare.ui.app import FlareDockWindow

dialog = None


def run_gui(project_path: str = '') -> None:
    """Show the main window, optionally loading a project."""

    with application():
        global dialog
        dialog = FlareDockWindow()

        if project_path:
            dialog.manager.open(project_path)
        elif recent := dialog.manager.recent_paths():
            dialog.manager.open(recent[0])

        dialog.show()
