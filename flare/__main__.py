import signal
import logging
from typing import Annotated, Optional
import os

# os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')
# os.environ.setdefault('PYOPENGL_PLATFORM', 'glx')


import typer
import flare
from flare import utils
from flare.cli import render, gui

signal.signal(signal.SIGINT, signal.SIG_DFL)

app = typer.Typer(add_completion=False)

app.command(name='render')(render)
app.command(name='gui')(gui)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: Annotated[
        Optional[int],
        typer.Option('--verbose', '-v', count=True),
    ] = None,
    version: Annotated[
        Optional[bool],
        typer.Option('--version', '-V'),
    ] = None,
):
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


if __name__ == '__main__':
    app()
