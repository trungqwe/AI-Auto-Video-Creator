"""CP7-11 / RG-10: đêm chạy 100 video trên ngăn xếp thật. Các test_unit_* ở đầu tệp là test thuần, không chạm ngăn xếp; test_rg10_* ở cuối tệp chạy lô thật (trần: ledger đêm +25 USD, tháng ≤ 50 USD, Drive ≤ 12 GiB, 12 giờ 15 phút; cách dừng `python tools/launcher/launcher.py stop`).
Mặc định (không đặt CP7_RG10_LIVE=1) tệp không chạy lô thật: các test_rg10_* bị bỏ qua và test_unit_recorded_report_rg10 kiểm bằng chứng RG-10 đã ghi trong report.md; chỉ khi đặt CP7_RG10_LIVE=1 mới chạy lô thật.
"""
from __future__ import annotations

import json
import os
import re
import sys
import types
import urllib.error
from datetime import date, datetime, timezone
from decimal import Decimal
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
import cp7_overnight_monitor as m  # noqa: E402

REPORT = REPO / 'docs' / 'delivery-evidence' / 'cp7-11' / 'report.md'
MONITOR_FILE = REPO / 'tools' / 'real' / 'cp7_overnight_monitor.py'
SELF = Path(__file__).resolve()
GIB = 1024 ** 3
PROFILE = json.loads(d.PROFILE_JSON.read_text(encoding='utf-8'))

LIVE = os.environ.get('CP7_RG10_LIVE') == '1'
RG10_REQUIRED = ('valid_synced_100', 'within_12h', 'auto_ratio_95', 'no_vanished_jobs', 'failure_isolated', 'resume_300s_midrun',
                 'no_rerun_completed', 'cost_under_cap', 'working_set_cap', 'drive_quota_ok', 'stage_metrics', 'secret_scan')


def _ascii_line(line):
    """Chuỗi in ra console Windows chỉ gồm ASCII."""
    return str(line).encode('ascii', 'backslashreplace').decode('ascii')


def _pass(emit, item, *details):
    emit(c.report_line('RG-10', item, 'PASS'))
    for detail in details:
        assert detail.isascii()
        emit('- ' + item + ': ' + detail)


# --- test thuần (không chạm ngăn xếp thật) -----------------------------------------------------------------------

def test_unit_constants_follow_profile():
    assert m.TARGET_VIDEOS == PROFILE['batch']['target']['value']['overnight_trial']
    assert m.VIDEOS_PER_NEWS == PROFILE['batch']['videos_per_news_per_round']['value']
    assert m.WORKING_SET_CAP_BYTES == PROFILE['working_set']['max_bytes']['value']
    assert m.RESUME_LIMIT_SECONDS == PROFILE['resume']['ready_within_seconds']['value'] == 300
    assert m.MONTH_COST_CAP_USD == Decimal(str(PROFILE['budget']['monthly_limit']['value']))
    assert m.WARN_COST_USD == m.MONTH_COST_CAP_USD * Decimal(str(PROFILE['budget']['warn_at_ratio']['value']))
    assert PROFILE['drive']['quota_reserve_ratio']['value'] == 0.2
    assert (m.DEADLINE_SECONDS, m.WITHIN_SECONDS, m.SAMPLE_SECONDS) == (44100, 43200, 300)
    assert m.NOT_FOUND_URL.startswith('https://')


def test_unit_drive_quota_requirement():
    low = m.drive_quota_requirement(15 * GIB, 2 * GIB)
    assert low['ok'] is False
    assert low['free_bytes'] == 13 * GIB
    assert low['required_bytes'] == 15 * GIB
    assert low['unlimited'] is False
    high = m.drive_quota_requirement(100 * GIB, 10 * GIB)
    assert high['ok'] is True
    assert high['required_bytes'] == 32 * GIB
    free = m.drive_quota_requirement(None, 5)
    assert free['ok'] is True
    assert free['unlimited'] is True
    assert free['free_bytes'] is None
    for limit, usage in ((True, 1), (-1, 0), ('5', 0), (10, -1)):
        with pytest.raises(ValueError):
            m.drive_quota_requirement(limit, usage)


def test_unit_parse_storage_quota():
    assert m.parse_storage_quota({'storageQuota': {'limit': '16106127360', 'usage': '1000'}}) == (16106127360, 1000)
    assert m.parse_storage_quota({'storageQuota': {'usage': '7'}}) == (None, 7)
    for bad in ({}, {'storageQuota': 5}, {'storageQuota': {'limit': 'x'}}, None):
        with pytest.raises(ValueError):
            m.parse_storage_quota(bad)


