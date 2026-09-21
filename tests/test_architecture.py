import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parent.parent / 'flare'

# Allowed intra-package imports per source package. Dependencies point inward:
# cli/ui -> services -> engine/infrastructure -> api/utils.
ALLOWED: dict[str, set[str]] = {
    'api': set(),
    'utils': set(),
    'infrastructure': {'api', 'utils'},
    'engine': {'api', 'infrastructure', 'utils'},
    'services': {'api', 'infrastructure', 'engine', 'utils'},
    'ui': {'api', 'services', 'infrastructure', 'engine', 'utils'},
    'cli': {'api', 'services', 'infrastructure', 'engine', 'ui', 'utils'},
}


def imported_packages(path: Path) -> set[str]:
    """Return the flare packages imported by a module."""

    tree = ast.parse(path.read_text())
    found: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ''
            if module == 'flare':
                found.update(alias.name.split('.')[0] for alias in node.names)
            elif module.startswith('flare.'):
                found.add(module.split('.')[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith('flare.'):
                    found.add(alias.name.split('.')[1])

    return {name for name in found if name in ALLOWED}


def source_package(path: Path) -> str | None:
    """Return the top-level package of a module, or None for root modules."""

    name = path.relative_to(PACKAGE).parts[0]
    return name if name in ALLOWED else None


@pytest.mark.parametrize('path', sorted(PACKAGE.rglob('*.py')), ids=str)
def test_import_boundaries(path: Path) -> None:
    source = source_package(path)
    if source is None:
        return

    for target in imported_packages(path):
        if target == source:
            continue
        assert target in ALLOWED[source], f'{source} must not import {target}: {path}'
