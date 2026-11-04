"""CP7-14 / RG-13, gói nghiệm thu R1–R6 và lô mẫu 20 video (quyết định user 04/11/2026: lô mẫu là 20 thay cho 10; không sửa profile.json, `batch.target.sample_run` giữ 10; trần 120 lời gọi AI, ledger +10 USD, Drive 3 GiB, 4 giờ; cách dừng `python tools/launcher/launcher.py stop`, `Deadline`, `CostGuard`; không in capability, cookie, token)."""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import cp7_batch_driver as d
import cp7_common as c
import cp7_overnight_monitor as m

REPO = Path(__file__).resolve().parents[2]
GIB = 1024 ** 3
SAMPLE_VIDEOS = 20
HOLDOUT_PAIRS = 40
AI_CALL_CAP = 120
LEDGER_CEILING_USD = Decimal('10')
DRIVE_CAP_BYTES = 3 * GIB
DEADLINE_SECONDS = 4 * 3600
MANIFEST_PATH = REPO / 'tests' / 'real' / 'fixtures' / 'cp7_holdout_manifest.json'
REPORT_PATH = REPO / 'docs' / 'delivery-evidence' / 'cp7-14' / 'report.md'
RG13_ITEMS = (
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
USER_HEADERS = ('Nhãn topic (user)', 'Nhãn media/hook (user)', 'Nhãn event-link (user)')
SAFETY_OK = ('SAFE', 'TRANSFORM_REQUIRED')
ARTICLE_ORIGINS = ('article', 'ai_generated')

GATE_EVIDENCE: dict[str, tuple[str, ...]] = {
    'RG-01': ('docs/delivery-evidence/cp7-1/report.md', 'docs/delivery-evidence/cp7-2/report.md'),
    'RG-02': ('docs/delivery-evidence/cp7-3/report.md',),
    'RG-03': ('docs/delivery-evidence/cp7-4/report.md',),
    'RG-04': ('docs/delivery-evidence/cp7-5/report.md',),
    'RG-05': ('docs/delivery-evidence/cp7-6/report.md',),
    'RG-06': ('docs/delivery-evidence/cp7-7/report.md',),
    'RG-07': ('docs/delivery-evidence/cp7-8/report.md',),
    'RG-08': ('docs/delivery-evidence/cp7-9/report.md',),
    'RG-09': ('docs/delivery-evidence/cp7-10/report.md',),
    'RG-10': ('docs/delivery-evidence/cp7-11/report.md',),
    'RG-11': ('docs/delivery-evidence/cp7-12/report.md',),
    'RG-12': ('docs/delivery-evidence/cp7-13/report.md',),
    'RG-13': ('docs/delivery-evidence/cp7-14/report.md',),
}


def _r_evidence(gates: tuple[str, ...]) -> tuple[str, ...]:
    out: list[str] = []
    for g in gates:
        for p in GATE_EVIDENCE.get(g, ()):
            if p not in out:
                out.append(p)
    return tuple(out)


R_TABLE = (
    {
        'code': 'R1',
        'title': 'Content Alpha',
        'pending': ('M3-EG7', 'M3-REAL'),
        'gates': ('RG-04',),
        'evidence': _r_evidence(('RG-04',)),
        'screens': ('sources', 'articles', 'events', 'stage-runs'),
        'note': '',
    },
    {
        'code': 'R2',
        'title': 'Media Alpha',
        'pending': ('M4-EG6', 'M4-EG5'),
        'gates': ('RG-02', 'RG-06'),
        'evidence': _r_evidence(('RG-02', 'RG-06')),
        'screens': ('media', 'hooks', 'artifacts'),
        'note': '',
    },
    {
        'code': 'R3',
        'title': 'Creative Alpha',
        'pending': ('M5-EG7', 'M5-REAL'),
        'gates': ('RG-03', 'RG-04', 'RG-13'),
        'evidence': _r_evidence(('RG-03', 'RG-04', 'RG-13')),
        'screens': ('snapshots', 'story-angles', 'scripts'),
        'note': '',
    },
    {
        'code': 'R4',
        'title': 'Video Alpha',
        'pending': ('M6-EG6', 'M6-EG1', 'M6-EG5'),
        'gates': ('RG-05', 'RG-06', 'RG-07', 'RG-09', 'RG-13'),
        'evidence': _r_evidence(('RG-05', 'RG-06', 'RG-07', 'RG-09', 'RG-13')),
        'screens': (),
        'note': 'plan.md mục 5 không nêu tên màn riêng cho R4; user xem 10 video mẫu trên Dashboard',
    },
    {
        'code': 'R5',
        'title': 'Unattended Beta',
        'pending': ('M7-R5-EG1',),
        'gates': ('RG-08', 'RG-10'),
        'evidence': _r_evidence(('RG-08', 'RG-10')),
        'screens': ('batches', 'jobs', 'logs'),
        'note': '',
    },
    {
        'code': 'R6',
        'title': 'Operational Baseline',
        'pending': ('M7-R6',),
        'gates': (
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
        ),
        'evidence': _r_evidence((
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
        )),
        'screens': ('cost',),
        'note': 'G03 xem màn cost',
    },
)

def sha256_file(path: str | Path) -> str:
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_r_rows(repo: Path = REPO) -> list[dict]:
    rows: list[dict] = []
    for r in R_TABLE:
        evidence_list: list[tuple[str, str]] = []
        for rel_path in r['evidence']:
            if rel_path == 'docs/delivery-evidence/cp7-14/report.md':
                h = 'SELF'
            else:
                full = repo / rel_path
                if full.is_file():
                    h = sha256_file(full)
                else:
                    h = 'MISSING'
            evidence_list.append((rel_path, h))
        rows.append({
            'code': r['code'],
            'title': r['title'],
            'pending': r['pending'],
            'gates': r['gates'],
            'screens': r['screens'],
            'note': r['note'],
            'evidence': evidence_list,
        })
    return rows


def load_holdout(path: Path = MANIFEST_PATH) -> tuple[dict, str]:
    raw = path.read_bytes()
    manifest = json.loads(raw.decode('utf-8'))
    assert len(manifest.get('pairs', [])) == HOLDOUT_PAIRS, f'pairs count != {HOLDOUT_PAIRS}'
    digest = hashlib.sha256(raw.replace(bytes([13, 10]), bytes([10]))).hexdigest()
    return manifest, digest


def holdout_rows(manifest: dict) -> list[tuple[int, str, str]]:
    pairs = manifest.get('pairs', [])
    return [(i + 1, pair[0], pair[1]) for i, pair in enumerate(pairs)]


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    def _clean(val: object) -> str:
        s = '' if val is None else str(val)
        s = s.replace('|', '/').replace(chr(13) + chr(10), ' ').replace(chr(10), ' ').replace(chr(13), ' ')
        return s.strip()

    header_cells = [_clean(h) for h in headers]
    head_line = '|' + '|'.join(' ' + h + ' ' if h != '' else '  ' for h in header_cells) + '|'
    sep_line = '|' + '|'.join(' --- ' for _ in headers) + '|'
    data_lines = []
    for row in rows:
        row_cells = [_clean(c) for c in row]
        line = '|' + '|'.join(' ' + c + ' ' if c != '' else '  ' for c in row_cells) + '|'
        data_lines.append(line)
    all_lines = [head_line, sep_line] + data_lines
    return chr(10).join(all_lines)


def user_fields_empty(text: str) -> tuple[bool, int]:
    lines = text.splitlines()
    in_table = False
    headers: list[str] = []
    user_col_indices: list[int] = []
    checked_rows = 0
    ok = True
    found_table = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped[1:-1].split('|')]
            if not in_table:
                matching_indices = [idx for idx, c in enumerate(cells) if c in USER_HEADERS]
                if matching_indices:
                    in_table = True
                    found_table = True
                    headers = cells
                    user_col_indices = matching_indices
                continue
            else:
                if all(c.startswith('-') for c in cells if c):
                    continue
                for col_idx in user_col_indices:
                    if col_idx < len(cells):
                        if cells[col_idx] != '':
                            ok = False
                checked_rows += 1
        else:
            in_table = False
            headers = []
            user_col_indices = []

    if not found_table:
        return False, 0
    return ok, checked_rows


