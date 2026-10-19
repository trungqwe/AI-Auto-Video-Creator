"""G-14: kế hoạch resume sau restart (CT-WF-004, CT-WF-006; TST-WF-INV-016, TST-E2E-008).

coveredIds: CT-WF-004, CT-WF-006, TST-WF-INV-016, TST-E2E-008
"""
import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import pathlib
import pytest

from controlplane.domain.orchestration.recovery_scan import (
    GrantView,
    PendingResult,
    ResumeAction,
    ResumeKind,
    ResumeSnapshot,
    plan_resume,
)
from controlplane.domain.orchestration.stage_run_plan import StageRun
from controlplane.domain.statemachine import StageRunState

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'recovery_scan.py'
S = StageRunState
K = ResumeKind
NOW = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
FUTURE = '2026-10-20T13:00:00Z'
PAST = '2026-10-20T11:00:00Z'


def _view(status):
    return {'desktop_production': {'status': status}}


ONLINE = _view('available')
OFFLINE = _view('unavailable')


def _run(stage_run_id, stage_type, state, attempt=1, job_id='job-1', deps=()):
    return StageRun(
        stage_run_id=stage_run_id,
        job_id=job_id,
        stage_type=stage_type,
        input_refs=('in-1',),
        state=state,
        attempt=attempt,
        dependency_refs=deps,
    )


def _grant(stage_run_id, epoch='epoch-2', generation=1, expires_at=FUTURE):
    return GrantView(
        stage_run_id=stage_run_id,
        execution_generation=generation,
        recovery_epoch=epoch,
        expires_at=expires_at,
    )


def _snap(runs, grants=(), results=(), epoch='epoch-2', now=NOW, view=ONLINE, cursor=0):
    return ResumeSnapshot(
        runs=tuple(runs),
        grants=tuple(grants),
        pending_results=tuple(results),
        current_recovery_epoch=epoch,
        now=now,
        capability_view=view,
        allocation_cursor=cursor,
    )


def _kinds(actions):
    return [(a.kind, a.stage_run_id) for a in actions]


def _kind_of(actions, srid):
    matching = [a.kind for a in actions if a.stage_run_id == srid]
    assert len(matching) == 1, f'Expected 1 action for {srid}, got {matching}'
    return matching[0]


def test_resume_kind_has_exactly_six_values():
    assert [k.value for k in ResumeKind] == [
        'RESUME_STAGE',
        'CREATE_NEW_ATTEMPT',
        'RECONCILE_OUTCOME_UNKNOWN',
        'QUARANTINE_OLD_EPOCH_RESULT',
        'REISSUE_GRANT_NEW_EPOCH',
        'KEEP_WAITING',
    ]


def test_succeeded_and_failed_final_are_never_rerun():
    runs = [
        _run('sr-collect', 'collect', S.SUCCEEDED),
        _run('sr-script', 'script', S.SUCCEEDED),
        _run('sr-plan', 'plan', S.SUCCEEDED),
        _run('sr-render', 'render', S.FAILED_FINAL),
    ]
    assert plan_resume(_snap(runs)) == ()


def test_online_again_resumes_only_waiting_stage():
    runs = [
        _run('sr-collect', 'collect', S.SUCCEEDED),
        _run('sr-script', 'script', S.SUCCEEDED),
        _run('sr-plan', 'plan', S.WAITING_CAPABILITY, deps=('script',)),
        _run('sr-tts', 'tts', S.WAITING_DEPENDENCY, deps=('plan',)),
    ]
    actions = plan_resume(_snap(runs, view=ONLINE))
    assert _kinds(actions) == [(K.RESUME_STAGE, 'sr-plan'), (K.KEEP_WAITING, 'sr-tts')]


