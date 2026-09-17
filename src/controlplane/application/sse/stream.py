"""Explicitly absent SSE replay and cursor-classification capabilities."""


class SseStreamService:
    def __init__(self, reader: object) -> None:
        self._reader = reader

    def replay_after(self, *, workspace_id: str, cursor: int) -> object:
        raise NotImplementedError("P7B_SSE_REPLAY_NOT_IMPLEMENTED")

    def classify_cursor(self, *, workspace_id: str, cursor: int) -> object:
        raise NotImplementedError("P7B_SSE_CURSOR_CLASSIFICATION_NOT_IMPLEMENTED")
