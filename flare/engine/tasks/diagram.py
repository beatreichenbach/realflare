import logging
from functools import lru_cache

import numpy as np
from OpenGL import GL
from qtpy import QtCore, QtGui

from flare import api
from ..base import Array
from flare.engine.tasks.common.lens import get_surfaces

from ..opengl import OpenGLTask
from .constants import SSBO, UBO
from .raytrace import get_iors

logger = logging.getLogger(__name__)


lens_params_dtype = np.dtype(
    [
        ('resolution', np.float32, 2),
        ('scale', np.float32),
        ('surface_count', np.uint32),
    ]
)

rays_params_dtype = np.dtype(
    [
        ('height', np.float32),
        ('scale', np.float32),
        ('ray_id_count', np.uint32),
        ('intersection_count', np.uint32),
    ]
)


class DiagramTask(OpenGLTask):
    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        super().__init__(context)

        vertex_source = self.load_source('screen.vert')
        vertex_shader = self.load_shader(vertex_source, GL.GL_VERTEX_SHADER)
        fragment_source = self.load_source('diagram_lens.frag')
        fragment_shader = self.load_shader(fragment_source, GL.GL_FRAGMENT_SHADER)

        self._lens_program = self.create_program((vertex_shader, fragment_shader))
        self._lens_fbo_texture = self.create_texture()
        self._lens_fbo = self.create_fbo(self._lens_fbo_texture)
        self._lens_vao = self.create_vao()
        self._lens_ubo = self.create_buffer()

        self.bind_ubo(self._lens_ubo, UBO.DIAGRAM_LENS)

        self.bind_ubo_block(self._lens_program, 'Params', UBO.DIAGRAM_LENS)
        self.bind_ssbo_block(self._lens_program, 'Surfaces', SSBO.SURFACES)
        self.bind_ssbo_block(self._lens_program, 'Iors', SSBO.IORS)

        # Rays Program
        vertex_source = self.load_source('screen.vert')
        vertex_shader = self.load_shader(vertex_source, GL.GL_VERTEX_SHADER)
        fragment_source = self.load_source('diagram_rays.frag')
        fragment_shader = self.load_shader(fragment_source, GL.GL_FRAGMENT_SHADER)

        self._rays_program = self.create_program((vertex_shader, fragment_shader))
        self._rays_fbo_texture = self.create_texture()
        self._rays_fbo = self.create_fbo(self._rays_fbo_texture)
        self._rays_vao = self.create_vao()
        self._rays_ubo = self.create_buffer()
        self._ray_ids_buffer = self.create_buffer()

        self.bind_ubo(self._lens_ubo, UBO.DIAGRAM_RAYS)
        self.bind_ssbo(self._ray_ids_buffer, SSBO.DIAGRAM_RAY_IDS)

        self.bind_ubo_block(self._rays_program, 'Params', UBO.DIAGRAM_RAYS)
        self.bind_ssbo_block(self._rays_program, 'RayIDs', SSBO.DIAGRAM_RAY_IDS)
        self.bind_ssbo_block(self._rays_program, 'Intersections', SSBO.INTERSECTIONS)

    def cleanup(self) -> None:
        self.delete(
            programs=(self._lens_program,),  # self._rays_program),
            textures=(self._lens_fbo_texture, self._rays_fbo_texture),
            render_buffers=(self._lens_fbo, self._rays_fbo),
            vertex_arrays=(self._lens_vao, self._rays_vao),
            buffers=(
                self._lens_ubo,
                self._rays_ubo,
                self._ray_ids_buffer,
            ),
        )

    @lru_cache(1)  # noqa: B019
    def update_fbo_resolution(self, resolution: QtCore.QSize) -> None:
        """Update the fbo with a new resolution."""

        self._lens_fbo_texture = self.create_texture(
            clamp_to_border=True, resolution=resolution.toTuple()
        )
        self.update_fbo(self._lens_fbo, self._lens_fbo_texture)

    @lru_cache(1)  # noqa: B019
    def render_lens(
        self,
        surface_count: int,
        scale: float,
        resolution: QtCore.QSize,
    ) -> None:
        """Render the lens diagram to the first frame buffer."""

        # Params
        params = np.zeros((), dtype=lens_params_dtype)
        params['resolution'] = resolution.toTuple()
        params['scale'] = scale
        params['surface_count'] = surface_count
        self.update_ubo(self._lens_ubo, params)

        # Render
        self.update_fbo_resolution(resolution)
        self.bind_vao(self._lens_vao)
        self.render(self._lens_program, self._lens_fbo, resolution)

    def render_rays(
        self,
        intersections: Array,
        scale: float,
        resolution: QtCore.QSize,
    ) -> None:
        """Render the rays to the second frame buffer."""

        ray_count, intersection_count = intersections.array.shape
        ray_ids = get_ray_ids(ray_count)
        ray_id_count = len(ray_ids.array)

        # Buffers
        cached_update_ssbo(self._ray_ids_buffer, ray_ids)
        self.update_texture(self._lens_fbo_texture)

        # Params
        params = np.zeros((), dtype=rays_params_dtype)
        params['height'] = resolution.height()
        params['scale'] = scale
        params['ray_id_count'] = ray_id_count
        params['intersection_count'] = intersection_count
        self.update_ubo(self._rays_ubo, params)

        # Render
        self.update_fbo_texture(self._rays_fbo_texture, resolution, unit=2)
        self.bind_vao(self._rays_vao)
        self.render(self._rays_program, self._rays_fbo, resolution)

    @lru_cache(1)
    def run(
        self,
        vendor: str,
        lens: str,
        intersections: Array,
        resolution: QtCore.QSize,
        lens_config: api.Flare.Lens,
    ) -> Array:
        """Render the lens diagram and the rays."""

        db = api.Database()
        lens_model = db.get_lens(vendor, lens)
        if lens_model:
            surfaces = lens_model.surfaces
            surface_count = len(lens_model.surfaces)

            # TODO: Temporary
            surfaces_array = get_surfaces(lens_model, coatings=())
            for surface in surfaces_array.array:
                logger.debug(surface['radius'])

            iors = get_iors(
                lens=lens_model,
                glass=lens_config.glass,
                abbe_offset=lens_config.abbe_offset,
                wavelength_count=1,
            )
            cached_update_ssbo(self._surfaces_buffer, surfaces_array)
            cached_update_ssbo(self._iors_buffer, iors)
        else:
            surfaces = ()
            surface_count = 0
        scale = get_scale(resolution, tuple(surfaces))

        self.render_lens(surface_count, scale, resolution)
        # self.render_rays(intersections, scale, resolution)

        array = self.read_texture(self._lens_fbo_texture, resolution, unit=2)
        image = Array(array=array, args=(vendor, lens, intersections, resolution))
        return image


@lru_cache(1)
def cached_update_ssbo(
    buffer: int, array: Array, usage: int = GL.GL_DYNAMIC_DRAW
) -> None:
    """Update the buffer with array."""

    OpenGLTask.update_ssbo(buffer, array.array, usage)


@lru_cache(1)
def get_scale(
    resolution: QtCore.QSize, surfaces: tuple[api.Lens.Surface, ...]
) -> float:
    """Return the scale to fit a Lens into a resolution."""

    padding = 1
    distance = padding * 2
    for surface in surfaces:
        distance += surface.spacing
    if distance == 0:
        scale = 1
    else:
        scale = resolution.width() / distance
    return scale


@lru_cache(1)
def get_ray_ids(ray_count: int) -> Array:
    """Return an Array with the center indices from a DiscMesh."""

    # Assume divisions without calculating them
    max_divisions = ray_count
    indices = [0]
    for circle in range(max_divisions):
        first = 3 * circle * (circle + 1)
        middle = (circle + 1) * 3
        if 1 + first >= ray_count:
            break
        indices.append(1 + first)
        indices.append(1 + first + middle)

    array = np.array(indices, np.uint32)
    ray_ids = Array(array=array, args=ray_count)
    return ray_ids
