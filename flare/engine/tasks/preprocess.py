import logging
import warnings
from functools import lru_cache

import numpy as np
from OpenGL import GL
from OpenGL.constant import Constant
from qtpy import QtGui

from flare import api
from flare.api import Lens
from flare.engine.tasks.common.lens import get_lens

from ..base import Array
from ..opengl import OpenGLTask
from .common import DiscMesh, get_ghost_scale, get_paths, raytracing
from .constants import SSBO, UBO
from .raytrace import ray_dtype

logger = logging.getLogger(__name__)

LOW_THRESHOLD = 1e-9

params_dtype = np.dtype(
    [
        ('ray_count', np.uint32),
        ('tri_count', np.uint32),
        ('area_orig', np.float32),
        ('_pad', np.float32),
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


class PreprocessTask(OpenGLTask):
    """
    The Preprocess task is run per lens to determine facts about ghosts that help
    optimize the raytracing step. The output of the preprocessing step changes depending
    on a couple of factors:
    - Glass (IORs)
    - Abbe Adjustment (IORs)
    - Sensor Size (Area variance culled)

    Per lens, per ghost:
        1. Trace rays with initial divisions.
        2. Calculate the average intensity.
        3. Calculate the average distortion (variance of areas).
        4. Calculate the bounds of the valid rays and determine a center and radius for
           the initial disc mesh.
    """

    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        super().__init__(context)

        # Prim
        comp_source = self.load_sources('preprocess.comp')
        comp_shader = self.load_shader(comp_source, GL.GL_COMPUTE_SHADER)

        self._program = self.create_program(shaders=(comp_shader,))
        self._ubo = self.create_buffer()
        self._mesh_buffer = self.create_buffer()
        self._areas_buffer = self.create_buffer()
        self._intensities_buffer = self.create_buffer()

        self.bind_ubo(self._ubo, UBO.PREPROCESS)
        self.bind_ssbo(self._mesh_buffer, SSBO.PRE_MESH)
        self.bind_ssbo(self._areas_buffer, SSBO.PRE_AREAS)
        self.bind_ssbo(self._intensities_buffer, SSBO.PRE_INTENSITIES)

        self.bind_ubo_block(self._program, 'Params', UBO.PREPROCESS)
        self.bind_ssbo_block(self._program, 'Mesh', SSBO.PRE_MESH)
        self.bind_ssbo_block(self._program, 'Areas', SSBO.PRE_AREAS)
        self.bind_ssbo_block(self._program, 'Intensities', SSBO.PRE_INTENSITIES)
        self.bind_ssbo_block(self._program, 'Rays', SSBO.RAYS)

    @staticmethod
    def compute(program: int, ghost_count: int, tri_count: int) -> None:
        local_size_x = 512
        groups_x = (tri_count + local_size_x - 1) // local_size_x
        groups_y = ghost_count

        GL.glUseProgram(program)
        GL.glDispatchCompute(groups_x, groups_y, 1)
        GL.glMemoryBarrier(GL.GL_SHADER_STORAGE_BARRIER_BIT)
        GL.glFinish()

    @lru_cache(1)  # noqa: B019
    def run(
        self,
        rays: Array,
        lens_config: api.Flare.Lens,
        divisions: int,
        fstop: float,
        cull_percentage: float,
        min_divisions: int,
        max_divisions: int,
        isolate_ghost: int | None,
    ) -> Array:

        # Params
        ray_count = DiscMesh.get_vertex_count(divisions)
        tri_count = DiscMesh.get_triangle_count(divisions)

        lens = get_lens(lens_config)
        entrance_surface = lens.surfaces[0]
        area_orig = DiscMesh.get_triangle_area(entrance_surface.radius, divisions)

        params = np.zeros((), dtype=params_dtype)
        params['ray_count'] = ray_count
        params['tri_count'] = tri_count
        params['area_orig'] = area_orig
        self.update_ubo(self._ubo, params)

        # Ghost Data
        ghost_datas = get_ghost_datas(lens)

        # Arrays
        mesh = get_mesh(divisions)
        ghost_count = len(ghost_datas.array)
        areas = get_areas(ghost_count, tri_count)
        intensities = get_intensities(ghost_count, tri_count)

        # Buffers
        usage = GL.GL_DYNAMIC_COPY
        self.update_ssbo(self._areas_buffer, areas.array, usage)
        self.update_ssbo(self._intensities_buffer, intensities.array, usage)
        cached_update_ssbo(self._mesh_buffer, mesh)

        # Compute
        self.compute(self._program, ghost_count, tri_count)

        # Read data
        areas.array = self.read_buffer(self._areas_buffer, areas.array)
        intensities.array = self.read_buffer(
            self._intensities_buffer, intensities.array
        )

        # Intensities
        if isolate_ghost is not None:
            ghost_datas.array['culled'] = True
            ghost_datas.array['culled'][isolate_ghost] = False
        else:
            apply_intensity_mask(
                ghost_datas=ghost_datas,
                intensities=intensities,
                cull_percentage=cull_percentage,
            )

        # Subdivisions
        apply_divisions(
            ghost_datas=ghost_datas,
            areas=areas,
            min_divisions=min_divisions,
            max_divisions=max_divisions,
        )

        # Bounds
        apply_bounds(
            ghost_datas=ghost_datas,
            rays=rays,
            lens=lens,
            divisions=divisions,
            fstop=fstop,
        )

        valid_ghost_count = int((~ghost_datas.array['culled']).sum())
        logger.debug(f'Valid Ghost Count: {valid_ghost_count}')

        ghost_datas.args = (
            lens,
            rays,
            areas,
            divisions,
            min_divisions,
            max_divisions,
            fstop,
            isolate_ghost,
            intensities,
            cull_percentage,
        )

        return ghost_datas


@lru_cache(1)
def cached_update_ssbo(
    buffer: int,
    array: Array,
    usage: int | Constant = GL.GL_DYNAMIC_DRAW,
) -> None:
    OpenGLTask.update_ssbo(buffer, array.array, usage)


def apply_intensity_mask(
    ghost_datas: Array, intensities: Array, cull_percentage: float
) -> None:
    """
    Set the culled attribute per ghost depending on how bright the average ghost is.
    """

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        mean_intensities = np.nanmean(intensities.array, axis=1)

    # Cull nan values
    culled_mask = np.isnan(mean_intensities)

    # Cull ghosts by percentage
    valid_count = np.sum(~culled_mask)
    if valid_count > 0:
        threshold = (1 - cull_percentage) * valid_count

        # Fill nans with -inf so they rank last
        valid_intensities = np.where(~culled_mask, mean_intensities, -np.inf)

        # Calculate ranks for valid entries
        ranks = np.argsort(np.argsort(-valid_intensities))

        culled_mask |= ranks >= threshold

    # Cull completely black ghosts
    culled_mask |= mean_intensities <= LOW_THRESHOLD

    ghost_datas.array['culled'] = culled_mask


def apply_divisions(
    ghost_datas: Array, areas: Array, min_divisions: int, max_divisions: int
) -> None:
    """
    Set the divisions attribute per ghost depending on how deformed the primitives
    are.
    """

    # areas.array[:] = 0

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        mean_areas = np.nanmean(areas.array, axis=1)
        variances = np.nanvar(areas.array, axis=1)

    mask = (mean_areas > 0.0) & (~np.isnan(mean_areas)) & (~ghost_datas.array['culled'])
    mask_count = int((~mask).sum())
    logger.debug(f'Mask Count: {mask_count}')
    # Calculate CV^2: Variance / (Mean^2)
    relative_variances = variances[mask] / (mean_areas[mask] ** 2)

    if not mask.sum():
        return

    # Log-transform the variance to dampen extreme caustics
    log_variances = np.log1p(relative_variances)

    min_variance = np.min(log_variances)
    max_variance = np.max(log_variances)

    if max_variance > min_variance:
        variance_range = max_variance - min_variance
        normalized_variance = (log_variances - min_variance) / variance_range
    else:
        normalized_variance = np.zeros_like(log_variances)

    division_range = max_divisions - min_divisions
    divisions = min_divisions + division_range * normalized_variance
    divisions = np.round(divisions).astype(int)

    ghost_datas.array['divisions'][mask] = divisions


def apply_bounds(
    ghost_datas: Array,
    rays: Array,
    lens: Lens,
    divisions: int,
    fstop: float,
) -> None:
    """
    Set the center and radius attributes per ghost to center the disc mesh around
    the visible area.
    """

    entrance_surface: Lens.Surface = lens.surfaces[0]
    radius = entrance_surface.radius
    delta = radius / divisions
    positions = DiscMesh.get_positions(radius=radius, resolution=divisions)
    ghost_scale = get_ghost_scale(fstop)
    ghost_count = len(ghost_datas.array)
    ray_count = DiscMesh.get_vertex_count(divisions)

    for i in range(ghost_count):
        ray_offset = ray_count * i
        ghost_rays = rays.array[ray_offset : ray_offset + ray_count]
        pos_apt = ghost_rays['pos_apt'][:, :2]
        mask = (ghost_rays['reflectance'] != np.inf) & (ghost_rays['rrel'] <= 1)

        ghost_mask = np.max(np.abs(pos_apt), axis=1) <= ghost_scale
        if np.any(ghost_mask):
            mask &= ghost_mask

        valid_positions = positions[mask]
        if not len(valid_positions):
            continue

        pos_min = np.min(valid_positions, axis=0)
        pos_max = np.max(valid_positions, axis=0)
        center = (pos_min + pos_max) / 2.0

        radiuses = np.linalg.norm(valid_positions - center, axis=1)
        # Increase the radius by one division.
        valid_radius = float(np.max(radiuses)) + delta
        center_x = float(center[0])

        if valid_radius < radius:
            ghost_datas.array[i]['center'] = center_x
            ghost_datas.array[i]['radius'] = valid_radius


def get_ghost_datas(lens: api.Lens) -> Array:
    """Return the GhostDatas for a lens."""

    paths = get_paths(lens.surfaces)
    entrance_surface = lens.surfaces[0]
    array = np.zeros((len(paths),), dtype=ghost_data_dtype)
    array['path'] = np.array(paths)
    array['radius'] = entrance_surface.radius
    ghost_datas = Array(array=array, args=lens)
    return ghost_datas


# NOTE: Don't cache this, will be overwritten on every frame.
def get_areas(ghost_count: int, tri_count: int) -> Array:
    """Return empty areas (np.nan) for every triangle for every ghost."""

    array = np.full((ghost_count, tri_count), np.nan, dtype=np.float32)
    areas = Array(array=array, args=(ghost_count, tri_count))
    return areas


# NOTE: Don't cache this, will be overwritten on every frame.
def get_intensities(ghost_count: int, tri_count: int) -> Array:
    """Return empty intensities (np.nan) for every triangle for every ghost."""

    array = np.full((ghost_count, tri_count), np.nan, dtype=np.float32)
    areas = Array(array=array, args=(ghost_count, tri_count))
    return areas


def get_area_orig(radius: float, divisions: int) -> float:
    """Return the original area for a triangle."""

    # Because not all triangles are the same size, the easiest approximation is to
    # get the area of the disc mesh and divide ti by the number of triangles.
    area_disc = np.pi * radius**2
    tri_count = raytracing.get_tri_count(divisions)
    area = area_disc / tri_count
    return area


@lru_cache(1)
def get_mesh(divisions: int) -> Array:
    """Return an Array with triangle indices."""

    array = DiscMesh.get_indices(divisions)

    # Pad to align 16bit
    padded = np.zeros((array.shape[0], 4), dtype=np.uint32)
    padded[:, :3] = array

    mesh_indices = Array(array=padded, args=divisions)
    return mesh_indices


def get_rays(ghost_count: int, ray_count: int) -> Array:
    """Return an empty array of rays."""

    array = np.zeros((ghost_count, ray_count), dtype=ray_dtype)
    rays = Array(array=array, args=(ghost_count, ray_count))
    return rays
