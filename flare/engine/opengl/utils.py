from typing import Any

from OpenGL import GL
from OpenGL.constant import Constant


def get_gl_string(name: int | Constant) -> str:
    """Return a decoded OpenGL string for a glGetString name."""

    value = GL.glGetString(name)
    return value.decode('utf-8') if value else 'unavailable'


def get_compute_work_group_size() -> tuple[int, int, int]:
    """Return the maximum compute work group size per dimension."""

    return _integer_array(GL.GL_MAX_COMPUTE_WORK_GROUP_SIZE)


def get_compute_work_group_count() -> tuple[int, int, int]:
    """Return the maximum compute work group count per dimension."""

    return _integer_array(GL.GL_MAX_COMPUTE_WORK_GROUP_COUNT)


def get_max_compute_work_group_invocations() -> int:
    """Return the maximum number of invocations in a compute work group."""

    return int(GL.glGetInteger(GL.GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS))


def get_gpu_info() -> list[tuple[str, str]]:
    """Return OpenGL and GPU information for the current context."""

    return [
        ('vendor', get_gl_string(GL.GL_VENDOR)),
        ('renderer', get_gl_string(GL.GL_RENDERER)),
        ('version', get_gl_string(GL.GL_VERSION)),
        ('glsl', get_gl_string(GL.GL_SHADING_LANGUAGE_VERSION)),
        ('max work group size', str(get_compute_work_group_size())),
        ('max work group count', str(get_compute_work_group_count())),
        ('max invocations', str(get_max_compute_work_group_invocations())),
        ('vram', _vram_text()),
    ]


def get_vram_info() -> dict[str, int | None]:
    """
    Return VRAM usage in KB.

    Keys: total_kb, available_kb, used_kb
    Values are int in KB or None if unsupported/unavailable.
    Works across vendors: NVIDIA (NVX), ATI/AMD (ATI_meminfo).
    Requires a current OpenGL context; otherwise returns all None.
    """

    total_kb: int | None = None
    available_kb: int | None = None

    # NVIDIA: GL_NVX_gpu_memory_info
    try:
        from OpenGL.GL.NVX.gpu_memory_info import (
            GL_GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX,
            GL_GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX,
        )

        total_val = GL.glGetIntegerv(GL_GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX)
        avail_val = GL.glGetIntegerv(GL_GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX)
        total_kb = _as_int(total_val)
        available_kb = _as_int(avail_val)
        # Treat 0 as unavailable (no context or unsupported)
        if total_kb == 0:
            total_kb = None
        if available_kb == 0 and total_kb is None:
            available_kb = None
    except Exception:
        pass

    # ATI / AMD: GL_ATI_meminfo (GL_TEXTURE_FREE_MEMORY_ATI = 0x87FC)
    # Returns 4 ints: [total free, largest block, aux free, largest aux] in KB.
    # No total dedicated, so only available can be queried.
    if available_kb is None:
        try:
            GL_TEXTURE_FREE_MEMORY_ATI = 0x87FC
            # Try to get via glGetIntegerv; may need to check extension.
            # Some implementations expose as vec4, others via glGetIntegerv with count.
            # We try generic call and parse first element.
            val = GL.glGetIntegerv(GL_TEXTURE_FREE_MEMORY_ATI)
            # In PyOpenGL, this returns a tuple/list of 4 ints if successful.
            if val is not None:
                if hasattr(val, '__len__') and len(val) >= 1:
                    available_kb = _as_int(val[0])
                else:
                    available_kb = _as_int(val)
                # Some drivers return 0 on failure, treat as unavailable
                if available_kb == 0:
                    available_kb = None
        except Exception:
            pass

    # Fallback for Renderbuffer free memory (same values)
    if available_kb is None:
        try:
            GL_RENDERBUFFER_FREE_MEMORY_ATI = 0x87FD
            val = GL.glGetIntegerv(GL_RENDERBUFFER_FREE_MEMORY_ATI)
            if val is not None and hasattr(val, '__len__') and len(val) >= 1:
                available_kb = _as_int(val[0])
            else:
                available_kb = _as_int(val)
            if available_kb == 0:
                available_kb = None
        except Exception:
            pass

    used_kb: int | None = None
    if total_kb is not None and available_kb is not None:
        try:
            used_kb = total_kb - available_kb
        except Exception:
            used_kb = None

    return {'total_kb': total_kb, 'available_kb': available_kb, 'used_kb': used_kb}


def get_total_vram_kb() -> int | None:
    """Return total VRAM in KB or None if unavailable."""

    return get_vram_info()['total_kb']


def get_available_vram_kb() -> int | None:
    """Return currently available VRAM in KB or None if unavailable."""

    return get_vram_info()['available_kb']


def get_used_vram_kb() -> int | None:
    """Return currently used VRAM in KB or None if unavailable."""

    return get_vram_info()['used_kb']


def _as_int(value: Any) -> int | None:  # noqa: ANN401
    """Return the int extracted from a glGet result."""

    if value is None:
        return None
    try:
        # numpy array or sequence
        if hasattr(value, '__len__') and not isinstance(value, (str, bytes)):
            if len(value) == 0:
                return None
            value = value[0]
        return int(value)
    except Exception:
        return None


def _integer_array(name: int | Constant) -> tuple[int, int, int]:
    return (
        int(GL.glGetIntegeri_v(name, 0)[0]),
        int(GL.glGetIntegeri_v(name, 1)[0]),
        int(GL.glGetIntegeri_v(name, 2)[0]),
    )


def _vram_text() -> str:
    info = get_vram_info()
    parts = []
    for label, key in (
        ('total', 'total_kb'),
        ('available', 'available_kb'),
        ('used', 'used_kb'),
    ):
        value = info.get(key)
        if value is not None:
            parts.append(f'{label} {value / 1024:.0f} MB')
    return ', '.join(parts) if parts else 'unavailable'
