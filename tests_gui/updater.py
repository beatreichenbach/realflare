import logging
import sys

from PySide2 import QtWidgets

from realflare.update import UpdateDialog


def main():
    app = QtWidgets.QApplication(sys.argv)

    dialog = UpdateDialog()
    dialog.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    main()
