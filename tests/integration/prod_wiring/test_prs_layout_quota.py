"""PRS-LAYOUT-QUOTA: nối cấu hình bố cục vào lập kế hoạch sản xuất (quyết định Control 02:12Z 03/11/2026, điểm 3 và 4).

wiring.creative_settings đảo render.presets.variants.<preset>.layout của hồ sơ thành bố cục -> preset; ProductionActivityInputs đưa vào
BuildProductionPlan tập bố cục đủ điều kiện của script và selection đã lưu, bỏ bố cục đã đủ 40% của lô; mô hình chọn bố cục và kế hoạch
lấy preset của bố cục đó (FR-PRS-003), không còn lấy preset đầu tiên của cấu hình.

Không CSDL: kho script, kho selection, cổng đếm bố cục và kết nối là bản trong bộ nhớ của test.

coveredIds: FR-PRS-003, FR-PRS-005
"""
from __future__ import annotations

import copy
import datetime
import importlib.util
import json
import pathlib
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from controlplane.api.wiring import creative as wiring
from controlplane.api.wiring.production_profile import load_production_profile
from creative.adapters.activity_inputs import ActivityInputError, ProductionActivityInputs
from creative.domain import layout_choice
from render.domain import layout as render_layout

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
PRESETS = {
    'HERO_STRIP': 'bold-yellow', 'MOSAIC_GRID': 'news-red', 'FULL_BLEED_INSET': 'soft-shadow', 'SPLIT_STACK': 'clean-white', 'DATA_CARD': 'neon-cyan',
}
NOW = datetime.datetime(2026, 11, 3, 8, 0, 0, tzinfo=datetime.timezone.utc)


