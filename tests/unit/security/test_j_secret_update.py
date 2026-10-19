"""J-10: UpdateSecret write-only and SecretStorePort (CT-SEC-001, INV-012).

coveredIds: CT-SEC-001, TST-SEC-INV-012, QR-SEC-001, QR-SEC-003
"""
import dataclasses
import traceback
from datetime import datetime, timezone

import pytest

from controlplane.application.config_security.secret_update import (
    SecretStorePort, SecretUpdateError, SecretUpdateReceipt, UpdateSecretService,
)
from controlplane.infrastructure.security.secret_redaction import SecretValue, find_canaries

C_VALUE = 'CANARY-J10-VALUE-a1b2qzxw'
C_TAIL = C_VALUE[-4:]
C_PASSWORD = 'CANARY-J10-PASSWORD-77d0e1'
LEAK_CANARIES = [C_VALUE, C_TAIL, C_PASSWORD]
NOW = datetime(2026, 10, 20, 1, 2, 3, tzinfo=timezone.utc)
REF = 'ws-1/acct-1/primary'
RECEIPT_FIELDS = ['secret_ref', 'account_ref', 'alias_ref', 'version', 'fingerprint', 'last_updated_at', 'validation_state', 'actor_ref']
_UNSET = object()


class FakeSecretStore:
    def __init__(self, put_error=None, current_error=None, put_result=_UNSET):
        self.put_error = put_error
        self.current_error = current_error
        self.put_result = put_result
        self.versions = {}
        self.stored_values = []
        self.puts = []
        self.revoked = []

    def put(self, secret_ref, value):
        if self.put_error is not None:
            raise self.put_error
        if self.put_result is not _UNSET:
            return self.put_result
        version = self.versions.get(secret_ref, 0) + 1
        self.versions[secret_ref] = version
        self.stored_values.append(value)
        self.puts.append(secret_ref)
        return version

    def revoke(self, secret_ref, version):
        self.revoked.append((secret_ref, version))

    def current_version(self, secret_ref):
        if self.current_error is not None:
            raise self.current_error
        return self.versions.get(secret_ref)


class FakeAuditSink:
    def __init__(self, error=None):
        self.error = error
        self.records = []

    def append(self, record):
        if self.error is not None:
            raise self.error
        self.records.append(record)


def _service(store=None, sink=None, clock=lambda: NOW):
    store = FakeSecretStore() if store is None else store
    sink = FakeAuditSink() if sink is None else sink
    return UpdateSecretService(store, sink, clock), store, sink


def _update(service, **overrides):
    kwargs = dict(workspace_id='ws-1', account_ref='acct-1', alias_ref='primary', value=SecretValue(C_VALUE), actor_ref='actor:u1', correlation_id='corr-1')
    kwargs.update(overrides)
    return service.update(**kwargs)


def _leaks(*outputs):
    return find_canaries(LEAK_CANARIES, *outputs)


def _error_texts(error):
    return [str(error), repr(error), error.args, ''.join(traceback.format_exception(error))]


def test_secret_store_port_has_no_read_api():
    assert sorted(name for name in vars(SecretStorePort) if not name.startswith('_')) == ['current_version', 'put', 'revoke']
    service, _, _ = _service()
    for name in ('get', 'read', 'reveal'):
        assert not hasattr(SecretStorePort, name)
        assert not hasattr(UpdateSecretService, name)
        assert not hasattr(service, name)


def test_two_updates_give_monotonic_versions_and_version_fingerprints():
    service, store, _ = _service()
    first = _update(service)
    second = _update(service, value=SecretValue('other-' + C_VALUE))
    assert (first.version, first.fingerprint) == (1, 'v1')
    assert (second.version, second.fingerprint) == (2, 'v2')
    assert store.current_version(REF) == 2
    assert len(store.stored_values) == 2
    assert all(isinstance(item, SecretValue) for item in store.stored_values)


def test_receipt_has_exactly_the_eight_contract_fields_and_is_frozen():
    assert [field.name for field in dataclasses.fields(SecretUpdateReceipt)] == RECEIPT_FIELDS
    receipt = _update(_service()[0])
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.version = 9
    assert receipt.secret_ref == REF
    assert (receipt.account_ref, receipt.alias_ref, receipt.actor_ref) == ('acct-1', 'primary', 'actor:u1')
    assert receipt.last_updated_at == NOW.isoformat()
    assert receipt.validation_state == 'unvalidated'


def test_fingerprint_is_version_string_not_derived_from_value():
    first = _update(_service()[0], value=SecretValue('aaaa-1111'))
    second = _update(_service()[0], value=SecretValue('zzzz-9999'))
    assert first.fingerprint == second.fingerprint == 'v1'


def test_each_update_appends_one_secret_update_audit_record():
    service, _, sink = _service()
    _update(service)
    _update(service)
    assert [record.action for record in sink.records] == ['secret_update', 'secret_update']
    first, second = sink.records
    assert (first.workspace_id, first.actor_ref, first.correlation_id, first.resource_ref, first.outcome) == ('ws-1', 'actor:u1', 'corr-1', REF, 'succeeded')
    assert (first.revision_before, first.revision_after) == (None, '1')
    assert (second.revision_before, second.revision_after) == ('1', '2')
    assert first.occurred_at == NOW.isoformat()
    assert first.audit_id != second.audit_id
    assert first.redacted_reason == 'validation_state=unvalidated'


