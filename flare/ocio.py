import functools
import logging
import os

import numpy as np
import PyOpenColorIO as OCIO

DEFAULT_CONFIG = 'cg-config-v2.2.0_aces-v1.3_ocio-v2.4'
XYZ_BUILTIN = 'UTILITY - ACES-AP0_to_CIE-XYZ-D65_BFD'

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def get_config() -> OCIO.Config:
    """
    Return the active OCIO config.

    The config is loaded from the `OCIO` environment variable when set,
    otherwise the built-in ACES CG config is used. The result is cached, so the
    environment is only read once.
    """

    config = os.environ.get('OCIO')
    if config:
        logger.debug(f'Loading OCIO config: {config}')
        return OCIO.Config.CreateFromEnv()
    else:
        logger.debug(f'Loading default OCIO config: {DEFAULT_CONFIG}')
        return OCIO.Config.CreateFromBuiltinConfig(DEFAULT_CONFIG)


@functools.lru_cache(maxsize=1)
def get_xyz_to_scene_linear() -> np.ndarray:
    """
    Return the CIE XYZ to scene-linear RGB matrix of the active config.

    The matrix assumes an XYZ white point of D65. OCIO configs do not define a
    CIE XYZ colorspace, so the conversion inverts the ACES AP0 utility transform
    and then maps to the config's scene-linear role.
    """

    config = get_config()

    transform = OCIO.GroupTransform()
    builtin_transform = OCIO.BuiltinTransform(
        style=XYZ_BUILTIN, direction=OCIO.TRANSFORM_DIR_INVERSE
    )
    transform.appendTransform(builtin_transform)
    color_space_transform = OCIO.ColorSpaceTransform(
        OCIO.ROLE_INTERCHANGE_SCENE, OCIO.ROLE_SCENE_LINEAR
    )
    transform.appendTransform(color_space_transform)

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

    transform = OCIO.DisplayViewTransform()
    transform.setSrc(OCIO.ROLE_SCENE_LINEAR)
    transform.setDisplay(display)
    transform.setView(view)

    gpu = config.getProcessor(transform).getDefaultGPUProcessor()
    shader_desc = OCIO.GpuShaderDesc.CreateShaderDesc(OCIO.GPU_LANGUAGE_GLSL_4_0)
    gpu.extractGpuShaderInfo(shader_desc)
    return shader_desc.getShaderText()
