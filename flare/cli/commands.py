import logging
from typing import Annotated

import typer

logger = logging.getLogger(__name__)


def render(
    project_path: Annotated[str, typer.Option('--project', '-p')],
    animation_path: Annotated[str, typer.Option('--animation', '-a')],
    output: Annotated[str, typer.Option('--output', '-o')],
) -> None:
    """Render an animation to disk."""

    from flare.cli.render import run_render

    try:
        run_render(project_path, animation_path, output)
    except KeyboardInterrupt:
        logger.warning('Render interrupted by user')
        raise typer.Exit(130) from None
    except Exception as e:
        logger.error('Failed to render project', exc_info=e)
        raise typer.Exit(1) from e


def gui(
    project_path: Annotated[str, typer.Option('--project', '-p')] = '',
) -> None:
    """Show the graphical user interface."""

    from flare.cli.gui import run_gui

    run_gui(project_path)