def test_receipt_and_audit_do_not_contain_value_or_last_four_chars():
    service, _, sink = _service()
    receipt = _update(service)
    assert _leaks(receipt, dataclasses.asdict(receipt), sink.records, [dataclasses.asdict(record) for record in sink.records]) == []


@pytest.mark.parametrize('raw', [C_VALUE, b'bytes-' + C_VALUE.encode(), None, 5, {'password': C_VALUE}])
def test_non_secret_value_is_rejected_with_type_error_without_leaking(raw):
    service, store, sink = _service()
    with pytest.raises(TypeError) as excinfo:
        _update(service, value=raw)
    assert _leaks(*_error_texts(excinfo.value)) == []
    assert store.puts == [] and sink.records == []


BAD_REFS = ['https://host/x', 'a://b', 'token=abc', 'TOKEN=abc', 'secret=abc', 'my-Secret=abc', '', '   ', None, 5]


@pytest.mark.parametrize('field', ['workspace_id', 'account_ref', 'alias_ref'])
@pytest.mark.parametrize('bad', BAD_REFS)
def test_ref_component_with_url_or_credential_marker_is_rejected(field, bad):
    service, store, sink = _service()
    with pytest.raises(ValueError) as excinfo:
        _update(service, **{field: bad})
    assert 'abc' not in str(excinfo.value)
    assert store.puts == [] and sink.records == []


@pytest.mark.parametrize('field', ['actor_ref', 'correlation_id'])
@pytest.mark.parametrize('bad', ['', '   ', None, 5])
def test_blank_actor_or_correlation_is_value_error(field, bad):
    service, store, sink = _service()
    with pytest.raises(ValueError):
        _update(service, **{field: bad})
    assert store.puts == [] and sink.records == []


@pytest.mark.parametrize('clock', [lambda: datetime(2026, 10, 20, 1, 2, 3), lambda: '2026-10-20T01:02:03+00:00'])
def test_clock_must_return_aware_datetime(clock):
    service, store, sink = _service(clock=clock)
    with pytest.raises(ValueError):
        _update(service)
    assert store.puts == [] and sink.records == []


@pytest.mark.parametrize(('result', 'state'), [(True, 'valid'), (False, 'invalid'), (None, 'invalid')])
def test_validator_result_maps_to_validation_state(result, state):
    seen = []

    def validator(value):
        seen.append(value)
        return result

    service, store, sink = _service()
    receipt = _update(service, validator=validator)
    assert receipt.validation_state == state
    assert len(seen) == 1 and isinstance(seen[0], SecretValue)
    assert sink.records[0].outcome == 'succeeded'
    assert sink.records[0].redacted_reason == f'validation_state={state}'
    assert store.current_version(REF) == 1


def test_validator_raise_gives_invalid_with_redacted_error():
    def validator(value):
        raise RuntimeError(f'provider rejected {value.reveal()} password={C_PASSWORD}')

    service, store, sink = _service()
    receipt = _update(service, validator=validator)
    assert receipt.validation_state == 'invalid'
    assert receipt.version == 1
    record = sink.records[0]
    assert record.outcome == 'succeeded'
    assert record.redacted_reason.startswith('validation_state=invalid; validator_error=RuntimeError')
    assert _leaks(receipt, sink.records, [dataclasses.asdict(item) for item in sink.records]) == []


def test_store_put_error_gives_redacted_secret_update_error_and_failed_audit():
    store = FakeSecretStore(put_error=RuntimeError(f'backend rejected {C_VALUE} password={C_PASSWORD}'))
    service, _, sink = _service(store=store)
    with pytest.raises(SecretUpdateError) as excinfo:
        _update(service)
    error = excinfo.value
    assert str(error).startswith('secret_store_failed: RuntimeError')
    assert error.__cause__ is None and error.__context__ is None
    assert _leaks(*_error_texts(error), sink.records) == []
    assert len(sink.records) == 1
    record = sink.records[0]
    assert (record.action, record.outcome, record.revision_before, record.revision_after) == ('secret_update', 'failed', None, None)


def test_store_current_version_error_is_wrapped_and_audited_as_failed():
    store = FakeSecretStore(current_error=RuntimeError(f'lookup failed {C_VALUE}'))
    service, _, sink = _service(store=store)
    with pytest.raises(SecretUpdateError) as excinfo:
        _update(service)
    assert _leaks(*_error_texts(excinfo.value), sink.records) == []
    assert [record.outcome for record in sink.records] == ['failed']


@pytest.mark.parametrize('bad', [0, -1, True, '1', None])
def test_invalid_version_from_store_is_secret_update_error_and_failed_audit(bad):
    service, _, sink = _service(store=FakeSecretStore(put_result=bad))
    with pytest.raises(SecretUpdateError):
        _update(service)
    assert [record.outcome for record in sink.records] == ['failed']


def test_audit_sink_error_is_wrapped_and_redacted():
    sink = FakeAuditSink(error=RuntimeError(f'sink down {C_VALUE}'))
    service, _, _ = _service(sink=sink)
    with pytest.raises(SecretUpdateError) as excinfo:
        _update(service)
    error = excinfo.value
    assert str(error).startswith('audit_sink_failed: RuntimeError')
    assert error.__cause__ is None and error.__context__ is None
    assert _leaks(*_error_texts(error)) == []