def test_unit_percentile():
    values = list(range(1, 11))
    assert m.percentile(values, 50) == 5
    assert m.percentile(values, 95) == 10
    assert m.percentile([], 50) is None
    assert m.percentile([7], 95) == 7
    for bad in (0, 101):
        with pytest.raises(ValueError):
            m.percentile(values, bad)


def test_unit_stage_metrics():
    rows = [('render', 'SUCCEEDED', 1, 60.0), ('render', 'SUCCEEDED', 1, 120.0), ('render', 'FAILED_RETRYABLE', 1, None),
            ('render', 'SUCCEEDED', 2, 30.0), ('tts', 'SUCCEEDED', 1, None)]
    out = m.stage_metrics(rows)
    assert out['render'] == {'n': 3, 'p50_s': 60.0, 'p95_s': 120.0, 'max_s': 120.0, 'extra_attempts': 1}
    assert out['tts'] == {'n': 0, 'p50_s': None, 'p95_s': None, 'max_s': None, 'extra_attempts': 0}
    assert set(out) == {'render', 'tts'}
    assert m.stage_metrics([]) == {}


def test_unit_parse_vram_mib():
    assert m.parse_vram_mib('1024\n2048\n') == 2048
    assert m.parse_vram_mib(' 512 ') == 512
    for bad in ('', 'N/A', 'abc'):
        with pytest.raises(ValueError):
            m.parse_vram_mib(bad)


def test_unit_wait_clock():
    w = m.WaitClock()
    assert w.seconds == 0
    w.observe(0, 0)
    w.observe(30, 2)
    w.observe(60, 1)
    w.observe(90, 0)
    assert w.seconds == 60
    w2 = m.WaitClock()
    w2.observe(10, 0)
    with pytest.raises(ValueError):
        w2.observe(5, 0)


def test_unit_should_resume():
    assert m.should_resume(40, 100, False, True) is True
    assert m.should_resume(39, 100, False, True) is False
    assert m.should_resume(39, 21600, False, True) is True
    assert m.should_resume(0, 21600, False, False) is True
    assert m.should_resume(40, 100, False, False) is False
    assert m.should_resume(50, 100, True, True) is False


def test_unit_month_window_start():
    assert m.month_window_start(datetime(2026, 10, 31, 18, 0, tzinfo=timezone.utc)) == datetime(2026, 10, 31, 17, 0, tzinfo=timezone.utc)
    assert m.month_window_start(datetime(2026, 10, 31, 16, 59, tzinfo=timezone.utc)) == datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        m.month_window_start(datetime(2026, 11, 2, 3, 0))


def test_unit_cost_violations():
    assert m.cost_violations('25', '50', 12 * GIB, 44100) == []
    assert m.cost_violations(Decimal('25.01'), '50', 12 * GIB, 44100) == ['night_usd']
    assert m.cost_violations('25', '50.01', 12 * GIB, 44100) == ['month_usd']
    assert m.cost_violations('25', '50', 12 * GIB + 1, 44100) == ['drive_bytes']
    assert m.cost_violations('25', '50', 12 * GIB, 44101) == ['elapsed']
    assert m.cost_violations('26', '51', 13 * GIB, 44101) == ['night_usd', 'month_usd', 'drive_bytes', 'elapsed']


def test_unit_auto_ratio_ok():
    assert m.auto_ratio_ok(95, 100) is True
    assert m.auto_ratio_ok(94, 100) is False
    assert m.auto_ratio_ok(0, 0) is False
    assert m.auto_ratio_ok(190, 200) is True
    assert m.auto_ratio_ok(19, 20) is True
    assert m.auto_ratio_ok(18, 19) is False
    assert m.auto_ratio_ok(100, 0) is False


def test_unit_audit_jobs():
    jobs = [('j1', 'COMPLETED'), ('j2', 'FAILED_FINAL'), ('j3', 'ACTIVE'), ('j4', 'BOGUS'), ('j5', 'CREATED')]
    out = m.audit_jobs(jobs, {'j1': 11, 'j2': 3, 'j3': 0, 'j4': 1}, {'j2'}, {'j1', 'j9'})
    assert out == ['failed_without_problem:j2', 'no_stage_rows:j3', 'unknown_status:j4', 'vanished:j9']


def test_unit_failure_causes():
    rows = [('j1', ('tts', 'FAILED_FINAL', 'TTS_TIMEOUT', 'synthesize', '{}')), ('j2', ('tts', 'FAILED_FINAL', 'TTS_TIMEOUT', 'synthesize', '{}')),
            ('j3', ('align', 'OUTCOME_UNKNOWN', 'X Y', None, '')), ('j4', None)]
    assert m.failure_causes(rows) == [{'stage': 'tts', 'code': 'TTS_TIMEOUT', 'activity': 'synthesize', 'n': 2},
                                      {'stage': 'align', 'code': 'X?Y', 'activity': 'none', 'n': 1},
                                      {'stage': 'none', 'code': 'none', 'activity': 'none', 'n': 1}]
    assert m.failure_causes([]) == []


