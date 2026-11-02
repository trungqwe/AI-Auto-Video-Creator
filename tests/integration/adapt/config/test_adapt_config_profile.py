# ADAPT-CONFIG: kiểm hồ sơ production, nguồn RSS, hook seed và khóa trọng số (chỉ stdlib).
import json
import re
from pathlib import Path

PROD = Path(__file__).resolve().parents[4] / 'tools' / 'launcher' / 'prod'
FILES = ('profile.json', 'sources.json', 'hooks.json', 'model-weights.lock.json')
BASES = {'DECIDED', 'MEASURED', 'CONSERVATIVE_DEFAULT'}
BAD_KEY_PARTS = ('secret', 'token', 'password', 'api_key', 'apikey')
GROUPS = {'meta', 'collection', 'ai', 'budget', 'credential', 'voice', 'aligner', 'audio', 'image_safety', 'render', 'qc', 'gpu', 'drive', 'working_set', 'retention', 'time', 'workflow', 'batch', 'resume'}
PRESETS = {'bold-yellow', 'clean-white', 'neon-cyan', 'news-red', 'soft-shadow'}
MEDIA_SUFFIXES = {'.mp4', '.wav', '.png', '.jpg', '.jpeg', '.webp', '.mp3', '.onnx', '.bin', '.safetensors'}


def load(name):
    return json.loads((PROD / name).read_text(encoding='utf-8'))


def all_keys(node):
    if isinstance(node, dict):
        for key, child in node.items():
            yield key
            yield from all_keys(child)
    elif isinstance(node, list):
        for child in node:
            yield from all_keys(child)


def contains_null(node):
    if node is None:
        return True
    if isinstance(node, dict):
        return any(contains_null(child) for child in node.values())
    if isinstance(node, list):
        return any(contains_null(child) for child in node)
    return False


def params(node, prefix=''):
    for key, child in node.items():
        assert isinstance(child, dict), prefix + key
        if 'value' in child:
            yield prefix + key, child
        else:
            yield from params(child, prefix + key + '.')


def profile_params():
    return dict(params(load('profile.json')))


def test_files_utf8_without_bom_and_without_sensitive_keys():
    for name in FILES:
        raw = (PROD / name).read_bytes()
        assert raw[:3] != bytes([239, 187, 191]), name
        text = raw.decode('utf-8')
        assert chr(0xFFFD) not in text and '??' not in text, name
        bad = [k for k in all_keys(json.loads(text)) if any(p in k.lower() for p in BAD_KEY_PARTS)]
        assert bad == [], (name, bad)


def test_profile_groups_and_param_shape():
    assert set(load('profile.json')) == GROUPS
    for name, param in profile_params().items():
        assert set(param) == {'value', 'reason', 'basis'}, name
        assert isinstance(param['reason'], str) and param['reason'].strip(), name
        assert param['basis'] in BASES, name


def test_profile_has_no_null_and_keeps_vietnamese_diacritics():
    assert not contains_null(load('profile.json'))
    text = ' '.join(p['reason'] for p in profile_params().values())
    assert re.search('[ăâđêôơưạảấầẩậắặẹẻếềểệịọcỏốồổộớờởợụủứừửự]', text)


