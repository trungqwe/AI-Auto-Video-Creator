"""Unit of work of D over PostgreSQL: one pooled connection per transaction, shared by every repository and the outbox."""
from __future__ import annotations

import uuid
from typing import Any

from controlplane.domain.interfaces.uow import IUnitOfWork
from creative.adapters.batch_layout_usage import PostgresBatchLayoutUsage
from creative.persistence import repositories as repos
from creative.persistence.outbox import PostgresCreativeOutboxWriter


class TransactionNotActiveError(RuntimeError):
    pass


class TransactionAlreadyActiveError(RuntimeError):
    pass


class PostgresCreativeUnitOfWork(IUnitOfWork):
    """`manager` is the control plane TransactionManager; leaving the with-block without commit() rolls everything back."""

    def __init__(self, manager: Any, *, workspace_id: str, correlation_id: str = 'creative-persistence', actor: str = 'system:creative') -> None:
        if not isinstance(workspace_id, str):
            raise ValueError('workspace_id must be a UUID string')
        try:
            workspace = str(uuid.UUID(workspace_id))
        except ValueError:
            raise ValueError('workspace_id must be a UUID string') from None
        for name, value in (('correlation_id', correlation_id), ('actor', actor)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} must be a non-empty string')
        self._manager = manager
        self._context: Any = None
        self._connection: Any = None
        source = self._require_connection
        self.snapshots = repos.PostgresSnapshotRepository(source, workspace)
        self.analyses = repos.PostgresAnalysisRepository(source, workspace)
        self.angle_sets = repos.PostgresAngleSetRepository(source, workspace)
        self.scripts = repos.PostgresScriptRepository(source, workspace)
        self.plans = repos.PostgresPlanRepository(source, workspace)
        self.variant_validations = repos.PostgresVariantValidationRepository(source, workspace)
        self.output_metadata = repos.PostgresOutputMetadataRepository(source, workspace)
        self.invocations = repos.PostgresInvocationRecordRepository(source, workspace)
        self.receipts = repos.PostgresReceiptStore(source, workspace)
        self.outbox = PostgresCreativeOutboxWriter(source, workspace, correlation_id, actor)
        # PRS-LAYOUT-QUOTA-FIX1: the pipeline checks the batch layout cap again in the transaction that stores a plan.
        self.layout_usage = PostgresBatchLayoutUsage(source, workspace)

    @property
    def active(self) -> bool:
        return self._connection is not None

    def _require_connection(self) -> Any:
        if self._connection is None:
            raise TransactionNotActiveError('UOW_NOT_ACTIVE')
        return self._connection

    def begin(self) -> None:
        if self.active:
            raise TransactionAlreadyActiveError('UOW_ALREADY_ACTIVE')
        context = self._manager.borrow_connection()
        self._connection = context.__enter__()
        self._context = context

    def _finish(self, *, rollback: bool) -> None:
        connection, context = self._connection, self._context
        self._connection = None
        self._context = None
        try:
            if rollback:
                connection.rollback()
        finally:
            context.__exit__(None, None, None)

    def commit(self) -> None:
        connection = self._require_connection()
        try:
            connection.commit()
        except BaseException:
            self._finish(rollback=True)
            raise
        self._finish(rollback=False)

    def rollback(self) -> None:
        self._require_connection()
        self._finish(rollback=True)

    def __enter__(self):
        self.begin()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.active:
            self.rollback()