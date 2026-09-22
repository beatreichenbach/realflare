import logging
import signal
from typing import Annotated

import typer

import flare
from flare import utils

from .commands import gui, render, report

signal.signal(signal.SIGINT, signal.SIG_DFL)

app = typer.Typer(add_completion=False)

app.command(name='render')(render)
app.command(name='gui')(gui)
app.command(name='report')(report)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: Annotated[int | None, typer.Option('--verbose', '-v', count=True)] = None,
    version: Annotated[bool | None, typer.Option('--version', '-V')] = None,
) -> None:
    utils.init_logging()
    utils.init_rich()

    if verbose == 1:
        logging.getLogger(flare.__name__).setLevel(logging.INFO)
    elif verbose == 2:
        logging.getLogger(flare.__name__).setLevel(logging.DEBUG)
    elif verbose == 3:
        logging.getLogger().setLevel(logging.DEBUG)

    if version:
        from flare import constants

        print(f'{constants.NAME.title()} Version: {flare.__version__}')
        raise typer.Exit()

    if not ctx.invoked_subcommand:
        pass
