"""CP7-10 / RG-09: một lô 1 video trên ngăn xếp thật (launcher, PostgreSQL, Temporal, 9Router, Drive, GPU).

Trần chi phí: <= 25 lời gọi AI, ledger +3 USD, Drive <= 200 MiB, <= 2 giờ. Cách dừng: `python tools/launcher/launcher.py stop`
(driver luôn dừng ở cuối). Giữa lúc render chạy stop rồi start đúng một lần. Không mock; driver không ghi DB và không làm thay production: thư mục staging, media seed và render config do `launcher start` tự tạo, driver chỉ đọc.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8')

REPO = Path(__file__).resolve().parents[2]
for _path in (REPO / 'tools' / 'real', REPO / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pytest  # noqa: E402

import cp7_batch_driver as d  # noqa: E402
import cp7_common as c  # noqa: E402

REPORT = REPO / 'docs' / 'delivery-evidence' / 'cp7-10' / 'report.md'
DRIVER_FILE = REPO / 'tools' / 'real' / 'cp7_batch_driver.py'
SELF = Path(__file__).resolve()
DEADLINE = c.Deadline(d.RUN_DEADLINE_SECONDS)


@pytest.fixture(scope='module')
def batch_run(tmp_path_factory):
    work = tmp_path_factory.mktemp('cp7_rg09')
    try:
        return d.run_batch(work, DEADLINE)
    except d.BlockedError as exc:
        pytest.fail(str(exc))


def _pass(emit, item, *details):
    emit(c.report_line('RG-09', item, 'PASS'))
    for detail in details:
        assert detail.isascii()
        emit('- ' + item + ': ' + detail)


def _stage(name, row):
    return f'{name}({d.STAGE_LABELS[name]})={row["status"]}/attempt{row["attempt"]}'


# --- test thuần (không chạm ngăn xếp thật) -----------------------------------------------------------------------

def test_unit_resume_rejects_late_ready():
    assert d.evaluate_resume({}, {}, 300)['ready_ok'] is True
    for bad in (301, 300.01, None, True, -1):
        assert d.evaluate_resume({}, {}, bad)['ready_ok'] is False


def test_unit_find_reruns_flags_attempt_change():
    before = {'analyze': {'status': 'SUCCEEDED', 'attempt': 1, 'stage_run_id': 'a'},
              'render': {'status': 'RUNNING', 'attempt': 1, 'stage_run_id': 'r'}}
    same = {k: dict(v) for k, v in before.items()}
    assert d.find_reruns(before, same) == []
    for change in ({'attempt': 2}, {'status': 'RUNNING'}, {'stage_run_id': 'b'}):
        after = {k: dict(v) for k, v in before.items()}
        after['analyze'].update(change)
        assert d.find_reruns(before, after) == ['analyze']
    assert d.find_reruns(before, {'render': dict(before['render'])}) == ['analyze']
    after = {k: dict(v) for k, v in before.items()}
    after['render']['attempt'] = 3
    assert d.find_reruns(before, after) == []


def test_unit_budget_violations():
    assert d.budget_violations(25, '3', d.DRIVE_CAP_BYTES, 7200) == []
    assert d.budget_violations(26, 0, 0, 0) == ['ai_calls']
    assert d.budget_violations(0, '3.01', 0, 0) == ['ledger_usd']
    assert d.budget_violations(0, 0, d.DRIVE_CAP_BYTES + 1, 0) == ['drive_bytes']
    assert d.budget_violations(0, 0, 0, 7201) == ['elapsed']


def test_unit_trace_missing():
    full = {k: 'x' for k in d.TRACE_KEYS}
    assert d.trace_missing(full) == []
    gone = dict(full)
    del gone['snapshot_id']
    assert d.trace_missing(gone) == ['snapshot_id']
    for empty in ('', [], {}, None):
        assert d.trace_missing({**full, 'model_refs': empty}) == ['model_refs']


def test_unit_no_batch_retry_loop():
    text = DRIVER_FILE.read_text(encoding='utf-8')
    for name in ('MAX_BATCH_ATTEMPTS', 'AI_CALLS_PER_JOB_RESERVE', 'RETRY_STAGES', 'RETRY_CODES', 'should_retry_batch'):
        assert name not in text
    assert text.count('session.post_batch(1)') == 1


def test_unit_format_failed_stage():
    assert d.format_failed_stage(None) == 'stage=none'
    assert d.format_failed_stage(('script', 'FAILED_FINAL', 'ai_output_schema_violation', 'GenerateScript', '{"hook": "required"}')) == 'stage=script status=FAILED_FINAL activity=GenerateScript code=ai_output_schema_violation field_errors={"hook": "required"}'


def test_unit_format_render_config():
    rows = [('preset', 'bold-yellow', 'PUBLISHED'), ('policy', 'quality', 'DRAFT')]
    assert d.format_render_config(rows) == 'render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=MISSING policy/quality=DRAFT]'
    missing = 'render_config=[preset/bold-yellow=MISSING preset/output-profile=MISSING policy/quality=MISSING]'
    assert d.format_render_config([]) == missing
    assert d.format_render_config(None) == missing
    assert d.RENDER_CONFIG_SCOPES == (('preset', 'bold-yellow'), ('preset', 'output-profile'), ('policy', 'quality'))
    text = DRIVER_FILE.read_text(encoding='utf-8')
    assert 'collect_render_config(db) + ' in text
    assert text.count('session.post_batch(1)') == 1


def test_unit_stage_labels_cover_all_stages():
    assert len(d.STAGES) == 11
    assert all(name in d.STAGE_LABELS for name in d.STAGES)


def test_unit_driver_is_read_only():
    text = DRIVER_FILE.read_text(encoding='utf-8')
    assert not re.search(r'(?i)\b(insert\s+into|update\s+controlplane|delete\s+from)\b', text)
    assert not re.search(r'(?m)^\s*(from\s+\S+\s+)?import\s+.*\b(Fake|InMemory)', text)
    assert 'default_transaction_read_only=on' in text
    assert 'CERT_NONE' not in text and '_create_unverified_context' not in text


def test_unit_driver_never_prints_launch_url():
    text = DRIVER_FILE.read_text(encoding='utf-8')
    assert not re.search(r'print\([^)]*(launch_path|launch2|\burl\b|raw)', text)


def test_unit_driver_does_not_call_import_seed():
    text = DRIVER_FILE.read_text(encoding='utf-8')
    for name in ('import_seed', 'make_seed_media', 'ensure_seed_media', 'seed_import'):
        assert name not in text, name
    assert not hasattr(d, 'ensure_seed_media')


def test_unit_driver_does_not_ensure_voice_staging():
    text = DRIVER_FILE.read_text(encoding='utf-8')
    for name in ('ensure_voice_staging', 'staging_voice'):
        assert name not in text, name
    assert not hasattr(d, 'ensure_voice_staging')


def test_unit_format_diagnostic():
    token = 'ya29.' + 'A' * 30
    diag = {'job': {'status': 'FAILED_FINAL', 'wait_reason': None, 'revision': 3},
            'stages': [{'stage': 'media_select', 'attempt': 1, 'status': 'FAILED_FINAL', 'code': 'INPUT_NOT_READY',
                        'wait_reason': None, 'message': 'seed_media_missing'}]}
    text = d.format_diagnostic(diag, 'boom cap' + '=abc123 ' + token)
    assert 'job=FAILED_FINAL' in text
    assert 'media_select#1=FAILED_FINAL/INPUT_NOT_READY/msg=seed_media_missing' in text
    assert 'abc123' not in text and token not in text
    assert len(text) <= 1500
    empty = d.format_diagnostic({'job': None, 'stages': []}, '')
    assert 'no_stage_rows' in empty and 'job=None' in empty
    assert d.serve_log_tail(SELF.parent / 'khong_co_tep.log') == 'no_serve_log'


_FULL_RENDER_CONFIG = [('preset', 'bold-yellow', 'PUBLISHED'), ('preset', 'output-profile', 'PUBLISHED'), ('policy', 'quality', 'PUBLISHED')]


def test_unit_render_config_published():
    full = _FULL_RENDER_CONFIG
    assert d.render_config_published(full) is True
    assert d.render_config_published(full[:2]) is False
    assert d.render_config_published(full[:2] + [('policy', 'quality', 'DRAFT')]) is False
    assert d.render_config_published([]) is False
    assert d.render_config_published(None) is False


def test_unit_require_render_config_blocks():
    class _Db:
        def __init__(self, rows):
            self.rows = rows

        def render_config_status(self):
            return self.rows

    class _Broken:
        def render_config_status(self):
            raise OSError('x')

    full = _FULL_RENDER_CONFIG
    assert d.require_render_config(_Db(full)) == 'render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]'
    with pytest.raises(d.BlockedError) as info:
        d.require_render_config(_Db(full[:1]))
    assert str(info.value).startswith('BLOCKED: ')
    assert 'preset/output-profile=MISSING' in str(info.value)
    with pytest.raises(d.BlockedError):
        d.require_render_config(_Broken())
    text = DRIVER_FILE.read_text(encoding='utf-8')
    assert text.index('result.render_config = require_render_config(db)') < text.index('session.post_batch(1)')


def test_unit_launcher_seed_line():
    token = 'ya29.' + 'A' * 30
    out = 'start ok\nseed media loaded (idempotent)\nOpen https://x/launch?cap' + '=abc123\nSeed done ' + token
    line = d.launcher_seed_line(out)
    assert 'seed media loaded (idempotent)' in line and 'Seed done' in line
    assert token not in line and 'start ok' not in line and 'abc123' not in line
    assert d.launcher_seed_line('start ok') == 'no_seed_line'
    assert d.launcher_seed_line('') == 'no_seed_line'


def test_unit_seed_counts_read_only():
    class _Db(d.ReadOnlyDb):
        def __init__(self):
            self.workspace_id = 'w'
            self.calls = []

        def query(self, sql, *params):
            self.calls.append((sql, params))
            return [(7, 10, 22)]

    db = _Db()
    assert db.seed_counts() == {'sources': 7, 'hooks': 10, 'media_assets': 22}
    assert db.calls[0][0].lstrip().upper().startswith('SELECT')
    assert len(db.calls[0][1]) == 2


# --- RG-09 trên ngăn xếp thật ------------------------------------------------------------------------------------

def test_rg09_stages_succeeded(batch_run, emit):
    for name in d.STAGES:
        assert batch_run.final_stages.get(name, {}).get('status') == 'SUCCEEDED', name
    assert batch_run.final_job_status == 'COMPLETED'
    assert batch_run.ledger_row is not None
    detail = ' '.join(_stage(n, batch_run.final_stages[n]) for n in d.STAGES)
    _pass(emit, 'stages_succeeded', detail,
          f'elapsed_s={batch_run.elapsed_seconds:.0f} final_batch_status={batch_run.final_batch_status} '
          '(so do, OI-PW-E2E-01: production chua co writer CREATED->RUNNING nen khong bat buoc COMPLETED_TARGET)')


def test_rg09_no_fake_adapters(batch_run, emit):
    composition = batch_run.composition
    assert composition['violations'] == []
    assert composition['objects_scanned'] > 0
    _pass(emit, 'no_fake_adapters', f'objects_scanned={composition["objects_scanned"]} violations=0 source=launcher.load_app '
          f'production_py_sha256={composition["production_py_sha256"]} read_only=True')


def test_rg09_qc_hard_gates(batch_run, emit):
    qc = batch_run.qc
    assert qc['hard_total'] > 0 and qc['hard_failed'] == 0 and qc['hard_passed'] == qc['hard_total']
    _pass(emit, 'qc_hard_gates', f'hard_total={qc["hard_total"]} hard_passed={qc["hard_passed"]} not_applicable={qc["not_applicable"]}')


def test_rg09_cloud_verified_before_count(batch_run, emit):
    drive = [loc for loc in batch_run.locations if 'drive' in loc['backend_ref'].lower()]
    assert len(drive) == 1 and drive[0]['state'] == 'VERIFIED' and drive[0]['verification_evidence_ref']
    assert batch_run.drive_check['md5_match'] and batch_run.drive_check['sha256_match']
    assert batch_run.ledger_row['output_artifact_hash'] == drive[0]['sha256_hash']
    if batch_run.verified_before_complete:
        ordering = 'sampled'
    elif drive[0]['updated_at'] <= batch_run.ledger_row['completed_at']:
        ordering = 'timestamps'
    else:
        pytest.fail('BLOCKED: chưa chứng minh được thứ tự verified trước khi đếm')
    _pass(emit, 'cloud_verified_before_count', f'md5_match=True sha256_match=True ledger_count=1 ordering={ordering}')


def test_rg09_cleanup_after_verify(batch_run, emit):
    assert not batch_run.cleanup_before_verified
    verified = {loc['artifact_version_id'] for loc in batch_run.locations
                if 'drive' in loc['backend_ref'].lower() and loc['state'] == 'VERIFIED' and loc['verification_evidence_ref']}
    cleaned = [loc for loc in batch_run.locations if 'drive' not in loc['backend_ref'].lower()
               and loc['state'] in d.CLEANUP_STATES]
    for loc in cleaned:
        assert loc['artifact_version_id'] in verified
    _pass(emit, 'cleanup_after_verify', f'cleaned_locations={len(cleaned)} cleanup_before_verified=False')


def test_rg09_plan_unchanged(batch_run, emit):
    assert batch_run.plan_before and batch_run.plan_before == batch_run.plan_after
    assert batch_run.render_matches is True
    plan = batch_run.plan_after
    _pass(emit, 'plan_unchanged', f'digest_equal=True script_sha256={plan["script_sha256"][:8]} '
          f'media_count={len(plan["media_sha256s"])} render_matches_plan=True')


def test_rg09_resume_300s(batch_run, emit):
    if not batch_run.render_seen_running:
        pytest.fail('BLOCKED: render không được thấy ở RUNNING; chưa chứng minh resume giữa lúc render')
    verdict = d.evaluate_resume(batch_run.before_stop, batch_run.final_stages, batch_run.ready_seconds)
    assert verdict['ready_ok'], f'resume ready {batch_run.ready_seconds}s > {d.READY_LIMIT_SECONDS}s'
    assert verdict['completed_stages'] >= 7
    _pass(emit, 'resume_300s', f'ready_seconds={batch_run.ready_seconds:.1f} limit=300 '
          f'stop_attempts={batch_run.stop_attempts} stopped_in_render=True')


def test_rg09_no_rerun_completed(batch_run, emit):
    assert batch_run.render_seen_running, 'BLOCKED: render không được thấy ở RUNNING'
    verdict = d.evaluate_resume(batch_run.before_stop, batch_run.final_stages, batch_run.ready_seconds)
    assert verdict['reruns'] == []
    assert d.find_reruns(batch_run.before_stop, batch_run.after_start) == []
    _pass(emit, 'no_rerun_completed', f'completed_before_stop={verdict["completed_stages"]} reruns=0 attempts_unchanged=True')


def test_rg09_trace_complete(batch_run, emit):
    trace = batch_run.trace
    assert d.trace_missing(trace) == []
    _pass(emit, 'trace_complete', f'snapshot_id_present=True model_refs={len(trace["model_refs"])} '
          f'prompt_refs={len(trace["prompt_refs"])} config_revision={trace["config_revision"]} '
          f'profile_sha256={trace["profile_sha256"][:8]}')


def test_rg09_secret_scan(batch_run, emit):
    texts = [SELF.read_text(encoding='utf-8'), DRIVER_FILE.read_text(encoding='utf-8')]
    if REPORT.exists():
        texts.append(REPORT.read_text(encoding='utf-8'))
    for text in texts:
        assert c.scan_secrets(text) == []
        assert not re.search(r'[?&]cap=', text)
        assert 'cp_session' + '=' not in text
    _pass(emit, 'secret_scan', 'match_count=0 khong_doc_Credentials=True capability_khong_ghi=True')


def test_rg09_budget_envelope(batch_run, emit):
    assert d.budget_violations(batch_run.ai_calls, batch_run.spent_usd, batch_run.drive_bytes, batch_run.elapsed_seconds) == []
    emit(f'- budget: attempts={len(batch_run.attempts)} ai_calls={batch_run.ai_calls} cap=25 spent_usd={batch_run.spent_usd} ceiling_usd=3 '
         f'drive_bytes={batch_run.drive_bytes} cap_bytes=209715200 elapsed_s={batch_run.elapsed_seconds:.0f} '
         f'limit_s=7200 remaining_s={DEADLINE.remaining():.0f}')
    emit('- seed: launcher_line=' + batch_run.launcher_seed_line + ' seed_counts=' + json.dumps(batch_run.seed_counts, sort_keys=True) + ' render_config=' + batch_run.render_config)
