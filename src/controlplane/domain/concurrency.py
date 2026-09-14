"""Pure revision-conflict semantics shared by domain and application ports."""


class RevisionConflictError(Exception):
    """Raised when a mutation is attempted against a stale aggregate revision."""

    def __init__(self, current_revision: int) -> None:
        super().__init__(f"Revision conflict; current revision is {current_revision}.")
        self.current_revision = current_revision
