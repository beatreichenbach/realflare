from qtpy import QtWidgets

import tests
from flare import api
from flare.engine.engine import Engine


def test_starburst_aperture() -> None:
    project = api.Project()
    engine = Engine()
    engine.render(project, api.Layer.STARBURST_APERTURE)
    engine.graph.aperture_task.cleanup()


def test_starburst() -> None:
    project = api.Project()
    engine = Engine()
    engine.render(project, api.Layer.STARBURST)


def test_ghost_aperture() -> None:
    project = api.Project()
    engine = Engine()
    engine.render(project, api.Layer.GHOST_APERTURE)


def test_ghost() -> None:
    project = api.Project()
    engine = Engine()
    engine.render(project, api.Layer.GHOST)


def test_flare() -> None:
    project = api.Project()
    project.flare.raytracing.wavelength_count = 5
    project.flare.debug.ghost = 0
    project.flare.debug.ghost_enabled = True
    project.flare.lens.vendor = 'Hasselblad'
    project.flare.lens.lens = 'Hasselblad XCD 2.8 65'

    engine = Engine()
    engine.render(project, api.Layer.FLARE)


def test_comp() -> None:
    project = api.Project()

    engine = Engine()
    engine.render(project, api.Layer.COMP)


def test_diagram() -> None:
    project = api.Project()
    project.flare.lens.vendor = 'Canon'
    project.flare.lens.lens = 'Canon EF20mm f2.8 USM'
    project.diagram.raytracing.ghost = 0
    project.diagram.raytracing.divisions = 2
    engine = Engine()
    engine.render(project, api.Layer.DIAGRAM)


if __name__ == '__main__':
    tests.init()
    QtWidgets.QApplication()
    # test_starburst_aperture()
    test_starburst()
    # test_ghost_aperture()
    # test_ghost()
    # test_flare()
    # test_comp()
    # test_diagram()
