"""CP7-REMEASURE: chỉ số hình và tiếng của lô 100 video đo lại trên dây chuyền mới (trước mẫu CP7-14).

Các test_unit_* là test thuần trên dữ liệu giả, không chạm CSDL, mạng hay AI. test_cq_quality_of_batch chỉ chạy khi đặt
CP7_REMEASURE_BATCH_PREFIX (8 ký tự đầu Batch ID của lô đã chạy bằng test_cp7_overnight.py với CP7_RG10_LIVE=1); nó chỉ đọc CSDL.
coveredIds: RG-10, RG-13
"""
from __future__ import annotations

import os
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
import cp7_remeasure_quality as q  # noqa: E402

MODULE_FILE = REPO / 'tools' / 'real' / 'cp7_remeasure_quality.py'


def _visual(media, origin, start, end, ref=None):
    item = {'media_asset_id': media, 'start_ms': start, 'end_ms': end, 'artifact_version_ref': ref or ('AV-' + media)}
    if origin is not None:
        item['origin'] = origin
    return item


def _package(scenes, *, fallbacks=(), visual_hook='vh-1', audio_hook='ah-1', beds=('music-' + 'a' * 64,), plan='plan:b1:job:1:r1'):
    segments = [{'scene_id': f's{i}', 'start_ms': s, 'end_ms': e, 'visuals': list(v)} for i, (s, e, v) in enumerate(scenes)]
    return {'production_plan_ref': plan, 'timeline': {'segments': segments}, 'allowed_fallbacks': list(fallbacks),
            'hook_placement': {'visual_hook_ref': visual_hook, 'audio_hook_ref': audio_hook, 'thumbnail_ref': 'th'},
            'mix_plan': {'beds': [{'rendition_ref': ref} for ref in beds]}}


HOOKS = {'vh-1': {'kind': 'visual_hook', 'source': 'pixabay', 'query': 'city'},
         'ah-1': {'kind': 'audio_hook', 'source': 'freesound', 'query': 'whoosh'},
         'ah-2': {'kind': 'audio_hook', 'source': 'freesound', 'query': 'impact'},
         'vh-old': {'kind': 'visual_hook', 'source': 'placeholder', 'query': None}}


def _rule(media, reason):
    return {'rule_id': 'image-safety:' + media, 'kind': 'replace_asset', 'replaced_media_asset_id': media, 'reason': reason}


def test_unit_hook_source():
    assert q.hook_source([['recipe_template', 'sweep'], ['hook_source', 'pixabay']]) == 'placeholder'
    assert q.hook_source([['hook_source', 'pixabay'], ['hook_license', 'Pixabay Content License']]) == 'pixabay'
    assert q.hook_source([['media_sha256', 'x']]) == 'other'
    assert q.hook_source(None) == 'other'


def test_unit_final_visuals_follow_image_safety_replacements():
    package = _package([(0, 4000, [_visual('m1', 'article', 0, 4000)]), (4000, 8000, [_visual('m2', 'ai_generated', 4000, 8000)]),
                        (8000, 9000, [_visual('m3', None, 8000, 9000)])], fallbacks=[_rule('m1', 'seed_fallback'), _rule('m2', 'image_fallback')])
    assert [(v['media_asset_id'], v['origin']) for v in q.final_visuals(package)] == [('m1', 'seed'), ('m2', 'replaced'), ('m3', 'unknown')]
    assert q.final_visuals({'timeline': None}) == []


