"""A-13: stdlib reference HTML extractor and CollectedDocumentPackage builder.

coveredIds: A-RULE-010, A-RULE-011
"""
from __future__ import annotations

import ast
import codecs
from datetime import datetime, timedelta, timezone
import hashlib
import json
import pathlib
import socket
import sys

import pytest

from source_ingestion.adapters import stdlib_html_extractor
from source_ingestion.adapters.stdlib_html_extractor import (
    EXTRACTOR_VERSION,
    WARNING_MEDIA_SKIPPED,
    WARNING_NOT_TEXT,
    WARNING_PARSE_ERROR,
    WARNING_UNBALANCED,
    StdlibHtmlExtractor,
)
from source_ingestion.application import package_builder
from source_ingestion.application.package_builder import (
    CONFIDENCE_DECLARED,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    DISPOSITION_FAILED,
    DISPOSITION_PARTIAL,
    DISPOSITION_SUCCESS,
    PARSE_ERROR_WARNING,
    PRECISION_DAY,
    PRECISION_SECOND,
    WARNING_CHARSET_UNKNOWN,
    WARNING_ELIGIBILITY_NOT_ASSESSED,
    WARNING_ENCODING_REPLACED,
    WARNING_EXTRACTOR_FAILED,
    WARNING_LANGUAGE_INVALID,
    WARNING_LANGUAGE_UNDECLARED,
    WARNING_MEDIA_INCOMPLETE,
    WARNING_TIMESTAMP_UNPARSEABLE,
    WARNING_TIMEZONE_ASSUMED,
    DecodedBody,
    LanguageCandidate,
    PackageContext,
    TimestampCandidate,
    build_package,
    decode_body,
    normalize_language,
    normalize_text,
    normalize_timestamp,
    normalize_title,
)
from source_ingestion.domain.package import (
    ExtractionPolicy,
    PackageValidationError,
    validate_package_schema,
)
from source_ingestion.ports.source_adapter import (
    ExtractedCandidate,
    FetchedDocument,
    FetchObservation,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
EXTRACTOR_PATH = ROOT / 'src' / 'source_ingestion' / 'adapters' / 'stdlib_html_extractor.py'
BUILDER_PATH = ROOT / 'src' / 'source_ingestion' / 'application' / 'package_builder.py'
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'a-b-collected-document.json'
REQUESTED = 'https://example.com/news/article-1'
FINAL = 'https://example.com/news/article-1-final'
SOURCE_ID = '00000000-0000-4000-8000-000000000002'
RUN_ID = '00000000-0000-4000-8000-000000000003'
FETCHED_AT = datetime(2026, 10, 18, 8, 0, 0, tzinfo=timezone.utc)
NETWORK_FUNCTIONS = ('getaddrinfo', 'create_connection', 'gethostbyname', 'gethostbyname_ex')
THIRD_PARTY_HTML = ('bs4', 'lxml', 'html5lib', 'trafilatura', 'readability', 'selectolax', 'parsel')
B_DECISION_FIELDS = frozenset({'dedup_policy_revision', 'disposition', 'article_id', 'article_revision_id'})
# Test-only policy fixture; not an approved production policy.
POLICY = ExtractionPolicy(revision='extraction-policy-fixture-r1', title_required_by_source_kind={'web_page': True})

ARTICLE_HTML = (
    '<!DOCTYPE html>\n'
    '<html lang="vi-VN">\n'
    '<head>\n'
    '<meta charset="utf-8">\n'
    '<title>  Tiêu đề    bài viết </title>\n'
    '<meta name="author" content="Nguyễn Văn A">\n'
    '<meta property="article:published_time" content="2026-10-18T15:30:00+07:00">\n'
    '<meta property="og:image" content="/images/hero.jpg">\n'
    '<link rel="canonical" href="/bai-viet-1">\n'
    '<style>.x{color:red}</style>\n'
    '</head>\n'
    '<body>\n'
    '<article>\n'
    '<h1>Tiêu đề bài viết</h1>\n'
    '<p>Đoạn   một\tcó  khoảng trắng.</p>\n'
    '<p>Đoạn&nbsp;hai.</p>\n'
    '<img src="photo.jpg" alt="  Ảnh   minh hoạ ">\n'
    '<img src="data:image/png;base64,AAAA" alt="inline">\n'
    '<video><source src="https://cdn.example.com/clip.mp4"></video>\n'
    '<iframe src="https://video.example.net/embed/42"></iframe>\n'
    '<script>var tracking = "secret-script";</script>\n'
    '</article>\n'
    '</body>\n'
    '</html>'
)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError('real DNS/network call in unit test')

    for name in NETWORK_FUNCTIONS:
        monkeypatch.setattr(socket, name, _network_forbidden)


def make_document(
    html: str | bytes,
    *,
    content_type: str | None = 'text/html; charset=utf-8',
    chain: tuple[str, ...] = (REQUESTED, FINAL),
) -> FetchedDocument:
    body = html.encode('utf-8') if isinstance(html, str) else bytes(html)
    headers = ((('content-type', content_type),) if content_type is not None else ()) + (('etag', '"1"'),)
    return FetchedDocument(
        FetchObservation(chain[0], chain[-1], tuple(chain), 200, 'text/html', len(body), headers, 'fetch-policy-r1'),
        body,
    )


def make_context(**overrides: object) -> PackageContext:
    values: dict[str, object] = {
        'source_id': SOURCE_ID,
        'source_revision': 1,
        'collection_run_id': RUN_ID,
        'fetched_at': FETCHED_AT,
    }
    values.update(overrides)
    return PackageContext(**values)  # type: ignore[arg-type]


def extract(html: object, base: str = FINAL) -> ExtractedCandidate:
    result = StdlibHtmlExtractor().extract(html, base_locator=base)
    assert isinstance(result, ExtractedCandidate)
    assert result.technical_fields.get('extractor_version') == EXTRACTOR_VERSION
    return result


def build(
    document: FetchedDocument,
    context: PackageContext | None = None,
    extractor: StdlibHtmlExtractor | None = None,
    **kwargs: object,
) -> dict[str, object]:
    package = build_package(
        document,
        extractor or StdlibHtmlExtractor(),
        context or make_context(),
        **kwargs,  # type: ignore[arg-type]
    )
    assert isinstance(package, dict)
    assert validate_package_schema(package) == ()
    return package


def _imports(path: pathlib.Path) -> list[str]:
    names: list[str] = []
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
    return names


def _binding_fields(entity: str) -> set[str]:
    data = json.loads(BINDING_PATH.read_text(encoding='utf-8'))
    for item in data.get('entities', ()):
        if item.get('name') == entity:
            return {field['name'] for field in item.get('fields', ())}
    return set()


def _all_keys(value: object):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _all_keys(v)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _all_keys(item)


def test_extractor_is_fixture_only_reference_with_pinned_version() -> None:
    assert EXTRACTOR_VERSION == 'stdlib-html-0'
    assert StdlibHtmlExtractor.version == EXTRACTOR_VERSION
    doc = stdlib_html_extractor.__doc__ or ''
    assert 'FIXTURE-ONLY' in doc
    assert 'not the production extractor' in doc
    assert 'html.parser' in doc


def test_extractor_imports_only_stdlib_and_html_parser() -> None:
    names = _imports(EXTRACTOR_PATH)
    assert 'html.parser' in names
    for name in names:
        root = name.split('.')[0]
        assert root in sys.stdlib_module_names or name.startswith('source_ingestion.ports')
        assert root not in THIRD_PARTY_HTML


def test_builder_imports_only_stdlib_domain_and_ports() -> None:
    names = _imports(BUILDER_PATH)
    for name in names:
        root = name.split('.')[0]
        assert root in sys.stdlib_module_names or name.startswith(('source_ingestion.domain', 'source_ingestion.ports'))
        assert not name.startswith('source_ingestion.adapters')


def test_extractor_reads_technical_fields() -> None:
    result = extract(ARTICLE_HTML)
    fields = result.technical_fields
    assert ' '.join(str(fields['title']).split()) == 'Tiêu đề bài viết'
    assert fields['language_tag'] == 'vi-VN'
    assert fields['language_origin'] == 'html_lang'
    assert fields['published_at_raw'] == '2026-10-18T15:30:00+07:00'
    assert fields['published_at_origin'] == 'meta_published_time'
    assert fields['author'] == 'Nguyễn Văn A'
    assert fields['canonical_url'] == 'https://example.com/bai-viet-1'
    assert 'secret-script' not in str(fields['text'])
    assert 'color:red' not in str(fields['text'])
    assert 'Đoạn' in str(fields['text'])
    media = fields['media']
    assert isinstance(media, tuple)
    assert [(m['role'], m['media_kind'], m['locator']) for m in media] == [
        ('hero', 'image', 'https://example.com/images/hero.jpg'),
        ('inline', 'image', 'https://example.com/news/photo.jpg'),
        ('embedded', 'video', 'https://cdn.example.com/clip.mp4'),
        ('embedded', 'embed', 'https://video.example.net/embed/42'),
    ]
    assert media[1]['context'] == {'element': 'img', 'position': 1, 'alt': '  Ảnh   minh hoạ '}
    assert WARNING_MEDIA_SKIPPED in result.warnings
    assert WARNING_UNBALANCED not in result.warnings


@pytest.mark.parametrize(
    'html',
    [
        '<div><p>Xin chào <b>thế giới</div></span>',
        '<html><body><p>unterminated <a href="x',
        '<<<>>>&&&#xZZZ;&#99999999;',
        '',
        '\x00\x01<p>nhị phân',
        '</p></p></div>',
        '<p' * 2000,
    ],
)
def test_malformed_html_becomes_warning_without_raising(html: str) -> None:
    result = extract(html)
    assert isinstance(result.technical_fields['text'], str)


@pytest.mark.parametrize('html', ['<div><p>Xin chào <b>thế giới</div></span>', '</p></p></div>'])
def test_unbalanced_markup_is_reported(html: str) -> None:
    assert WARNING_UNBALANCED in extract(html).warnings


def test_parser_exception_is_captured_as_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(self: object, data: object) -> None:
        raise ValueError('boom')

    monkeypatch.setattr(stdlib_html_extractor._CandidateParser, 'feed', _boom)
    assert WARNING_PARSE_ERROR in extract(ARTICLE_HTML).warnings


def test_non_text_input_is_warning() -> None:
    assert WARNING_NOT_TEXT in extract(b'<p>x</p>').warnings


def test_decode_body_charset_bom_default_and_replacement() -> None:
    assert decode_body('café'.encode('cp1252'), (('content-type', 'text/html; charset=windows-1252'),)) == DecodedBody(
        'café', 'cp1252', 'http_header', ()
    )
    assert decode_body('x'.encode(), (('content-type', 'text/html; charset="UTF-8"'),)) == DecodedBody(
        'x', 'utf-8', 'http_header', ()
    )
    assert decode_body(codecs.BOM_UTF8 + 'xin chào'.encode('utf-8'), ()) == DecodedBody(
        'xin chào', 'utf-8', 'bom', ()
    )
    assert decode_body(b'ok \xff\xfe', ()) == DecodedBody(
        'ok \ufffd\ufffd', 'utf-8', 'default', (WARNING_ENCODING_REPLACED,)
    )
    assert decode_body(b'abc', (('content-type', 'text/html; charset=x-unknown-9'),)) == DecodedBody(
        'abc', 'utf-8', 'default', (WARNING_CHARSET_UNKNOWN,)
    )
    assert decode_body(b'abc', (('content-type', 'text/html; charset=base64'),)) == DecodedBody(
        'abc', 'utf-8', 'default', (WARNING_CHARSET_UNKNOWN,)
    )


def test_normalize_text_and_title_whitespace_and_unicode() -> None:
    assert normalize_text('  Vie\u0302\u0323t\u00a0Nam \t\n\n  xin   chào \r\n') == 'Việt Nam\nxin chào'
    assert normalize_text(None) == ''
    assert normalize_title('  a \n b\u00a0 ') == 'a b'
    assert normalize_title(42) == ''


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        (
            '2026-10-18T15:30:00+07:00',
            (TimestampCandidate('2026-10-18T08:30:00Z', PRECISION_SECOND, CONFIDENCE_HIGH, 'meta_published_time'), ()),
        ),
        (
            '2026-10-18T08:30:00',
            (
                TimestampCandidate('2026-10-18T08:30:00Z', PRECISION_SECOND, CONFIDENCE_LOW, 'meta_published_time'),
                (WARNING_TIMEZONE_ASSUMED,),
            ),
        ),
        (
            '2026-10-18',
            (TimestampCandidate('2026-10-18T00:00:00Z', PRECISION_DAY, CONFIDENCE_LOW, 'meta_published_time'), ()),
        ),
        ('hôm qua', (None, (WARNING_TIMESTAMP_UNPARSEABLE,))),
        ('2026-02-30', (None, (WARNING_TIMESTAMP_UNPARSEABLE,))),
        ('9999-12-31T23:59:59-23:59', (None, (WARNING_TIMESTAMP_UNPARSEABLE,))),
        (None, (None, ())),
    ],
)
def test_normalize_timestamp_precision_and_confidence(
    raw: object, expected: tuple[TimestampCandidate | None, tuple[str, ...]]
) -> None:
    assert normalize_timestamp(raw, 'meta_published_time') == expected


