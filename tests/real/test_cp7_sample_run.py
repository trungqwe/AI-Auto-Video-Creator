"""CP7-14 / RG-13; test_unit_* thuần không chạm ngăn xếp; test_rg13_* chạy lô thật CHỈ khi đặt CP7_RG13_LIVE=1 (cách dừng python tools/launcher/launcher.py stop); mặc định test_recorded_report_rg13 kiểm bằng chứng đã ghi."""
from __future__ import annotations

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import hashlib
import json
import os
import re
from decimal import Decimal
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools' / 'real'))
sys.path.insert(0, str(REPO / 'src'))

import cp7_acceptance_pack as p
import cp7_common as c
import cp7_batch_driver as d

LIVE = os.environ.get('CP7_RG13_LIVE') == '1'
PROFILE = json.loads(d.PROFILE_JSON.read_text(encoding='utf-8'))
REAUDIT_BATCH_ID = '43fb05ea-f976-4bee-a0c4-e393db5502f4'


def _pass(emit, item: str, *details: str) -> None:
    emit(c.report_line('RG-13', item, 'PASS'))
    for det in details:
        if det:
            assert str(det).isascii(), f'detail not ASCII: {det}'
            emit(f"- {item}: {det}")

def test_unit_constants():
    assert p.SAMPLE_VIDEOS == 10
    assert PROFILE['batch']['target']['value']['sample_run'] == 10
    assert p.AI_CALL_CAP == 60
    assert p.LEDGER_CEILING_USD == Decimal('5')
    assert p.DRIVE_CAP_BYTES == 3 * p.GIB // 2
    assert p.DEADLINE_SECONDS == 10800
    assert p.RG13_ITEMS == (
        'sample_10_valid',
        'cloud_verified_10',
        'trace_per_video',
        'story_angle_distinct',
        'rights_unverified_excluded',
        'holdout_sheet_40',
        'video_sheet_10',
        'pack_r1_r6_complete',
        'no_user_field_filled',
        'secret_scan',
    )


def test_unit_r_table():
    assert len(p.R_TABLE) == 6
    assert p.R_TABLE[0]['pending'] == ('M3-EG7', 'M3-REAL')
    assert p.R_TABLE[3]['pending'] == ('M6-EG6', 'M6-EG1', 'M6-EG5')
    assert p.R_TABLE[4]['pending'] == ('M7-R5-EG1',)
    r6_gates = set(p.R_TABLE[5]['gates'])
    assert r6_gates == {
        'RG-01',
        'RG-02',
        'RG-03',
        'RG-04',
        'RG-05',
        'RG-06',
        'RG-07',
        'RG-08',
        'RG-09',
        'RG-10',
        'RG-11',
        'RG-12',
    }
    assert p.R_TABLE[0]['screens'] == ('sources', 'articles', 'events', 'stage-runs')
    assert p.R_TABLE[2]['screens'] == ('snapshots', 'story-angles', 'scripts')
    for r in p.R_TABLE:
        for path in r['evidence']:
            if path != 'docs/delivery-evidence/cp7-14/report.md':
                assert (p.REPO / path).exists(), f'Missing evidence: {path}'


def test_unit_holdout_read_only():
    manifest, digest = p.load_holdout()
    assert len(manifest['pairs']) == 40
    rows = p.holdout_rows(manifest)
    assert len(rows) == 40
    assert len(digest) == 64 and all(c in '0123456789abcdef' for c in digest)
    rep5 = (p.REPO / 'docs' / 'delivery-evidence' / 'cp7-5' / 'report.md').read_text(encoding='utf-8')
    assert f'holdout_manifest_sha256: {digest}' in rep5


def test_unit_md_table():
    rendered = p.md_table(['A', 'B'], [['1', ''], ['', '2']])
    for line in rendered.splitlines():
        assert not line.endswith(' '), f'Trailing whitespace in: {repr(line)}'
    rendered2 = p.md_table(['A|B'], [['x|y']])
    assert '|' not in rendered2.splitlines()[0][1:-1].replace(' | ', '')

