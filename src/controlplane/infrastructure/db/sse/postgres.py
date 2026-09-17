"""Caller-owned PostgreSQL connection, no implemented SSE read behavior."""


class PostgresSseReader:
    def __init__(self, connection: object) -> None:
        self._connection = connection

    def fetch_workspace_page(self, *, workspace_id: str, after_cursor: int,
                             limit: int = 100) -> object:
        raise NotImplementedError("P7B_SSE_WORKSPACE_PAGE_NOT_IMPLEMENTED")
