"""CollectedDocumentPackage builder with technical normalization (A-13; A-RULE-010, A-RULE-011).

A normalizes encoding, whitespace, timestamp (precision/confidence) and language candidate, builds
content fingerprints and media discoveries with provenance, and always passes the result through
the A-02 validator. The package is an observation: it never carries B decisions such as
``disposition`` or ``article_id``; duplicate, revision and event conclusions belong to B.
"""
from __future__ import annotations

import codecs
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import re
from typing import Protocol
import unicodedata
import uuid

from source_ingestion.domain.package import (
    ELIGIBILITY_CANDIDATE,
    ELIGIBILITY_INCOMPLETE,
    ExtractionPolicy,
    PackageValidationError,
    assess_content_eligibility,
    validate_package_schema,
)
from source_ingestion.ports.source_adapter import ExtractedCandidate, FetchedDocument

DISPOSITION_SUCCESS = 'SUCCESS'
DISPOSITION_PARTIAL = 'PARTIAL'
DISPOSITION_FAILED = 'FAILED'

PRECISION_SECOND = 'second'
PRECISION_DAY = 'day'

CONFIDENCE_HIGH = 'high'
CONFIDENCE_LOW = 'low'
CONFIDENCE_DECLARED = 'declared'

WARNING_ENCODING_REPLACED = 'encoding_replacement_applied'
WARNING_CHARSET_UNKNOWN = 'declared_charset_unknown'
WARNING_TIMEZONE_ASSUMED = 'published_at_timezone_assumed_utc'
WARNING_TIMESTAMP_UNPARSEABLE = 'published_at_unparseable'
WARNING_LANGUAGE_UNDECLARED = 'language_undeclared'
WARNING_LANGUAGE_INVALID = 'language_tag_invalid'
WARNING_EXTRACTOR_FAILED = 'extractor_failed'
WARNING_MEDIA_INCOMPLETE = 'media_discovery_incomplete'
WARNING_ELIGIBILITY_NOT_ASSESSED = 'content_eligibility_not_assessed:'
# Same literal as the extractor warning; application never imports adapters.
PARSE_ERROR_WARNING = 'html_parse_error'

_CHARSET_RE = re.compile(r'charset\s*=\s*["\']?([A-Za-z0-9._:-]+)', re.IGNORECASE)
_DATE_ONLY_RE = re.compile(r'\d{4}-\d{2}-\d{2}')
_LANGUAGE_RE = re.compile(r'[a-z]{2,3}(?:-[a-z0-9]{1,8})*')
_DOCUMENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, 'urn:source-ingestion:collected-document')


@dataclass(frozen=True)
class DecodedBody:
    text: str
    encoding: str
    origin: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class TimestampCandidate:
    value: str
    precision: str
    confidence: str
    origin: str | None


@dataclass(frozen=True)
class LanguageCandidate:
    tag: str
    primary: str
    origin: str | None
    confidence: str


@dataclass(frozen=True)
class PackageContext:
    source_id: str
    source_revision: int
    collection_run_id: str
    fetched_at: datetime
    raw_snapshot_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError('INVALID_PACKAGE_CONTEXT')
        if type(self.source_revision) is not int or self.source_revision < 1:
            raise ValueError('INVALID_PACKAGE_CONTEXT')
        if not isinstance(self.collection_run_id, str) or not self.collection_run_id.strip():
            raise ValueError('INVALID_PACKAGE_CONTEXT')
        if not isinstance(self.fetched_at, datetime) or self.fetched_at.utcoffset() is None:
            raise ValueError('INVALID_PACKAGE_CONTEXT')
        if self.raw_snapshot_ref is not None and (
            not isinstance(self.raw_snapshot_ref, str) or not self.raw_snapshot_ref.strip()
        ):
            raise ValueError('INVALID_PACKAGE_CONTEXT')


class HtmlExtractor(Protocol):
    version: str

    def extract(self, html: str, *, base_locator: str) -> ExtractedCandidate: ...


def _declared_charset(headers: Iterable[tuple[str, str]]) -> str | None:
    for name, value in headers:
        if name.strip().lower() == 'content-type':
            match = _CHARSET_RE.search(value)
            return match.group(1) if match else None
    return None


