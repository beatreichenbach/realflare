from typing import Any

from pydantic import BaseModel, Field


class Preferences(BaseModel):
    ocio: str = ''
    view_colorspace: str = ''
    clear_log_on_render: bool = True
    check_updates: bool = True


class State(BaseModel):
    main_window: dict[str, Any] = Field(default_factory=dict)
    widgets: dict[str, Any] = Field(default_factory=dict)
    recent_paths: tuple[str, ...] = ()
    last_update_check: str = ''