def approval_claims(text: str) -> list[str]:
    lowered = text.lower()
    forbidden = ('đã duyệt', 'da duyet', 'approved', 'accepted', '[x]')
    found: list[str] = []
    for token in forbidden:
        if token in lowered:
            found.append(token)
    return found

def budget_violations(ai_calls: int, spent_usd: str | Decimal, drive_bytes: int, elapsed_s: float) -> list[str]:
    bad: list[str] = []
    if ai_calls > AI_CALL_CAP:
        bad.append('ai_calls')
    if Decimal(str(spent_usd)) > LEDGER_CEILING_USD:
        bad.append('ledger_usd')
    if drive_bytes > DRIVE_CAP_BYTES:
        bad.append('drive_bytes')
    if elapsed_s > DEADLINE_SECONDS:
        bad.append('elapsed')
    return bad


def group_key_of(article_ids: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(article_ids)))


def angle_distinct(videos: list[dict]) -> dict:
    grouped: dict[tuple[str, ...], list[str]] = {}
    for v in videos:
        grp = v.get('group', ())
        grouped.setdefault(grp, []).append(v.get('angle_id', ''))

    duplicates: list[tuple[tuple[str, ...], str]] = []
    for grp, angles in grouped.items():
        seen: set[str] = set()
        for a in angles:
            if a in seen:
                if (grp, a) not in duplicates:
                    duplicates.append((grp, a))
            seen.add(a)

    has_empty_angle = any(not v.get('angle_id') for v in videos)
    multi_groups = sum(1 for angles in grouped.values() if len(angles) >= 2)
    ok = (
        len(videos) > 0
        and multi_groups >= 1
        and len(duplicates) == 0
        and not has_empty_angle
    )
    return {
        'groups': len(grouped),
        'multi_groups': multi_groups,
        'duplicates': duplicates,
        'ok': ok,
    }


