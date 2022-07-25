import logging
import sys

from realflare.__main__ import parse_args
from realflare.cli import app as cli_app

logging.getLogger().setLevel(logging.DEBUG)


def test_cli_app():
    parser = parse_args(
        [
            '--frame-start',
            '1',
            '--frame-end',
            '1',
            '--project',
            r'C:\Users\Beat\.realflare\project.json',
            '--arg',
            'flare.light_position [-0.56,0.38] [0.1,-0.2]',
            '--output',
            'D:/files/dev/027_flare/render/nikon_v002/render.$F4.exr',
        ]
    )
    cli_app.exec_(parser)


test_cli_app()
