"""J-15: external account test with operation receipt (CT-ACC-002).

coveredIds: CT-ACC-002, TST-SEC-INV-012
"""
import ast
import dataclasses
import inspect
from pathlib import Path

import pytest

from controlplane.application.config_security import account_test
from controlplane.application.config_security.account_test import (
    AccountProbePort, AccountTestReceipt, ExternalAccountTester, ProbeResult, ReceiptStorePort,
)
from controlplane.domain.config_security.external_account import ExternalAccount
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.security.secret_redaction import find_canaries, redact_value

C_PASSWORD = 'CANARY-J15-PASSWORD-5a3f19'
C_BEARER = 'CANARY-J15-BEARER-7d4c02'
C_SK = 'sk-CANARYJ15SK1234567890'
C_JWT = 'eyJCANARYJ15.PAYLOADPART.SIGPART'
C_OAUTH = 'ya29.CANARYJ15OAUTH'
ALL_CANARIES = [C_PASSWORD, C_BEARER, C_SK, C_JWT, C_OAUTH]
RAW_DETAIL = f'password={C_PASSWORD}; Authorization: Bearer {C_BEARER}; key {C_SK}; jwt {C_JWT}; oauth {C_OAUTH}'
NOW = '2026-10-20T01:02:03+00:00'


class FakeProbe:
    def __init__(self, result=None, error=None):
        self.result = result if result is not None else ProbeResult(ok=True, latency_ms=42)
        self.error = error
        self.calls = []

    def probe(self, account_ref, minimal):
        self.calls.append((account_ref, minimal))
        if self.error is not None:
            raise self.error
        return self.result


class FakeReceiptStore:
    def __init__(self):
        self.items = {}
        self.save_count = 0

    def get(self, operation_key):
        return self.items.get(operation_key)

    def save(self, receipt):
        self.save_count += 1
        self.items[receipt.operation_key] = receipt


class ProviderBoomError(Exception):
    pass


def _account(status=ExternalAccountStatus.ENABLED):
    return ExternalAccount(
        external_account_id='acc-1', workspace_id='ws-1', provider='gemini', account_label='Gemini 1', status=status,
        project_ref='proj-1', capabilities=frozenset({'caption', 'script'}), credential_version=1,
        credential_updated_at='2026-10-01T00:00:00+00:00', credential_expires_at=None, quota_observation_ref=None, health=None, revision=3,
    )


def _tester(probe=None, receipts=None):
    probe = probe if probe is not None else FakeProbe()
    receipts = receipts if receipts is not None else FakeReceiptStore()
    return ExternalAccountTester(probe, receipts, lambda: NOW), probe, receipts


def test_module_docstring_declares_covered_ids():
    assert 'coveredIds: CT-ACC-002, TST-SEC-INV-012' in __doc__


def test_tester_name_does_not_start_with_test_so_pytest_never_collects_it():
    assert not ExternalAccountTester.__name__.startswith('Test')
    assert [name for name, value in globals().items() if name.startswith('Test') and isinstance(value, type)] == []


def _public(cls):
    return sorted(name for name in vars(cls) if not name.startswith('_'))


def test_dataclass_fields_match_the_contract_in_order():
    assert [field.name for field in dataclasses.fields(ProbeResult)] == ['ok', 'latency_ms', 'error_class', 'detail']
    assert [field.name for field in dataclasses.fields(AccountTestReceipt)] == [
        'receipt_id', 'operation_key', 'external_account_id', 'ok', 'latency_ms', 'error_class', 'redacted_detail', 'tested_at',
    ]


def test_receipt_and_probe_result_are_frozen():
    receipt = _tester()[0].run(_account(), 'op-1')
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.ok = False
    with pytest.raises(dataclasses.FrozenInstanceError):
        ProbeResult(ok=True).ok = False


def test_ports_expose_exactly_the_contract_methods():
    assert _public(AccountProbePort) == ['probe']
    assert _public(ReceiptStorePort) == ['get', 'save']
    assert list(inspect.signature(AccountProbePort.probe).parameters) == ['self', 'account_ref', 'minimal']
    assert list(inspect.signature(ReceiptStorePort.get).parameters) == ['self', 'operation_key']
    assert list(inspect.signature(ReceiptStorePort.save).parameters) == ['self', 'receipt']


def test_tester_constructor_takes_only_probe_receipts_and_clock():
    assert list(inspect.signature(ExternalAccountTester.__init__).parameters) == ['self', 'probe', 'receipts', 'clock']