def test_unit_budget():
    assert p.budget_violations(60, '5', p.DRIVE_CAP_BYTES, 10800) == []
    assert p.budget_violations(61, '5', p.DRIVE_CAP_BYTES, 10800) == ['ai_calls']
    assert p.budget_violations(60, '5.01', p.DRIVE_CAP_BYTES, 10800) == ['ledger_usd']
    assert p.budget_violations(60, '5', p.DRIVE_CAP_BYTES + 1, 10800) == ['drive_bytes']
    assert p.budget_violations(60, '5', p.DRIVE_CAP_BYTES, 10801) == ['elapsed']
    assert p.budget_violations(61, '5.01', p.DRIVE_CAP_BYTES + 1, 10801) == [
        'ai_calls',
        'ledger_usd',
        'drive_bytes',
        'elapsed',
    ]
    assert p.budget_gate_violations(124, '0', 307516118, 3479.5) == []
    assert p.budget_gate_violations(61, '5.01', p.DRIVE_CAP_BYTES + 1, 10801) == ['ledger_usd', 'drive_bytes', 'elapsed']


def test_unit_angle_distinct():
    vids = [{'group': ('art1',), 'angle_id': 'ang1'}, {'group': ('art1',), 'angle_id': 'ang2'}]
    res = p.angle_distinct(vids)
    assert res['ok'] is True and len(res['duplicates']) == 0

    vids2 = [{'group': ('art1',), 'angle_id': 'ang1'}, {'group': ('art1',), 'angle_id': 'ang1'}]
    res2 = p.angle_distinct(vids2)
    assert res2['ok'] is False and len(res2['duplicates']) > 0

    vids3 = [{'group': ('art1',), 'angle_id': 'ang1'}, {'group': ('art2',), 'angle_id': 'ang2'}]
    res3 = p.angle_distinct(vids3)
    assert res3['ok'] is False

    vids4 = [{'group': ('art1',), 'angle_id': ''}, {'group': ('art1',), 'angle_id': 'ang2'}]
    res4 = p.angle_distinct(vids4)
    assert res4['ok'] is False


