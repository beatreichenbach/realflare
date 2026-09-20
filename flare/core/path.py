import os
import re


class PathParser:
    @staticmethod
    def format_path(path: str, frame: int) -> str:
        """Format a path."""

        if path:
            path = re.sub(r'\$F(\d)?', r'{:0\g<1>d}', path)
            path = re.sub(r'%0(\d)d', r'{:0\g<1>d}', path)
            path = re.sub(r'#+', lambda m: fr'{{:0{len(m.group(0))}d}}', path)
            path = path.format(frame)

            path = os.path.abspath(path)
        return path