def visual_violations(visuals: list[dict], safety_by_media: dict, processed_ok: dict) -> list[str]:
    violations: list[str] = []
    for v in visuals:
        m_id = str(v.get('media_asset_id') or '')
        id6 = m_id[:6]
        origin = v.get('origin')
        if not origin:
            violations.append(f'origin_missing:{id6}')
            continue
        if origin in ARTICLE_ORIGINS:
            outcome = safety_by_media.get(m_id)
            if not outcome:
                violations.append(f'safety_missing:{id6}')
            elif outcome not in SAFETY_OK:
                violations.append(f'safety_not_ok:{id6}:{outcome}')
            elif outcome == 'TRANSFORM_REQUIRED' and not processed_ok.get(m_id, False):
                violations.append(f'not_processed:{id6}')

    if not visuals or all(v.get('origin') == 'seed' for v in visuals):
        violations.append('only_seed_background')
    return violations


def evaluate_items(run: dict) -> dict[str, tuple[str, str]]:
    videos = run.get('videos', [])
    drive_checks = run.get('drive_checks', [])
    holdout_ok = run.get('holdout_ok', False)
    sheets_ok = run.get('sheets_ok', False)
    r_missing = run.get('r_missing', [])
    user_ok = run.get('user_ok', False)
    secret_matches = run.get('secret_matches', 0)

    # 1. sample_10_valid
    sample_valid = len(videos) == SAMPLE_VIDEOS and all(bool(v.get('valid')) for v in videos)
    sample_status = 'PASS' if sample_valid else 'FAIL'
    valid_count = sum(1 for v in videos if v.get('valid'))
    sample_detail = f"valid={valid_count}/{len(videos)}"

    # 2. cloud_verified_10
    cloud_count = sum(1 for v in videos if v.get('cloud_ok'))
    drive_matches = sum(1 for dc in drive_checks if dc.get('md5_match') and dc.get('sha256_match'))
    cloud_verified = (
        len(videos) == SAMPLE_VIDEOS
        and cloud_count == SAMPLE_VIDEOS
        and len(drive_checks) == SAMPLE_VIDEOS
        and drive_matches == SAMPLE_VIDEOS
    )
    cloud_status = 'PASS' if cloud_verified else 'FAIL'
    cloud_detail = f"cloud_ok={cloud_count}/{len(videos)} drive_matches={drive_matches}/{len(drive_checks)}"

    # 3. trace_per_video
    trace_clean = len(videos) > 0 and all(len(v.get('trace_missing', [])) == 0 for v in videos)
    missing_trace_count = sum(len(v.get('trace_missing', [])) for v in videos)
    trace_status = 'PASS' if trace_clean else 'FAIL'
    trace_detail = f"missing={missing_trace_count}"

    # 4. story_angle_distinct
    angle_eval = angle_distinct(videos)
    angle_status = 'PASS' if angle_eval['ok'] else 'FAIL'
    angle_detail = f"groups={angle_eval['groups']} multi={angle_eval['multi_groups']} dups={len(angle_eval['duplicates'])}"

    # 5. rights_unverified_excluded
    viol_clean = len(videos) > 0 and all(len(v.get('violations', [])) == 0 for v in videos)
    viol_total = sum(len(v.get('violations', [])) for v in videos)
    rights_status = 'PASS' if viol_clean else 'FAIL'
    rights_detail = f"violations={viol_total}"

    # 6. holdout_sheet_40
    holdout_status = 'PASS' if holdout_ok else 'FAIL'
    holdout_detail = f"holdout_ok={holdout_ok}"

    # 7. video_sheet_10
    sheet_status = 'PASS' if sheets_ok else 'FAIL'
    sheet_detail = f"sheets_ok={sheets_ok}"

    # 8. pack_r1_r6_complete
    pack_status = 'PASS' if len(r_missing) == 0 else 'FAIL'
    pack_detail = f"missing={len(r_missing)}"

    # 9. no_user_field_filled
    user_status = 'PASS' if user_ok else 'FAIL'
    user_detail = f"user_ok={user_ok}"

    # 10. secret_scan
    secret_status = 'PASS' if secret_matches == 0 else 'FAIL'
    secret_detail = f"matches={secret_matches}"

    return {
        'sample_10_valid': (sample_status, sample_detail),
        'cloud_verified_10': (cloud_status, cloud_detail),
        'trace_per_video': (trace_status, trace_detail),
        'story_angle_distinct': (angle_status, angle_detail),
        'rights_unverified_excluded': (rights_status, rights_detail),
        'holdout_sheet_40': (holdout_status, holdout_detail),
        'video_sheet_10': (sheet_status, sheet_detail),
        'pack_r1_r6_complete': (pack_status, pack_detail),
        'no_user_field_filled': (user_status, user_detail),
        'secret_scan': (secret_status, secret_detail),
    }

