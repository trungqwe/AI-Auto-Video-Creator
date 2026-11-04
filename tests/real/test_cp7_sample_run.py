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


def _pass(emit, item: str, *details: str) -> None:
    emit(c.report_line('RG-13', item, 'PASS'))
    for det in details:
        if det:
            assert str(det).isascii(), f'detail not ASCII: {det}'
            emit(f"- {item}: {det}")

def test_unit_constants():
    assert p.SAMPLE_VIDEOS == 20
    assert PROFILE['batch']['target']['value']['sample_run'] == 10
    assert p.AI_CALL_CAP == 120
    assert p.LEDGER_CEILING_USD == Decimal('10')
    assert p.DRIVE_CAP_BYTES == 3 * p.GIB
    assert p.DEADLINE_SECONDS == 14400
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
    assert p.budget_violations(120, '10', 3 * p.GIB, 14400) == []
    assert p.budget_violations(121, '10', 3 * p.GIB, 14400) == ['ai_calls']
    assert p.budget_violations(120, '10.01', 3 * p.GIB, 14400) == ['ledger_usd']
    assert p.budget_violations(120, '10', 3 * p.GIB + 1, 14400) == ['drive_bytes']
    assert p.budget_violations(120, '10', 3 * p.GIB, 14401) == ['elapsed']
    assert p.budget_violations(121, '10.01', 3 * p.GIB + 1, 14401) == [
        'ai_calls',
        'ledger_usd',
        'drive_bytes',
        'elapsed',
    ]


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
    assert p.visual_violations([{'media_asset_id': 'm1', 'origin': 'article'}], {'m1': 'SAFE'}, {'m1': False}) == []
    for outcome in ('UNCERTAIN', 'DETECTION_FAILED', 'TRANSFORM_FAILED', 'UNREADABLE'):
        assert len(p.visual_violations([{'media_asset_id': 'm1', 'origin': 'article'}], {'m1': outcome}, {})) > 0
    assert len(p.visual_violations([{'media_asset_id': 'm1', 'origin': 'article'}], {}, {})) > 0

    viols = p.visual_violations(
        [{'media_asset_id': 'm12345678', 'origin': 'article'}],
        {'m12345678': 'TRANSFORM_REQUIRED'},
        {'m12345678': False},
    )
    assert 'not_processed:m12345' in viols

    assert (
        p.visual_violations(
            [{'media_asset_id': 'm12345678', 'origin': 'article'}],
            {'m12345678': 'TRANSFORM_REQUIRED'},
            {'m12345678': True},
        )
        == []
    )

    assert 'only_seed_background' in p.visual_violations([{'media_asset_id': 's1', 'origin': 'seed'}], {}, {})
    assert any('origin_missing:' in v for v in p.visual_violations([{'media_asset_id': 'm1', 'origin': None}], {}, {}))

def _make_mock_video(idx: int, valid: bool = True, cloud_ok: bool = True, trace_missing: list | None = None, group: tuple = ('art1',), angle_id: str | None = None, violations: list | None = None) -> dict:
    return {
        'job_id': f'job-{idx:02d}',
        'valid': valid,
        'cloud_ok': cloud_ok,
        'trace_missing': trace_missing or [],
        'group': group,
        'angle_id': angle_id or f'ang-{idx:02d}',
        'violations': violations or [],
        'topic': f'Topic {idx}',
        'media_summary': 'article=2 ai=2 seed=1 hook=12345678',
    }


