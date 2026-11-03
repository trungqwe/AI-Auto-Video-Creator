"""HOOK-HARVEST: hook thu từ kho được nhập thật vào bảng hook, tài sản và artifact của C (PostgreSQL thật, transport và ffmpeg giả, không mạng).

Sau khi nhập, cổng ứng viên production (PostgresHookCandidates qua launcher.open_hooks, exclude_placeholders=True) đưa ra đúng các hook đó với
rights_cleared và provenance.index, bản đã xử lý có version đã kiểm cho render, và chạy lại không thêm dòng nào.

coveredIds: FR-HOOK-004, FR-HOOK-005
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import pathlib
import sys
from dataclasses import dataclass
from urllib.parse import urlsplit

import pytest

from controlplane.application.storage_meta.handlers import STAGED_HOOK_EXTENSIONS, verified_version_for_sha
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.production_ports.stock_harvest import HarvestBudget, MeteredTransport, PostgresHookLibrary, ProcessedMedia, harvest_hooks
from controlplane.infrastructure.production_ports.stock_media import FREESOUND_SEARCH_API, PIXABAY_VIDEO_API, FreesoundSearch, PixabayVideoSearch
from creative.adapters.hook_candidates import PostgresHookCandidates

ROOT = pathlib.Path(__file__).resolve().parents[3]
LAUNCHER_PATH = ROOT / 'tools' / 'launcher' / 'launcher.py'
COUNT_TABLES = ('cp_media_assets', 'cp_hooks', 'cp_hook_revisions', 'cp_artifact_versions')
HIT = {'id': 11, 'pageURL': 'https://pixabay.com/videos/x-11/', 'tags': 'police, night', 'duration': 8, 'user': 'maker',
       'videos': {'medium': {'url': 'https://cdn.pixabay.com/video/11_medium.mp4', 'width': 1280, 'height': 720}}}
SOUND = {'id': 21, 'name': 'Whoosh 21', 'tags': ['whoosh'], 'description': 'fast air swish', 'license': 'https://creativecommons.org/licenses/by/4.0/',
         'username': 'rec', 'duration': 1.5, 'url': 'https://freesound.org/people/rec/sounds/21/', 'previews': {'preview-hq-mp3': 'https://cdn.freesound.org/previews/1/21_hq.mp3'}}


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    final_url: str


class FakeTransport:
    ROUTES = {
        PIXABAY_VIDEO_API: json.dumps({'hits': [HIT]}).encode('utf-8'), FREESOUND_SEARCH_API: json.dumps({'results': [SOUND]}).encode('utf-8'),
        HIT['videos']['medium']['url']: b'video-11', SOUND['previews']['preview-hq-mp3']: b'sound-21'}

    def fetch(self, url, *, max_bytes, timeout_seconds):
        parts = urlsplit(url)
        return Response(200, self.ROUTES[parts.scheme + '://' + parts.netloc + parts.path], url)


class Keys:
    @contextlib.contextmanager
    def acquire(self, provider):
        yield 'Kx9canaryHarvestKey0123456789'


class FakeMedia:
    def cut_visual(self, data):
        return ProcessedMedia(b'mp4:' + data, 'mp4', {'width': '1280', 'height': '720', 'fps': '30', 'duration_ms': '4000'})

    def normalize_audio(self, data):
        return ProcessedMedia(b'wav:' + data, 'wav', {'sample_rate_hz': '48000', 'channels': '2', 'duration_ms': '1500'})


@pytest.fixture(scope='module')
def launcher():
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location('hook_harvest_launcher', LAUNCHER_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


@pytest.fixture
def manager(pw_database):
    manager = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        yield manager
    finally:
        manager.close()


def counts(database):
    with database.connect() as connection:
        return {table: connection.execute(f'SELECT count(*) FROM controlplane.{table} WHERE workspace_id = %s', (database.workspace_id,)).fetchone()[0] for table in COUNT_TABLES}


def harvest(store):
    transport = MeteredTransport(FakeTransport(), HarvestBudget(), sleep=lambda seconds: None)
    return harvest_hooks(
        pixabay=PixabayVideoSearch(transport=transport, keys=Keys()), freesound=FreesoundSearch(transport=transport, keys=Keys()), transport=transport,
        media=FakeMedia(), store=store, per_query=2, visual_queries=('police lights night',), audio_queries=('whoosh',))


def test_harvested_hooks_become_production_candidates_with_verified_versions(launcher, pw_database, manager, tmp_path):
    workspace_id = pw_database.workspace_id
    staging = tmp_path / 'staging'
    store = PostgresHookLibrary(manager, workspace_id=workspace_id, staging_root=staging)
    report = harvest(store)
    assert (report.imported, report.existing, report.skipped, report.stopped) == (2, 0, {}, [])
    hooks = PostgresHookCandidates(launcher.open_hooks(manager), safety_policy_revision='safe-r1', exclude_placeholders=True)
    visual = hooks.visual_hook_candidates(workspace_id=workspace_id, snapshot_ref='snap-1')
    audio = hooks.audio_hook_candidates(workspace_id=workspace_id, snapshot_ref='snap-1')
    assert [item.hook_id for item in visual] == ['pxb-11'] and [item.hook_id for item in audio] == ['fs-21']
    for item, sha, extension in ((visual[0], hashlib.sha256(b'mp4:video-11').hexdigest(), 'mp4'), (audio[0], hashlib.sha256(b'wav:sound-21').hexdigest(), 'wav')):
        assert item.safety_rights_status['rights_cleared'] is True and item.provenance['sha256'] == sha
        assert item.provenance['index']['license'] in ('Pixabay Content License', 'CC-BY-4.0') and item.provenance['placeholder'] is False
        assert (staging / 'media' / f'{sha}.{extension}').is_file()
        assert verified_version_for_sha(manager, workspace_id=workspace_id, sha256=sha, extensions=STAGED_HOOK_EXTENSIONS) is not None
    assert audio[0].provenance['index']['author'] == 'rec'
    assert store.count_by_source() == {'audio_hook:freesound': 1, 'visual_hook:pixabay': 1}
    first = counts(pw_database)
    assert first == {'cp_media_assets': 2, 'cp_hooks': 2, 'cp_hook_revisions': 2, 'cp_artifact_versions': 2}
    again = harvest(store)
    assert (again.imported, again.existing) == (0, 2) and counts(pw_database) == first
