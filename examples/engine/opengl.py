import logging

from qtpy import QtWidgets

from examples import init
from flare.engine.opengl import create_context_surface, utils


def get_vram_info() -> None:
    QtWidgets.QApplication()
    context, surface = create_context_surface()
    context.makeCurrent(surface)

    vram_info = utils._get_vram_info()
    logging.info(vram_info)


def get_gpu_info() -> None:
    QtWidgets.QApplication()
    context, surface = create_context_surface()
    context.makeCurrent(surface)

    gpu_info = utils.get_gpu_info()
    for label, value in gpu_info:
        logging.info(f'{label: <24} {value}')


def main() -> None:
    get_vram_info()
    get_gpu_info()


if __name__ == '__main__':
    init()
    main()