def test_unit_visual_violations():
    # Article without labels and non-only-seed visual -> []
    visuals_clean = [
        {'media_asset_id': 'm1', 'origin': 'article'},
        {'media_asset_id': 'a1', 'origin': 'ai_generated'},
    ]
    assert p.visual_violations(visuals_clean, {}, {}) == []

    # Article with minor_child and processed_ok False -> contains minor_child_unmasked:m12345
    v_mc = [
        {'media_asset_id': 'm12345678', 'origin': 'article'},
        {'media_asset_id': 'a1', 'origin': 'ai_generated'},
    ]
    viols_mc = p.visual_violations(v_mc, {'m12345678': ('minor_child',)}, {'m12345678': False})
    assert 'minor_child_unmasked:m12345' in viols_mc

    # processed_ok True -> no violation
    assert p.visual_violations(v_mc, {'m12345678': ('minor_child',)}, {'m12345678': True}) == []

    # Other label ('weapon',) unmasked -> no violation
    assert p.visual_violations(v_mc, {'m12345678': ('weapon',)}, {'m12345678': False}) == []

    # All seed -> contains only_seed_background
    assert 'only_seed_background' in p.visual_violations([{'media_asset_id': 's1', 'origin': 'seed'}], {}, {})

    # Origin None -> contains origin_missing:
    assert any('origin_missing:' in v for v in p.visual_violations([{'media_asset_id': 'm1', 'origin': None}], {}, {}))

    # classify_unverified 5 states
    test_vis = [
        {'media_asset_id': 'm_unassessed', 'origin': 'article'},
        {'media_asset_id': 'm_masked', 'origin': 'article'},
        {'media_asset_id': 'm_safe', 'origin': 'article'},
        {'media_asset_id': 'm_minor', 'origin': 'article'},
        {'media_asset_id': 'm_other', 'origin': 'article'},
        {'media_asset_id': 'm_seed', 'origin': 'seed'},
    ]
    safety_map = {
        'm_masked': 'TRANSFORM_REQUIRED',
        'm_safe': 'SAFE',
        'm_minor': 'TRANSFORM_REQUIRED',
        'm_other': 'TRANSFORM_REQUIRED',
    }
    cat_map = {
        'm_minor': ('minor_child',),
        'm_other': ('weapon',),
    }
    proc_map = {
        'm_masked': True,
    }
    classified = p.classify_unverified(test_vis, safety_map, cat_map, proc_map)
    assert classified == {
        'safe': 1,
        'masked': 1,
        'unmasked_minor_child': 1,
        'other_unmasked': 1,
        'unassessed': 1,
    }

    # sum_unverified
    vids_mock = [
        {'unverified': {'safe': 2, 'masked': 1, 'unmasked_minor_child': 0, 'other_unmasked': 1, 'unassessed': 0}},
        {'unverified': {'safe': 1, 'masked': 0, 'unmasked_minor_child': 0, 'other_unmasked': 0, 'unassessed': 3}},
    ]
    summed = p.sum_unverified(vids_mock)
    assert summed == {
        'safe': 3,
        'masked': 1,
        'unmasked_minor_child': 0,
        'other_unmasked': 1,
        'unassessed': 3,
    }

    # select_sheet: 12 videos with 2 videos valid False or cloud_ok False at index 0 and 3 -> exactly 10 videos
    twelve_vids = []
    for idx in range(12):
        is_valid = (idx != 0)
        is_cloud = (idx != 3)
        twelve_vids.append({'job_id': f'job-{idx}', 'valid': is_valid, 'cloud_ok': is_cloud})
    sheet = p.select_sheet(twelve_vids)
    assert len(sheet) == 10
    sheet_jobs = [v['job_id'] for v in sheet]
    assert 'job-0' not in sheet_jobs
    assert 'job-3' not in sheet_jobs
    expected_jobs = [f'job-{i}' for i in range(12) if i not in (0, 3)]
    assert sheet_jobs == expected_jobs
def _make_mock_video(idx: int, valid: bool = True, cloud_ok: bool = True, trace_missing: list | None = None, group: tuple = ('art1',), angle_id: str | None = None, violations: list | None = None) -> dict:
    return {
        'job_id': f'job-{idx:02d}',
        'valid': valid,
        'cloud_ok': cloud_ok,
        'trace_missing': trace_missing or [],
        'group': group,
        'angle_id': angle_id or f'ang-{idx:02d}',
        'violations': violations or [],
        'unverified': {'safe': 1, 'masked': 1, 'unmasked_minor_child': 0, 'other_unmasked': 0, 'unassessed': 0},
        'topic': f'Topic {idx}',
        'media_summary': 'article=2 ai=2 seed=1 hook=12345678',
    }
