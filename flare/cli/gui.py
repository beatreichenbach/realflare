import logging

import flare
from flare.ui import application
from flare.ui.app import FlareDockWindow

dialog = None


def run_gui(project_path: str = '') -> None:
    """Show the main window, optionally loading a project."""

    logging.getLogger(flare.__name__).setLevel(logging.DEBUG)

    with application():
        global dialog
        dialog = FlareDockWindow()
        dialog.show()

        if project_path:
            dialog.manager.open(project_path)
        elif recent := dialog.manager.recent_paths():
            dialog.manager.open(recent[0])
