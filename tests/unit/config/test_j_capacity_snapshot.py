"""J-07: ProviderCapacitySnapshot và quota domain (CT-CAP-001, RM-RISK-007).

coveredIds: CT-CAP-001, RM-RISK-007
"""
import dataclasses
import inspect
from datetime import datetime, timezone

import pytest

from controlplane.domain.config_security.capacity_snapshot import (
    CONFIDENCE_VALUES, QUOTA_KINDS, DomainCapacity, ProviderCapacitySnapshot, effective_confidence, is_expired,
    merge_quota_domain, quota_domain_key, remaining,
)

NOW = datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc)
FIELD_NAMES = (
    'snapshot_id', 'provider', 'model', 'project', 'account', 'capability', 'limit_requests', 'used_requests', 'limit_tokens',
    'used_tokens', 'limit_storage_bytes', 'used_storage_bytes', 'reset_at', 'backoff_until', 'health', 'latency_ms', 'error_rate',
    'confidence', 'source', 'observed_at', 'expires_at',
)
INT_FIELDS = ('limit_requests', 'used_requests', 'limit_tokens', 'used_tokens', 'limit_storage_bytes', 'used_storage_bytes')
FLOAT_FIELDS = ('latency_ms', 'error_rate')
ID_FIELDS = ('snapshot_id', 'provider', 'model', 'project', 'account', 'capability')
TIME_FIELDS = ('reset_at', 'backoff_until', 'observed_at', 'expires_at')


def _snap(**overrides: object) -> ProviderCapacitySnapshot:
    values = dict(
        snapshot_id='snap-1', provider='gemini', model='flash', project='proj-a', account='acct-1', capability='text',
        limit_requests=100, used_requests=40, limit_tokens=1000, used_tokens=250, limit_storage_bytes=5000,
        used_storage_bytes=1000, reset_at='2026-10-20T12:00:00+00:00', backoff_until=None, health='healthy', latency_ms=120,
        error_rate=0.01, confidence='observed', source='fixture', observed_at='2026-10-20T10:00:00+00:00',
        expires_at='2026-10-20T11:00:00+00:00',
    )
    values.update(overrides)
    return ProviderCapacitySnapshot(**values)


def test_snapshot_has_21_fields_in_spec_order_and_is_frozen() -> None:
    assert tuple(f.name for f in dataclasses.fields(ProviderCapacitySnapshot)) == FIELD_NAMES
    assert len(FIELD_NAMES) == 21
    with pytest.raises(dataclasses.FrozenInstanceError):
        _snap().account = 'other'


def test_minimal_snapshot_uses_safe_defaults() -> None:
    snap = ProviderCapacitySnapshot(snapshot_id='s', provider='p', model='m', project='j', account='a', capability='c')
    assert (snap.limit_requests, snap.used_requests, snap.confidence, snap.health, snap.expires_at) == (None, 0, 'unknown', 'unknown', None)


@pytest.mark.parametrize('field', INT_FIELDS + FLOAT_FIELDS)
def test_negative_number_is_rejected(field: str) -> None:
    with pytest.raises(ValueError):
        _snap(**{field: -1})


@pytest.mark.parametrize('field', INT_FIELDS + FLOAT_FIELDS)
@pytest.mark.parametrize('value', [True, False])
def test_bool_is_rejected(field: str, value: bool) -> None:
    with pytest.raises(ValueError):
        _snap(**{field: value})


@pytest.mark.parametrize('field', INT_FIELDS)
def test_non_integer_count_is_rejected(field: str) -> None:
    with pytest.raises(ValueError):
        _snap(**{field: 1.5})


