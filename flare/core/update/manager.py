import dataclasses
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

import platformdirs

import flare
from flare.core.update.release import Release

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class UpdatePlan:
    mode: str
    root: Path
    release: Release
    script: Path
    log: Path


def install_root() -> Path | None:
    """Return the source directory of an editable install, or None."""

    root = Path(flare.__file__).resolve().parent.parent
    if (root / 'pyproject.toml').exists():
        return root
    return None


def is_git(root: Path) -> bool:
    """Return whether a source directory is a git checkout."""

    return (root / '.git').exists() and shutil.which('git') is not None


def build_plan(release: Release) -> UpdatePlan | None:
    """Return an UpdatePlan for a release, or None if updating is not possible."""

    root = install_root()
    if root is None:
        logger.error('Cannot update: could not locate the install directory.')
        return None

    if not os.access(root, os.W_OK):
        logger.error(f'Cannot update: no write access to {root}.')
        return None

    mode = 'git' if is_git(root) else 'zip'
    return UpdatePlan(
        mode=mode,
        root=root,
        release=release,
        script=_write_script(),
        log=_log_path(),
    )


def spawn(plan: UpdatePlan, args: Sequence[str] = ()) -> None:
    """Run the updater detached so it can update after this process exits."""

    payload = {
        'pid': os.getpid(),
        'mode': plan.mode,
        'root': str(plan.root),
        'tag': plan.release.tag,
        'zip_url': plan.release.zip_url,
        'page_url': plan.release.page_url,
        'log': str(plan.log),
        'args': list(args),
    }

    descriptor, name = tempfile.mkstemp(prefix='flare_update_', suffix='.json')
    with os.fdopen(descriptor, 'w') as file:
        json.dump(payload, file)

    command = [sys.executable, str(plan.script), name]
    if sys.platform == 'win32':
        subprocess.Popen(command, creationflags=_detach_flags())
    else:
        subprocess.Popen(command, start_new_session=True)
    logger.info(f'Started updater for {plan.release.version}.')


def _write_script() -> Path:
    """Copy the standalone updater script to a temporary location."""

    source = Path(__file__).parent / 'updater.py'
    descriptor, name = tempfile.mkstemp(prefix='flare_updater_', suffix='.py')
    os.close(descriptor)

    target = Path(name)
    shutil.copyfile(source, target)
    return target


def _log_path() -> Path:
    """Return the path of the updater log file."""

    directory = Path(platformdirs.user_log_dir(flare.__name__))
    directory.mkdir(parents=True, exist_ok=True)
    return directory / 'update.log'


def _detach_flags() -> int:
    """Return Windows creation flags to detach the updater process."""

    flags = getattr(subprocess, 'DETACHED_PROCESS', 0)
    flags |= getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    return flags