@pytest.mark.parametrize(
    ('raw', 'origin', 'expected'),
    [
        (
            'vi-VN',
            'html_lang',
            (LanguageCandidate('vi-vn', 'vi', 'html_lang', CONFIDENCE_DECLARED), ()),
        ),
        (
            'en_US',
            'meta_content_language',
            (LanguageCandidate('en-us', 'en', 'meta_content_language', CONFIDENCE_DECLARED), ()),
        ),
        (None, None, (None, (WARNING_LANGUAGE_UNDECLARED,))),
        ('123', 'html_lang', (None, (WARNING_LANGUAGE_INVALID,))),
    ],
)
def test_normalize_language_candidate(
    raw: object, origin: str | None, expected: tuple[LanguageCandidate | None, tuple[str, ...]]
) -> None:
    assert normalize_language(raw, origin) == expected


def test_package_passes_a02_validator_with_binding_fields_only() -> None:
    package = build(make_document(ARTICLE_HTML))
    assert set(package) <= _binding_fields('CollectedDocumentPackage')
    assert json.loads(json.dumps(package)) == package


def test_package_fields_from_observation_and_context() -> None:
    document = make_document(ARTICLE_HTML)
    package = build(document)
    assert package['source_id'] == SOURCE_ID
    assert package['source_revision'] == 1
    assert package['collection_run_id'] == RUN_ID
    assert package['requested_url'] == REQUESTED
    assert package['final_url'] == FINAL
    assert package['fetched_at'] == '2026-10-18T08:00:00Z'
    assert package['extractor_version'] == EXTRACTOR_VERSION
    assert package['extraction_disposition'] == DISPOSITION_SUCCESS
    assert package['canonical_url_candidate'] == 'https://example.com/bai-viet-1'
    assert package['published_at_candidate'] == '2026-10-18T08:30:00Z'
    assert package['http_observation'] == {
        'status': 200,
        'media_type': 'text/html',
        'size_bytes': len(document.body),
        'redirect_chain': [REQUESTED, FINAL],
        'safe_headers': [['content-type', 'text/html; charset=utf-8'], ['etag', '"1"']],
        'fetch_policy_revision': 'fetch-policy-r1',
    }
    assert package['provenance_chain'] == [
        {'step': 'redirect_hop', 'url': REQUESTED, 'hop': 0},
        {'step': 'final_fetch', 'url': FINAL, 'hop': 1},
        {'step': 'extraction', 'extractor_version': EXTRACTOR_VERSION, 'fetch_policy_revision': 'fetch-policy-r1'},
    ]
    assert package['extracted_content_candidate'] == {
        'title': 'Tiêu đề bài viết',
        'text': 'Tiêu đề bài viết\nĐoạn một có khoảng trắng.\nĐoạn hai.',
        'encoding': 'utf-8',
        'encoding_origin': 'http_header',
        'author': 'Nguyễn Văn A',
        'language': 'vi',
        'language_candidate': {
            'tag': 'vi-vn',
            'primary': 'vi',
            'origin': 'html_lang',
            'confidence': 'declared',
        },
        'published_at': {
            'value': '2026-10-18T08:30:00Z',
            'precision': 'second',
            'confidence': 'high',
            'origin': 'meta_published_time',
        },
    }
    assert package['warnings'] == [WARNING_MEDIA_SKIPPED, WARNING_ELIGIBILITY_NOT_ASSESSED + 'missing_extraction_policy']
    assert 'raw_snapshot_ref' not in package


