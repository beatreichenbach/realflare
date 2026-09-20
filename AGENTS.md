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
