"""Page image discovery for article HTML (ADAPT-A-FIX1; OI-CP7-11-Q1; stdlib and canonicalize_locator only).

page_images lists the images of one article page: meta og:image and twitter:image, JSON-LD image, then the
img and picture elements of the main region (first article, else first itemprop=articleBody, else first
main, else the whole page). One photo is kept once and a variant without overlay or watermark parameters
beats a decorated one. decode_html and page_images never raise.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urljoin, urlsplit

from source_ingestion.domain.locator import canonicalize_locator

MAX_PAGE_IMAGES = 12
MIN_DECLARED_SIDE = 200
_ROLE_HERO = 'hero'
_ROLE_INLINE = 'inline'
_RANK_BODY, _RANK_JSON_LD, _RANK_META = 0, 1, 2
_SKIP_EXTENSIONS = frozenset({'svg', 'svgz', 'gif', 'avif', 'ico', 'bmp', 'tif', 'tiff'})
_IMAGE_EXTENSIONS = frozenset({'jpg', 'jpeg', 'png', 'webp'})
_SOURCE_TYPES = frozenset({'', 'image/jpeg', 'image/png', 'image/webp'})
_LAZY_ATTRIBUTES = ('data-src', 'data-original', 'data-lazy-src', 'src')
_META_SUFFIXES = ('', ':url', ':secure_url', ':src')
_SMALL_QUERY_KEYS = frozenset({'w', 'width', 'h', 'height'})
_UNWANTED_NAME = re.compile(r'(?<![a-z])(?:logo|icon|avatar|sprite|pixel|spacer|badge|emoji|placeholder|blank)s?(?![a-z])|(?<![a-z0-9])1x1(?![a-z0-9])', re.IGNORECASE)
_DESCRIPTOR = re.compile(r'(\d+(?:\.\d+)?)([wx]),?', re.IGNORECASE)
_DECLARED = re.compile(r'\s*(\d+)\s*(?:px)?\s*', re.IGNORECASE)
_UUID_STEM = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
_HEX_STEM = re.compile(r'[0-9a-f]{32,}')
_CHARSET_HEADER = re.compile(r'charset\s*=\s*\W?([\w.:-]+)', re.IGNORECASE)
_CHARSET_META = re.compile(rb'<meta[^>]+charset\s*=\s*\W?([\w.:-]+)', re.IGNORECASE)


@dataclass
class _Candidate:
    locator: str
    role: str
    element: str
    rank: int
    order: int


@dataclass(frozen=True)
class PageImage:
    locator: str
    role: str
    element: str


def decode_html(body: bytes, headers: Iterable[tuple[str, str]]) -> str:
    """Text of an HTML body: charset from Content-Type, else from a meta tag, else UTF-8; never raises."""
    try:
        raw = bytes(body)
        label = ''
        for name, value in headers:
            if str(name).strip().lower() == 'content-type':
                found = _CHARSET_HEADER.search(str(value))
                label = found.group(1) if found else ''
                break
        if not label:
            found = _CHARSET_META.search(raw[:4096])
            label = found.group(1).decode('ascii', 'replace') if found else 'utf-8'
        try:
            return raw.decode(label, 'replace')
        except LookupError:
            return raw.decode('utf-8', 'replace')
    except Exception:
        return ''


def _extension(path: str) -> str:
    name = path.rsplit('/', 1)[-1]
    return name.rsplit('.', 1)[-1].lower() if '.' in name else ''


def _small_by_query(query: str) -> bool:
    for key, value in parse_qsl(query, keep_blank_values=True):
        key = key.lower()
        if key in _SMALL_QUERY_KEYS:
            numbers = [value]
        elif key == 'resize':
            numbers = value.split(',')
        else:
            continue
        if any(item.isascii() and item.isdigit() and 1 <= int(item) < MIN_DECLARED_SIDE for item in numbers):
            return True
    return False


def _acceptable(locator: str) -> bool:
    parts = urlsplit(locator)
    return not (
        _extension(parts.path) in _SKIP_EXTENSIONS
        or _UNWANTED_NAME.search(parts.path)
        or _small_by_query(parts.query)
    )


def _decorated(locator: str) -> bool:
    query = urlsplit(locator).query
    return any(key.lower().startswith(('overlay', 'watermark')) for key, _ in parse_qsl(query, keep_blank_values=True))


def _photo_key(locator: str) -> tuple[str, ...]:
    parts = urlsplit(locator)
    stem = parts.path.rsplit('/', 1)[-1].split('.', 1)[0].lower()
    host = (parts.hostname or '').lower()
    if _UUID_STEM.fullmatch(stem) or _HEX_STEM.fullmatch(stem):
        return (parts.scheme, host, stem)
    if _extension(parts.path) in _IMAGE_EXTENSIONS:
        return (parts.scheme, host, parts.path)
    return (locator,)


def _resolve(base: str, raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        locator = canonicalize_locator(urljoin(base, raw.strip()))
    except ValueError:
        return None
    return locator if _acceptable(locator) else None


def _srcset_candidates(value: str) -> list[tuple[str, str, float]]:
    found: list[tuple[str, str, float]] = []
    tokens = value.split()
    index = 0
    while index < len(tokens):
        url = tokens[index]
        index += 1
        kind, weight = '', 0.0
        if url.endswith(','):
            url = url.rstrip(',')
        elif index < len(tokens):
            match = _DESCRIPTOR.fullmatch(tokens[index])
            if match:
                index += 1
                kind, weight = match.group(2).lower(), float(match.group(1))
        if url:
            found.append((url, kind, weight))
    return found


def _pick_srcset(candidates: list[tuple[str, str, float]]) -> str | None:
    for kind in ('w', 'x'):
        sized = [item for item in candidates if item[1] == kind]
        if sized:
            return max(sized, key=lambda item: item[2])[0]
    return candidates[0][0] if candidates else None


def _declared_small(attrs: Mapping[str, str]) -> bool:
    for name in ('width', 'height'):
        match = _DECLARED.fullmatch(attrs.get(name, ''))
        if match and int(match.group(1)) < MIN_DECLARED_SIDE:
            return True
    return False


def _body_url(item: _BodyItem) -> str | None:
    """One URL per img or picture: srcset (largest w, then x, then first), else the lazy attributes."""
    candidates: list[tuple[str, str, float]] = []
    for source in item.sources:
        if source.get('type', '').strip().lower() in _SOURCE_TYPES:
            for name in ('srcset', 'data-srcset'):
                candidates.extend(_srcset_candidates(source.get(name, '')))
    for name in ('srcset', 'data-srcset'):
        candidates.extend(_srcset_candidates(item.img.get(name, '')))
    picked = _pick_srcset(candidates)
    if picked:
        return picked
    for name in _LAZY_ATTRIBUTES:
        value = item.img.get(name, '').strip()
        if value:
            return value
    return None


@dataclass
class _BodyItem:
    element: str
    sources: list
    img: dict
    in_noscript: bool
    kinds: list


class _PageScan(HTMLParser):
    """One pass: meta tags, base href, JSON-LD scripts and the img and picture elements per region."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metas: list[dict[str, str]] = []
        self.scripts: list[str] = []
        self.base_href = ''
        self._items: dict[str, list[_BodyItem]] = {'article': [], 'articlebody': [], 'main': [], 'page': []}
        self._regions: dict[str, list] = {}
        self._script: list[str] | None = None
        self._noscript = 0
        self._picture: _BodyItem | None = None

    @staticmethod
    def _kind(tag: str, values: dict[str, str]) -> str | None:
        if tag in ('article', 'main'):
            return tag
        return 'articlebody' if 'articlebody' in values.get('itemprop', '').lower() else None

    def _new_item(self, element: str, img: dict[str, str]) -> _BodyItem:
        kinds = ['page'] + [kind for kind, region in self._regions.items() if region[1] > 0]
        return _BodyItem(element, [], img, self._noscript > 0, kinds)

    def _store(self, item: _BodyItem) -> None:
        for kind in item.kinds:
            self._items[kind].append(item)

    def handle_starttag(self, tag, attrs):
        values = {name.lower(): value or '' for name, value in attrs}
        for region in self._regions.values():
            if region[1] > 0 and region[0] == tag:
                region[1] += 1
        kind = self._kind(tag, values)
        if kind and kind not in self._regions:
            self._regions[kind] = [tag, 1]
        if tag == 'meta':
            self.metas.append(values)
        elif tag == 'base':
            self.base_href = self.base_href or values.get('href', '')
        elif tag == 'script' and 'ld+json' in values.get('type', '').lower():
            self._script = []
        elif tag == 'noscript':
            self._noscript += 1
        elif tag == 'picture' and self._picture is None:
            self._picture = self._new_item('picture', {})
        elif tag == 'source' and self._picture is not None:
            self._picture.sources.append(values)
        elif tag == 'img':
            if self._picture is None:
                self._store(self._new_item('img', values))
            elif not self._picture.img:
                self._picture.img = values

    def handle_endtag(self, tag):
        for region in self._regions.values():
            if region[1] > 0 and region[0] == tag:
                region[1] -= 1
        if tag == 'script' and self._script is not None:
            self.scripts.append(''.join(self._script))
            self._script = None
        elif tag == 'noscript':
            self._noscript = max(0, self._noscript - 1)
        elif tag == 'picture' and self._picture is not None:
            self._store(self._picture)
            self._picture = None

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)

    def finish(self) -> None:
        self.close()
        if self._picture is not None:
            self._store(self._picture)
            self._picture = None

    def body_items(self) -> list[_BodyItem]:
        for kind in ('article', 'articlebody', 'main'):
            if kind in self._regions:
                return self._items[kind]
        return self._items['page']