def test_unit_video_row_counts_images_hooks_music_and_layout():
    package = _package([(0, 5000, [_visual('m1', 'article', 0, 5000)]),
                        (5000, 10000, [_visual('m2', 'ai_generated', 5000, 10000, 'AV-X')]),
                        (10000, 15000, [_visual('m3', 'ai_generated', 10000, 15000, 'av-x')]),
                        (15000, 20000, [_visual('m4', 'ai_generated', 15000, 20000)]),
                        (20000, 21000, [_visual('m5', 'seed', 20000, 21000)])], audio_hook='ah-2')
    plan = {'layout_choice': {'layout_key': 'MOSAIC_GRID', 'preset_key': 'p', 'fallback_reason': None}}
    row = q.video_row('b1:job:1', package, plan, HOOKS)
    assert row['layout'] == 'MOSAIC_GRID' and row['layout_fallback'] is None
    assert (row['ai_images'], row['article_images'], row['replaced_images']) == (2, 1, 0)
    assert row['background_only'] is False
    assert row['seed_share_pct'] == round(1000 * 100 / 21000, 1)
    assert (row['scenes'], row['duration_s']) == (5, 21.0)
    assert (row['visual_hook_source'], row['audio_hook_source'], row['audio_hook_query']) == ('pixabay', 'freesound', 'impact')
    assert row['music'] == ['music-' + 'a' * 64]
    missing = q.video_row('b1:job:2', _package([(0, 1000, [_visual('m1', 'article', 0, 1000)])], visual_hook='vh-gone'), None, HOOKS)
    assert missing['visual_hook_source'] == 'missing' and missing['layout'] == 'none'


def test_unit_background_only_after_seed_fallback_or_unknown_origin():
    seed_only = _package([(0, 3000, [_visual('m1', 'seed', 0, 3000)]), (3000, 6000, [_visual('m2', 'article', 3000, 6000)])],
                         fallbacks=[_rule('m2', 'seed_fallback')])
    row = q.video_row('j', seed_only, None, HOOKS)
    assert row['background_only'] is True and row['seed_share_pct'] == 100.0
    unknown = q.video_row('j', _package([(0, 3000, [_visual('m1', None, 0, 3000)])]), None, HOOKS)
    assert unknown['background_only'] is True
    replaced = q.video_row('j', _package([(0, 3000, [_visual('m1', 'article', 0, 3000)])], fallbacks=[_rule('m1', 'image_fallback')]), None, HOOKS)
    assert replaced['background_only'] is False and replaced['replaced_images'] == 1


def test_unit_union_ms_counts_overlap_once():
    assert q.union_ms([(0, 1000), (500, 1500), (3000, 4000)]) == 2500
    assert q.union_ms([(0, 5000), (1000, 2000), (2000, 3000)]) == 5000
    assert q.union_ms([]) == 0


def test_unit_layout_counts_use_the_quota_cap():
    keys = ['HERO_STRIP'] * 40 + ['MOSAIC_GRID'] * 30 + ['DATA_CARD'] * 30
    out = q.layout_counts(keys, 100)
    assert out['limit'] == 40 and out['over'] == {} and out['distinct'] == 3
    over = q.layout_counts(keys + ['HERO_STRIP'], 100)
    assert over['over'] == {'HERO_STRIP': 41}
    assert q.layout_counts([None, 'SPLIT_STACK'], 2)['counts'] == {'SPLIT_STACK': 1, 'none': 1}
    assert q.layout_counts(['HERO_STRIP'], 0)['limit'] is None


def test_unit_target_span():
    assert q.target_span_s(1000.0, [1300.0, 1100.0, 1200.0], 2) == 200.0
    assert q.target_span_s(1000.0, [1100.0], 2) is None
    assert q.target_span_s(1000.0, [1100.0], 0) is None


def _rows():
    rows = []
    for i in range(10):
        ai = [_visual(f'a{i}', 'ai_generated', 5000, 10000, f'AI{i}')] if i % 2 == 0 else []
        package = _package([(0, 5000, [_visual(f'm{i}', 'article', 0, 5000)]), (5000, 10000, ai or [_visual(f'n{i}', 'article', 5000, 10000)])],
                           audio_hook='ah-1' if i < 5 else 'ah-2', beds=(f'music-{i % 3:064d}',))
        plan = {'layout_choice': {'layout_key': q.LAYOUT_KEYS[i % 5], 'preset_key': 'p', 'fallback_reason': 'cap_full' if i == 9 else None}}
        rows.append(q.video_row(f'b1:job:{i}', package, plan, HOOKS))
    return rows


