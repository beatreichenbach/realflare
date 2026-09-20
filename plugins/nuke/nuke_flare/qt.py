try:
    from PySide6 import QtCore as QtCore
except ImportError:
    from PySide2 import QtCore as QtCore  # ty: ignore[unresolved-import]
