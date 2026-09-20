import tests
from flare.gui.widgets.about import AboutDialog
from flare.utils.gui import application


def main() -> None:
    with application():
        dialog = AboutDialog()
        dialog.show()


if __name__ == '__main__':
    tests.init()
    main()
