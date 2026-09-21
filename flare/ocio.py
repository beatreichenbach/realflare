import functools
import os

import numpy as np
import PyOpenColorIO as OCIO

from flare import env

DEFAULT_CONFIG = 'cg-config-v2.2.0_aces-v1.3_ocio-v2.4'
XYZ_BUILTIN = 'UTILITY - ACES-AP0_to_CIE-XYZ-D65_BFD'


@functools.lru_cache(maxsize=1)
def get_config() -> OCIO.Config:  # ty: ignore[unresolved-attribute]
    """
    Return the active OCIO config.

    The config is loaded from the `OCIO` environment variable when set,
    otherwise the built-in ACES CG config is used. The result is cached, so the
    environment is only read once.
    """

    if os.environ.get(env.OCIO):
        return OCIO.Config.CreateFromEnv()  # ty: ignore[unresolved-attribute]
    return OCIO.Config.CreateFromBuiltinConfig(DEFAULT_CONFIG)  # ty: ignore[unresolved-attribute]


@functools.lru_cache(maxsize=1)
def get_xyz_to_scene_linear() -> np.ndarray:
    """
    Return the CIE XYZ to scene-linear RGB matrix of the active config.

    The matrix assumes an XYZ white point of D65. OCIO configs do not define a
    CIE XYZ colorspace, so the conversion inverts the ACES AP0 utility transform
    and then maps to the config's scene-linear role.
    """

    config = get_config()

    transform = OCIO.GroupTransform()  # ty: ignore[unresolved-attribute]
    transform.appendTransform(
        OCIO.BuiltinTransform(  # ty: ignore[unresolved-attribute]
            style=XYZ_BUILTIN,
            direction=OCIO.TRANSFORM_DIR_INVERSE,  # ty: ignore[unresolved-attribute]
        )
    )
    transform.appendTransform(
        OCIO.ColorSpaceTransform(  # ty: ignore[unresolved-attribute]
            OCIO.ROLE_INTERCHANGE_SCENE,  # ty: ignore[unresolved-attribute]
            OCIO.ROLE_SCENE_LINEAR,  # ty: ignore[unresolved-attribute]
        )
    )

    processor = config.getProcessor(transform)
    cpu = processor.getDefaultCPUProcessor()
    basis = ([1, 0, 0], [0, 1, 0], [0, 0, 1])
    return np.array([cpu.applyRGB(vector) for vector in basis]).T


def create_shader_source() -> str:
    """
    Return the GLSL source for the OCIO view transform.

    The transform maps scene-linear values through the default display and view
    of the active config. The source is baked into the program when it is
    created, so a change to the OCIO config does not recompile the shader yet.
    """

    config = get_config()

    display = config.getDefaultDisplay()
    view = config.getDefaultView(display)

    transform = OCIO.DisplayViewTransform()  # ty: ignore[unresolved-attribute]
    transform.setSrc(OCIO.ROLE_SCENE_LINEAR)  # ty: ignore[unresolved-attribute]
    transform.setDisplay(display)
    transform.setView(view)

    gpu = config.getProcessor(transform).getDefaultGPUProcessor()
    shader_desc = OCIO.GpuShaderDesc.CreateShaderDesc(OCIO.GPU_LANGUAGE_GLSL_4_0)  # ty: ignore[unresolved-attribute]
    gpu.extractGpuShaderInfo(shader_desc)
    return shader_desc.getShaderText()
