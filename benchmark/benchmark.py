import os

import qt_extensions
import PySide2
import numpy
import pyopencl
import PyOpenColorIO


if 'REALFLARE_REBUILD' in os.environ:
    del os.environ['REALFLARE_REBUILD']


with open('/output/output.md', 'w') as f:
    f.write('hello')