def decode_body(body: bytes, headers: Iterable[tuple[str, str]]) -> DecodedBody:
    warnings: list[str] = []
    data = bytes(body)
    if data.startswith(codecs.BOM_UTF8):
        encoding, origin = 'utf-8', 'bom'
        data = data[len(codecs.BOM_UTF8) :]
    else:
        encoding, origin = 'utf-8', 'default'
        declared = _declared_charset(headers)
        if declared is not None:
            try:
                info = codecs.lookup(declared)
                if not getattr(info, '_is_text_encoding', True):
                    raise LookupError('not a text encoding')
                name = info.name
            except LookupError:
                warnings.append(WARNING_CHARSET_UNKNOWN)
            else:
                encoding, origin = name, 'http_header'
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        text = data.decode(encoding, errors='replace')
        warnings.append(WARNING_ENCODING_REPLACED)
    return DecodedBody(text, encoding, origin, tuple(warnings))


def normalize_text(value: object) -> str:
    if not isinstance(value, str):
        return ''
    value = unicodedata.normalize('NFC', value)
    lines = [' '.join(line.split()) for line in value.splitlines()]
    return '\n'.join(line for line in lines if line)


def normalize_title(value: object) -> str:
    if not isinstance(value, str):
        return ''
    return ' '.join(unicodedata.normalize('NFC', value).split())


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + 'Z'


def normalize_timestamp(raw: object, origin: str | None) -> tuple[TimestampCandidate | None, tuple[str, ...]]:
    if not isinstance(raw, str) or not raw.strip():
        return (None, ())
    text = raw.strip()
    try:
        if _DATE_ONLY_RE.fullmatch(text):
            day = date.fromisoformat(text)
            return (TimestampCandidate(f'{day.isoformat()}T00:00:00Z', PRECISION_DAY, CONFIDENCE_LOW, origin), ())
        parsed = datetime.fromisoformat(text)
        confidence, warnings = CONFIDENCE_HIGH, ()
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
            confidence, warnings = CONFIDENCE_LOW, (WARNING_TIMEZONE_ASSUMED,)
        return (TimestampCandidate(_format_utc(parsed), PRECISION_SECOND, confidence, origin), warnings)
    except (ValueError, OverflowError):
        return (None, (WARNING_TIMESTAMP_UNPARSEABLE,))


def normalize_language(raw: object, origin: str | None) -> tuple[LanguageCandidate | None, tuple[str, ...]]:
    if not isinstance(raw, str) or not raw.strip():
        return (None, (WARNING_LANGUAGE_UNDECLARED,))
    tag = raw.strip().replace('_', '-').lower()
    if not _LANGUAGE_RE.fullmatch(tag):
        return (None, (WARNING_LANGUAGE_INVALID,))
    return (LanguageCandidate(tag, tag.split('-', 1)[0], origin, CONFIDENCE_DECLARED), ())


def _provenance_chain(
    chain: tuple[str, ...], extractor_version: str, policy_revision: str
) -> list[dict[str, object]]:
    return [
        {'step': 'final_fetch' if index == len(chain) - 1 else 'redirect_hop', 'url': locator, 'hop': index}
        for index, locator in enumerate(chain)
    ] + [{'step': 'extraction', 'extractor_version': extractor_version, 'fetch_policy_revision': policy_revision}]


def _media_discoveries(
    items: object, provenance: Mapping[str, object], observed_at: str
) -> tuple[list[dict[str, object]], list[str]]:
    discoveries: list[dict[str, object]] = []
    warnings: list[str] = []
    for item in items or ():
        if not isinstance(item, Mapping) or any(
            not isinstance(item.get(key), str) or not str(item.get(key)).strip()
            for key in ('locator', 'role', 'media_kind')
        ):
            warnings.append(WARNING_MEDIA_INCOMPLETE)
            continue
        raw_context = item.get('context') if isinstance(item.get('context'), Mapping) else {}
        context: dict[str, object] = {}
        for key, value in raw_context.items():
            if isinstance(value, str):
                value = normalize_title(value)
                if not value:
                    continue
            context[str(key)] = value
        discoveries.append({
            'locator': str(item['locator']).strip(),
            'role': item['role'],
            'media_kind': item['media_kind'],
            'context': context,
            'observed_at': observed_at,
            'provenance': {**provenance, 'redirect_chain': list(provenance['redirect_chain'])},
        })
    return (discoveries, warnings)