def test_capability_view_controls_resume():
    run_desktop = _run('sr-script', 'script', S.WAITING_CAPABILITY)
    for bad_view in [OFFLINE, _view('unknown'), {}, None]:
        actions = plan_resume(_snap([run_desktop], view=bad_view))
        assert _kinds(actions) == [(K.KEEP_WAITING, 'sr-script')]

    for good_view in [ONLINE, _view('degraded')]:
        actions = plan_resume(_snap([run_desktop], view=good_view))
        assert _kinds(actions) == [(K.RESUME_STAGE, 'sr-script')]

    run_cloud = _run('sr-collect', 'collect', S.WAITING_CAPABILITY)
    actions = plan_resume(_snap([run_cloud], view=OFFLINE))
    assert _kinds(actions) == [(K.RESUME_STAGE, 'sr-collect')]


def test_pending_and_waiting_dependency_follow_dependencies():
    # script PENDING deps ('collect',) v?i collect SUCCEEDED => RESUME_STAGE
    runs1 = [
        _run('sr-collect', 'collect', S.SUCCEEDED),
        _run('sr-script', 'script', S.PENDING, deps=('collect',)),
    ]
    assert _kind_of(plan_resume(_snap(runs1, view=ONLINE)), 'sr-script') == K.RESUME_STAGE

    # v?i collect RUNNING (k?m grant h?p l?) => KEEP_WAITING cho script
    grant = _grant('sr-collect')
    runs2 = [
        _run('sr-collect', 'collect', S.RUNNING),
        _run('sr-script', 'script', S.PENDING, deps=('collect',)),
    ]
    assert _kind_of(plan_resume(_snap(runs2, grants=[grant], view=ONLINE)), 'sr-script') == K.KEEP_WAITING

    # script PENDING v?i OFFLINE => KEEP_WAITING
    assert _kind_of(plan_resume(_snap(runs1, view=OFFLINE)), 'sr-script') == K.KEEP_WAITING

    # WAITING_DEPENDENCY: deps xong+ONLINE => RESUME_STAGE, deps ch?a xong => KEEP_WAITING
    runs3 = [
        _run('sr-collect', 'collect', S.SUCCEEDED),
        _run('sr-script', 'script', S.WAITING_DEPENDENCY, deps=('collect',)),
    ]
    assert _kind_of(plan_resume(_snap(runs3, view=ONLINE)), 'sr-script') == K.RESUME_STAGE

    runs4 = [
        _run('sr-collect', 'collect', S.RUNNING),
        _run('sr-script', 'script', S.WAITING_DEPENDENCY, deps=('collect',)),
    ]
    assert _kind_of(plan_resume(_snap(runs4, grants=[grant], view=ONLINE)), 'sr-script') == K.KEEP_WAITING


def test_failed_retryable_and_stale_create_new_attempt():
    for st in [S.FAILED_RETRYABLE, S.STALE]:
        run = _run('sr-script', 'script', st)
        assert _kind_of(plan_resume(_snap([run], view=ONLINE)), 'sr-script') == K.CREATE_NEW_ATTEMPT
        assert _kind_of(plan_resume(_snap([run], view=OFFLINE)), 'sr-script') == K.KEEP_WAITING

    run_cloud = _run('sr-collect', 'collect', S.FAILED_RETRYABLE)
    assert _kind_of(plan_resume(_snap([run_cloud], view=OFFLINE)), 'sr-collect') == K.CREATE_NEW_ATTEMPT


def test_outcome_unknown_is_reconciled_never_rerun():
    run = _run('sr-script', 'script', S.OUTCOME_UNKNOWN)
    assert _kind_of(plan_resume(_snap([run], view=ONLINE)), 'sr-script') == K.RECONCILE_OUTCOME_UNKNOWN
    assert _kind_of(plan_resume(_snap([run], view=OFFLINE)), 'sr-script') == K.RECONCILE_OUTCOME_UNKNOWN


