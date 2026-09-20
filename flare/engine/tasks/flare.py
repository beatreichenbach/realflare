import logging
from functools import lru_cache

import numpy as np
from OpenGL import GL
from OpenGL.constant import Constant
from qtpy import QtCore, QtGui

from flare import api

from ..base import Array
from ..opengl import OpenGLTask
from .common import LAMBDA_MAX, LAMBDA_MIN, DiscMesh, get_screen_scale, get_spectral
from .constants import SSBO, TEX, UBO

logger = logging.getLogger(__name__)

BATCH_PRIMITIVE_COUNT = 255


command_dtype = np.dtype(
    [
        ('count', np.uint32),
        ('instanceCount', np.uint32),
        ('firstIndex', np.uint32),
        ('baseVertex', np.uint32),
        ('baseInstance', np.uint32),
    ]
)

prim_params_dtype = np.dtype(
    [
        ('wavelength_count', np.uint32),
        ('wavelength_sub_count', np.uint32),
        ('min_area', np.float32),
        ('min_sliver', np.float32),
    ]
)

params_dtype = np.dtype(
    [
        ('wavelength_count', np.uint32),
        ('wavelength_sub_count', np.uint32),
        ('screen_scale', np.float32, 2),
        ('ghost_scale', np.float32),
        ('intensity', np.float32),
        ('_pad', np.float32, 2),
    ]
)


ghost_dtype = np.dtype(
    [
        ('ray_offset', np.uint32),
        ('ray_count', np.uint32),
        ('tri_offset', np.uint32),
        ('tri_count', np.uint32),
    ]
)


