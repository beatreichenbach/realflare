import logging
from functools import lru_cache

import numpy as np
from OpenGL import GL
from qtpy import QtGui

from flare import api
from ..base import Array
from flare.engine.tasks.common.lens import get_lens, get_surfaces
from flare.utils import profiling

from ..opengl import OpenGLTask
from .common import LAMBDA_MAX, LAMBDA_MIN, DiscMesh, get_paths
from .constants import SSBO, UBO

logger = logging.getLogger(__name__)


intersection_dtype = np.dtype(
    [
        ('pos', np.float32, 3),
        ('incident', np.float32),
        ('normal', np.float32, 3),
        ('hit', np.int32),
    ]
)


ray_dtype = np.dtype(
    # rrel is the relative distance from the optical axis
    # pos_apt is the xy position at which the ray moved through the aperture
    [
        ('pos', np.float32, 3),
        ('rrel', np.float32),
        ('dir', np.float32, 3),
        ('reflectance', np.float32),
        ('pos_apt', np.float32, 2),
        ('_pad', np.int32, 2),
    ]
)

ghost_dtype = np.dtype(
    [
        ('path', np.int32, 2),
        ('offset', np.uint32),
        ('count', np.uint32),
    ]
)

ghost_data_dtype = np.dtype(
    [
        ('path', np.int32, 2),
        ('divisions', np.uint32),
        ('radius', np.float32),
        ('center', np.float32),
        ('culled', np.bool),
    ]
)

params_dtype = np.dtype(
    [
        ('surface_count', np.uint32),
        ('intersection_count', np.uint32),
        ('use_aspheric', np.uint32),
        ('_pad', np.uint32),
    ]
)


