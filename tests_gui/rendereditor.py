import dataclasses
import json
import logging
import sys
from PySide2 import QtWidgets

from realflare.api import data
from realflare.gui.rendereditor import RenderEditor
from qt_extensions import theme
from qt_extensions.typeutils import cast_basic, cast


def main():
    logging.getLogger().setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(theme.monokai)

    editor = RenderEditor()

    config = editor.render_config()
    config_dict = cast_basic(dataclasses.asdict(config))
    config_string = json.dumps(config_dict, indent=4)
    config = cast(data.Render, json.loads(config_string))
    editor.update_editor(config)
    editor.parameter_changed.connect(lambda p: logging.debug(p.value))

    editor.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