def test_unit_collection_isolation():
    runs = [('a', 'COMPLETED'), ('a', 'COMPLETED_PARTIAL'), ('nf', 'FAILED_FINAL'), ('nf', 'FAILED_FINAL')]
    assert m.collection_isolation(runs, 'nf') == {'target_runs': 2, 'target_failed': 2, 'others_ok': 2,
                                                  'completed_after_failure': 0, 'isolated': False}
    assert m.collection_isolation(runs, 'nf', 3) == {'target_runs': 2, 'target_failed': 2, 'others_ok': 2,
                                                     'completed_after_failure': 3, 'isolated': True}
    none = m.collection_isolation([('a', 'COMPLETED')], 'nf', 5)
    assert none['target_runs'] == 0
    assert none['isolated'] is False
    bad = m.collection_isolation([('a', 'FAILED_FINAL'), ('nf', 'FAILED_FINAL')], 'nf', 5)
    assert bad['others_ok'] == 0
    assert bad['isolated'] is False
    alone = m.collection_isolation([('nf', 'FAILED_FINAL')], 'nf', 5)
    assert alone['others_ok'] == 0
    assert alone['isolated'] is False


def test_unit_business_date_vn():
    assert m.business_date_vn(datetime(2026, 11, 1, 18, 30, tzinfo=timezone.utc)) == date(2026, 11, 2)
    assert m.business_date_vn(datetime(2026, 11, 1, 16, 59, tzinfo=timezone.utc)) == date(2026, 11, 1)
    with pytest.raises(ValueError):
        m.business_date_vn(datetime(2026, 11, 2))


def test_unit_manual_actions():
    calls = [('GET', '/v1/batch-settings'), ('POST', '/v1/batches'), ('GET', '/v1/batches/b1'), ('GET', '/v1/batches/b1')]
    assert m.manual_actions(calls, 'b1') == []
    assert m.manual_actions(calls + [('POST', '/v1/batches')], 'b1') == ['POST /v1/batches']
    assert m.manual_actions(calls + [('PUT', '/v1/configs/x')], 'b1') == ['PUT /v1/configs/x']


def test_unit_format_sample():
    sample = {'t_utc': '2026-11-02T10:00:00Z', 'elapsed_s': 305.4, 'batch_status': 'RUNNING', 'jobs': {'ACTIVE': 4, 'COMPLETED': 7},
              'valid_synced': 7, 'running_stages': 5, 'night_usd': '0', 'month_usd': '1.5', 'ai_calls': 80,
              'disk_free_data_bytes': 50 * GIB, 'disk_free_system_bytes': 20 * GIB, 'working_set_bytes': 3 * GIB,
              'vram_used_mib': 8123, 'vram_error': None}
    line = m.format_sample(sample)
    assert line == ('- sample t=2026-11-02T10:00:00Z elapsed_s=305 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":7} valid=7 running_stages=5 '
                    'night_usd=0 month_usd=1.5 ai_calls=80 data_free_gib=50.0 sys_free_gib=20.0 working_set_gib=3.00 vram_mib=8123')
    assert line.isascii()
    sparse = m.format_sample({'t_utc': '2026-11-02T10:00:00Z'})
    assert ' batch=- ' in sparse
    assert 'vram_mib=-' in sparse
    assert sparse.isascii()
    err = m.format_sample({'t_utc': 'T', 'sample_error': 'OSError'})
    assert err == '- sample t=T sample_error=OSError'
    assert m.format_sample({'t_utc': 'TĐ', 'batch_status': 'Đ'}).isascii()


def test_unit_dir_size_bytes(tmp_path):
    (tmp_path / 'a.bin').write_bytes(b'abc')
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'b.bin').write_bytes(b'12345')
    assert m.dir_size_bytes(tmp_path) == 8
    assert m.dir_size_bytes(tmp_path / 'missing') == 0


# --- OvernightDb: truy vấn chỉ đọc -------------------------------------------------------------------------------

class _Rec(m.OvernightDb):
    def __init__(self, rows):
        self.workspace_id = 'w'
        self.rows = rows
        self.calls = []

    def query(self, sql, *params):
        self.calls.append((sql, params))
        return self.rows


