from qtpy import QtWidgets

import tests
from flare import api
from flare.api.project.default import default_project
from flare.engine.engine import Engine


def render(layer: api.Layer, project: api.Project | None = None) -> None:
    """Render a layer of a project and release the engine resources."""

    if project is None:
        project = default_project()

    engine = Engine()
    try:
        engine.render(project, layer)
    finally:
        engine.release()


def starburst_aperture() -> None:
    render(api.Layer.STARBURST_APERTURE)


def starburst() -> None:
    render(api.Layer.STARBURST)


def ghost_aperture() -> None:
    render(api.Layer.GHOST_APERTURE)


def ghost() -> None:
    render(api.Layer.GHOST)


def flare() -> None:
    render(api.Layer.FLARE)


def comp() -> None:
    render(api.Layer.COMP)


def diagram() -> None:
    project = default_project()
    project.diagram.raytracing.ghost = 0
    project.diagram.raytracing.divisions = 2

    render(api.Layer.DIAGRAM, project)


if __name__ == '__main__':
    tests.init()
    QtWidgets.QApplication()

    starburst_aperture()
    starburst()
    ghost_aperture()
    ghost()
    flare()
    comp()
    # diagram()
