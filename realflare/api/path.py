import os


class File:
    # A File object as a snapshot in time. It is used to check if the file
    # at the time of creation is the same as the file on disk now.

    def __init__(self, path: str):
        self.path = path
        self._hash = hash((path, os.path.getmtime(path)))

    def __add__(self, other):
        self.path += other

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return self._hash

    def __repr__(self):
        return f"File('{self.path}')"

    def __str__(self):
        return self.path
