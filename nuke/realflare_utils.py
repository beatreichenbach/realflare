import glob
import os.path
import platform
import re
import subprocess

import nuke

from realflare_setup import Setup

try:
    import realflare
except (ModuleNotFoundError, ImportError):
    setup = Setup()
    # install realflare first time
    if not os.path.exists(setup.venv_path):
        task = nuke.ProgressTask('Installing Realflare')
        task.setMessage('Check the console for more information.')
        task.setProgress(0)
        setup.run()
        task.setProgress(100)
        del task
    lib_path = setup.lib_path
    lib_path = lib_path.replace('\\', '/')
    if lib_path not in nuke.pluginPath():
        nuke.pluginAddPath(lib_path)

from realflare.gui import app as gui_app
from realflare.storage import Storage

storage = Storage()


def open_app():
    node = nuke.thisNode()
    project_path = node.knob('project').value()
    gui_app.init_window(project_path)


def export_animation(
    node: nuke.Node, path: str, frame_start: int, frame_end: int
) -> None:
    # project
    project = {}

    # resolution
    width = node.width()
    height = node.height()
    project['render'] = {'resolution': [(width, height)]}

    # flare
    project['flare'] = {}

    # light
    light = {}
    use_image = node.knob('use_image').value()
    if use_image:
        light['image_file_enabled'] = True
        file = node.knob('image').getValue()
        light['image_file'] = [file]
    else:
        light['position'] = []
        for frame in range(frame_start, frame_end + 1):
            position = node.knob('position').getValueAt(frame)
            x = (position[0] / width) * 2 - 1
            y = (position[1] / height) * 2 - 1
            light['position'].append((x, y))
    project['flare']['light'] = light

    storage.write_data(project, path)


def frame_range_from_path(file_path: str) -> tuple[int, int]:
    pattern = file_path
    pattern = pattern.replace('#', '?')
    pattern = re.sub(
        r'%0(\d)d',
        lambda m: int(m.group(1)) * '?' if m.group(1) else '',
        pattern,
    )

    files = glob.glob(pattern)
    files.sort()

    frame_range = [1, 1]
    if files:
        for i, index in enumerate((0, -1)):
            characters = [s for j, s in enumerate(files[index]) if s != pattern[j]]
            try:
                frame_range[i] = int(''.join(characters))
            except ValueError:
                pass
    return (frame_range[0], frame_range[1])


def reload() -> None:
    node = nuke.thisNode()
    for read in nuke.allNodes('Read', node):
        read.knob('reload').execute()


def run(
    project_path: str,
    animation_path: str,
    output_path: str,
    element: str,
    colorspace: str,
    frame_start: int,
    frame_end: int,
) -> None:
    setup = Setup()
    executable = setup.executable
    cmd = (
        f'"{executable}" -m realflare '
        f'--project "{project_path}" --animation "{animation_path}" '
        f'--output "{output_path}" --element {element} --colorspace "{colorspace}" '
        f'--frame-start {frame_start} --frame-end {frame_end} --log 20'
    )
    print(cmd)

    kwargs = {}
    if platform.system() == 'Windows':
        kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE

    subprocess.run(cmd, **kwargs)


def render():
    node = nuke.thisNode()

    project_path = node.knob('project').value()
    start = int(node.knob('frame_start').value())
    end = int(node.knob('frame_end').value())
    output_path = node.knob('file').value()
    colorspace = node.knob('render_colorspace').value()
    element = node.knob('element').value()

    if not project_path:
        nuke.message('Project cannot be empty.')
        return

    if not output_path:
        nuke.message('File cannot be empty.')
        return

    # animation path
    filename = os.path.basename(project_path)
    words = filename.split('.')
    words.insert(-1, 'animation')
    filename = '.'.join(words)
    animation_path = os.path.join(os.path.dirname(project_path), filename)

    export_animation(node, animation_path, start, end)

    run(project_path, animation_path, output_path, element, colorspace, start, end)

    if not node.knob('lock_colorspace').value():
        node.knob('colorspace').setValue(colorspace)

    if not node.knob('lock_frame_range').value():
        words = os.path.basename(output_path).split('.')
        words.insert(1, 'flare')
        flare_path = os.path.join(os.path.dirname(output_path), '.'.join(words))

        words = os.path.basename(output_path).split('.')
        words.insert(1, 'starburst')
        starburst_path = os.path.join(os.path.dirname(output_path), '.'.join(words))

        first = 1
        last = 1
        for path in (output_path, flare_path, starburst_path):
            frame_range = frame_range_from_path(path)
            first = min(first, frame_range[0])
            last = max(last, frame_range[1])
        node.knob('first').setValue(first)
        node.knob('last').setValue(last)
