"""PP-6: ProfileRouteCatalog through the real ProviderRouteResolver (CT-AI-ROUTE-001, QR-SEC-009)."""
from __future__ import annotations

import ast
import dataclasses
import pathlib
from datetime import datetime, timezone

import pytest

from controlplane.application.config_security.capacity_reservation import CapacityReservationBook, InMemoryReservationStore
from controlplane.application.config_security.route_resolver import NO_ELIGIBLE_ROUTE, NoRouteError, ProviderRouteResolver
from controlplane.domain.config_security.route_binding import ProviderRouteRequest
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.production_ports.route_catalog import ProfileRouteCatalog
from controlplane.infrastructure.production_ports.router_key_entry import store_router_key
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'production_ports' / 'route_catalog.py'
NOW = datetime(2026, 10, 25, 9, 0, tzinfo=timezone.utc)
WS = 'ws-prod-1'
ACCOUNT = 'router-primary'
SECRET = 'router-primary-api-key'
CANARY = 'sk-pp6-canary-0123456789abcdef'
MODEL_REFS = {
    'analysis': 'profile-model-analysis',
    'angle': 'profile-model-angle',
    'script': 'profile-model-script',
    'selection': 'profile-model-selection',
    'metadata': 'profile-model-metadata',
    'image_safety': 'profile-model-image-safety',
}


@pytest.fixture
def vault(tmp_path):
    return DpapiSecretStore(tmp_path / 'vault')


def with_key(vault):
    store_router_key(vault, SECRET, lambda: CANARY)
    return vault


def build(vault, model_refs=MODEL_REFS):
    catalog = ProfileRouteCatalog(model_refs, ACCOUNT, SECRET, vault)
    held = InMemoryReservationStore()
    resolver = ProviderRouteResolver(catalog, CapacityReservationBook(held), lambda domain_key: None, 'route-rev-1')
    return catalog, resolver, held


def resolve(resolver, role, job='job-1', workspace=WS):
    request = ProviderRouteRequest(
        ai_role=role, job_ref=job, snapshot_ref='snap-1', config_refs=[], data_sensitivity='internal',
        quality_latency_cost_bounds={}, allowed_fallbacks=[],
    )
    return resolver.resolve(request, workspace, NOW, 1, 60, True)


@pytest.mark.parametrize('role', sorted(MODEL_REFS))
def test_role_resolves_to_profile_model(vault, role) -> None:
    _, resolver, held = build(with_key(vault))
    decision = resolve(resolver, role)
    assert decision.account_ref == ACCOUNT
    assert decision.provider_ref == '9router'
    assert decision.model_ref == MODEL_REFS[role]
    assert decision.credential_acquisition_method == 'secret_broker_handle'
    assert decision.estimated_cost_class == 'free'
    assert decision.fallback_order == []
    assert len(held.list_all()) == 1 and held.list_all()[0].domain_key == '9router-gemini'


def test_candidate_fields(vault) -> None:
    catalog, _, _ = build(with_key(vault))
    found = catalog.candidates(WS, 'script')
    assert len(found) == 1
    candidate = found[0]
    assert candidate.candidate_ref == '9router:profile-model-script'
    assert candidate.provider_ref == '9router'
    assert candidate.model_ref == 'profile-model-script'
    assert candidate.cost_class == 'free'
    assert candidate.max_data_sensitivity == 'internal'
    assert candidate.local is False
    assert candidate.quota_domain_key == '9router-gemini'
    assert candidate.roles == frozenset(MODEL_REFS)
    account = candidate.account
    assert account.external_account_id == ACCOUNT
    assert account.workspace_id == WS
    assert account.capabilities == frozenset(MODEL_REFS)
    assert account.status is ExternalAccountStatus.ENABLED
    with pytest.raises(dataclasses.FrozenInstanceError):
        candidate.model_ref = 'x'


def test_account_workspace_follows_argument(vault) -> None:
    catalog, resolver, _ = build(with_key(vault))
    assert catalog.candidates('ws-other', 'angle')[0].account.workspace_id == 'ws-other'
    assert resolve(resolver, 'angle', workspace='ws-other').model_ref == MODEL_REFS['angle']


def test_unknown_role_has_no_candidate_and_no_route(vault) -> None:
    catalog, resolver, held = build(with_key(vault))
    assert list(catalog.candidates(WS, 'unknown_role')) == []
    with pytest.raises(NoRouteError) as info:
        resolve(resolver, 'unknown_role')
    assert info.value.code == NO_ELIGIBLE_ROUTE
    assert held.list_all() == ()