def test_unit_evaluate_items():
    # Base 16 videos (8 group art1, 8 group art2)
    base_videos = []
    for i in range(8):
        base_videos.append(_make_mock_video(i, group=('art1',), angle_id=f'ang1-{i}'))
    for i in range(8, 16):
        base_videos.append(_make_mock_video(i, group=('art2',), angle_id=f'ang2-{i}'))

    base_drive = [{'md5_match': True, 'sha256_match': True, 'size': 1000}] * 16
    base_run = {
        'videos': base_videos,
        'drive_checks': base_drive,
        'holdout_ok': True,
        'sheets_ok': True,
        'r_missing': [],
        'user_ok': True,
        'secret_matches': 0,
    }
    items = p.evaluate_items(base_run)
    for k in p.RG13_ITEMS:
        assert items[k][0] == 'PASS', f'{k} not PASS: {items[k]}'

    # Counterexamples:
    # 9 videos -> sample_10_valid and cloud_verified_10 FAIL
    r9 = dict(base_run, videos=base_videos[:9], drive_checks=base_drive[:9])
    assert p.evaluate_items(r9)['sample_10_valid'][0] == 'FAIL'
    assert p.evaluate_items(r9)['cloud_verified_10'][0] == 'FAIL'

    # 16 videos with 6 videos valid False -> sample_10_valid PASS (10 remain valid)
    v16_6bad = list(base_videos)
    for i in range(6):
        v16_6bad[i] = dict(v16_6bad[i], valid=False)
    assert p.evaluate_items(dict(base_run, videos=v16_6bad))['sample_10_valid'][0] == 'PASS'

    # 16 videos with 7 videos valid False -> sample_10_valid FAIL (9 remain valid)
    v16_7bad = list(base_videos)
    for i in range(7):
        v16_7bad[i] = dict(v16_7bad[i], valid=False)
    assert p.evaluate_items(dict(base_run, videos=v16_7bad))['sample_10_valid'][0] == 'FAIL'

    # drive_checks only 9 matching items -> cloud FAIL
    assert p.evaluate_items(dict(base_run, drive_checks=base_drive[:9]))['cloud_verified_10'][0] == 'FAIL'

    # trace_missing at video 0 (in sheet) -> trace_per_video FAIL
    v_bad = list(base_videos)
    v_bad[0] = dict(v_bad[0], trace_missing=['snapshot'])
    assert p.evaluate_items(dict(base_run, videos=v_bad))['trace_per_video'][0] == 'FAIL'

    # trace_missing at video 15 (outside sheet) -> still PASS
    v_outside_trace = list(base_videos)
    v_outside_trace[15] = dict(v_outside_trace[15], trace_missing=['snapshot'])
    assert p.evaluate_items(dict(base_run, videos=v_outside_trace))['trace_per_video'][0] == 'PASS'

    # duplicate angle in same group -> story_angle_distinct FAIL
    v_bad_angle = list(base_videos)
    v_bad_angle[1] = dict(v_bad_angle[1], angle_id=v_bad_angle[0]['angle_id'])
    assert p.evaluate_items(dict(base_run, videos=v_bad_angle))['story_angle_distinct'][0] == 'FAIL'

    # violations at video 0 -> rights FAIL
    v_bad_viol = list(base_videos)
    v_bad_viol[0] = dict(v_bad_viol[0], violations=['minor_child_unmasked:123456'])
    assert p.evaluate_items(dict(base_run, videos=v_bad_viol))['rights_unverified_excluded'][0] == 'FAIL'

    # violations at video 15 (outside sheet) -> still PASS
    v_outside_viol = list(base_videos)
    v_outside_viol[15] = dict(v_outside_viol[15], violations=['minor_child_unmasked:123456'])
    assert p.evaluate_items(dict(base_run, videos=v_outside_viol))['rights_unverified_excluded'][0] == 'PASS'

    # holdout_ok False
    assert p.evaluate_items(dict(base_run, holdout_ok=False))['holdout_sheet_40'][0] == 'FAIL'

    # sheets_ok False
    assert p.evaluate_items(dict(base_run, sheets_ok=False))['video_sheet_10'][0] == 'FAIL'

    # r_missing non-empty
    assert p.evaluate_items(dict(base_run, r_missing=['some/path']))['pack_r1_r6_complete'][0] == 'FAIL'

    # user_ok False
    assert p.evaluate_items(dict(base_run, user_ok=False))['no_user_field_filled'][0] == 'FAIL'

    # secret_matches 1
    assert p.evaluate_items(dict(base_run, secret_matches=1))['secret_scan'][0] == 'FAIL'