def render_r_section(rows: list[dict]) -> str:
    headers = ['R', 'Mã chờ gốc', 'Gate RG', 'Tệp bằng chứng', 'sha256', 'Màn Dashboard']
    table_rows: list[list[str]] = []
    for r in rows:
        code = r['code']
        pending = ' ; '.join(r['pending'])
        gates = ' ; '.join(r['gates'])
        screens = ' ; '.join(r['screens']) if r['screens'] else r.get('note', '')
        for ev_path, ev_sha in r['evidence']:
            table_rows.append([code, pending, gates, ev_path, ev_sha, screens])
    return (
        "## Bảng R1–R6" + chr(10) + chr(10)
        + md_table(headers, table_rows) + chr(10) + chr(10)
        + "Kết luận R1–R6 là của user; gói này chỉ chuẩn bị bằng chứng."
    )


def render_video_sheet(videos: list[dict]) -> str:
    headers = [
        'STT',
        'Job',
        'Topic',
        'Media/hook',
        'Cloud verified',
        'Nhãn topic (user)',
        'Nhãn media/hook (user)',
    ]
    rows: list[list[str]] = []
    for i, v in enumerate(videos):
        stt = str(i + 1)
        job = str(v.get('job_id') or '')
        topic = str(v.get('topic') or '')[:80]
        media_summary = str(v.get('media_summary') or '')
        cloud = 'PASS' if v.get('cloud_ok') else 'FAIL'
        rows.append([stt, job, topic, media_summary, cloud, '', ''])
    return "## Bảng chấm video" + chr(10) + chr(10) + md_table(headers, rows)


