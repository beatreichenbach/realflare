import glob
import os
from importlib.metadata import version


def latest_project() -> str | None:
    project_path = os.path.dirname(__file__)
    files = glob.glob(os.path.join(project_path, 'benchmark*.json'))
    if files:
        project = sorted(files)[-1]
        return project


def hardware_specs():
    # should be queried from opencl
    pass


def run():
    if 'REALFLARE_REBUILD' in os.environ:
        del os.environ['REALFLARE_REBUILD']

    versions = {
        'realflare': version('realflare'),
        'qt_extensions': version('qt_extensions'),
        'PySide2': version('PySide2'),
        'numpy': version('numpy'),
        'pyopencl': version('pyopencl'),
        'PyOpenColorIO': version('PyOpenColorIO'),
    }

    with open('/output/output.md', 'w') as f:
        f.write('hello')
