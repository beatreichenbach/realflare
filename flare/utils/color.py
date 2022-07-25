import logging
import numpy as np
import os
import re

import PyOpenColorIO as OCIO


def colorspace(array: np.ndarray, src: str, dst: str) -> np.ndarray:
    # https://opencolorio.readthedocs.io/en/latest/guides/developing/developing.html
    try:
        config = OCIO.GetCurrentConfig()

        src_colorspace = config.getColorSpace(src)
        dst_colorspace = config.getColorSpace(dst)
        processor = config.getProcessor(src_colorspace, dst_colorspace)
        cpu = processor.getDefaultCPUProcessor()
        if array.shape[-1] == 3:
            cpu.applyRGB(array)
        elif array.shape[-1] == 4:
            cpu.applyRGBA(array)
    except Exception as e:
        pass
        # logging.debug("OpenColorIO Error: ", e)
    finally:
        return array


# # https://opencolorio.readthedocs.io/en/latest/guides/developing/developing.html
# # ocio configs available here: https://github.com/colour-science/OpenColorIO-Configs/releases
# # for downloading and installing zip file: https://stackoverflow.com/questions/72502959/download-zip-file-from-url-using-python
# import PyOpenColorIO as OCIO

# # Step 1: Get the config
# config = OCIO.GetCurrentConfig()

# # Step 2: Lookup the display ColorSpace
# display = config.getDefaultDisplay()
# view = config.getDefaultView(display)

# # Step 3: Create a DisplayViewTransform, and set the input, display, and view
# # (This example assumes the input is a role. Adapt as needed.)

# transform = OCIO.DisplayViewTransform()
# transform.setSrc(OCIO.ROLE_SCENE_LINEAR)
# transform.setDisplay(display)
# transform.setView(view)

# # Step 4: Create the processor
# processor = config.getProcessor(transform)
# cpu = processor.getDefaultCPUProcessor()

# # Step 5: Apply the color transform to an existing RGB pixel
# imageData = [1, 0, 0]
# print(cpu.applyRGB(imageData))


def main():
    logging.getLogger().setLevel(logging.DEBUG)
    xyz = np.array(
        [[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9], [0.1, 0.5, 0.9]]],
        dtype=np.float32,
    )

    # config = OCIO.GetCurrentConfig()
    # for name in config.getViews('ACES'):
    #     logging.debug(name)

    # display = config.getDefaultDisplay()
    # view = config.getDefaultView(display)
    # logging.debug(display)
    # logging.debug(view)
    rgb = colorspace(xyz, 'Utility - XYZ - D60', 'Output - sRGB')
    logging.debug(rgb)


if __name__ == '__main__':
    main()