def render_holdout_sheet(manifest: dict, digest: str) -> str:
    headers = ['STT', 'Bài A', 'Bài B', 'Nhãn event-link (user)']
    rows: list[list[str]] = []
    for num, a, b in holdout_rows(manifest):
        rows.append([str(num), str(a), str(b), ''])
    return (
        "## Bảng 40 cặp holdout (event-link)" + chr(10) + chr(10)
        + f"holdout_manifest_sha256: {digest}" + chr(10) + chr(10)
        + md_table(headers, rows)
    )


def render_report(
    run: object,
    items: dict,
    batch_id: str,
    manifest: dict,
    digest: str,
    repo: Path = REPO,
) -> str:
    lines = [
        "# CP7-14 — Mẫu 20 video và gói bằng chứng nghiệm thu R1–R6 (RG-13)",
        "",
        "## Kết quả",
        "",
    ]
    for key in RG13_ITEMS:
        status, detail = items.get(key, ('FAIL', ''))
        lines.append(c.report_line('RG-13', key, status))
    lines.append("")
    for key in RG13_ITEMS:
        status, detail = items.get(key, ('FAIL', ''))
        lines.append(f"- {key}: {detail}")
    lines.append("")
    lines.append("## Ngân sách")
    lines.append("")
    ai_calls = getattr(run, 'ai_calls', 0) if hasattr(run, 'ai_calls') else run.get('ai_calls', 0)
    spent_usd = getattr(run, 'spent_usd', '0') if hasattr(run, 'spent_usd') else run.get('spent_usd', '0')
    drive_bytes = getattr(run, 'drive_bytes', 0) if hasattr(run, 'drive_bytes') else run.get('drive_bytes', 0)
    elapsed_seconds = (
        getattr(run, 'elapsed_seconds', 0.0)
        if hasattr(run, 'elapsed_seconds')
        else run.get('elapsed_seconds', 0.0)
    )
    lines.append(f"- Lời gọi AI: {ai_calls} (trần: {AI_CALL_CAP})")
    lines.append(f"- Chi phí ledger: {spent_usd} USD (trần: {LEDGER_CEILING_USD} USD)")
    lines.append(f"- Dung lượng Drive: {drive_bytes} byte ({drive_bytes / GIB:.2f} GiB, trần: 3 GiB)")
    lines.append(f"- Thời gian chạy: {elapsed_seconds:.1f} giây ({elapsed_seconds / 3600:.2f} giờ, trần: 4 giờ)")
    lines.append("")
    lines.append(f"Batch ID: `{batch_id}`")
    lines.append("")
    lines.append(
        "Theo quyết định của user ngày 04/11/2026, lô mẫu nghiệm thu được nâng lên 20 video (thay vì 10 video); "
        "profile.json không sửa (`batch.target.sample_run` giữ 10); trần ngân sách nhân đôi: ≤ 120 lời gọi AI, "
        "ledger +10 USD, Drive ≤ 3 GiB, ≤ 4 giờ; giữ nguyên tên các khóa báo cáo dạng *_10 để tương thích probe kiểm tra."
    )
    lines.append("")
    r_rows = build_r_rows(repo)
    lines.append(render_r_section(r_rows))
    lines.append("")
    videos = getattr(run, 'videos', []) if hasattr(run, 'videos') else run.get('videos', [])
    lines.append(render_video_sheet(videos))
    lines.append("")
    lines.append(render_holdout_sheet(manifest, digest))
    lines.append("")
    return chr(10).join(lines)

