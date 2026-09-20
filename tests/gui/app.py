import tests
from flare.gui.app import FlareDockWindow
from flare.utils.gui import application


def main() -> None:
    with application():
        dialog = FlareDockWindow()
        dialog.show()


if __name__ == '__main__':
    tests.init()
    main()