def test_raw_snapshot_ref_is_carried_from_context() -> None:
    package = build(make_document(ARTICLE_HTML), make_context(raw_snapshot_ref='artifact://snapshot/1'))
    assert package['raw_snapshot_ref'] == 'artifact://snapshot/1'


def test_package_has_no_b_decision_fields() -> None:
    assert _binding_fields('CollectedDocumentResolution') - {'collected_document_id'} == B_DECISION_FIELDS
    assert set(_all_keys(build(make_document(ARTICLE_HTML)))).isdisjoint(B_DECISION_FIELDS)


def test_content_fingerprint_is_sha256_of_normalized_text_not_title() -> None:
    document = make_document(ARTICLE_HTML)
    package = build(document)
    content = package['extracted_content_candidate']
    assert isinstance(content, dict)
    assert package['content_fingerprints'] == {
        'normalized_text_sha256': hashlib.sha256(str(content['text']).encode('utf-8')).hexdigest(),
        'raw_body_sha256': hashlib.sha256(document.body).hexdigest(),
    }
    retitled = build(
        make_document(ARTICLE_HTML.replace('<title>  Tiêu đề    bài viết </title>', '<title>Tiêu đề khác</title>'))
    )
    assert retitled['content_fingerprints']['normalized_text_sha256'] == package['content_fingerprints']['normalized_text_sha256']
    assert retitled['collected_document_id'] != package['collected_document_id']
    changed = build(make_document(ARTICLE_HTML.replace('Đoạn&nbsp;hai.', 'Đoạn hai đã cập nhật.')))
    assert changed['content_fingerprints']['normalized_text_sha256'] != package['content_fingerprints']['normalized_text_sha256']


