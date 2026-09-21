# AGENTS.md

Python docstrings, formatting, type hints, errors, and verification follow the
global opencode skills: `python-docstrings`, `python-type-hints`, and
`python-conventions`.

## Task docstrings

1. Task class docstrings explain the science, not the code. The docstring
   lives on the class because it describes the whole task.
2. Keep it short and structured, not a wall of text. Start with one summary
   sentence stating what the task produces, then explain the details with
   short paragraphs, bullet points, or a numbered list of steps.
3. Describe what physical or optical process this task simulates, why it is
   modeled this way, and which approximations are made. Do not restate the
   Python or GLSL mechanics unless needed to understand the science. State
   the "why" for non-obvious choices (e.g. why Fraunhofer instead of Fresnel,
   why the pattern scales with wavelength and f-number).
4. Cite the sources the implementation follows. Cite papers with author and
   year and, where useful, section or equation. Link GitHub repos with the
   full URL.
5. If part of the physics or intent is unclear, ask the user instead of
   inventing a justification.

Example:
```python
class StarburstTask(OpenGLTask):
   """
   This task ...

   Steps:

   1. ...
   2. ...

   References:
   Ritschel et al. 2009, Sec. 4.
   https://github.com/...
   """
```
