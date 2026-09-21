import tests
from flare.ui import application
from flare.ui.widgets.parameter import MenuParameter


def main() -> None:
    with application():
        param = MenuParameter()
        data = {'Entry1': 1, 'Entry2': 2, 'Entry3': {'A': 1, 'B': 2}}
        param.set_data(data)
        param.show()
        param.set_value(1)


if __name__ == '__main__':
    tests.init()
    main()
