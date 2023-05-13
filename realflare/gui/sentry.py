import sys

from PySide2 import QtWidgets

from qt_extensions import theme
from qt_extensions.messagebox import MessageBox
from realflare.utils.settings import Settings


def request_permission():
    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(theme.monokai)

    settings = Settings()
    settings.load()

    result = MessageBox.question(
        None,
        'Enable Automated Crash Reporting',
        'May Realflare upload crash reports automatically? \n\n'
        'Crash reports don\'t include any personal information. '
        'Enabling automated crash reporting with Sentry.io means issues don\'t '
        'have to be reported manually and bugs can be fixed sooner. \n\n'
        'Crash reporting can be disabled at any time under Settings.',
    )

    settings.config.sentry = result == QtWidgets.QMessageBox.StandardButton.Yes
    settings.save()
    app.quit()


if __name__ == '__main__':
    request_permission()
