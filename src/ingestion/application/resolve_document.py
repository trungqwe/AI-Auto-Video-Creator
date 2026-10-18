"""ResolveCollectedDocument for module B (CT-CNT-001, CT-STATE-003, D8-B-01..04, D8-B-09, D8-B-11).

One unit-of-work transaction per collected document; dedup thresholds come from the policy revision passed by the caller.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from ingestion.application.ports import SourceTierLookup, UnitOfWork
from ingestion.domain.article import Article, ArticleRevision
from ingestion.domain.events import build_event
from ingestion.domain.fingerprint import NEAR_DUPLICATE_JACCARD, SHINGLE_SIZE, exact_fingerprint, is_near_duplicate
from ingestion.domain.normalization import NORMALIZER_VERSION, normalize_text
from ingestion.domain.package_validation import validate_collected_document_package, validate_collected_document_resolution
from ingestion.domain.representative import RepresentativeCandidate, select_representative
from ingestion.domain.topic import classify_topic

VALIDATION_ERROR = 'VALIDATION_ERROR'
FAILED_RETRYABLE = 'FAILED_RETRYABLE'
FAILED_FINAL = 'FAILED_FINAL'
RECEIVED = 'RECEIVED'
NORMALIZING = 'NORMALIZING'
RESOLVING_IDENTITY = 'RESOLVING_IDENTITY'
NEW_ARTICLE = 'NEW_ARTICLE'
NEW_REVISION = 'NEW_REVISION'
DUPLICATE_MEDIA_ONLY = 'DUPLICATE_MEDIA_ONLY'
DUPLICATE_NO_NEW_VALUE = 'DUPLICATE_NO_NEW_VALUE'
REJECTED_INCOMPLETE = 'REJECTED_INCOMPLETE'
TERMINAL_STATES = {
    NEW_ARTICLE: 'NEW_ARTICLE_ACCEPTED',
    NEW_REVISION: 'NEW_REVISION_ACCEPTED',
    DUPLICATE_MEDIA_ONLY: DUPLICATE_MEDIA_ONLY,
    DUPLICATE_NO_NEW_VALUE: DUPLICATE_NO_NEW_VALUE,
    REJECTED_INCOMPLETE: REJECTED_INCOMPLETE,
}
CONTENT_ELIGIBILITY_ABSENT = 'content_eligibility_absent'
CONTENT_INCOMPLETE = 'content_incomplete'
EMPTY_MAIN_TEXT = 'empty_main_text'
MATCH_EXACT = 'exact'
MATCH_NEAR = 'near'
DEDUP_POLICY_REVISION = 'dedup_policy_revision'
KIND_DEDUP_EVIDENCE = 'dedup_evidence'
KIND_MEDIA_ATTACHMENT = 'article_media_attachment'
LOCAL_RECOVERY_EPOCH = 'epoch-local'
_URL_RE = re.compile(r'(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://(?P<host>[^/?#]*)(?P<path>[^?#]*)(?P<query>\?[^#]*)?(?:#.*)?', re.DOTALL)


class ResolveDocumentError(Exception):
    """VALIDATION_ERROR is raised before RECEIVED (state None); FAILED_* carry the CT-STATE-003 state."""

    def __init__(self, code: str, state: str | None = None, issues: Sequence[object] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.state = state
        self.issues = tuple(issues)


def identity_key(url: str) -> str:
    """Lower-case scheme and host, drop the fragment and a trailing '/', keep the query (D8-B-02)."""
    match = _URL_RE.fullmatch(url)
    if match is None:
        return url.split('#', 1)[0].rstrip('/')
    scheme, host = match.group('scheme').lower(), match.group('host').lower()
    return scheme + '://' + host + match.group('path').rstrip('/') + (match.group('query') or '')


def _utc(value: datetime | str) -> str:
    moment = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise ValueError('timestamps must be timezone-aware')
    return moment.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _candidate_field(package: Mapping[str, Any], name: str) -> str:
    content = package.get('extracted_content_candidate')
    value = content.get(name) if isinstance(content, Mapping) else None
    return value if isinstance(value, str) else ''


def _media_refs(package: Mapping[str, Any]) -> tuple[str, ...]:
    """Media discovery refs in package order: the item 'ref', else its 'url'; items with neither are skipped."""
    refs: dict[str, None] = {}
    for item in package.get('media_discoveries') or ():
        ref = next((item[key] for key in ('ref', 'url') if isinstance(item.get(key), str) and item[key]), None)
        if ref is not None:
            refs[ref] = None
    return tuple(refs)


def _incomplete_reason(package: Mapping[str, Any], normalized_text: str) -> str | None:
    """Return the REJECTED_INCOMPLETE reason of D8-B-09, or None for a candidate package with main text."""
    eligibility = package.get('content_eligibility')
    if eligibility is None:
        return CONTENT_ELIGIBILITY_ABSENT
    if eligibility != 'candidate':
        return CONTENT_INCOMPLETE
    if not normalized_text:
        return EMPTY_MAIN_TEXT
    return None


def _attachment(uow: UnitOfWork, article_id: str) -> Mapping[str, Any]:
    stored = uow.records.get(KIND_MEDIA_ATTACHMENT, article_id)
    return stored if stored is not None else {'media_discovery_refs': (), 'source_ids': ()}


def attached_media_refs(uow: UnitOfWork, article_id: str) -> tuple[str, ...]:
    """Media refs of the article revisions followed by media attached from duplicates, first occurrence kept."""
    article = uow.articles.get(article_id)
    revision_refs = [ref for revision in (article.revisions if article else ()) for ref in revision.media_discovery_refs]
    return tuple(dict.fromkeys([*revision_refs, *_attachment(uow, article_id)['media_discovery_refs']]))


def _match(
    uow: UnitOfWork, key: str, fingerprint: str, normalized_text: str, policy: Mapping[str, Any],
) -> tuple[str, Article | None]:
    """Return (NEW_ARTICLE, None), (NEW_REVISION, article) or (MATCH_EXACT | MATCH_NEAR, duplicated article).

    Same identity key with an unseen exact fingerprint is a new revision (D8-B-03); otherwise exact then near
    duplicates are searched, near ones in article_id order against the latest revision (D8-B-01).
    """
    same_identity = uow.articles.find_by_identity_key(key)
    if same_identity is not None:
        if any(revision.exact_fingerprint == fingerprint for revision in same_identity.revisions):
            return MATCH_EXACT, same_identity
        return NEW_REVISION, same_identity
    exact = uow.articles.find_by_exact_fingerprint(fingerprint)
    if exact is not None:
        return MATCH_EXACT, exact
    for article in sorted(uow.articles.list_all(), key=lambda item: item.article_id):
        latest = article.latest_revision
        if latest is not None and is_near_duplicate(normalized_text, latest.normalized_text, policy):
            return MATCH_NEAR, article
    return NEW_ARTICLE, None


def _revision(
    package: Mapping[str, Any],
    article_id: str,
    revision_number: int,
    normalized_text: str,
    fingerprint: str,
    article_revision_id: str,
    topic_rules: Sequence[Mapping[str, Any]],
) -> ArticleRevision:
    title = _candidate_field(package, 'title')
    published = package.get('published_at_candidate')
    topic, topic_uncertain = classify_topic(normalized_text, topic_rules)
    missing = (
        ('title', not title),
        ('published_at', published is None),
        ('raw_snapshot_ref', package.get('raw_snapshot_ref') is None),
        ('topic', topic_uncertain),
    )
    return ArticleRevision(
        article_revision_id=article_revision_id,
        article_id=article_id,
        revision_number=revision_number,
        title=title,
        normalized_text=normalized_text,
        source_id=package['source_id'],
        source_revision=package['source_revision'],
        collection_run_id=package['collection_run_id'],
        collected_document_id=package['collected_document_id'],
        requested_url=package['requested_url'],
        final_url=package['final_url'],
        provenance_chain=package['provenance_chain'],
        raw_snapshot_ref=package.get('raw_snapshot_ref'),
        published_at=None if published is None else _utc(published),
        published_at_confidence='absent' if published is None else 'candidate',
        fetched_at=_utc(package['fetched_at']),
        topic=topic,
        topic_uncertain=topic_uncertain,
        exact_fingerprint=fingerprint,
        media_discovery_refs=_media_refs(package),
        extractor_version=package['extractor_version'],
        normalizer_version=NORMALIZER_VERSION,
        is_complete=True,
        uncertain_fields=[name for name, is_missing in missing if is_missing],
    )


def _emit(
    uow: UnitOfWork,
    event_name: str,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_revision: int,
    payload: Mapping[str, Any],
    recovery_epoch: str,
    id_factory: Callable[[], str],
    deduplication_id: str,
) -> None:
    event = build_event(event_name, aggregate_type, aggregate_id, aggregate_revision, payload, recovery_epoch, id_factory())
    uow.outbox.append_event(event_name, aggregate_id, event, deduplication_id)


def _resolve_duplicate(
    package: Mapping[str, Any],
    policy_revision: str,
    match: str,
    article: Article,
    uow: UnitOfWork,
    tier_lookup: SourceTierLookup,
    id_factory: Callable[[], str],
    recovery_epoch: str,
    deduplication_id: str,
) -> str:
    """Attach new media and provenance to the representative article without a new Article or revision (D8-B-04)."""
    document_id, source_id = package['collected_document_id'], package['source_id']
    attachment = _attachment(uow, article.article_id)
    attached = attached_media_refs(uow, article.article_id)
    new_media = [ref for ref in _media_refs(package) if ref not in attached]
    known_sources = {revision.source_id for revision in article.revisions} | set(attachment['source_ids'])
    disposition = DUPLICATE_MEDIA_ONLY if new_media or source_id not in known_sources else DUPLICATE_NO_NEW_VALUE
    incumbent = RepresentativeCandidate(article.representative_source_id, tier_lookup.tier_of(article.representative_source_id))
    selection = select_representative(incumbent, [RepresentativeCandidate(source_id, tier_lookup.tier_of(source_id))])
    if selection.changed:
        uow.articles.save(replace(article, representative_source_id=selection.representative.source_id))
    if disposition == DUPLICATE_MEDIA_ONLY:
        uow.records.put(KIND_MEDIA_ATTACHMENT, article.article_id, {
            'article_id': article.article_id,
            'media_discovery_refs': (*attachment['media_discovery_refs'], *new_media),
            'source_ids': tuple(dict.fromkeys([*attachment['source_ids'], source_id])),
        })
    uow.records.put(KIND_DEDUP_EVIDENCE, deduplication_id, {
        'collected_document_id': document_id,
        DEDUP_POLICY_REVISION: policy_revision,
        'article_id': article.article_id,
        'source_id': source_id,
        'match': match,
        'selection_reason': selection.selection_reason,
    })
    payload: dict[str, Any] = {
        'collected_document_id': document_id,
        DEDUP_POLICY_REVISION: policy_revision,
        'article_id': article.article_id,
        'representative_source_id': selection.representative.source_id,
    }
    if disposition == DUPLICATE_MEDIA_ONLY:
        payload['new_media_discovery_refs'] = new_media
    _emit(
        uow, 'DuplicateDocumentResolved', 'CollectedDocumentResolution', document_id, 1, payload,
        recovery_epoch, id_factory, deduplication_id,
    )
    return disposition


def _resolve(
    package: Mapping[str, Any],
    policy: Mapping[str, Any],
    policy_revision: str,
    uow: UnitOfWork,
    tier_lookup: SourceTierLookup,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
    topic_rules: Sequence[Mapping[str, Any]],
    recovery_epoch: str,
) -> dict[str, Any]:
    """Walk RECEIVED, NORMALIZING, RESOLVING_IDENTITY to a terminal state, staging every write (CT-STATE-003)."""
    document_id = package['collected_document_id']
    deduplication_id = f'{document_id}:{policy_revision}'
    trail = [RECEIVED, NORMALIZING]
    normalized_text = normalize_text(_candidate_field(package, 'text'))
    reason = _incomplete_reason(package, normalized_text)
    trail.append(RESOLVING_IDENTITY)
    resolution: dict[str, Any] = {'collected_document_id': document_id, DEDUP_POLICY_REVISION: policy_revision}
    if reason is not None:
        disposition = REJECTED_INCOMPLETE
        resolution['reason'] = reason
    else:
        key = identity_key(package.get('canonical_url_candidate') or package['final_url'])
        fingerprint = exact_fingerprint(normalized_text)
        match, article = _match(uow, key, fingerprint, normalized_text, policy)
        if match in (NEW_ARTICLE, NEW_REVISION):
            disposition = match
            if article is None:
                article = Article(article_id=id_factory(), identity_key=key, representative_source_id=package['source_id'])
            revision = _revision(
                package, article.article_id, article.next_revision_number, normalized_text, fingerprint, id_factory(),
                topic_rules,
            )
            uow.articles.save(article.with_revision(revision))
            resolution.update(article_id=revision.article_id, article_revision_id=revision.article_revision_id)
            _emit(uow, 'ArticleRevisionAccepted', 'Article', revision.article_id, revision.revision_number, {
                'article_id': revision.article_id,
                'article_revision_id': revision.article_revision_id,
                'collected_document_id': document_id,
                DEDUP_POLICY_REVISION: policy_revision,
                'source_id': revision.source_id,
                'source_revision': revision.source_revision,
            }, recovery_epoch, id_factory, deduplication_id)
        else:
            disposition = _resolve_duplicate(
                package, policy_revision, match, article, uow, tier_lookup, id_factory, recovery_epoch, deduplication_id,
            )
            resolution['article_id'] = article.article_id
    state = TERMINAL_STATES[disposition]
    resolution.update(disposition=disposition, state=state, state_trail=(*trail, state), resolved_at=_utc(clock()))
    issues = validate_collected_document_resolution(resolution)
    if issues:
        raise ValueError(f'invalid CollectedDocumentResolution: {issues}')
    uow.resolutions.save(resolution)
    return resolution


def resolve_collected_document(
    package: Mapping[str, Any],
    dedup_policy: Mapping[str, Any],
    uow: UnitOfWork,
    tier_lookup: SourceTierLookup,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
    *,
    topic_rules: Sequence[Mapping[str, Any]] = (),
    recovery_epoch: str = LOCAL_RECOVERY_EPOCH,
) -> dict[str, Any]:
    """Resolve one CollectedDocumentPackage into a CollectedDocumentResolution dict (CT-CNT-001).

    A structurally invalid package raises VALIDATION_ERROR before RECEIVED and writes nothing. A resolution already
    stored for the same collected_document_id and dedup_policy_revision is returned without new writes. OSError from a
    port raises FAILED_RETRYABLE and LookupError raises FAILED_FINAL; the unit of work then discards every staged
    write (D8-B-11).
    """
    issues = validate_collected_document_package(package)
    if issues:
        raise ResolveDocumentError(VALIDATION_ERROR, issues=issues)
    policy_revision = dedup_policy.get(DEDUP_POLICY_REVISION) if isinstance(dedup_policy, Mapping) else None
    if not isinstance(policy_revision, str) or not policy_revision or not {NEAR_DUPLICATE_JACCARD, SHINGLE_SIZE} <= set(dedup_policy):
        raise ValueError('dedup_policy needs dedup_policy_revision, near_duplicate_jaccard and shingle_size')
    try:
        with uow:
            stored = uow.resolutions.get(package['collected_document_id'], policy_revision)
            if stored is not None:
                return dict(stored)
            resolution = _resolve(
                package, dedup_policy, policy_revision, uow, tier_lookup, clock, id_factory, topic_rules, recovery_epoch,
            )
            uow.commit()
            return resolution
    except OSError as exc:
        raise ResolveDocumentError(FAILED_RETRYABLE, state=FAILED_RETRYABLE) from exc
    except LookupError as exc:
        raise ResolveDocumentError(FAILED_FINAL, state=FAILED_FINAL) from exc
