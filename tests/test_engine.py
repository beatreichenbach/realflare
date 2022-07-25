import logging

from realflare.api import data
from realflare.api.data import RenderElement
from realflare.api.engine import Engine


def test_engine():
    engine = Engine()
    flare_config = data.Flare()
    flare_config.starburst.aperture.file = (
        r'D:\files\dev\027_flare\realflare\library\apertures\hexagon_scratch.png'
    )
    render_config = data.Render()
    outputs = [RenderElement.STARBURST_APERTURE]
    engine.render(flare_config, render_config, outputs)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    test_engine()