REQUIRED = '''
meta.profile_name meta.revision collection.source_kind collection.tiers collection.fetch_policy.feed collection.fetch_policy.article collection.fetch_policy.image collection.retry_fetch collection.concurrency collection.collection_interval_minutes collection.freshness_window_hours collection.extraction_min_text_chars collection.user_agent
ai.route_endpoint ai.route_model_refs ai.request_timeout_seconds ai.retry ai.reservation_ttl_seconds ai.quota_wait_poll_seconds ai.quota_wait_max budget.monthly_limit budget.currency budget.hard_stop budget.warn_at_ratio budget.window_timezone credential.max_ttl_seconds
voice.engine voice.duration_range_ms voice.speech_rate_wpm voice.tts_timeout_seconds voice.stage_retry voice.speed_fit aligner.engine aligner.word_timing_tolerance_ms aligner.max_unmatched_word_ratio audio.loudness audio.bed_gain_db image_safety.categories image_safety.thresholds image_safety.boxblur image_safety.vision
render.profile render.nvenc render.fallback render.timeout_seconds render.presets render.ass_style render.layout render.sections render.output_stream qc.duration_range_ms qc.required_language qc.karaoke_tolerance_ms qc.hook_similarity_min qc.hook_audio_min_dbfs qc.visual_continuity_min qc.max_file_bytes qc.quality_thresholds gpu.slots
drive.account drive.folders drive.chunk_bytes drive.chunk_timeout_seconds drive.retry drive.session_ttl_seconds drive.quota_reserve_ratio drive.verify working_set.max_video_sets working_set.max_bytes working_set.disk_reserve_bytes retention.original retention.reusable retention.output retention.temporary retention.log_days retention.audit_days
time.timezone workflow.start_to_close_seconds workflow.heartbeat_seconds workflow.retry workflow.schedule batch.videos_per_news_per_round batch.target batch.max_concurrent_videos resume.ready_within_seconds
'''.split()


def test_profile_has_exactly_the_required_parameters():
    assert len(REQUIRED) == 85
    assert sorted(profile_params()) == sorted(REQUIRED)


def test_batch_max_concurrent_videos_is_decided():
    p = profile_params()['batch.max_concurrent_videos']
    assert p['value'] == {'default': 6, 'max': 10}
    assert p['basis'] == 'DECIDED'
    assert 'RG-10' in p['reason']


def test_voice_speed_fit_is_decided_and_in_profile():
    p = profile_params()['voice.speed_fit']
    assert p['value'] == {'min_scale': 0.85, 'max_scale': 1.15, 'duration_slope': 0.56}
    assert p['basis'] == 'DECIDED'
    assert '0,85-1,15' in p['reason']


def test_budget_timezone_and_basis():
    p = profile_params()
    assert p['budget.monthly_limit']['value'] == 50
    assert p['budget.currency']['value'] == 'USD'
    assert p['budget.hard_stop']['value'] is True
    assert p['budget.monthly_limit']['basis'] == 'DECIDED'
    assert p['budget.window_timezone']['value'] == 'Asia/Ho_Chi_Minh'
    assert p['time.timezone']['value']['name'] == 'Asia/Ho_Chi_Minh'
    assert p['time.timezone']['value']['storage'] == 'UTC'


def test_exactly_five_presets():
    value = profile_params()['render.presets']['value']
    assert set(value['variants']) == PRESETS
    common = value['common']
    assert (common['font'], common['font_size'], common['outline_width'], common['margin_v']) == ('Arial', 72, 4, 360)
    assert len({json.dumps(v, sort_keys=True) for v in value['variants'].values()}) == 5


def test_ai_routes_and_duration_anchors():
    p = profile_params()
    routes = p['ai.route_model_refs']['value']
    assert set(routes) == {'analysis', 'angle', 'script', 'selection', 'metadata', 'image_safety', 'illustration'}
    assert set(routes.values()) == {'ag/gemini-3.8-flash-high'}
    for key in ('voice.duration_range_ms', 'qc.duration_range_ms'):
        assert (p[key]['value']['min'], p[key]['value']['max']) == (61000, 70000)
    assert p['qc.karaoke_tolerance_ms']['value'] == p['aligner.word_timing_tolerance_ms']['value'] == 200
    assert p['qc.required_language']['value'] == 'en'


def test_illustration_route_shares_the_image_safety_model_and_cites_the_user_decision():
    p = profile_params()['ai.route_model_refs']
    routes = p['value']
    assert list(routes)[-1] == 'illustration'
    assert routes['illustration'] == routes['image_safety'] == 'ag/gemini-3.8-flash-high'
    assert p['basis'] == 'DECIDED'
    for needle in ('illustration', 'CLOSURE_NOTE CP7/RG-13', 'D4', '02/11/2026'):
        assert needle in p['reason'], needle


