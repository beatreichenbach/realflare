import hashlib
import os


class File:
    # A File object as a snapshot in time. It is used to check if the file
    # at the time of creation is the same as the file on disk now.

    def __init__(self, path: str):
        self.path = path
        self.mtime = os.path.getmtime(path)
        hasher = hashlib.sha256()
        hasher.update((str(self.mtime) + path).encode('utf-8'))
        self._hash = int.from_bytes(hasher.digest(), 'big')

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
