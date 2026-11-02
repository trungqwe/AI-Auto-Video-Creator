"""HOOK-STOCK: search clients of the free stock libraries chosen by the user (D1 Pixabay video, D2 Freesound SFX and music, 02/11/2026).

Both clients turn one search into StockItem values that carry everything the hook and music libraries need for FR-HOOK-004 and
FR-AUD-007: provider id, download URL, page URL, duration, size, tags, description, author, a canonical license and the
attribution text. Only licenses that allow commercial use in a video are kept: Pixabay Content License, CC0 and CC BY 3.0/4.0
(CC BY needs author and attribution); NC, ND and Sampling+ are dropped. Download URLs must be https on the CDN host of the
provider. The HTTPS transport is injected (same shape as the music transport: fetch(url, *, max_bytes, timeout_seconds) ->
response with status and body); this module opens no socket. The API key comes from an injected key source
(acquire(provider) context manager, StockKeyCredentials in production) and is put only into the request URL: no exception,
repr or returned value holds it or the request URL.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit

PROVIDER_PIXABAY = 'pixabay'
PROVIDER_FREESOUND = 'freesound'
PIXABAY_VIDEO_API = 'https://pixabay.com/api/videos/'
FREESOUND_SEARCH_API = 'https://freesound.org/apiv2/search/text/'
DOWNLOAD_HOSTS = {PROVIDER_PIXABAY: frozenset({'cdn.pixabay.com'}), PROVIDER_FREESOUND: frozenset({'cdn.freesound.org'})}
LICENSE_PIXABAY = 'Pixabay Content License'
LICENSE_CC0 = 'CC0-1.0'
LICENSE_CC_BY_3 = 'CC-BY-3.0'
LICENSE_CC_BY_4 = 'CC-BY-4.0'
CLEARED_LICENSES = frozenset({LICENSE_PIXABAY, LICENSE_CC0, LICENSE_CC_BY_3, LICENSE_CC_BY_4})
ATTRIBUTION_REQUIRED = frozenset({LICENSE_CC_BY_3, LICENSE_CC_BY_4})
_FREESOUND_LICENSES = {
    'creativecommons.org/publicdomain/zero/1.0': LICENSE_CC0,
    'creativecommons.org/licenses/by/3.0': LICENSE_CC_BY_3,
    'creativecommons.org/licenses/by/4.0': LICENSE_CC_BY_4,
}
FREESOUND_LICENSE_FILTER = 'license:("Creative Commons 0" OR "Attribution")'
FREESOUND_FIELDS = 'id,name,tags,description,license,username,duration,previews,url'
FREESOUND_PREVIEW = 'preview-hq-mp3'
PIXABAY_RENDITIONS = ('medium', 'large', 'small')
MAX_JSON_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_QUERY_CHARS = 100
MAX_TAGS = 20
MAX_DESCRIPTION_CHARS = 500
MEDIA_KIND_CLIP = 'clip'
MEDIA_KIND_AUDIO = 'audio'

ERR_KEY_MISSING = 'stock_key_missing'
ERR_FETCH_FAILED = 'stock_fetch_failed'
ERR_HTTP_STATUS = 'stock_http_status'
ERR_RESPONSE_INVALID = 'stock_response_invalid'
ERR_QUERY_INVALID = 'stock_query_invalid'
ERR_DOWNLOAD_NOT_ALLOWED = 'stock_download_not_allowed'
ERR_DOWNLOAD_TOO_LARGE = 'stock_download_too_large'


class StockSearchError(Exception):
    """Fixed code and a detail without key or URL."""

    def __init__(self, code: str, detail: str = '') -> None:
        super().__init__(f'{code}: {detail}' if detail else code)
        self.code = code
        self.detail = detail


class StockTransport(Protocol):
    def fetch(self, url: str, *, max_bytes: int, timeout_seconds: float) -> Any:
        ...


class StockKeySource(Protocol):
    def acquire(self, provider: str) -> Any:
        ...


@dataclass(frozen=True)
class StockItem:
    provider: str
    provider_id: str
    media_kind: str
    download_url: str
    page_url: str
    duration_ms: int
    width: int
    height: int
    tags: tuple[str, ...]
    description: str
    author: str
    license: str
    attribution: str
    query: str

    @property
    def hook_id(self) -> str:
        return ('pxb-' if self.provider == PROVIDER_PIXABAY else 'fs-') + self.provider_id


def license_cleared(license_code: object, author: object, attribution: object) -> bool:
    """Commercial use in a video allowed; CC BY also needs a named author and an attribution text."""
    if license_code not in CLEARED_LICENSES:
        return False
    if license_code in ATTRIBUTION_REQUIRED:
        return isinstance(author, str) and bool(author.strip()) and isinstance(attribution, str) and bool(attribution.strip())
    return True


def freesound_license(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    for prefix in ('https://', 'http://'):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return _FREESOUND_LICENSES.get(text.rstrip('/'))


def download_allowed(provider: str, url: object) -> bool:
    try:
        parts = urlsplit(url)
        host, port = parts.hostname, parts.port
    except (ValueError, AttributeError, TypeError):
        return False
    return parts.scheme == 'https' and host in DOWNLOAD_HOSTS.get(provider, ()) and not parts.username and not parts.password and port in (None, 443)


def _query(query: object) -> str:
    if not isinstance(query, str) or not query.strip():
        raise StockSearchError(ERR_QUERY_INVALID, 'query must be non-empty text')
    return ' '.join(query.split())[:MAX_QUERY_CHARS]


def _tags(raw: object) -> tuple[str, ...]:
    items = raw.split(',') if isinstance(raw, str) else raw if isinstance(raw, list) else []
    seen: list[str] = []
    for item in items:
        if isinstance(item, str):
            tag = ' '.join(item.lower().split())
            if tag and tag not in seen:
                seen.append(tag)
    return tuple(seen[:MAX_TAGS])


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return int(round(value))
    return None


def _duration_ms(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        return None
    return int(round(value * 1000))


def _get_json(transport: StockTransport, url: str, timeout_seconds: float) -> Mapping:
    try:
        response = transport.fetch(url, max_bytes=MAX_JSON_BYTES, timeout_seconds=timeout_seconds)
    except Exception:
        raise StockSearchError(ERR_FETCH_FAILED, 'transport') from None
    status = getattr(response, 'status', None)
    if status != 200:
        raise StockSearchError(ERR_HTTP_STATUS, str(status) if isinstance(status, int) else 'unknown')
    body = getattr(response, 'body', None)
    if not isinstance(body, bytes) or not body or len(body) > MAX_JSON_BYTES:
        raise StockSearchError(ERR_RESPONSE_INVALID, 'body')
    try:
        data = json.loads(body.decode('utf-8'))
    except ValueError:
        raise StockSearchError(ERR_RESPONSE_INVALID, 'json') from None
    if not isinstance(data, Mapping):
        raise StockSearchError(ERR_RESPONSE_INVALID, 'object')
    return data


def _with_key(keys: StockKeySource, provider: str, build_url) -> str:
    try:
        with keys.acquire(provider) as key:
            if not isinstance(key, str) or not key:
                raise StockSearchError(ERR_KEY_MISSING, provider)
            return build_url(key)
    except StockSearchError:
        raise
    except Exception:
        raise StockSearchError(ERR_KEY_MISSING, provider) from None


class PixabayVideoSearch:
    """Pixabay video API (D1): safesearch on, one rendition per hit (medium, else large, else small), hits outside the duration window dropped."""

    def __init__(self, *, transport: StockTransport, keys: StockKeySource, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._transport = transport
        self._keys = keys
        self._timeout = timeout_seconds

    def __repr__(self) -> str:
        return 'PixabayVideoSearch()'

    def search(self, query: str, *, min_duration_s: int = 3, max_duration_s: int = 60, per_page: int = 20) -> tuple[StockItem, ...]:
        text = _query(query)
        params = {'q': text, 'safesearch': 'true', 'video_type': 'film', 'per_page': max(3, min(int(per_page), 200)), 'order': 'popular'}
        url = _with_key(self._keys, PROVIDER_PIXABAY, lambda key: PIXABAY_VIDEO_API + '?' + urlencode({'key': key, **params}))
        hits = _get_json(self._transport, url, self._timeout).get('hits')
        if not isinstance(hits, list):
            raise StockSearchError(ERR_RESPONSE_INVALID, 'hits')
        items = []
        for hit in hits:
            item = self._item(hit, text, min_duration_s, max_duration_s)
            if item is not None:
                items.append(item)
        return tuple(items)

    @staticmethod
    def _item(hit: object, query: str, min_s: int, max_s: int) -> StockItem | None:
        if not isinstance(hit, Mapping):
            return None
        hit_id, duration = _int(hit.get('id')), _int(hit.get('duration'))
        if hit_id is None or hit_id <= 0 or duration is None or not (min_s <= duration <= max_s):
            return None
        videos = hit.get('videos') if isinstance(hit.get('videos'), Mapping) else {}
        rendition = next((videos[name] for name in PIXABAY_RENDITIONS if isinstance(videos.get(name), Mapping) and download_allowed(PROVIDER_PIXABAY, videos[name].get('url'))), None)
        if rendition is None:
            return None
        width, height = _int(rendition.get('width')), _int(rendition.get('height'))
        user = hit.get('user') if isinstance(hit.get('user'), str) else ''
        page = hit.get('pageURL') if isinstance(hit.get('pageURL'), str) and hit['pageURL'].startswith('https://pixabay.com/') else ''
        if not width or not height or width <= 0 or height <= 0 or not page:
            return None
        tags = _tags(hit.get('tags'))
        attribution = f'Video by {user.strip() or "Pixabay user"} from Pixabay ({page})'
        return StockItem(
            provider=PROVIDER_PIXABAY, provider_id=str(hit_id), media_kind=MEDIA_KIND_CLIP, download_url=rendition['url'], page_url=page,
            duration_ms=duration * 1000, width=width, height=height, tags=tags, description=', '.join(tags)[:MAX_DESCRIPTION_CHARS],
            author=user.strip(), license=LICENSE_PIXABAY, attribution=attribution, query=query)


class FreesoundSearch:
    """Freesound text search (D2): CC0 and CC BY only (filter on the server, checked again here), HQ mp3 preview on cdn.freesound.org as the download."""

    def __init__(self, *, transport: StockTransport, keys: StockKeySource, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._transport = transport
        self._keys = keys
        self._timeout = timeout_seconds

    def __repr__(self) -> str:
        return 'FreesoundSearch()'

    def search_sfx(self, query: str, *, max_duration_s: float = 5.0, page_size: int = 20) -> tuple[StockItem, ...]:
        return self._search(query, 0.3, max_duration_s, page_size)

    def search_music(self, query: str, *, min_duration_s: float = 60.0, max_duration_s: float = 600.0, page_size: int = 20) -> tuple[StockItem, ...]:
        return self._search(query, min_duration_s, max_duration_s, page_size)

    def _search(self, query: str, low: float, high: float, page_size: int) -> tuple[StockItem, ...]:
        text = _query(query)
        params = {
            'query': text, 'filter': f'duration:[{low:g} TO {high:g}] {FREESOUND_LICENSE_FILTER}', 'fields': FREESOUND_FIELDS,
            'page_size': max(1, min(int(page_size), 150)), 'sort': 'score'}
        url = _with_key(self._keys, PROVIDER_FREESOUND, lambda key: FREESOUND_SEARCH_API + '?' + urlencode({**params, 'token': key}))
        results = _get_json(self._transport, url, self._timeout).get('results')
        if not isinstance(results, list):
            raise StockSearchError(ERR_RESPONSE_INVALID, 'results')
        items = []
        for result in results:
            item = self._item(result, text, low, high)
            if item is not None:
                items.append(item)
        return tuple(items)

    @staticmethod
    def _item(result: object, query: str, low: float, high: float) -> StockItem | None:
        if not isinstance(result, Mapping):
            return None
        sound_id, duration_ms = _int(result.get('id')), _duration_ms(result.get('duration'))
        if sound_id is None or sound_id <= 0 or duration_ms is None or not (low * 1000 <= duration_ms <= high * 1000):
            return None
        license_code = freesound_license(result.get('license'))
        previews = result.get('previews') if isinstance(result.get('previews'), Mapping) else {}
        download = previews.get(FREESOUND_PREVIEW)
        name = ' '.join(str(result.get('name') or '').split())
        author = ' '.join(str(result.get('username') or '').split())
        page = result.get('url') if isinstance(result.get('url'), str) and result['url'].startswith('https://freesound.org/') else ''
        if license_code is None or not download_allowed(PROVIDER_FREESOUND, download) or not name or not page:
            return None
        attribution = f'"{name}" by {author} ({page}) licensed under {license_code}' if author else ''
        if not license_cleared(license_code, author, attribution):
            return None
        description = ' '.join(str(result.get('description') or '').split())[:MAX_DESCRIPTION_CHARS]
        return StockItem(
            provider=PROVIDER_FREESOUND, provider_id=str(sound_id), media_kind=MEDIA_KIND_AUDIO, download_url=download, page_url=page,
            duration_ms=duration_ms, width=0, height=0, tags=_tags(result.get('tags')), description=description or name, author=author,
            license=license_code, attribution=attribution or f'"{name}" ({page}) {license_code}', query=query)


def download_stock_file(transport: StockTransport, item: StockItem, *, max_bytes: int, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> tuple[bytes, str]:
    """GET the exact download URL of an item (https, CDN host of its provider); returns the bytes and their sha256."""
    if not isinstance(item, StockItem) or not download_allowed(item.provider, item.download_url):
        raise StockSearchError(ERR_DOWNLOAD_NOT_ALLOWED, 'host')
    try:
        response = transport.fetch(item.download_url, max_bytes=max_bytes, timeout_seconds=timeout_seconds)
    except Exception:
        raise StockSearchError(ERR_FETCH_FAILED, 'download') from None
    status = getattr(response, 'status', None)
    if status != 200:
        raise StockSearchError(ERR_HTTP_STATUS, str(status) if isinstance(status, int) else 'unknown')
    body = getattr(response, 'body', None)
    if not isinstance(body, bytes) or not body:
        raise StockSearchError(ERR_RESPONSE_INVALID, 'download_body')
    if len(body) > max_bytes:
        raise StockSearchError(ERR_DOWNLOAD_TOO_LARGE, str(max_bytes))
    return body, hashlib.sha256(body).hexdigest()


__all__ = [
    'CLEARED_LICENSES', 'DOWNLOAD_HOSTS', 'FREESOUND_SEARCH_API', 'FreesoundSearch', 'LICENSE_CC0', 'LICENSE_CC_BY_3', 'LICENSE_CC_BY_4',
    'LICENSE_PIXABAY', 'PIXABAY_VIDEO_API', 'PixabayVideoSearch', 'StockItem', 'StockSearchError', 'download_allowed', 'download_stock_file',
    'freesound_license', 'license_cleared',
]
