import numpy as np
from qtpy import QtWidgets

import tests
from flare import api
from flare.engine.engine import Engine


def test_aperture():


# def test_raytrace() -> None:
#     project = api.Project()
#     project.flare.raytracing.wavelength_count = 3
#     project.flare.raytracing.divisions = 16
#     project.flare.lens.vendor = 'Nikon'
#     project.flare.lens.lens = 'Nikon AF-S Nikkor 70-200mm f2.8 E FL ED VR'
#
#     engine = Engine()
#     engine.context.makeCurrent(engine.surface)
#     graph = RenderGraph(engine.context)
#
#     position = project.flare.light.position.toTuple()
#     sensor_size = project.flare.camera.sensor_size.toTuple()
#     resolution = project.flare.render.resolution.toTuple()
#
#     pos_x = np.linalg.norm(np.array(position))
#     pre_position = (pos_x, 0)
#     divisions = 16
#     wavelength_count = 1
#
#     rays = graph.raytrace_task.run_preprocess(
#         lens_config=project.flare.lens,
#         sensor_size=sensor_size,
#         position=pre_position,
#         resolution=resolution,
#         wavelength_count=wavelength_count,
#         divisions=divisions,
#     )
#
#     debug = project.flare.debug
#     isolate_ghost = debug.ghost if debug.ghost_enabled else None
#     ghost_datas = graph.preprocess_task.run(
#         lens_config=project.flare.lens,
#         divisions=divisions,
#         cull_percentage=0.5,
#         rays=rays,
#         fstop=1.0,
#         isolate_ghost=isolate_ghost,
#     )
#     position = project.flare.light.position.toTuple()
#
#     rays = graph.raytrace_task.run_flare(
#         lens_config=project.flare.lens,
#         sensor_size=sensor_size,
#         position=position,
#         resolution=resolution,
#         wavelength_count=project.flare.raytracing.wavelength_count,
#         ghost_datas=ghost_datas,
#     )


if __name__ == '__main__':
    tests.init()
    QtWidgets.QApplication()
    test_raytrace()