@pytest.mark.parametrize('status', [
    ExternalAccountStatus.ENABLED, ExternalAccountStatus.DISABLED, ExternalAccountStatus.DEGRADED, ExternalAccountStatus.INVALID,
])
def test_probe_is_always_called_with_minimal_true(status):
    tester, probe, _ = _tester()
    tester.run(_account(status), 'op-1')
    assert probe.calls == [('acc-1', True)]
    assert probe.calls[0][1] is True


@pytest.mark.parametrize('error', [None, RuntimeError('boom')])
def test_minimal_is_true_even_when_the_probe_fails_or_raises(error):
    tester, probe, _ = _tester(FakeProbe(ProbeResult(ok=False, error_class='AUTH'), error=error))
    for key in ('op-1', 'op-2', 'op-3'):
        tester.run(_account(), key)
    assert len(probe.calls) == 3
    assert all(minimal is True for _, minimal in probe.calls)


def test_success_receipt_carries_probe_outcome_and_clock_time():
    tester, probe, receipts = _tester(FakeProbe(ProbeResult(ok=True, latency_ms=42, detail='pong')))
    receipt = tester.run(_account(), 'op-1')
    assert isinstance(receipt, AccountTestReceipt)
    assert (receipt.operation_key, receipt.external_account_id) == ('op-1', 'acc-1')
    assert (receipt.ok, receipt.latency_ms, receipt.error_class, receipt.redacted_detail) == (True, 42, None, 'pong')
    assert receipt.tested_at == NOW
    assert isinstance(receipt.receipt_id, str) and receipt.receipt_id
    assert receipts.items == {'op-1': receipt}
    assert receipts.save_count == 1


def test_failed_probe_result_is_mapped_without_raising():
    tester, _, _ = _tester(FakeProbe(ProbeResult(ok=False, latency_ms=120, error_class='AUTH', detail='denied')))
    receipt = tester.run(_account(), 'op-1')
    assert (receipt.ok, receipt.latency_ms, receipt.error_class, receipt.redacted_detail) == (False, 120, 'AUTH', 'denied')


def test_none_detail_stays_none():
    tester, _, _ = _tester(FakeProbe(ProbeResult(ok=True, latency_ms=7)))
    assert tester.run(_account(), 'op-1').redacted_detail is None


def test_receipt_id_is_deterministic_per_account_and_operation_key():
    first = _tester()[0].run(_account(), 'op-1')
    again = _tester()[0].run(_account(), 'op-1')
    other = _tester()[0].run(_account(), 'op-2')
    assert first.receipt_id == again.receipt_id
    assert first.receipt_id != other.receipt_id


@pytest.mark.parametrize('operation_key', ['', None, 7, b'op'])
def test_invalid_operation_key_is_value_error_and_never_probes_or_saves(operation_key):
    tester, probe, receipts = _tester()
    with pytest.raises(ValueError):
        tester.run(_account(), operation_key)
    assert probe.calls == []
    assert receipts.save_count == 0


def test_second_run_with_same_operation_key_returns_stored_receipt_and_does_not_probe_again():
    tester, probe, receipts = _tester()
    first = tester.run(_account(), 'op-1')
    second = tester.run(_account(), 'op-1')
    assert second is first
    assert probe.calls == [('acc-1', True)]
    assert receipts.save_count == 1


def test_second_run_ignores_a_probe_that_would_now_answer_differently():
    tester, probe, _ = _tester()
    first = tester.run(_account(), 'op-1')
    probe.result = ProbeResult(ok=False, latency_ms=999, error_class='AUTH', detail='changed')
    assert tester.run(_account(), 'op-1') == first
    assert len(probe.calls) == 1


def test_different_operation_keys_each_probe_once():
    tester, probe, receipts = _tester()
    first = tester.run(_account(), 'op-1')
    second = tester.run(_account(), 'op-2')
    assert len(probe.calls) == 2
    assert receipts.save_count == 2
    assert first.receipt_id != second.receipt_id


def test_failed_receipt_is_also_idempotent():
    tester, probe, _ = _tester(FakeProbe(error=RuntimeError('boom')))
    first = tester.run(_account(), 'op-1')
    probe.error = None
    assert tester.run(_account(), 'op-1') is first
    assert len(probe.calls) == 1


def test_revoked_account_is_not_probed_and_gets_revoked_receipt():
    tester, probe, receipts = _tester()
    receipt = tester.run(_account(ExternalAccountStatus.REVOKED), 'op-1')
    assert probe.calls == []
    assert (receipt.ok, receipt.error_class, receipt.latency_ms, receipt.redacted_detail) == (False, 'REVOKED', None, None)
    assert (receipt.operation_key, receipt.external_account_id, receipt.tested_at) == ('op-1', 'acc-1', NOW)
    assert receipts.items == {'op-1': receipt}


