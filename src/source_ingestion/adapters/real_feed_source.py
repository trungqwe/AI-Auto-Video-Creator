"""Real RSS/Atom feed adapter (ADAPT-A; A-12, A-13).

Feed and article bytes are loaded only through SecureFetcher. feedparser.parse and
trafilatura.extract run on those bytes alone, so neither library opens a socket or a file.
Raw bytes and both library versions travel in technical_fields because extraction output can
change between releases. Unsupported operations return CapabilityUnavailable; fetch and parse
failures are returned as ProblemDetail and never raised.
"""
from __future__ import annotations

import io
import json
import logging
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from urllib.parse import urljoin

import feedparser
import trafilatura

from controlplane.domain.common.contracts import ProblemDetail
from source_ingestion.adapters.secure_fetch import PROBLEM_TYPE_PREFIX, FetchPolicy, SecureFetcher
from source_ingestion.domain.locator import canonicalize_locator
from source_ingestion.ports.source_adapter import (
    AdapterDescriptor,
    AdapterOperation,
    CandidateListing,
    CapabilityUnavailable,
    ExtractedCandidate,
    FetchedDocument,
    ProbeResult,
)

_LOG = logging.getLogger(__name__)

ADAPTER_VERSION = '1.0.0'
SOURCE_KINDS = frozenset({'rss_feed', 'atom_feed'})
FEEDPARSER_VERSION = feedparser.__version__
TRAFILATURA_VERSION = trafilatura.__version__
EXTRACTOR_VERSION = f'feedparser-{FEEDPARSER_VERSION}+trafilatura-{TRAFILATURA_VERSION}'
WARNING_FEED_MALFORMED = 'feed_malformed'
WARNING_FEED_KIND_MISMATCH = 'feed_kind_mismatch'
WARNING_NO_CONTENT = 'trafilatura_no_content'
_FEED_VERSION_PREFIX = {'rss_feed': 'rss', 'atom_feed': 'atom'}


def _new_correlation_id() -> str:
    return 'feed-' + uuid.uuid4().hex


def _problem(code: str, detail: str, category: str, retryable: bool, correlation_id: str) -> ProblemDetail:
    """Fixed-text problem; the detail never echoes locators, headers or exception text."""
    _LOG.info('feed adapter problem code=%s', code)
    return ProblemDetail.create(
        type=PROBLEM_TYPE_PREFIX + code.lower(),
        title=code,
        detail=detail,
        instance=f'urn:source-ingestion:feed:{correlation_id}',
        code=code,
        category=category,
        retryable=retryable,
        correlation_id=correlation_id,
    )