def _ld_values(value: object, found: list[str]) -> None:
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, list):
        for item in value:
            _ld_values(item, found)
    elif isinstance(value, dict):
        for key in ('url', 'contentUrl'):
            if isinstance(value.get(key), str):
                found.append(value[key])


def _ld_nodes(node: object, found: list[str], depth: int = 0) -> None:
    """Collect the image values of JSON-LD nodes (also inside @graph), skipping Person and Organization nodes."""
    if depth > 6:
        return
    if isinstance(node, list):
        for item in node:
            _ld_nodes(item, found, depth + 1)
    elif isinstance(node, dict):
        _ld_nodes(node.get('@graph'), found, depth + 1)
        kinds = node.get('@type')
        kinds = kinds if isinstance(kinds, list) else [kinds]
        names = [str(kind).lower().rsplit('/', 1)[-1].rsplit(':', 1)[-1] for kind in kinds if kind]
        if not any(name == 'person' or name.endswith('organization') for name in names):
            _ld_values(node.get('image'), found)


def _strength(candidate: _Candidate) -> tuple[bool, int, int]:
    return (_decorated(candidate.locator), candidate.rank, candidate.order)


def page_images(html: str, base: str) -> tuple[PageImage, ...]:
    """Article page images in priority order, at most MAX_PAGE_IMAGES; never raises."""
    try:
        return _page_images(html, base)
    except Exception:
        return ()


