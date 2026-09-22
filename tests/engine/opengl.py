import logging

from qtpy import QtWidgets

from flare.engine.opengl import create_context_surface, utils


def test_get_vram_info() -> None:
    QtWidgets.QApplication()
    context, surface = create_context_surface()
    context.makeCurrent(surface)

    vram_info = utils._get_vram_info()
    logging.info(vram_info)


def test_get_gpu_info() -> None:
    QtWidgets.QApplication()
    context, surface = create_context_surface()
    context.makeCurrent(surface)

    gpu_info = utils.get_gpu_info()
    for label, value in gpu_info:
        logging.info(f'{label: <24} {value}')
