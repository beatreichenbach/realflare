from qtpy import QtWidgets

import tests
from flare.utils.gui import application
from flare.widgets import DockWindow


class Widget(QtWidgets.QWidget): ...


def main() -> None:
    with application():
        window = DockWindow()
        name = 'Widget'
        window.register_widget(Widget, name)
        window.set_state(
            {
                'states': [
                    {
                        'kind': 'dock',
                        'current_index': 0,
                        'widgets': [[name, 'Widget']],
                        'detachable': True,
                        'auto_delete': False,
                        'is_center_widget': True,
                    },
                ],
            }
        )
        window.show()


if __name__ == '__main__':
    tests.init()
    main()
