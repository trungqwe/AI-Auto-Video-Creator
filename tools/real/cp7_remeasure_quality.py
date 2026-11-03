"""CP7-REMEASURE: chỉ số hình và tiếng của một lô thật đã chạy (chỉ đọc, không mạng ngoài CSDL cục bộ, không gọi AI).

Lô 100 video chạy bằng chính test của CP7-11 (`CP7_RG10_LIVE=1 python -m pytest tests/real/test_cp7_overnight.py`), ngưỡng RG-10
giữ nguyên. Sau lô, `CP7_REMEASURE_BATCH_PREFIX=<8 ký tự đầu Batch ID> python -m pytest tests/real/test_cp7_remeasure.py -k test_cq`
đọc CSDL (SELECT, default_transaction_read_only) và in các dòng `CQ.*` cùng số đo `- cq: ...` cho báo cáo
docs/delivery-evidence/cp7-remeasure/report.md. Hàm thuần ở đầu tệp nhận dữ liệu đã đọc nên test được bằng dữ liệu giả.

Nguồn sự thật của một video là render package mới nhất của job (đúng snapshot ở sổ hoàn tất): timeline sau khi thay ảnh an toàn
(visuals[].origin, allowed_fallbacks `image-safety:*`), hook_placement (hook_id), mix_plan.beds (bản nhạc). Bố cục lấy từ
production plan mà package trỏ tới (layout_choice.layout_key). Nguồn hook lấy từ revision hiện hành của hook như render đọc.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field

import cp7_overnight_monitor as m

LAYOUT_KEYS = ('HERO_STRIP', 'MOSAIC_GRID', 'FULL_BLEED_INSET', 'SPLIT_STACK', 'DATA_CARD')
LAYOUT_SHARE_MAX = 0.4
ORIGIN_SEED = 'seed'
ORIGIN_ARTICLE = 'article'
ORIGIN_AI = 'ai_generated'
ORIGIN_REPLACED = 'replaced'
NON_SEED_ORIGINS = (ORIGIN_ARTICLE, ORIGIN_AI, ORIGIN_REPLACED)
IMAGE_SAFETY_RULE_PREFIX = 'image-safety:'
SEED_FALLBACK_REASON = 'seed_fallback'
PLACEHOLDER_METADATA_KEY = 'recipe_template'
HOOK_KINDS = ('visual_hook', 'audio_hook')
CQ_STATUSES = ('PASS', 'FAIL', 'OVER')

# Lượt đo trước trên dây chuyền cũ: CP7-11 Lượt 4, lô 74e795ef (docs/delivery-evidence/cp7-11/report.md).
PREVIOUS = {'batch': '74e795ef', 't_target_s': 6849.0, 'pytest_s': 6906.16, 'lead_p50_s': 364.6, 'lead_p95_s': 748.1,
            'videos_per_hour': 52.6, 'jobs': 101, 'failed_final': 1}
PREVIOUS_STAGE_P50_S = {'analyze': 42.3, 'script': 98.3, 'plan': 66.7, 'media_select': 50.3, 'tts': 15.9, 'align': 9.9,
                        'process': 27.5, 'render': 13.5, 'qc': 3.2, 'sync': 13.7, 'complete': 0.1}


def _mappings(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, (list, tuple)) else []


def _int_ms(value):
    return isinstance(value, int) and not isinstance(value, bool)


def union_ms(spans):
    """Tổng độ dài hợp các khoảng [start, end) (ms), khoảng chồng chỉ tính một lần."""
    total = 0
    reach = None
    for start, end in sorted(spans):
        if reach is not None:
            start = max(start, reach)
        if end > start:
            total += end - start
        reach = end if reach is None else max(reach, end)
    return total


def hook_source(technical_metadata):
    """Nguồn của một revision hook như PostgresHookLibrary.count_by_source: 'placeholder' nếu có recipe_template, không thì hook_source, không có thì 'other'."""
    pairs = dict(tuple(pair) for pair in technical_metadata or () if isinstance(pair, (list, tuple)) and len(pair) == 2)
    if PLACEHOLDER_METADATA_KEY in pairs:
        return 'placeholder'
    return pairs.get('hook_source') or 'other'


def final_visuals(package):
    """Ảnh của từng cảnh trong timeline cuối của render package, với origin cuối:
    ảnh bị thay bằng seed (luật image-safety reason seed_fallback) là 'seed'; bị thay bằng ảnh khác là 'replaced'; còn lại giữ origin
    của visual (thiếu origin thì 'unknown', không được tính là ảnh minh hoạ)."""
    rules = [r for r in _mappings(package.get('allowed_fallbacks')) if str(r.get('rule_id', '')).startswith(IMAGE_SAFETY_RULE_PREFIX)]
    to_seed = {r.get('replaced_media_asset_id') for r in rules if r.get('reason') == SEED_FALLBACK_REASON}
    to_other = {r.get('replaced_media_asset_id') for r in rules if r.get('reason') != SEED_FALLBACK_REASON}
    timeline = package.get('timeline') if isinstance(package.get('timeline'), dict) else {}
    out = []
    for scene in _mappings(timeline.get('segments')):
        if not (_int_ms(scene.get('start_ms')) and _int_ms(scene.get('end_ms'))):
            continue
        for visual in _mappings(scene.get('visuals')):
            if not (_int_ms(visual.get('start_ms')) and _int_ms(visual.get('end_ms'))):
                continue
            media = visual.get('media_asset_id')
            if media in to_seed:
                origin = ORIGIN_SEED
            elif media in to_other:
                origin = ORIGIN_REPLACED
            else:
                origin = visual.get('origin') if isinstance(visual.get('origin'), str) and visual.get('origin') else 'unknown'
            ref = visual.get('artifact_version_ref')
            out.append({'media_asset_id': media, 'ref': ref.lower() if isinstance(ref, str) else None, 'origin': origin,
                        'start_ms': max(scene['start_ms'], visual['start_ms']), 'end_ms': min(scene['end_ms'], visual['end_ms'])})
    return out


def video_row(job_id, package, plan, hooks):
    """Một dòng chỉ số của một video hợp lệ. hooks: {hook_id: {'kind', 'source', 'query'}}."""
    visuals = final_visuals(package)
    timeline = package.get('timeline') if isinstance(package.get('timeline'), dict) else {}
    scenes = [s for s in _mappings(timeline.get('segments')) if _int_ms(s.get('start_ms')) and _int_ms(s.get('end_ms'))]
    timeline_ms = union_ms([(s['start_ms'], s['end_ms']) for s in scenes])
    seed_ms = union_ms([(v['start_ms'], v['end_ms']) for v in visuals if v['origin'] not in NON_SEED_ORIGINS])
    placement = package.get('hook_placement') if isinstance(package.get('hook_placement'), dict) else {}
    choice = (plan or {}).get('layout_choice') if isinstance((plan or {}).get('layout_choice'), dict) else {}
    beds = _mappings((package.get('mix_plan') or {}).get('beds') if isinstance(package.get('mix_plan'), dict) else None)
    row = {
        'job': job_id,
        'layout': choice.get('layout_key') or 'none',
        'layout_fallback': choice.get('fallback_reason') or None,
        'scenes': len(scenes),
        'duration_s': round(max((s['end_ms'] for s in scenes), default=0) / 1000, 1),
        'ai_images': len({v['ref'] for v in visuals if v['origin'] == ORIGIN_AI and v['ref']}),
        'article_images': len({v['ref'] for v in visuals if v['origin'] == ORIGIN_ARTICLE and v['ref']}),
        'replaced_images': len({v['media_asset_id'] for v in visuals if v['origin'] == ORIGIN_REPLACED}),
        'seed_share_pct': round(seed_ms * 100 / timeline_ms, 1) if timeline_ms else 100.0,
        'background_only': not any(v['origin'] in NON_SEED_ORIGINS for v in visuals),
        'music': sorted({b.get('rendition_ref') for b in beds if isinstance(b.get('rendition_ref'), str)}),
    }
    for kind, key in (('visual_hook', 'visual_hook_ref'), ('audio_hook', 'audio_hook_ref')):
        ref = placement.get(key)
        info = hooks.get(ref) if isinstance(ref, str) else None
        row[kind] = ref if isinstance(ref, str) else None
        row[kind + '_source'] = 'missing' if info is None else info.get('source') or 'other'
        row[kind + '_query'] = None if info is None else info.get('query')
    return row


def layout_counts(layout_keys, target):
    """Đếm bố cục và trần của lô: floor(LAYOUT_SHARE_MAX * target), ít nhất 1 (creative.domain.layout_choice.capped_layouts)."""
    counts = Counter(key or 'none' for key in layout_keys)
    limit = max(1, math.floor(LAYOUT_SHARE_MAX * target)) if target > 0 else None
    over = {key: n for key, n in counts.items() if limit is not None and n > limit}
    return {'counts': dict(sorted(counts.items())), 'limit': limit, 'over': dict(sorted(over.items())), 'distinct': len(counts)}


def _stats(values):
    vals = sorted(values)
    if not vals:
        return {'n': 0, 'min': None, 'p50': None, 'max': None, 'total': 0}
    return {'n': len(vals), 'min': vals[0], 'p50': m.percentile(vals, 50), 'max': vals[-1], 'total': sum(vals)}


def target_span_s(batch_created_epoch, completed_epochs, target):
    """Giây từ lúc tạo lô tới video hoàn tất thứ `target`; None khi chưa đủ."""
    done = sorted(completed_epochs)
    if len(done) < target or target < 1:
        return None
    return round(done[target - 1] - batch_created_epoch, 1)


def summarize(rows, *, target, plan_layouts, failure_causes, leads, span_s, stage_rows):
    """Tổng hợp chỉ số của lô. plan_layouts: layout_key của mọi job không FAILED_FINAL (đúng tập trần 40% đếm)."""
    hooks = {kind: Counter(r[kind + '_source'] for r in rows) for kind in HOOK_KINDS}
    placeholders = sum(hooks[kind].get('placeholder', 0) + hooks[kind].get('missing', 0) for kind in HOOK_KINDS)
    stages = m.stage_metrics(stage_rows)
    lead50, lead95 = m.percentile(leads, 50), m.percentile(leads, 95)
    return {
        'videos': len(rows),
        'layout_valid': layout_counts([r['layout'] for r in rows], target),
        'layout_batch': layout_counts(plan_layouts, target),
        'layout_fallbacks': dict(sorted(Counter(r['layout_fallback'] for r in rows if r['layout_fallback']).items())),
        'ai_images': _stats([r['ai_images'] for r in rows]),
        'videos_with_ai': sum(1 for r in rows if r['ai_images'] > 0),
        'article_images': _stats([r['article_images'] for r in rows]),
        'background_only': sorted(r['job'] for r in rows if r['background_only']),
        'seed_share_max_pct': max((r['seed_share_pct'] for r in rows), default=None),
        'scenes': _stats([r['scenes'] for r in rows]),
        'duration_s': _stats([r['duration_s'] for r in rows]),
        'hook_sources': {kind: dict(sorted(hooks[kind].items())) for kind in HOOK_KINDS},
        'hook_not_real': placeholders,
        'distinct_visual_hooks': len({r['visual_hook'] for r in rows if r['visual_hook']}),
        'distinct_audio_hooks': len({r['audio_hook'] for r in rows if r['audio_hook']}),
        'distinct_audio_hook_queries': len({r['audio_hook_query'] for r in rows if r['audio_hook_query']}),
        'distinct_music': len({ref for r in rows for ref in r['music']}),
        'videos_without_music': sum(1 for r in rows if not r['music']),
        'failure_causes': list(failure_causes),
        'lead_p50_s': None if lead50 is None else round(lead50, 1),
        'lead_p95_s': None if lead95 is None else round(lead95, 1),
        'span_s': span_s,
        'stage_p50_s': {k: v['p50_s'] for k, v in stages.items()},
    }


def cq_line(item, status):
    if status not in CQ_STATUSES:
        raise ValueError('invalid status')
    return f'CQ.{item}: {status}'


def _delta(now, before):
    if now is None:
        return 'n/a'
    return format(now - before, '+.1f')


def quality_lines(summary, batch_prefix):
    """Dòng bằng chứng ASCII: ba dòng CQ.* rồi số đo '- cq: ...'."""
    j = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'))
    lines = [
        cq_line('no_background_only', 'PASS' if summary['videos'] and not summary['background_only'] else 'FAIL'),
        cq_line('real_hooks', 'PASS' if summary['videos'] and summary['hook_not_real'] == 0 else 'FAIL'),
        cq_line('layout_cap_40', 'PASS' if not summary['layout_batch']['over'] else 'OVER'),
        '- cq: batch=' + batch_prefix + ' videos=' + str(summary['videos']),
        '- cq: layout_valid=' + j(summary['layout_valid']),
        '- cq: layout_batch=' + j(summary['layout_batch']),
        '- cq: layout_fallbacks=' + j(summary['layout_fallbacks']),
        '- cq: ai_images=' + j(summary['ai_images']) + ' videos_with_ai=' + str(summary['videos_with_ai']),
        '- cq: article_images=' + j(summary['article_images']),
        '- cq: background_only=' + str(len(summary['background_only'])) + ' seed_share_max_pct=' + str(summary['seed_share_max_pct']),
        '- cq: scenes=' + j(summary['scenes']) + ' duration_s=' + j(summary['duration_s']),
        '- cq: hook_sources=' + j(summary['hook_sources']) + ' not_real=' + str(summary['hook_not_real']),
        '- cq: distinct_visual_hooks=' + str(summary['distinct_visual_hooks']) + ' distinct_audio_hooks=' + str(summary['distinct_audio_hooks'])
        + ' distinct_audio_hook_queries=' + str(summary['distinct_audio_hook_queries']),
        '- cq: distinct_music=' + str(summary['distinct_music']) + ' videos_without_music=' + str(summary['videos_without_music']),
        '- cq: span_s=' + str(summary['span_s']) + ' prev_t_target_s=' + format(PREVIOUS['t_target_s'], '.0f')
        + ' delta_s=' + _delta(summary['span_s'], PREVIOUS['t_target_s']),
        '- cq: lead_p50_s=' + str(summary['lead_p50_s']) + ' prev=' + str(PREVIOUS['lead_p50_s'])
        + ' lead_p95_s=' + str(summary['lead_p95_s']) + ' prev=' + str(PREVIOUS['lead_p95_s']),
    ]
    for stage, before in PREVIOUS_STAGE_P50_S.items():
        now = summary['stage_p50_s'].get(stage)
        lines.append(f'- cq: stage_p50 {stage} now={now} prev={before} delta={_delta(now, before)}')
    for cause in summary['failure_causes']:
        lines.append(f"- cq: failed_final stage={cause['stage']} code={cause['code']} activity={cause['activity']} n={cause['n']}")
    return [line.encode('ascii', 'backslashreplace').decode('ascii') for line in lines]


# --- truy vấn chỉ đọc ------------------------------------------------------------------------------------------

class QualityDb(m.OvernightDb):
    """Truy vấn chỉ đọc cho chỉ số hình và tiếng (mỗi câu bắt đầu bằng SELECT, lọc workspace_id = %s)."""

    def resolve_batch(self, prefix):
        rows = self.query('SELECT b.batch_id, b.target_count, EXTRACT(EPOCH FROM b.created_at) FROM controlplane.cp_production_batches b '
                          'WHERE b.workspace_id = %s AND starts_with(b.batch_id::text, %s)', prefix)
        return [(r[0], int(r[1]), float(r[2])) for r in rows]

    def completed_epochs(self, batch_id):
        rows = self.query('SELECT EXTRACT(EPOCH FROM cl.completed_at) FROM controlplane.cp_completion_ledger cl JOIN controlplane.cp_video_jobs v '
                          'ON v.workspace_id = cl.workspace_id AND v.job_id = cl.job_id WHERE cl.workspace_id = %s AND v.batch_id = %s', batch_id)
        return [float(r[0]) for r in rows]

    def render_packages(self, batch_id):
        """{job_id: payload} của render package mới nhất ứng với snapshot ở sổ hoàn tất của mỗi job đã hoàn tất."""
        rows = self.query(
            'SELECT DISTINCT ON (cl.job_id) cl.job_id, p.payload FROM controlplane.cp_completion_ledger cl '
            'JOIN controlplane.cp_video_jobs v ON v.workspace_id = cl.workspace_id AND v.job_id = cl.job_id '
            "JOIN controlplane.cp_render_packages p ON p.workspace_id = cl.workspace_id AND p.payload->>'production_snapshot_ref' = cl.snapshot_ref "
            'WHERE cl.workspace_id = %s AND v.batch_id = %s ORDER BY cl.job_id, p.created_at DESC', batch_id)
        return {r[0]: r[1] for r in rows}

    def plans(self, plan_ids):
        rows = self.query('SELECT p.production_plan_id, p.payload FROM controlplane.cp_production_plans p '
                          'WHERE p.workspace_id = %s AND p.production_plan_id = ANY(%s)', list(plan_ids))
        return {r[0]: r[1] for r in rows}

    def plan_layouts(self, batch_id):
        """layout_key của plan mới nhất mỗi job không FAILED_FINAL (cùng tập LAYOUT_USAGE_SQL của PRS-LAYOUT-QUOTA đếm)."""
        rows = self.query(
            "SELECT DISTINCT ON (j.job_id) j.job_id, p.payload->'layout_choice'->>'layout_key' FROM controlplane.cp_video_jobs j "
            "JOIN controlplane.cp_production_plans p ON p.workspace_id = j.workspace_id AND p.production_plan_id LIKE 'plan:' || j.job_id || ':r%%' "
            "WHERE j.workspace_id = %s AND j.batch_id = %s AND j.status <> 'FAILED_FINAL' ORDER BY j.job_id, p.created_at DESC", batch_id)
        return [r[1] for r in rows]

    def hooks(self, hook_ids):
        """{hook_id: {'kind', 'source', 'query'}} theo revision hiện hành (cùng revision render đọc)."""
        rows = self.query(
            'SELECT h.hook_id, h.kind, r.payload FROM controlplane.cp_hooks h JOIN controlplane.cp_hook_revisions r '
            'ON r.workspace_id = h.workspace_id AND r.hook_id = h.hook_id AND r.revision = h.current_revision '
            'WHERE h.workspace_id = %s AND h.hook_id = ANY(%s)', list(hook_ids))
        out = {}
        for hook_id, kind, payload in rows:
            metadata = (payload or {}).get('technical_metadata') or []
            query = dict(tuple(p) for p in metadata if isinstance(p, (list, tuple)) and len(p) == 2).get('hook_query')
            out[hook_id] = {'kind': kind, 'source': hook_source(metadata), 'query': query}
        return out


@dataclass
class BatchQuality:
    batch_id: str = ''
    target: int = 0
    rows: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def analyze_batch(db, prefix):
    """Đọc lô theo tiền tố Batch ID (đúng một lô) và trả BatchQuality; chỉ đọc."""
    found = db.resolve_batch(prefix)
    if len(found) != 1:
        raise ValueError('batches=' + str(len(found)))
    batch_id, target, created = found[0]
    packages = db.render_packages(batch_id)
    plans = db.plans(sorted({p.get('production_plan_ref') for p in packages.values() if isinstance(p.get('production_plan_ref'), str)}))
    hook_ids = sorted({p.get('hook_placement', {}).get(k) for p in packages.values() for k in ('visual_hook_ref', 'audio_hook_ref')
                       if isinstance(p.get('hook_placement'), dict) and isinstance(p['hook_placement'].get(k), str)})
    hooks = db.hooks(hook_ids)
    rows = [video_row(job, package, plans.get(package.get('production_plan_ref')), hooks) for job, package in sorted(packages.items())]
    failed = [j for j, s in db.batch_jobs(batch_id) if s == 'FAILED_FINAL']
    summary = summarize(rows, target=target, plan_layouts=db.plan_layouts(batch_id),
                        failure_causes=m.failure_causes([(j, db.failed_stage(j)) for j in failed]),
                        leads=db.job_lead_seconds(batch_id), span_s=target_span_s(created, db.completed_epochs(batch_id), target),
                        stage_rows=db.stage_durations(batch_id))
    return BatchQuality(batch_id, target, rows, summary)
