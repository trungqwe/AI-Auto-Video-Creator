"""PostgreSQL adapters of module B ports (PERSIST-B, REQ-B-CONV-02)."""
from ingestion.persistence.repositories import (
    PostgresArticleRepository,
    PostgresEventRepository,
    PostgresRecordRepository,
    PostgresResolutionRepository,
    UnknownRecordKindError,
)
from ingestion.persistence.uow import (
    PostgresIngestionUnitOfWork,
    PostgresOutboxWriter,
)

__all__ = [
    "PostgresArticleRepository",
    "PostgresEventRepository",
    "PostgresIngestionUnitOfWork",
    "PostgresOutboxWriter",
    "PostgresRecordRepository",
    "PostgresResolutionRepository",
    "UnknownRecordKindError",
]
