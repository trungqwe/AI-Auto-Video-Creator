"""J-16: adapter capability health từ ProviderCapacitySnapshot (CT-CAP-003, CT-CAP-001).

coveredIds: CT-CAP-003, CT-CAP-001
"""
import ast
import dataclasses
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from controlplane.application.config_security import capability_health
from controlplane.application.config_security.capability_health import project_capability_health, snapshot_to_observation
from controlplane.config.capability_view import CapabilityView
from controlplane.domain.config_security.capacity_snapshot import ProviderCapacitySnapshot

NOW = datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc)
MODULE_PATH = Path(capability_health.__file__)


def _snap(**overrides: object) -> ProviderCapacitySnapshot:
    values = dict(
        snapshot_id='snap-1', provider='gemini', model='flash', project='proj-a', account='acct-1', capability='text',
        limit_requests=100, used_requests=40, reset_at='2026-10-20T12:00:00+00:00', backoff_until=None, health='healthy',
        confidence='observed', source='canary-j16-source', observed_at='2026-10-20T10:00:00+00:00', expires_at='2026-10-20T11:00:00+00:00',
    )
    values.update(overrides)
    return ProviderCapacitySnapshot(**values)


def _view(**overrides: object) -> CapabilityView:
    return project_capability_health([_snap(**overrides)], NOW)[0]


def test_module_docstring_declares_covered_ids() -> None:
    assert 'coveredIds: CT-CAP-003, CT-CAP-001' in (__doc__ or '')


def test_observation_maps_every_key_from_snapshot() -> None:
    assert snapshot_to_observation(_snap(), NOW) == {
        'provider': 'gemini', 'capability_type': 'text', 'account_scope': 'acct-1:proj-a', 'limit': 100, 'used': 40, 'health': 'healthy',
        'confidence': 'observed', 'observed_at': '2026-10-20T10:00:00+00:00', 'expires_at': '2026-10-20T11:00:00+00:00',
        'reset_at': '2026-10-20T12:00:00+00:00', 'backoff_active': False, 'location': 'cloud',
    }


def test_missing_limit_omits_the_limit_key_and_is_never_available() -> None:
    observation = snapshot_to_observation(_snap(limit_requests=None), NOW)
    assert 'limit' not in observation
    assert observation['used'] == 40
    assert _view(limit_requests=None).status != 'available'


def test_observation_does_not_mutate_the_snapshot() -> None:
    snap = _snap(backoff_until='2026-10-20T10:45:00+00:00')
    before = dataclasses.asdict(snap)
    first = snapshot_to_observation(snap, NOW)
    first['provider'] = 'tampered'
    assert dataclasses.asdict(snap) == before
    assert snapshot_to_observation(snap, NOW)['provider'] == 'gemini'


def test_confidence_comes_from_effective_confidence() -> None:
    assert snapshot_to_observation(_snap(confidence='estimated'), NOW)['confidence'] == 'estimated'
    assert snapshot_to_observation(_snap(expires_at='2026-10-20T10:00:00+00:00'), NOW)['confidence'] == 'unknown'


def test_datetime_values_become_iso_text() -> None:
    moment = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    observation = snapshot_to_observation(
        _snap(observed_at=moment, expires_at=moment + timedelta(hours=1), reset_at=moment + timedelta(hours=2)), NOW)
    assert (observation['observed_at'], observation['expires_at'], observation['reset_at']) == (
        '2026-10-20T10:00:00+00:00', '2026-10-20T11:00:00+00:00', '2026-10-20T12:00:00+00:00')

@pytest.mark.parametrize(('backoff_until', 'active'), [
    (None, False),
    ('2026-10-20T10:31:00+00:00', True),
    ('2026-10-20T17:31:00+07:00', True),
    ('2026-10-20T10:30:00+00:00', False),
    ('2026-10-20T10:00:00+00:00', False),
    (datetime(2026, 10, 20, 10, 45, tzinfo=timezone.utc), True),
    ('2026-10-20T10:45:00', True),
    ('not-a-date', True),
])
def test_backoff_active_only_while_backoff_until_is_after_now(backoff_until: object, active: bool) -> None:
    assert snapshot_to_observation(_snap(backoff_until=backoff_until), NOW)['backoff_active'] is active


def test_expired_or_unknown_confidence_marks_quota_uncertain() -> None:
    assert 'is_quota_uncertain' not in snapshot_to_observation(_snap(), NOW)
    assert snapshot_to_observation(_snap(expires_at='2026-10-20T10:00:00+00:00'), NOW)['is_quota_uncertain'] is True
    assert snapshot_to_observation(_snap(confidence='unknown'), NOW)['is_quota_uncertain'] is True


def test_location_is_passed_through_and_defaults_to_cloud() -> None:
    assert snapshot_to_observation(_snap(), NOW)['location'] == 'cloud'
    assert snapshot_to_observation(_snap(), NOW, location='edge')['location'] == 'edge'
    assert project_capability_health([_snap()], NOW, location='edge')[0].location == 'edge'


