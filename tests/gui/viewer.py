import numpy as np

import tests
from flare.utils.gui import application
from flare.widgets.viewer.viewer import Viewer


def main() -> None:
    with application():
        array = np.tile(
            np.linspace(start=0, stop=2, num=512, dtype=np.float32), reps=(512, 1)
        )
        r = np.swapaxes(array, 0, 1)
        g = np.swapaxes(array, 0, 1)
        b = np.zeros((512, 512), np.float32)
        a = np.ones((512, 512), np.float32)
        image_array = np.dstack((r, g, b, a))

        widget = Viewer()
        widget.show()
        widget.set_array(image_array)


if __name__ == '__main__':
    tests.init()
    main()
