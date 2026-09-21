import tests
from flare.ui import application
from flare.ui.app import FlareDockWindow


def main() -> None:
    with application():
        dialog = FlareDockWindow()
        dialog.show()


if __name__ == '__main__':
    tests.init()
    main()