class FlareTask(OpenGLTask):
    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        super().__init__(context)

        # Prim
        comp_source = self.load_source('flare_prim.comp')
        comp_shader = self.load_shader(comp_source, GL.GL_COMPUTE_SHADER)

        self._prim_program = self.create_program(shaders=(comp_shader,))
        self._prim_ubo = self.create_buffer()
        self._ghosts_buffer = self.create_buffer()
        self._intensities_buffer = self.create_buffer()
        self._indices_buffer = self.create_buffer()
        self._counts_buffer = self.create_buffer()
        self._mesh_buffer = self.create_buffer()
        self._areas_buffer = self.create_buffer()

        self.bind_ubo(self._prim_ubo, UBO.PRIM)
        self.bind_ssbo(self._ghosts_buffer, SSBO.FLARE_GHOSTS)
        self.bind_ssbo(self._intensities_buffer, SSBO.INTENSITIES)
        self.bind_ssbo(self._indices_buffer, SSBO.INDICES)
        self.bind_ssbo(self._counts_buffer, SSBO.COUNTS)
        self.bind_ssbo(self._mesh_buffer, SSBO.MESH)
        self.bind_ssbo(self._areas_buffer, SSBO.AREAS)

        self.bind_ubo_block(self._prim_program, 'Params', UBO.PRIM)
        self.bind_ssbo_block(self._prim_program, 'Ghosts', SSBO.FLARE_GHOSTS)
        self.bind_ssbo_block(self._prim_program, 'Intensities', SSBO.INTENSITIES)
        self.bind_ssbo_block(self._prim_program, 'Indices', SSBO.INDICES)
        self.bind_ssbo_block(self._prim_program, 'Counts', SSBO.COUNTS)
        self.bind_ssbo_block(self._prim_program, 'Mesh', SSBO.MESH)
        self.bind_ssbo_block(self._prim_program, 'Areas', SSBO.AREAS)
        self.bind_ssbo_block(self._prim_program, 'Rays', SSBO.RAYS)

        self.bind_ubo_block(self._prim_program, 'Params', UBO.PRIM)
        self.bind_ssbo_block(self._prim_program, 'Ghosts', SSBO.FLARE_GHOSTS)
        self.bind_ssbo_block(self._prim_program, 'Intensities', SSBO.INTENSITIES)
        self.bind_ssbo_block(self._prim_program, 'Indices', SSBO.INDICES)
        self.bind_ssbo_block(self._prim_program, 'Counts', SSBO.COUNTS)
        self.bind_ssbo_block(self._prim_program, 'Mesh', SSBO.MESH)
        self.bind_ssbo_block(self._prim_program, 'Areas', SSBO.AREAS)
        self.bind_ssbo_block(self._prim_program, 'Rays', SSBO.RAYS)

        # Commands
        comp_source = self.load_source('flare_commands.comp')
        comp_shader = self.load_shader(comp_source, GL.GL_COMPUTE_SHADER)

        self._commands_program = self.create_program(shaders=(comp_shader,))
        self._commands_buffer = self.create_buffer()

        self.bind_ssbo(self._commands_buffer, SSBO.COMMANDS)

        self.bind_ubo_block(self._commands_program, 'Params', UBO.PRIM)
        self.bind_ssbo_block(self._commands_program, 'Commands', SSBO.COMMANDS)
        self.bind_ssbo_block(self._commands_program, 'Ghosts', SSBO.FLARE_GHOSTS)
        self.bind_ssbo_block(self._commands_program, 'Counts', SSBO.COUNTS)

        # Render
        vertex_source = self.load_source('flare.vert')
        vertex_shader = self.load_shader(vertex_source, GL.GL_VERTEX_SHADER)
        fragment_source = self.load_source('flare.frag')
        fragment_shader = self.load_shader(fragment_source, GL.GL_FRAGMENT_SHADER)

        self._program = self.create_program(shaders=(vertex_shader, fragment_shader))
        self._fbo_texture = self.create_texture(clamp_to_border=True)
        self._fbo = self.create_fbo(self._fbo_texture)
        self._fbo_texture_ssaa = self.create_texture(clamp_to_border=True)
        self._fbo_ssaa = self.create_fbo(self._fbo_texture_ssaa)
        self._ubo = self.create_buffer()
        self._vao = self.create_vao()
        self._neighbors_buffer = self.create_buffer()
        self._spectral_image = self.create_texture()
        self._ghost_image = self.create_texture(clamp_to_border=True)

        self.bind_ubo(self._ubo, UBO.FLARE)
        self.bind_ssbo(self._neighbors_buffer, SSBO.NEIGHBORS)
        self.bind_texture(self._spectral_image, TEX.FLARE_SPECTRAL)
        self.bind_texture(self._ghost_image, TEX.FLARE_GHOST)

        self.bind_ubo_block(self._program, 'Params', UBO.FLARE)
        self.bind_ssbo_block(self._program, 'Neighbors', SSBO.NEIGHBORS)
        self.bind_ssbo_block(self._program, 'Ghosts', SSBO.FLARE_GHOSTS)
        self.bind_ssbo_block(self._program, 'Intensities', SSBO.INTENSITIES)
        self.bind_ssbo_block(self._program, 'Mesh', SSBO.MESH)
        self.bind_ssbo_block(self._program, 'Rays', SSBO.RAYS)
        self.bind_texture_loc(self._program, 'spectral_image', TEX.FLARE_SPECTRAL)
        self.bind_texture_loc(self._program, 'ghost_image', TEX.FLARE_GHOST)

    def cleanup(self) -> None:
        self.delete(
            programs=(
                self._prim_program,
                self._commands_program,
                self._program,
            ),
            textures=(
                self._fbo_texture,
                self._fbo_texture_ssaa,
                self._spectral_image,
                self._ghost_image,
            ),
            render_buffers=(
                self._fbo,
                self._fbo_ssaa,
            ),
            vertex_arrays=(self._vao,),
            buffers=(
                # Prim
                self._prim_ubo,
                self._ghosts_buffer,
                self._intensities_buffer,
                self._indices_buffer,
                self._counts_buffer,
                self._mesh_buffer,
                self._areas_buffer,
                # Commands
                self._commands_buffer,
                # Render
                self._ubo,
                self._neighbors_buffer,
            ),
        )

    @lru_cache(1)  # noqa: B019
    def update_fbo_resolution(self, resolution: QtCore.QSize) -> None:
        self._fbo_texture = self.create_texture(
            clamp_to_border=True, resolution=resolution.toTuple()
        )
        self.update_fbo(self._fbo, self._fbo_texture)

    @lru_cache(1)  # noqa: B019
    def update_fbo_ssaa_resolution(self, resolution: QtCore.QSize) -> None:
        self._fbo_texture_ssaa = self.create_texture(
            clamp_to_border=True, resolution=resolution.toTuple()
        )
        self.update_fbo(self._fbo_ssaa, self._fbo_texture_ssaa)

    @staticmethod
    def compute_prims(program: int, ghost_datas: Array) -> None:
        """Run the compute shader, dispatching each ghost separately."""

        GL.glUseProgram(program)

        loc = GL.glGetUniformLocation(program, 'ghost_id')
        ghost_array = ghost_datas.array[~ghost_datas.array['culled']]
        tri_counts = ghost_array['divisions'] ** 2 * 6

        local_size_x = 512
        for ghost_id, tri_count in enumerate(tri_counts):
            groups_x = (tri_count + local_size_x - 1) // local_size_x
            GL.glUniform1ui(loc, ghost_id)
            GL.glDispatchCompute(groups_x, 1, 1)

        GL.glMemoryBarrier(GL.GL_SHADER_STORAGE_BARRIER_BIT)
        GL.glFinish()

    @staticmethod
    def compute_commands(program: int, commands_count: int) -> None:
        groups_x = commands_count

        GL.glUseProgram(program)
        GL.glDispatchCompute(groups_x, 1, 1)
        GL.glMemoryBarrier(
            GL.GL_SHADER_STORAGE_BARRIER_BIT  # ty: ignore[unsupported-operator]
            | GL.GL_COMMAND_BARRIER_BIT
            | GL.GL_ELEMENT_ARRAY_BARRIER_BIT
        )
        GL.glFinish()

    @staticmethod
    def render_vao(
        program: int,
        fbo: int,
        resolution: QtCore.QSize,
        vao: int,
        indices_buffer: int,
        commands_buffer: int,
        commands_count: int,
        wireframe: bool = False,
    ) -> None:
        """Render the program to the framebuffer."""

        # GL.glEnable(GL.GL_MULTISAMPLE)

        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(GL.GL_FALSE)

        GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, fbo)
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glViewport(0, 0, resolution.width(), resolution.height())

        GL.glUseProgram(program)

        GL.glBindVertexArray(vao)
        GL.glBindBuffer(GL.GL_DRAW_INDIRECT_BUFFER, commands_buffer)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, indices_buffer)

        if wireframe:
            GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)

        GL.glMultiDrawElementsIndirect(
            GL.GL_TRIANGLES,
            GL.GL_UNSIGNED_INT,
            None,
            commands_count,
            command_dtype.itemsize,
        )

        if wireframe:
            GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_FILL)

        GL.glFinish()

    @lru_cache(1)  # noqa: B019
    def run(
        self,
        camera: api.Flare.Camera,
        raytracing: api.Flare.Raytracing,
        render: api.Flare.Render,
        intensity: float,
        illuminant: str,
        ghost_datas: Array,
        rays: Array,
        ghost: Array,
        samples: int,
        wireframe: bool,
    ) -> Array:
        """Render the lens flare to a framebuffer."""

        # TODO: Determine pixel based subwavelengths.
        # Loop through all rays of wavelength 1 and compare with wavelength -1,
        # based on difference determine subwavelengths. To find the ideal sub count,
        # get the largest difference and scale it to screen, then turn that difference to
        # an integer (length in pixels > one sub count per pixel).

        # Params
        if raytracing.wavelength_count > 1:
            wavelength_sub_count = raytracing.wavelength_sub_count
        else:
            wavelength_sub_count = 1

        params = np.zeros((), dtype=prim_params_dtype)
        params['wavelength_count'] = raytracing.wavelength_count
        params['wavelength_sub_count'] = wavelength_sub_count
        params['min_area'] = raytracing.min_area
        params['min_sliver'] = raytracing.min_sliver
        self.update_ubo(self._prim_ubo, params)

        # Arrays
        ghosts = get_ghosts(ghost_datas)
        intensities = get_intensities(ghost_datas, raytracing.wavelength_count)
        indices = get_indices(ghost_datas)
        counts = get_counts(ghost_datas)
        mesh_indices = get_mesh(ghost_datas)
        neighbors = get_neighbors(ghost_datas)
        areas = get_areas(ghost_datas)

        # Buffers
        usage = GL.GL_DYNAMIC_COPY
        self.update_ssbo(self._indices_buffer, indices.array, usage)
        self.update_ssbo(self._counts_buffer, counts.array, usage)
        self.update_ssbo(self._intensities_buffer, intensities.array, usage)
        cached_update_ssbo(self._ghosts_buffer, ghosts)
        cached_update_ssbo(self._mesh_buffer, mesh_indices)
        cached_update_ssbo(self._areas_buffer, areas)

        # Compute
        self.compute_prims(self._prim_program, ghost_datas)

        # Update args after compute
        indices.args = rays
        counts.args = rays
        intensities.args = (rays, areas, raytracing.min_area)

        # Arrays
        commands = get_commands(ghost_datas)
        commands_count = len(commands.array)

        # Buffers
        self.update_ssbo(self._commands_buffer, commands.array, GL.GL_DYNAMIC_COPY)

        # Compute
        self.compute_commands(self._commands_program, commands_count)

        # Update args after compute
        commands.args = rays

        # Params
        sensor_size = camera.sensor_size.toTuple()
        screen_scale = get_screen_scale(sensor_size, render.resolution)
        ghost_scale = get_ghost_scale(camera.fstop)

        params = np.zeros((), dtype=params_dtype)
        params['wavelength_count'] = raytracing.wavelength_count
        params['wavelength_sub_count'] = wavelength_sub_count
        params['screen_scale'] = tuple(i * 0.8 for i in screen_scale)
        params['ghost_scale'] = ghost_scale
        params['intensity'] = intensity
        self.update_ubo(self._ubo, params)

        # Images
        spectral_wavelength_count = LAMBDA_MAX - LAMBDA_MIN + 1
        spectral = get_spectral(illuminant, spectral_wavelength_count)

        # Buffers
        ssaa_scale = 2 ** (samples - 1)
        if ssaa_scale > 1:
            ssaa_resolution = render.resolution * ssaa_scale
            render_fbo = self._fbo_ssaa
            render_resolution = ssaa_resolution
            self.update_fbo_ssaa_resolution(ssaa_resolution)
            self.update_fbo_resolution(render.resolution)
        else:
            render_resolution = render.resolution
            render_fbo = self._fbo
            self.update_fbo_resolution(render.resolution)

        cached_update_ssbo(self._neighbors_buffer, neighbors)
        cached_update_texture(self._spectral_image, spectral)
        cached_update_texture(self._ghost_image, ghost)

        self.render_vao(
            program=self._program,
            fbo=render_fbo,
            resolution=render_resolution,
            vao=self._vao,
            indices_buffer=self._indices_buffer,
            commands_buffer=self._commands_buffer,
            commands_count=commands_count,
            wireframe=wireframe,
        )

        if ssaa_scale > 1:
            self.blit_fbos(
                source=self._fbo_ssaa,
                destination=self._fbo,
                source_resolution=render_resolution,
                destination_resolution=render.resolution,
            )

        array = self.read_texture(self._fbo_texture, render.resolution)
        args = (
            rays,
            ghost,
            intensity,
            illuminant,
            camera,
            raytracing,
            render,
            samples,
            wireframe,
        )
        image = Array(array=array, args=args)
        return image


