from typing import NamedTuple

import numpy as np
from OpenGL import GL
from OpenGL.constant import Constant


class VramInfo(NamedTuple):
    total_kb: int | None = None
    available_kb: int | None = None


def get_compute_work_group_size() -> tuple[int, int, int]:
    """Return the maximum compute work group size per dimension."""

    work_group_size = (
        int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_SIZE, 0)[0]),
        int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_SIZE, 1)[0]),
        int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_SIZE, 2)[0]),
    )
    return work_group_size


def get_compute_work_group_count() -> tuple[int, int, int]:
    """Return the maximum compute work group count per dimension."""

    work_group_count = (
        int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_COUNT, 0)[0]),
        int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_COUNT, 1)[0]),
        int(GL.glGetIntegeri_v(GL.GL_MAX_COMPUTE_WORK_GROUP_COUNT, 2)[0]),
    )
    return work_group_count


def get_max_compute_work_group_invocations() -> int:
    """Return the maximum number of invocations in a compute work group."""

    max_work_group_invocations = int(
        GL.glGetInteger(GL.GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS)
    )
    return max_work_group_invocations


def get_gpu_info() -> list[tuple[str, str]]:
    """Return OpenGL and GPU information for the current context."""

    return [
        ('vendor', _get_gl_string(GL.GL_VENDOR)),
        ('renderer', _get_gl_string(GL.GL_RENDERER)),
        ('version', _get_gl_string(GL.GL_VERSION)),
        ('glsl', _get_gl_string(GL.GL_SHADING_LANGUAGE_VERSION)),
        ('max work group size', str(get_compute_work_group_size())),
        ('max work group count', str(get_compute_work_group_count())),
        ('max invocations', str(get_max_compute_work_group_invocations())),
        ('vram', get_vram_text()),
    ]


def get_vram_text() -> str:
    """Return a one-line VRAM summary in GB, or 'unavailable'."""

    info = _get_vram_info()

    if info.total_kb is None:
        values = (('available', info.available_kb),)
    else:
        used_kb = None
        if info.available_kb is not None:
            used_kb = info.total_kb - info.available_kb
        values = (('used', used_kb), ('total', info.total_kb))

    parts = [
        f'{label} {value / 2**20:.1f} GB'
        for label, value in values
        if value is not None
    ]
    text = ', '.join(parts) if parts else 'unavailable'
    return text


def _get_vram_info() -> VramInfo:
    """
    Return VRAM usage in KB, or an empty VramInfo if unsupported/unavailable.

    Requires a current OpenGL context; otherwise all fields are None.
    """

    info = _nvidia_vram()
    if info is None:
        info = _ati_vram()
        if info is None:
            info = VramInfo()
    return info


def _nvidia_vram() -> VramInfo | None:
    """Return VRAM info in KB from the NVIDIA NVX extension."""

    # NVIDIA: GL_NVX_gpu_memory_info
    try:
        from OpenGL.GL.NVX.gpu_memory_info import (
            GL_GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX,
            GL_GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX,
        )

        total_val = GL.glGetIntegerv(GL_GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX)
        avail_val = GL.glGetIntegerv(GL_GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX)
    except (ImportError, GL.error.Error):
        return None

    total_kb = int(total_val)
    available_kb = int(avail_val)

    # Treat 0 as unavailable (no context or unsupported)
    if total_kb == 0:
        total_kb = None
    if available_kb == 0 and total_kb is None:
        available_kb = None

    if total_kb is None and available_kb is None:
        return None

    return VramInfo(total_kb, available_kb)


def _ati_vram() -> VramInfo | None:
    """Return VRAM info in KB from the ATI/AMD ATI_meminfo extension."""

    # GL_ATI_meminfo returns 4 ints:
    # [total free, largest block, aux free, largest aux] in KB.
    try:
        from OpenGL.GL.ATI.meminfo import GL_TEXTURE_FREE_MEMORY_ATI

        values = np.zeros(4, dtype=np.int32)
        GL.glGetIntegerv(GL_TEXTURE_FREE_MEMORY_ATI, values)
    except (ImportError, GL.error.Error):
        return None

    # Treat 0 as unavailable (no context or unsupported)
    available_kb = int(values[0])

    if available_kb == 0:
        return None

    return VramInfo(None, available_kb)


def _get_gl_string(name: int | Constant) -> str:
    """Return a decoded OpenGL string for a glGetString name."""

    value = GL.glGetString(name)
    return value.decode('utf-8') if value else 'unavailable'
