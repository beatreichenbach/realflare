# AGENTS.md

## Docstrings

Do not add docstrings by default. Only add one where it adds value beyond
the name and type hints. Self-explanatory functions, and especially
self-explanatory classes, must NOT have a docstring.

### Formatting

1. Always leave a blank line after a docstring before code.
2. Single-line docstrings stay on one line:
   ```python
   def get_renderer(layer: Layer) -> Renderer:
       """Return the renderer for a layer."""

       ...
   ```
3. Multi-line docstrings: first and last lines contain only `"""`:
   ```python
   def fresnel_diffraction(
       aperture: np.ndarray, wavelength: float, distance: float, size: float
   ) -> np.ndarray:
       """
       Return the near-field Fresnel diffraction using the Angular Spectrum Method.
       """
   ```
   Do not write `"""Summary...` or `..."""` on the same line as text.

### Content

1. Write in imperative mood: `Return`, `Update`, `Run`, `Render`, `Compute`, not `Returns`, `Updates`, `This function renders`.
2. Functions that return something start the docstring with `Return ...`.
   Functions that return `None` start with a verb describing the side effect, e.g. `Update ...`, `Run ...`, `Render ...`.
3. Never use `:param:`, `:type:`, `:return:`, or `:rtype:`. Parameters and return values are documented by type hints and must be fully annotated.
4. Use `:raises ...:` if the function raises, with a trailing period:
   ```python
   def get_renderer(layer: Layer) -> Renderer:
       """
       Return the renderer for a layer.

       :raises ValueError: if no renderer exists for the layer.
       """

       ...
   ```

## Package imports / exports

1. Every `__init__.py` that re-exports names must define `__all__` listing
   exactly the public names. Keep re-exports and `__all__` in sync.

## Type hints

1. Fully annotate all parameters and return values, including `-> None`
   and dunders (`__eq__(self, other: object) -> bool`,
   `__hash__(self) -> int`). Never leave a parameter unannotated.
2. Never use bare generics: `dict[str, Any]`, not `dict`;
   `tuple[Any, ...]`, not `tuple`.
3. Use `object` when accepting anything and narrowing with `isinstance`
   (e.g. `__eq__`). Use `Any` only for dynamic passthrough
   (e.g. delegating `__getattr__` / `__getitem__` to numpy).

## Errors

1. Exception messages are lowercase: they are read by developers in
   tracebacks and often composed into larger messages.
2. Log messages shown to the user are capitalized sentences, e.g.
   `logger.error(f'Could not read file: {path}')`.
3. Log once, at the boundary: library code raises, the CLI/UI layer logs.
   Never log an error you also raise — it double-reports.

## Verification

After a change, format the touched files with ruff, e.g.
`uv run ruff format flare/core`. Ruff format does not sort imports,
so also run `uv run ruff check --select I --fix flare/core`.
Then run the scoped type check for the touched package,
e.g. `uv run ty check flare/core`. Do not run unrelated suites
unless asked.
