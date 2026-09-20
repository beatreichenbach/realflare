from typing import Any

import numpy as np


class HashableArray:
    def __init__(self, array: np.ndarray, args: tuple):
        self._array = array
        self._hash = None
        self.args = args

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(self.args)
        return self._hash

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, HashableArray) and self.args == other.args

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._array, attr)

    # Python looks up these attributes on the class

    def __array__(self) -> np.ndarray:
        return self._array

    def __getitem__(self, key) -> Any:
        return self._array.__getitem__(key)


class Image:
    def __init__(self, array: np.ndarray, args: Any) -> None:
        self._hash = None
        self.array = array
        self.args = args

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(self.args)
        return self._hash

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Image) and self.args == other.args
