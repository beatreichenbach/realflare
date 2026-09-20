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

        dialog.show()
