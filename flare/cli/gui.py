from typing import Annotated

import typer

dialog = None


def gui(
    project_path: Annotated[str, typer.Option('--project', '-p')] = '',
) -> None:
    from flare.gui.app import FlareDockWindow
    from flare.utils.gui import application

    with application():
        global dialog
        dialog = FlareDockWindow()

        if project_path:
            dialog.load_project(project_path)

        dialog.show()