def test_unit_render_report():
    mock_videos = []
    for i in range(6):
        mock_videos.append(_make_mock_video(i, group=('art1',), angle_id=f'ang1-{i}'))
    for i in range(6, 12):
        mock_videos.append(_make_mock_video(i, group=('art2',), angle_id=f'ang2-{i}'))
    mock_drive = [{'md5_match': True, 'sha256_match': True, 'size': 1000}] * 12
    manifest, digest = p.load_holdout()
    items = p.evaluate_items({
        'videos': mock_videos,
        'drive_checks': mock_drive,
        'holdout_ok': True,
        'sheets_ok': True,
        'r_missing': [],
        'user_ok': True,
        'secret_matches': 0,
    })
    run_obj = {
        'ai_calls': 20,
        'spent_usd': '1.50',
        'drive_bytes': 2000000,
        'elapsed_seconds': 120.0,
        'videos': mock_videos,
    }
    text = p.render_report(run_obj, items, 'batch-test-01', manifest, digest)
    for k in p.RG13_ITEMS:
        assert re.search(r'(?m)^RG-13[.]' + k + r': (PASS|FAIL|BLOCKED|NOT_OBSERVED)$', text)

    # 10 video rows, 40 holdout rows
    v_sheet_lines = [l for l in text.split('## Bảng chấm video')[1].split('## Bảng 40 cặp holdout')[0].splitlines() if l.strip().startswith('|') and not l.strip().startswith('| ---') and 'STT' not in l]
    assert len(v_sheet_lines) == 10

    h_sheet_lines = [l for l in text.split('## Bảng 40 cặp holdout')[1].splitlines() if l.strip().startswith('|') and not l.strip().startswith('| ---') and 'STT' not in l]
    assert len(h_sheet_lines) == 40

    assert p.user_fields_empty(text) == (True, 50)
    assert p.approval_claims(text) == []
    assert 'Đính chính của Control ngày 05/11/2026' in text
    assert 'Mẫu 10 video' in text
    assert '## Lô' in text
    for line in text.splitlines():
        assert not line.endswith(' '), f'Trailing whitespace in: {repr(line)}'
    assert 'Bảng chấm video' in text
    assert 'Bảng R1–R6' in text

    # Altering a cell to 'x' makes user_fields_empty False
    bad_text = text.replace('|  |  |', '| x |  |', 1)
    assert p.user_fields_empty(bad_text)[0] is False

    # Adding 'đã duyệt' makes approval_claims non-empty
    bad_claim_text = text + chr(10) + 'đã duyệt' + chr(10)
    assert len(p.approval_claims(bad_claim_text)) > 0


def test_unit_pack_is_read_only():
    text = (p.REPO / 'tools' / 'real' / 'cp7_acceptance_pack.py').read_text(encoding='utf-8')
    assert not re.search(r'(?i)\b(insert\s+into|update\s+controlplane|delete\s+from)\b', text)
    assert 'CERT_NONE' not in text
    assert '_create_unverified_context' not in text
    # Check MANIFEST_PATH only in read calls
    manifest_lines = [l for l in text.splitlines() if 'MANIFEST_PATH' in l and 'MANIFEST_PATH =' not in l]
    assert manifest_lines
    for l in manifest_lines:
        assert 'write' not in l and "open(" not in l
    assert c.scan_secrets(text) == []


def test_unit_reaudit_is_read_only():
    text = (p.REPO / 'tools' / 'real' / 'cp7_acceptance_pack.py').read_text(encoding='utf-8')
    assert 'def reaudit_batch(' in text
    assert 'def run_sample(' not in text
    for forbidden in ('start_capturing', 'post_overnight_batch', 'OvernightSession', 'stop_until_exited', 'require_no_other_workflows'):
        assert forbidden not in text, f'{forbidden} found in cp7_acceptance_pack.py'
