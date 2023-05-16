import sys

from PySide2 import QtWidgets

from qt_extensions import theme
from qt_extensions.messagebox import MessageBox
from realflare.storage import Storage


def request_permission():
    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(theme.monokai)

    storage = Storage()

    result = MessageBox.question(
        None,
        'Enable Automated Crash Reporting',
        'May Realflare upload crash reports automatically? \n\n'
        'Crash reports don\'t include any personal information. '
        'Enabling automated crash reporting with Sentry.io means issues don\'t '
        'have to be reported manually and bugs can be fixed sooner. \n\n'
        'Crash reporting can be disabled at any time under Settings.',
    )

    storage.settings.sentry = result == QtWidgets.QMessageBox.StandardButton.Yes
    storage.save_settings()
    app.quit()


if __name__ == '__main__':
    request_permission()
