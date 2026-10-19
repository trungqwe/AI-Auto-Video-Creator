"""J-09: AuditRecord append-only (CT-SEC-004).

coveredIds: CT-SEC-004, TST-SEC-INV-012
"""
import dataclasses
import json
from datetime import datetime, timedelta, timezone

import pytest

from controlplane.domain.config_security import audit_record
from controlplane.domain.config_security.audit_record import (
    AUDIT_REQUIRED_ACTIONS, AuditRecord, AuditSinkPort, UnknownAuditActionError, build_audit_record,
)
from controlplane.infrastructure.security import secret_redaction
from controlplane.infrastructure.security.secret_redaction import find_canaries

EXPECTED_ACTIONS = frozenset({
    'config_change', 'prompt_change', 'policy_change', 'preset_change',
    'source_add', 'source_disable', 'source_remove', 'source_restore',
    'hook_metadata_edit',
    'account_update', 'account_test', 'account_enable', 'account_disable', 'secret_update',
    'debug_run', 'retry', 'variant_create',
    'cleanup', 'restore', 'recovery',
    'technical_detail_view', 'sensitive_operation',
})
FIELD_NAMES = [
    'audit_id', 'workspace_id', 'actor_ref', 'action', 'resource_ref', 'revision_before',
    'revision_after', 'occurred_at', 'correlation_id', 'outcome', 'redacted_reason',
]
C_PASSWORD = 'CANARY-J09-PASSWORD-4c1d77'
C_BEARER = 'CANARY-J09-BEARER-8e2b03'
C_SK = 'sk-CANARYJ09SK1234567890'
ALL_CANARIES = [C_PASSWORD, C_BEARER, C_SK]
RAW_REASON = f'password={C_PASSWORD}; Authorization: Bearer {C_BEARER}; key {C_SK}'


def _build(**overrides):
    kwargs = dict(
        audit_id='audit-1', workspace_id='ws-1', actor_ref='actor:u1', action='config_change',
        resource_ref='config:global', revision_before='rev-1', revision_after='rev-2',
        occurred_at='2026-10-20T01:02:03+00:00', correlation_id='corr-1', outcome='succeeded',
        reason='manual change',
    )
    kwargs.update(overrides)
    return build_audit_record(**kwargs)


def test_required_actions_are_exactly_the_22_contract_codes():
    assert isinstance(AUDIT_REQUIRED_ACTIONS, frozenset)
    assert len(EXPECTED_ACTIONS) == 22
    assert len(AUDIT_REQUIRED_ACTIONS) == 22
    assert AUDIT_REQUIRED_ACTIONS == EXPECTED_ACTIONS


@pytest.mark.parametrize('action', sorted(EXPECTED_ACTIONS))
def test_every_required_action_can_be_built(action):
    record = _build(action=action)
    assert isinstance(record, AuditRecord)
    assert record.action == action


def test_audit_record_has_exactly_the_eleven_contract_fields_in_order():
    assert [field.name for field in dataclasses.fields(AuditRecord)] == FIELD_NAMES


def test_audit_record_is_frozen():
    record = _build()
    for name in FIELD_NAMES + ['extra']:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(record, name, 'changed')
    assert record.redacted_reason == 'manual change'
    assert record.action == 'config_change'


@pytest.mark.parametrize('action', ['unknown_action', '', 'CONFIG_CHANGE', ' config_change', None, 7])
def test_unknown_action_is_rejected_fail_closed(action):
    with pytest.raises(UnknownAuditActionError):
        _build(action=action)


def test_unknown_action_error_is_a_value_error():
    assert issubclass(UnknownAuditActionError, ValueError)


@pytest.mark.parametrize('outcome', ['succeeded', 'failed', 'denied'])
def test_allowed_outcomes_are_accepted(outcome):
    assert _build(outcome=outcome).outcome == outcome


@pytest.mark.parametrize('outcome', ['ok', 'SUCCEEDED', '', None, 1])
def test_other_outcomes_are_rejected(outcome):
    with pytest.raises(ValueError):
        _build(outcome=outcome)


