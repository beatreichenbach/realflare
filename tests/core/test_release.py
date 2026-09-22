import pytest

from flare.services.update import release


class Response:
    def __init__(self, data: dict) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return

    def json(self) -> dict:
        return self._data


def test_has_update() -> None:
    item = release.Release('v1.2.0', '1.2.0', '', '', '', '')
    assert release.has_update('1.0.0', item)
    assert not release.has_update('1.2.0', item)
    assert not release.has_update('2.0.0', item)
    assert not release.has_update('invalid', item)


def test_latest_release(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        'tag_name': 'v1.2.3',
        'html_url': 'https://example.com/release',
        'zipball_url': 'https://example.com/archive.zip',
        'body': 'notes',
        'published_at': '2026-01-01T00:00:00Z',
    }
    monkeypatch.setattr(release.requests, 'get', lambda *a, **k: Response(payload))

    item = release.latest_release()

    assert item is not None
    assert item.tag == 'v1.2.3'
    assert item.version == '1.2.3'
    assert item.page_url == 'https://example.com/release'
    assert item.zip_url == 'https://example.com/archive.zip'
    assert item.notes == 'notes'


def test_latest_release_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_error(*args: object, **kwargs: object) -> None:
        raise release.requests.RequestException('boom')

    monkeypatch.setattr(release.requests, 'get', raise_error)

    assert release.latest_release() is None
