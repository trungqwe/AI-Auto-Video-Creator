"""ADAPT-A: real HTTP transport (loopback only), RSS/Atom adapter and image fetch (offline fakes)."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import http.server
import io
import ipaddress
import logging
import pathlib
import socket
import threading
import urllib.request
from datetime import datetime, timezone

import feedparser
import pytest
import trafilatura

from catalog.application.discovery import DiscoveryObservation
from catalog.domain.identity import MediaKind, ProvenanceRelation
from controlplane.domain.common.contracts import ProblemDetail
from source_ingestion.adapters.real_feed_source import RealFeedSource
from source_ingestion.adapters.real_http_transport import RealHttpTransport
from source_ingestion.adapters.real_media_fetch import RealMediaFetcher, StagedImage
from source_ingestion.adapters.secure_fetch import FetchPolicy, SecureFetcher, TransportRequest, TransportResponse
from source_ingestion.ports.source_adapter import (
    AdapterOperation, CandidateListing, CapabilityUnavailable, ExtractedCandidate, FetchedDocument, ProbeResult, SourceAdapter,
)

ROOT = pathlib.Path(__file__).resolve().parents[4]
ADAPTERS = ROOT / 'src' / 'source_ingestion' / 'adapters'
PUBLIC = '93.184.216.34'
LOOPBACK = ipaddress.ip_address('127.0.0.1')
NOW = datetime(2026, 10, 21, 8, 30, 0, tzinfo=timezone.utc)
SECRET = 'SECRET-VALUE-7f3a'


def policy(types, **overrides):
    values = {'revision': 'fp-r1', 'max_redirects': 3, 'max_body_bytes': 200000,
              'allowed_media_types': frozenset(types), 'timeout_seconds': 10.0}
    values.update(overrides)
    return FetchPolicy(**values)


FEED_POLICY = policy({'application/rss+xml', 'application/atom+xml'})
ARTICLE_POLICY = policy({'text/html'})
IMAGE_POLICY = policy({'image/jpeg', 'image/png', 'image/webp'}, max_body_bytes=5000)


class FakeResolver:
    def __init__(self, table):
        self.table = table

    def __call__(self, host):
        if host not in self.table:
            raise socket.gaierror('fake resolver: unknown host')
        return list(self.table[host])


class FakeTransport:
    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        route = self.routes[request.locator]
        if isinstance(route, BaseException):
            raise route
        return route


def response(status, headers=(), chunks=()):
    return TransportResponse(status, tuple(headers), list(chunks))


def make_fetcher(routes, table=None):
    transport = FakeTransport(routes)
    names = {'news.example': [PUBLIC], 'img.example': [PUBLIC]} if table is None else table
    return SecureFetcher(transport, FakeResolver(names)), transport


@pytest.fixture
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('real network call in offline test')
    for owner, name in (
        (socket.socket, 'connect'), (socket, 'getaddrinfo'), (socket, 'create_connection'), (urllib.request, 'urlopen'),
    ):
        monkeypatch.setattr(owner, name, forbidden)


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, body, headers):
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.server.seen.append({'command': self.command, 'path': self.path, 'host': self.headers.get('Host')})
        path = self.path.split('?')[0]
        html = {'Content-Type': 'text/html'}
        try:
            if path == '/ok':
                self._send(200, b'hello', html)
            elif path == '/redirect':
                self._send(302, b'', {'Location': '/ok'})
            elif path == '/redirect-internal':
                self._send(302, b'', {'Location': 'http://internal.example/secret'})
            elif path == '/big':
                self._send(200, b'x' * 100000, html)
            elif path == '/stream':
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                for _ in range(200):
                    self.wfile.write(b'y' * 1000)
                    self.wfile.flush()
            elif path == '/slow':
                self.server.release.wait(5)
                self._send(200, b'late', html)
            else:
                self._send(404, b'', {})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


@pytest.fixture
def loopback():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
    server.seen = []
    server.release = threading.Event()
    server.port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.release.set()
    server.shutdown()
    server.server_close()
    thread.join(5)


def transport_request(server, path, *, host='pinned.example', timeout=5.0):
    return TransportRequest(f'http://{host}:{server.port}{path}', host, (LOOPBACK,), timeout)


class LoopbackRewrite:
    """Lets SecureFetcher validate a public address, then connects to the loopback test server."""

    def __init__(self, inner):
        self.inner = inner

    def send(self, request):
        return self.inner.send(dataclasses.replace(request, addresses=(LOOPBACK,)))

def test_transport_connects_to_pinned_address_and_sends_get_with_host(loopback):
    resp = RealHttpTransport().send(transport_request(loopback, '/ok?a=1'))
    body = b''.join(resp.body)
    resp.body.close()
    assert resp.status == 200
    assert body == b'hello'
    assert dict(resp.headers)['Content-Type'] == 'text/html'
    assert loopback.seen == [{'command': 'GET', 'path': '/ok?a=1', 'host': f'pinned.example:{loopback.port}'}]


def test_transport_does_not_follow_redirect(loopback):
    resp = RealHttpTransport().send(transport_request(loopback, '/redirect'))
    assert resp.status == 302
    assert dict(resp.headers)['Location'] == '/ok'
    assert len(loopback.seen) == 1
    resp.body.close()


def test_transport_ignores_proxy_environment(loopback, monkeypatch):
    for var in ('HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy'):
        monkeypatch.setenv(var, 'http://127.0.0.1:9')
    resp = RealHttpTransport().send(transport_request(loopback, '/ok'))
    assert resp.status == 200
    assert len(loopback.seen) == 1
    resp.body.close()


def test_transport_reads_body_in_chunks(loopback):
    resp = RealHttpTransport(chunk_size=1024).send(transport_request(loopback, '/big'))
    chunks = list(resp.body)
    assert len(chunks) > 1
    assert max(map(len, chunks)) <= 1024
    assert sum(map(len, chunks)) == 100000
    resp.body.close()


def test_transport_times_out(loopback):
    with pytest.raises(TimeoutError):
        RealHttpTransport().send(transport_request(loopback, '/slow', timeout=0.3))


def test_transport_connection_refused_is_oserror():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    req = TransportRequest(f'http://pinned.example:{port}/', 'pinned.example', (LOOPBACK,), 2.0)
    with pytest.raises(OSError):
        RealHttpTransport().send(req)


def test_transport_rejects_unsupported_scheme_and_empty_addresses():
    req1 = TransportRequest('ftp://pinned.example/x', 'pinned.example', (LOOPBACK,), 1.0)
    req2 = TransportRequest('http://pinned.example/x', 'pinned.example', (), 1.0)
    with pytest.raises(ConnectionError):
        RealHttpTransport().send(req1)
    with pytest.raises(ConnectionError):
        RealHttpTransport().send(req2)


def test_secure_fetcher_with_real_transport_enforces_limits(loopback):
    fetcher = SecureFetcher(
        LoopbackRewrite(RealHttpTransport(chunk_size=1024)),
        FakeResolver({'news.example': [PUBLIC], 'internal.example': ['10.0.0.5']}),
    )
    base = f'http://news.example:{loopback.port}'
    pol = policy({'text/html'}, max_body_bytes=1000)
    assert fetcher.fetch(base + '/big', pol, correlation_id='t').code == 'BODY_TOO_LARGE'
    assert fetcher.fetch(base + '/stream', pol, correlation_id='t').code == 'BODY_TOO_LARGE'
    loopback.seen.clear()
    assert fetcher.fetch(base + '/redirect-internal', pol, correlation_id='t').code == 'UNSAFE_REDIRECT'
    assert len(loopback.seen) == 1
    doc = fetcher.fetch(base + '/redirect', pol, correlation_id='t')
    assert isinstance(doc, FetchedDocument)
    assert doc.body == b'hello'
    assert doc.observation.final_locator == base + '/ok'


FEED_LOCATOR = 'https://news.example/feed.xml'
ARTICLE_LOCATOR = 'https://news.example/a/1'

RSS_FEED = b'''<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
    <title>News Example</title>
    <link>https://news.example/feed.xml</link>
    <description>News Example Feed</description>
    <language>en</language>
    <item>
        <title>Port strike ends</title>
        <link>https://news.example/a/1</link>
        <dc:creator>Jane Roe</dc:creator>
        <pubDate>Tue, 20 Oct 2026 09:00:00 GMT</pubDate>
        <enclosure url="https://img.example/enc.jpg" type="image/jpeg" length="1000"/>
        <media:content url="https://img.example/mc.png" medium="image"/>
        <media:thumbnail url="https://img.example/th.webp"/>
    </item>
    <item>
        <title>Item 2</title>
        <link>/a/2</link>
    </item>
    <item>
        <title>Item 3 duplicate</title>
        <link>https://news.example/a/1</link>
    </item>
    <item>
        <title>Item 4 js</title>
        <link>javascript:alert(1)</link>
    </item>
</channel>
</rss>
'''

ATOM_FEED = b'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>Atom Feed</title>
    <link href="https://news.example/atom.xml"/>
    <updated>2026-10-20T09:00:00Z</updated>
    <id>tag:news.example,2026:feed</id>
    <entry>
        <id>tag:news.example,2026:1</id>
        <title>Atom item</title>
        <link rel="alternate" href="https://news.example/atom/1"/>
        <updated>2026-10-20T09:00:00Z</updated>
    </entry>
</feed>
'''

ARTICLE_HTML = b'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Port strike ends</title>
    <meta property="og:image" content="https://news.example/img/hero.jpg">
    <meta name="author" content="Jane Roe">
</head>
<body>
    <nav><a href="/">Home</a></nav>
    <article>
        <h1>Port strike ends</h1>
        <p>The harbour workers reached a comprehensive agreement following intensive negotiations that lasted throughout the previous evening and continued well into early Tuesday morning across the entire maritime terminal facility.</p>
        <p>Port operations resumed immediately as container traffic began moving steadily through the primary freight corridors, allowing long queues of waiting transport trucks to finally discharge their cargo safely.</p>
        <p>Union representatives praised the commitment of all participating delegates while management reiterated their collective dedication to establishing sustainable labor practices for every shift going forward.</p>
        <p>Economic analysts noted that the swift resolution prevented major supply chain bottlenecks from compounding ahead of the upcoming seasonal retail surge across international distribution hubs.</p>
    </article>
    <footer><p>Copyright 2026 News Example</p></footer>
</body>
</html>
'''


def feed_response(body, kind='application/rss+xml'):
    return response(200, [('Content-Type', kind + '; charset=utf-8')], [body])


def article_response():
    return response(200, [('Content-Type', 'text/html; charset=utf-8'), ('Set-Cookie', 'session=' + SECRET)], [ARTICLE_HTML])


def make_source(routes, kind='rss_feed'):
    fetcher, transport = make_fetcher(routes)
    source = RealFeedSource(
        fetcher,
        source_kind=kind,
        feed_policy=FEED_POLICY,
        article_policy=ARTICLE_POLICY,
        correlation_id=lambda: 'feed-test',
    )
    return source, transport


def test_rss_list_candidates_dedupes_and_keeps_only_http_links(no_network):
    source, _ = make_source({FEED_LOCATOR: feed_response(RSS_FEED)})
    listing = source.list_candidates(FEED_LOCATOR, None)
    assert isinstance(listing, CandidateListing)
    assert listing.locators == ('https://news.example/a/1', 'https://news.example/a/2')
    assert listing.complete is True
    assert isinstance(source.list_candidates(FEED_LOCATOR, 'cursor'), CapabilityUnavailable)


def test_atom_list_candidates(no_network):
    source, _ = make_source({FEED_LOCATOR: feed_response(ATOM_FEED, 'application/atom+xml')}, kind='atom_feed')
    listing = source.list_candidates(FEED_LOCATOR, None)
    assert isinstance(listing, CandidateListing)
    assert listing.locators == ('https://news.example/atom/1',)


def test_probe_reports_descriptor_and_kind_mismatch(no_network):
    source_rss, _ = make_source({FEED_LOCATOR: feed_response(RSS_FEED)}, kind='rss_feed')
    probe_rss = source_rss.probe(FEED_LOCATOR)
    assert isinstance(probe_rss, ProbeResult)
    assert probe_rss.descriptor.adapter_id == 'real-rss-feed'
    assert probe_rss.warnings == ()
    source_atom, _ = make_source({FEED_LOCATOR: feed_response(RSS_FEED)}, kind='atom_feed')
    probe_atom = source_atom.probe(FEED_LOCATOR)
    assert isinstance(probe_atom, ProbeResult)
    assert 'feed_kind_mismatch' in probe_atom.warnings
    assert isinstance(source_rss, SourceAdapter)


def test_extract_candidate_keeps_raw_bytes_versions_and_media(no_network):
    source, _ = make_source({FEED_LOCATOR: feed_response(RSS_FEED), ARTICLE_LOCATOR: article_response()})
    listing = source.list_candidates(FEED_LOCATOR, None)
    assert isinstance(listing, CandidateListing)
    doc = source.fetch_document(ARTICLE_LOCATOR)
    assert isinstance(doc, FetchedDocument)
    candidate = source.extract_candidate(doc)
    assert isinstance(candidate, ExtractedCandidate)
    fields = candidate.technical_fields
    assert fields['raw_bytes'] == ARTICLE_HTML
    assert fields['feedparser_version'] == feedparser.__version__ == '6.0.14'
    assert fields['trafilatura_version'] == trafilatura.__version__ == '2.2.0'
    assert fields['extractor_version'] == 'feedparser-6.0.14+trafilatura-2.2.0'
    assert 'harbour workers' in fields['text']
    assert 'Port strike' in fields['title']
    assert fields['author'] == 'Jane Roe'
    assert fields['published_at_raw'] == '2026-10-20T09:00:00Z'
    assert fields['published_at_origin'] == 'feed_entry_published'
    assert fields['language_tag'] == 'en'
    media_set = {(m['role'], m['locator']) for m in fields['media']}
    assert media_set == {
        ('enclosure', 'https://img.example/enc.jpg'),
        ('media_content', 'https://img.example/mc.png'),
        ('media_thumbnail', 'https://img.example/th.webp'),
        ('hero', 'https://news.example/img/hero.jpg'),
    }


def test_resume_and_supplemental_search_are_capability_unavailable(no_network):
    source, _ = make_source({})
    res1 = source.resume_from_checkpoint('v1', 'cursor')
    res2 = source.supplemental_search({'topic': 'x'})
    assert isinstance(res1, CapabilityUnavailable)
    assert isinstance(res2, CapabilityUnavailable)
    assert res1.operation == AdapterOperation.RESUME_FROM_CHECKPOINT
    assert res2.operation == AdapterOperation.SUPPLEMENTAL_SEARCH
    assert res1.code == 'CAPABILITY_UNAVAILABLE'
    assert res2.code == 'CAPABILITY_UNAVAILABLE'
    assert res1.adapter_id == 'real-rss-feed'


def test_network_failures_return_problem_detail_and_do_not_raise(no_network):
    source, _ = make_source({FEED_LOCATOR: ConnectionRefusedError(), ARTICLE_LOCATOR: TimeoutError()})
    prob_list = source.list_candidates(FEED_LOCATOR, None)
    assert isinstance(prob_list, ProblemDetail)
    assert prob_list.code == 'CONNECTION_FAILED'
    assert prob_list.retryable is True
    prob_probe = source.probe(FEED_LOCATOR)
    assert isinstance(prob_probe, ProblemDetail)
    assert prob_probe.code == 'CONNECTION_FAILED'
    assert prob_probe.retryable is True
    prob_fetch = source.fetch_document(ARTICLE_LOCATOR)
    assert isinstance(prob_fetch, ProblemDetail)
    assert prob_fetch.code == 'FETCH_TIMEOUT'

    source_503, _ = make_source({FEED_LOCATOR: response(503)})
    prob_503 = source_503.list_candidates(FEED_LOCATOR, None)
    assert isinstance(prob_503, ProblemDetail)
    assert prob_503.code == 'UPSTREAM_ERROR'

    fetcher_ssrf, transport_ssrf = make_fetcher({}, table={'news.example': ['10.0.0.5']})
    source_ssrf = RealFeedSource(fetcher_ssrf, source_kind='rss_feed', feed_policy=FEED_POLICY, article_policy=ARTICLE_POLICY)
    prob_ssrf = source_ssrf.list_candidates(FEED_LOCATOR, None)
    assert isinstance(prob_ssrf, ProblemDetail)
    assert prob_ssrf.code == 'UNSAFE_LOCATOR'
    assert transport_ssrf.requests == []

    source_bad, _ = make_source({FEED_LOCATOR: feed_response(b'<html><body>nope</body></html>')})
    prob_bad = source_bad.list_candidates(FEED_LOCATOR, None)
    assert isinstance(prob_bad, ProblemDetail)
    assert prob_bad.code == 'FEED_PARSE_FAILED'


def test_feedparser_and_trafilatura_run_only_on_downloaded_bytes(no_network, monkeypatch):
    feedparser_args = []
    trafilatura_args = []
    orig_fp = feedparser.parse
    orig_traf = trafilatura.extract

    def recording_fp(arg, *args, **kwargs):
        feedparser_args.append(arg)
        return orig_fp(arg, *args, **kwargs)

    def recording_traf(arg, *args, **kwargs):
        trafilatura_args.append(arg)
        return orig_traf(arg, *args, **kwargs)

    monkeypatch.setattr(feedparser, 'parse', recording_fp)
    monkeypatch.setattr(trafilatura, 'extract', recording_traf)

    source, _ = make_source({FEED_LOCATOR: feed_response(RSS_FEED), ARTICLE_LOCATOR: article_response()})
    source.list_candidates(FEED_LOCATOR, None)
    doc = source.fetch_document(ARTICLE_LOCATOR)
    source.extract_candidate(doc)

    assert len(feedparser_args) > 0
    assert all(isinstance(a, io.BytesIO) for a in feedparser_args)
    assert len(trafilatura_args) > 0
    assert all(isinstance(a, bytes) for a in trafilatura_args)


def test_no_cookie_or_token_reaches_log_or_observation(no_network, caplog):
    caplog.set_level(logging.DEBUG)
    token_url = f'https://news.example/feed.xml?token={SECRET}'
    feed_resp = response(
        200,
        [
            ('Content-Type', 'application/rss+xml; charset=utf-8'),
            ('Set-Cookie', f'session={SECRET}'),
            ('Authorization', f'Bearer {SECRET}'),
            ('X-Api-Token', SECRET),
        ],
        [RSS_FEED],
    )
    source, _ = make_source({token_url: feed_resp, ARTICLE_LOCATOR: article_response()})
    listing = source.list_candidates(token_url, None)
    assert isinstance(listing, CandidateListing)
    doc = source.fetch_document(ARTICLE_LOCATOR)
    assert isinstance(doc, FetchedDocument)
    assert SECRET not in caplog.text
    safe_names = [name.lower() for name, _ in doc.observation.safe_headers]
    for name in safe_names:
        assert 'cookie' not in name
        assert 'auth' not in name
        assert 'token' not in name
    for _, value in doc.observation.safe_headers:
        assert SECRET not in value


def test_constructor_rejects_bad_config():
    fetcher, _ = make_fetcher({})
    with pytest.raises(ValueError):
        RealFeedSource(fetcher, source_kind='web_page', feed_policy=FEED_POLICY, article_policy=ARTICLE_POLICY)
    with pytest.raises(ValueError):
        RealFeedSource('not_a_fetcher', source_kind='rss_feed', feed_policy=FEED_POLICY, article_policy=ARTICLE_POLICY)
    with pytest.raises(ValueError):
        RealFeedSource(fetcher, source_kind='rss_feed', feed_policy=FEED_POLICY, article_policy=ARTICLE_POLICY, max_candidates=0)


PNG = bytes.fromhex('89504e470d0a1a0a') + bytes(range(256)) * 4
HERO = 'https://img.example/hero.png'


def png_response():
    return response(200, [('Content-Type', 'image/png')], [PNG])


def make_media(routes, tmp_path, table=None, **kw):
    fetcher, transport = make_fetcher(routes, table)
    staging = kw.pop('staging_root', tmp_path / 'staging')
    media = RealMediaFetcher(
        fetcher,
        image_policy=IMAGE_POLICY,
        staging_root=staging,
        utc_now=lambda: NOW,
        correlation_id=lambda: 'media-test',
        **kw,
    )
    return media, transport, staging


def test_fetch_image_stages_file_and_builds_discovery_observation(no_network, tmp_path):
    media, transport, staging = make_media({HERO: png_response()}, tmp_path)
    result = media.fetch_image(HERO, role='hero', source_ref='src-1', article_ref='art-1')
    assert isinstance(result, StagedImage)
    sha = hashlib.sha256(PNG).hexdigest()
    assert result.sha256 == sha
    assert result.staged_path == staging / f'{sha}.png'
    assert result.staged_path.read_bytes() == PNG
    assert result.size_bytes == len(PNG)
    obs = result.observation
    assert isinstance(obs, DiscoveryObservation)
    assert obs.kind == MediaKind.IMAGE
    assert obs.fingerprint.value == sha
    assert obs.locator_validated is True
    assert obs.provenance.original_locator == HERO
    assert obs.provenance.relation == ProvenanceRelation.HERO_IMAGE
    assert obs.provenance.observed_at == '2026-10-21T08:30:00Z'
    assert obs.provenance.source_ref == 'src-1'
    assert obs.provenance.article_ref == 'art-1'
    assert obs.provenance.event_ref is None

    result2 = media.fetch_image(HERO, role='hero', source_ref='src-1', article_ref='art-1')
    assert isinstance(result2, StagedImage)
    assert result2.observation.discovery_id == obs.discovery_id
    assert result2.staged_path == result.staged_path


def test_fetch_image_rejects_oversized_body(no_network, tmp_path):
    fetcher, _ = make_fetcher({HERO: png_response()})
    staging = tmp_path / 'staging'
    media = RealMediaFetcher(fetcher, image_policy=policy({'image/png'}, max_body_bytes=100), staging_root=staging)
    result = media.fetch_image(HERO, role='hero', source_ref='src-1', article_ref='art-1')
    assert isinstance(result, ProblemDetail)
    assert result.code == 'BODY_TOO_LARGE'
    assert not any(staging.rglob('*'))


def test_fetch_image_rejects_address_outside_ssrf_policy(no_network, tmp_path):
    media1, transport1, staging1 = make_media({HERO: png_response()}, tmp_path / 's1', table={'img.example': ['10.0.0.7']})
    res1 = media1.fetch_image(HERO, role='hero', source_ref='src-1', article_ref='art-1')
    assert isinstance(res1, ProblemDetail)
    assert res1.code == 'UNSAFE_LOCATOR'
    assert transport1.requests == []

    routes_redir = {HERO: response(302, [('Location', 'http://internal.example/p.png')])}
    table_redir = {'img.example': [PUBLIC], 'internal.example': ['10.0.0.9']}
    media2, transport2, staging2 = make_media(routes_redir, tmp_path / 's2', table=table_redir)
    res2 = media2.fetch_image(HERO, role='hero', source_ref='src-1', article_ref='art-1')
    assert isinstance(res2, ProblemDetail)
    assert res2.code == 'UNSAFE_REDIRECT'
    assert len(transport2.requests) == 1
    assert not any(staging2.rglob('*'))


def test_fetch_image_rejects_disallowed_media_type(no_network, tmp_path):
    svg_resp = response(200, [('Content-Type', 'image/svg+xml')], [b'<svg></svg>'])
    media, _, staging = make_media({HERO: svg_resp}, tmp_path)
    res = media.fetch_image(HERO, role='hero', source_ref='src-1', article_ref='art-1')
    assert isinstance(res, ProblemDetail)
    assert res.code == 'MEDIA_TYPE_NOT_ALLOWED'
    assert not any(staging.rglob('*'))


def test_fetch_article_media_filters_dedupes_and_reports_problems(no_network, tmp_path):
    ENC = 'https://img.example/enc.jpg'
    GONE = 'https://img.example/gone.png'
    routes = {
        HERO: png_response(),
        ENC: response(200, [('Content-Type', 'image/jpeg')], [b'jpeg-data']),
        GONE: response(404),
    }
    media, transport, _ = make_media(routes, tmp_path)
    items = [
        {'locator': HERO, 'role': 'hero', 'media_kind': 'image'},
        {'locator': ENC, 'role': 'enclosure', 'media_kind': 'image'},
        {'locator': 'https://video.example/v.mp4', 'role': 'video', 'media_kind': 'video'},
        {'locator': HERO, 'role': 'hero', 'media_kind': 'image'},
        {'locator': GONE, 'role': 'thumbnail', 'media_kind': 'image'},
    ]
    batch = media.fetch_article_media(items, source_ref='s1', article_ref='a1')
    assert len(batch.staged) == 2
    assert len(batch.problems) == 1
    assert batch.problems[0].code == 'HTTP_STATUS_REJECTED'
    assert len(transport.requests) == 3


def test_fetch_article_media_caps_attempts(no_network, tmp_path):
    routes = {f'https://img.example/{i}.png': png_response() for i in range(3)}
    media, transport, _ = make_media(routes, tmp_path, max_images_per_article=2)
    items = [
        {'locator': f'https://img.example/{i}.png', 'role': 'image', 'media_kind': 'image'}
        for i in range(3)
    ]
    batch = media.fetch_article_media(items, source_ref='s1', article_ref='a1')
    assert len(batch.staged) == 2
    assert len(transport.requests) == 2


def test_staging_write_failure_and_bad_root(no_network, tmp_path):
    blocker = tmp_path / 'blocker'
    blocker.write_text('blocking file')
    media, _, _ = make_media({HERO: png_response()}, tmp_path, staging_root=blocker)
    res = media.fetch_image(HERO, role='hero', source_ref='s1', article_ref='a1')
    assert isinstance(res, ProblemDetail)
    assert res.code == 'STAGING_WRITE_FAILED'

    fetcher, _ = make_fetcher({})
    with pytest.raises(ValueError):
        RealMediaFetcher(fetcher, image_policy=IMAGE_POLICY, staging_root=pathlib.Path('relative'))


def imported(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result.add(node.module)
    return result


def test_no_src_prefix_in_adapter_modules():
    for name in ('real_http_transport.py', 'real_feed_source.py', 'real_media_fetch.py'):
        path = ADAPTERS / name
        text = path.read_text(encoding='utf-8')
        assert 'from src.' not in text
        for mod in imported(path):
            assert mod != 'src' and not mod.startswith('src.')


def test_transport_hygiene():
    path = ADAPTERS / 'real_http_transport.py'
    text = path.read_text(encoding='utf-8')
    assert not (imported(path) & {'os', 'urllib.request', 'requests', 'httpx', 'urllib3'})
    assert 'environ' not in text
    assert 'getproxies' not in text
    assert 'PROXY' not in text
    assert 'server_hostname=' in text
    assert "'GET'" in text
    assert "'POST'" not in text


def test_feed_and_media_never_open_network_themselves():
    feed_path = ADAPTERS / 'real_feed_source.py'
    media_path = ADAPTERS / 'real_media_fetch.py'
    forbidden = {'socket', 'http.client', 'urllib.request', 'requests', 'httpx', 'urllib3'}
    assert not (imported(feed_path) & forbidden)
    assert not (imported(media_path) & forbidden)
    feed_text = feed_path.read_text(encoding='utf-8')
    assert 'feedparser' in feed_text
    assert 'trafilatura' in feed_text
    assert 'SecureFetcher' in feed_text
    assert 'fetch_url' not in feed_text
    media_text = media_path.read_text(encoding='utf-8')
    assert 'SecureFetcher' in media_text
    assert 'DiscoveryObservation' in media_text
