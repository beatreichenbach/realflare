from __future__ import annotations

import webbrowser
from functools import partial

from qtpy import QtWidgets

from flare.services.update import Release


class UpdateDialog(QtWidgets.QDialog):
    def __init__(
        self,
        release: Release,
        version: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.release = release
        self.update_requested = False

        self._init_ui(version)

    def _init_ui(self, version: str) -> None:
        self.setWindowTitle('Update Available')
        self.resize(640, 480)

        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel(
            f'Version {self.release.version} is available. You are running {version}.'
        )
        layout.addWidget(label)

        notes = QtWidgets.QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setMarkdown(self.release.notes)
        layout.addWidget(notes, 1)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()

        later = QtWidgets.QPushButton('Later')
        later.clicked.connect(self.reject)
        buttons.addWidget(later)

        page = QtWidgets.QPushButton('Release Notes')
        page.clicked.connect(partial(webbrowser.open, self.release.page_url))
        buttons.addWidget(page)

        update = QtWidgets.QPushButton('Update Now')
        update.setDefault(True)
        update.clicked.connect(self._update)
        buttons.addWidget(update)

        layout.addLayout(buttons)

    def _update(self) -> None:
        self.update_requested = True
        self.accept()