class SampleDb(m.OvernightDb):
    def selection_angle(self, job_id: str) -> str | None:
        rows = self.query(
            "SELECT payload->>'angle_ref' FROM controlplane.cp_creative_selections "
            "WHERE workspace_id = %s AND job_id = %s ORDER BY selection_revision DESC LIMIT 1",
            job_id,
        )
        return rows[0][0] if rows else None

    def angle_title(self, angle_id: str) -> str:
        if not angle_id:
            return ''
        rows = self.query(
            "SELECT payload->>'title' FROM controlplane.cp_story_angles "
            "WHERE workspace_id = %s AND (angle_id = %s OR position(%s in angle_id) > 0) LIMIT 1",
            angle_id,
            angle_id,
        )
        return (rows[0][0] or '') if rows else ''

    def snapshot_article_ids(self, snapshot_id: str) -> list[str]:
        snap = self.query(
            'SELECT payload FROM controlplane.cp_production_snapshots WHERE workspace_id = %s AND snapshot_id = %s',
            snapshot_id,
        )
        if not snap or not snap[0][0]:
            return []
        payload = snap[0][0]
        refs = payload.get('source_refs') or []
        if isinstance(refs, dict) and '@tuple' in refs:
            refs = refs['@tuple']
        out: list[str] = []
        for r in refs:
            if isinstance(r, dict) and r.get('ref_type') == 'article_revision':
                ref_id = r.get('ref_id')
                if ref_id and ref_id not in out:
                    out.append(ref_id)
        return out

    def image_safety_outcome(self, media_asset_id: str) -> str | None:
        rows = self.query(
            'SELECT record_key, revision, payload FROM controlplane.cp_image_safety_assessments '
            'WHERE workspace_id = %s AND position(%s in record_key) > 0 '
            'ORDER BY created_at DESC, revision DESC LIMIT 1',
            media_asset_id,
        )
        if rows:
            val = d._find_key(rows[0][2], 'outcome')
            if isinstance(val, dict):
                return val.get('value')
            return val
        p_rows = self.query(
            'SELECT payload FROM controlplane.cp_production_plans '
            'WHERE workspace_id = %s AND position(%s in cast(payload as text)) > 0 ORDER BY created_at DESC LIMIT 1',
            media_asset_id,
        )
        if not p_rows:
            return None
        plan = p_rows[0][0]
        art_ref = None
        for seg in (plan.get('timeline') or {}).get('segments') or []:
            for vis in seg.get('visuals') or []:
                if vis.get('media_asset_id') == media_asset_id:
                    art_ref = vis.get('artifact_version_ref')
                    break
            if art_ref:
                break
        if not art_ref:
            return None
        o_rows = self.query(
            'SELECT aggregate_id, payload FROM controlplane.cp_outbox_events '
            'WHERE workspace_id = %s AND event_name = %s AND position(%s in cast(payload as text)) > 0 '
            'ORDER BY occurred_at DESC LIMIT 1',
            'ImageSafetyAssessed',
            art_ref,
        )
        if not o_rows:
            return None
        rec_key = o_rows[0][1].get('assessment_ref', '').removeprefix('assessment:')
        if not rec_key:
            return None
        a_rows = self.query(
            'SELECT record_key, revision, payload FROM controlplane.cp_image_safety_assessments '
            'WHERE workspace_id = %s AND record_key = %s ORDER BY created_at DESC, revision DESC LIMIT 1',
            rec_key,
        )
        if not a_rows:
            return None
        val = d._find_key(a_rows[0][2], 'outcome')
        if isinstance(val, dict):
            return val.get('value')
        return val

    def processed_ok(self, media_asset_id: str) -> bool:
        rows = self.query(
            'SELECT record_key, revision, payload FROM controlplane.cp_processed_media '
            'WHERE workspace_id = %s AND position(%s in record_key) > 0 '
            'ORDER BY created_at DESC, revision DESC LIMIT 1',
            media_asset_id,
        )
        if rows:
            val = d._find_key(rows[0][2], 'status')
            if isinstance(val, dict):
                val = val.get('value')
            return str(val).lower() == 'success'
        p_rows = self.query(
            'SELECT payload FROM controlplane.cp_production_plans '
            'WHERE workspace_id = %s AND position(%s in cast(payload as text)) > 0 ORDER BY created_at DESC LIMIT 1',
            media_asset_id,
        )
        if not p_rows:
            return False
        plan = p_rows[0][0]
        art_ref = None
        for seg in (plan.get('timeline') or {}).get('segments') or []:
            for vis in seg.get('visuals') or []:
                if vis.get('media_asset_id') == media_asset_id:
                    art_ref = vis.get('artifact_version_ref')
                    break
            if art_ref:
                break
        if not art_ref:
            return False
        rows2 = self.query(
            'SELECT record_key, revision, payload FROM controlplane.cp_processed_media '
            'WHERE workspace_id = %s AND position(%s in cast(payload as text)) > 0 ORDER BY created_at DESC LIMIT 1',
            art_ref,
        )
        if not rows2:
            return False
        val2 = d._find_key(rows2[0][2], 'status')
        if isinstance(val2, dict):
            val2 = val2.get('value')
        return str(val2).lower() == 'success'