_DB_CASES = [
    ('batch_job_counts', ('b1',), [('ACTIVE', 4), ('COMPLETED', 7)], {'ACTIVE': 4, 'COMPLETED': 7}),
    ('batch_jobs', ('b1',), [('j1', 'COMPLETED'), ('j2', 'ACTIVE')], [('j1', 'COMPLETED'), ('j2', 'ACTIVE')]),
    ('valid_synced_count', ('b1',), [(7,)], 7),
    ('running_busy', ('b1',), [(2,)], True),
    ('running_busy', ('b1',), [(0,)], False),
    ('running_stage_count', ('b1',), [(3,)], 3),
    ('wait_provider_jobs', ('b1',), [(1,)], 1),
    ('completed_job_ids', ('b1',), [('j2',), ('j1',)], ['j1', 'j2']),
    ('stage_row_counts', ('b1',), [('j1', 11), ('j2', 3)], {'j1': 11, 'j2': 3}),
    ('problem_missing', ('b1',), [('j2',)], {'j2'}),
    ('stage_durations', ('b1',), [('render', 'SUCCEEDED', 1, Decimal('60.5')), ('tts', 'SUCCEEDED', 1, None)],
     [('render', 'SUCCEEDED', 1, 60.5), ('tts', 'SUCCEEDED', 1, None)]),
    ('job_lead_seconds', ('b1',), [(120.0,), (Decimal('60'),)], [120.0, 60.0]),
    ('batch_drive_bytes', ('b1',), [(5,)], 5),
    ('collection_runs', (date(2026, 11, 2), datetime(2026, 11, 1, 18, 4, tzinfo=timezone.utc)), [('s1', 'COMPLETED')],
     [('s1', 'COMPLETED')]),
    ('videos_completed_after_source_failure', ('b1', 's9', datetime(2026, 11, 1, 18, 4, tzinfo=timezone.utc)), [(4,)], 4),
    ('source_id_for', ('https://x/',), [('s9',)], 's9'),
    ('source_id_for', ('https://x/',), [], None),
]


@pytest.mark.parametrize('name,args,rows,expected', _DB_CASES)
def test_unit_overnight_db_methods(name, args, rows, expected):
    db = _Rec(rows)
    result = getattr(db, name)(*args)
    assert result == expected
    assert type(result) is type(expected)
    assert len(db.calls) == 1
    sql, params = db.calls[0]
    assert sql.lstrip().upper().startswith(('SELECT', 'WITH'))
    assert 'workspace_id = %s' in sql
    assert args[0] in params


def test_unit_valid_synced_count_requires_cloud_verified_evidence():
    db = _Rec([(0,)])
    db.valid_synced_count('b1')
    sql = db.calls[0][0]
    for needle in ('cp_completion_ledger', 'cp_artifact_locations', "l.state = 'VERIFIED'", "l.backend_ref = 'cloud'",
                   'starts_with(l.verification_evidence_ref', 'cloud_location_verification_ref'):
        assert needle in sql, needle


def test_unit_collection_queries_use_business_day():
    since = datetime(2026, 11, 1, 18, 4, tzinfo=timezone.utc)
    db = _Rec([('s1', 'COMPLETED')])
    db.collection_runs(date(2026, 11, 2), since)
    sql = db.calls[0][0]
    assert 'r.business_date >= %s' in sql
    assert "r.run_kind = 'PERIODIC'" in sql
    assert db.calls[0][1] == (date(2026, 11, 2), since)
    db2 = _Rec([(1,)])
    db2.videos_completed_after_source_failure('b1', 's9', since)
    sql2 = db2.calls[0][0]
    assert 'cp_completion_ledger' in sql2
    assert 'cp_collection_runs' in sql2
    assert "r.status = 'FAILED_FINAL'" in sql2
    assert 'cl.completed_at > (SELECT max(r.updated_at)' in sql2
    assert db2.calls[0][1] == ('b1', 's9', since)


def test_unit_collection_queries_count_only_runs_created_since_the_launch():
    """CP7-11-FIX2: lượt thu thập của cùng ngày kinh doanh tạo trước phép đo (lô f132d43a: lượt ngày 03/11 tạo 17:13Z ngày 02/11, lô tạo
    07:48Z ngày 03/11) không được làm bằng chứng cô lập lỗi; cả hai truy vấn lọc r.created_at >= mốc khởi launcher."""
    since = datetime(2026, 11, 3, 7, 40, tzinfo=timezone.utc)
    db = _Rec([])
    db.collection_runs(date(2026, 11, 3), since)
    sql, params = db.calls[0]
    assert sql.endswith('AND r.business_date >= %s AND r.created_at >= %s') and params == (date(2026, 11, 3), since)
    db2 = _Rec([(0,)])
    db2.videos_completed_after_source_failure('b1', 's9', since)
    sql2, params2 = db2.calls[0]
    assert 'r.source_id = %s AND r.created_at >= %s AND' in sql2 and params2 == ('b1', 's9', since)
    assert sql2.count('%s') == 4


