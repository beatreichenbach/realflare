import os


class File:
    """A hashable file on disk using the modification time for comparison."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._hash = hash((path, os.path.getmtime(path))) if os.path.exists(path) else 0

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.path!r})'

    def __str__(self) -> str:
        return self.path

    def __eq__(self, other: object) -> bool:
        if isinstance(other, File):
            return self._hash == other._hash
        return False

    def __hash__(self) -> int:
        return self._hash

    def __add__(self, other: str) -> str:
        return self.path + other