def test_missing_key_marks_account_revoked_and_blocks_route(vault) -> None:
    catalog, resolver, held = build(vault)
    assert catalog.candidates(WS, 'analysis')[0].account.status is ExternalAccountStatus.REVOKED
    with pytest.raises(NoRouteError) as info:
        resolve(resolver, 'analysis')
    assert info.value.code == NO_ELIGIBLE_ROUTE
    assert 'ACCOUNT_NOT_ELIGIBLE' in info.value.rationale_codes
    assert held.list_all() == ()


def test_revoke_removes_route_and_new_key_restores_it(vault) -> None:
    catalog, resolver, held = build(with_key(vault))
    assert resolve(resolver, 'script', job='job-1').model_ref == MODEL_REFS['script']
    vault.revoke(SECRET, vault.current_version(SECRET))
    assert catalog.candidates(WS, 'script')[0].account.status is ExternalAccountStatus.REVOKED
    with pytest.raises(NoRouteError) as info:
        resolve(resolver, 'script', job='job-2')
    assert info.value.code == NO_ELIGIBLE_ROUTE
    assert 'ACCOUNT_NOT_ELIGIBLE' in info.value.rationale_codes
    assert len(held.list_all()) == 1
    with_key(vault)
    assert resolve(resolver, 'script', job='job-3').model_ref == MODEL_REFS['script']


class VersionOnlyStore:
    def __init__(self, version) -> None:
        self.version = version
        self.asked = []

    def current_version(self, secret_ref):
        self.asked.append(secret_ref)
        return self.version


@pytest.mark.parametrize('version, status', [(1, ExternalAccountStatus.ENABLED), (7, ExternalAccountStatus.ENABLED), (None, ExternalAccountStatus.REVOKED)])
def test_status_comes_only_from_current_version(version, status) -> None:
    store = VersionOnlyStore(version)
    catalog = ProfileRouteCatalog(MODEL_REFS, ACCOUNT, SECRET, store)
    assert catalog.candidates(WS, 'metadata')[0].account.status is status
    assert store.asked == [SECRET]


def test_model_refs_are_copied_at_construction(vault) -> None:
    refs = dict(MODEL_REFS)
    catalog, _, _ = build(with_key(vault), refs)
    refs['script'] = 'changed'
    refs['extra'] = 'extra-model'
    assert catalog.candidates(WS, 'script')[0].model_ref == MODEL_REFS['script']
    assert list(catalog.candidates(WS, 'extra')) == []


@pytest.mark.parametrize('model_refs, account_ref, secret_ref', [
    ({}, ACCOUNT, SECRET), (None, ACCOUNT, SECRET), (['analysis'], ACCOUNT, SECRET),
    ({'analysis': ''}, ACCOUNT, SECRET), ({'': 'm'}, ACCOUNT, SECRET), ({'analysis': 5}, ACCOUNT, SECRET),
    (MODEL_REFS, '', SECRET), (MODEL_REFS, None, SECRET),
    (MODEL_REFS, ACCOUNT, ''), (MODEL_REFS, ACCOUNT, '  '), (MODEL_REFS, ACCOUNT, None),
])
def test_constructor_rejects_bad_arguments(vault, model_refs, account_ref, secret_ref) -> None:
    with pytest.raises(ValueError):
        ProfileRouteCatalog(model_refs, account_ref, secret_ref, vault)


ALLOWED_IMPORTS = {
    '__future__', 'collections.abc', 'typing',
    'controlplane.application.config_security.route_resolver',
    'controlplane.domain.config_security.external_account',
    'controlplane.domain.config_security.status_graph',
}
FORBIDDEN_TEXT = (
    'from src.', 'mock', 'fake', 'os.environ', 'getenv', 'sqlite', 'socket', 'subprocess', 'urllib', 'httpx',
    'requests', 'psycopg', 'sqlalchemy', 'open(', 'reveal', 'dpapi',
)


def test_source_is_pure_and_hard_codes_no_model() -> None:
    text = SOURCE.read_text(encoding='utf-8')
    lowered = text.lower()
    assert 'routecandidate' in lowered
    for forbidden in FORBIDDEN_TEXT:
        assert forbidden not in lowered
    assert 'gemini-' not in lowered.replace('9router-gemini', '')
    for model in MODEL_REFS.values():
        assert model not in text
    imported = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert imported <= ALLOWED_IMPORTS
