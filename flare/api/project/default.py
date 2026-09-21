from qtpy import QtCore

from .model import Layer, Project


def default_project() -> Project:
    """Return the Project used for a new session and first launch."""

    project = Project()

    project.flare.light.intensity = 100
    project.flare.light.position = QtCore.QPointF(0.66, 0.0)

    project.flare.lens.vendor = 'Fujifilm'
    project.flare.lens.lens = 'Fujifilm Fujinon XF27mm F2.8'

    project.flare.raytracing.wavelength_count = 5
    project.flare.raytracing.wavelength_sub_count = 8
    project.flare.raytracing.min_divisions = 16
    project.flare.raytracing.max_divisions = 128
    project.flare.raytracing.cull_percentage = 0.5
    project.flare.raytracing.min_sliver = 0.1

    project.flare.camera.fstop = 2.8

    project.ghost.aperture.shape.blades = 64
    project.ghost.diffraction.distance = 2

    project.output.layer = Layer.FLARE

    return project
