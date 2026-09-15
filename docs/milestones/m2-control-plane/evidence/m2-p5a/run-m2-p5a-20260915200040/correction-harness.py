import importlib.util
import sys
import uuid
from pathlib import Path
import pytest
from controlplane.domain.config_security import ConfigRevisionStatus
from controlplane.domain.concurrency import RevisionConflictError

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('correction_oracle', root / 'tests/m2/test_p5a_config_and_secrets.py')
oracle = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = oracle
spec.loader.exec_module(oracle)

@pytest.fixture
def database():
    with oracle._create_disposable_database(oracle.PRODUCTION_MIGRATIONS) as result:
        with result.connect() as connection:
            oracle._seed_workspaces(connection)
        yield result

def values():
    return dict(workspace_id=oracle.WORKSPACE_A, scope_kind='prompt', scope_key='correction', config_revision_number=1, payload={'enabled': True}, actor_ref='correction', change_reason='correction')

def test_correction_stale_cas_reports_persisted_current(database):
    with oracle._p5a_transaction_manager(database) as manager:
        service = oracle._config_revision_service()
        with manager.unit_of_work() as uow:
            stale = service.create_revision(**values(), connection=uow.connection)
        with manager.unit_of_work() as uow:
            published = service.transition(revision=stale, expected_revision=1, requested_status=ConfigRevisionStatus.PUBLISHED, actor_ref='correction', connection=uow.connection)
        with manager.unit_of_work() as uow:
            persisted = oracle._config_revision_repository().get_scoped(workspace_id=oracle.WORKSPACE_A, config_revision_id=stale.config_revision_id, connection=uow.connection)
            before = oracle._revision_snapshot(persisted)
            outbox_before = oracle._p5a_outbox_count(uow.connection, stale.config_revision_id)
            with pytest.raises(RevisionConflictError) as conflict:
                service.transition(revision=stale, expected_revision=0, requested_status=ConfigRevisionStatus.PUBLISHED, actor_ref='correction', connection=uow.connection)
            assert persisted.revision == published.revision == 2
            assert conflict.value.current_revision == persisted.revision
            after = oracle._config_revision_repository().get_scoped(workspace_id=oracle.WORKSPACE_A, config_revision_id=stale.config_revision_id, connection=uow.connection)
            assert oracle._revision_snapshot(after) == before
            assert oracle._p5a_outbox_count(uow.connection, stale.config_revision_id) == outbox_before

def test_correction_explicit_config_revision_id(database):
    identity = str(uuid.uuid4())
    with oracle._p5a_transaction_manager(database) as manager:
        with manager.unit_of_work() as uow:
            result = oracle._config_revision_service().create_revision(**values(), config_revision_id=identity, connection=uow.connection)
            assert result.config_revision_id == identity
        with manager.unit_of_work() as uow:
            persisted = oracle._config_revision_repository().get_scoped(workspace_id=oracle.WORKSPACE_A, config_revision_id=identity, connection=uow.connection)
            assert persisted is not None and persisted.config_revision_id == identity

def test_correction_explicit_secret_handle_id(database):
    identity = str(uuid.uuid4())
    with oracle._p5a_transaction_manager(database) as manager:
        with manager.unit_of_work() as uow:
            result = oracle._secret_handle_store().register(secret_handle_id=identity, workspace_id=oracle.WORKSPACE_A, provider_ref='vault', account_ref='account', alias_ref='alias', redacted_fingerprint_or_version='redacted', validation_status='VALID', audit_ref='correction', connection=uow.connection)
            assert result.secret_handle_id == identity
        with manager.unit_of_work() as uow:
            assert uow.connection.execute('SELECT secret_handle_id::text FROM controlplane.cp_secret_handles WHERE workspace_id=%s AND secret_handle_id=%s', (oracle.WORKSPACE_A, identity)).fetchone() == (identity,)
