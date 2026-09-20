from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from qtpy import QtGui

from flare import api


class EngineError(Exception):
    """An exception that allows passing a log message to the user."""

    def __init__(self, message: str = '', log: str = '') -> None:
        super().__init__(message)
        self.log = log


class Array:
    """
    Hashable Array
    This is a wrapper around a numpy array which stores a hash to quickly compare
    numpy arrays.
    """

    def __init__(self, array: np.ndarray, args: Any = None) -> None:
        self._hash = None
        self.array = array
        self.args = args

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(self.args)
        return self._hash

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Array) and self._hash == other._hash

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.array.shape if self.array is not None else None})'

    @property
    def args(self) -> Any:
        return self._args

    @args.setter
    def args(self, args: Any) -> None:
        self._hash = None
        self._args = args


class Task:
    def cleanup(self) -> None: ...


class Renderer(ABC):
    def __init__(self, context: QtGui.QOpenGLContext) -> None:
        self.context = context

    @abstractmethod
    def run(self, project: api.Project) -> Array: ...


class Output(ABC):
    @abstractmethod
    def write(self, image: Array, project: api.Project) -> str:
        """Write a Render to disk based on the Project's output values."""
        ...
