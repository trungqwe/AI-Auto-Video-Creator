"""CP7-5 / RG-04: thu thập RSS/web thật và khóa holdout.

Bảy nguồn của tools/launcher/prod/sources.json đi qua RealHttpTransport, SecureFetcher, RealFeedSource và collect_source thật
(UoW trong bộ nhớ). Mỗi nguồn: pha 1 dừng giữa lượt sau 2 bài đã commit, pha 2 chạy tiếp từ checkpoint và thêm một URL 404 thật
của chính nguồn (đường dẫn cp7-not-found); ≤ 5 bài và ≤ 1 ảnh kèm mỗi bài. Fetch đi qua cổng đồng thời của hồ sơ production
(4 toàn cục, 1 mỗi host). Trần: 0 USD, ≤ 35 bài, ≤ 35 ảnh, ≤ 200 MiB. Cách dừng: Deadline 30 phút; Ctrl+C.
Phần scheduler cloud là OUT_OF_V1_SCOPE (OI-CP7-03), không ghi PASS. Không in nội dung bài, chỉ in số đo.
"""
import hashlib
import json
import random
import re
import socket
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, datetime, timezone
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
for _path in (REPO / 'tools' / 'real', REPO / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pytest  # noqa: E402,F401

import cp7_common as c  # noqa: E402
from controlplane.domain.common.contracts import ProblemDetail  # noqa: E402
from source_ingestion.adapters.memory import InMemoryUnitOfWork  # noqa: E402
from source_ingestion.adapters.real_feed_source import RealFeedSource  # noqa: E402
from source_ingestion.adapters.real_http_transport import RealHttpTransport  # noqa: E402
from source_ingestion.adapters.real_media_fetch import RealMediaFetcher  # noqa: E402
from source_ingestion.adapters.secure_fetch import (  # noqa: E402
    REDIRECT_STATUSES, FetchPolicy, SecureFetcher, TransportResponse)
from source_ingestion.application.collect_source import (  # noqa: E402
    CollectSourceRequest, SourceCollectionJob, collect_source)
from source_ingestion.domain.locator import canonicalize_locator, validate_destination  # noqa: E402
from source_ingestion.domain.source import SourcePolicy, register_source  # noqa: E402
from source_ingestion.ports.source_adapter import (  # noqa: E402
    CandidateListing, ExtractedCandidate, FetchedDocument)
from source_ingestion.worker.production_deps import (  # noqa: E402
    DEFAULT_ADAPTER_REVISION, DEFAULT_EXTRACTION_POLICY, DEFAULT_RETRY_POLICY, _FetchBridge)


PROD = REPO / 'tools' / 'launcher' / 'prod'
PROFILE = json.loads((PROD / 'profile.json').read_text(encoding='utf-8'))['collection']
SOURCES = json.loads((PROD / 'sources.json').read_text(encoding='utf-8'))['sources']
MANIFEST_PATH = REPO / 'tests' / 'real' / 'fixtures' / 'cp7_holdout_manifest.json'
REPORT_PATH = REPO / 'docs' / 'delivery-evidence' / 'cp7-5' / 'report.md'
DEADLINE = c.Deadline(30 * 60)
STOP = threading.Event()
WORKSPACE = 'cp7-5'
MIB = 1024 * 1024
BYTES_CAP = 200 * MIB
ARTICLE_CAP = 35
IMAGE_CAP = 35
ARTICLES_PER_SOURCE = 5
INTERRUPT_AFTER = 2
MIN_TEXT = PROFILE['extraction_min_text_chars']['value']
GLOBAL_LIMIT = PROFILE['concurrency']['value']['global_fetches']
HOST_LIMIT = PROFILE['concurrency']['value']['per_host_fetches']
HOLDOUT_SEED = 'cp7-5-holdout-v1'
HOLDOUT_PAIRS = 40


def _policy(kind):
    value = PROFILE['fetch_policy'][kind]['value']
    return FetchPolicy(
        revision='profile-cp7-5-' + kind, max_redirects=value['max_redirects'], max_body_bytes=value['max_body_bytes'],
        allowed_media_types=frozenset(value['content_types']), timeout_seconds=value['timeout_seconds'])


FEED_POLICY, ARTICLE_POLICY, IMAGE_POLICY = _policy('feed'), _policy('article'), _policy('image')


def _resolve(host):
    # Bản sao hành vi system_dns_resolver của sản phẩm (src/controlplane/api/wiring/collection.py): DNS hệ thống thật.
    try:
        return tuple(sorted({info[4][0] for info in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}))
    except OSError:
        return ()


class _CapExceeded(BaseException):
    # Dừng cứng khi vượt trần byte hoặc có yêu cầu dừng; BaseException để SecureFetcher và collect_source không nuốt.
    pass


class _Interrupted(BaseException):
    # Giả lập Ctrl+C giữa hai bài của một lượt.
    pass


class MeterTransport:
    # Bọc RealHttpTransport thật: ghi từng hop, giữ cổng đồng thời của hồ sơ (4 toàn cục, 1 mỗi host), đếm byte, băm raw bytes.
    def __init__(self, inner):
        self._inner, self._lock = inner, threading.Lock()
        self._global, self._hosts = threading.Semaphore(GLOBAL_LIMIT), {}
        self._active, self._active_host = 0, {}
        self.max_global, self.max_host, self.total_bytes = 0, 0, 0
        self.hops, self.digests = [], set()

    def guard(self):
        DEADLINE.check()
        if STOP.is_set() or self.total_bytes >= BYTES_CAP:
            raise _CapExceeded('stop requested or byte ceiling reached')

    def _gate(self, host):
        with self._lock:
            return self._hosts.setdefault(host, threading.Lock())

    def send(self, request):
        self.guard()
        gate = self._gate(request.host)
        gate.acquire()
        self._global.acquire()
        with self._lock:
            self._active += 1
            self._active_host[request.host] = self._active_host.get(request.host, 0) + 1
            self.max_global = max(self.max_global, self._active)
            self.max_host = max(self.max_host, self._active_host[request.host])
        try:
            self.guard()
            limited = replace(request, timeout_seconds=min(request.timeout_seconds, DEADLINE.remaining()))
            response = self._inner.send(limited)
        except BaseException:
            self.release(request, None, None)
            raise
        return replace(response, body=_MeteredBody(self, request, response))

    def release(self, request, status, digest):
        with self._lock:
            self._active -= 1
            self._active_host[request.host] -= 1
            self.hops.append({'host': request.host, 'locator': request.locator, 'status': status,
                              'addresses': tuple(str(address) for address in request.addresses)})
            if digest is not None:
                self.digests.add(digest)
        self._global.release()
        self._gate(request.host).release()


class _MeteredBody:
    # Giữ chỗ đồng thời tới khi SecureFetcher gọi close(); băm từng chunk; digest chỉ ghi khi đọc hết thân 2xx.
    def __init__(self, meter, request, response):
        self._meter, self._request, self._response = meter, request, response
        self._hash, self._complete, self._closed = hashlib.sha256(), False, False

    def __iter__(self):
        for chunk in self._response.body:
            self._hash.update(chunk)
            with self._meter._lock:
                self._meter.total_bytes += len(chunk)
            self._meter.guard()
            yield chunk
        self._complete = True

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            close = getattr(self._response.body, 'close', None)
            if callable(close):
                close()
        finally:
            done = self._complete and 200 <= self._response.status < 300
            self._meter.release(self._request, self._response.status, self._hash.hexdigest() if done else None)


class _Source:
    # Bọc RealFeedSource thật: pha 1 chọn và đóng băng ≤ 5 bài rồi dừng giữa lượt; pha 2 thêm URL 404 thật rồi chỉ lấy bài chưa commit; nhớ ảnh kèm.
    def __init__(self, inner, not_found):
        self.inner, self.descriptor, self.not_found = inner, inner.descriptor, not_found
        self.interrupt_after, self.committed = None, frozenset()
        self.selected, self.entries, self.feed_problem = None, 0, None
        self.fetch_log, self.fetched_ok, self.probe_404, self.media = [], 0, None, {}

    def list_candidates(self, locator, cursor):
        if self.selected is None:
            listing = self.inner.list_candidates(locator, cursor)
            if not isinstance(listing, CandidateListing):
                self.feed_problem = str(listing.values.get('code') if isinstance(listing, ProblemDetail) else listing.code)
                return listing
            self.entries = len(listing.locators)
            self.selected = tuple(listing.locators[:ARTICLES_PER_SOURCE])
            return CandidateListing(self.selected, None, True)
        pending = tuple(item for item in self.selected if item not in self.committed)
        return CandidateListing((self.not_found,) + pending, None, True)

    def fetch_document(self, locator):
        DEADLINE.check()
        if self.interrupt_after is not None and self.fetched_ok >= self.interrupt_after:
            raise _Interrupted('stop between two items')
        result = self.inner.fetch_document(locator)
        if locator == self.not_found:
            if isinstance(result, FetchedDocument):
                self.probe_404 = ('FETCHED', result.observation.status)
            else:
                self.probe_404 = (result.values.get('code'), result.values.get('status'))
            return result
        self.fetch_log.append((self.interrupt_after is not None, locator))
        if isinstance(result, FetchedDocument):
            self.fetched_ok += 1
        return result

    def extract_candidate(self, document):
        result = self.inner.extract_candidate(document)
        if isinstance(result, ExtractedCandidate):
            self.media[document.observation.final_locator] = tuple(result.technical_fields.get('media') or ())
        return result


def _run_source(source, fetcher, staging):
    code, started = source['code'], time.monotonic()
    feed_url = canonicalize_locator(source['url'])
    parts = urlsplit(feed_url)
    unit = InMemoryUnitOfWork()
    policy = SourcePolicy('cp7-5', frozenset({'rss_feed'}), frozenset(PROFILE['tiers']['value']), frozenset())
    registered = register_source(
        source_id=code, workspace_id=WORKSPACE, canonical_locator=feed_url, name=code, source_kind='rss_feed',
        tier=source['tier'], topics=['news'], notes='', collection_enabled=True, admin_metadata={}, actor='cp7-5',
        at=datetime.now(timezone.utc), policy=policy)
    with unit:
        unit.sources.add(registered)
        unit.commit()
    adapter = _Source(
        RealFeedSource(fetcher, source_kind='rss_feed', feed_policy=FEED_POLICY, article_policy=ARTICLE_POLICY),
        f'{parts.scheme}://{parts.netloc}/cp7-not-found')
    bridge = _FetchBridge()
    request = CollectSourceRequest(
        workspace_id=WORKSPACE, source_id=code, business_date=date.today(), run_id='cp7-5-' + code,
        retry_policy=DEFAULT_RETRY_POLICY, adapter_revision=DEFAULT_ADAPTER_REVISION,
        extraction_policy=DEFAULT_EXTRACTION_POLICY)
    job = SourceCollectionJob(request, bridge.bind(adapter), bridge)
    adapter.interrupt_after = INTERRUPT_AFTER
    interrupted, second = False, None
    try:
        collect_source(unit, job)
    except _Interrupted:
        interrupted = True
    done = {r.payload['requested_url']: r.observation_fingerprint for r in unit.packages.list_by_run(request.run_id)}
    latest = unit.checkpoints.get_latest(code)
    revision_1 = latest.revision if latest else 0
    if interrupted:
        adapter.interrupt_after, adapter.committed = None, frozenset(done)
        second = collect_source(unit, job)
    records = unit.packages.list_by_run(request.run_id)
    latest = unit.checkpoints.get_latest(code)
    media_fetcher = RealMediaFetcher(
        fetcher, image_policy=IMAGE_POLICY, staging_root=Path(staging) / code, max_images_per_article=1)
    offered, staged, digests, hash_ok = 0, 0, [], True
    for record in records:
        images = [m for m in adapter.media.get(record.payload['final_url'], ()) if m.get('media_kind') == 'image']
        offered += 1 if images else 0
        batch = media_fetcher.fetch_article_media(
            images[:1], source_ref=code, article_ref=str(record.payload['collected_document_id']))
        for image in batch.staged:
            staged += 1
            digests.append(image.sha256)
            hash_ok = hash_ok and hashlib.sha256(image.staged_path.read_bytes()).hexdigest() == image.sha256
    return {
        'code': code, 'host': parts.hostname, 'feed_ok': adapter.selected is not None, 'feed_problem': adapter.feed_problem,
        'entries': adapter.entries, 'interrupted': interrupted, 'done_1': done, 'revision_1': revision_1,
        'revision_2': latest.revision if latest else 0, 'second': second, 'probe_404': adapter.probe_404,
        'pending': len([item for item in (adapter.selected or ()) if item not in done]),
        'records': [(r.payload['requested_url'], r.canonical_locator, r.observation_fingerprint) for r in records],
        'texts': [len(r.payload['extracted_content_candidate']['text']) for r in records],
        'fetch_log': adapter.fetch_log, 'offered': offered, 'staged': staged, 'image_digests': digests,
        'image_hash_ok': hash_ok, 'seconds': time.monotonic() - started}


@pytest.fixture(scope='module')
def collection():
    meter = MeterTransport(RealHttpTransport(user_agent=PROFILE['user_agent']['value']))
    fetcher = SecureFetcher(meter, _resolve)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='cp7-5-media-') as staging:
        with ThreadPoolExecutor(max_workers=GLOBAL_LIMIT) as pool:
            futures = [pool.submit(_run_source, source, fetcher, staging) for source in SOURCES]
            try:
                results = [future.result() for future in futures]
            except BaseException:
                STOP.set()
                raise
    return SimpleNamespace(results=results, meter=meter, elapsed=time.monotonic() - started)


