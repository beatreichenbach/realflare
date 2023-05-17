import logging
import os
import platform
import re
import subprocess
import sys
from importlib.metadata import version

import PyOpenColorIO
import pyopencl as cl

from realflare.api.tasks import opencl
from markdownTable import markdownTable

import realflare


def markdown_table(data: dict, headers: tuple[str, str]) -> str:
    if not data:
        return ''
    data_list = [
        {f' {headers[0]} ': f' {name} ', f' {headers[1]} ': f' {value} '}
        for name, value in data.items()
    ]
    table = (
        markdownTable(data_list)
        .setParams(
            row_sep='markdown',
            quote=False,
            padding_weight='right',
        )
        .getMarkdown()
    )
    return table


def build_report(args: list, output: str):

    # hardware
    queue = opencl.command_queue()
    device = queue.device

    hardware = {'processor': platform.processor(), 'OpenCL Device': device.name}

    for name in (
        'MAX_COMPUTE_UNITS',
        'MAX_WORK_GROUP_SIZE',
        'LOCAL_MEM_SIZE',
        'GLOBAL_MEM_SIZE',
        'MAX_CONSTANT_BUFFER_SIZE',
    ):
        parameter = getattr(cl.device_info, name)
        hardware[name] = device.get_info(parameter)

    hardware_table = markdown_table(hardware, ('Name', 'Value'))

    # software

    # using __version__ ensures the correct version for editable installs
    realflare_version = realflare.__version__
    software = {
        'platform': platform.platform(),
        'opencl': device.get_info(cl.device_info.OPENCL_C_VERSION),
        'python': platform.python_version(),
        'realflare': realflare_version,
        'qt_extensions': version('qt_extensions'),
        'pyopencl': version('pyopencl'),
        'numpy': version('numpy'),
        'PyOpenColorIO': PyOpenColorIO.__version__,
        'PySide2': version('PySide2'),
    }
    software_table = markdown_table(software, ('Name', 'Version'))

    # realflare
    project_path = args[-1]
    package_path = os.path.dirname(os.path.dirname(__file__))
    args[0] = os.path.relpath(args[0], package_path)
    args[-1] = os.path.relpath(args[-1], package_path)
    command = '`' + ' '.join(args) + '`'

    # score
    score = {}
    pattern = re.compile(r'([\w.]+):\s*(\d+(?:\.\d+)?ms)$')
    for line in output.split('\n'):
        match = pattern.search(line.strip())
        if match:
            func = match.group(1)
            time = match.group(2)
            if func == 'Engine.render':
                func = f'**{func}**'
                time = f'**{time}**'
            score[func] = time

    score_table = markdown_table(score, ('Function', 'Time'))

    fields = {
        'version': f'v{realflare_version}',
        'hardware_table': hardware_table,
        'software_table': software_table,
        'command': command,
        'score_table': score_table,
    }

    # read template
    template_path = os.path.join(os.path.dirname(__file__), 'report_template.md')
    with open(template_path, 'r') as f:
        report = f.read()

    # create text
    for key, value in fields.items():
        placeholder = f'<!--{key}-->'
        report = report.replace(placeholder, value)

    report_name = f'report_v{realflare_version}.md'
    project_dir = os.path.dirname(project_path)
    report_path = os.path.join(project_dir, report_name)
    with open(report_path, 'w') as f:
        f.write(report)


def run(name: str = 'nikon_ai_50_135mm'):

    # set environment variables
    env = os.environ.copy()
    if 'REALFLARE_DEV' in env:
        del env['REALFLARE_DEV']
    if 'REALFLARE_REBUILD' in env:
        del env['REALFLARE_REBUILD']

    project_path = os.path.join(os.path.dirname(__file__), name, 'project.json')

    command = [sys.executable, '-m', 'realflare', '--project', project_path]

    output = subprocess.check_output(command, env=env, stderr=subprocess.STDOUT)
    # process = processing.popen(command, env=env)
    # output = []
    # while process.poll() is None:
    #     output.append(process.stdout.readline())
    # process.stdout.close()
    #
    # return_code = process.returncode
    # if return_code:
    #     logging.error(subprocess.CalledProcessError(return_code, command))

    build_report(command, output.decode('utf-8'))
    # return return_code


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    run()