class RaytraceTask(OpenGLTask):
    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        super().__init__(context)

        sources = ('constants.glsl', 'raytracing.comp')
        comp_source = self.load_sources(*sources)
        comp_shader = self.load_shader(comp_source, GL.GL_COMPUTE_SHADER)

        self._program = self.create_program(shaders=(comp_shader,))
        self._ubo = self.create_buffer()
        self._surfaces_buffer = self.create_buffer()
        self._iors_buffer = self.create_buffer()
        self._wavelengths_buffer = self.create_buffer()
        self._ghosts_buffer = self.create_buffer()
        self._rays_buffer = self.create_buffer()
        self._intersections_buffer = self.create_buffer()

        self.bind_ubo(self._ubo, UBO.RAYTRACING)
        self.bind_ssbo(self._surfaces_buffer, SSBO.SURFACES)
        self.bind_ssbo(self._iors_buffer, SSBO.IORS)
        self.bind_ssbo(self._wavelengths_buffer, SSBO.WAVELENGTHS)
        self.bind_ssbo(self._ghosts_buffer, SSBO.GHOSTS)
        self.bind_ssbo(self._rays_buffer, SSBO.RAYS)
        self.bind_ssbo(self._intersections_buffer, SSBO.INTERSECTIONS)

        self.bind_ubo_block(self._program, 'Params', UBO.RAYTRACING)
        self.bind_ssbo_block(self._program, 'Surfaces', SSBO.SURFACES)
        self.bind_ssbo_block(self._program, 'Iors', SSBO.IORS)
        self.bind_ssbo_block(self._program, 'Wavelengths', SSBO.WAVELENGTHS)
        self.bind_ssbo_block(self._program, 'Ghosts', SSBO.GHOSTS)
        self.bind_ssbo_block(self._program, 'Rays', SSBO.RAYS)
        self.bind_ssbo_block(self._program, 'Intersections', SSBO.INTERSECTIONS)

    def cleanup(self) -> None:
        self.delete(
            programs=(self._program,),
            buffers=(
                self._ubo,
                self._surfaces_buffer,
                self._iors_buffer,
                self._wavelengths_buffer,
                self._ghosts_buffer,
                self._rays_buffer,
                self._intersections_buffer,
            ),
        )

    @staticmethod
    def compute(
        program: int, ray_counts: tuple[int, ...], wavelength_count: int
    ) -> None:
        """Run the compute shader, dispatching each ghost separately."""

        local_size_x = 512

        GL.glUseProgram(program)
        loc = GL.glGetUniformLocation(program, 'ghost_id')
        for ghost_id, ray_count in enumerate(ray_counts):
            GL.glUniform1ui(loc, ghost_id)
            groups_x = (ray_count + local_size_x - 1) // local_size_x
            groups_y = wavelength_count
            GL.glDispatchCompute(groups_x, groups_y, 1)
        GL.glMemoryBarrier(GL.GL_SHADER_STORAGE_BARRIER_BIT)
        GL.glFinish()

    def raytrace(
        self,
        surfaces: Array,
        iors: Array,
        ghosts: Array,
        rays: Array,
        use_aspheric: bool,
    ) -> None:
        """Trace the rays through the lens system."""

        surface_count = len(surfaces.array)
        wavelength_count = iors.array.shape[1]
        wavelengths = get_wavelengths(wavelength_count)
        intersection_count = surface_count * 3 - 1

        # Params
        params = np.zeros((), dtype=params_dtype)
        params['surface_count'] = surface_count
        params['intersection_count'] = intersection_count
        params['use_aspheric'] = use_aspheric
        self.update_ubo(self._ubo, params)

        # Buffers
        cached_update_ssbo(self._surfaces_buffer, surfaces)
        cached_update_ssbo(self._iors_buffer, iors)
        cached_update_ssbo(self._wavelengths_buffer, wavelengths)
        cached_update_ssbo(self._ghosts_buffer, ghosts)
        self.update_ssbo(self._rays_buffer, rays.array, usage=GL.GL_DYNAMIC_COPY)

        rays.args = (*rays.args, use_aspheric)

        # Render
        ray_counts = tuple(ghost['count'] for ghost in ghosts.array)
        self.compute(self._program, ray_counts, wavelength_count)

    @profiling.timer
    # @lru_cache(1)
    def run_preprocess(
        self,
        lens_config: api.Flare.Lens,
        sensor_size: tuple[float, float],
        position: tuple[float, float],
        resolution: tuple[float, float],
        wavelength_count: int,
        divisions: int,
        use_aspheric: bool,
    ) -> Array:

        lens = get_lens(lens_config)
        surfaces = get_surfaces(lens=lens, coatings=lens_config.coatings)
        iors = get_iors(
            lens=lens,
            glass=lens_config.glass,
            abbe_offset=lens_config.abbe_offset,
            wavelength_count=wavelength_count,
        )
        direction = get_direction(
            position=position,
            sensor_size=sensor_size,
            resolution=resolution,
            focal_length=lens.focal_length,
        )
        ghost_datas = get_ghost_datas(lens, divisions)
        ghosts = get_ghosts(ghost_datas=ghost_datas)
        max_divisions = max(int(ghost_datas.array['divisions'].max()), 1)
        rays = get_rays(
            ghost_datas=ghost_datas,
            wavelength_count=wavelength_count,
            direction=direction,
            max_divisions=max_divisions,
        )

        self.raytrace(
            surfaces=surfaces,
            iors=iors,
            ghosts=ghosts,
            rays=rays,
            use_aspheric=use_aspheric,
        )

        array = self.read_buffer(self._rays_buffer, rays.array)
        args = (*rays.args, surfaces, iors, use_aspheric)
        traced_rays = Array(array=array, args=args)
        return traced_rays

    @profiling.timer
    # @lru_cache(1)
    def run_flare(
        self,
        lens_config: api.Flare.Lens,
        sensor_size: tuple[float, float],
        position: tuple[float, float],
        resolution: tuple[float, float],
        wavelength_count: int,
        ghost_datas: Array,
        use_aspheric: bool,
    ) -> Array:
        lens = get_lens(lens_config)
        surfaces = get_surfaces(lens=lens, coatings=lens_config.coatings)
        iors = get_iors(
            lens=lens,
            glass=lens_config.glass,
            abbe_offset=lens_config.abbe_offset,
            wavelength_count=wavelength_count,
        )
        direction = get_direction(
            position=position,
            sensor_size=sensor_size,
            resolution=resolution,
            focal_length=lens.focal_length,
        )
        ghosts = get_ghosts(ghost_datas=ghost_datas)
        max_divisions = max(int(ghost_datas.array['divisions'].max()), 1)
        rays = get_rays(
            ghost_datas=ghost_datas,
            wavelength_count=wavelength_count,
            direction=direction,
            max_divisions=max_divisions,
        )

        self.raytrace(
            surfaces=surfaces,
            iors=iors,
            ghosts=ghosts,
            rays=rays,
            use_aspheric=use_aspheric,
        )
        # Update the args after raytracing
        rays.args = (*rays.args, surfaces, iors)

        array = self.read_buffer(self._rays_buffer, rays.array)
        args = (*rays.args, surfaces, iors, use_aspheric)
        traced_rays = Array(array=array, args=args)
        return traced_rays

    @profiling.timer
    # @lru_cache(1)
    def run_diagram(
        self,
        lens_config: api.Flare.Lens,
        sensor_size: tuple[float, float],
        position: tuple[float, float],
        resolution: tuple[float, float],
        wavelength_count: int,
        ghost_datas: Array,
        use_aspheric: bool,
    ) -> Array:

        lens = get_lens(lens_config)
        surfaces = get_surfaces(lens=lens, coatings=lens_config.coatings)
        iors = get_iors(
            lens=lens,
            glass=lens_config.glass,
            abbe_offset=lens_config.abbe_offset,
            wavelength_count=wavelength_count,
        )
        direction = get_direction(
            position=position,
            sensor_size=sensor_size,
            resolution=resolution,
            focal_length=lens.focal_length,
        )
        ghosts = get_ghosts(ghost_datas=ghost_datas)
        max_divisions = max(int(ghost_datas.array['divisions'].max()), 1)
        rays = get_rays(
            ghost_datas=ghost_datas,
            wavelength_count=wavelength_count,
            direction=direction,
            max_divisions=max_divisions,
        )
        surface_count = len(surfaces.array)
        intersections_count = surface_count * 3 - 1
        intersections = get_intersections(
            ray_count=rays.array.shape[0],
            intersection_count=intersections_count,
        )

        # Intersections
        array = intersections.array
        self.update_ssbo(self._intersections_buffer, array, GL.GL_DYNAMIC_COPY)

        self.raytrace(
            surfaces=surfaces,
            iors=iors,
            ghosts=ghosts,
            rays=rays,
            use_aspheric=use_aspheric,
        )

        # Update the args after raytracing
        intersections.args = (*intersections.args, surfaces, iors)

        intersections.array = self.read_buffer(
            self._intersections_buffer, intersections.array
        )

        return intersections


