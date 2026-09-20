# Realflare Nuke Plugin

The Realflare Nuke plugin adds a `Realflare` gizmo that renders lens flares with
the `flare` CLI and loads the result back into Nuke.

## Installation

Install Realflare as described in [../../README.md](../../README.md), then add
the `plugins/nuke` directory to Nuke's plug-in path using either option below.
See [Defining the Nuke Plug-in Path](https://learn.foundry.com/nuke/content/comp_environment/configuring_nuke/defining_nuke_plugin_path.html)
for details.

### 1. init.py

Add the directory to Nuke's plug-in path (Linux: `~/.nuke/init.py`, Windows: `%USERPROFILE%\.nuke\init.py`):

```python
import nuke

nuke.pluginAddPath('/path/to/realflare/plugins/nuke')
```

### 2. NUKE_PATH

Append the absolute path to the `NUKE_PATH` environment variable, for example `/path/to/realflare/plugins/nuke`.

See [Defining the Nuke Plug-in Path](https://learn.foundry.com/nuke/content/comp_environment/configuring_nuke/defining_nuke_plugin_path.html)
for details.

### Binary location

The plugin looks for the `flare` binary in the following order:

1. The `REALFLARE_BIN` environment variable, if set.
2. A `venv` or `.venv` environment in the repository root (default installation).
3. The `PATH` environment variable.

## Usage

Once installed, a **Realflare** gizmo and menu are added to Nuke.
