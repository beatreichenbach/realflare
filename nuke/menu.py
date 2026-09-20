import nuke
import os

nuke.pluginAddPath(os.path.dirname(__file__))

menu = nuke.menu('Nodes').addMenu('Realflare', 'realflare.png')
menu.addCommand('Realflare', icon='Flare.png')

menu = nuke.menu('Nuke').menu('Render')
menu.addCommand(
    'Render selected Realflare Nodes',
    command='import flare_utils; flare_utils.render_selected()',
)
