from pydantic import BaseModel, Field


class Preferences(BaseModel):
    ocio: str = ''
    view_colorspace: str = ''
    clear_log_on_render: bool = True


class State(BaseModel):
    main_window: dict = Field(default_factory=dict)
    widgets: dict = Field(default_factory=dict)
    recent_paths: tuple[str, ...] = ()