def test_empty_text_has_no_text_fingerprint_and_is_partial() -> None:
    package = build(make_document('<html><head><title>Chỉ có tiêu đề</title></head><body></body></html>'))
    assert 'normalized_text_sha256' not in package['content_fingerprints']
    assert 'raw_body_sha256' in package['content_fingerprints']
    assert package['extraction_disposition'] == DISPOSITION_PARTIAL
    content = package['extracted_content_candidate']
    assert isinstance(content, dict)
    assert content['title'] == 'Chỉ có tiêu đề'


def test_media_discoveries_have_locator_role_context_and_provenance() -> None:
    package = build(make_document(ARTICLE_HTML))
    discoveries = package['media_discoveries']
    assert isinstance(discoveries, list)
    assert [(m['role'], m['media_kind'], m['locator']) for m in discoveries] == [
        ('hero', 'image', 'https://example.com/images/hero.jpg'),
        ('inline', 'image', 'https://example.com/news/photo.jpg'),
        ('embedded', 'video', 'https://cdn.example.com/clip.mp4'),
        ('embedded', 'embed', 'https://video.example.net/embed/42'),
    ]
    assert [m['context'] for m in discoveries] == [
        {'element': 'meta', 'position': 0},
        {'element': 'img', 'position': 1, 'alt': 'Ảnh minh hoạ'},
        {'element': 'source', 'position': 2},
        {'element': 'iframe', 'position': 3},
    ]
    for m in discoveries:
        assert m['observed_at'] == '2026-10-18T08:00:00Z'
        assert m['provenance'] == {
            'source_id': SOURCE_ID,
            'source_revision': 1,
            'collection_run_id': RUN_ID,
            'collected_document_id': package['collected_document_id'],
            'document_locator': FINAL,
            'redirect_chain': [REQUESTED, FINAL],
            'extractor_version': EXTRACTOR_VERSION,
        }