@lru_cache(1)
def cached_update_texture(texture: int, array: Array) -> None:
    OpenGLTask.update_texture(texture, array.array)


@lru_cache(1)
def cached_update_ssbo(
    buffer: int,
    array: Array,
    usage: int | Constant = GL.GL_DYNAMIC_DRAW,
) -> None:
    OpenGLTask.update_ssbo(buffer, array.array, usage)


@lru_cache(1)
def get_areas(ghost_datas: Array) -> Array:
    """Return the original areas of a triangle for every ghost."""

    ghost_array = ghost_datas.array[~ghost_datas.array['culled']]

    lengths = ghost_array['radius'] / ghost_array['divisions']
    array = np.asarray((np.sqrt(3) / 4) * (lengths**2), dtype=np.float32)

    areas = Array(array=array, args=ghost_datas)
    return areas


def get_ghost_scale(fstop: float) -> float:
    """
    Return the scale for a ghost based on the fstop of the lens.
    While the minimum fstop is different per lens and could be used, it doesn't
    make sense to adjust the ProjectEditor parameters every time the lens changes.
    Instead, a default of f1 is used.
    """

    min_fstop = 1
    ghost_scale = min_fstop / fstop
    return ghost_scale


@lru_cache(1)
def get_mesh(ghost_datas: Array) -> Array:
    """Return an Array with triangle indices."""

    ghost_array = ghost_datas.array[~ghost_datas.array['culled']]
    if ghost_array.size > 0:
        max_divisions = max(int(ghost_array['divisions'].max()), 1)
    else:
        max_divisions = 1

    array = CachedDiscMesh.get_indices(max_divisions)

    # Pad to align 16bit
    padded = np.zeros((array.shape[0], 4), dtype=np.uint32)
    padded[:, :3] = array

    mesh_indices = Array(array=padded, args=max_divisions)
    return mesh_indices


