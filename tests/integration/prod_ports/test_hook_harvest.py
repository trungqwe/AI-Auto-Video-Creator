"""HOOK-HARVEST: thu video hook Pixabay, âm hook Freesound và catalog nhạc qua transport giả (không mạng, không PostgreSQL).

Kho hook trong bộ nhớ (HookHistory của C); ffmpeg giả cho phần điều phối, ffmpeg ghim thật (C:/ffmpeg/bin) cho bộ cắt trên nguồn tự sinh.
Khoá giả không bao giờ xuất hiện trong lời in, báo cáo, repr hay ngoại lệ.

coveredIds: FR-HOOK-004, FR-HOOK-005, FR-AUD-007
"""
from __future__ import annotations

import contextlib
import datetime
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import pytest

from catalog.application.hooks import HookHistory, import_hook
from catalog.domain.hooks import HookKind
from controlplane.infrastructure.production_ports.stock_harvest import (
    MAX_CLIP_BYTES,
    REQUEST_INTERVAL_SECONDS,
    FfmpegHookMedia,
    HarvestBudget,
    MediaProcessingError,
    MeteredTransport,
    ProcessedMedia,
    harvest_hooks,
    harvest_music,
    probe_providers,
)
from controlplane.infrastructure.production_ports.stock_media import (
    FREESOUND_SEARCH_API,
    LICENSE_CC_BY_4,
    PIXABAY_VIDEO_API,
    FreesoundSearch,
    PixabayVideoSearch,
    StockItem,
)
from creative.adapters.hook_candidates import PostgresHookCandidates
from voice.adapters.audio_bed_source import MusicSource, load_music_catalog, save_music_catalog

ROOT = pathlib.Path(__file__).resolve().parents[3]
CLI = ROOT / 'tools' / 'launcher' / 'prod' / 'harvest_media.py'
FFMPEG = pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe')
FFPROBE = pathlib.Path('C:/ffmpeg/bin/ffprobe.exe')
KEY = 'Kx9canaryHarvestKey0123456789'
CC0 = 'http://creativecommons.org/publicdomain/zero/1.0/'
CC_BY = 'https://creativecommons.org/licenses/by/4.0/'
CC_BY_NC = 'http://creativecommons.org/licenses/by-nc/4.0/'


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    final_url: str