@pytest.mark.parametrize('field', FLOAT_FIELDS)
@pytest.mark.parametrize('value', [float('nan'), float('inf')])
def test_non_finite_measure_is_rejected(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        _snap(**{field: value})


@pytest.mark.parametrize('confidence', ['guaranteed', 'OBSERVED', '', None, 5])
def test_unknown_confidence_is_rejected(confidence: object) -> None:
    with pytest.raises(ValueError):
        _snap(confidence=confidence)


def test_confidence_values_are_exactly_three_and_all_accepted() -> None:
    assert CONFIDENCE_VALUES == ('observed', 'estimated', 'unknown')
    assert [_snap(confidence=value).confidence for value in CONFIDENCE_VALUES] == list(CONFIDENCE_VALUES)


@pytest.mark.parametrize('field', ID_FIELDS)
@pytest.mark.parametrize('value', ['', '   ', 5, None])
def test_identity_field_must_be_non_empty_string(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _snap(**{field: value})


@pytest.mark.parametrize('field', TIME_FIELDS)
def test_time_field_rejects_non_text_non_datetime(field: str) -> None:
    with pytest.raises(ValueError):
        _snap(**{field: 5})


def test_unparsable_time_text_is_accepted_at_construction() -> None:
    assert _snap(expires_at='not-a-date').expires_at == 'not-a-date'


def test_quota_domain_key_signature_has_no_account() -> None:
    assert list(inspect.signature(quota_domain_key).parameters) == ['provider', 'project', 'model']


def test_quota_domain_key_ignores_account_and_separates_scopes() -> None:
    first, second = _snap(account='acct-1'), _snap(account='acct-4')
    keys = {quota_domain_key(s.provider, s.project, s.model) for s in (first, second)}
    assert len(keys) == 1
    key = keys.pop()
    assert 'acct' not in key
    assert quota_domain_key('gemini', 'proj-b', 'flash') != key
    assert quota_domain_key('gemini', 'proj-a', 'pro') != key
    assert quota_domain_key('openai', 'proj-a', 'flash') != key


def test_quota_domain_key_is_unambiguous_and_rejects_empty_parts() -> None:
    assert quota_domain_key('a/b', 'c', 'd') != quota_domain_key('a', 'b/c', 'd')
    with pytest.raises(ValueError):
        quota_domain_key('gemini', '', 'flash')


def test_expires_at_none_is_not_expired_and_keeps_confidence() -> None:
    snap = _snap(expires_at=None, confidence='estimated')
    assert is_expired(snap, NOW) is False
    assert effective_confidence(snap, NOW) == 'estimated'
    assert remaining(snap, 'requests', NOW) == 60


@pytest.mark.parametrize(('expires_at', 'expired'), [
    ('2026-10-20T11:00:00+00:00', False),
    ('2026-10-20T11:00:00Z', False),
    ('2026-10-20T17:31:00+07:00', False),
    (datetime(2026, 10, 20, 11, 0, tzinfo=timezone.utc), False),
    ('2026-10-20T10:30:00+00:00', True),
    ('2026-10-20T10:00:00+00:00', True),
    ('2026-10-20T17:00:00+07:00', True),
])
def test_aware_expiry_is_compared_against_now(expires_at: object, expired: bool) -> None:
    assert is_expired(_snap(expires_at=expires_at), NOW) is expired


@pytest.mark.parametrize('expires_at', ['2026-10-20T11:00:00', datetime(2026, 10, 20, 11, 0), 'not-a-date', ''])
def test_naive_or_unparsable_expiry_is_expired_fail_closed(expires_at: object) -> None:
    snap = _snap(expires_at=expires_at)
    assert is_expired(snap, NOW) is True
    assert effective_confidence(snap, NOW) == 'unknown'
    assert remaining(snap, 'requests', NOW) is None


@pytest.mark.parametrize('confidence', ['observed', 'estimated'])
def test_expired_snapshot_is_unknown_and_has_no_remaining(confidence: str) -> None:
    snap = _snap(confidence=confidence, expires_at='2026-10-20T10:00:00+00:00')
    assert effective_confidence(snap, NOW) == 'unknown'
    assert all(remaining(snap, kind, NOW) is None for kind in QUOTA_KINDS)


def test_fresh_snapshot_keeps_confidence_and_remaining_per_kind() -> None:
    snap = _snap(confidence='estimated')
    assert effective_confidence(snap, NOW) == 'estimated'
    assert [remaining(snap, kind, NOW) for kind in QUOTA_KINDS] == [60, 750, 4000]


def test_remaining_is_none_for_unknown_confidence_even_when_fresh() -> None:
    assert remaining(_snap(confidence='unknown'), 'requests', NOW) is None


def test_remaining_is_none_when_limit_is_none_and_clamped_at_zero() -> None:
    assert remaining(_snap(limit_tokens=None), 'tokens', NOW) is None
    assert remaining(_snap(limit_requests=10, used_requests=25), 'requests', NOW) == 0


def test_remaining_rejects_unknown_kind() -> None:
    assert QUOTA_KINDS == ('requests', 'tokens', 'storage_bytes')
    with pytest.raises(ValueError):
        remaining(_snap(), 'cpu', NOW)


def test_naive_now_is_rejected() -> None:
    naive = datetime(2026, 10, 20, 10, 30)
    for call in (lambda: is_expired(_snap(), naive), lambda: remaining(_snap(), 'requests', naive), lambda: merge_quota_domain([_snap()], naive)):
        with pytest.raises(ValueError):
            call()


def _four_accounts(**overrides: object) -> list[ProviderCapacitySnapshot]:
    return [
        _snap(snapshot_id=f'snap-{n}', account=f'acct-{n}', used_requests=10 * n, observed_at=f'2026-10-20T10:0{n}:00+00:00', **overrides)
        for n in range(1, 5)
    ]


def test_four_accounts_in_one_domain_do_not_multiply_limit() -> None:
    merged = merge_quota_domain(_four_accounts(), NOW)
    key = quota_domain_key('gemini', 'proj-a', 'flash')
    assert list(merged) == [key]
    domain = merged[key]
    assert isinstance(domain, DomainCapacity)
    assert domain.domain_key == key
    assert domain.limit_requests == 100
    assert (domain.used_requests, domain.remaining_requests) == (40, 60)
    assert (domain.health, domain.confidence) == ('healthy', 'observed')
    assert (domain.reset_at, domain.observed_at) == ('2026-10-20T12:00:00+00:00', '2026-10-20T10:04:00+00:00')


def test_different_project_gives_two_domains() -> None:
    snaps = _four_accounts()[:2] + [_snap(snapshot_id='snap-x', account='acct-9', project='proj-b')]
    merged = merge_quota_domain(snaps, NOW)
    assert set(merged) == {quota_domain_key('gemini', 'proj-a', 'flash'), quota_domain_key('gemini', 'proj-b', 'flash')}


def test_latest_observed_at_wins_regardless_of_input_order() -> None:
    snaps = _four_accounts()
    assert merge_quota_domain(list(reversed(snaps)), NOW) == merge_quota_domain(snaps, NOW)
    assert next(iter(merge_quota_domain(snaps[::-1], NOW).values())).used_requests == 40


def test_observed_at_is_compared_as_instants_across_offsets() -> None:
    older = _snap(snapshot_id='a', account='a1', used_requests=1, observed_at='2026-10-20T10:00:00+00:00')
    newer = _snap(snapshot_id='b', account='a2', used_requests=2, observed_at='2026-10-20T17:30:00+07:00')
    assert next(iter(merge_quota_domain([newer, older], NOW).values())).used_requests == 2


@pytest.mark.parametrize('bad', [None, 'not-a-date', '2026-10-20T11:00:00'])
def test_missing_naive_or_unparsable_observed_at_is_oldest(bad: object) -> None:
    dated = _snap(snapshot_id='a', account='a1', used_requests=1)
    undated = _snap(snapshot_id='b', account='a2', used_requests=2, observed_at=bad)
    assert next(iter(merge_quota_domain([dated, undated], NOW).values())).used_requests == 1


def test_tie_on_observed_at_takes_later_snapshot_in_input() -> None:
    first, second = _snap(snapshot_id='a', account='a1', used_requests=1), _snap(snapshot_id='b', account='a2', used_requests=2)
    assert next(iter(merge_quota_domain([first, second], NOW).values())).used_requests == 2


def test_expired_latest_snapshot_gives_unknown_and_no_remaining() -> None:
    domain = next(iter(merge_quota_domain([_snap(expires_at='2026-10-20T10:00:00+00:00')], NOW).values()))
    assert domain.confidence == 'unknown'
    assert domain.remaining_requests is None
    assert domain.limit_requests == 100


def test_empty_input_gives_empty_dict() -> None:
    assert merge_quota_domain([], NOW) == {}


def test_domain_capacity_has_eight_fields_is_frozen_and_has_no_secret_field() -> None:
    names = tuple(f.name for f in dataclasses.fields(DomainCapacity))
    assert names == ('domain_key', 'limit_requests', 'used_requests', 'remaining_requests', 'health', 'confidence', 'reset_at', 'observed_at')
    domain = next(iter(merge_quota_domain([_snap()], NOW).values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        domain.health = 'down'
    forbidden = ('secret', 'api_key', 'password', 'credential', 'access_token', 'refresh_token')
    for name in names + FIELD_NAMES:
        assert not any(word in name for word in forbidden)
