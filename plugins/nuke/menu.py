import logging
import os

import nuke

logger = logging.getLogger(__name__)


def setup() -> None:
    """Add the Realflare menus to Nuke."""

    nuke.pluginAddPath(os.path.dirname(__file__))

    nodes_menu = nuke.menu('Nodes')
    realflare_menu = nodes_menu.addMenu('Realflare', 'realflare.png')
    realflare_menu.addCommand('Realflare', icon='Flare.png')

    render_menu = nuke.menu('Nuke').menu('Render')
    if render_menu is not None:
        render_menu.addCommand(
            'Render selected Realflare Nodes',
            command='import nuke_flare; nuke_flare.render_selected()',
        )


try:
    setup()
except Exception as e:
    logger.error('Failed to load Realflare', exc_info=e)