class FakeTransport:
    """Routes by scheme, host and path; JSON routes take the parsed query, CDN routes return fixed bytes."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def fetch(self, url, *, max_bytes, timeout_seconds):
        self.calls.append(url)
        parts = urlsplit(url)
        handler = self.routes.get(parts.scheme + '://' + parts.netloc + parts.path)
        if handler is None:
            raise OSError('no route')
        status, body = handler(parse_qs(parts.query))
        return Response(status, body, url)

    def downloads(self):
        return [url for url in self.calls if '/api' not in url]


class Keys:
    @contextlib.contextmanager
    def acquire(self, provider):
        yield KEY


class FakeMedia:
    def __init__(self, fail_on=()):
        self.fail_on = set(fail_on)
        self.seen = []

    def cut_visual(self, data):
        self.seen.append(data)
        if data in self.fail_on:
            raise MediaProcessingError('harvest_media_failed')
        return ProcessedMedia(b'mp4:' + data, 'mp4', {'width': '1280', 'height': '720', 'fps': '30', 'duration_ms': '4000'})

    def normalize_audio(self, data):
        self.seen.append(data)
        return ProcessedMedia(b'wav:' + data, 'wav', {'sample_rate_hz': '48000', 'channels': '2', 'duration_ms': '1500'})


class MemoryHookLibrary:
    def __init__(self):
        self.history = HookHistory(clock=lambda: datetime.datetime(2026, 11, 3, tzinfo=datetime.timezone.utc))
        self.files = {}

    def has_hook(self, hook_id):
        try:
            self.history.latest(hook_id)
        except KeyError:
            return False
        return True

    def add_hook(self, hook):
        self.files[f'media/{hook.sha256}.{hook.extension}'] = hook.data
        import_hook(self.history, hook_id=hook.hook_id, kind=HookKind(hook.kind), artifact_version_ref=f'stock:{hook.hook_id}:sha256:{hook.sha256}',
                    tags=hook.tags, description=hook.description, technical_metadata=hook.technical_metadata + (('media_asset_id', 'ma-' + hook.hook_id),))
        return 'ma-' + hook.hook_id


def pixabay_hit(hit_id, duration=8, host='cdn.pixabay.com', user='maker'):
    return {'id': hit_id, 'pageURL': f'https://pixabay.com/videos/x-{hit_id}/', 'tags': 'police, night', 'duration': duration, 'user': user,
            'videos': {'medium': {'url': f'https://{host}/video/{hit_id}_medium.mp4', 'width': 1280, 'height': 720}}}


def freesound_result(sound_id, license_url=CC0, duration=1.5, username='rec'):
    return {'id': sound_id, 'name': f'Whoosh {sound_id}', 'tags': ['whoosh', 'air'], 'description': 'fast air swish', 'license': license_url,
            'username': username, 'duration': duration, 'url': f'https://freesound.org/people/rec/sounds/{sound_id}/',
            'previews': {'preview-hq-mp3': f'https://cdn.freesound.org/previews/1/{sound_id}_hq.mp3'}}


def json_route(payload, status=200):
    return lambda query: (status, json.dumps(payload).encode('utf-8'))


def cdn(query):
    return 200, b'bytes'


def routes(hits=(), sounds=(), pixabay_status=200, cdn_status=200):
    table = {
        PIXABAY_VIDEO_API: json_route({'hits': list(hits)}, pixabay_status),
        FREESOUND_SEARCH_API: json_route({'results': list(sounds)}),
    }
    for hit in hits:
        url = hit['videos']['medium']['url']
        table[url] = (lambda body: lambda query: (cdn_status, body))(f'video-{hit["id"]}'.encode())
    for sound in sounds:
        table[sound['previews']['preview-hq-mp3']] = (lambda body: lambda query: (cdn_status, body))(f'sound-{sound["id"]}'.encode())
    return table


def clients(transport):
    return PixabayVideoSearch(transport=transport, keys=Keys()), FreesoundSearch(transport=transport, keys=Keys())


def run_hooks(transport, store, media=None, **kwargs):
    pixabay, freesound = clients(transport)
    kwargs.setdefault('visual_queries', ('police lights night',))
    kwargs.setdefault('audio_queries', ('whoosh',))
    return harvest_hooks(pixabay=pixabay, freesound=freesound, transport=transport, media=media or FakeMedia(), store=store, **kwargs)


def metered(table, budget=None, slept=None):
    inner = FakeTransport(table)
    return inner, MeteredTransport(inner, budget or HarvestBudget(), sleep=(slept.append if slept is not None else (lambda seconds: None)))


def text_of(*values):
    return ' '.join(repr(value) for value in values)


def test_visual_and_audio_items_are_cut_and_imported_with_license_and_index():
    inner, transport = metered(routes(hits=[pixabay_hit(11), pixabay_hit(12, user='')], sounds=[freesound_result(21), freesound_result(22, CC_BY), freesound_result(23, CC_BY_NC)]))
    store = MemoryHookLibrary()
    placeholder = (('duration_ms', '3000'), ('media_sha256', 'a' * 64), ('recipe_template', 'lavfi_gradient_pulse_v1'), ('seed_rights_status', 'SELF_GENERATED'))
    import_hook(store.history, hook_id='vh-01', kind=HookKind.VISUAL_HOOK, artifact_version_ref='seed:vh-01', tags=('seed',), technical_metadata=placeholder)
    report = run_hooks(transport, store, per_query=4)
    assert (report.imported, report.existing, report.stopped) == (4, 0, [])
    assert sorted(store.files) == sorted(f'media/{hashlib.sha256(prefix + body).hexdigest()}.{ext}' for prefix, body, ext in (
        (b'mp4:', b'video-11', 'mp4'), (b'mp4:', b'video-12', 'mp4'), (b'wav:', b'sound-21', 'wav'), (b'wav:', b'sound-22', 'wav')))
    hook = store.history.latest('pxb-11')
    meta = dict(hook.technical_metadata)
    assert hook.kind is HookKind.VISUAL_HOOK and 'recipe_template' not in meta
    assert meta['media_sha256'] == hashlib.sha256(b'mp4:video-11').hexdigest() and meta['hook_source_sha256'] == hashlib.sha256(b'video-11').hexdigest()
    assert (meta['hook_source'], meta['hook_license'], meta['hook_page_url'], meta['duration_ms'], meta['fps']) == ('pixabay', 'Pixabay Content License', 'https://pixabay.com/videos/x-11/', '4000', '30')
    assert {'police', 'night', 'lights'} <= set(hook.tags) and hook.description.startswith('police lights night: ')
    sound = dict(store.history.latest('fs-22').technical_metadata)
    assert sound['hook_license'] == LICENSE_CC_BY_4 and sound['hook_author'] == 'rec' and 'rec' in sound['hook_attribution'] and sound['sample_rate_hz'] == '48000'
    assert 'hook_author' not in dict(store.history.latest('pxb-12').technical_metadata)
    candidates = PostgresHookCandidates(lambda workspace_id: contextlib.nullcontext(store.history), safety_policy_revision='safe-r1', exclude_placeholders=True)
    visual = candidates.visual_hook_candidates(workspace_id='ws', snapshot_ref='snap-1')
    audio = candidates.audio_hook_candidates(workspace_id='ws', snapshot_ref='snap-1')
    assert sorted(item.hook_id for item in visual) == ['pxb-11', 'pxb-12'] and sorted(item.hook_id for item in audio) == ['fs-21', 'fs-22']
    for item in visual + audio:
        assert item.safety_rights_status['rights_cleared'] is True and item.provenance['index']['license'] and item.provenance['placeholder'] is False
    assert KEY not in text_of(report, report.lines(HarvestBudget()), transport, store.history.list_heads())


def test_running_again_imports_nothing_twice_and_downloads_nothing():
    table = routes(hits=[pixabay_hit(11)], sounds=[freesound_result(21)])
    inner, transport = metered(table)
    store = MemoryHookLibrary()
    run_hooks(transport, store)
    first = len(inner.downloads())
    again = run_hooks(transport, store)
    assert (again.imported, again.existing) == (0, 2) and len(inner.downloads()) == first == 2
    assert [head.revision.revision for head in store.history.list_heads()] == [1, 1]


def test_refused_license_and_foreign_host_are_skipped_before_download():
    good = dict(provider='freesound', provider_id='31', media_kind='audio', download_url='https://cdn.freesound.org/previews/1/31_hq.mp3',
                page_url='https://freesound.org/people/rec/sounds/31/', duration_ms=1500, width=0, height=0, tags=('whoosh',), description='swish',
                author='rec', license=LICENSE_CC_BY_4, attribution='"Whoosh" by rec', query='whoosh')
    items = [StockItem(**{**good, 'provider_id': '32', 'license': 'CC-BY-NC-4.0'}), StockItem(**{**good, 'provider_id': '33', 'author': ''}),
             StockItem(**{**good, 'provider_id': '34', 'download_url': 'https://evil.example/34.mp3'}), StockItem(**{**good, 'provider_id': '35', 'media_kind': 'clip'})]
    inner = FakeTransport({})

    class Search:
        def search(self, *args, **kwargs):
            return ()

        def search_sfx(self, *args, **kwargs):
            return tuple(items)

    store = MemoryHookLibrary()
    report = harvest_hooks(pixabay=Search(), freesound=Search(), transport=MeteredTransport(inner, HarvestBudget(), sleep=lambda s: None), media=FakeMedia(),
                           store=store, visual_queries=('news',), audio_queries=('whoosh',))
    assert report.skipped == {'license_not_cleared': 2, 'download_not_allowed': 1, 'kind_mismatch': 1} and report.imported == 0
    assert inner.calls == [] and store.files == {}


def test_failed_download_or_cut_leaves_no_hook_and_no_file():
    table = routes(hits=[pixabay_hit(11), pixabay_hit(12)], sounds=[])
    table['https://cdn.pixabay.com/video/12_medium.mp4'] = lambda query: (500, b'')
    inner, transport = metered(table)
    store = MemoryHookLibrary()
    report = run_hooks(transport, store, media=FakeMedia(fail_on={b'video-11'}))
    assert report.imported == 0 and report.skipped == {'harvest_media_failed': 1, 'download_stock_http_status': 1}
    assert store.files == {} and store.history.list_heads() == []


def test_dry_run_downloads_and_writes_nothing(tmp_path):
    inner, transport = metered(routes(hits=[pixabay_hit(11)], sounds=[freesound_result(21), freesound_result(22, duration=90)]))
    store = MemoryHookLibrary()
    report = run_hooks(transport, store, dry_run=True)
    assert (report.planned, report.imported) == (2, 0) and inner.downloads() == [] and store.history.list_heads() == []
    catalog = tmp_path / 'audio_library' / 'catalog' / 'music_sources.json'
    music = harvest_music(freesound=clients(transport)[1], transport=transport, catalog_path=catalog, dry_run=True, moods={'calm': ('calm ambient',)})
    assert music.planned == 1 and not catalog.exists() and inner.downloads() == []


def test_budget_caps_requests_downloads_and_bytes_and_spaces_requests():
    slept = []
    inner, transport = metered(routes(hits=[pixabay_hit(11), pixabay_hit(12)], sounds=[freesound_result(21)]), HarvestBudget(max_downloads=1), slept)
    report = run_hooks(transport, MemoryHookLibrary())
    assert report.imported == 1 and report.stopped == ['budget:downloads'] and len(inner.downloads()) == 1
    assert slept == [REQUEST_INTERVAL_SECONDS] * (len(inner.calls) - 1)
    inner, transport = metered(routes(hits=[pixabay_hit(11)]), HarvestBudget(max_requests=1))
    assert run_hooks(transport, MemoryHookLibrary()).stopped == ['budget:requests'] and len(inner.calls) == 1
    inner, transport = metered(routes(hits=[pixabay_hit(11)]), HarvestBudget(max_bytes=MAX_CLIP_BYTES - 1))
    assert run_hooks(transport, MemoryHookLibrary()).stopped == ['budget:bytes'] and inner.downloads() == []


def test_rate_limit_stops_only_that_library():
    inner, transport = metered(routes(hits=[pixabay_hit(11)], sounds=[freesound_result(21)], pixabay_status=429))
    store = MemoryHookLibrary()
    report = run_hooks(transport, store, visual_queries=('crowd street', 'storm lightning', 'fire smoke'))
    assert report.stopped == ['pixabay:stock_http_status:429'] and report.imported == 1
    assert len([url for url in inner.calls if url.startswith(PIXABAY_VIDEO_API)]) == 1 and store.has_hook('fs-21')


def test_music_catalog_gets_new_tracks_with_measured_sha_and_moods(tmp_path):
    catalog = tmp_path / 'audio_library' / 'catalog' / 'music_sources.json'
    old = MusicSource('fs-1', 'catalog', 'https://cdn.freesound.org/previews/1/41_hq.mp3', 'CC0-1.0', '"Old" (page) CC0-1.0', 'rec', 'c' * 64, ('calm',))
    save_music_catalog(catalog, [old])
    sounds = [freesound_result(41, duration=120), freesound_result(42, duration=120), freesound_result(43, CC_BY, duration=200), freesound_result(44, duration=90, username='')]
    inner, transport = metered(routes(sounds=sounds))
    report = harvest_music(freesound=clients(transport)[1], transport=transport, catalog_path=catalog, per_mood=4, moods={'calm': ('calm ambient',)})
    assert (report.imported, report.existing) == (2, 1) and report.skipped == {'author_missing': 1}
    saved = load_music_catalog(catalog)
    assert [source.source_id for source in saved] == ['fs-1', 'fs-42', 'fs-43']
    assert saved[1].sha256 == hashlib.sha256(b'sound-42').hexdigest() and saved[1].moods == ('calm', 'ambient') and saved[1].role == 'catalog'
    assert saved[2].license == LICENSE_CC_BY_4 and 'rec' in saved[2].attribution and saved[2].url == 'https://cdn.freesound.org/previews/1/43_hq.mp3'
    query = parse_qs(urlsplit(inner.calls[0]).query)
    assert query['filter'][0].startswith('duration:[60 TO 600]')
    assert KEY not in catalog.read_text(encoding='utf-8')


def load_cli():
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location('hook_harvest_cli', CLI)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def test_cli_probe_and_dry_run_never_print_the_key_and_refuse_odd_arguments(tmp_path):
    cli = load_cli()
    inner, transport = metered(routes(hits=[pixabay_hit(11)], sounds=[freesound_result(21)]))
    pixabay, freesound = clients(transport)
    opened = []

    def services(layout, environ, *, need_db, budget):
        opened.append((need_db, budget.max_requests))
        return cli.HarvestServices(pixabay, freesound, transport, budget, FakeMedia(), MemoryHookLibrary(), tmp_path / 'catalog.json', lambda: {'pixabay': 1, 'freesound': None}, lambda: None)

    lines, errors = [], []
    environ = {'AIAVC_DATA_DIR': str(tmp_path / 'data')}
    assert cli.main(['--probe'], environ=environ, out=lines.append, err=errors.append, services=services) == 0
    assert lines == ['pixabay: 1 kết quả dùng được', 'freesound: 1 kết quả dùng được'] and opened == [(False, 2)] and inner.downloads() == []
    assert cli.main(['hooks', '--dry-run', '--per-query', '2'], environ=environ, out=lines.append, err=errors.append, services=services) == 0
    assert inner.downloads() == [] and any('dự kiến (chạy thử) 2' in line for line in lines)
    for argv in (['--key', KEY], ['hooks', KEY], ['hooks', '--per-query', '0'], ['music', '--per-query', '3'], []):
        assert cli.main(argv, environ=environ, out=lines.append, err=errors.append, services=services) == 2
    assert KEY not in ' '.join(lines + errors) and errors[-1].startswith('Cách dùng: harvest_media.py')
    assert 'argparse' not in CLI.read_text(encoding='utf-8')
    assert probe_providers(pixabay=pixabay, freesound=freesound) == ['pixabay: 1 kết quả dùng được', 'freesound: 1 kết quả dùng được']


@pytest.fixture
def pinned_ffmpeg():
    if not (FFMPEG.is_file() and FFPROBE.is_file()):
        pytest.fail('BLOCKED_EXTERNAL: thiếu ffmpeg và ffprobe đã ghim tại C:/ffmpeg/bin', pytrace=False)


def make_source(tmp_path, name, args):
    target = tmp_path / name
    subprocess.run([str(FFMPEG), '-nostdin', '-hide_banner', '-loglevel', 'error', *args, '-y', str(target)], check=True, timeout=120)
    return target.read_bytes()


def test_pinned_ffmpeg_cuts_a_four_second_clip_and_a_short_loud_wav(tmp_path, pinned_ffmpeg):
    media = FfmpegHookMedia(FFMPEG, FFPROBE)
    video = make_source(tmp_path, 'source.mp4', ['-f', 'lavfi', '-i', 'testsrc=size=640x360:rate=25:duration=6', '-c:v', 'libx264', '-pix_fmt', 'yuv420p'])
    clip = media.cut_visual(video)
    assert clip.extension == 'mp4' and clip.technical['width'] == '640' and clip.technical['height'] == '360' and clip.technical['fps'] == '30'
    assert 3900 <= int(clip.technical['duration_ms']) <= 4100
    sound = make_source(tmp_path, 'source.wav', ['-f', 'lavfi', '-i', 'sine=frequency=440:duration=2', '-ar', '22050', '-ac', '1'])
    wav = media.normalize_audio(sound)
    assert wav.extension == 'wav' and wav.data[:4] == b'RIFF' and wav.technical['sample_rate_hz'] == '48000' and wav.technical['channels'] == '2'
    assert 1900 <= int(wav.technical['duration_ms']) <= 2100
    with pytest.raises(MediaProcessingError) as caught:
        media.cut_visual(b'not a video')
    assert str(caught.value) == 'harvest_media_failed'