def test_profile_revision_moves_to_7_for_the_illustration_role():
    p = profile_params()['meta.revision']
    assert type(p['value']) is int and p['value'] >= 7
    assert p['basis'] == 'DECIDED'
    if p['value'] == 7:
        for needle in ('illustration', 'CLOSURE_NOTE CP7/RG-13', 'D4', '02/11/2026'):
            assert needle in p['reason'], needle


EXPECTED_SOURCES = {
    'bbc-world': ('https://feeds.bbci.co.uk/news/world/rss.xml', 'tier_1'),
    'bbc-tech': ('https://feeds.bbci.co.uk/news/technology/rss.xml', 'tier_1'),
    'npr-news': ('https://feeds.npr.org/1001/rss.xml', 'tier_1'),
    'guardian-world': ('https://www.theguardian.com/world/rss', 'tier_1'),
    'aljazeera-all': ('https://www.aljazeera.com/xml/rss/all.xml', 'tier_1'),
    'nasa-news': ('https://www.nasa.gov/feed/', 'tier_1'),
    'ars-technica': ('https://feeds.arstechnica.com/arstechnica/index', 'tier_2'),
}


def sha_ok(item):
    if item['sha256'] is None:
        return item['sha256_status'] == 'PENDING_GENERATION'
    return bool(re.fullmatch(r'[0-9a-f]{64}', item['sha256'])) and item['sha256_status'] == 'GENERATED'


def test_sources_seven_https_feeds():
    sources = load('sources.json')['sources']
    assert len(sources) == 7
    assert {s['code']: (s['url'], s['tier']) for s in sources} == EXPECTED_SOURCES
    for s in sources:
        assert s['url'].startswith('https://'), s['code']
        assert s['enabled'] is True and s['source_kind'] == 'rss_feed', s['code']


def test_hooks_structure_and_recipes():
    hooks = load('hooks.json')
    for key, prefix, count in (('visual_hooks', 'vh', 5), ('audio_hooks', 'ah', 5), ('background_images', 'bg', 12)):
        items = hooks[key]
        assert [i['id'] for i in items] == ['%s-%02d' % (prefix, n) for n in range(1, count + 1)]
        for item in items:
            assert item['file_name'].startswith(item['id']), item['id']
            assert item['recipe']['template'] in hooks['recipe_templates'], item['id']
            assert sha_ok(item), item['id']
    assert all((i['width'], i['height'], i['fps'], i['duration_ms']) == (1080, 1920, 30, 3000) for i in hooks['visual_hooks'])
    assert all((i['sample_rate_hz'], i['channels'], i['duration_ms']) == (24000, 1, 1500) for i in hooks['audio_hooks'])
    assert all((i['width'], i['height']) == (1080, 1920) for i in hooks['background_images'])
    assert hooks['storage']['in_git'] is False
    assert hooks['rights']['seed_rights_status'] == 'SELF_GENERATED'
    assert hooks['rights']['article_image_rights_status'] == 'UNVERIFIED'
    assert hooks['rights']['article_images_in_sample_video'] is True
    assert 'pending_user_checkpoint' not in hooks['rights']


def test_weights_lock_structure():
    lock = load('model-weights.lock.json')
    assert lock['storage']['in_git'] is False
    files = lock['files']
    names = [f['name'] for f in files]
    assert len(set(names)) == len(names)
    assert {'kokoro-v1.0.onnx', 'voices-v1.0.bin'} <= set(names)
    assert sum(1 for f in files if f['group'] == 'faster-whisper-small.en') >= 4
    for f in files:
        assert f['url'].startswith('https://'), f['name']
        if f['sha256'] is None:
            assert f['status'] == 'BLOCKED', f['name']
        else:
            assert re.fullmatch(r'[0-9a-f]{64}', f['sha256']) and f['status'] == 'PINNED', f['name']
        if '<commit>' in f['url']:
            assert f['commit'] is None and f['status'] == 'BLOCKED', f['name']


def test_no_media_or_large_files_under_prod_tree():
    for path in PROD.rglob('*'):
        if path.is_file():
            assert path.suffix.lower() not in MEDIA_SUFFIXES, path
            assert path.stat().st_size <= 1024 * 1024, path