def _summary(rows, plan_layouts=None):
    return q.summarize(rows, target=10, plan_layouts=plan_layouts if plan_layouts is not None else [r['layout'] for r in rows],
                       failure_causes=[{'stage': 'media_select', 'code': 'illustration_generation_failed', 'activity': 'GenerateIllustrations', 'n': 2}],
                       leads=[300.0, 400.0, 500.0], span_s=5000.0,
                       stage_rows=[('media_select', 'SUCCEEDED', 1, 80.0), ('render', 'SUCCEEDED', 1, 20.0)])


def test_unit_summarize_and_quality_lines():
    s = _summary(_rows())
    assert s['videos'] == 10 and s['videos_with_ai'] == 5
    assert s['ai_images'] == {'n': 10, 'min': 0, 'p50': 0, 'max': 1, 'total': 5}
    assert s['background_only'] == [] and s['hook_not_real'] == 0
    assert (s['distinct_visual_hooks'], s['distinct_audio_hooks'], s['distinct_audio_hook_queries'], s['distinct_music']) == (1, 2, 2, 3)
    assert s['layout_batch']['limit'] == 4 and s['layout_batch']['over'] == {} and s['layout_fallbacks'] == {'cap_full': 1}
    assert (s['lead_p50_s'], s['lead_p95_s'], s['span_s']) == (400.0, 500.0, 5000.0)
    lines = q.quality_lines(s, 'abcdef12')
    assert lines[:3] == ['CQ.no_background_only: PASS', 'CQ.real_hooks: PASS', 'CQ.layout_cap_40: PASS']
    assert all(line.isascii() for line in lines)
    text = '\n'.join(lines)
    assert '- cq: batch=abcdef12 videos=10' in text
    assert '- cq: span_s=5000.0 prev_t_target_s=6849 delta_s=-1849.0' in text
    assert '- cq: stage_p50 media_select now=80.0 prev=50.3 delta=+29.7' in text
    assert '- cq: stage_p50 tts now=None prev=15.9 delta=n/a' in text
    assert '- cq: failed_final stage=media_select code=illustration_generation_failed activity=GenerateIllustrations n=2' in text


def test_unit_quality_lines_fail_and_over():
    rows = _rows()
    rows[3] = q.video_row('b1:job:3', _package([(0, 3000, [_visual('s', 'seed', 0, 3000)])], visual_hook='vh-old'), None, HOOKS)
    s = _summary(rows, plan_layouts=['HERO_STRIP'] * 5 + ['DATA_CARD'] * 5)
    lines = q.quality_lines(s, 'abcdef12')
    assert lines[:3] == ['CQ.no_background_only: FAIL', 'CQ.real_hooks: FAIL', 'CQ.layout_cap_40: OVER']
    assert s['background_only'] == ['b1:job:3'] and s['hook_not_real'] == 1
    empty = q.quality_lines(_summary([], plan_layouts=[]), 'abcdef12')
    assert empty[:2] == ['CQ.no_background_only: FAIL', 'CQ.real_hooks: FAIL']
    with pytest.raises(ValueError):
        q.cq_line('x', 'NOT_OBSERVED')


class _Rec(q.QualityDb):
    def __init__(self, rows):
        self.workspace_id = 'w'
        self.rows = rows
        self.calls = []

    def query(self, sql, *params):
        self.calls.append((sql, params))
        return self.rows


_DB_CASES = [
    ('resolve_batch', ('abcdef12',), [('abcdef12-0000', 100, 1000.5)], [('abcdef12-0000', 100, 1000.5)]),
    ('completed_epochs', ('b1',), [(1100.0,), (1200,)], [1100.0, 1200.0]),
    ('render_packages', ('b1',), [('b1:job:1', {'timeline': {}})], {'b1:job:1': {'timeline': {}}}),
    ('plans', (['plan:b1:job:1:r1'],), [('plan:b1:job:1:r1', {'layout_choice': {}})], {'plan:b1:job:1:r1': {'layout_choice': {}}}),
    ('plan_layouts', ('b1',), [('b1:job:1', 'HERO_STRIP'), ('b1:job:2', None)], ['HERO_STRIP', None]),
    ('hooks', (['ah-1'],), [('ah-1', 'audio_hook', {'technical_metadata': [['hook_source', 'freesound'], ['hook_query', 'whoosh']]})],
     {'ah-1': {'kind': 'audio_hook', 'source': 'freesound', 'query': 'whoosh'}}),
]


