import logging

from ..base import Array, Task

logger = logging.getLogger(__name__)


class CompTask(Task):
    @staticmethod
    def run(flare: Array, starburst: Array) -> Array:
        array = flare.array + starburst.array
        image = Array(array=array, args=(flare, starburst))
        return image
