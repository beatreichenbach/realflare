from qtpy import QtWidgets

import tests
from flare.utils.gui import application
from flare.widgets import DockWidgetState, StateDockWindow, TabState, WindowState


class Widget(QtWidgets.QWidget): ...


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
    tests.init()
    main()
