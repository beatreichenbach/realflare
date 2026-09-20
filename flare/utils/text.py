import re
from collections.abc import Sequence


def title(text: str) -> str:
    text = re.sub(r'([a-z0-9])([A-Z])', r'\g<1> \g<2>', text).replace('_', ' ').title()
    return text


def unique_name(name: str, existing_names: Sequence[str]) -> str:
    """Return a unique name."""

    for existing_name in existing_names:
        if name.casefold() == existing_name.casefold():
            match = re.search(r'(.*?)(\d+)$', name)
            if match:
                number = int(match.group(2))
                name = match.group(1)
            else:
                number = 0
            name = f'{name}{number + 1}'
            return unique_name(name, existing_names)
    return name


# def unique_path(path: str) -> str:
#     parent_path = os.path.dirname(path)
#     try:
#         items = os.listdir(parent_path)
#     except OSError:
#         return path
#
#     basename = os.path.basename(path)
#     name, ext = os.path.splitext(basename)
#     names = []
#     for item in items:
#         item_name, item_ext = os.path.splitext(item)
#         if ext == item_ext:
#             names.append(item_name)
#     basename = unique_name(name, names) + ext
#     path = os.path.join(parent_path, basename)
#     return path
