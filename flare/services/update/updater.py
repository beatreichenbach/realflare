"""
Standalone updater that runs after the main application exits.

This script is copied to a temporary location and launched with the virtual
environment's Python. It only uses the standard library so it can run while the
``flare`` package is being replaced.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from contextlib import suppress
from pathlib import Path

logger = logging.getLogger('flare.update')

PRESERVE = {'flare', '.venv', '.git', 'custom', 'render', '.flare-backup'}


def main() -> None:
    plan_path = Path(sys.argv[1])
    plan = json.loads(plan_path.read_text())
    configure_logging(Path(plan['log']))

    try:
        wait_for_exit(int(plan['pid']))
        if plan['mode'] == 'git':
            apply_git(plan)
        else:
            apply_zip(plan)
        reinstall(Path(plan['root']))
        logger.info('Update complete.')
    except Exception:
        logger.exception('Update failed.')

    relaunch(list(plan.get('args') or []))
    plan_path.unlink(missing_ok=True)


def configure_logging(path: Path) -> None:
    """Log to a file and to stderr."""

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    with suppress(OSError):
        handlers.append(logging.FileHandler(path))

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=handlers,
        force=True,
    )


def wait_for_exit(pid: int) -> None:
    """Block until the process with a pid has exited."""

    if sys.platform == 'win32':
        wait_for_exit_windows(pid)
        return

    while pid_alive(pid):
        time.sleep(0.2)


def wait_for_exit_windows(pid: int) -> None:
    """Block until a Windows process has exited using its process handle."""

    import ctypes

    windll = getattr(ctypes, 'windll', None)
    if windll is None:
        return

    synchronize = 0x00100000
    infinite = 0xFFFFFFFF
    handle = windll.kernel32.OpenProcess(synchronize, False, pid)
    if handle:
        windll.kernel32.WaitForSingleObject(handle, infinite)
        windll.kernel32.CloseHandle(handle)


def pid_alive(pid: int) -> bool:
    """Return whether a process is still running."""

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def apply_git(plan: dict) -> None:
    """Update a git checkout to a release tag."""

    root = plan['root']
    tag = plan['tag']

    if run(['git', '-C', root, 'status', '--porcelain']).stdout.strip():
        raise RuntimeError('the git working tree is not clean')

    run(['git', '-C', root, 'fetch', '--tags', '--force'])
    run(['git', '-C', root, 'checkout', f'tags/{tag}'])


def apply_zip(plan: dict) -> None:
    """Overwrite the source tree with the files of a release archive."""

    root = Path(plan['root'])
    archive = download(plan['zip_url'])
    staging = make_staging(root)
    source = extract(archive, staging)
    archive.unlink(missing_ok=True)
    validate(source)

    backup = root / '.flare-backup'
    shutil.rmtree(backup, ignore_errors=True)
    shutil.move(str(root / 'flare'), str(backup))

    try:
        shutil.move(str(source / 'flare'), str(root / 'flare'))
        overlay(source, root)
    except Exception:
        shutil.rmtree(root / 'flare', ignore_errors=True)
        shutil.move(str(backup), str(root / 'flare'))
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    shutil.rmtree(backup, ignore_errors=True)


def download(url: str) -> Path:
    """Download a file and return its temporary path."""

    logger.info(f'Downloading: {url}')
    descriptor, name = tempfile.mkstemp(prefix='flare_update_', suffix='.zip')
    with (
        os.fdopen(descriptor, 'wb') as target,
        urllib.request.urlopen(url, timeout=60) as response,
    ):
        shutil.copyfileobj(response, target)
    return Path(name)


def make_staging(root: Path) -> Path:
    """Return a staging directory next to the source tree."""

    try:
        return Path(tempfile.mkdtemp(prefix='flare_update_', dir=str(root.parent)))
    except OSError:
        return Path(tempfile.mkdtemp(prefix='flare_update_'))


def extract(archive: Path, destination: Path) -> Path:
    """Extract an archive and return its top level directory."""

    logger.info(f'Extracting: {archive}')
    with zipfile.ZipFile(archive) as file:
        file.extractall(destination)

    for entry in destination.iterdir():
        if entry.is_dir():
            return entry
    raise RuntimeError('the archive is empty')


def validate(source: Path) -> None:
    """Raise if a source tree is not a valid flare checkout."""

    if not (source / 'flare').is_dir() or not (source / 'pyproject.toml').exists():
        raise RuntimeError('the archive does not contain a flare source tree')


def overlay(source: Path, root: Path) -> None:
    """Copy top level files from a source tree into an install directory."""

    for entry in source.iterdir():
        if entry.name in PRESERVE:
            continue
        target = root / entry.name
        if entry.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(entry, target)
        else:
            shutil.copy2(entry, target)


def reinstall(root: Path) -> None:
    """Reinstall the package editable, bootstrapping pip if necessary."""

    python = sys.executable
    if run([python, '-m', 'pip', '--version'], check=False).returncode != 0:
        run([python, '-m', 'ensurepip', '--upgrade'])
    run([python, '-m', 'pip', 'install', '-e', str(root)])


def relaunch(args: list[str]) -> None:
    """Relaunch the graphical application."""

    command = [sys.executable, '-m', 'flare', *(args or ['gui'])]
    logger.info(f'Relaunching: {" ".join(command)}')
    if sys.platform == 'win32':
        subprocess.Popen(command, creationflags=detach_flags())
    else:
        subprocess.Popen(command, start_new_session=True)


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the completed process."""

    logger.info(f'Running: {" ".join(command)}')
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stdout.strip():
        logger.info(result.stdout.strip())
    if result.stderr.strip():
        logger.info(result.stderr.strip())
    if check and result.returncode != 0:
        raise RuntimeError(f'command failed ({result.returncode}): {command[0]}')
    return result


def detach_flags() -> int:
    """Return Windows creation flags to detach a process."""

    flags = getattr(subprocess, 'DETACHED_PROCESS', 0)
    flags |= getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    return flags


if __name__ == '__main__':
    main()