def test_feeds_alive(collection, emit):
    assert len(SOURCES) == 7
    for r in collection.results:
        code, ok, problem, entries = r['code'], r['feed_ok'], r['feed_problem'], r['entries']
        articles, offered, staged, seconds = len(r['records']), r['offered'], r['staged'], r['seconds']
        emit(f'detail source={code} feed_ok={ok} problem={problem} entries={entries} articles={articles} images_offered={offered} images_staged={staged} seconds={seconds:.1f}')
    good = [r for r in collection.results if r['feed_ok'] and r['entries'] >= 5]
    hops_200 = sum(1 for hop in collection.meter.hops if hop['status'] == 200)
    emit(f'detail feeds_alive good={len(good)}/7 hops_status_200={hops_200}')
    assert len(good) >= 6 and hops_200 >= len(good)
    assert sum(r['staged'] for r in collection.results) >= 1
    emit(c.report_line('RG-04', 'feeds_alive', 'PASS'))


def test_extraction_ratio(collection, emit):
    texts = [length for r in collection.results for length in r['texts']]
    long_enough = sum(1 for length in texts if length >= MIN_TEXT)
    emit(f'detail extraction articles={len(texts)} text_ge_{MIN_TEXT}={long_enough}')
    assert len(texts) >= 20 and long_enough * 10 >= len(texts) * 9
    emit(c.report_line('RG-04', 'extraction_ratio', 'PASS'))


