"""PRS-LAYOUT-QUOTA-FIX1: trần 40% mỗi bố cục không bị vượt khi nhiều job của một lô lập kế hoạch cùng lúc (lô 875e2e7d: HERO_STRIP 41/100).

Tập bố cục mời mô hình được tính lúc activity bắt đầu, còn kế hoạch chỉ được lưu sau khoảng một phút gọi mô hình; job:43 thấy 39 kế hoạch
HERO_STRIP lúc bắt đầu và lưu khi đã có 40. Bản sửa kiểm lại trần trong giao dịch lưu kế hoạch, với số bố cục đọc sau khoá tư vấn theo lô
(creative.adapters.batch_layout_usage); bố cục đã đầy thì kế hoạch chuyển sang bố cục được mời còn chỗ (fallback_reason batch_cap_race),
mọi bố cục được mời đều đầy thì giữ bố cục đã chọn và ghi batch_cap_full, để kế hoạch không bao giờ thiếu bố cục.

Không CSDL: chuỗi D-14 trong bộ nhớ của test gói chủ (test_prs_layout_quota.py), cổng đếm và kết nối là bản trong bộ nhớ.
Khoá thật trên PostgreSQL: tests/integration/persistence/d/test_layout_cap_lock_postgres.py.

coveredIds: FR-PRS-005
"""
from __future__ import annotations

import importlib.util
import pathlib

from controlplane.api.wiring import creative as wiring
from creative.domain import layout_choice
from creative.persistence import PostgresCreativeUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
WS = '00000000-0000-0000-0000-0000000000f1'