class SampleWatch(d.CostWatch):
    def check(self) -> None:
        c.CostGuard(LEDGER_CEILING_USD, self.spent).check()
        if self.calls() > AI_CALL_CAP:
            raise c.CostCeilingExceeded('AI call cap exceeded')


def require_restored_db(db: SampleDb) -> bool:
    name = db.launcher.active_db_name(db.layout)
    if not re.fullmatch(r'controlplane_[0-9]{14}', name):
        raise d.BlockedError('BLOCKED: hồ sơ production chưa ở CSDL sau restore (CP7-13)')
    return True


@dataclass
class SampleRun:
    batch_id: str = ''
    record_prefix: str = ''
    concurrency: dict = field(default_factory=dict)
    videos: list = field(default_factory=list)
    drive_checks: list = field(default_factory=list)
    ai_calls: int = 0
    spent_usd: str = '0'
    drive_bytes: int = 0
    elapsed_seconds: float = 0.0
    stop_reason: str = ''
    job_counts: dict = field(default_factory=dict)
    failed_final_jobs: list = field(default_factory=list)
    secret_matches: int = 0
    window_start: object = None
    other_workflows_running: int = -1

def audit_video(db: SampleDb, job_id: str) -> dict:
    ledger = db.ledger_row(job_id)
    cloud = [l for l in db.locations(job_id) if d.is_drive(l)]
    cloud_ok = len(cloud) == 1 and ledger is not None and d.ordering_proof(cloud[0], ledger) is not None
    trace = d.build_trace(db, job_id)
    trace_missing = d.trace_missing(trace)
    plan = d.plan_digest(db, job_id)
    render_ok = d.render_matches_plan(db, job_id, plan)
    try:
        hard_failed = d.qc_gates(db, job_id)['hard_failed']
    except d.BlockedError:
        hard_failed = 1
    valid = cloud_ok and render_ok and hard_failed == 0
    group = group_key_of(db.snapshot_article_ids(trace['snapshot_id']))
    angle_id = db.selection_angle(job_id) or ''
    plan_row = d._plan_row(db, job_id)
    plan_payload = plan_row[0] if plan_row else {}
    visuals: list[dict] = []
    timeline = plan_payload.get('timeline') or {}
    for segment in timeline.get('segments') or []:
        for vis in segment.get('visuals') or []:
            visuals.append({
                'media_asset_id': vis.get('media_asset_id'),
                'origin': vis.get('origin'),
            })
    safety_by_media: dict[str, str | None] = {}
    processed_ok_map: dict[str, bool] = {}
    for vis in visuals:
        m_id = vis.get('media_asset_id')
        origin = vis.get('origin')
        if m_id and origin in ARTICLE_ORIGINS:
            if m_id not in safety_by_media:
                safety_by_media[m_id] = db.image_safety_outcome(m_id)
            if m_id not in processed_ok_map:
                processed_ok_map[m_id] = db.processed_ok(m_id)
    violations = visual_violations(visuals, safety_by_media, processed_ok_map)
    topic = db.angle_title(angle_id)
    art_count = sum(1 for v in visuals if v.get('origin') == 'article')
    ai_count = sum(1 for v in visuals if v.get('origin') == 'ai_generated')
    seed_count = sum(1 for v in visuals if v.get('origin') == 'seed')
    hook_placement = plan_payload.get('hook_placement') or {}
    hook_ref = hook_placement.get('visual_hook_ref')
    hook_str = str(hook_ref)[:8] if hook_ref else ''
    media_summary = f"article={art_count} ai={ai_count} seed={seed_count} hook={hook_str}"
    return {
        'job_id': job_id,
        'valid': valid,
        'cloud_ok': cloud_ok,
        'trace_missing': trace_missing,
        'group': group,
        'angle_id': angle_id,
        'violations': violations,
        'topic': topic,
        'media_summary': media_summary,
    }


