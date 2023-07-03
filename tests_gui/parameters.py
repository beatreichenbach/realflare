import json
import logging
import sys
from PySide2 import QtWidgets

from realflare.api import data
from realflare.gui.parameters import ProjectEditor
from qt_extensions import theme
from qt_extensions.typeutils import basic, cast


def main():
    logging.getLogger().setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(theme.monokai)

    editor = ProjectEditor()

    project = editor.project()
    project.flare.lens.lens_model_path = r'$RES/model/Leica/35mm_1_4.json'
    project_string = json.dumps(basic(project), indent=4)
    project = cast(data.Project, json.loads(project_string))
    editor.set_project(project)

    editor.parameter_changed.connect(lambda: logging.debug(editor.project()))
    logging.debug(editor.state())

    editor.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