@pytest.fixture(scope='module')
def sample_run():
    if not LIVE:
        pytest.skip('đọc lại lô đã chạy xong chỉ khi đặt CP7_RG13_LIVE=1 (chỉ đọc CSDL và Drive, không khởi launcher); mặc định kiểm bằng chứng đã ghi (test_recorded_report_rg13)')
    try:
        run = p.reaudit_batch(REAUDIT_BATCH_ID)
    except d.BatchDriverError as exc:
        pytest.fail(str(exc))

    manifest, digest = p.load_holdout()
    r_rows = p.build_r_rows()
    holdout_ok = len(p.holdout_rows(manifest)) == 40
    sheets_ok = len(p.select_sheet(run.videos)) == p.SAMPLE_VIDEOS
    r_missing = [path for r in r_rows for path, sha in r['evidence'] if sha == 'MISSING']

    draft_body = p.render_report(run, {}, run.batch_id, manifest, digest)
    user_ok = p.user_fields_empty(draft_body)[0] and not p.approval_claims(draft_body)
    secret_matches = run.secret_matches + len(c.scan_secrets(draft_body))

    items = p.evaluate_items({
        'videos': run.videos,
        'drive_checks': run.drive_checks,
        'budget': {},
        'holdout_ok': holdout_ok,
        'sheets_ok': sheets_ok,
        'r_missing': r_missing,
        'user_ok': user_ok,
        'secret_matches': secret_matches,
    })

    final_body = p.render_report(run, items, run.batch_id, manifest, digest)
    p.REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(p.REPORT_PATH, 'w', encoding='utf-8', newline=chr(10)) as handle:
        handle.write(final_body)

    return run, items
def test_rg13_sample_10_valid(sample_run, emit):
    run, items = sample_run
    st, det = items['sample_10_valid']
    if st != 'PASS':
        emit(c.report_line('RG-13', 'sample_10_valid', 'FAIL'))
        pytest.fail(f'sample_10_valid failed: {det}')
    _pass(emit, 'sample_10_valid', det)


def test_rg13_cloud_verified_10(sample_run, emit):
    run, items = sample_run
    st, det = items['cloud_verified_10']
    if st != 'PASS':
        emit(c.report_line('RG-13', 'cloud_verified_10', 'FAIL'))
        pytest.fail(f'cloud_verified_10 failed: {det}')
    _pass(emit, 'cloud_verified_10', det)


def test_rg13_trace_per_video(sample_run, emit):
    run, items = sample_run
    st, det = items['trace_per_video']
    if st != 'PASS':
        emit(c.report_line('RG-13', 'trace_per_video', 'FAIL'))
        pytest.fail(f'trace_per_video failed: {det}')
    _pass(emit, 'trace_per_video', det)


def test_rg13_story_angle_distinct(sample_run, emit):
    run, items = sample_run
    st, det = items['story_angle_distinct']
    if st != 'PASS':
        emit(c.report_line('RG-13', 'story_angle_distinct', 'FAIL'))
        pytest.fail(f'story_angle_distinct failed: {det}')
    _pass(emit, 'story_angle_distinct', det)


def test_rg13_rights_unverified_excluded(sample_run, emit):
    run, items = sample_run
    st, det = items['rights_unverified_excluded']
    if st != 'PASS':
        emit(c.report_line('RG-13', 'rights_unverified_excluded', 'FAIL'))
        pytest.fail(f'rights_unverified_excluded failed: {det}')
    _pass(emit, 'rights_unverified_excluded', det)


def test_rg13_holdout_sheet_40(sample_run, emit):
    run, items = sample_run
    st, det = items['holdout_sheet_40']
    if st != 'PASS':
        emit(c.report_line('RG-13', 'holdout_sheet_40', 'FAIL'))
        pytest.fail(f'holdout_sheet_40 failed: {det}')
    _pass(emit, 'holdout_sheet_40', det)


def test_rg13_video_sheet_10(sample_run, emit):
    run, items = sample_run
    st, det = items['video_sheet_10']
    if st != 'PASS':
        emit(c.report_line('RG-13', 'video_sheet_10', 'FAIL'))
        pytest.fail(f'video_sheet_10 failed: {det}')
    _pass(emit, 'video_sheet_10', det)


def test_rg13_pack_r1_r6_complete(sample_run, emit):
    run, items = sample_run
    st, det = items['pack_r1_r6_complete']
    if st != 'PASS':
        emit(c.report_line('RG-13', 'pack_r1_r6_complete', 'FAIL'))
        pytest.fail(f'pack_r1_r6_complete failed: {det}')
    _pass(emit, 'pack_r1_r6_complete', det)