def test_running_stage_follows_grant():
    run = _run('sr-script', 'script', S.RUNNING)
    # Grant epoch 'epoch-2' h?t h?n FUTURE => KEEP_WAITING
    g_curr = _grant('sr-script', epoch='epoch-2', expires_at=FUTURE)
    assert _kind_of(plan_resume(_snap([run], grants=[g_curr])), 'sr-script') == K.KEEP_WAITING

    # Grant epoch 'epoch-1' => REISSUE_GRANT_NEW_EPOCH
    g_old = _grant('sr-script', epoch='epoch-1', expires_at=FUTURE)
    assert _kind_of(plan_resume(_snap([run], grants=[g_old])), 'sr-script') == K.REISSUE_GRANT_NEW_EPOCH

    # Grant h?t h?n PAST => RECONCILE_OUTCOME_UNKNOWN
    g_past = _grant('sr-script', epoch='epoch-2', expires_at=PAST)
    assert _kind_of(plan_resume(_snap([run], grants=[g_past])), 'sr-script') == K.RECONCILE_OUTCOME_UNKNOWN

    # expires_at ??ng b?ng NOW ('2026-10-20T12:00:00Z') => RECONCILE_OUTCOME_UNKNOWN
    g_exact = _grant('sr-script', epoch='epoch-2', expires_at='2026-10-20T12:00:00Z')
    assert _kind_of(plan_resume(_snap([run], grants=[g_exact])), 'sr-script') == K.RECONCILE_OUTCOME_UNKNOWN

    # expires_at thu?c ['garbage','2026-10-20T13:00:00'] => RECONCILE_OUTCOME_UNKNOWN
    for bad_exp in ['garbage', '2026-10-20T13:00:00']:
        g_bad = _grant('sr-script', epoch='epoch-2', expires_at=bad_exp)
        assert _kind_of(plan_resume(_snap([run], grants=[g_bad])), 'sr-script') == K.RECONCILE_OUTCOME_UNKNOWN

    # Kh?ng c? grant => RECONCILE_OUTCOME_UNKNOWN
    assert _kind_of(plan_resume(_snap([run], grants=[])), 'sr-script') == K.RECONCILE_OUTCOME_UNKNOWN

    # Grant c?a stage_run_id kh?c b? b? qua => RECONCILE_OUTCOME_UNKNOWN
    g_other = _grant('sr-other', epoch='epoch-2', expires_at=FUTURE)
    assert _kind_of(plan_resume(_snap([run], grants=[g_other])), 'sr-script') == K.RECONCILE_OUTCOME_UNKNOWN

    # Nhi?u grant: generation 1 epoch 'epoch-1' + generation 2 epoch 'epoch-2' FUTURE => KEEP_WAITING
    g1 = _grant('sr-script', epoch='epoch-1', generation=1, expires_at=FUTURE)
    g2 = _grant('sr-script', epoch='epoch-2', generation=2, expires_at=FUTURE)
    assert _kind_of(plan_resume(_snap([run], grants=[g1, g2])), 'sr-script') == K.KEEP_WAITING

    # Grant epoch l? int 2 v?i current_recovery_epoch '2' => KEEP_WAITING
    g_int = _grant('sr-script', epoch=2, expires_at=FUTURE)
    assert _kind_of(plan_resume(_snap([run], grants=[g_int], epoch='2')), 'sr-script') == K.KEEP_WAITING


def test_old_epoch_result_with_same_generation_is_quarantined():
    run = _run('sr-script', 'script', S.RUNNING)
    grant = _grant('sr-script', epoch='epoch-1', generation=3, expires_at=FUTURE)
    res = PendingResult('res-1', 'sr-script', 3, 'epoch-1')
    actions = plan_resume(_snap([run], grants=[grant], results=[res], epoch='epoch-2'))
    assert actions[0] == ResumeAction(K.QUARANTINE_OLD_EPOCH_RESULT, stage_run_id='sr-script', result_id='res-1')
    assert actions[0].job_id is None
    assert actions[1].kind == K.REISSUE_GRANT_NEW_EPOCH


def test_current_epoch_result_is_not_quarantined():
    res1 = PendingResult('res-1', 'sr-script', 1, 'epoch-2')
    actions1 = plan_resume(_snap([], results=[res1], epoch='epoch-2'))
    assert not any(a.kind == K.QUARANTINE_OLD_EPOCH_RESULT for a in actions1)

    res2 = PendingResult('res-2', 'sr-script', 1, 2)
    actions2 = plan_resume(_snap([], results=[res2], epoch='2'))
    assert not any(a.kind == K.QUARANTINE_OLD_EPOCH_RESULT for a in actions2)