@pytest.mark.parametrize('name,args,rows,expected', _DB_CASES)
def test_unit_quality_db_methods_are_read_only(name, args, rows, expected):
    db = _Rec(rows)
    assert getattr(db, name)(*args) == expected
    sql, params = db.calls[0]
    assert len(db.calls) == 1
    assert sql.lstrip().upper().startswith('SELECT')
    assert 'workspace_id = %s' in sql
    assert params == args or params == (list(args[0]),)
    assert not re.search(r'(?i)\b(insert|update|delete|truncate|drop|alter)\b', sql)


def test_unit_plan_layouts_escapes_like_percent():
    db = _Rec([])
    db.plan_layouts('b1')
    sql = db.calls[0][0]
    assert ":r%%'" in sql and "FAILED_FINAL" in sql and 'DISTINCT ON (j.job_id)' in sql


class _FakeDb:
    def __init__(self, batches):
        self.batches = batches

    def resolve_batch(self, prefix):
        return self.batches

    def render_packages(self, batch_id):
        return {'b1:job:1': _package([(0, 4000, [_visual('m1', 'ai_generated', 0, 4000)])])}

    def plans(self, plan_ids):
        assert plan_ids == ['plan:b1:job:1:r1']
        return {'plan:b1:job:1:r1': {'layout_choice': {'layout_key': 'DATA_CARD', 'preset_key': 'p'}}}

    def hooks(self, hook_ids):
        assert hook_ids == ['ah-1', 'vh-1']
        return HOOKS

    def batch_jobs(self, batch_id):
        return [('b1:job:1', 'COMPLETED'), ('b1:job:2', 'FAILED_FINAL')]

    def failed_stage(self, job_id):
        return ('render', 'FAILED_FINAL', 'no_illustration_available', 'resolve_render_package', '{}')

    def plan_layouts(self, batch_id):
        return ['DATA_CARD']

    def job_lead_seconds(self, batch_id):
        return [300.0]

    def completed_epochs(self, batch_id):
        return [1300.0]

    def stage_durations(self, batch_id):
        return [('render', 'SUCCEEDED', 1, 12.0)]


def test_unit_analyze_batch_reads_one_batch():
    out = q.analyze_batch(_FakeDb([('b1', 1, 1000.0)]), 'b1')
    assert out.batch_id == 'b1' and out.target == 1 and len(out.rows) == 1
    assert out.summary['ai_images']['total'] == 1 and out.summary['span_s'] == 300.0
    assert out.summary['failure_causes'] == [{'stage': 'render', 'code': 'no_illustration_available', 'activity': 'resolve_render_package', 'n': 1}]
    for batches in ([], [('b1', 1, 0.0), ('b2', 1, 0.0)]):
        with pytest.raises(ValueError):
            q.analyze_batch(_FakeDb(batches), 'b')


def test_unit_module_has_no_writes_or_network():
    text = MODULE_FILE.read_text(encoding='utf-8')
    assert not re.search(r'(?i)\b(insert\s+into|update\s+controlplane|delete\s+from)\b', text)
    for word in ('urllib', 'http.client', 'requests', 'socket', 'subprocess', 'stop_until_exited', 'start_capturing'):
        assert word not in text, word


def test_cq_quality_of_batch(emit):
    """Sau lô thật: đọc chỉ số hình và tiếng của lô (chỉ đọc) và in dòng bằng chứng cho báo cáo."""
    prefix = os.environ.get('CP7_REMEASURE_BATCH_PREFIX', '')
    if not re.fullmatch(r'[0-9a-f]{8}', prefix):
        pytest.skip('CP7_REMEASURE_BATCH_PREFIX chưa đặt (8 ký tự hex đầu Batch ID)')
    result = q.analyze_batch(q.QualityDb(d.load_launcher()), prefix)
    for line in q.quality_lines(result.summary, prefix):
        emit(line)
    assert result.summary['videos'] >= 1
