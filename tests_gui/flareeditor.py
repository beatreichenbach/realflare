import dataclasses
import json
import logging
import sys
from PySide2 import QtWidgets

from realflare.api import data
from realflare.gui.flareeditor import FlareEditor
from qt_extensions import theme
from qt_extensions.typeutils import cast_basic, cast


def main():
    logging.getLogger().setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(theme.monokai)

    editor = FlareEditor()
    # editor.values_changed.connect(logging.debug)

    config = editor.flare_config()
    config.lens.prescription_path = r'$RES/model/Leica/35mm_1_4.json'
    # config.lens.glasses_path = r'C:\Users\Beat\.realflare\library\glass\schott'
    config_dict = dataclasses.asdict(config)
    config_dict = cast_basic(config_dict)
    config_string = json.dumps(config_dict, indent=4)
    config = cast(data.Flare, json.loads(config_string))
    editor.update_editor(config)

    # editor.parameter_changed.connect(logging.debug)
    editor.parameter_changed.connect(lambda: logging.debug(editor.flare_config()))

    editor.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
