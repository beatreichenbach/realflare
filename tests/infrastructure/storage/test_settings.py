from pathlib import Path

import platformdirs
import pytest

from flare.infrastructure.storage import (
    Preferences,
    PreferencesManager,
    State,
    StateManager,
)


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the settings managers at an isolated temporary config directory."""

    monkeypatch.setattr(
        platformdirs, 'user_config_dir', lambda *args, **kwargs: str(tmp_path)
    )
    PreferencesManager.get.cache_clear()
    return tmp_path


def test_preferences_round_trip(config_dir: Path) -> None:
    preferences = Preferences(clear_log_on_render=False, check_updates=False)

    PreferencesManager.set(preferences)

    assert (config_dir / 'preferences.json').exists()
    assert PreferencesManager.get() == preferences


def test_state_round_trip(config_dir: Path) -> None:
    state = State(
        recent_paths=('/one.flare', '/two.flare'),
        last_update_check='2026-01-01T00:00:00Z',
    )

    StateManager.set(state)

    assert (config_dir / 'state.json').exists()
    assert StateManager.get() == state


def test_preferences_default(config_dir: Path) -> None:
    assert PreferencesManager.get() == Preferences()


def test_state_default(config_dir: Path) -> None:
    assert StateManager.get() == State()
