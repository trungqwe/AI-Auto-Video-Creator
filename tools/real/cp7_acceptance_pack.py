"""CP7-14 / RG-13, gói nghiệm thu R1–R6 và đọc lại lô mẫu đã chạy xong (đính chính Control 05/11/2026 theo quyết định user seq 18: mẫu nghiệm thu là 10 video; không chạy lô mới, không khởi launcher, chỉ đọc CSDL và Drive; trần kế hoạch 60 lời gọi AI, ledger +5 USD, Drive 1,5 GiB, 3 giờ; cách dừng `python tools/launcher/launcher.py stop`, `Deadline`, `CostGuard`; không in capability, cookie, token)."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import cp7_batch_driver as d
import cp7_common as c
import cp7_overnight_monitor as m

REPO = Path(__file__).resolve().parents[2]
GIB = 1024 ** 3
SAMPLE_VIDEOS = 10
HOLDOUT_PAIRS = 40
AI_CALL_CAP = 60
LEDGER_CEILING_USD = Decimal('5')
DRIVE_CAP_BYTES = 3 * GIB // 2
DEADLINE_SECONDS = 3 * 3600
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
UNVERIFIED_KEYS = ('safe', 'masked', 'unmasked_minor_child', 'other_unmasked', 'unassessed')

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




def budget_gate_violations(ai_calls: int, spent_usd: str | Decimal, drive_bytes: int, elapsed_s: float) -> list[str]:
    """Số lời gọi AI chỉ là số đo (Control 05/11/2026, 9 lần provider timeout), không phải khoá nghiệm thu."""
    return [k for k in budget_violations(ai_calls, spent_usd, drive_bytes, elapsed_s) if k != 'ai_calls']


def select_sheet(videos: list[dict]) -> list[dict]:
    """videos theo thứ tự hoàn tất; sheet là SAMPLE_VIDEOS video hợp lệ và cloud verified đầu tiên."""
    return [v for v in videos if v.get('valid') and v.get('cloud_ok')][:SAMPLE_VIDEOS]
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


def visual_violations(visuals: list[dict], categories_by_media: dict, processed_ok: dict) -> list[str]:
    violations: list[str] = []
    for v in visuals:
        m_id = str(v.get('media_asset_id') or '')
        id6 = m_id[:6]
        origin = v.get('origin')
        if not origin:
            violations.append(f'origin_missing:{id6}')
            continue
        if origin in ARTICLE_ORIGINS:
            if 'minor_child' in (categories_by_media.get(m_id) or ()) and not processed_ok.get(m_id, False):
                violations.append(f'minor_child_unmasked:{id6}')

    if not visuals or all(v.get('origin') == 'seed' for v in visuals):
        violations.append('only_seed_background')
    return violations


def classify_unverified(
    visuals: list[dict],
    safety_by_media: dict,
    categories_by_media: dict,
    processed_ok: dict,
) -> dict[str, int]:
    counts = {k: 0 for k in UNVERIFIED_KEYS}
    for v in visuals:
        if v.get('origin') != 'article':
            continue
        m_id = str(v.get('media_asset_id') or '')
        outcome = safety_by_media.get(m_id)
        if outcome is None:
            counts['unassessed'] += 1
        elif processed_ok.get(m_id):
            counts['masked'] += 1
        elif outcome == 'SAFE':
            counts['safe'] += 1
        elif 'minor_child' in (categories_by_media.get(m_id) or ()):
            counts['unmasked_minor_child'] += 1
        else:
            counts['other_unmasked'] += 1
    return counts


def sum_unverified(videos: list[dict]) -> dict[str, int]:
    total = {k: 0 for k in UNVERIFIED_KEYS}
    for v in videos:
        u = v.get('unverified') or {}
        for k in UNVERIFIED_KEYS:
            total[k] += int(u.get(k, 0))
    return total

def evaluate_items(run: dict) -> dict[str, tuple[str, str]]:
    videos = run.get('videos', [])
    drive_checks = run.get('drive_checks', [])
    holdout_ok = run.get('holdout_ok', False)
    sheets_ok = run.get('sheets_ok', False)
    r_missing = run.get('r_missing', [])
    user_ok = run.get('user_ok', False)
    secret_matches = run.get('secret_matches', 0)

    sheet = select_sheet(videos)
    valid_all = [v for v in videos if v.get('valid')]

    # 1. sample_10_valid
    sample_valid = len(valid_all) >= SAMPLE_VIDEOS
    sample_status = 'PASS' if sample_valid else 'FAIL'
    valid_count = len(valid_all)
    sample_detail = f"valid={valid_count}/{len(videos)} need>={SAMPLE_VIDEOS}"

    # 2. cloud_verified_10
    cloud_count = sum(1 for v in videos if v.get('valid') and v.get('cloud_ok'))
    drive_matches = sum(1 for dc in drive_checks if dc.get('md5_match') and dc.get('sha256_match'))
    cloud_verified = cloud_count >= SAMPLE_VIDEOS and drive_matches >= SAMPLE_VIDEOS
    cloud_status = 'PASS' if cloud_verified else 'FAIL'
    cloud_detail = f"cloud_ok={cloud_count}/{len(videos)} drive_matches={drive_matches}/{len(drive_checks)} need>={SAMPLE_VIDEOS}"

    # 3. trace_per_video
    trace_clean = len(sheet) == SAMPLE_VIDEOS and all(len(v.get('trace_missing', [])) == 0 for v in sheet)
    missing_trace_count = sum(len(v.get('trace_missing', [])) for v in sheet)
    trace_status = 'PASS' if trace_clean else 'FAIL'
    trace_detail = f"missing={missing_trace_count} sheet={len(sheet)}"

    # 4. story_angle_distinct
    angle_eval = angle_distinct(valid_all)
    angle_status = 'PASS' if angle_eval['ok'] else 'FAIL'
    angle_detail = f"groups={angle_eval['groups']} multi={angle_eval['multi_groups']} dups={len(angle_eval['duplicates'])}"

    # 5. rights_unverified_excluded
    viol_clean = len(sheet) == SAMPLE_VIDEOS and all(len(v.get('violations', [])) == 0 for v in sheet)
    viol_total = sum(len(v.get('violations', [])) for v in sheet)
    u = sum_unverified(sheet)
    rights_status = 'PASS' if viol_clean else 'FAIL'
    rights_detail = f"violations={viol_total} sheet={len(sheet)} unverified_safe={u['safe']} masked={u['masked']} unmasked_minor_child={u['unmasked_minor_child']} other_unmasked={u['other_unmasked']} unassessed={u['unassessed']}"

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
        "# CP7-14 — Mẫu 10 video và gói bằng chứng nghiệm thu R1–R6 (RG-13)",
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
    lines.append(f"- Lời gọi AI: {ai_calls} (số đo; trần kế hoạch {AI_CALL_CAP} không phải khoá nghiệm thu)")
    lines.append(f"- Chi phí ledger: {spent_usd} USD (trần: {LEDGER_CEILING_USD} USD)")
    lines.append(f"- Dung lượng Drive: {drive_bytes} byte ({drive_bytes / GIB:.2f} GiB, trần: 1,5 GiB)")
    lines.append(f"- Thời gian chạy: {elapsed_seconds:.1f} giây ({elapsed_seconds / 3600:.2f} giờ, trần: 3 giờ)")
    lines.append("")
    lines.append(f"Batch ID: `{batch_id}`")
    lines.append("")
    lines.append(
        f"Đính chính của Control ngày 05/11/2026 theo quyết định của user (seq 18, CLOSURE_NOTE CP7/RG-10): "
        f"mẫu nghiệm thu là 10 video, không phải 20. Lô `{batch_id}` đã chạy xong từ trước; báo cáo này chỉ "
        f"đọc lại CSDL và Drive của lô đó, không chạy lô mới và không khởi launcher. `sample_10_valid` và "
        f"`cloud_verified_10` PASS khi lô có ít nhất 10 video hợp lệ và cloud verified; bảng chấm video lấy "
        f"10 video hợp lệ đầu theo thứ tự hoàn tất. Theo CLOSURE_NOTE seq 17 (MC-POLICY) và seq 15 (RG-13), "
        f"ảnh UNVERIFIED được dùng; `rights_unverified_excluded` PASS khi 0 ảnh có nhãn minor_child vào "
        f"10 video mà chưa che. Số lời gọi AI là số đo (lô có 9 lần provider timeout), không phải khoá nghiệm thu."
    )
    lines.append("")
    videos = getattr(run, 'videos', []) if hasattr(run, 'videos') else run.get('videos', [])
    sheet = select_sheet(videos)
    u = sum_unverified(sheet)
    cloud_verified_count = sum(1 for v in videos if v.get('valid') and v.get('cloud_ok'))
    lines.append("## Lô")
    lines.append("")
    lines.append(f"- Video hoàn tất trong lô: {len(videos)}")
    lines.append(f"- Video hợp lệ và cloud verified: {cloud_verified_count}")
    lines.append(
        f"- Ảnh UNVERIFIED trong 10 video mẫu theo trạng thái xử lý: an toàn không cần che={u['safe']}; "
        f"đã che={u['masked']}; cần che (minor_child) nhưng chưa che={u['unmasked_minor_child']}; "
        f"nhãn khác chưa che, dùng nguyên bản theo chính sách={u['other_unmasked']}; "
        f"chưa có đánh giá an toàn={u['unassessed']}"
    )
    lines.append("")
    r_rows = build_r_rows(repo)
    lines.append(render_r_section(r_rows))
    lines.append("")
    lines.append(render_video_sheet(select_sheet(videos)))
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
        candidates = []
        for cand in (angle_id, angle_id.removeprefix('angle:')):
            if cand and cand not in candidates:
                candidates.append(cand)
        for cand in candidates:
            rows = self.query(
                'SELECT payload FROM controlplane.cp_story_angles WHERE workspace_id = %s AND angle_id = %s',
                cand,
            )
            if rows and rows[0][0]:
                t = d._find_key(rows[0][0], 'title')
                if isinstance(t, dict):
                    t = t.get('value')
                if t:
                    return str(t)
        rows = self.query(
            'SELECT payload FROM controlplane.cp_story_angles WHERE workspace_id = %s AND (position(%s in angle_id) > 0) LIMIT 1',
            angle_id,
        )
        if rows and rows[0][0]:
            t = d._find_key(rows[0][0], 'title')
            if isinstance(t, dict):
                t = t.get('value')
            if t:
                return str(t)
        return ''

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

    def _safety_payload(self, media_asset_id: str) -> dict | None:
        rows = self.query(
            'SELECT record_key, revision, payload FROM controlplane.cp_image_safety_assessments '
            'WHERE workspace_id = %s AND position(%s in record_key) > 0 '
            'ORDER BY created_at DESC, revision DESC LIMIT 1',
            media_asset_id,
        )
        if rows:
            return rows[0][2]
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
        return a_rows[0][2]

    def image_safety_outcome(self, media_asset_id: str) -> str | None:
        payload = self._safety_payload(media_asset_id)
        if payload is None:
            return None
        val = d._find_key(payload, 'outcome')
        if isinstance(val, dict):
            return val.get('value')
        return val

    def image_safety_categories(self, media_asset_id: str) -> tuple:
        payload = self._safety_payload(media_asset_id)
        if payload is None:
            return ()
        raw = d._find_key(payload, 'categories')
        if isinstance(raw, dict) and '@tuple' in raw:
            raw = raw['@tuple']
        if not isinstance(raw, (list, tuple)):
            return ()
        items = []
        for x in raw:
            if isinstance(x, dict):
                items.append(x.get('value'))
            else:
                items.append(x)
        return tuple(str(x) for x in items if x)

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

    def completed_in_order(self, batch_id: str) -> list[str]:
        rows = self.query(
            'SELECT cl.job_id FROM controlplane.cp_completion_ledger cl '
            'JOIN controlplane.cp_video_jobs v ON v.workspace_id = cl.workspace_id AND v.job_id = cl.job_id '
            'WHERE cl.workspace_id = %s AND v.batch_id = %s ORDER BY cl.completed_at, cl.job_id',
            batch_id,
        )
        return [r[0] for r in rows]

    def batch_window(self, batch_id: str) -> tuple:
        rows = self.query(
            'SELECT min(v.created_at), max(cl.completed_at) FROM controlplane.cp_video_jobs v '
            'LEFT JOIN controlplane.cp_completion_ledger cl ON cl.workspace_id = v.workspace_id AND cl.job_id = v.job_id '
            'WHERE v.workspace_id = %s AND v.batch_id = %s',
            batch_id,
        )
        return (rows[0][0], rows[0][1])


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
    categories_by_media: dict[str, tuple] = {}
    processed_ok_map: dict[str, bool] = {}
    for vis in visuals:
        m_id = vis.get('media_asset_id')
        origin = vis.get('origin')
        if m_id and origin in ARTICLE_ORIGINS:
            if m_id not in safety_by_media:
                safety_by_media[m_id] = db.image_safety_outcome(m_id)
            if m_id not in categories_by_media:
                categories_by_media[m_id] = db.image_safety_categories(m_id)
            if m_id not in processed_ok_map:
                processed_ok_map[m_id] = db.processed_ok(m_id)
    violations = visual_violations(visuals, categories_by_media, processed_ok_map)
    unverified = classify_unverified(visuals, safety_by_media, categories_by_media, processed_ok_map)
    topic = db.angle_title(angle_id) or angle_id
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
        'unverified': unverified,
        'topic': topic,
        'media_summary': media_summary,
    }


def reaudit_batch(batch_id: str) -> SampleRun:
    launcher = d.load_launcher()
    db = SampleDb(launcher)
    require_restored_db(db)
    start, end = db.batch_window(batch_id)
    if start is None:
        raise d.BlockedError('BLOCKED: lô không có job trong CSDL: ' + batch_id[:8])
    run = SampleRun(batch_id=batch_id, window_start=start)
    prefix = d.video_key_prefix(db.workspace_id, batch_id)
    run.record_prefix = prefix
    run.stop_reason = 'reaudit_read_only'
    jobs = db.batch_jobs(batch_id)
    run.job_counts = db.batch_job_counts(batch_id)
    run.failed_final_jobs = [j for j, s in jobs if s == 'FAILED_FINAL']
    run.videos = [audit_video(db, j) for j in db.completed_in_order(batch_id)]
    drive_checks = []
    for v in run.videos:
        for l in db.locations(v['job_id']):
            if d.is_drive(l):
                chk = d.drive_md5_check(db, l)
                drive_checks.append({
                    'job_id': v['job_id'],
                    'md5_match': chk.get('md5_match', False),
                    'sha256_match': chk.get('sha256_match', False),
                    'size': chk.get('size', 0),
                })
    run.drive_checks = drive_checks
    run.ai_calls = db.ai_invocation_count(prefix)
    run.spent_usd = str(d.CostWatch(db, start).spent())
    run.drive_bytes = db.batch_drive_bytes(batch_id)
    run.elapsed_seconds = (end - start).total_seconds() if end is not None else 0.0

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