def build_package(
    document: FetchedDocument,
    extractor: HtmlExtractor,
    context: PackageContext,
    *,
    extraction_policy: ExtractionPolicy | None = None,
    source_kind: str | None = None,
) -> dict[str, object]:
    obs = document.observation
    version = getattr(extractor, 'version', None)
    if not isinstance(version, str) or not version.strip():
        raise ValueError('INVALID_EXTRACTOR')
    if not isinstance(context, PackageContext):
        raise ValueError('INVALID_PACKAGE_CONTEXT')

    warnings: list[str] = []
    decoded = decode_body(document.body, obs.safe_headers)
    warnings.extend(decoded.warnings)
    failed = False
    try:
        extracted = extractor.extract(decoded.text, base_locator=obs.final_locator)
        fields = dict(extracted.technical_fields)
        warnings.extend(extracted.warnings)
    except Exception:
        failed = True
        fields = {}
        warnings.append(WARNING_EXTRACTOR_FAILED)

    title = normalize_title(fields.get('title'))
    text = normalize_text(fields.get('text'))
    author = normalize_title(fields.get('author'))
    timestamp, w1 = normalize_timestamp(fields.get('published_at_raw'), fields.get('published_at_origin'))
    language, w2 = normalize_language(fields.get('language_tag'), fields.get('language_origin'))
    warnings.extend(w1)
    warnings.extend(w2)

    fetched_at = _format_utc(context.fetched_at)
    raw_sha = hashlib.sha256(document.body).hexdigest()
    chain = tuple(obs.redirect_chain) or (obs.final_locator,)
    document_id = str(
        uuid.uuid5(
            _DOCUMENT_NAMESPACE,
            '\x1f'.join((
                context.source_id,
                str(context.source_revision),
                context.collection_run_id,
                obs.requested_locator,
                obs.final_locator,
                fetched_at,
                raw_sha,
            )),
        )
    )

    provenance = {
        'source_id': context.source_id,
        'source_revision': context.source_revision,
        'collection_run_id': context.collection_run_id,
        'collected_document_id': document_id,
        'document_locator': obs.final_locator,
        'redirect_chain': list(chain),
        'extractor_version': version,
    }
    media, w3 = _media_discoveries(fields.get('media'), provenance, fetched_at)
    warnings.extend(w3)

    content: dict[str, object] = {
        'title': title,
        'text': text,
        'encoding': decoded.encoding,
        'encoding_origin': decoded.origin,
    }
    if author:
        content['author'] = author
    if language:
        content['language'] = language.primary
        content['language_candidate'] = {
            'tag': language.tag,
            'primary': language.primary,
            'origin': language.origin,
            'confidence': language.confidence,
        }
    if timestamp:
        content['published_at'] = {
            'value': timestamp.value,
            'precision': timestamp.precision,
            'confidence': timestamp.confidence,
            'origin': timestamp.origin,
        }

    fingerprints: dict[str, str] = {'raw_body_sha256': raw_sha}
    if text:
        fingerprints = {
            'normalized_text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'raw_body_sha256': raw_sha,
        }

    if failed:
        extraction_disposition = DISPOSITION_FAILED
    elif not text or PARSE_ERROR_WARNING in warnings:
        extraction_disposition = DISPOSITION_PARTIAL
    else:
        extraction_disposition = DISPOSITION_SUCCESS

    package: dict[str, object] = {
        'collected_document_id': document_id,
        'source_id': context.source_id,
        'source_revision': context.source_revision,
        'collection_run_id': context.collection_run_id,
        'requested_url': obs.requested_locator,
        'final_url': obs.final_locator,
        'fetched_at': fetched_at,
        'http_observation': {
            'status': obs.status,
            'media_type': obs.media_type,
            'size_bytes': obs.size_bytes,
            'redirect_chain': list(chain),
            'safe_headers': [[name, value] for name, value in obs.safe_headers],
            'fetch_policy_revision': obs.policy_revision,
        },
        'extraction_disposition': extraction_disposition,
        'extractor_version': version,
        'provenance_chain': _provenance_chain(chain, version, obs.policy_revision),
        'warnings': list(dict.fromkeys(warnings)),
    }
    canonical = fields.get('canonical_url')
    if isinstance(canonical, str) and canonical.strip():
        package['canonical_url_candidate'] = canonical.strip()
    if timestamp:
        package['published_at_candidate'] = timestamp.value
    if context.raw_snapshot_ref is not None:
        package['raw_snapshot_ref'] = context.raw_snapshot_ref
    package['extracted_content_candidate'] = content
    package['content_fingerprints'] = fingerprints
    package['media_discoveries'] = media

    assessment = assess_content_eligibility(package, source_kind or '', extraction_policy)
    if assessment.outcome in (ELIGIBILITY_CANDIDATE, ELIGIBILITY_INCOMPLETE):
        package['content_eligibility'] = assessment.outcome
        if assessment.reason:
            package['eligibility_reason'] = assessment.reason
    else:
        package_warnings = package['warnings']
        assert isinstance(package_warnings, list)
        package_warnings.append(WARNING_ELIGIBILITY_NOT_ASSESSED + str(assessment.reason))

    errors = validate_package_schema(package)
    if errors:
        raise PackageValidationError(errors)
    return package
