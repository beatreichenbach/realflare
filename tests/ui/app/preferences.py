import tests
from flare.ui import application
from flare.ui.app.widgets.preferences import PreferencesDialog


def main() -> None:
    with application():
        dialog = PreferencesDialog()
        dialog.show()


if __name__ == '__main__':
    tests.init()
    main()
