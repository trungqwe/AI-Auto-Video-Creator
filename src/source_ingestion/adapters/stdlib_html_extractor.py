"""Reference HTML extractor built only on the standard library ``html.parser`` (A-13).

FIXTURE-ONLY: this extractor exists to exercise the package builder with inline test fixtures.
It is not the production extractor; the production choice is pending USER-CKPT-D9-D10 and
MODULE-A-OPEN-008. Malformed HTML becomes a warning and is never raised to the caller.
"""
from __future__ import annotations

from html.parser import HTMLParser
from types import MappingProxyType
from urllib.parse import urljoin, urlsplit

from source_ingestion.ports.source_adapter import ExtractedCandidate

EXTRACTOR_VERSION = 'stdlib-html-0'
WARNING_PARSE_ERROR = 'html_parse_error'
WARNING_UNBALANCED = 'html_unbalanced_tags'
WARNING_MEDIA_SKIPPED = 'media_locator_skipped'
WARNING_NOT_TEXT = 'html_not_text'

SKIP_TAGS = frozenset({'script', 'style', 'noscript', 'template'})
BLOCK_TAGS = frozenset({
    'address', 'article', 'aside', 'blockquote', 'br', 'dd', 'div', 'dl', 'dt',
    'figcaption', 'figure', 'footer', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'header', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'pre', 'section',
    'table', 'td', 'th', 'tr', 'ul',
})
VOID_TAGS = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'source', 'track', 'wbr',
})
OPTIONAL_END_TAGS = frozenset({
    'html', 'head', 'body', 'p', 'li', 'dt', 'dd', 'tr', 'td', 'th',
    'thead', 'tbody', 'tfoot', 'option', 'colgroup', 'caption',
})
PUBLISHED_META_KEYS = frozenset({'article:published_time', 'datepublished', 'pubdate'})


class _CandidateParser(HTMLParser):
    def __init__(self, base_locator: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_locator = base_locator
        self.stack: list[str] = []
        self.unbalanced = False
        self.skip_depth = 0
        self.in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.author: str | None = None
        self.html_lang: str | None = None
        self.meta_lang: str | None = None
        self.canonical: str | None = None
        self.published: tuple[str, str] | None = None
        self.media: list[dict[str, object]] = []
        self.warnings: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {name.lower(): (value or '') for name, value in attrs}
        if tag not in VOID_TAGS:
            self.stack.append(tag)
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        if tag in BLOCK_TAGS:
            self.text_parts.append('\n')

        if tag == 'html' and self.html_lang is None and values.get('lang', '').strip():
            self.html_lang = values.get('lang', '').strip()
        elif tag == 'title':
            self.in_title = True
        elif tag == 'meta':
            self._meta(values)
        elif tag == 'link' and 'canonical' in values.get('rel', '').lower().split() and self.canonical is None:
            self.canonical = self._resolve(values.get('href', ''))
        elif tag == 'img':
            self._add_media(values.get('src'), 'inline', 'image', 'img', values.get('alt'))
        elif tag == 'video':
            self._add_media(values.get('src'), 'embedded', 'video', 'video', None)
        elif tag == 'source' and 'video' in self.stack:
            self._add_media(values.get('src'), 'embedded', 'video', 'source', None)
        elif tag == 'iframe':
            self._add_media(values.get('src'), 'embedded', 'embed', 'iframe', None)
        elif tag == 'time' and self.published is None and values.get('datetime', '').strip():
            self.published = (values.get('datetime', '').strip(), 'time_datetime')

    def _meta(self, values: dict[str, str]) -> None:
        key = (values.get('property') or values.get('name') or values.get('itemprop') or '').strip().lower()
        content = values.get('content', '').strip()
        if values.get('http-equiv', '').strip().lower() == 'content-language' and content and self.meta_lang is None:
            self.meta_lang = content
        if not content:
            return
        if key == 'og:image':
            self._add_media(content, 'hero', 'image', 'meta', None)
        elif key in PUBLISHED_META_KEYS and self.published is None:
            self.published = (content, 'meta_published_time')
        elif key == 'author' and self.author is None:
            self.author = content

    def _resolve(self, raw: str | None) -> str | None:
        if raw is None or not raw.strip():
            return None
        try:
            locator = urljoin(self.base_locator, raw.strip())
            parts = urlsplit(locator)
        except ValueError:
            return None
        if parts.scheme in ('http', 'https') and parts.netloc:
            return locator
        return None

    def _add_media(
        self,
        raw: str | None,
        role: str,
        kind: str,
        element: str,
        alt: str | None,
    ) -> None:
        if raw is None or not raw.strip():
            return
        locator = self._resolve(raw)
        if locator is None:
            self.warnings.append(WARNING_MEDIA_SKIPPED)
            return
        if any(item['locator'] == locator and item['role'] == role for item in self.media):
            return
        context: dict[str, object] = {'element': element, 'position': len(self.media)}
        if alt is not None:
            context['alt'] = alt
        self.media.append({'locator': locator, 'role': role, 'media_kind': kind, 'context': context})

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in VOID_TAGS:
            return
        if tag in BLOCK_TAGS:
            self.text_parts.append('\n')
        if tag == 'title':
            self.in_title = False
        if tag not in self.stack:
            self.unbalanced = True
            return
        while self.stack:
            open_tag = self.stack.pop()
            if open_tag in SKIP_TAGS:
                self.skip_depth = max(0, self.skip_depth - 1)
            if open_tag == tag:
                break
            if open_tag not in OPTIONAL_END_TAGS:
                self.unbalanced = True

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if self.in_title:
            self.title_parts.append(data)
        else:
            self.text_parts.append(data)


class StdlibHtmlExtractor:
    """Fixture-only reference extractor; never raises on malformed HTML."""

    version = EXTRACTOR_VERSION

    def extract(self, html: object, *, base_locator: str) -> ExtractedCandidate:
        parser = _CandidateParser(base_locator)
        warnings: list[str] = []
        if isinstance(html, str):
            try:
                parser.feed(html)
                parser.close()
            except Exception:
                # Malformed markup must never escape the reference extractor.
                warnings.append(WARNING_PARSE_ERROR)
        else:
            warnings.append(WARNING_NOT_TEXT)

        if parser.unbalanced or any(tag not in OPTIONAL_END_TAGS for tag in parser.stack):
            warnings.append(WARNING_UNBALANCED)
        warnings.extend(parser.warnings)

        if parser.html_lang:
            language_tag, language_origin = parser.html_lang, 'html_lang'
        elif parser.meta_lang:
            language_tag, language_origin = parser.meta_lang, 'meta_content_language'
        else:
            language_tag, language_origin = None, None

        published_raw, published_origin = parser.published or (None, None)
        fields: dict[str, object] = {
            'extractor_version': EXTRACTOR_VERSION,
            'title': ''.join(parser.title_parts),
            'text': ''.join(parser.text_parts),
            'author': parser.author,
            'language_tag': language_tag,
            'language_origin': language_origin,
            'published_at_raw': published_raw,
            'published_at_origin': published_origin,
            'canonical_url': parser.canonical,
            'media': tuple(parser.media),
        }
        return ExtractedCandidate(base_locator, MappingProxyType(fields), tuple(dict.fromkeys(warnings)))