def _page_images(html: str, base: str) -> tuple[PageImage, ...]:
    scan = _PageScan()
    scan.feed(html)
    scan.finish()
    if scan.base_href.strip():
        base = urljoin(base, scan.base_href.strip())
    entries: list[tuple[object, str, str, int, bool]] = []
    for prefix in ('og:image', 'twitter:image'):
        names = {prefix + suffix for suffix in _META_SUFFIXES}
        for meta in scan.metas:
            for field in ('property', 'name'):
                key = meta.get(field, '').strip().lower()
                if key in names:
                    entries.append((meta.get('content', ''), _ROLE_HERO, 'meta:' + key, _RANK_META, False))
    for text in scan.scripts:
        try:
            data = json.loads(text.strip())
        except (ValueError, RecursionError):
            continue
        found: list[str] = []
        _ld_nodes(data, found)
        entries.extend((raw, _ROLE_HERO, 'json-ld', _RANK_JSON_LD, False) for raw in found)
    for item in scan.body_items():
        if not _declared_small(item.img):
            entries.append((_body_url(item), _ROLE_INLINE, item.element, _RANK_BODY, item.in_noscript))
    merged: dict[str, _Candidate] = {}
    for raw, role, element, rank, extension_only in entries:
        locator = _resolve(base, raw)
        if locator is None or (extension_only and _extension(urlsplit(locator).path) not in _IMAGE_EXTENSIONS):
            continue
        known = merged.get(locator)
        if known is None:
            merged[locator] = _Candidate(locator, role, element, rank, len(merged))
        else:
            known.rank = min(known.rank, rank)
    best: dict[tuple[str, ...], _Candidate] = {}
    for candidate in merged.values():
        key = _photo_key(candidate.locator)
        if key not in best or _strength(candidate) < _strength(best[key]):
            best[key] = candidate
    kept = sorted(best.values(), key=lambda candidate: candidate.order)[:MAX_PAGE_IMAGES]
    return tuple(PageImage(item.locator, item.role, item.element) for item in kept)
