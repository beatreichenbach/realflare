import logging

from qtpy import QtWidgets

from examples import init
from flare.engine import create_context_surface, get_gpu_info, get_vram_text


def print_vram_info() -> None:
    QtWidgets.QApplication()
    context, surface = create_context_surface()
    context.makeCurrent(surface)

    logging.info(get_vram_text())


def print_gpu_info() -> None:
    QtWidgets.QApplication()
    context, surface = create_context_surface()
    context.makeCurrent(surface)

    for label, value in get_gpu_info():
        logging.info(f'{label: <24} {value}')


def main() -> None:
    print_vram_info()
    print_gpu_info()


if __name__ == '__main__':
    init()
    main()
