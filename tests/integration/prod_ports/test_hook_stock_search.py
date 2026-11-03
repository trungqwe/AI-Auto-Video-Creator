"""HOOK-STOCK: tìm video Pixabay và SFX, nhạc Freesound qua transport giả (không mạng); chỉ giữ giấy phép dùng thương mại được, khoá không lọt ra ngoài.

coveredIds: FR-HOOK-004, FR-AUD-007
"""
from __future__ import annotations

import contextlib
import hashlib
import json
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import pytest

from controlplane.infrastructure.production_ports.stock_media import (
    FREESOUND_SEARCH_API,
    LICENSE_CC0,
    LICENSE_CC_BY_4,
    LICENSE_PIXABAY,
    PIXABAY_VIDEO_API,
    FreesoundSearch,
    PixabayVideoSearch,
    StockSearchError,
    download_stock_file,
    license_cleared,
)

KEY = 'Kx9canaryStockKey0123456789'


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    final_url: str


class FakeTransport:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def fetch(self, url, *, max_bytes, timeout_seconds):
        self.calls.append((url, max_bytes))
        parts = urlsplit(url)
        handler = self.routes.get(parts.scheme + '://' + parts.netloc + parts.path)
        if handler is None:
            raise OSError('no route for ' + url)
        status, body = handler(parse_qs(parts.query))
        return Response(status, body, url)


class Keys:
    def __init__(self, value=KEY):
        self.value = value
        self.asked = []

    @contextlib.contextmanager
    def acquire(self, provider):
        self.asked.append(provider)
        if self.value is None:
            raise LookupError('missing ' + provider)
        yield self.value


def pixabay_hit(hit_id, duration, url='https://cdn.pixabay.com/video/2024/01/01/{id}_medium.mp4', tags='police, night, city'):
    return {
        'id': hit_id, 'pageURL': f'https://pixabay.com/videos/x-{hit_id}/', 'tags': tags, 'duration': duration, 'user': 'maker',
        'videos': {'medium': {'url': url.format(id=hit_id), 'width': 1280, 'height': 720, 'size': 100}, 'tiny': {'url': '', 'width': 0, 'height': 0}}}


def freesound_result(sound_id, license_url, duration=1.5, preview='https://cdn.freesound.org/previews/1/{id}_hq.mp3', username='rec'):
    return {
        'id': sound_id, 'name': f'Whoosh {sound_id}', 'tags': ['whoosh', 'transition', 'Whoosh'], 'description': 'fast  air swish',
        'license': license_url, 'username': username, 'duration': duration, 'url': f'https://freesound.org/people/rec/sounds/{sound_id}/',
        'previews': {'preview-hq-mp3': preview.format(id=sound_id)}}


def json_route(payload, status=200):
    return lambda query: (status, json.dumps(payload).encode('utf-8'))


def test_pixabay_search_sends_key_and_safesearch_and_keeps_clips_in_the_window() -> None:
    hits = [pixabay_hit(11, 8), pixabay_hit(12, 2), pixabay_hit(13, 30, url='https://evil.example/{id}.mp4'), pixabay_hit(14, 61)]
    transport = FakeTransport({PIXABAY_VIDEO_API: json_route({'total': 4, 'hits': hits})})
    items = PixabayVideoSearch(transport=transport, keys=Keys()).search('  police   night ', min_duration_s=3, max_duration_s=60)
    assert [item.provider_id for item in items] == ['11']
    query = parse_qs(urlsplit(transport.calls[0][0]).query)
    assert query['key'] == [KEY] and query['q'] == ['police night'] and query['safesearch'] == ['true']
    item = items[0]
    assert item.hook_id == 'pxb-11' and item.media_kind == 'clip' and item.license == LICENSE_PIXABAY
    assert item.download_url == 'https://cdn.pixabay.com/video/2024/01/01/11_medium.mp4' and (item.width, item.height, item.duration_ms) == (1280, 720, 8000)
    assert item.tags == ('police', 'night', 'city') and item.page_url == 'https://pixabay.com/videos/x-11/'
    assert 'maker' in item.attribution and 'Pixabay' in item.attribution
    assert KEY not in repr(item) and KEY not in repr(items)