def test_unit_collection_since_is_taken_before_the_launcher_starts_and_used_by_the_audit():
    text = MONITOR_FILE.read_text(encoding='utf-8')
    body = text[text.index('def run_overnight('):text.index('def audit_run(')]
    marks = ['result.other_workflows_running = d.require_no_other_workflows()', 'result.collection_since = db.db_now()',
             "d.start_capturing(work_dir, 'first')", 'result.window_start = window_start = db.db_now()']
    positions = [body.index(item) for item in marks]
    assert positions == sorted(positions) and body.count('result.collection_since =') == 1
    audit = text[text.index('def audit_run('):]
    assert 'since = run.collection_since if run.collection_since is not None else run.window_start' in audit
    assert 'db.videos_completed_after_source_failure(batch_id, not_found_id, since)' in audit
    assert 'db.collection_runs(business_date_vn(run.window_start), since)' in audit
    assert m.OvernightRun().collection_since is None


def test_unit_session_records_calls():
    s = object.__new__(m.OvernightSession)
    s.cookies = {'csrf_token': 't', 'cp_session': 's'}
    s.calls = []
    s._request = lambda method, path, headers, body: (200, [], '{"max_concurrent_videos": {"default": 6, "min": 1, "max": 10}}')
    assert s.call('GET', '/v1/batch-settings?x=1')[0] == 200
    assert s.calls == [('GET', '/v1/batch-settings')]
    assert s.get_batch_settings() == {'default': 6, 'min': 1, 'max': 10}
    seen = {}

    def post(method, path, headers, body):
        seen['body'] = body
        return 202, [], '{"resource_ref": {"batch_id": "b9"}}'

    s._request = post
    assert s.post_overnight_batch(100, 6) == 'b9'
    assert json.loads(seen['body']) == {'target_completed_videos': 100, 'max_concurrent_videos': 6}
    s._request = lambda method, path, headers, body: (500, [], '')
    with pytest.raises(d.BatchDriverError):
        s.get_batch_settings()
    with pytest.raises(d.BatchDriverError):
        s.post_overnight_batch(100, 6)


# --- nguồn 404, sampler, thứ tự run_overnight --------------------------------------------------------------------

def test_unit_probe_not_found():
    def gone(request, timeout):
        raise urllib.error.HTTPError('u', 404, 'nf', {}, None)

    assert m.probe_not_found('https://x/y', gone) == 404
    assert m.require_not_found_url('https://x/y', gone) == 404

    def ok(request, timeout):
        return types.SimpleNamespace(status=200, close=lambda: None)

    assert m.probe_not_found('https://x/y', ok) == 200
    with pytest.raises(d.BlockedError) as info:
        m.require_not_found_url('https://x/y', ok)
    assert str(info.value).startswith('BLOCKED: ')

    def down(request, timeout):
        raise urllib.error.URLError('x')

    with pytest.raises(d.BlockedError):
        m.probe_not_found('https://x/y', down)


class _SamplerDb:
    def __init__(self, fail=False):
        self.fail = fail

    def batch_job_counts(self, batch_id):
        if self.fail:
            raise OSError('boom')
        return {'ACTIVE': 1}

    def batch_status(self, batch_id):
        return 'RUNNING'

    def valid_synced_count(self, batch_id):
        return 3

    def running_stage_count(self, batch_id):
        return 2

    def ai_invocation_count(self, prefix):
        return 9

    def db_now(self):
        return datetime(2026, 11, 2, tzinfo=timezone.utc)


def _sampler(tmp_path, db=None, vram=lambda: 4096, interval=0.01):
    staging = tmp_path / 'st'
    staging.mkdir(exist_ok=True)
    (staging / 'f.bin').write_bytes(b'1234')
    layout = types.SimpleNamespace(data_dir=tmp_path, staging_dir=staging)
    return m.OvernightSampler(db or _SamplerDb(), 'b1', 'w:b1:video:', 't0', layout, tmp_path / 'tl.jsonl',
                              lambda start: Decimal('1.5'), vram, interval=interval)


def test_unit_sampler(tmp_path):
    s = _sampler(tmp_path)
    sample = s.collect_sample()
    assert sample['valid_synced'] == 3
    assert sample['jobs'] == {'ACTIVE': 1}
    assert sample['vram_used_mib'] == 4096
    assert sample['working_set_bytes'] == 4
    assert sample['night_usd'] == '1.5'
    assert sample['month_usd'] == '1.5'
    assert sample['ai_calls'] == 9
    assert sample['t_utc'].endswith('Z')

    failing = _sampler(tmp_path, _SamplerDb(fail=True)).collect_sample()
    assert failing['sample_error'] == 'OSError'
    assert 't_utc' in failing

    def broken():
        raise RuntimeError('no gpu')

    partial = _sampler(tmp_path, vram=broken).collect_sample()
    assert partial['vram_used_mib'] is None
    assert partial['vram_error'] == 'RuntimeError'
    assert partial['valid_synced'] == 3

    sink = tmp_path / 'tl.jsonl'
    s.write({'batch_status': 'ya29.' + 'A' * 30, 't_utc': 'T'})
    lines = sink.read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])['t_utc'] == 'T'
    assert 'ya29.' not in lines[0]

    sink.unlink()
    import time as _time
    s.start()
    deadline = _time.monotonic() + 5
    while len(s.samples) < 2 and _time.monotonic() < deadline:
        _time.sleep(0.02)
    s.stop()
    assert len(s.samples) >= 2
    assert not s._thread.is_alive()
    assert len(sink.read_text(encoding='utf-8').splitlines()) >= 2
    assert s.latest() is not None