def test_source_404_isolated(collection, emit):
    probed = [r for r in collection.results if r['second'] is not None]
    for r in probed:
        second, code, probe = r['second'], r['code'], r['probe_404']
        emit(f'detail 404 source={code} probe={probe} pending={r["pending"]} committed={second.packages_committed} failed={second.failed}')
        assert probe == ('HTTP_STATUS_REJECTED', 404), (code, probe)
        assert second.urls_seen == 1 + r['pending']
        assert second.packages_committed + second.skipped + (second.failed - 1) == r['pending']
    assert len(probed) >= 5
    assert sum(1 for r in collection.results if r['records']) >= 6
    emit(c.report_line('RG-04', 'source_404_isolated', 'PASS'))


def test_checkpoint_resume(collection, emit):
    resumed = [r for r in collection.results if r['interrupted']]
    assert len(resumed) >= 5
    for r in resumed:
        before, records = r['done_1'], r['records']
        keys = [requested for requested, _canonical, _fp in records]
        assert 1 <= len(before) <= INTERRUPT_AFTER and r['revision_1'] == len(before)
        assert len(keys) == len(set(keys)), 'duplicate article after resume'
        assert len({(canonical, fp) for _requested, canonical, fp in records}) == len(records)
        after = {requested: fp for requested, _canonical, fp in records}
        assert all(after.get(key) == value for key, value in before.items())
        assert not [loc for phase_1, loc in r['fetch_log'] if not phase_1 and loc in before]
        assert r['revision_2'] == len(records)
    emit(f'detail checkpoint resumed_sources={len(resumed)} duplicates=0')
    emit(c.report_line('RG-04', 'checkpoint_resume', 'PASS'))


