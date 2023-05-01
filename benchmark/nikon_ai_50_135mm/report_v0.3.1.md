# Benchmark Report v0.3.1

## Score

| Function                      | Time            |
|-------------------------------|-----------------|
| ApertureTask.run              | 1.172ms         |
| StarburstTask.run             | 10.177ms        |
| GhostTask.run                 | 474.003ms       |
| RaytracingTask.run            | 828.768ms       |
| RasterizingTask.prim_shader   | 40.692ms        |
| RasterizingTask.vertex_shader | 41.685ms        |
| RasterizingTask.binner        | 77.324ms        |
| RasterizingTask.rasterizer    | 10639.003ms     |
| RasterizingTask.rasterize     | 10897.632ms     |
| **Engine.render**             | **12973.680ms** |

## Software

| Name          | Version                   |
|---------------|---------------------------|
| platform      | Windows-10-10.0.19044-SP0 |
| opencl        | OpenCL C 1.2              |
| python        | 3.10.10                   |
| realflare     | 0.3.1                     |
| qt_extensions | 0.1.3                     |
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

`venv\Scripts\python.exe -m realflare --project benchmark\nikon_ai_50_135mm\project.json`
