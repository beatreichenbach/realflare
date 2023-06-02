# Benchmark Report v0.4.4

## Score

| Function                      | Time            |
|-------------------------------|-----------------|
| ApertureTask.run              | 1.927ms         |
| GhostTask.run                 | 95.970ms        |
| RaytracingTask.run            | 843.095ms       |
| RasterizingTask.prim_shader   | 41.563ms        |
| RasterizingTask.vertex_shader | 39.259ms        |
| RasterizingTask.binner        | 70.969ms        |
| RasterizingTask.rasterizer    | 10020.515ms     |
| **Engine.render**             | **12045.031ms** |

## Software

| Name          | Version                   |
|---------------|---------------------------|
| platform      | Windows-10-10.0.19045-SP0 |
| opencl        | OpenCL C 1.2              |
| python        | 3.10.11                   |
| realflare     | 0.4.4                     |
| qt_extensions | 0.1.2                     |
| pyopencl      | 2023.1                    |
| numpy         | 1.24.3                    |
| PyOpenColorIO | 2.2.1                     |
| PySide2       | 5.15.2.1                  |

## Hardware
| Name                     | Value                                              |
|--------------------------|----------------------------------------------------|
| processor                | Intel64 Family 6 Model 79 Stepping 1, GenuineIntel |
| OpenCL Device            | NVIDIA GeForce GTX 1080 Ti                         |
| MAX_COMPUTE_UNITS        | 28                                                 |
| MAX_WORK_GROUP_SIZE      | 1024                                               |
| LOCAL_MEM_SIZE           | 49152                                              |
| GLOBAL_MEM_SIZE          | 11810897920                                        |
| MAX_CONSTANT_BUFFER_SIZE | 65536                                              |

## Realflare

`venv310\Scripts\python.exe -m realflare --project benchmark\nikon_ai_50_135mm\project.json --log 20`
