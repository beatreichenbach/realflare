import os

try:
    from ._version import __version__
except ImportError:
    pass

os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '1'