@lru_cache(1)
def cached_update_ssbo(
    buffer: int, array: Array, usage: int = GL.GL_DYNAMIC_DRAW
) -> None:
    """Update the buffer with array."""

    OpenGLTask.update_ssbo(buffer, array.array, usage)


@lru_cache(64)
def get_positions(radius: float, divisions: int) -> np.ndarray:
    """Return the vertex positions for the mesh."""

    return DiscMesh.get_positions(radius=radius, resolution=divisions)


def get_ghost_datas(lens: api.Lens, divisions: int) -> Array:
    """Return the GhostDatas for a lens."""

    paths = get_paths(lens.surfaces)
    entrance_surface = lens.surfaces[0]
    array = np.zeros((len(paths),), dtype=ghost_data_dtype)
    array['path'] = np.array(paths)
    array['radius'] = entrance_surface.radius
    array['divisions'] = divisions
    ghost_datas = Array(array=array, args=(lens, divisions))
    return ghost_datas


@lru_cache(1)
def get_direction(
    position: tuple[float, float],
    sensor_size: tuple[float, float],
    resolution: tuple[float, float],
    focal_length: float,
) -> Array:
    """Return an Array with the initial direction of the rays."""

    sensor_width = sensor_size[0]
    sensor_height = sensor_width / resolution[0] * resolution[1]

    x = position[0] * sensor_width / 2
    y = position[1] * sensor_height / 2
    z = -focal_length

    direction = np.array([x, y, z], dtype=np.float32)

    # Normalize the direction
    norm = np.linalg.norm(direction)
    if norm > 1e-6:
        direction /= norm
    else:
        direction[:] = 0

    direction = Array(
        array=direction, args=(position, sensor_size, resolution, focal_length)
    )
    return direction


@lru_cache(1)
def get_wavelengths(wavelength_count: int) -> Array:
    """Return an Array of evenly distributed wavelengths in nm."""

    wavelengths = []
    for i in range(wavelength_count):
        step = (i + 0.5) / wavelength_count
        wavelength = LAMBDA_MIN + step * (LAMBDA_MAX - LAMBDA_MIN)
        wavelengths.append(wavelength)

    array = np.array(wavelengths, dtype=np.float32)
    wavelengths = Array(array=array, args=wavelength_count)
    return wavelengths


