import logging
import sys

import numpy as np
from PySide2 import QtWidgets

from qt_extensions import theme
from realflare.gui.viewer import ElementViewer
from realflare.storage import Storage

storage = Storage()
storage.update_ocio()


def main():
    logging.getLogger().setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(theme.monokai)

    viewer = ElementViewer()
    array = np.tile(np.linspace(0, 1, 512), (512, 1))
    image_array = np.dstack((array, array, array))
    viewer.set_array(image_array)

    viewer.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
