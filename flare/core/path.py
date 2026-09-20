import os
import re


class PathParser:
    @staticmethod
    def format_path(path: str, frame: int) -> str:
        """
        Return an absolute path with frame patterns replaced.
        Accepted frame patterns: $F4, %04d, ####
        """

        if path:
            path = re.sub(r'\$F(\d)?', r'{:0\g<1>d}', path)
            path = re.sub(r'%0(\d)d', r'{:0\g<1>d}', path)
            path = re.sub(r'#+', lambda m: rf'{{:0{len(m.group(0))}d}}', path)
            path = path.format(frame)

            path = os.path.abspath(path)
        return path