def test_naive_now_is_rejected() -> None:
    naive = datetime(2026, 10, 20, 10, 30)
    with pytest.raises(ValueError):
        snapshot_to_observation(_snap(), naive)
    with pytest.raises(ValueError):
        project_capability_health([_snap()], naive)


def test_non_snapshot_input_is_type_error() -> None:
    with pytest.raises(TypeError):
        snapshot_to_observation({'provider': 'gemini'}, NOW)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        project_capability_health([{'provider': 'gemini'}], NOW)  # type: ignore[arg-type]

@pytest.mark.parametrize(('overrides', 'status'), [
    ({}, 'available'),
    ({'expires_at': '2026-10-20T10:00:00+00:00'}, 'degraded'),
    ({'backoff_until': '2026-10-20T10:45:00+00:00'}, 'degraded'),
    ({'limit_requests': None}, 'unknown'),
    ({'health': 'down'}, 'unavailable'),
    ({'health': 'unknown'}, 'unknown'),
    ({'confidence': 'unknown'}, 'degraded'),
    ({'limit_requests': 40, 'used_requests': 40}, 'unavailable'),
])
def test_status_projection(overrides: dict, status: str) -> None:
    assert _view(**overrides).status == status


def test_expired_quota_is_never_available() -> None:
    assert _view(expires_at='2026-10-20T10:30:00+00:00').status != 'available'
    assert _view(expires_at='2026-10-20T10:30:01+00:00').status == 'available'


def test_healthy_view_fields() -> None:
    view = _view()
    assert isinstance(view, CapabilityView)
    assert (view.provider, view.capability_type, view.account_scope, view.location) == ('gemini', 'text', 'acct-1:proj-a', 'cloud')
    assert view.capability_id == 'gemini:text:acct-1:proj-a'
    assert (view.capacity.limit, view.capacity.used, view.capacity.remaining, view.capacity.confidence) == (100.0, 40.0, 60.0, 'observed')
    assert (view.last_observed_at, view.expires_at, view.next_check_at) == ('2026-10-20T10:00:00Z', '2026-10-20T11:00:00Z', '2026-10-20T12:00:00Z')


@pytest.mark.parametrize('newer_first', [False, True])
def test_latest_snapshot_of_the_same_scope_wins(newer_first: bool) -> None:
    older = _snap(snapshot_id='old', used_requests=40, observed_at='2026-10-20T10:00:00+00:00')
    newer = _snap(snapshot_id='new', used_requests=90, observed_at='2026-10-20T10:05:00+00:00')
    views = project_capability_health([newer, older] if newer_first else [older, newer], NOW)
    assert len(views) == 1
    assert (views[0].capacity.used, views[0].capacity.remaining) == (90.0, 10.0)


def test_different_accounts_give_separate_views_sorted_by_capability_id() -> None:
    views = project_capability_health([_snap(account='acct-2'), _snap(account='acct-1')], NOW)
    assert [v.capability_id for v in views] == ['gemini:text:acct-1:proj-a', 'gemini:text:acct-2:proj-a']


def test_empty_input_gives_empty_list() -> None:
    assert project_capability_health([], NOW) == []

FORBIDDEN_WORDS = ('secret', 'token', 'password', 'credential', 'api_key', 'private_key', 'authorization', 'bearer')


def _key_names(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _key_names(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _key_names(child)


def test_view_and_observation_have_no_sensitive_key_or_source_canary() -> None:
    for view in project_capability_health([_snap(), _snap(account='acct-2', health='down')], NOW):
        data = view.to_dict()
        assert not any(word in name.lower() for name in _key_names(data) for word in FORBIDDEN_WORDS)
        assert 'canary-j16-source' not in json.dumps(data)
    observation = snapshot_to_observation(_snap(), NOW)
    assert not any(word in name.lower() for name in observation for word in FORBIDDEN_WORDS)
    assert 'canary-j16-source' not in json.dumps(observation)


def test_module_has_no_grant_function_and_views_expose_none() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    assert {'snapshot_to_observation', 'project_capability_health'} <= defined
    assert not any('grant' in name.lower() for name in defined | set(dir(capability_health)))
    assert not any('grant' in name.lower() for name in dir(_view()))


def test_module_is_pure_and_imports_only_allowed_modules() -> None:
    allowed = {
        '__future__', 'collections.abc', 'datetime',
        'controlplane.config.capability_view', 'controlplane.domain.config_security.capacity_snapshot',
    }
    imported, clock_calls = set(), set()
    for node in ast.walk(ast.parse(MODULE_PATH.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
        elif isinstance(node, ast.Attribute) and node.attr in {'now', 'utcnow', 'today'}:
            clock_calls.add(node.attr)
    assert imported <= allowed
    assert not clock_calls