class CachedDiscMesh:
    @staticmethod
    @lru_cache(1)
    def get_indices(divisions: int) -> np.ndarray:
        return DiscMesh.get_indices(divisions)

    @staticmethod
    @lru_cache(1)
    def get_neighbors(divisions: int) -> np.ndarray:
        return DiscMesh.get_neighbors(divisions)


@lru_cache(1)
def get_neighbors(ghost_datas: Array) -> Array:
    """Return an Array with neighbor indices (primitives) for every vertex."""

    ghost_array = ghost_datas.array[~ghost_datas.array['culled']]
    if ghost_array.size > 0:
        max_divisions = max(int(ghost_array['divisions'].max()), 1)
    else:
        max_divisions = 1

    tris = CachedDiscMesh.get_neighbors(max_divisions)

    neighbors = Array(array=tris, args=max_divisions)
    return neighbors


@lru_cache(1)
def get_intensities(ghost_datas: Array, wavelength_count: int) -> Array:
    """
    Return an Array to store intensities of the primitives. The intensities are
    calculated by determining how compressed the light (area) gets. The smaller an area,
    the brighter the primitive.
    """

    ghost_array = ghost_datas.array[~ghost_datas.array['culled']]
    tri_counts = ghost_array['divisions'] ** 2 * 6
    total_tri_count = np.sum(tri_counts).item()
    array = np.zeros((total_tri_count, wavelength_count), dtype=np.float32)
    intensities = Array(array=array, args=ghost_datas)
    return intensities