def test_revoked_receipt_is_idempotent_and_never_probes():
    tester, probe, receipts = _tester()
    first = tester.run(_account(ExternalAccountStatus.REVOKED), 'op-1')
    assert tester.run(_account(ExternalAccountStatus.REVOKED), 'op-1') is first
    assert probe.calls == []
    assert receipts.save_count == 1


def test_control_raw_detail_exposes_every_canary():
    assert sorted(find_canaries(ALL_CANARIES, RAW_DETAIL)) == sorted(ALL_CANARIES)


@pytest.mark.parametrize('error', [
    RuntimeError(RAW_DETAIL), ValueError(RAW_DETAIL), TimeoutError(RAW_DETAIL), ProviderBoomError(RAW_DETAIL), KeyError(RAW_DETAIL),
])
def test_raising_probe_becomes_failed_receipt_with_class_name_and_no_canary(error):
    tester, _, receipts = _tester(FakeProbe(error=error))
    receipt = tester.run(_account(), 'op-1')
    assert receipt.ok is False
    assert receipt.error_class == type(error).__name__
    assert receipt.latency_ms is None
    assert isinstance(receipt.redacted_detail, str) and receipt.redacted_detail
    assert find_canaries(ALL_CANARIES, receipt, receipt.redacted_detail, receipts.items) == []


def test_probe_result_detail_goes_through_redact_value():
    tester, _, _ = _tester(FakeProbe(ProbeResult(ok=False, latency_ms=5, error_class='AUTH', detail=RAW_DETAIL)))
    receipt = tester.run(_account(), 'op-1')
    assert receipt.redacted_detail == redact_value(RAW_DETAIL)
    assert find_canaries(ALL_CANARIES, receipt) == []
    assert (receipt.ok, receipt.latency_ms, receipt.error_class) == (False, 5, 'AUTH')


def test_redacted_detail_has_no_token_pattern():
    tester, _, _ = _tester(FakeProbe(ProbeResult(ok=False, detail=RAW_DETAIL)))
    detail = tester.run(_account(), 'op-1').redacted_detail
    for pattern in ('sk-', 'ya29.', 'eyJ', 'password=CANARY', 'Bearer CANARY'):
        assert pattern not in detail


def test_probe_error_class_string_is_redacted_too():
    tester, _, _ = _tester(FakeProbe(ProbeResult(ok=False, error_class=C_SK)))
    assert find_canaries([C_SK], tester.run(_account(), 'op-1')) == []


def test_probe_exception_with_unprintable_message_still_yields_receipt():
    class Unprintable(Exception):
        def __str__(self):
            raise RuntimeError('no str')

    receipt = _tester(FakeProbe(error=Unprintable()))[0].run(_account(), 'op-1')
    assert receipt.ok is False
    assert receipt.error_class == 'Unprintable'
    assert receipt.redacted_detail == '[REDACTED]'


def test_probe_returning_garbage_is_a_failed_receipt_not_an_exception():
    probe = FakeProbe()
    probe.result = object()
    receipt = _tester(probe)[0].run(_account(), 'op-1')
    assert receipt.ok is False
    assert receipt.error_class == 'AttributeError'


@pytest.mark.parametrize('status', list(ExternalAccountStatus))
def test_run_never_changes_the_account(status):
    account = _account(status)
    before = dataclasses.replace(account)
    _tester()[0].run(account, 'op-1')
    assert account == before
    assert account.status is status
    assert account.capabilities == frozenset({'caption', 'script'})
    assert account.health is None
    assert account.revision == 3


@pytest.mark.parametrize('error', [RuntimeError('boom'), None])
def test_failed_probe_does_not_disable_or_degrade_the_account(error):
    account = _account()
    before = dataclasses.replace(account)
    probe = FakeProbe(ProbeResult(ok=False, error_class='AUTH'), error=error)
    _tester(probe)[0].run(account, 'op-1')
    assert account == before
    assert account.status is ExternalAccountStatus.ENABLED


def test_tester_has_no_enable_disable_or_set_route_and_only_run_is_public():
    tester = _tester()[0]
    for name in ('enable', 'disable', 'set_route'):
        assert not hasattr(tester, name)
    assert [name for name in dir(ExternalAccountTester) if not name.startswith('_')] == ['run']


def test_service_module_does_not_import_route_catalog_or_routing():
    tree = ast.parse(Path(account_test.__file__).read_text(encoding='utf-8'))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or '')
            imported += [alias.name for alias in node.names]
    assert imported
    assert [name for name in imported if 'route' in name.casefold() or 'catalog' in name.casefold()] == []


def test_redaction_uses_j02_redact_value():
    assert account_test.redact_value is redact_value
