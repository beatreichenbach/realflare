# Rendering

## OpenCL

[An Introduction to the OpenCL Programming Model](https://cims.nyu.edu/~schlacht/OpenCLModel.pdf)
[OpenCL 3.0 Reference Guide](https://www.khronos.org/files/opencl-quick-reference-card.pdf)

[My first opencl issue!](https://github.com/inducer/pyopencl/issues/618)

[OpenCL benchmark example](https://github.com/stefanv/PyOpenCL/blob/master/examples/benchmark-all.py)

[image2d_array_t](https://stackoverflow.com/questions/73166631/composite-multiple-images-using-opencl-and-python-kernel-image2d-array-t)

To run OpenCL on the CPU download the [runtime](https://www.intel.com/content/www/us/en/developer/articles/tool/opencl-drivers.html#latest_CPU_runtime).
## Rasterization

[Rasterization: a Practical Implementation](https://www.scratchapixel.com/lessons/3d-basic-rendering/rasterization-practical-implementation/overview-rasterization-algorithm.html)

[Optimizing Software Occlusion Culling](https://fgiesen.wordpress.com/2013/02/17/optimizing-sw-occlusion-culling-index/)

[Generalized Barycentric Coordinates on Irregular Polygons
](http://geometry.caltech.edu/pubs/MHBD02.pdf)

[A Quadrilateral Rendering Primitive](https://core.ac.uk/download/pdf/53544051.pdf) (implemented)

[a2flo/oclraster](https://github.com/a2flo/oclraster)

[Tiny renderer or how OpenGL works: software rendering in 500 lines of code](https://github.com/ssloy/tinyrenderer/wiki)

### Sampling
[Antialiasing: To Splat or Not](https://www.reedbeta.com/blog/antialiasing-to-splat-or-not/)
[Filter Importance Sampling](https://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.183.3579&rep=rep1&type=pdf)
[Blender Cycles implementation of importance sampling](https://github.com/blender/cycles/blob/c40170f6ea8828757eb2cb8db960d3bf4620d03f/src/scene/film.cpp)

# Rasterization Workflow

## Primitive Shader
The prim shader calculates the area per primitive. This will later be used to calculate the intensity.
It also calculates the bounds per primitive for all wavelengths. There were a few optimizations that didn't work.
To interpolate between different wavelengths, we have to store prims in the binning queue that are outside rrel.
Only if the prim of all wavelengths is outside rrel can the primitive be culled.

Culling areas that were really small also didn't seem like it was helping as it just introduced small artefacts in caustics and didn't speed up the renderer.
## Vertex Shader
## Binner
## Rasterizer
