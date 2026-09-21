import os

import PyOpenColorIO as OCIO

# Step 1: Get the config
config = OCIO.GetCurrentConfig()

# Step 2: Lookup the display ColorSpace
display = config.getDefaultDisplay()
view = config.getDefaultView(display)

# Step 3: Create a DisplayViewTransform, and set the input, display, and view
# (This example assumes the input is a role. Adapt as needed.)
transform = OCIO.DisplayViewTransform()
transform.setSrc(OCIO.ROLE_SCENE_LINEAR)
transform.setDisplay(display)
transform.setView(view)

# Step 4: Create the processor
processor = config.getProcessor(transform)
gpu = processor.getDefaultGPUProcessor()

# Step 5: Extract the GLSL ShaderText to be used in OpenGL.
shader_desc = OCIO.GpuShaderDesc.CreateShaderDesc(language=OCIO.GPU_LANGUAGE_GLSL_4_0)
gpu.extractGpuShaderInfo(shader_desc)
source = shader_desc.getShaderText()
print(source)
