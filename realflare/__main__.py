import argparse
import logging
import sys

from realflare import sentry
from realflare.cli import app as cli_app
from realflare.gui import app as gui_app


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='Realflare',
        description='Physically-Based Lens Flares',
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
        help='the project to render, a path to a .json file',
    )
    parser.add_argument(
        '--animation',
        type=str,
        help='path to a .json file containing animation data',
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output image',
    )
    parser.add_argument(
        '--element',
        type=str,
        help='element to render, for example: '
        'STARBURST_APERTURE, STARBURST ... FLARE, FLARE_STARBURST',
    )
    parser.add_argument(
        '--colorspace',
        type=str,
        default='ACES - ACEScg',
        help='output colorspace',
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
    parser.add_argument(
        '--log',
        type=int,
        default=logging.WARNING,
        help='logging level',
    )
    return parser


def main() -> None:
    sentry.init()

    parser = argument_parser()
    args = parser.parse_args(sys.argv[1:])

    if args.gui:
        gui_app.exec_()
    else:
        cli_app.exec_(parser)


if __name__ == '__main__':
    main()
