import logging
import sys

from PySide2 import QtWidgets

from qt_extensions import theme
from realflare.update import UpdateDialog


def main():
    logging.getLogger().setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(theme.monokai)

    dialog = UpdateDialog()
    dialog.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