def test_unit_evaluate_items():
    # Base 20 valid videos with 2 groups (multi_groups >= 1)
    base_videos = []
    for i in range(10):
        base_videos.append(_make_mock_video(i, group=('art1',), angle_id=f'ang1-{i}'))
    for i in range(10, 20):
        base_videos.append(_make_mock_video(i, group=('art2',), angle_id=f'ang2-{i}'))

    base_drive = [{'md5_match': True, 'sha256_match': True, 'size': 1000}] * 20
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

    # Counterexamples
    # 19 videos
    r = dict(base_run, videos=base_videos[:19])
    assert p.evaluate_items(r)['sample_10_valid'][0] == 'FAIL'
    assert p.evaluate_items(r)['cloud_verified_10'][0] == 'FAIL'

    # valid False
    v_bad = list(base_videos)
    v_bad[0] = dict(v_bad[0], valid=False)
    assert p.evaluate_items(dict(base_run, videos=v_bad))['sample_10_valid'][0] == 'FAIL'

    # cloud_ok False
    v_bad = list(base_videos)
    v_bad[0] = dict(v_bad[0], cloud_ok=False)
    assert p.evaluate_items(dict(base_run, videos=v_bad))['cloud_verified_10'][0] == 'FAIL'

    # missing drive_check
    assert p.evaluate_items(dict(base_run, drive_checks=base_drive[:19]))['cloud_verified_10'][0] == 'FAIL'

    # trace_missing non-empty
    v_bad = list(base_videos)
    v_bad[0] = dict(v_bad[0], trace_missing=['snapshot'])
    assert p.evaluate_items(dict(base_run, videos=v_bad))['trace_per_video'][0] == 'FAIL'

    # duplicate angle
    v_bad = list(base_videos)
    v_bad[1] = dict(v_bad[1], angle_id=v_bad[0]['angle_id'])
    assert p.evaluate_items(dict(base_run, videos=v_bad))['story_angle_distinct'][0] == 'FAIL'

    # violations non-empty
    v_bad = list(base_videos)
    v_bad[0] = dict(v_bad[0], violations=['origin_missing:123456'])
    assert p.evaluate_items(dict(base_run, videos=v_bad))['rights_unverified_excluded'][0] == 'FAIL'

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
    for i in range(10):
        mock_videos.append(_make_mock_video(i, group=('art1',), angle_id=f'ang1-{i}'))
    for i in range(10, 20):
        mock_videos.append(_make_mock_video(i, group=('art2',), angle_id=f'ang2-{i}'))
    mock_drive = [{'md5_match': True, 'sha256_match': True, 'size': 1000}] * 20
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

    # 20 video rows, 40 holdout rows
    v_sheet_lines = [l for l in text.split('## Bảng chấm video')[1].split('## Bảng 40 cặp holdout')[0].splitlines() if l.strip().startswith('|') and not l.strip().startswith('| ---') and 'STT' not in l]
    assert len(v_sheet_lines) == 20

    h_sheet_lines = [l for l in text.split('## Bảng 40 cặp holdout')[1].splitlines() if l.strip().startswith('|') and not l.strip().startswith('| ---') and 'STT' not in l]
    assert len(h_sheet_lines) == 40

    assert p.user_fields_empty(text) == (True, 60)
    assert p.approval_claims(text) == []
    for line in text.splitlines():
        assert not line.endswith(' '), f'Trailing whitespace in: {repr(line)}'
    assert 'Bảng chấm video' in text
    assert 'Bảng R1–R6' in text

    # Altering a cell to 'x' makes user_fields_empty False
    bad_text = text.replace('|  |  |', '| x |  |', 1)
    assert p.user_fields_empty(bad_text)[0] is False

    # Adding 'đã duyệt' makes approval_claims non-empty
    bad_claim_text = text + '\nđã duyệt\n'
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


def test_unit_run_sample_order():
    text = (p.REPO / 'tools' / 'real' / 'cp7_acceptance_pack.py').read_text(encoding='utf-8')
    idx = text.find('def run_sample(')
    sub = text[idx:]
    p1 = sub.find('require_restored_db(db)')
    p2 = sub.find('d.stop_until_exited()')
    p3 = sub.find('d.require_no_other_workflows()')
    p4 = sub.find("d.start_capturing(work_dir")
    p5 = sub.find('d.require_render_config(db)')
    p6 = sub.find('post_overnight_batch(SAMPLE_VIDEOS')
    assert p1 < p2 < p3 < p4 < p5 < p6, f'Order check failed: {p1}, {p2}, {p3}, {p4}, {p5}, {p6}'
    assert sub.count('post_overnight_batch(') == 1
    finally_idx = sub.find('finally:')
    last_stop = sub.rfind('d.stop_until_exited()')
    assert finally_idx < last_stop

@pytest.fixture(scope='module')
def sample_run(tmp_path_factory):
    if not LIVE:
        pytest.skip('lô thật chỉ chạy khi đặt CP7_RG13_LIVE=1; mặc định kiểm bằng chứng đã ghi (test_recorded_report_rg13)')
    work = tmp_path_factory.mktemp('cp7_rg13')
    try:
        run = p.run_sample(work)
    except (d.BlockedError, c.CostCeilingExceeded, c.DeadlineExceeded) as exc:
        pytest.fail(str(exc))

    manifest, digest = p.load_holdout()
    r_rows = p.build_r_rows()
    holdout_ok = len(p.holdout_rows(manifest)) == 40
    sheets_ok = len(run.videos) == p.SAMPLE_VIDEOS
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
    assert p.budget_violations(run.ai_calls, run.spent_usd, run.drive_bytes, run.elapsed_seconds) == []
    emit(f'- budget: ai_calls={run.ai_calls} spent_usd={run.spent_usd} drive_bytes={run.drive_bytes} elapsed_s={run.elapsed_seconds:.1f} caps=120/10/3GiB/14400')


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
    assert uf[0] is True and uf[1] == 60, f'user_fields_empty mismatch: {uf}'
    assert p.approval_claims(text) == []

    manifest, digest = p.load_holdout()
    assert f'holdout_manifest_sha256: {digest}' in text

    assert c.scan_secrets(text) == []
    assert not re.search(r'AIza[0-9A-Za-z_-]{20}|-{5}BEGIN', text), 'Found secret pattern in report'
    assert 'Bảng R1–R6' in text
