from qtpy import QtWidgets

from examples import init
from flare.ui import application
from flare.ui.widgets import DockWidgetState, StateDockWindow, TabState, WindowState


class Widget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(QtWidgets.QPushButton('asdf'))
        layout.addWidget(QtWidgets.QPushButton('asdf'))
        layout.addWidget(QtWidgets.QPushButton('asdf'))
        self.setLayout(layout)


def main() -> None:
    with application():
        window = StateDockWindow()
        name = 'Widget'
        window.register_widget(Widget, name)
        window.set_window_state(
            WindowState(
                states=(
                    DockWidgetState(
                        current_index=0,
                        widgets=(
                            TabState('Tab 1', name),
                            TabState('Tab 2', name),
                        ),
                        detachable=True,
                        auto_delete=False,
                        is_center_widget=True,
                    ),
                ),
            )
        )
        window.show()


if __name__ == '__main__':
    init()
    main()
