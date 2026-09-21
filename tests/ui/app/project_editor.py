import tests
from flare.api.project import Project
from flare.ui import application
from flare.ui.app.widgets.project_editor import ProjectEditor


def main() -> None:
    with application():
        dialog = ProjectEditor()
        project = Project()
        dialog.set_project(project)
        dialog.show()


if __name__ == '__main__':
    tests.init()
    main()
