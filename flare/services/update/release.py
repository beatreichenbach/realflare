import dataclasses
import logging

import requests
from packaging.version import InvalidVersion, Version

logger = logging.getLogger(__name__)

REPOSITORY = 'beatreichenbach/realflare'
RELEASES_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
TIMEOUT = 10


@dataclasses.dataclass(frozen=True)
class Release:
    tag: str
    version: str
    page_url: str
    zip_url: str
    notes: str
    published: str

    def __str__(self) -> str:
        return self.version


def latest_release() -> Release | None:
    """Return the latest release, or None if it could not be retrieved."""

    try:
        response = requests.get(RELEASES_URL, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        logger.error(f'Could not check for updates: {e}')
        return None

    tag = data.get('tag_name', '')
    return Release(
        tag=tag,
        version=tag.lstrip('v'),
        page_url=data.get('html_url', ''),
        zip_url=data.get('zipball_url', ''),
        notes=data.get('body') or '',
        published=data.get('published_at', ''),
    )


def has_update(version: str, release: Release) -> bool:
    """Return whether a release is newer than an installed version."""

    try:
        return Version(release.version) > Version(version)
    except InvalidVersion:
        return False
