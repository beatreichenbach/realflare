# Benchmark Report v0.4.2

## Score

| Function                      | Time            |
|-------------------------------|-----------------|
| ApertureTask.run              | 1.942ms         |
| GhostTask.run                 | 80.440ms        |
| RaytracingTask.run            | 803.626ms       |
| RasterizingTask.prim_shader   | 35.509ms        |
| RasterizingTask.vertex_shader | 38.063ms        |
| RasterizingTask.binner        | 68.042ms        |
| RasterizingTask.rasterizer    | 10450.261ms     |
| **Engine.render**             | **12813.759ms** |

## Software

| Name          | Version                   |
|---------------|---------------------------|
| platform      | Windows-10-10.0.19044-SP0 |
| opencl        | OpenCL C 1.2              |
| python        | 3.10.10                   |
| realflare     | 0.4.2                     |
| qt_extensions | 0.0.2                     |
| pyopencl      | 2022.3.1                  |
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

`venv\Scripts\python.exe -m realflare --project benchmark\nikon_ai_50_135mm\project.json --log 20`