def test_malformed_result_epoch_is_quarantined():
    for bad_ep in [None, True, '', 'epoch-9']:
        res = PendingResult('res-x', 'sr-missing', 1, bad_ep)
        actions = plan_resume(_snap([], results=[res], epoch='epoch-2'))
        assert actions == (ResumeAction(K.QUARANTINE_OLD_EPOCH_RESULT, stage_run_id='sr-missing', result_id='res-x'),)

    # Nhi?u result gi? nguy?n th? t? ??u v?o
    r1 = PendingResult('res-a', 'sr-1', 1, 'old-1')
    r2 = PendingResult('res-b', 'sr-2', 1, 'old-2')
    actions_multi = plan_resume(_snap([], results=[r1, r2], epoch='epoch-2'))
    assert [a.result_id for a in actions_multi] == ['res-a', 'res-b']


def test_superseded_attempts_are_skipped():
    run1 = _run('sr-script-1', 'script', S.WAITING_CAPABILITY, attempt=1)
    run2 = _run('sr-script-2', 'script', S.PENDING, attempt=2)
    actions = plan_resume(_snap([run1, run2], view=ONLINE))
    assert _kinds(actions) == [(K.RESUME_STAGE, 'sr-script-2')]


def test_jobs_are_independent():
    run1 = _run('sr-job1-script', 'script', S.SUCCEEDED, job_id='job-1')
    run2 = _run('sr-other', 'script', S.WAITING_CAPABILITY, job_id='job-2')
    actions = plan_resume(_snap([run1, run2], view=ONLINE))
    assert _kinds(actions) == [(K.RESUME_STAGE, 'sr-other')]
    assert actions[0].job_id == 'job-2'


def test_allocation_cursor_never_restarts_from_first_item():
    runs = [
        _run('sr-collect', 'collect', S.SUCCEEDED),
        _run('sr-script', 'script', S.WAITING_CAPABILITY),
    ]
    res0 = plan_resume(_snap(runs, cursor=0))
    res7 = plan_resume(_snap(runs, cursor=7))
    assert res0 == res7
    for a in res0:
        assert a.kind in set(ResumeKind)
        assert a.stage_run_id != 'sr-collect'


@pytest.mark.parametrize('bad', [-1, True, 1.5, '3', None])
def test_allocation_cursor_is_validated(bad):
    with pytest.raises(ValueError):
        plan_resume(_snap([], cursor=bad))


def test_plan_is_deterministic_pure_and_returns_tuple():
    runs = (_run('sr-script', 'script', S.WAITING_CAPABILITY),)
    snap = _snap(runs)
    res1 = plan_resume(snap)
    res2 = plan_resume(snap)
    assert res1 == res2
    assert isinstance(res1, tuple)
    assert snap.runs == runs
    assert plan_resume(_snap([], grants=(), results=())) == ()


def test_snapshot_validation():
    for bad_snap in [None, {}, 'x']:
        with pytest.raises(TypeError):
            plan_resume(bad_snap)

    naive_now = datetime(2026, 10, 20, 12, 0, 0)
    with pytest.raises(ValueError):
        plan_resume(_snap([], now=naive_now))

    for bad_epoch in [None, True, '', '  ', 1.5]:
        with pytest.raises(ValueError):
            plan_resume(_snap([], epoch=bad_epoch))

    with pytest.raises(TypeError):
        plan_resume(ResumeSnapshot(runs=[], grants=(), pending_results=(), current_recovery_epoch='epoch-2', now=NOW))


def test_resume_action_is_frozen():
    action = ResumeAction(K.RESUME_STAGE, 'sr-1')
    with pytest.raises(FrozenInstanceError):
        action.kind = K.KEEP_WAITING


def test_module_imports_only_stdlib_and_controlplane_domain():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots, internal = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or '').split('.')[0])
            if (node.module or '').startswith('controlplane'):
                internal.add(node.module)
    assert roots <= {'__future__', 'collections', 'dataclasses', 'datetime', 'enum', 'controlplane'}
    assert internal == {
        'controlplane.domain.orchestration.job_waiting',
        'controlplane.domain.orchestration.stage_run_plan',
        'controlplane.domain.statemachine',
    }
