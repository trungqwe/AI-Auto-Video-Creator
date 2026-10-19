"""J-03: kế hoạch publish ConfigRevision, lineage và rollback (CT-CFG-001).

coveredIds: CT-CFG-001, CT-STATE-013, TST-INT-INV-004
"""
import ast
import copy
import dataclasses
import pathlib

import pytest

from controlplane.application.config_security.publish_plan import (
    SCOPE_KINDS, PublishPlan, PublishRequest, RollbackTargetInvalidError, SecretInConfigError, StaleBaseRevisionError, plan_publish,
)
from controlplane.application.idempotency import request_hash
from controlplane.domain.config_security import ConfigRevision, ConfigRevisionStatus

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'application' / 'config_security' / 'publish_plan.py'
WS, KIND, KEY = 'ws-1', 'provider', 'gemini'
PUBLISHED = ConfigRevisionStatus.PUBLISHED
SUPERSEDED = ConfigRevisionStatus.SUPERSEDED
INVALIDATED = ConfigRevisionStatus.INVALIDATED
DRAFT = ConfigRevisionStatus.DRAFT


def _payload(number: int) -> dict:
    return {'model': f'm{number}', 'limits': {'rpm': number}}


def _rev(number: int, status: ConfigRevisionStatus = PUBLISHED, *, workspace_id: str = WS, scope_kind: str = KIND, scope_key: str = KEY, payload: dict | None = None) -> ConfigRevision:
    payload = _payload(number) if payload is None else payload
    return ConfigRevision(
        config_revision_id=f'{workspace_id}-{scope_kind}-{scope_key}-{number}', workspace_id=workspace_id, scope_kind=scope_kind, scope_key=scope_key,
        config_revision_number=number, revision=number + 10, content_hash=request_hash(payload), payload=payload, status=status,
    )


def _chain(count: int) -> list[ConfigRevision]:
    return [_rev(n, SUPERSEDED if n < count else PUBLISHED) for n in range(1, count + 1)]


def _request(**overrides: object) -> PublishRequest:
    fields = dict(
        workspace_id=WS, scope_kind=KIND, scope_key=KEY, base_config_revision_number=None, payload={'model': 'new', 'limits': {'rpm': 9}},
        effective_at=None, actor_ref='actor-1', change_reason='test',
    )
    fields.update(overrides)
    return PublishRequest(**fields)


def test_empty_scope_gives_number_one_without_supersede() -> None:
    request = _request()
    assert plan_publish([], request) == PublishPlan(1, None, request_hash(request.payload), (), None)


@pytest.mark.parametrize('count', [1, 2, 3])
def test_scope_with_revisions_gives_max_plus_one_and_supersedes_published(count: int) -> None:
    existing = _chain(count)
    plan = plan_publish(existing, _request(base_config_revision_number=count))
    assert plan.config_revision_number == count + 1
    assert plan.superseded_config_revision_id == existing[-1].config_revision_id
    assert plan.validation == ()


def test_supersedes_the_published_revision_not_the_highest_number() -> None:
    existing = [_rev(1, SUPERSEDED), _rev(2, PUBLISHED), _rev(3, INVALIDATED)]
    plan = plan_publish(existing, _request(base_config_revision_number=3))
    assert (plan.config_revision_number, plan.superseded_config_revision_id) == (4, existing[1].config_revision_id)


def test_draft_counts_for_number_but_is_never_superseded() -> None:
    existing = [_rev(1, PUBLISHED), _rev(2, DRAFT)]
    plan = plan_publish(existing, _request(base_config_revision_number=2))
    assert (plan.config_revision_number, plan.superseded_config_revision_id) == (3, existing[0].config_revision_id)


def test_scope_without_published_revision_supersedes_nothing() -> None:
    existing = [_rev(1, SUPERSEDED), _rev(2, INVALIDATED)]
    plan = plan_publish(existing, _request(base_config_revision_number=2))
    assert (plan.config_revision_number, plan.superseded_config_revision_id) == (3, None)

def test_number_ignores_concurrency_revision_field() -> None:
    existing = [dataclasses.replace(_rev(1), revision=99)]
    assert plan_publish(existing, _request(base_config_revision_number=1)).config_revision_number == 2


@pytest.mark.parametrize('kind', sorted(SCOPE_KINDS))
def test_valid_scope_kinds_are_accepted(kind: str) -> None:
    assert plan_publish([], _request(scope_kind=kind)).config_revision_number == 1


