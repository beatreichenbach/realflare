import tests
from flare.ui import application
from flare.ui.app import FlareDockWindow


def main() -> None:
    with application():
        window = FlareDockWindow()
        window.show()

        if recent := window.manager.recent_paths():
            window.manager.open(recent[0])


if __name__ == '__main__':
    tests.init()
    main()