def test_freesound_sfx_keeps_only_cc0_and_cc_by_with_author() -> None:
    results = [
        freesound_result(1, 'http://creativecommons.org/publicdomain/zero/1.0/'),
        freesound_result(2, 'https://creativecommons.org/licenses/by/4.0/'),
        freesound_result(3, 'https://creativecommons.org/licenses/by-nc/4.0/'),
        freesound_result(4, 'http://creativecommons.org/licenses/sampling+/1.0/'),
        freesound_result(5, 'https://creativecommons.org/licenses/by/4.0/', username=''),
        freesound_result(6, 'http://creativecommons.org/publicdomain/zero/1.0/', preview='http://cdn.freesound.org/previews/1/{id}_hq.mp3'),
        freesound_result(7, 'http://creativecommons.org/publicdomain/zero/1.0/', duration=9.0),
    ]
    transport = FakeTransport({FREESOUND_SEARCH_API: json_route({'count': 7, 'results': results})})
    items = FreesoundSearch(transport=transport, keys=Keys()).search_sfx('whoosh', max_duration_s=5)
    assert [(item.provider_id, item.license) for item in items] == [('1', LICENSE_CC0), ('2', LICENSE_CC_BY_4)]
    query = parse_qs(urlsplit(transport.calls[0][0]).query)
    assert query['token'] == [KEY] and query['query'] == ['whoosh']
    assert 'license:("Creative Commons 0" OR "Attribution")' in query['filter'][0] and 'duration:[0.3 TO 5]' in query['filter'][0]
    cc_by = items[1]
    assert cc_by.hook_id == 'fs-2' and cc_by.media_kind == 'audio' and cc_by.author == 'rec'
    assert 'rec' in cc_by.attribution and LICENSE_CC_BY_4 in cc_by.attribution and cc_by.tags == ('whoosh', 'transition')
    assert cc_by.description == 'fast air swish' and cc_by.duration_ms == 1500


def test_freesound_music_uses_the_long_duration_window() -> None:
    transport = FakeTransport({FREESOUND_SEARCH_API: json_route({'results': [
        freesound_result(21, 'https://creativecommons.org/licenses/by/4.0/', duration=150.0),
        freesound_result(22, 'https://creativecommons.org/licenses/by/4.0/', duration=20.0)]})})
    items = FreesoundSearch(transport=transport, keys=Keys()).search_music('calm ambient', min_duration_s=60)
    assert [item.provider_id for item in items] == ['21']
    assert 'duration:[60 TO 600]' in parse_qs(urlsplit(transport.calls[0][0]).query)['filter'][0]


@pytest.mark.parametrize('status, body, code', [
    (401, b'{"detail": "bad key"}', 'stock_http_status'),
    (200, b'not json', 'stock_response_invalid'),
    (200, b'{"hits": 3}', 'stock_response_invalid'),
])
def test_errors_carry_a_code_and_never_the_key(status, body, code) -> None:
    transport = FakeTransport({PIXABAY_VIDEO_API: lambda query: (status, body)})
    with pytest.raises(StockSearchError) as raised:
        PixabayVideoSearch(transport=transport, keys=Keys()).search('city')
    assert raised.value.code == code and KEY not in str(raised.value) and KEY not in repr(raised.value)
    assert raised.value.__cause__ is None or KEY not in str(raised.value.__cause__)


def test_transport_failure_hides_the_request_url() -> None:
    transport = FakeTransport({})
    with pytest.raises(StockSearchError) as raised:
        FreesoundSearch(transport=transport, keys=Keys()).search_sfx('boom')
    assert raised.value.code == 'stock_fetch_failed' and KEY not in str(raised.value)
    assert raised.value.__suppress_context__ is True


def test_missing_key_stops_before_any_request() -> None:
    transport = FakeTransport({PIXABAY_VIDEO_API: json_route({'hits': []})})
    with pytest.raises(StockSearchError) as raised:
        PixabayVideoSearch(transport=transport, keys=Keys(None)).search('city')
    assert raised.value.code == 'stock_key_missing' and transport.calls == []


def test_download_takes_only_the_cdn_url_and_pins_sha256() -> None:
    clip = b'\x00\x00\x00\x18ftypmp42fake-clip'
    transport = FakeTransport({
        PIXABAY_VIDEO_API: json_route({'hits': [pixabay_hit(31, 10)]}),
        'https://cdn.pixabay.com/video/2024/01/01/31_medium.mp4': lambda query: (200, clip)})
    item = PixabayVideoSearch(transport=transport, keys=Keys()).search('city')[0]
    assert download_stock_file(transport, item, max_bytes=1024) == (clip, hashlib.sha256(clip).hexdigest())
    with pytest.raises(StockSearchError) as raised:
        download_stock_file(transport, item, max_bytes=4)
    assert raised.value.code == 'stock_download_too_large'
    forged = type(item)(**{**item.__dict__, 'download_url': 'https://cdn.pixabay.com.evil.example/x.mp4'})
    with pytest.raises(StockSearchError) as raised:
        download_stock_file(transport, forged, max_bytes=1024)
    assert raised.value.code == 'stock_download_not_allowed'


def test_license_rule_needs_attribution_for_cc_by_only() -> None:
    assert license_cleared(LICENSE_PIXABAY, '', '') and license_cleared(LICENSE_CC0, '', '')
    assert license_cleared(LICENSE_CC_BY_4, 'rec', 'Whoosh by rec') and not license_cleared(LICENSE_CC_BY_4, 'rec', '')
    assert not license_cleared('CC-BY-NC-4.0', 'rec', 'x') and not license_cleared(None, 'rec', 'x')
