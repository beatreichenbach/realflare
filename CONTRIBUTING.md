# Contributing

## Development

To get started:

```sh
uv venv --python 3.13
uv pip install -e ".[dev]"
pre-commit install
```

Run the checks:

```sh
uv run ruff format flare
uv run ruff check --select I --fix flare
uv run ruff check flare
uv run ty check flare
uv run pytest
```

## Project layout

```
flare/
  api/                 # engine-facing domain (Project, Lens, Material, color, output paths)
  engine/              # OpenGL rendering engine
  infrastructure/      # adapters to the outside world
    storage/           #   persistence gateways (project files, preferences/state)
    database/          #   optics database download and parsing
  services/            # application layer: project session, rendering, updates
  ui/                  # Qt user interface
    widgets/           #   generic, reusable components (DockWindow, Viewer, ...)
    app/               #   components of this application (window, editors, dialogs)
  cli/                 # entrypoints (Typer commands, run_gui, run_render)
  utils/               # shared helpers (logging, text, profiling, path)
```

Notes:

- `api` holds the data model that the engine consumes. It deliberately uses
  QtCore value types (via `qt_pydantic`) because they integrate with the
  parameter system.
- `ui/widgets` has no knowledge of the application. `ui/app` contains the
  application-specific views and wires them to the services.
- `cli` is lazy: the Typer commands only import GUI/engine/rendering modules
  inside the command functions.

## Layering

Dependencies point inward. A package may only import the packages listed for it:

| package          | may import                                                   |
|------------------|--------------------------------------------------------------|
| `api`            | –                                                            |
| `utils`          | –                                                            |
| `infrastructure` | `api`, `utils`                                               |
| `engine`         | `api`, `infrastructure`, `utils`                             |
| `services`       | `api`, `infrastructure`, `engine`, `utils`                   |
| `ui`             | `api`, `services`, `infrastructure`, `engine`, `utils`       |
| `cli`            | `api`, `services`, `infrastructure`, `engine`, `ui`, `utils` |

`tests/test_architecture.py` walks the import graph and fails when one of these
edges is violated. Keep it in sync when the layering changes.