def test_unit_run_overnight_order():
    text = MONITOR_FILE.read_text(encoding='utf-8')
    body = text[text.index('def run_overnight('):text.index('def audit_run(')]
    ordered = ['result.quota = require_drive_quota(db)', 'result.not_found_status = require_not_found_url()',
               'result.pre_stop_attempts = d.stop_until_exited()', 'result.other_workflows_running = d.require_no_other_workflows()',
               "d.start_capturing(work_dir, 'first')", 'result.not_found_source = register_not_found_source(launcher, db, work_dir)',
               'result.render_config = d.require_render_config(db)', 'session.post_overnight_batch(']
    positions = [body.index(item) for item in ordered]
    assert positions == sorted(positions) and len(set(positions)) == len(positions)
    assert body.count('post_overnight_batch(') == 1
    assert body.count('d.require_no_other_workflows()') == 1
    assert 'c.Deadline(DEADLINE_SECONDS)' in body
    assert 'audit_run(db, result, seen_ids)' in body
    first = body.index("d.start_capturing(work_dir, 'first')")
    stop_after_first = body.index('d.stop_until_exited()', first)
    resume = body.index("d.start_capturing(work_dir, 'resume')")
    assert resume > stop_after_first > first
    assert body.rindex('d.stop_until_exited()') > body.rindex('finally:')


def test_unit_monitor_is_read_only():
    text = MONITOR_FILE.read_text(encoding='utf-8')
    assert not re.search(r'(?i)\b(insert\s+into|update\s+controlplane|delete\s+from)\b', text)
    assert 'CERT_NONE' not in text
    assert '_create_unverified_context' not in text
    assert not re.search(r'print\([^)]*(launch_path|launch2|\burl\b|raw)', text)


def test_unit_recorded_report_rg10():
    """Chế độ mặc định: kiểm bằng chứng lô thật đã ghi trong report.md, không chạy lại lô."""
    text = REPORT.read_text(encoding='utf-8')
    for item in RG10_REQUIRED:
        assert re.search(r'(?m)^RG-10[.]' + item + r': PASS[ \t]*\r?(?:\n|\Z)', text), item
    assert re.search(r'(?m)^RG-10[.]warn_80_visible: (?:PASS|NOT_OBSERVED)[ \t]*\r?(?:\n|\Z)', text)
    assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', text)
    assert re.search(r'Batch ID: `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`', text)
    assert re.search(r'(?m)^- Dòng tổng kết pytest nguyên văn: `[0-9]+ passed[^`]* in [0-9.]+s', text)
    assert c.scan_secrets(text) == []


# --- RG-10 trên ngăn xếp thật ------------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def overnight(tmp_path_factory):
    if not LIVE:
        pytest.skip('lô thật chỉ chạy khi đặt CP7_RG10_LIVE=1; mặc định kiểm bằng chứng đã ghi (test_unit_recorded_report_rg10)')
    work = tmp_path_factory.mktemp('cp7_rg10')
    try:
        return m.run_overnight(work, work / 'timeline.jsonl')
    except d.BlockedError as exc:
        pytest.fail(str(exc))


def test_rg10_drive_quota_ok(overnight, emit):
    quota = overnight.quota
    assert quota['ok'] is True
    free = 'none' if quota['free_bytes'] is None else format(quota['free_bytes'] / GIB, '.2f')
    _pass(emit, 'drive_quota_ok', 'free_gib=' + free, 'required_gib=' + format(quota['required_bytes'] / GIB, '.2f'),
          'unlimited=' + str(quota['unlimited']))


def test_rg10_valid_synced_100(overnight, emit):
    assert len(overnight.valid_jobs) >= m.TARGET_VIDEOS, 'valid=' + str(len(overnight.valid_jobs))
    assert len(overnight.drive_checks) >= 1
    assert all(check['md5_match'] and check['sha256_match'] for check in overnight.drive_checks)
    _pass(emit, 'valid_synced_100', 'valid=' + str(len(overnight.valid_jobs)), 'invalid=' + str(len(overnight.invalid_jobs)),
          'drive_sample=' + str(len(overnight.drive_checks)))