class _StaticExtractor:
    version = 'fake-static-0'

    def __init__(self, fields: dict[str, object]) -> None:
        self._fields = fields

    def extract(self, html: str, *, base_locator: str) -> ExtractedCandidate:
        return ExtractedCandidate(base_locator, self._fields, ())


def test_media_without_locator_is_dropped_with_warning() -> None:
    package = build(
        make_document('<p>x</p>'),
        extractor=_StaticExtractor({'title': 'T', 'text': 'Nội dung', 'media': ({'role': 'inline', 'media_kind': 'image', 'context': {}},)}),  # type: ignore[arg-type]
    )
    assert package['media_discoveries'] == []
    assert WARNING_MEDIA_INCOMPLETE in package['warnings']


def test_refetch_with_changed_content_creates_new_package_and_fingerprint() -> None:
    doc_a = make_document(ARTICLE_HTML)
    doc_b = make_document(ARTICLE_HTML.replace('Đoạn&nbsp;hai.', 'Đoạn hai đã cập nhật.'))
    later = make_context(fetched_at=FETCHED_AT + timedelta(hours=1))
    p_a = build(doc_a)
    p_b = build(doc_b, later)
    p_c = build(doc_a, later)
    assert p_a['collected_document_id'] != p_b['collected_document_id']
    assert p_a['content_fingerprints']['normalized_text_sha256'] != p_b['content_fingerprints']['normalized_text_sha256']
    assert p_c['collected_document_id'] != p_a['collected_document_id']
    assert p_c['content_fingerprints']['normalized_text_sha256'] == p_a['content_fingerprints']['normalized_text_sha256']
    for p in (p_a, p_b, p_c):
        assert set(_all_keys(p)).isdisjoint(B_DECISION_FIELDS)


