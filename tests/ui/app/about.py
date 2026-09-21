import tests
from flare.ui import application
from flare.ui.app.widgets.about import AboutDialog


def main() -> None:
    with application():
        dialog = AboutDialog()
        dialog.show()


if __name__ == '__main__':
    tests.init()
    main()
