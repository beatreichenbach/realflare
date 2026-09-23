from qtpy import QtCore

from .model import Layer, Project


def default_project() -> Project:
    """Return the Project used for a new session and first launch."""

    project = Project()

    project.flare.light.intensity = 100
    project.flare.light.position = QtCore.QPointF(0.5, 0.25)

    project.flare.lens.vendor = 'Nikon'
    project.flare.lens.lens = 'Nikon AF Zoom-Nikkor 28-85mm f3.5-4.5'

    project.flare.raytracing.wavelength_count = 5
    project.flare.raytracing.wavelength_sub_count = 1
    project.flare.raytracing.min_divisions = 16
    project.flare.raytracing.max_divisions = 64
    project.flare.raytracing.cull_percentage = 0.5
    project.flare.raytracing.min_sliver = 0.1

    project.flare.camera.fstop = 2.8

    project.ghost.aperture.shape.blades = 64
    project.ghost.diffraction.distance = 2

    project.output.layer = Layer.FLARE

    return project
