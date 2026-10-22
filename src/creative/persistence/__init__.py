"""PostgreSQL adapters of the creative bounded context (module D): repositories, receipt store, outbox writer and unit of work over the 0015_creative tables."""

from creative.persistence.outbox import PostgresCreativeOutboxWriter
from creative.persistence.repositories import (
    PostgresAnalysisRepository,
    PostgresAngleSetRepository,
    PostgresAppendOnlyRepository,
    PostgresInvocationRecordRepository,
    PostgresOutputMetadataRepository,
    PostgresPlanRepository,
    PostgresReceiptStore,
    PostgresScriptRepository,
    PostgresSnapshotRepository,
    PostgresVariantValidationRepository,
)
from creative.persistence.uow import (
    PostgresCreativeUnitOfWork,
    TransactionAlreadyActiveError,
    TransactionNotActiveError,
)

__all__ = [
    'PostgresAnalysisRepository',
    'PostgresAngleSetRepository',
    'PostgresAppendOnlyRepository',
    'PostgresCreativeOutboxWriter',
    'PostgresCreativeUnitOfWork',
    'PostgresInvocationRecordRepository',
    'PostgresOutputMetadataRepository',
    'PostgresPlanRepository',
    'PostgresReceiptStore',
    'PostgresScriptRepository',
    'PostgresSnapshotRepository',
    'PostgresVariantValidationRepository',
    'TransactionAlreadyActiveError',
    'TransactionNotActiveError',
]