@lru_cache(1)
def get_iors(
    lens: api.Lens,
    glass: str,
    abbe_offset: float,
    wavelength_count: int,
) -> Array:
    """Return an Array with IORs for every surface and wavelength."""

    db = api.Database()
    wavelengths = get_wavelengths(wavelength_count)
    wavelengths_array = wavelengths.array

    calculated_iors = []
    for surface in lens.surfaces:
        if surface.ior > 1:
            ior = surface.ior
            abbe = surface.abbe + abbe_offset
            material = db.get_material(glass, ior, abbe)
            if material:
                iors = tuple(material.get_ior(w) for w in wavelengths_array)
                calculated_iors.append(iors)
                continue

        iors = tuple(1 for _ in wavelengths_array)
        calculated_iors.append(iors)

    array = np.array(calculated_iors, np.float32)

    iors = Array(array=array, args=(lens, glass, abbe_offset, wavelength_count))
    return iors


@lru_cache(1)
def get_rays(
    ghost_datas: Array, wavelength_count: int, direction: Array, max_divisions: int
) -> Array:
    """Return an array of rays."""

    # NOTE: Flattening the array is slower. This was the code before optimization:
    # arrays = []
    # for i, ghost_data in enumerate(ghost_datas):
    #     ...
    #     shape = (wavelength_count, ray_count)
    #     array = np.zeros(shape, dtype=ray_dtype)
    #     arrays.append(array)
    # flattened_array = np.concatenate(tuple(array.ravel() for array in arrays))

    ghost_array = ghost_datas.array[~ghost_datas.array['culled']]
    ray_counts = 1 + (3 * ghost_array['divisions'] * (ghost_array['divisions'] + 1))
    total_ray_count = wavelength_count * np.sum(ray_counts).item()

    flattened_array = np.zeros(total_ray_count, dtype=ray_dtype)
    flattened_array['reflectance'] = 1.0
    flattened_array['dir'] = direction.array

    global_positions = get_positions(radius=1.0, divisions=max_divisions)
    transforms = get_transforms(ghost_datas, direction, max_divisions)
    scales, rotation, translations = transforms

    start_idx = 0
    for i, ray_count in enumerate(ray_counts):
        ghost_ray_count = wavelength_count * ray_count
        end_idx = start_idx + ghost_ray_count
        view = flattened_array[start_idx:end_idx].reshape(wavelength_count, -1)
        positions = np.copy(global_positions[:ray_count])
        positions[:, :2] *= scales[i]
        positions[:, :2] @= rotation
        positions[:, :2] += translations[i]
        view['pos'] = positions
        start_idx = end_idx

    rays = Array(array=flattened_array, args=(ghost_datas, wavelength_count, direction))
    return rays


def get_transforms(
    ghost_datas: Array, direction: Array, max_divisions: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return an array of transforms from GhostDatas."""

    flat_direction = direction.array[:2]
    norm = np.linalg.norm(flat_direction)
    if norm > 1.0e-6:
        normalized = flat_direction / norm
        c, s = normalized
        rotation = np.array(((c, s), (-s, c)))
    else:
        normalized = np.zeros(2, np.float32)
        rotation = np.eye(2)

    ghost_array = ghost_datas.array[~ghost_datas.array['culled']]
    centers = ghost_array['center']
    divisions = ghost_array['divisions']
    radiuses = ghost_array['radius']
    scales = (max_divisions / divisions) * radiuses
    translations = normalized * centers[:, np.newaxis]

    transforms = (scales, rotation, translations)
    # transforms = Array(array=array, args=(ghost_datas, direction))
    return transforms


@lru_cache(1)
def get_intersections(ray_count: int, intersection_count: int) -> Array:
    """Return an Array with Intersections per Ray."""

    shape = (ray_count, intersection_count)
    array = np.zeros(shape, dtype=intersection_dtype)

    intersections = Array(array=array, args=(ray_count, intersection_count))
    return intersections


@lru_cache(1)
def get_ghosts(ghost_datas: Array) -> Array:
    """Return an Array from GhostDatas."""

    ghost_array = ghost_datas.array[~ghost_datas.array['culled']]
    ray_counts = 1 + (3 * ghost_array['divisions'] * (ghost_array['divisions'] + 1))

    array = np.zeros(len(ghost_array), ghost_dtype)
    array['path'] = ghost_array['path']
    array['count'] = ray_counts

    # NOTE: The following can be optimized by using cumulative sum.
    # ray_offset = 0
    # for i, ray_count in enumerate(ray_counts):
    # project.flare.debug.ghost = 0
    #     array[i]['offset'] = ray_offset
    #     ray_offset += ray_count
    array['offset'] = np.cumsum(ray_counts) - ray_counts

    ghosts = Array(array=array, args=ghost_datas)
    return ghosts