def test_rg10_within_12h(overnight, emit):
    assert overnight.t_target_s is not None, 'chưa đủ 100 video hợp lệ'
    assert overnight.t_target_s <= m.WITHIN_SECONDS
    assert overnight.stop_reason != 'deadline'
    _pass(emit, 'within_12h', 'started_utc=' + overnight.started_utc, 'target_utc=' + overnight.target_utc,
          't_target_s=' + format(overnight.t_target_s, '.0f'))
    emit('- wait_provider_seconds=' + format(overnight.wait_provider_seconds, '.0f'))
    emit(_ascii_line('- concurrency=' + json.dumps(overnight.concurrency, sort_keys=True)))


def test_rg10_auto_ratio_95(overnight, emit):
    total = sum(overnight.job_counts.values())
    valid = len(overnight.valid_jobs)
    for cause in overnight.failure_causes:
        emit(_ascii_line(f"- auto_ratio_95: failure_cause stage={cause['stage']} code={cause['code']} activity={cause['activity']} n={cause['n']}"))
    if not m.auto_ratio_ok(valid, total):
        emit(c.report_line('RG-10', 'auto_ratio_95', 'FAIL'))
        emit(f'- auto_ratio_95: valid={valid} total={total} failed_final={len(overnight.failed_final_jobs)}')
        pytest.fail(f'valid={valid} total={total}')
    assert m.manual_actions(overnight.api_calls, overnight.batch_id) == []
    _pass(emit, 'auto_ratio_95', 'valid=' + str(valid), 'total=' + str(total),
          'failed_final=' + str(len(overnight.failed_final_jobs)), 'manual_actions=0')


def test_rg10_no_vanished_jobs(overnight, emit):
    assert overnight.findings == []
    _pass(emit, 'no_vanished_jobs', 'jobs=' + str(sum(overnight.job_counts.values())), 'findings=0')


def test_rg10_failure_isolated(overnight, emit):
    c_ = overnight.collection
    if c_.get('target_runs', 0) == 0:
        pytest.fail('BLOCKED: nguồn 404 chưa có lượt thu thập nào trong lô, không chứng minh được cô lập lỗi')
    assert c_['isolated']
    assert not overnight.failed_final_jobs or len(overnight.valid_jobs) >= m.TARGET_VIDEOS
    source_id = overnight.not_found_source['source_id']
    _pass(emit, 'failure_isolated', 'target_runs=' + str(c_['target_runs']), 'target_failed=' + str(c_['target_failed']),
          'others_ok=' + str(c_['others_ok']), 'completed_after_failure=' + str(c_['completed_after_failure']),
          'failed_final_jobs=' + str(len(overnight.failed_final_jobs)),
          _ascii_line('source=' + source_id[:6] + '***'))


def test_rg10_resume_300s_midrun(overnight, emit):
    if not overnight.resumed:
        pytest.fail('BLOCKED: chưa thực hiện stop/start giữa lô')
    assert overnight.ready_seconds <= m.RESUME_LIMIT_SECONDS
    assert overnight.busy_at_stop >= 1
    _pass(emit, 'resume_300s_midrun', 'ready_seconds=' + format(overnight.ready_seconds, '.1f'),
          'stop_attempts=' + str(overnight.stop_attempts), 'busy_at_stop=' + str(overnight.busy_at_stop),
          'completed_at_stop=' + str(overnight.completed_at_stop))


def test_rg10_no_rerun_completed(overnight, emit):
    if not overnight.resumed:
        pytest.fail('BLOCKED: chưa thực hiện stop/start giữa lô')
    assert overnight.reruns == {}
    assert overnight.completed_unchanged is True
    _pass(emit, 'no_rerun_completed', 'jobs_checked=' + str(len(overnight.before_stop)), 'reruns=0')


def test_rg10_cost_under_cap(overnight, emit):
    assert m.cost_violations(overnight.night_usd, overnight.month_usd, overnight.drive_bytes, overnight.elapsed_seconds) == []
    valid = len(overnight.valid_jobs)
    per_video = format(Decimal(overnight.night_usd) / valid, '.4f') if valid else 'n/a'
    _pass(emit, 'cost_under_cap', 'night_usd=' + overnight.night_usd, 'month_usd=' + overnight.month_usd,
          'ai_calls=' + str(overnight.ai_calls), 'drive_bytes=' + str(overnight.drive_bytes), 'usd_per_valid_video=' + per_video,
          'route_cost_per_request=0 nen ledger co the bang 0')


