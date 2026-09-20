class StateWidget:
    """Abstract Base Class for a widget that can save and load state."""

    def state(self) -> dict:
        return {}

    def set_state(self, state: dict) -> None:
        return
