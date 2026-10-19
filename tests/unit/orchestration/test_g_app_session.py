"""G-14: AppSession và log_ref (CT-ORC-011; TST-E2E-013).

coveredIds: CT-ORC-011, TST-E2E-013
"""
import ast
from dataclasses import FrozenInstanceError
import pathlib
import pytest

from controlplane.domain.orchestration.app_session import (
    INVALID_CHECKPOINT,
    INVALID_COMPLETED_COUNT,
    INVALID_LOG_REF,
    INVALID_SESSION,
    OUTPUT_FOLDER_WITHOUT_VIDEO,
    SESSION_ALREADY_CLOSED,
    SESSION_ID_REUSED,
    AppSession,
    AppSessionError,
    JobCheckpoint,
    LogRef,
    OutputFolderIntent,
    SessionCheckpoint,
    close_session,
    make_log_ref,
    resume_session,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'app_session.py'

T0 = '2026-10-20T08:00:00Z'
T1 = '2026-10-20T09:00:00Z'


def _session(**over):
    base = {
        'session_id': 'sess-1',
        'started_at': T0,
        'desktop_identity': 'desk-1',
        'log_scope': 'scope-1',
    }
    base.update(over)
    return AppSession(**base)


def _checkpoint():
    return SessionCheckpoint(
        'batch-1',
        (JobCheckpoint('job-1', 'sr-1'), JobCheckpoint('job-2')),
    )


def _code(exc_info):
    return exc_info.value.code


def test_session_is_immutable_and_hashable():
    session = _session()
    with pytest.raises(FrozenInstanceError):
        session.ended_at = T1
    assert isinstance(hash(session), int)


def test_session_field_validation():
    for fld in ['session_id', 'desktop_identity', 'log_scope']:
        for bad in ['', '  ', None, 5]:
            with pytest.raises(AppSessionError) as exc_info:
                _session(**{fld: bad})
            assert _code(exc_info) == INVALID_SESSION

    for bad_start in ['garbage', '2026-10-20T08:00:00', None]:
        with pytest.raises(AppSessionError) as exc_info:
            _session(started_at=bad_start)
        assert _code(exc_info) == INVALID_SESSION

    for bad_end in ['garbage', '2026-10-20T08:00:00', '2026-10-20T07:00:00Z']:
        with pytest.raises(AppSessionError) as exc_info:
            _session(ended_at=bad_end)
        assert _code(exc_info) == INVALID_SESSION

    with pytest.raises(AppSessionError) as exc_info:
        _session(checkpoint='x')
    assert _code(exc_info) == INVALID_SESSION

    with pytest.raises(AppSessionError) as exc_info:
        _session(output_folder_intent='x')
    assert _code(exc_info) == INVALID_SESSION


def test_empty_session_has_no_output_folder_intent():
    s = _session()
    closed = close_session(s, 0, ended_at=T1)
    assert closed.ended_at == T1
    assert closed.output_folder_intent is None


def test_session_with_videos_gets_intent_and_original_unchanged():
    s = _session()
    closed = close_session(s, 3, ended_at=T1)
    assert closed.output_folder_intent == OutputFolderIntent('sess-1', 3)
    assert s.ended_at is None
    assert s.output_folder_intent is None
    assert closed is not s


@pytest.mark.parametrize('bad_count', [-1, True, False, 1.5, '1', None])
def test_invalid_completed_count(bad_count):
    with pytest.raises(AppSessionError) as exc_info:
        close_session(_session(), bad_count, ended_at=T1)
    assert _code(exc_info) == INVALID_COMPLETED_COUNT


def test_closed_session_cannot_be_closed_again():
    s = close_session(_session(), 0, ended_at=T1)
    with pytest.raises(AppSessionError) as exc_info1:
        close_session(s, 0, ended_at='2026-10-20T10:00:00Z')
    assert _code(exc_info1) == SESSION_ALREADY_CLOSED

    s2 = close_session(_session(), 1, ended_at=T1)
    with pytest.raises(AppSessionError) as exc_info2:
        close_session(s2, 2, ended_at='2026-10-20T10:00:00Z')
    assert _code(exc_info2) == SESSION_ALREADY_CLOSED


@pytest.mark.parametrize('bad_end', ['', 'garbage', '2026-10-20T09:00:00', '2026-10-20T07:00:00Z'])
def test_close_rejects_bad_end_time(bad_end):
    with pytest.raises(AppSessionError) as exc_info:
        close_session(_session(), 0, ended_at=bad_end)
    assert _code(exc_info) == INVALID_SESSION


def test_close_rejects_non_session():
    with pytest.raises(TypeError):
        close_session('not-session', 0, ended_at=T1)


@pytest.mark.parametrize('bad_count', [0, -1, True, 1.5])
def test_intent_requires_video_and_closed_session(bad_count):
    with pytest.raises(AppSessionError) as exc_info:
        OutputFolderIntent('sess-1', bad_count)
    assert _code(exc_info) == OUTPUT_FOLDER_WITHOUT_VIDEO

    intent = OutputFolderIntent('sess-1', 2)
    with pytest.raises(AppSessionError) as exc_info2:
        _session(output_folder_intent=intent, ended_at=None)
    assert _code(exc_info2) == INVALID_SESSION

    other_intent = OutputFolderIntent('other-sess', 2)
    with pytest.raises(AppSessionError) as exc_info3:
        _session(output_folder_intent=other_intent, ended_at=T1)
    assert _code(exc_info3) == INVALID_SESSION


def test_resume_keeps_batch_and_job_checkpoint():
    previous = close_session(_session(checkpoint=_checkpoint()), 2, ended_at=T1)
    new = resume_session(
        previous,
        new_session_id='sess-2',
        started_at='2026-10-20T10:00:00Z',
        desktop_identity='desk-2',
        log_scope='scope-2',
    )
    assert new.checkpoint == previous.checkpoint
    assert new.session_id == 'sess-2'
    assert new.ended_at is None
    assert new.output_folder_intent is None
    assert previous.ended_at == T1
    assert previous.output_folder_intent is not None


def test_resume_after_crash_and_empty_session():
    crashed = _session(checkpoint=_checkpoint())
    resumed1 = resume_session(
        crashed,
        new_session_id='sess-res-1',
        started_at='2026-10-20T10:00:00Z',
        desktop_identity='desk-2',
        log_scope='scope-2',
    )
    assert resumed1.checkpoint == crashed.checkpoint

    empty_closed = close_session(_session(checkpoint=_checkpoint()), 0, ended_at=T1)
    resumed2 = resume_session(
        empty_closed,
        new_session_id='sess-res-2',
        started_at='2026-10-20T10:00:00Z',
        desktop_identity='desk-2',
        log_scope='scope-2',
    )
    assert resumed2.checkpoint == empty_closed.checkpoint

    no_cp = _session()
    resumed3 = resume_session(
        no_cp,
        new_session_id='sess-res-3',
        started_at='2026-10-20T10:00:00Z',
        desktop_identity='desk-2',
        log_scope='scope-2',
    )
    assert resumed3.checkpoint is None


def test_resume_rejects_reused_id_and_bad_fields():
    s = _session()
    with pytest.raises(AppSessionError) as exc_info1:
        resume_session(
            s,
            new_session_id='sess-1',
            started_at='2026-10-20T10:00:00Z',
            desktop_identity='desk-2',
            log_scope='scope-2',
        )
    assert _code(exc_info1) == SESSION_ID_REUSED

    for bad in ['', '  ', None]:
        with pytest.raises(AppSessionError) as exc:
            resume_session(
                s,
                new_session_id=bad,
                started_at='2026-10-20T10:00:00Z',
                desktop_identity='desk-2',
                log_scope='scope-2',
            )
        assert _code(exc) == INVALID_SESSION

        with pytest.raises(AppSessionError) as exc:
            resume_session(
                s,
                new_session_id='sess-new',
                started_at='2026-10-20T10:00:00Z',
                desktop_identity=bad,
                log_scope='scope-2',
            )
        assert _code(exc) == INVALID_SESSION

        with pytest.raises(AppSessionError) as exc:
            resume_session(
                s,
                new_session_id='sess-new',
                started_at='2026-10-20T10:00:00Z',
                desktop_identity='desk-2',
                log_scope=bad,
            )
        assert _code(exc) == INVALID_SESSION

    with pytest.raises(AppSessionError) as exc:
        resume_session(
            s,
            new_session_id='sess-new',
            started_at='garbage',
            desktop_identity='desk-2',
            log_scope='scope-2',
        )
    assert _code(exc) == INVALID_SESSION

    with pytest.raises(TypeError):
        resume_session(
            'not-session',
            new_session_id='sess-new',
            started_at='2026-10-20T10:00:00Z',
            desktop_identity='desk-2',
            log_scope='scope-2',
        )


def test_checkpoint_validation():
    for bad_bid in ['', '  ', None, 5]:
        with pytest.raises(AppSessionError) as exc:
            SessionCheckpoint(batch_id=bad_bid)
        assert _code(exc) == INVALID_CHECKPOINT

    with pytest.raises(AppSessionError) as exc:
        SessionCheckpoint('batch-1', job_checkpoints=[JobCheckpoint('job-1')])
    assert _code(exc) == INVALID_CHECKPOINT

    with pytest.raises(AppSessionError) as exc:
        SessionCheckpoint('batch-1', job_checkpoints=('not-job-checkpoint',))
    assert _code(exc) == INVALID_CHECKPOINT

    with pytest.raises(AppSessionError) as exc:
        SessionCheckpoint('batch-1', job_checkpoints=(JobCheckpoint('job-1'), JobCheckpoint('job-1')))
    assert _code(exc) == INVALID_CHECKPOINT

    for bad_jid in ['', '  ', None, 5]:
        with pytest.raises(AppSessionError) as exc:
            JobCheckpoint(job_id=bad_jid)
        assert _code(exc) == INVALID_CHECKPOINT

    for bad_srid in ['', '  ', 5]:
        with pytest.raises(AppSessionError) as exc:
            JobCheckpoint('job-1', last_stage_run_id=bad_srid)
        assert _code(exc) == INVALID_CHECKPOINT


def test_complete_log_ref_is_accepted():
    ref = LogRef('sess-1', 'job-1', 'script', 'corr-1')
    assert ref.session_id == 'sess-1'
    with pytest.raises(FrozenInstanceError):
        ref.job_id = 'job-2'


@pytest.mark.parametrize('field', ['session_id', 'job_id', 'stage', 'correlation_id'])
@pytest.mark.parametrize('bad', [None, '', '  ', 5])
def test_log_ref_missing_any_component_is_rejected(field, bad):
    kwargs = {
        'session_id': 'sess-1',
        'job_id': 'job-1',
        'stage': 'script',
        'correlation_id': 'corr-1',
    }
    kwargs[field] = bad
    with pytest.raises(AppSessionError) as exc_info:
        LogRef(**kwargs)
    assert _code(exc_info) == INVALID_LOG_REF


def test_make_log_ref_binds_session_id():
    ref = make_log_ref(_session(), job_id='job-1', stage='script', correlation_id='corr-1')
    assert ref == LogRef('sess-1', 'job-1', 'script', 'corr-1')

    with pytest.raises(AppSessionError) as exc_info1:
        make_log_ref(_session(), job_id='job-1', stage='', correlation_id='corr-1')
    assert _code(exc_info1) == INVALID_LOG_REF

    with pytest.raises(AppSessionError) as exc_info2:
        make_log_ref(_session(), job_id='job-1', stage='script', correlation_id=None)
    assert _code(exc_info2) == INVALID_LOG_REF

    with pytest.raises(TypeError):
        make_log_ref('not-session', job_id='job-1', stage='script', correlation_id='corr-1')


def test_module_imports_only_stdlib():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or '').split('.')[0])
            assert not (node.module or '').startswith('controlplane')
    assert roots <= {'__future__', 'dataclasses', 'datetime'}