def test_same_observation_rebuild_is_deterministic() -> None:
    assert build(make_document(ARTICLE_HTML)) == build(make_document(ARTICLE_HTML))


def test_encoding_is_normalized_in_package() -> None:
    p = build(
        make_document(
            '<html lang="fr"><body><p>café crème</p></body></html>'.encode('cp1252'),
            content_type='text/html; charset=windows-1252',
        )
    )
    content = p['extracted_content_candidate']
    assert isinstance(content, dict)
    assert content['text'] == 'café crème'
    assert content['encoding'] == 'cp1252'
    assert content['encoding_origin'] == 'http_header'
    assert content['language'] == 'fr'

    q = build(make_document(b'<p>ok \xff</p>', content_type='text/html'))
    q_content = q['extracted_content_candidate']
    assert isinstance(q_content, dict)
    assert q_content['text'] == 'ok \ufffd'
    assert WARNING_ENCODING_REPLACED in q['warnings']
    assert WARNING_LANGUAGE_UNDECLARED in q['warnings']


def test_malformed_html_package_still_validates() -> None:
    p = build(make_document('<div><p>Xin chào <b>thế giới</div></span>'))
    assert WARNING_UNBALANCED in p['warnings']
    content = p['extracted_content_candidate']
    assert isinstance(content, dict)
    assert content['text'] == 'Xin chào thế giới'
    assert p['extraction_disposition'] == DISPOSITION_SUCCESS


class _RaisingExtractor:
    version = 'fake-raising-0'

    def extract(self, html: str, *, base_locator: str) -> ExtractedCandidate:
        raise RuntimeError('boom')


def test_extractor_failure_yields_failed_disposition() -> None:
    document = make_document(ARTICLE_HTML)
    p = build(document, extractor=_RaisingExtractor())  # type: ignore[arg-type]
    assert p['extraction_disposition'] == DISPOSITION_FAILED
    assert WARNING_EXTRACTOR_FAILED in p['warnings']
    assert p['extractor_version'] == 'fake-raising-0'
    assert p['content_fingerprints'] == {'raw_body_sha256': hashlib.sha256(document.body).hexdigest()}
    assert p['media_discoveries'] == []


def test_extraction_policy_layer_two_sets_content_eligibility() -> None:
    ok = build(make_document(ARTICLE_HTML), extraction_policy=POLICY, source_kind='web_page')
    assert ok['content_eligibility'] == 'candidate'
    assert 'eligibility_reason' not in ok

    untitled = build(
        make_document(ARTICLE_HTML.replace('<title>  Tiêu đề    bài viết </title>', '<title> </title>')),
        extraction_policy=POLICY,
        source_kind='web_page',
    )
    assert untitled['content_eligibility'] == 'incomplete'
    assert untitled['eligibility_reason'] == 'missing_required_title'

    unknown = build(make_document(ARTICLE_HTML), extraction_policy=POLICY, source_kind='rss_feed')
    assert 'content_eligibility' not in unknown
    assert WARNING_ELIGIBILITY_NOT_ASSESSED + 'missing_source_kind_policy' in unknown['warnings']


@pytest.mark.parametrize(
    'overrides',
    [
        {'fetched_at': datetime(2026, 10, 18, 8, 0, 0)},
        {'source_revision': True},
        {'source_revision': 0},
        {'source_id': ' '},
        {'collection_run_id': ''},
        {'raw_snapshot_ref': ''},
    ],
)
def test_package_context_rejects_invalid_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError, match='INVALID_PACKAGE_CONTEXT'):
        make_context(**overrides)


def test_validator_gate_rejects_invalid_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(package_builder, '_format_utc', lambda value: 'yesterday')
    with pytest.raises(PackageValidationError) as info:
        build_package(make_document(ARTICLE_HTML), StdlibHtmlExtractor(), make_context())
    assert any(error.field == 'fetched_at' for error in info.value.errors)
