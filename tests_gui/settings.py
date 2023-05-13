import logging
import sys

from PySide2 import QtWidgets

from realflare.gui.settings import SettingsDialog
from qt_extensions import theme


def main():
    logging.getLogger().setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(theme.monokai)

    dialog = SettingsDialog()
    dialog.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