def run_sample(work_dir: str | Path, deadline_seconds: float = DEADLINE_SECONDS) -> SampleRun:
    launcher = d.load_launcher()
    db = SampleDb(launcher)
    require_restored_db(db)
    window_start = db.db_now()
    watch = SampleWatch(db, window_start)
    watch.check()
    t0 = time.monotonic()
    run = SampleRun(window_start=window_start)
    try:
        d.stop_until_exited()
        run.other_workflows_running = d.require_no_other_workflows()
        launch_path, _, _ = d.start_capturing(work_dir, 'first')
        d.require_render_config(db)
        session = m.OvernightSession(db.layout.cert_file)
        session.open(launch_path)
        run.concurrency = session.get_batch_settings()
        batch_id = session.post_overnight_batch(SAMPLE_VIDEOS, run.concurrency['default'])
        run.batch_id = batch_id
        prefix = d.video_key_prefix(db.workspace_id, batch_id)
        run.record_prefix = prefix
        watch.bind_prefix(prefix)

        deadline = c.Deadline(deadline_seconds)
        stop_reason = ''
        while True:
            try:
                watch.check()
            except c.CostCeilingExceeded:
                stop_reason = 'cost_cap'
                break
            except c.DeadlineExceeded:
                stop_reason = 'deadline'
                break
            if deadline.remaining() <= 0:
                stop_reason = 'deadline'
                break
            valid_count = db.valid_synced_count(batch_id)
            if valid_count >= SAMPLE_VIDEOS:
                stop_reason = 'target_reached'
                break
            status = db.batch_status(batch_id)
            if status in m.TERMINAL_BATCH:
                stop_reason = 'batch_terminal'
                break
            time.sleep(30)
        run.stop_reason = stop_reason

        d.stop_until_exited()
        jobs = db.batch_jobs(batch_id)
        run.job_counts = db.batch_job_counts(batch_id)
        run.failed_final_jobs = [j for j, s in jobs if s == 'FAILED_FINAL']
        completed_jobs = [j for j, s in jobs if s == 'COMPLETED']
        run.videos = [audit_video(db, j) for j in completed_jobs[:SAMPLE_VIDEOS]]
        drive_checks = []
        for v in run.videos:
            for l in db.locations(v['job_id']):
                if d.is_drive(l):
                    chk = d.drive_md5_check(db, l)
                    drive_checks.append({
                        'md5_match': chk.get('md5_match', False),
                        'sha256_match': chk.get('sha256_match', False),
                        'size': chk.get('size', 0),
                    })
        run.drive_checks = drive_checks
        run.ai_calls = db.ai_invocation_count(prefix)
        run.spent_usd = str(watch.spent())
        run.drive_bytes = db.batch_drive_bytes(batch_id)
        run.elapsed_seconds = time.monotonic() - t0

        paths = [p for p in Path(db.layout.logs_dir).glob('*.log')] if Path(db.layout.logs_dir).is_dir() else []
        if Path(db.layout.serve_log).is_file():
            paths.append(Path(db.layout.serve_log))
        matches = 0
        for path in paths:
            try:
                matches += len(c.scan_secrets(path.read_text(encoding='utf-8', errors='replace')))
            except OSError:
                continue
        run.secret_matches = matches
        return run
    finally:
        try:
            d.stop_until_exited()
        except Exception:
            pass