def test_scope_kinds_are_exactly_the_contract_set() -> None:
    assert SCOPE_KINDS == {'workspace', 'module', 'provider', 'preset', 'policy', 'prompt'}


@pytest.mark.parametrize('kind', ['', 'Workspace', 'account', 'secret', 'unknown', 'config'])
def test_unknown_scope_kind_raises_invalid_scope_kind(kind: str) -> None:
    with pytest.raises(ValueError) as caught:
        plan_publish([], _request(scope_kind=kind))
    assert type(caught.value) is ValueError
    assert str(caught.value) == 'invalid_scope_kind'


@pytest.mark.parametrize('base', [None, 0, 1, 2, 4])
def test_base_other_than_max_raises_stale_base_revision(base: int | None) -> None:
    with pytest.raises(StaleBaseRevisionError):
        plan_publish(_chain(3), _request(base_config_revision_number=base))


@pytest.mark.parametrize('base', [0, 1])
def test_empty_scope_requires_base_none(base: int) -> None:
    with pytest.raises(StaleBaseRevisionError):
        plan_publish([], _request(base_config_revision_number=base))


def _noise() -> list[ConfigRevision]:
    return (
        [_rev(n, workspace_id='ws-2') for n in range(1, 8)]
        + [_rev(n, scope_kind='module') for n in range(1, 8)]
        + [_rev(n, scope_key='other') for n in range(1, 8)]
    )


def test_revisions_of_other_scopes_are_ignored_for_empty_scope() -> None:
    plan = plan_publish(_noise(), _request())
    assert (plan.config_revision_number, plan.superseded_config_revision_id) == (1, None)


def test_base_taken_from_another_scope_is_stale() -> None:
    with pytest.raises(StaleBaseRevisionError):
        plan_publish(_noise() + _chain(2), _request(base_config_revision_number=7))


def test_other_scopes_do_not_change_number_or_supersede_target() -> None:
    own = _chain(2)
    plan = plan_publish(_noise() + own, _request(base_config_revision_number=2))
    assert (plan.config_revision_number, plan.superseded_config_revision_id) == (3, own[-1].config_revision_id)

def test_content_hash_equals_request_hash_of_payload() -> None:
    payload = {'b': [1, {'z': None, 'a': 'x'}], 'a': 1.5}
    plan = plan_publish(_chain(1), _request(base_config_revision_number=1, payload=payload))
    assert plan.content_hash == request_hash(payload)
    assert plan.content_hash == request_hash({'a': 1.5, 'b': [1, {'a': 'x', 'z': None}]})


def test_effective_at_is_passed_through_without_clock() -> None:
    assert plan_publish([], _request(effective_at='2026-10-20T00:00:00Z')).effective_at == '2026-10-20T00:00:00Z'
    assert plan_publish([], _request(effective_at=None)).effective_at is None


def test_inputs_are_not_mutated() -> None:
    existing = _chain(3)
    request = _request(base_config_revision_number=3, payload={'a': {'b': [1, 2]}})
    existing_before, request_before = copy.deepcopy(existing), copy.deepcopy(request)
    first = plan_publish(existing, request)
    assert existing == existing_before
    assert request == request_before
    assert plan_publish(existing, request) == first


SECRET_PAYLOADS = [
    {'password': 'canary-value'},
    {'Secret': 'canary-value'},
    {'token': 'canary-value'},
    {'api_key': 'canary-value'},
    {'private_key': 'canary-value'},
    {'credential': None},
    {'client_secret': 'canary-value'},
    {'access_token': 'canary-value'},
    {'apiKey': 'canary-value'},
    {'x-api-key': 'canary-value'},
    {'a': {'b': {'api_key': 'canary-value'}}},
    {'items': [{'token': 'canary-value'}]},
    {'items': [[{'private_key': 'canary-value'}]]},
]


@pytest.mark.parametrize('payload', SECRET_PAYLOADS)
def test_sensitive_key_at_any_depth_raises_secret_in_config(payload: dict) -> None:
    with pytest.raises(SecretInConfigError) as caught:
        plan_publish([], _request(payload=payload))
    assert 'canary-value' not in str(caught.value)