def _load_owner():
    path = ROOT / 'tests' / 'integration' / 'prod_wiring' / 'test_prs_layout_quota.py'
    spec = importlib.util.spec_from_file_location('prs_layout_quota_fix1_owner', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _usage_module():
    # Imported inside the tests so that each test fails on its own on the code before the fix (no collection error).
    from creative.adapters import batch_layout_usage as module
    return module


def _cap_module():
    from creative.domain import layout_cap as module
    return module


OWNER = _load_owner()
PRESETS = OWNER.PRESETS
HERO = {'key': 'HERO_STRIP', 'reason': 'one strong picture', 'title': 'Port strike ends'}


class Ledger:
    """Batch usage read under the batch lock in the storing unit: what earlier plans of the batch committed (`stored`)."""

    def __init__(self, stored, batch_size):
        self.stored, self.batch_size, self.asked = dict(stored), batch_size, []

    def locked_usage(self, production_plan_id):
        self.asked.append(production_plan_id)
        return dict(self.stored), self.batch_size

    def commit(self, plan):
        key = plan.layout_choice['layout_key']
        self.stored[key] = self.stored.get(key, 0) + 1


def _plan_args(used, batch_size):
    """Chuỗi D-14 tới script và selection đã lưu; đầu vào BuildProductionPlan được tính khi lô đã có `used` (lúc activity bắt đầu)."""
    rig, shelf, selection_id = OWNER._chain(HERO)
    rig.pipeline._selections = shelf
    usage = OWNER.FixedUsage((used, batch_size))
    args = OWNER._inputs(rig, shelf, OWNER._settings(PRESETS), usage).resolve('BuildProductionPlan', OWNER._request(selection_id), OWNER.GRANT)
    args.pop('context')
    return rig, args


def _build(rig, args, key='k-plan', plan_id=None):
    if plan_id is not None:
        args = {**args, 'production_plan_id': plan_id}
    return rig.pipeline.build_production_plan(context=OWNER.D14._ctx(6), idempotency_key=key, **args).output


def test_a_plan_whose_layout_filled_while_the_model_ran_moves_to_an_offered_layout_with_room():
    rig, args = _plan_args({'HERO_STRIP': 3}, 10)
    assert args['layout_options'] == ['HERO_STRIP', 'SPLIT_STACK']
    # Another job of the batch committed the fourth HERO_STRIP plan (cap floor(0.4 * 10) = 4) during the model call.
    ledger = Ledger({'HERO_STRIP': 4}, 10)
    rig.uow.layout_usage = ledger
    plan = _build(rig, args)
    assert ledger.asked == ['plan:job-7:r1']
    assert plan.layout_choice['layout_key'] == 'SPLIT_STACK' and plan.preset_revision_ref == 'clean-white'
    assert plan.layout_choice['fallback_reason'] == _cap_module().FALLBACK_BATCH_CAP == 'batch_cap_race'
    assert plan.layout_choice['preset_key'] == 'clean-white' and plan.layout_choice['contrast_pair'] is None
    assert plan.layout_choice['reason'] == 'one strong picture' and plan.layout_choice['title'] == 'Port strike ends'
    assert plan.plan_fingerprint == plan.compute_fingerprint()
    stored = rig.uow.plans.latest('plan:job-7:r1')
    assert stored is not None and stored.record.layout_choice['layout_key'] == 'SPLIT_STACK'


def test_six_plans_in_flight_never_take_a_layout_past_its_share():
    # Six jobs start their plan activity before any of them stores a plan: each is offered HERO_STRIP and SPLIT_STACK and the model
    # names HERO_STRIP for all; the plans are stored one at a time, as the batch lock orders them.
    rig, args = _plan_args({}, 5)
    assert args['layout_options'] == ['HERO_STRIP', 'SPLIT_STACK']
    ledger = Ledger({}, 5)
    rig.uow.layout_usage = ledger
    picked = []
    for job in range(1, 5):
        plan = _build(rig, args, key=f'k-plan-{job}', plan_id=f'plan:job-{job}:r1')
        ledger.commit(plan)
        picked.append((plan.layout_choice['layout_key'], plan.layout_choice['fallback_reason']))
    # floor(0.4 * 5) = 2 plans per layout.
    assert picked == [('HERO_STRIP', None), ('HERO_STRIP', None), ('SPLIT_STACK', 'batch_cap_race'), ('SPLIT_STACK', 'batch_cap_race')]
    assert ledger.asked == [f'plan:job-{job}:r1' for job in range(1, 5)]


def test_when_every_offered_layout_is_full_the_plan_keeps_its_layout_and_says_so():
    rig, args = _plan_args({'HERO_STRIP': 3}, 10)
    rig.uow.layout_usage = Ledger({'HERO_STRIP': 4, 'SPLIT_STACK': 4}, 10)
    plan = _build(rig, args)
    assert plan.layout_choice['layout_key'] == 'HERO_STRIP' and plan.preset_revision_ref == 'bold-yellow'
    assert plan.layout_choice['fallback_reason'] == _cap_module().FALLBACK_BATCH_FULL == 'batch_cap_full'
    assert plan.plan_fingerprint == plan.compute_fingerprint()


def test_a_layout_with_room_and_units_without_a_ledger_keep_the_plan_as_before():
    rig, args = _plan_args({'HERO_STRIP': 3}, 10)
    plain = _build(rig, args, key='k-plain', plan_id='plan:job-8:r1')
    assert plain.layout_choice['layout_key'] == 'HERO_STRIP' and plain.layout_choice['fallback_reason'] is None
    rig.uow.layout_usage = Ledger({'HERO_STRIP': 3}, 10)
    room = _build(rig, args, key='k-room', plan_id='plan:job-9:r1')
    assert room.layout_choice == plain.layout_choice and room.preset_revision_ref == plain.preset_revision_ref == 'bold-yellow'
    rig.uow.layout_usage = Ledger({'HERO_STRIP': 9}, 0)
    assert _build(rig, args, key='k-nocap', plan_id='plan:job-10:r1').layout_choice['layout_key'] == 'HERO_STRIP'


def test_recheck_layout_moves_only_a_full_layout_and_keeps_the_choose_layout_order():
    layout_cap = _cap_module()
    hero = layout_choice.LayoutChoice(layout_key='HERO_STRIP', preset_key='bold-yellow', reason='r', title='t').to_payload()
    options = ('HERO_STRIP', 'FULL_BLEED_INSET', 'SPLIT_STACK')
    assert layout_cap.recheck_layout(hero, options=options, used={'HERO_STRIP': 39}, batch_size=100, presets=PRESETS) is None
    moved = layout_cap.recheck_layout(hero, options=options, used={'HERO_STRIP': 40}, batch_size=100, presets=PRESETS)
    assert moved == {
        'layout_key': 'FULL_BLEED_INSET', 'preset_key': 'soft-shadow', 'reason': 'r', 'fallback_reason': 'batch_cap_race', 'contrast_pair': None, 'title': 't'}
    split = layout_choice.LayoutChoice(
        layout_key='SPLIT_STACK', preset_key='clean-white', reason='r', contrast_pair=('s1', 's2')).to_payload()
    full = layout_cap.recheck_layout(split, options=('SPLIT_STACK',), used={'SPLIT_STACK': 40}, batch_size=100, presets=PRESETS)
    assert full['layout_key'] == 'SPLIT_STACK' and full['contrast_pair'] == ['s1', 's2'] and full['fallback_reason'] == 'batch_cap_full'
    assert layout_cap.batch_share_limit(100) == 40 and layout_cap.batch_share_limit(1) == 1 and layout_cap.batch_share_limit(0) is None
    assert layout_choice.capped_layouts(options, {'HERO_STRIP': 40}, 100) == ('FULL_BLEED_INSET', 'SPLIT_STACK')
    # Same cap and same fallback order as layout_choice (capped_layouts, choose_layout), which this fix leaves untouched.
    for size in range(0, 201):
        limit = layout_cap.batch_share_limit(size)
        for used in range(0, 82):
            kept = layout_choice.capped_layouts(('HERO_STRIP', 'SPLIT_STACK'), {'HERO_STRIP': used}, size)
            assert ('HERO_STRIP' in kept) == (limit is None or used < limit), (size, used)
    keys = layout_choice.LAYOUT_KEYS
    for mask in range(1, 2 ** len(keys)):
        subset = tuple(key for index, key in enumerate(keys) if mask >> index & 1)
        assert layout_cap._fallback(subset) == layout_choice._fallback(subset), subset


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
        layout_usage = _usage_module()
        self.calls.append((sql, params))
        if sql == layout_usage.LAYOUT_TARGET_SQL:
            return Rows([] if self.target is None else [(self.target,)])
        if sql == layout_usage.LAYOUT_LOCK_SQL:
            return Rows([('',)])
        return Rows([(key,) for key in self.layouts])


def test_locked_usage_takes_the_batch_lock_before_it_counts_the_plans_of_the_other_jobs():
    layout_usage = _usage_module()
    conn = Connection(10, ['HERO_STRIP', 'HERO_STRIP', 'DATA_CARD', None, 'CAROUSEL'])
    ledger = layout_usage.PostgresBatchLayoutUsage(lambda: conn, WS)
    assert ledger.locked_usage('plan:batch-1:job:43:r2') == ({'HERO_STRIP': 2, 'DATA_CARD': 1}, 10)
    job = 'batch-1:job:43'
    assert conn.calls == [
        (layout_usage.LAYOUT_TARGET_SQL, (WS, job)),
        (layout_usage.LAYOUT_LOCK_SQL, ('creative.layout_cap:', WS, job)),
        (layout_usage.LAYOUT_USAGE_SQL, (WS, WS, job, job)),
    ]
    # Same count as the activity inputs read before the model call.
    assert layout_usage.LAYOUT_USAGE_SQL == wiring.LAYOUT_USAGE_SQL and layout_usage.LAYOUT_TARGET_SQL == wiring.LAYOUT_TARGET_SQL
    assert 'pg_advisory_xact_lock(' in layout_usage.LAYOUT_LOCK_SQL
    no_batch = Connection(None, ['HERO_STRIP'])
    assert layout_usage.PostgresBatchLayoutUsage(lambda: no_batch, WS).locked_usage('plan:job-7:r1') is None
    assert [sql for sql, _ in no_batch.calls] == [layout_usage.LAYOUT_TARGET_SQL]
    other = Connection(10, [])
    assert layout_usage.PostgresBatchLayoutUsage(lambda: other, WS).locked_usage('selection:job-7') is None and other.calls == []


def test_the_postgres_unit_of_work_carries_the_batch_layout_usage():
    unit = PostgresCreativeUnitOfWork(object(), workspace_id=WS)
    assert isinstance(unit.layout_usage, _usage_module().PostgresBatchLayoutUsage)
