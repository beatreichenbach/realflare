from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar('T')


class Parser(ABC, Generic[T]):
    supported_extensions: tuple[str, ...]

    @abstractmethod
    def parse(self, path: str) -> T | None: ...