class _Redirect:
    # Control SSRF offline: mọi hop đầu trả 302 tới Location cố định; không dùng cho dữ liệu nguồn.
    def __init__(self, location):
        self.location, self.calls = location, 0

    def send(self, request):
        self.calls += 1
        return TransportResponse(302, (('Location', self.location),), iter(()))


def test_ssrf_policy(collection, emit):
    hops = collection.meter.hops
    redirects = sum(1 for hop in hops if hop['status'] in REDIRECT_STATUSES)
    for hop in hops:
        validate_destination(hop['host'], hop['addresses'])
    emit(f'detail ssrf hops={len(hops)} redirect_hops={redirects} private_hops=0')
    policy = FetchPolicy(revision='cp7-5-control', max_redirects=3, max_body_bytes=1024,
                         allowed_media_types=frozenset({'text/html'}), timeout_seconds=5)
    resolver = lambda host: ('10.0.0.5',) if host == 'internal.example' else ('8.8.8.8',)
    for target in ('http://127.0.0.1/admin', 'http://169.254.169.254/latest', 'http://internal.example/x'):
        stub = _Redirect(target)
        result = SecureFetcher(stub, resolver).fetch('https://start.example/x', policy, correlation_id='cp7-5-control')
        assert isinstance(result, ProblemDetail) and result.values['code'] == 'UNSAFE_REDIRECT' and stub.calls == 1
    emit('detail ssrf control=3 private_redirects_rejected_before_connect')
    emit(c.report_line('RG-04', 'ssrf_policy', 'PASS'))