@lru_cache(1)
def get_indices(ghost_datas: Array) -> Array:
    """
    Return an Array to store vertex indices. These indices are a collection of the
    valid vertices that should be rendered.
    """

    ghost_array = ghost_datas.array[~ghost_datas.array['culled']]
    tri_counts = ghost_array['divisions'] ** 2 * 6
    total_tri_count = np.sum(tri_counts).item()

    array = np.zeros((total_tri_count, 3), dtype=np.uint32)
    indices = Array(array=array, args=ghost_datas)
    return indices


@lru_cache(1)
def get_counts(ghost_datas: Array) -> Array:
    """Return an Array to store vertex index counts."""

    ghost_array = ghost_datas.array[~ghost_datas.array['culled']]
    ghost_count = len(ghost_array)
    array = np.zeros(ghost_count, np.uint32)
    counts = Array(array=array, args=ghost_datas)
    return counts


@lru_cache(1)
def get_commands(ghost_datas: Array) -> Array:
    """Return an Array to store indirect draw commands."""

    ghost_array = ghost_datas.array[~ghost_datas.array['culled']]
    ghost_count = len(ghost_array)
    array = np.zeros(ghost_count, command_dtype)
    commands = Array(array=array, args=ghost_datas)
    return commands


@lru_cache(1)
def get_ghosts(ghost_datas: Array) -> Array:
    """Return an Array with ghosts."""

    ghost_array = ghost_datas.array[~ghost_datas.array['culled']]
    ray_counts = 1 + (3 * ghost_array['divisions'] * (ghost_array['divisions'] + 1))
    tri_counts = ghost_array['divisions'] ** 2 * 6

    array = np.zeros(len(ghost_array), ghost_dtype)
    array['ray_offset'] = np.cumsum(ray_counts) - ray_counts
    array['ray_count'] = ray_counts
    array['tri_offset'] = np.cumsum(tri_counts) - tri_counts
    array['tri_count'] = tri_counts

    ghosts = Array(array=array, args=ghost_datas)
    return ghosts
