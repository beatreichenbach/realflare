import logging
import time
import tracemalloc
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


def timer(func) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        with Timer(func.__qualname__):
            return func(*args, **kwargs)

    return wrapper


class Timer:
    def __init__(self, name: str = '') -> None:
        self.name = name

    def __enter__(self) -> None:
        self.start_time = time.perf_counter()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        ms = (time.perf_counter() - self.start_time) * 1000
        label = f'{self.name} (Time):'
        logger.debug(f'{label: <40}{ms:9.3f} ms')


def memory(func) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        with Memory(func.__qualname__):
            return func(*args, **kwargs)

    return wrapper


class Memory:
    def __init__(self, name: str = '') -> None:
        self.name = name

    def __enter__(self) -> None:
        tracemalloc.start()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mem = peak / 1024**2
        label = f'{self.name} (Peak Memory):'
        logger.debug(f'{label: <40}{mem:9.3f} MB')
