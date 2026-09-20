# Realflare

Physically-based lens flare rendering using spectral raytracing on the GPU.

## Installation

### Requirements

- **Python 3.11–3.13** (OpenEXR ships no 3.14 wheels yet)
- **OpenGL 4.3+** (compute shaders required)
- **Discrete GPU** recommended (NVIDIA/AMD with 4GB+ VRAM)

| Platform        | Status            | Notes                                       |
|-----------------|-------------------|---------------------------------------------|
| Linux (Wayland) | Partial           | Use `egl` backend and `wayland` Qt Platform |
| Linux (X11)     | Supported         | Use `glx` backend and `xcb` Qt Platform     |
| Windows         | Supported         | Install GPU drivers                         |
| macOS           | **Not supported** | Apple stopped at OpenGL 4.1                 |

### Quick Install (Linux)

```bash
git clone https://github.com/beatreichenbach/realflare.git
cd realflare
chmod +x scripts/install.sh
./scripts/install.sh
```

### Wayland

If not automatically detected:
```bash
export QT_QPA_PLATFORM=wayland
export PYOPENGL_PLATFORM=egl
```

### NVIDIA

Force to use the discrete NVIDIA GPU:
```bash
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
```

### Quick Install (Windows)

```bat
git clone https://github.com/beatreichenbach/realflare.git
cd realflare
scripts\install.bat
```

### Manual Install

```bash
git clone https://github.com/beatreichenbach/realflare.git
cd realflare
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[openexr]"
```

## Usage

```bash
# Launch the GUI
flare gui

# Render a project from CLI
flare render --project path/to/project.json

# Render with animation
flare render --project path/to/project.json --animation path/to/animation.json
```

## Nuke Plugin

A Nuke plugin is available for rendering lens flares from the Nuke gizmo.
See [plugins/nuke/README.md](plugins/nuke/README.md) for installation and usage.

## About this Repository

### External Resources

- [OpticsExplorer Optics Database](https://github.com/amegahed/OpticsDatabase)

### References

Primary research this app is based on:
- [Physically-Based Real-Time Lens Flare Rendering](https://dl.acm.org/doi/abs/10.1145/2010324.1965003), Hullin et al., 2011
- [Temporal Glare: Real-Time Dynamic Simulation of the Scattering in the Human Eye](https://people.mpi-inf.mpg.de/~ritschel/Papers/TemporalGlare.pdf), Ritschel et al., 2009
- [Glare Generation Based on Wave Optics](http://nishitalab.org/user/nis/cdrom/pg/glare_m.pdf), Kakimoto et al., 2014

Additional interesting research:
- [General Spectral Camera Lens Simulation](https://jo.dreggn.org/home/2011_lens_simulation.pdf), Steinert et al., 2011
- [Efficient Monte Carlo Rendering with Realistic Lenses](https://jo.dreggn.org/home/2014_lenssim.pdf), Hanika and Dachsbacher, 2014
- [Sparse high-degree polynomials for wide-angle lenses](https://jo.dreggn.org/home/2014_lenssim.pdf), Schrade et al., 2016
- [Brute-force calculation of aperture diffraction in camera lenses](https://jo.dreggn.org/home/2019_diffraction.pdf), Schrade et al., 2019
- [Polynomial Optics: A Construction Kit for Efficient Ray-Tracing of Lens Systems](https://www.cs.ubc.ca/labs/imager/tr/2012/PolynomialOptics/), Hullin et al., 2012
- [Reference Implementation for papers titled Real-time ray transfer for lens flare rendering using sparse polynomials and Efficient tile-based rendering of lens flare ghosts](https://github.com/bodonyiandi94/LensFlareFramework)

Further references:
- [Johannes Hanika](https://jo.dreggn.org/home)
- [Zhongyi Flare Test](https://www.youtube.com/watch?v=WjKnqnbiCWU), YouTube, 2016
- [Diffractsim: A diffraction simulator for exploring and visualizing physical optics](https://github.com/rafael-fuente/diffractsim)


## Development

To get started:
```sh
uv venv --python 3.13
uv pip install -e ".[dev]"
pre-commit install
```

### Project Structure

```
flare/
  api/        - Data models (project, database, illuminants)
  core/       - Path parsing, preferences, state management
  engine/     - OpenGL rendering engine
  cli/        - Command-line interface
  gui/        - Qt GUI application
  widgets/    - Reusable Qt components (Viewer, DockWindow)
```

## License

Copyright (c) 2026 Beat Reichenbach. This project is licensed under the [GPLv3 License](LICENSE).
