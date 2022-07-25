import logging
import sys
from PySide2 import QtWidgets

from realflare.gui.logger import Logger
from qt_extensions import theme


def main():
    logging.getLogger().setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(theme.monokai)

    logger = Logger()
    logger.show()
    logging.warning('Test')

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