def _http_locator(base: str, raw: object) -> str | None:
    """Absolute canonical http(s) locator, or None when the value is empty or not acceptable."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return canonicalize_locator(urljoin(base, raw.strip()))
    except ValueError:
        return None


def _append_media(media: list[dict[str, object]], locator: str | None, role: str, element: str) -> None:
    if locator is None or any(item['locator'] == locator and item['role'] == role for item in media):
        return
    media.append({
        'locator': locator,
        'role': role,
        'media_kind': 'image',
        'context': {'element': element, 'position': len(media)},
    })


def _feed_media(entry: Mapping[str, object], base: str) -> list[dict[str, object]]:
    """Images attached to one feed entry: enclosure, media:content and media:thumbnail."""
    media: list[dict[str, object]] = []
    for item in entry.get('enclosures') or ():
        if str(item.get('type', '')).lower().startswith('image/'):
            _append_media(media, _http_locator(base, item.get('href')), 'enclosure', 'enclosure')
    for item in entry.get('media_content') or ():
        if item.get('medium') == 'image' or str(item.get('type', '')).lower().startswith('image/'):
            _append_media(media, _http_locator(base, item.get('url')), 'media_content', 'media:content')
    for item in entry.get('media_thumbnail') or ():
        _append_media(media, _http_locator(base, item.get('url')), 'media_thumbnail', 'media:thumbnail')
    return media


def _entry_published(entry: Mapping[str, object]) -> tuple[str | None, str | None]:
    for key, origin in (('published_parsed', 'feed_entry_published'), ('updated_parsed', 'feed_entry_updated')):
        parsed = entry.get(key)
        if parsed is None:
            continue
        try:
            stamp = datetime(*parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        return stamp.strftime('%Y-%m-%dT%H:%M:%SZ'), origin
    return None, None


@dataclass(frozen=True)
class _EntryHint:
    """Feed-side facts about one article, kept from list_candidates until extract_candidate."""

    title: str | None
    author: str | None
    published_at_raw: str | None
    published_at_origin: str | None
    language_tag: str | None
    media: tuple[dict[str, object], ...]


class RealFeedSource:
    """SourceAdapter for rss_feed and atom_feed; one instance serves one source kind."""

    def __init__(
        self,
        fetcher: SecureFetcher,
        *,
        source_kind: str,
        feed_policy: FetchPolicy,
        article_policy: FetchPolicy,
        max_candidates: int = 200,
        correlation_id: Callable[[], str] = _new_correlation_id,
    ) -> None:
        if not isinstance(fetcher, SecureFetcher) or source_kind not in SOURCE_KINDS:
            raise ValueError('INVALID_ADAPTER_CONFIG')
        if not isinstance(feed_policy, FetchPolicy) or not isinstance(article_policy, FetchPolicy):
            raise ValueError('INVALID_ADAPTER_CONFIG')
        if type(max_candidates) is not int or max_candidates <= 0:
            raise ValueError('INVALID_ADAPTER_CONFIG')
        self._fetcher = fetcher
        self._source_kind = source_kind
        self._feed_policy = feed_policy
        self._article_policy = article_policy
        self._max_candidates = max_candidates
        self._new_correlation_id = correlation_id
        self._hints: dict[str, _EntryHint] = {}
        self.descriptor = AdapterDescriptor(
            'real-' + source_kind.replace('_', '-'),
            ADAPTER_VERSION,
            frozenset({
                AdapterOperation.PROBE,
                AdapterOperation.LIST_CANDIDATES,
                AdapterOperation.FETCH_DOCUMENT,
                AdapterOperation.EXTRACT_CANDIDATE,
            }),
        )

    def _load_feed(self, locator: str) -> tuple[FetchedDocument, feedparser.FeedParserDict] | ProblemDetail:
        correlation_id = self._new_correlation_id()
        fetched = self._fetcher.fetch(locator, self._feed_policy, correlation_id=correlation_id)
        if isinstance(fetched, ProblemDetail):
            return fetched
        headers = {'content-location': fetched.observation.final_locator}
        if fetched.observation.media_type:
            headers['content-type'] = fetched.observation.media_type
        parsed = feedparser.parse(
            io.BytesIO(fetched.body),
            response_headers=headers,
        )
        version = str(parsed.get('version') or '')
        if (parsed.get('bozo') and not parsed.get('entries') and not parsed.get('feed')) or (not parsed.get('entries') and not version):
            return _problem('FEED_PARSE_FAILED', 'Feed body could not be parsed.', 'dependency', False, correlation_id)
        return fetched, parsed

    def probe(self, locator: str) -> ProbeResult | CapabilityUnavailable | ProblemDetail:
        loaded = self._load_feed(locator)
        if isinstance(loaded, ProblemDetail):
            return loaded
        fetched, parsed = loaded
        warnings: list[str] = []
        if parsed.get('bozo'):
            warnings.append(WARNING_FEED_MALFORMED)
        version = str(parsed.get('version') or '')
        if version and not version.startswith(_FEED_VERSION_PREFIX[self._source_kind]):
            warnings.append(WARNING_FEED_KIND_MISMATCH)
        return ProbeResult(fetched.observation.requested_locator, self.descriptor, tuple(warnings))

    def list_candidates(
        self, locator: str, cursor: str | None
    ) -> CandidateListing | CapabilityUnavailable | ProblemDetail:
        if cursor is not None:
            return self.descriptor.unavailable(AdapterOperation.LIST_CANDIDATES, 'feed_has_no_paging_cursor')
        loaded = self._load_feed(locator)
        if isinstance(loaded, ProblemDetail):
            return loaded
        fetched, parsed = loaded
        base = fetched.observation.final_locator
        hints: dict[str, _EntryHint] = {}
        complete = True
        for entry in parsed.entries:
            link = _http_locator(base, entry.get('link'))
            if link is None or link in hints:
                continue
            if len(hints) >= self._max_candidates:
                complete = False
                break
            published, origin = _entry_published(entry)
            language = entry.get('language') or parsed.feed.get('language')
            hints[link] = _EntryHint(
                entry.get('title'), entry.get('author'), published, origin, language, tuple(_feed_media(entry, base))
            )
        self._hints = hints
        return CandidateListing(tuple(hints), None, complete)

    def fetch_document(self, locator: str) -> FetchedDocument | CapabilityUnavailable | ProblemDetail:
        return self._fetcher.fetch(locator, self._article_policy, correlation_id=self._new_correlation_id())

    def extract_candidate(
        self, document: FetchedDocument
    ) -> ExtractedCandidate | CapabilityUnavailable | ProblemDetail:
        observation = document.observation
        try:
            raw = trafilatura.extract(
                document.body,
                url=observation.final_locator,
                output_format='json',
                with_metadata=True,
                include_comments=False,
                include_images=False,
                include_links=False,
            )
            extracted = json.loads(raw) if raw else {}
        except Exception:
            return _problem(
                'EXTRACTION_FAILED', 'Article extraction failed.', 'internal', False, self._new_correlation_id()
            )
        warnings = [] if extracted else [WARNING_NO_CONTENT]
        hint = self._hints.get(observation.requested_locator) or self._hints.get(observation.final_locator)
        media = list(hint.media) if hint else []
        _append_media(media, _http_locator(observation.final_locator, extracted.get('image')), 'hero', 'trafilatura_image')
        if hint and hint.language_tag:
            language, language_origin = hint.language_tag, 'feed'
        else:
            language = extracted.get('language')
            language_origin = 'trafilatura' if language else None
        if hint and hint.published_at_raw:
            published, published_origin = hint.published_at_raw, hint.published_at_origin
        else:
            published = extracted.get('date')
            published_origin = 'trafilatura_date' if published else None
        fields: dict[str, object] = {
            'extractor_version': EXTRACTOR_VERSION,
            'feedparser_version': FEEDPARSER_VERSION,
            'trafilatura_version': TRAFILATURA_VERSION,
            'raw_bytes': bytes(document.body),
            'title': extracted.get('title') or (hint.title if hint else None) or '',
            'text': extracted.get('text') or '',
            'author': (hint.author if hint else None) or extracted.get('author'),
            'language_tag': language,
            'language_origin': language_origin,
            'published_at_raw': published,
            'published_at_origin': published_origin,
            'canonical_url': _http_locator(observation.final_locator, extracted.get('source')),
            'media': tuple(media),
        }
        return ExtractedCandidate(observation.final_locator, MappingProxyType(fields), tuple(warnings))

    def resume_from_checkpoint(
        self, checkpoint_version: str, cursor: str
    ) -> CandidateListing | CapabilityUnavailable | ProblemDetail:
        return self.descriptor.unavailable(AdapterOperation.RESUME_FROM_CHECKPOINT, 'feed_has_no_checkpoint_semantics')

    def supplemental_search(
        self, intent: Mapping[str, str]
    ) -> CandidateListing | CapabilityUnavailable | ProblemDetail:
        return self.descriptor.unavailable(AdapterOperation.SUPPLEMENTAL_SEARCH, 'feed_has_no_supplemental_search')