def test_non_sensitive_keys_are_accepted() -> None:
    payload = {'max_tokens': 100, 'token_budget': 5, 'secret_handle_ref': 'handle-1', 'items': ['password', {'name': 'token'}]}
    assert plan_publish([], _request(payload=payload)).content_hash == request_hash(payload)

def _rollback_scope() -> list[ConfigRevision]:
    return [_rev(1, SUPERSEDED), _rev(2, SUPERSEDED), _rev(3, PUBLISHED)]


def test_valid_rollback_adds_marker_and_keeps_old_revisions_untouched() -> None:
    existing = _rollback_scope()
    before = copy.deepcopy(existing)
    plan = plan_publish(existing, _request(base_config_revision_number=3, payload=_payload(1), rollback_of_number=1))
    assert plan.validation == ('ROLLBACK_OF:1',)
    assert plan.config_revision_number == 4
    assert plan.superseded_config_revision_id == existing[2].config_revision_id
    assert plan.content_hash == existing[0].content_hash
    assert existing == before


def test_rollback_with_different_payload_is_rejected() -> None:
    with pytest.raises(RollbackTargetInvalidError):
        plan_publish(_rollback_scope(), _request(base_config_revision_number=3, payload=_payload(7), rollback_of_number=1))


@pytest.mark.parametrize('status', [INVALIDATED, DRAFT])
def test_rollback_to_invalidated_or_draft_target_is_rejected(status: ConfigRevisionStatus) -> None:
    existing = [_rev(1, status), _rev(2, PUBLISHED)]
    with pytest.raises(RollbackTargetInvalidError):
        plan_publish(existing, _request(base_config_revision_number=2, payload=_payload(1), rollback_of_number=1))


def test_rollback_to_missing_number_is_rejected() -> None:
    with pytest.raises(RollbackTargetInvalidError):
        plan_publish(_rollback_scope(), _request(base_config_revision_number=3, payload=_payload(1), rollback_of_number=9))


def test_rollback_target_must_be_in_the_same_scope() -> None:
    existing = [_rev(1, PUBLISHED), _rev(3, SUPERSEDED, workspace_id='ws-2')]
    with pytest.raises(RollbackTargetInvalidError):
        plan_publish(existing, _request(base_config_revision_number=1, payload=_payload(3), rollback_of_number=3))


def test_rollback_with_stale_base_is_rejected() -> None:
    with pytest.raises(StaleBaseRevisionError):
        plan_publish(_rollback_scope(), _request(base_config_revision_number=2, payload=_payload(1), rollback_of_number=1))


def test_business_errors_are_plain_exceptions_not_value_errors() -> None:
    for cls in (StaleBaseRevisionError, SecretInConfigError, RollbackTargetInvalidError):
        assert issubclass(cls, Exception) and not issubclass(cls, ValueError)

def test_publish_request_and_plan_are_frozen_with_contract_fields() -> None:
    request_fields = dataclasses.fields(PublishRequest)
    assert [f.name for f in request_fields] == [
        'workspace_id', 'scope_kind', 'scope_key', 'base_config_revision_number', 'payload', 'effective_at', 'actor_ref', 'change_reason',
        'rollback_of_number',
    ]
    assert [f.name for f in dataclasses.fields(PublishPlan)] == [
        'config_revision_number', 'superseded_config_revision_id', 'content_hash', 'validation', 'effective_at',
    ]
    assert PublishRequest.__dataclass_params__.frozen and PublishPlan.__dataclass_params__.frozen
    assert {f.name for f in request_fields if f.default is not dataclasses.MISSING} == {'rollback_of_number'}
    assert request_fields[-1].default is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(_request(), 'scope_key', 'x')
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(PublishPlan(1, None, 'h', (), None), 'config_revision_number', 2)


def test_validation_is_a_tuple() -> None:
    assert type(plan_publish([], _request()).validation) is tuple


def test_module_is_pure_and_imports_only_allowed_modules() -> None:
    allowed = {
        '__future__', 'collections.abc', 'dataclasses', 'typing', 'controlplane.application.idempotency', 'controlplane.domain.config_security',
    }
    imported = set()
    for node in ast.walk(ast.parse(MODULE_PATH.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    assert imported <= allowed


def test_module_docstring_declares_covered_ids() -> None:
    assert 'coveredIds: CT-CFG-001, CT-STATE-013, TST-INT-INV-004' in (__doc__ or '')
