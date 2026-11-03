"""PRS-LAYOUT-RENDER (FR-PRS-003): render dùng preset mà kế hoạch sản xuất đã chọn (preset_revision_ref), không còn luôn bold-yellow;
kế hoạch không có hoặc nêu preset chưa seed thì dùng DEFAULT_PRESET_KEY như cũ; seed cấu hình render của production truyền scope để
preset đổi trong hồ sơ được ghi revision mới.

Không CSDL: kết nối và cổng cấu hình là bản trong bộ nhớ của test.

coveredIds: FR-PRS-003
"""
import contextlib
import inspect
import json
import pathlib
from types import SimpleNamespace

from controlplane.api.wiring import render as render_wiring
from controlplane.api.wiring.production_profile import load_production_profile
from controlplane.domain.config_security import ConfigRevisionStatus
from render.adapters.config_render_sources import PRESET_SCOPE_KIND, ConfigRenderSources, render_config_payloads

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROFILE = load_production_profile(ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json')
PAYLOADS = {key: payload for kind, key, payload in render_config_payloads(PROFILE.parameters, render_wiring.render_supplements(PROFILE)) if kind == PRESET_SCOPE_KIND}


class PlanRows:
    def __init__(self, plans):
        self.plans = plans
        self.asked = []

    @contextlib.contextmanager
    def borrow_connection(self):
        yield self

    def execute(self, sql, params):
        self.asked.append(params[1])
        payload = self.plans.get(params[1])
        return SimpleNamespace(fetchone=lambda: None if payload is None else (json.dumps(payload),))


class SeededScope:
    def __init__(self, keys):
        self.keys = keys

    def current(self, *, workspace_id, scope_kind, scope_key):
        if scope_key not in self.keys:
            return None
        return SimpleNamespace(status=ConfigRevisionStatus.PUBLISHED, payload=PAYLOADS[scope_key], config_revision_number=1, config_revision_id=f'rev-{scope_key}')


def chosen(plans, plan_ref, seeded=tuple(PAYLOADS)):
    sources = render_wiring.ProductionRenderSources(PlanRows(plans), 'ws-1', PROFILE, None, None)
    return sources._plan_preset(ConfigRenderSources(SeededScope(set(seeded)), 'ws-1'), plan_ref)


def test_the_plan_preset_is_rendered_with_its_layout():
    pin = chosen({'plan-1': {'preset_revision_ref': 'news-red'}}, 'plan-1')
    assert pin.revision_ref == 'rev-news-red'
    assert dict(pin.preset.layout_rules['presentation']) == {'layout_key': 'MOSAIC_GRID', 'accent_colour': '#FF3B30'}


def test_plans_without_a_seeded_preset_keep_the_default():
    assert render_wiring.DEFAULT_PRESET_KEY == 'bold-yellow'
    for plans, ref in (({'plan-1': {'preset_revision_ref': 'common'}}, 'plan-1'), ({}, 'plan-1'), ({'plan-1': {}}, 'plan-1'), ({}, None)):
        assert chosen(plans, ref).revision_ref == 'rev-bold-yellow', (plans, ref)
    assert chosen({'plan-1': {'preset_revision_ref': 'neon-cyan'}}, 'plan-1', seeded=('bold-yellow',)).revision_ref == 'rev-bold-yellow'


def test_every_render_step_reads_the_plan_preset_and_seed_passes_a_scope():
    source = inspect.getsource(render_wiring.ProductionRenderSources)
    assert "preset('bold-yellow')" not in source
    assert source.count('self._plan_preset(cfg_sources,') == 4
    assert 'scope=FreshScope(manager)' in inspect.getsource(render_wiring.seed_production_render_config)
