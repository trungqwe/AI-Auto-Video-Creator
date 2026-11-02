"""IMGGEN-ROLE: vai trò illustration của hồ sơ production đi qua loader, catalog tuyến và tuyến thị giác.

coveredIds: OI-CP7-11-Q2
Không dùng DB, mạng, GPU hay Temporal: chỉ đọc tools/launcher/prod/profile.json thật và dùng double Static* trong bộ nhớ.
"""
from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest

from controlplane.api.wiring.production_profile import REQUIRED_PARAMETERS, load_production_profile
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.production_ports.route_catalog import ProfileRouteCatalog
from controlplane.infrastructure.production_ports.vision_route import RouterVisionRoute, VisionRouteError

PROFILE_PATH = Path(__file__).resolve().parents[4] / 'tools' / 'launcher' / 'prod' / 'profile.json'
MODEL = 'ag/gemini-3.8-flash-high'
PIPELINE_ROLES = ('analysis', 'angle', 'script', 'selection', 'metadata', 'image_safety')
ACCOUNT = 'router-primary'
SECRET = 'router-primary-api-key'
WS = 'ws-imggen-role'


class StaticSecretVersions:
    def current_version(self, secret_ref):
        return 1


class StaticCredentials:
    def __init__(self):
        self.calls = []

    @contextlib.contextmanager
    def acquire(self, credential_method, account_ref):
        self.calls.append((credential_method, account_ref))
        yield 'sk-static-0123456789abcdef'


def test_loader_reads_the_illustration_route_and_keeps_the_85_required_parameters():
    data = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
    profile = load_production_profile(PROFILE_PATH)
    assert len(data) == 19 and len(REQUIRED_PARAMETERS) == 85
    assert 'ai.route_model_refs.illustration' not in REQUIRED_PARAMETERS
    assert list(profile.ai.route_model_refs) == [*PIPELINE_ROLES, 'illustration']
    assert set(profile.ai.route_model_refs.values()) == {MODEL}
    assert profile.revision >= 7


def test_route_catalog_resolves_the_illustration_role_like_the_six_pipeline_roles():
    profile = load_production_profile(PROFILE_PATH)
    catalog = ProfileRouteCatalog(profile.ai.route_model_refs, ACCOUNT, SECRET, StaticSecretVersions())
    reference = catalog.candidates(WS, 'image_safety')[0]
    for role in (*PIPELINE_ROLES, 'illustration'):
        found = catalog.candidates(WS, role)
        assert len(found) == 1, role
        candidate = found[0]
        assert (candidate.provider_ref, candidate.model_ref, candidate.candidate_ref) == ('9router', MODEL, '9router:' + MODEL), role
        assert candidate.account.status == ExternalAccountStatus.ENABLED, role
        assert role in candidate.roles, role
        assert (candidate.quota_domain_key, candidate.cost_class) == (reference.quota_domain_key, reference.cost_class), role
    assert catalog.candidates(WS, 'Illustration') == ()


def test_vision_route_built_from_the_profile_knows_the_illustration_role():
    profile = load_production_profile(PROFILE_PATH)
    credentials = StaticCredentials()
    route = RouterVisionRoute(profile.ai.route_endpoint, profile.ai.route_model_refs, credentials, ACCOUNT)
    with pytest.raises(ValueError):
        route.invoke_vision('illustration', 'Describe the image.', 'AAAA', 'image/png', 0)
    with pytest.raises(ValueError):
        route.invoke_chat('illustration', 'Write a caption.', 'An article about a flood.', timeout=0)
    assert credentials.calls == []
    with pytest.raises(VisionRouteError) as unknown:
        route.invoke_vision('Illustration', 'Describe the image.', 'AAAA', 'image/png', 5.0)
    assert unknown.value.code == 'unknown_role'
    assert credentials.calls == []
