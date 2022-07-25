import logging
import sys
from PySide2 import QtWidgets

from realflare.gui.presetbrowser import PresetBrowser
from realflare.gui.settings import Settings
from qt_extensions import theme


def main():
    logging.getLogger().setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(theme.monokai)

    path = Settings().decode_path('$PRESET')
    logging.debug(path)
    widget = PresetBrowser(path)
    widget.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
