import tests
from flare.gui.widgets.preferences import PreferencesDialog
from flare.utils.gui import application


def main() -> None:
    with application():
        dialog = PreferencesDialog()
        dialog.show()


if __name__ == '__main__':
    tests.init()
    main()
