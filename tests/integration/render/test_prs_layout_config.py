"""PRS-LAYOUT-CONFIG: năm preset của hồ sơ production, mỗi preset ghép đúng một bố cục trình bày (quyết định Control 02:12Z 03/11/2026,
điểm 3), lề phải phụ đề 140 (điểm 5), và seed cấu hình render ghi revision mới khi nội dung đổi (không có thì production giữ preset cũ mãi).

Không CSDL: cổng cấu hình là bản trong bộ nhớ của test.

coveredIds: FR-PRS-001, FR-PRS-003
"""
import copy
import json
import pathlib
from types import SimpleNamespace

import pytest

from controlplane.api.wiring.production_profile import load_production_profile
from controlplane.api.wiring.render import render_supplements
from controlplane.domain.concurrency import RevisionConflictError
from render.adapters.config_render_sources import PRESET_SCOPE_KIND, ass_inputs, render_config_payloads, seed_render_config
from render.domain.layout import LAYOUT_KEYS
from render.domain.preset import build_preset_revision

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
PAIRING = {
    'bold-yellow': 'HERO_STRIP', 'news-red': 'MOSAIC_GRID', 'soft-shadow': 'FULL_BLEED_INSET', 'clean-white': 'SPLIT_STACK', 'neon-cyan': 'DATA_CARD',
}


def profile_inputs():
    profile = load_production_profile(PROFILE_PATH)
    return dict(profile.parameters), render_supplements(profile)


def presets(params, supplements):
    return {key: payload for kind, key, payload in render_config_payloads(params, supplements) if kind == PRESET_SCOPE_KIND and key in PAIRING}


def test_profile_pairs_each_preset_with_one_layout_and_moves_the_right_margin():
    raw = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
    variants = raw['render']['presets']['value']['variants']
    assert {name: v['layout'] for name, v in variants.items()} == PAIRING
    assert sorted(PAIRING.values()) == sorted(LAYOUT_KEYS)
    layout = raw['render']['layout']['value']
    assert (layout['margin_left'], layout['margin_right']) == (60, 140)
    assert raw['meta']['revision']['value'] == 8
    assert 'PRS-LAYOUT-CONFIG' in raw['meta']['revision']['reason']


def test_each_seeded_preset_carries_its_layout_accent_and_the_new_margin():
    found = presets(*profile_inputs())
    assert set(found) == set(PAIRING)
    raw = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))['render']['presets']['value']['variants']
    for name, payload in found.items():
        rules = payload['layout_rules']
        assert rules['presentation'] == {'layout_key': PAIRING[name], 'accent_colour': raw[name]['highlight_color']}
        assert rules['safe_area']['margin_right'] == 140
        preset = build_preset_revision({**payload, 'revision': 1})
        assert ass_inputs(preset, SimpleNamespace(width=1080, height=1920)).safe_area['margin_right'] == 140


def test_a_variant_without_layout_keeps_the_old_layout_rules():
    params, supplements = profile_inputs()
    params = copy.deepcopy(params)
    del params['render.presets']['variants']['news-red']['layout']
    found = presets(params, supplements)
    assert 'presentation' not in found['news-red']['layout_rules']
    assert set(found['news-red']['layout_rules']) == {'safe_area', 'line_limits', 'disclosure'}
    assert found['bold-yellow']['layout_rules']['presentation']['layout_key'] == 'HERO_STRIP'


@pytest.mark.parametrize('layout', ['hero_strip', 'GRID', 'HERO_STRIP'])
def test_an_unknown_or_repeated_layout_is_refused(layout):
    params, supplements = profile_inputs()
    params = copy.deepcopy(params)
    params['render.presets']['variants']['news-red']['layout'] = layout
    with pytest.raises(ValueError, match='render.presets.variants.news-red.layout'):
        render_config_payloads(params, supplements)


class ConfigStore:
    """In-memory published config: current() and put_config() with the expected-revision rule of the control API command service."""

    def __init__(self):
        self.rows = {}
        self.calls = []

    def current(self, *, workspace_id, scope_kind, scope_key):
        row = self.rows.get((scope_kind, scope_key))
        return None if row is None else SimpleNamespace(revision=row[0], config_revision_number=row[0], payload=row[1])

    def put_config(self, *, workspace_id, actor_id, idempotency_key, scope_kind, scope_key, expected_revision, payload):
        self.calls.append((scope_kind, scope_key, expected_revision, idempotency_key))
        current = self.rows.get((scope_kind, scope_key), (0, None))[0]
        if current != expected_revision:
            raise RevisionConflictError(current)
        self.rows[(scope_kind, scope_key)] = (current + 1, json.loads(json.dumps(payload)))
        return {'disposition': 'accepted'}


def test_seed_with_scope_publishes_a_new_revision_only_when_the_payload_changed():
    params, supplements = profile_inputs()
    store = ConfigStore()
    first = seed_render_config(store, workspace_id='w', actor_id='a', parameters=params, supplements=supplements, scope=store)
    assert ('preset:bold-yellow' in first) and len(first) == len(store.rows)
    store.calls.clear()
    assert seed_render_config(store, workspace_id='w', actor_id='a', parameters=params, supplements=supplements, scope=store) == ()
    assert store.calls == []
    changed = copy.deepcopy(supplements)
    changed['layout']['margin_right'] = 150
    again = seed_render_config(store, workspace_id='w', actor_id='a', parameters=params, supplements=changed, scope=store)
    assert set(again) == {f'preset:{name}' for name in PAIRING}
    assert {(c[1], c[2]) for c in store.calls} == {(name, 1) for name in PAIRING}
    assert all(c[3].endswith(':r1') for c in store.calls)
    assert store.rows[(PRESET_SCOPE_KIND, 'news-red')][1]['layout_rules']['safe_area']['margin_right'] == 150


def test_seed_without_scope_still_only_fills_empty_scopes():
    params, supplements = profile_inputs()
    store = ConfigStore()
    seed_render_config(store, workspace_id='w', actor_id='a', parameters=params, supplements=supplements)
    changed = copy.deepcopy(supplements)
    changed['layout']['margin_right'] = 150
    assert seed_render_config(store, workspace_id='w', actor_id='a', parameters=params, supplements=changed) == ()
    assert store.rows[(PRESET_SCOPE_KIND, 'news-red')][1]['layout_rules']['safe_area']['margin_right'] == 140