def test_rg13_no_user_field_filled(sample_run, emit):
    run, items = sample_run
    st, det = items['no_user_field_filled']
    if st != 'PASS':
        emit(c.report_line('RG-13', 'no_user_field_filled', 'FAIL'))
        pytest.fail(f'no_user_field_filled failed: {det}')
    _pass(emit, 'no_user_field_filled', det)


def test_rg13_secret_scan(sample_run, emit):
    run, items = sample_run
    st, det = items['secret_scan']
    if st != 'PASS':
        emit(c.report_line('RG-13', 'secret_scan', 'FAIL'))
        pytest.fail(f'secret_scan failed: {det}')
    _pass(emit, 'secret_scan', det)


def test_rg13_budget(sample_run, emit):
    run, _ = sample_run
    assert p.budget_gate_violations(run.ai_calls, run.spent_usd, run.drive_bytes, run.elapsed_seconds) == []
    emit(f'- budget: ai_calls={run.ai_calls} (measure; plan cap {p.AI_CALL_CAP} is not an acceptance gate) spent_usd={run.spent_usd} drive_bytes={run.drive_bytes} elapsed_s={run.elapsed_seconds:.1f} caps=60/5/1.5GiB/10800')


def test_rg13_run_facts(sample_run, emit):
    run, _ = sample_run
    emit(f'- batch: id={run.batch_id[:8]} concurrency={run.concurrency} other_workflows_running={run.other_workflows_running} stop_reason={run.stop_reason} job_counts={run.job_counts}')


def test_recorded_report_rg13(emit):
    assert p.REPORT_PATH.exists(), f'Missing report: {p.REPORT_PATH}'
    text = p.REPORT_PATH.read_text(encoding='utf-8')

    for k in p.RG13_ITEMS:
        assert re.search(r'(?m)^RG-13[.]' + k + r': PASS[ \t]*\r?(?:\n|\Z)', text), f'RG-13.{k} not PASS in report'

    assert not re.search(r'(?m)^RG-[0-9]{2}[.]\w+: (?:FAIL|BLOCKED)', text), 'Found FAIL/BLOCKED item in report'

    assert re.search(r'Batch ID: `[0-9a-fA-F-]+`', text), 'Missing Batch ID UUID in report'
    assert f'Batch ID: `{REAUDIT_BATCH_ID}`' in text
    assert 'Đính chính của Control ngày 05/11/2026' in text
    assert 'Mẫu 10 video' in text

    v_lines = [l for l in text.split('## Bảng chấm video')[1].split('## Bảng 40 cặp holdout')[0].splitlines() if l.strip().startswith('|') and not l.strip().startswith('| ---') and 'STT' not in l]
    assert len(v_lines) == p.SAMPLE_VIDEOS, f'Expected {p.SAMPLE_VIDEOS} video rows, got {len(v_lines)}'

    h_lines = [l for l in text.split('## Bảng 40 cặp holdout')[1].splitlines() if l.strip().startswith('|') and not l.strip().startswith('| ---') and 'STT' not in l]
    assert len(h_lines) == 40, f'Expected 40 holdout rows, got {len(h_lines)}'

    # R1..R6 present with valid sha256
    r_rows = p.build_r_rows()
    for r in r_rows:
        for rel_path, sha in r['evidence']:
            assert sha != 'MISSING', f'Missing evidence in R table: {rel_path}'
            if sha != 'SELF':
                assert len(sha) == 64 and all(c in '0123456789abcdef' for c in sha)

    uf = p.user_fields_empty(text)
    assert uf[0] is True and uf[1] == 50, f'user_fields_empty mismatch: {uf}'
    assert p.approval_claims(text) == []

    manifest, digest = p.load_holdout()
    assert f'holdout_manifest_sha256: {digest}' in text

    assert c.scan_secrets(text) == []
    assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', text), 'Found secret pattern in report'
    assert 'Bảng R1–R6' in text
