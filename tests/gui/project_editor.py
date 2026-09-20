import tests
from flare.api.project import Project
from flare.gui.widgets.project_editor import ProjectEditor
from flare.utils.gui import application


def main() -> None:
    with application():
        dialog = ProjectEditor()
        project = Project()
        dialog.set_project(project)
        dialog.show()


if __name__ == '__main__':
    tests.init()
    main()
