'PostgreSQL adapters for the source ingestion ports (PERSIST-A).'
from source_ingestion.persistence.outbox import OutboxContext, PostgresSourceOutboxWriter
from source_ingestion.persistence.repositories import (
    PostgresCheckpointRepository,
    PostgresCollectionRunRepository,
    PostgresPackageRepository,
    PostgresReceiptStore,
    PostgresSourceCandidateRepository,
    PostgresSourceRepository,
)
from source_ingestion.persistence.unit_of_work import (
    PostgresSourceIngestionUnitOfWork,
    UnitOfWorkAlreadyActiveError,
    UnitOfWorkNotActiveError,
)

__all__ = [
    'OutboxContext',
    'PostgresCheckpointRepository',
    'PostgresCollectionRunRepository',
    'PostgresPackageRepository',
    'PostgresReceiptStore',
    'PostgresSourceCandidateRepository',
    'PostgresSourceIngestionUnitOfWork',
    'PostgresSourceOutboxWriter',
    'PostgresSourceRepository',
    'UnitOfWorkAlreadyActiveError',
    'UnitOfWorkNotActiveError',
]