def test_concurrency_limits(collection, emit):
    meter = collection.meter
    emit(f'detail concurrency global_limit={GLOBAL_LIMIT} host_limit={HOST_LIMIT} max_global={meter.max_global} max_host={meter.max_host} fetches={len(meter.hops)}')
    assert (GLOBAL_LIMIT, HOST_LIMIT) == (4, 1)
    assert 1 <= meter.max_global <= GLOBAL_LIMIT and 1 <= meter.max_host <= HOST_LIMIT
    emit(c.report_line('RG-04', 'concurrency_limits', 'PASS'))


def test_raw_hash(collection, emit):
    digests, total = collection.meter.digests, 0
    for r in collection.results:
        for _requested, _canonical, fingerprint in r['records']:
            assert re.fullmatch('[0-9a-f]{64}', fingerprint) and fingerprint in digests
            total += 1
        assert r['image_hash_ok'] and all(digest in digests for digest in r['image_digests'])
    assert total >= 20
    emit(f'detail raw_hash packages={total} distinct_body_digests={len(digests)}')
    emit(c.report_line('RG-04', 'raw_hash', 'PASS'))


def test_cycle_time(collection, emit):
    assert 0 < collection.elapsed < 30 * 60
    emit(f'detail cycle_time basis=MEASURED seconds={collection.elapsed:.1f}')
    emit(c.report_line('RG-04', 'cycle_time', 'PASS'))