def test_reason_is_redacted_through_j02_redact_value():
    assert audit_record.redact_value is secret_redaction.redact_value
    assert set(find_canaries(ALL_CANARIES, RAW_REASON)) == set(ALL_CANARIES)
    record = _build(reason=RAW_REASON)
    assert find_canaries(ALL_CANARIES, record, dataclasses.asdict(record), record.redacted_reason) == []
    assert record.redacted_reason == secret_redaction.redact_value(RAW_REASON)
    text = json.dumps(dataclasses.asdict(record), ensure_ascii=False)
    assert all(canary not in text for canary in ALL_CANARIES)


def test_reason_none_gives_empty_redacted_reason():
    assert _build(reason=None).redacted_reason == ''


@pytest.mark.parametrize('reason', [{'password': C_PASSWORD}, ['x'], 5, b'bytes'])
def test_non_string_reason_is_rejected_with_type_error(reason):
    with pytest.raises(TypeError):
        _build(reason=reason)


@pytest.mark.parametrize('field', ['audit_id', 'workspace_id', 'actor_ref', 'resource_ref', 'correlation_id'])
@pytest.mark.parametrize('value', ['', '   ', None, 5])
def test_identity_and_correlation_fields_must_be_non_empty_strings(field, value):
    with pytest.raises(ValueError):
        _build(**{field: value})


REVISION_FIELDS = ['revision_before', 'revision_after']


@pytest.mark.parametrize('field', REVISION_FIELDS)
@pytest.mark.parametrize('value', [{'k': 'v'}, {}, ['rev-1'], ('rev-1',), 1.5, True, object()])
def test_revision_payload_is_rejected_with_type_error(field, value):
    with pytest.raises(TypeError):
        _build(**{field: value})


@pytest.mark.parametrize('field', REVISION_FIELDS)
def test_revision_accepts_ref_number_or_none(field):
    assert getattr(_build(**{field: 'rev-9'}), field) == 'rev-9'
    assert getattr(_build(**{field: 7}), field) == '7'
    assert getattr(_build(**{field: 0}), field) == '0'
    assert getattr(_build(**{field: None}), field) is None


@pytest.mark.parametrize('field', REVISION_FIELDS)
@pytest.mark.parametrize('value', [-1, '', '   '])
def test_negative_number_or_blank_revision_is_value_error(field, value):
    with pytest.raises(ValueError):
        _build(**{field: value})


AWARE_UTC = datetime(2026, 10, 20, 1, 2, 3, tzinfo=timezone.utc)


@pytest.mark.parametrize('value', [
    '2026-10-20T01:02:03+00:00', '2026-10-20T01:02:03Z', '2026-10-20T08:02:03+07:00',
    AWARE_UTC, datetime(2026, 10, 20, 8, 2, 3, tzinfo=timezone(timedelta(hours=7))),
])
def test_aware_occurred_at_is_accepted_and_stored_as_iso_string(value):
    record = _build(occurred_at=value)
    assert isinstance(record.occurred_at, str)
    parsed = datetime.fromisoformat(record.occurred_at)
    assert parsed.utcoffset() is not None
    assert parsed == AWARE_UTC


@pytest.mark.parametrize('value', ['2026-10-20T01:02:03', '2026-10-20', datetime(2026, 10, 20, 1, 2, 3)])
def test_naive_occurred_at_is_value_error(value):
    with pytest.raises(ValueError):
        _build(occurred_at=value)


@pytest.mark.parametrize('value', ['', 'not-a-time', '2026-13-45T00:00:00+00:00'])
def test_unparsable_occurred_at_is_value_error(value):
    with pytest.raises(ValueError):
        _build(occurred_at=value)


@pytest.mark.parametrize('value', [None, 123, 1.5])
def test_non_time_occurred_at_is_type_error(value):
    with pytest.raises(TypeError):
        _build(occurred_at=value)


def test_audit_sink_port_is_append_only():
    assert hasattr(AuditSinkPort, 'append')
    assert not hasattr(AuditSinkPort, 'update')
    assert not hasattr(AuditSinkPort, 'delete')
    assert sorted(name for name in vars(AuditSinkPort) if not name.startswith('_')) == ['append']


def test_audit_sink_port_append_returns_none():
    assert AuditSinkPort.append.__annotations__['return'] in (None, 'None')
