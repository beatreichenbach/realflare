# Benchmark Report v0.5.0

## Score

| Function                      | Time          |
|-------------------------------|---------------|
| PreprocessTask.run            | 222.42ms      |
| GhostApertureTask.run         | 1.29ms        |
| GhostTask.run                 | 74.34ms       |
| RaytracingTask.run            | 234.13ms      |
| RasterizingTask.prim_shader   | 5.82ms        |
| RasterizingTask.vertex_shader | 7.52ms        |
| RasterizingTask.binner        | 8.89ms        |
| RasterizingTask.rasterizer    | 3875.74ms     |
| StarburstApertureTask.run     | 1.73ms        |
| StarburstTask.run             | 402.51ms      |
| **Engine.render**             | **9313.48ms** |

## Software

| Name          | Version                   |
|---------------|---------------------------|
| platform      | Windows-10-10.0.19045-SP0 |
| opencl        | OpenCL C 1.2              |
| python        | 3.10.11                   |
| realflare     | 0.5.0                     |
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

`"venv310\Scripts\python.exe" -m realflare --project "benchmark\nikon_ai_50_135mm\project.json" --animation "benchmark\nikon_ai_50_135mm\project.json" --frame-start 1 --frame-end 2 --log 20`
