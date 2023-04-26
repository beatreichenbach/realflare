import argparse
import logging
import os
import sys

import sentry_sdk

from realflare.cli import app as cli_app
from realflare.gui import app as gui_app

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"


def parse_args(args):
    parser = argparse.ArgumentParser(
        description='Lens Flare',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '--gui',
        action='store_true',
        help='run the application in gui mode',
    )
    parser.add_argument(
        '--project',
        type=str,
        help='the project to render the flare, a path to a .json file',
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output image',
    )
    parser.add_argument(
        '--colorspace',
        type=str,
        default='ACES - ACEScg',
        help='output colorspace',
    )

    parser.add_argument(
        '--arg',
        type=str,
        metavar='ARG VALUE VALUE',
        action='append',
        help='argument being interpolated from frame-start to frame-end',
    )

    parser.add_argument(
        '--frame-start',
        type=int,
        default=1,
        help='start frame number',
    )
    parser.add_argument(
        '--frame-end',
        type=int,
        default=1,
        help='end frame number',
    )
    return parser.parse_args(args)


def main():
    environment = 'production'
    logging.getLogger().setLevel(logging.INFO)

    if os.getenv('REALFLARE_DEV'):
        environment = 'development'
        logging.getLogger().setLevel(logging.DEBUG)

    sentry_sdk.init(
        dsn="https://ca69319449554a2885eb98218ede9110@o4504738332016640.ingest.sentry.io/4504738333655040",
        traces_sample_rate=1.0,
        environment=environment,
    )

    parser = parse_args(sys.argv[1:])

    if parser.gui:
        gui_app.exec_()
    else:
        cli_app.exec_(parser)


if __name__ == '__main__':
    main()