def test_rg10_working_set_cap(overnight, emit):
    good = [s for s in overnight.samples if 'sample_error' not in s]
    assert good, 'không có mẫu hợp lệ nào'
    assert overnight.max_working_set_bytes <= m.WORKING_SET_CAP_BYTES
    free = 'none' if overnight.min_disk_free_bytes is None else format(overnight.min_disk_free_bytes / GIB, '.1f')
    _pass(emit, 'working_set_cap', 'max_working_set_gib=' + format(overnight.max_working_set_bytes / GIB, '.2f'),
          'min_disk_free_gib=' + free, 'max_vram_mib=' + str(overnight.max_vram_mib), 'samples=' + str(len(overnight.samples)),
          'sample_errors=' + str(len(overnight.samples) - len(good)))


def test_rg10_stage_metrics(overnight, emit):
    valid = len(overnight.valid_jobs)
    for stage in d.STAGES:
        assert overnight.stage_metrics[stage]['n'] >= valid, stage
    emit(c.report_line('RG-10', 'stage_metrics', 'PASS'))
    for stage in d.STAGES:
        row = overnight.stage_metrics[stage]
        emit(_ascii_line(f"- stage_metrics: {stage}({d.STAGE_LABELS[stage]}) n={row['n']} p50_s={row['p50_s']} p95_s={row['p95_s']} "
                         f"max_s={row['max_s']} extra_attempts={row['extra_attempts']}"))
    span = overnight.t_target_s if overnight.t_target_s is not None else overnight.elapsed_seconds
    per_hour = format(valid * 3600 / span, '.1f') if span else 'n/a'
    emit(f'- lead_time: p50_s={overnight.lead_p50_s} p95_s={overnight.lead_p95_s} videos_per_hour={per_hour}')


def test_rg10_secret_scan(overnight, emit):
    assert overnight.secret_matches == 0
    for path in (SELF, MONITOR_FILE, REPORT):
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        assert c.scan_secrets(text) == []
        assert not re.search(r'[?&]cap=', text)
        assert 'cp_session' + '=' not in text
    _pass(emit, 'secret_scan', 'match_count=0', 'khong_doc_Credentials=True', 'capability_khong_ghi=True')


def test_rg10_warn_80_visible(overnight, emit):
    if overnight.warn_seen:
        pytest.fail('BLOCKED: tháng chạm 40 USD, cần xác nhận cảnh báo 80% hiển thị trên Dashboard')
    emit(c.report_line('RG-10', 'warn_80_visible', 'NOT_OBSERVED'))
    emit('- warn_80_visible: peak_month_usd=' + overnight.month_usd)


def test_rg10_timeline_and_budget(overnight, emit):
    for sample in overnight.samples:
        emit(m.format_sample(sample))
    emit(_ascii_line(f'- budget: night_usd={overnight.night_usd} month_usd={overnight.month_usd} drive_bytes={overnight.drive_bytes} '
                     f'elapsed_s={overnight.elapsed_seconds:.0f} deadline_s={m.DEADLINE_SECONDS} stop_reason={overnight.stop_reason}'))
    emit(_ascii_line(f'- seed: launcher_seed_line={overnight.launcher_seed_line} render_config={overnight.render_config}'))
    source = overnight.not_found_source
    emit(_ascii_line(f'- batch: id={overnight.batch_id[:8]} concurrency={json.dumps(overnight.concurrency, sort_keys=True)} '
                     f'other_workflows_running={overnight.other_workflows_running} not_found_status={overnight.not_found_status} '
                     f"not_found_source registered={source.get('registered')} existing={source.get('existing')}"))


def test_diag_failed_jobs_of_batch(emit):
    prefix = os.environ.get('CP7_DIAG_BATCH_PREFIX', '')
    if not re.fullmatch(r'[0-9a-f-]{8,36}', prefix):
        pytest.skip('CP7_DIAG_BATCH_PREFIX chưa đặt')
    db = m.OvernightDb(d.load_launcher())
    rows = db.query('SELECT batch_id FROM controlplane.cp_production_batches WHERE workspace_id = %s AND starts_with(batch_id, %s)', prefix)
    assert len(rows) == 1, 'batches=' + str(len(rows))
    batch_id = rows[0][0]
    jobs = db.batch_jobs(batch_id)
    failed = [j for j, s in jobs if s == 'FAILED_FINAL']
    emit(_ascii_line(f'- diag: batch={batch_id[:8]} jobs={len(jobs)} failed_final={len(failed)}'))
    for cause in m.failure_causes([(j, db.failed_stage(j)) for j in failed]):
        emit(_ascii_line(f"- diag_cause: stage={cause['stage']} code={cause['code']} activity={cause['activity']} n={cause['n']}"))
    for job_id in failed:
        for row in db.job_diagnostics(job_id)['stages']:
            if row['status'] in ('FAILED_FINAL', 'OUTCOME_UNKNOWN'):
                emit(_ascii_line(f"- diag_job: job={job_id[:8]} stage={row['stage']} attempt={row['attempt']} status={row['status']} code={row['code']} message={str(row['message'])[:120]}"))
