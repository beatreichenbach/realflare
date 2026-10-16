# Contributing

## Development

To get started:

```sh
uv venv --python 3.13
uv pip install -e ".[dev]"
uv run pre-commit install
```

Run the checks:

```sh
uv run ruff format flare examples
uv run ruff check --select I --fix flare examples
uv run ruff check flare examples
uv run ty check flare examples
uv run pytest
```

To version up using [python-semantic-release](https://github.com/python-semantic-release/python-semantic-release):

```sh
uv run semantic-release version
```

## Project layout

```
flare/
  api/                 # domain (Project, Lens, Material, color, output paths)
  engine/              # OpenGL rendering engine
  adapters/            # adapters
    storage/           #   persistence gateways (project files, preferences/state)
    database/          #   optics database download and parsing
  services/            # application layer: project session, rendering
  ui/                  # Qt user interface
    widgets/           #   generic, reusable components (DockWindow, Viewer, ...)
    app/               #   components of this application (window, editors, dialogs)
  cli/                 # entrypoints (Typer commands, run_gui, run_render)
  utils/               # shared helpers (logging, text, profiling, path)
`tests/`               # automated test suite
`examples/`            # runnable scripts for visual and manual checks
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

| package    | may import                                             |
|------------|--------------------------------------------------------|
| `api`      | –                                                      |
| `utils`    | –                                                      |
| `adapters` | `api`, `utils`                                         |
| `engine`   | `api`, `adapters`, `utils`                             |
| `services` | `api`, `adapters`, `engine`, `utils`                   |
| `ui`       | `api`, `services`, `adapters`, `engine`, `utils`       |
| `cli`      | `api`, `services`, `adapters`, `engine`, `ui`, `utils` |

`tests/test_architecture.py` walks the import graph and fails when one of these
edges is violated. Keep it in sync when the layering changes.