def _load_d14():
    path = ROOT / 'tests' / 'integration' / 'creative' / 'test_d14_creative_pipeline.py'
    spec = importlib.util.spec_from_file_location('prs_layout_quota_d14_support', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D14 = _load_d14()


class SelectionShelf:
    """Selection store of the test: what the pipeline saves is what the activity inputs load."""

    def __init__(self):
        self.items = {}

    def save(self, *, workspace_id, job_id, selection):
        self.items[(workspace_id, 'sel:' + selection.selection_fingerprint)] = selection
        return SimpleNamespace(selection_id='sel:' + selection.selection_fingerprint)

    def load(self, *, workspace_id, selection_id):
        return self.items.get((workspace_id, selection_id))


class FixedUsage:
    def __init__(self, found):
        self.found = found
        self.asked = []

    def usage(self, *, workspace_id, job_id):
        self.asked.append((workspace_id, job_id))
        return self.found


def _settings(layout_presets):
    base = wiring.creative_settings(load_production_profile(PROFILE_PATH))
    return type(base)(
        language_policy=base.language_policy, target_range=base.target_range, requested_angle_count=base.requested_angle_count,
        variation_policy_revision=base.variation_policy_revision, preset_revision_ref=base.preset_revision_ref, layout_presets=layout_presets)


def _chain(plan_layout):
    """D-14 chain up to the stored script and selection; the production plan answer of the fake model names plan_layout."""
    rig = D14.Rig()
    plan_json = D14._plan_json()
    if plan_layout is not None:
        plan_json['layout'] = plan_layout
    rig.ai._selection_by_instructions['Return JSON for production_plan'] = {'text': json.dumps(plan_json), 'refs': []}
    D14._prepare(rig)
    rig.pipeline.generate_script(context=D14._ctx(4), idempotency_key='k-script', **D14.SCRIPT_ARGS)
    selection = rig.pipeline.select_creative_assets(
        context=D14._ctx(5), idempotency_key='k-select', snapshot_id='snap-1', script_version_id='script-1',
        set_id='set-1', angle_id='angle-a', **D14._asset_inputs()).output
    shelf = SelectionShelf()
    shelf.save(workspace_id=D14.WS, job_id='job-7', selection=selection)
    return rig, shelf, 'sel:' + selection.selection_fingerprint


def _inputs(rig, shelf, settings, usage=None):
    return ProductionActivityInputs(
        uow_factory=lambda: rig.uow, prompts=None, sources=None, selection_inputs=None, variant_context=None, selections=shelf,
        settings=settings, clock=lambda: NOW, layout_usage=usage)


def _request(selection_id):
    refs = [
        {'ref_type': 'production_snapshot', 'ref_id': 'snap-1', 'revision_id': '1'},
        {'ref_type': 'script_version', 'ref_id': 'script-1', 'revision_id': '1'},
        {'ref_type': 'creative_asset_selection', 'ref_id': selection_id, 'revision_id': '1'},
    ]
    return {
        'stage_run_id': 'job-7:plan:r1', 'video_job_id': 'job-7', 'operation_key': 'op-plan-1', 'workflow_run_id': 'wf-1', 'input_refs': refs,
    }


GRANT = SimpleNamespace(workspace_id=D14.WS, job_id='job-7', recovery_epoch=1)


def test_profile_presets_name_one_preset_per_layout_and_the_default_plan_preset_is_the_hero_preset():
    settings = wiring.creative_settings(load_production_profile(PROFILE_PATH))
    assert settings.layout_presets == PRESETS
    assert settings.preset_revision_ref == 'bold-yellow'
    # The creative side (D) keeps its own copy of the five keys; it must stay equal to the render side (F).
    assert layout_choice.LAYOUT_KEYS == render_layout.LAYOUT_KEYS and layout_choice.DEFAULT_LAYOUT == render_layout.DEFAULT_LAYOUT
    raw = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
    without = copy.deepcopy(raw['render']['presets']['value'])
    del without['variants']['neon-cyan']['layout']
    plain = SimpleNamespace(parameters={'render.presets': without}, revision=3)
    assert wiring.creative_settings(plain).layout_presets is None


def test_plan_inputs_offer_the_eligible_layouts_without_the_ones_full_in_the_batch():
    rig, shelf, selection_id = _chain(None)
    args = _inputs(rig, shelf, _settings(PRESETS)).resolve('BuildProductionPlan', _request(selection_id), GRANT)
    # Two story pictures, no figure in the narration, no AI picture: HERO_STRIP and SPLIT_STACK.
    assert args['layout_options'] == ['HERO_STRIP', 'SPLIT_STACK'] and args['layout_presets'] == PRESETS
    assert args['preset_revision_ref'] == 'bold-yellow' and args['production_plan_id'] == 'plan:job-7:r1'
    usage = FixedUsage(({'HERO_STRIP': 4, 'SPLIT_STACK': 1}, 10))
    capped = _inputs(rig, shelf, _settings(PRESETS), usage).resolve('BuildProductionPlan', _request(selection_id), GRANT)
    assert capped['layout_options'] == ['SPLIT_STACK'] and usage.asked == [(D14.WS, 'job-7')]
    unknown = _inputs(rig, shelf, _settings(PRESETS), FixedUsage(None)).resolve('BuildProductionPlan', _request(selection_id), GRANT)
    assert unknown['layout_options'] == ['HERO_STRIP', 'SPLIT_STACK']


def test_without_layout_presets_the_plan_inputs_stay_as_before_and_bad_presets_are_refused():
    rig, shelf, selection_id = _chain(None)
    args = _inputs(rig, shelf, _settings(None)).resolve('BuildProductionPlan', _request(selection_id), GRANT)
    assert 'layout_options' not in args and 'layout_presets' not in args
    with pytest.raises(ActivityInputError) as caught:
        _inputs(rig, shelf, _settings({'HERO_STRIP': 'bold-yellow'})).resolve('BuildProductionPlan', _request(selection_id), GRANT)
    assert caught.value.reason == 'invalid_layout_presets'


def test_the_plan_takes_the_preset_of_the_layout_the_model_picks():
    rig, shelf, selection_id = _chain({'key': 'SPLIT_STACK', 'reason': 'strike then ships', 'contrast_pair': ['s1', 's2']})
    rig.pipeline._selections = shelf
    args = _inputs(rig, shelf, _settings(PRESETS)).resolve('BuildProductionPlan', _request(selection_id), GRANT)
    args.pop('context')
    result = rig.pipeline.build_production_plan(context=D14._ctx(6), idempotency_key='k-plan', **args)
    plan = result.output
    assert plan.preset_revision_ref == 'clean-white'
    assert plan.layout_choice['layout_key'] == 'SPLIT_STACK' and plan.layout_choice['fallback_reason'] is None


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class Connection:
    def __init__(self, target, layouts):
        self.target, self.layouts, self.calls = target, layouts, []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        if sql == wiring.LAYOUT_TARGET_SQL:
            return Rows([] if self.target is None else [(self.target,)])
        return Rows([(key,) for key in self.layouts])


class Manager:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def borrow_connection(self):
        yield self.connection


def test_layout_usage_counts_the_latest_plan_of_the_other_jobs_of_the_batch():
    conn = Connection(10, ['HERO_STRIP', 'HERO_STRIP', 'DATA_CARD', None, 'CAROUSEL'])
    assert wiring.PostgresLayoutUsage(Manager(conn)).usage(workspace_id='ws-1', job_id='job-7') == ({'HERO_STRIP': 2, 'DATA_CARD': 1}, 10)
    assert conn.calls == [(wiring.LAYOUT_TARGET_SQL, ('ws-1', 'job-7')), (wiring.LAYOUT_USAGE_SQL, ('ws-1', 'ws-1', 'job-7', 'job-7'))]
    assert "j.job_id <> %s" in wiring.LAYOUT_USAGE_SQL and 'DISTINCT ON (j.job_id)' in wiring.LAYOUT_USAGE_SQL and "'layout_choice'->>'layout_key'" in wiring.LAYOUT_USAGE_SQL
    assert wiring.PostgresLayoutUsage(Manager(Connection(None, ['HERO_STRIP']))).usage(workspace_id='ws-1', job_id='job-7') is None