def test_cost_ceiling(collection, emit):
    articles = sum(len(r['records']) for r in collection.results)
    images = sum(r['staged'] for r in collection.results)
    total = collection.meter.total_bytes
    emit(f'detail ceiling cost_usd=0 articles={articles}/{ARTICLE_CAP} images={images}/{IMAGE_CAP} mib={total / MIB:.2f}/200 deadline_left_s={DEADLINE.remaining():.0f}')
    assert articles <= ARTICLE_CAP and images <= IMAGE_CAP and total <= BYTES_CAP


HOLDOUT_RULE = 'sort article ids; list all unordered id pairs in lexicographic order; random.Random(seed).sample(range(pair_total), 40); keep chosen indices ascending'
MANIFEST_KEYS = {'schema_version', 'seed', 'rule', 'pair_count', 'articles', 'pairs', 'id', 'raw_sha256'}


def _article_id(code, requested):
    return code + '-' + hashlib.sha256(requested.encode('utf-8')).hexdigest()[:12]


def _select_pairs(articles):
    pairs = list(combinations(sorted(article['id'] for article in articles), 2))
    chosen = sorted(random.Random(HOLDOUT_SEED).sample(range(len(pairs)), HOLDOUT_PAIRS))
    return [list(pairs[index]) for index in chosen]


def _build_manifest(results):
    articles = sorted(
        ({'id': _article_id(r['code'], requested), 'raw_sha256': fingerprint}
         for r in results for requested, _canonical, fingerprint in r['records']),
        key=lambda article: article['id'])
    return {'schema_version': 1, 'seed': HOLDOUT_SEED, 'rule': HOLDOUT_RULE, 'pair_count': HOLDOUT_PAIRS,
            'articles': articles, 'pairs': _select_pairs(articles)}


def _keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _keys(item)


def test_holdout_locked(collection, emit):
    created = not MANIFEST_PATH.exists()
    if created:
        assert sum(len(r['records']) for r in collection.results) >= 10
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MANIFEST_PATH, 'w', encoding='utf-8', newline=chr(10)) as handle:
            handle.write(json.dumps(_build_manifest(collection.results), indent=2) + chr(10))
    raw = MANIFEST_PATH.read_bytes()
    manifest = json.loads(raw.decode('utf-8'))
    assert set(_keys(manifest)) <= MANIFEST_KEYS
    assert manifest['pair_count'] == HOLDOUT_PAIRS == len(manifest['pairs'])
    ids = {article['id'] for article in manifest['articles']}
    assert len(ids) == len(manifest['articles']) >= 10
    assert all(re.fullmatch('[0-9a-f]{64}', article['raw_sha256']) for article in manifest['articles'])
    assert all(a != b and a in ids and b in ids for a, b in manifest['pairs'])
    assert len({tuple(pair) for pair in manifest['pairs']}) == HOLDOUT_PAIRS
    assert manifest['seed'] == HOLDOUT_SEED and manifest['pairs'] == _select_pairs(manifest['articles'])
    digest = hashlib.sha256(raw.replace(bytes([13, 10]), bytes([10]))).hexdigest()
    if REPORT_PATH.exists():
        assert f'holdout_manifest_sha256: {digest}' in REPORT_PATH.read_text(encoding='utf-8')
    emit(f'detail holdout created={created} pairs={len(manifest["pairs"])} articles={len(ids)} manifest_sha256={digest}')
    emit(c.report_line('RG-04', 'holdout_locked', 'PASS'))


def test_secret_scan(collection, emit):
    assert c.scan_secrets(MANIFEST_PATH.read_text(encoding='utf-8')) == []
    if REPORT_PATH.exists():
        assert c.scan_secrets(REPORT_PATH.read_text(encoding='utf-8')) == []
    emit('detail secret_scan manifest_and_report_clean evidence_lines_scanned_by_emit')
    emit(c.report_line('RG-04', 'secret_scan', 'PASS'))
