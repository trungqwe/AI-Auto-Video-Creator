"""B-8: EvaluateEventUpdate separates reposts from new developments (CT-CNT-005, CT-STATE-004, D8-B-07)."""
from __future__ import annotations

import itertools
import pathlib
import re
from datetime import datetime, timezone
from collections.abc import Mapping, Sequence

import pytest

from ingestion.application.evaluate_event_update import (
    EVENT_UPDATE_ACCEPTED,
    EVENT_UPDATE_CANDIDATE_KIND,
    EVENT_UPDATE_KIND,
    ClaimCandidateProvider,
    evaluate_event_update,
)
from ingestion.domain.article import Article, ArticleRevision
from ingestion.domain.event_update import (
    ACCEPTED_NEW_DEVELOPMENT,
    REJECTED_NO_NEW_FACT,
    REJECTED_REPOST,
    STATE_PROPOSED,
    STATES,
    UNCERTAIN,
    ClaimCandidate,
    parse_event_update_policy,
)
from ingestion.infrastructure.memory import InMemoryUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCES = (
    ROOT / 'src' / 'ingestion' / 'domain' / 'event_update.py',
    ROOT / 'src' / 'ingestion' / 'application' / 'evaluate_event_update.py',
)
BOUNDARY_RE = re.compile(r'(?m)^\s*(from|import)\s+(src\.|socket|requests|httpx|urllib|http\.client|psycopg)')
THRESHOLD_LITERAL_RE = re.compile(r'(?<![\w.])(0\.75|0\.85)(?![\w.])')
POLICY = {'event_update_policy_revision': 'event-update-policy-r1', 'repost_jaccard': 0.75, 'shingle_size': 3}
EPOCH = 'epoch-0001'
EVENT_ID = 'evt-0001'
T0 = '2026-10-18T08:00:00Z'
NOW = '2026-10-19T08:00:00Z'
TEXT_BASE = 'mua lon gay ngap nang tai trung tam thanh pho sang nay'
TEXT_NEAR = 'mua lon gay ngap nang tai trung tam thanh pho sang qua'
TEXT_SAME_FACT = 'nhieu tuyen pho trung tam bi ngap sau tran mua lon sang nay'
TEXT_BRIDGE = 'cau truot sap mot phan khien hai nguoi bi thuong toi nay'
TEXT_BRIDGE_OTHER = 'doan cau phia ngoai o da sap lam hai nguoi bi thuong'
TEXT_RESCUE = 'luc luong cuu ho da dua toan bo nguoi dan ra khoi khu vuc'
CLAIM_FLOOD = 'claim-flood'
CLAIM_BRIDGE = 'claim-bridge'
CLAIM_RESCUE = 'claim-rescue'
MISSING = object()
CLAIMS = {
    'art-a-r1': (CLAIM_FLOOD,),
    'art-b-r1': (CLAIM_FLOOD, CLAIM_BRIDGE),
    'art-c-r1': (CLAIM_FLOOD, CLAIM_RESCUE),
    'art-n-r1': (CLAIM_FLOOD, CLAIM_RESCUE),
    'art-s-r1': (CLAIM_FLOOD,),
    'art-d-r1': (CLAIM_BRIDGE,),
    'art-e-r1': (CLAIM_FLOOD, CLAIM_BRIDGE, CLAIM_RESCUE),
}


def _clock() -> datetime:
    return datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc)


def _revision(article_id: str, text: str, *, fingerprint: str | None = None) -> ArticleRevision:
    return ArticleRevision(
        article_revision_id=f'{article_id}-r1',
        article_id=article_id,
        revision_number=1,
        title=f'tieu de {article_id}',
        normalized_text=text,
        source_id=f'src-{article_id}',
        source_revision=1,
        collection_run_id='run-b8',
        collected_document_id=f'doc-{article_id}',
        requested_url=f'https://example.invalid/{article_id}',
        final_url=f'https://example.invalid/{article_id}',
        provenance_chain=({'step': 'final_fetch'},),
        raw_snapshot_ref=None,
        published_at=T0,
        published_at_confidence='high',
        fetched_at='2026-10-18T09:00:00Z',
        topic='thoi-tiet',
        topic_uncertain=False,
        exact_fingerprint=fingerprint or f'fp-{article_id}',
        media_discovery_refs=(),
        extractor_version='extractor-r1',
        normalizer_version='normalize-text-r1',
        is_complete=True,
        uncertain_fields=(),
    )


A = _revision('art-a', TEXT_BASE)
B = _revision('art-b', TEXT_BRIDGE)
C = _revision('art-c', TEXT_BASE, fingerprint='fp-art-a')
N = _revision('art-n', TEXT_NEAR)
S = _revision('art-s', TEXT_SAME_FACT)
D = _revision('art-d', TEXT_BRIDGE_OTHER)
E = _revision('art-e', TEXT_RESCUE)


class FakeClaimProvider:
    def __init__(self, claims: Mapping[str, Sequence[str]], *, evidence: str | None = None, raw: object = MISSING) -> None:
        self.claims = claims
        self.evidence = evidence
        self.raw = raw
        self.calls: list[str] = []

    def claim_candidates(self, revision: ArticleRevision) -> Sequence[ClaimCandidate]:
        self.calls.append(revision.article_revision_id)
        if self.raw is not MISSING:
            return self.raw  # type: ignore[return-value]
        return tuple(
            ClaimCandidate(ref, self.evidence or revision.article_revision_id)
            for ref in self.claims.get(revision.article_revision_id, ())
        )


def _member_refs(members: Sequence[ArticleRevision]) -> tuple[tuple[str, str], ...]:
    return tuple((r.article_id, r.article_revision_id) for r in members)


def _setup(*revisions: ArticleRevision, members: Sequence[ArticleRevision] | None = None):
    ids = itertools.count(1)
    outbox_ids = itertools.count(1)
    uow = InMemoryUnitOfWork(id_factory=lambda: f'outbox-{next(outbox_ids):04d}')
    for revision in revisions:
        with uow:
            uow.articles.save(
                Article(
                    article_id=revision.article_id,
                    identity_key=f'key-{revision.article_id}',
                    representative_source_id=revision.source_id,
                    revisions=(revision,),
                )
            )
            uow.commit()
    with uow:
        uow.events.save(
            {
                'event_id': EVENT_ID,
                'status': 'candidate',
                'revision': 1,
                'topic': 'thoi-tiet',
                'member_refs': _member_refs(revisions if members is None else members),
                'effective_time_range': (T0, T0),
                'event_link_policy_revision': 'event-link-policy-r1',
                'created_at': T0,
                'updated_at': T0,
            }
        )
        uow.commit()
    return uow, lambda: f'b8-{next(ids):04d}'


def _save_members(uow: InMemoryUnitOfWork, members: Sequence[ArticleRevision]) -> None:
    with uow:
        event = dict(uow.events.get(EVENT_ID))
        event['member_refs'] = _member_refs(members)
        uow.events.save(event)
        uow.commit()


def _ref(revision: ArticleRevision) -> dict[str, str]:
    return {'article_id': revision.article_id, 'article_revision_id': revision.article_revision_id}


def _evaluate(uow: InMemoryUnitOfWork, ids, revision: ArticleRevision, provider: FakeClaimProvider, policy: Mapping = POLICY):
    return evaluate_event_update(EVENT_ID, _ref(revision), provider, policy, uow, _clock, ids, recovery_epoch=EPOCH)


def _assert_no_writes(uow: InMemoryUnitOfWork) -> None:
    assert uow.committed_outbox() == ()
    assert uow.records.list(EVENT_UPDATE_KIND) == ()
    assert uow.records.list(EVENT_UPDATE_CANDIDATE_KIND) == ()


def test_states_follow_ct_state_004() -> None:
    assert STATES == (ACCEPTED_NEW_DEVELOPMENT, REJECTED_REPOST, REJECTED_NO_NEW_FACT, UNCERTAIN) == (
        'ACCEPTED_NEW_DEVELOPMENT',
        'REJECTED_REPOST',
        'REJECTED_NO_NEW_FACT',
        'UNCERTAIN',
    )
    assert STATE_PROPOSED == 'PROPOSED'


def test_new_claim_from_non_repost_is_accepted() -> None:
    uow, ids = _setup(A, B)
    r = _evaluate(uow, ids, B, FakeClaimProvider(CLAIMS))
    assert (r.state, r.is_new_development, r.reason) == (ACCEPTED_NEW_DEVELOPMENT, True, 'new_claim_found')
    assert r.new_claim_refs == (CLAIM_BRIDGE,)
    assert r.source_revision_refs == ('art-b-r1', 'art-a-r1')
    assert r.confidence == pytest.approx(0.5)
    assert r.event_update_revision == 1
    assert r.event_update_id is not None and r.domain_event_id is not None
    assert (r.event_id, r.article_id, r.article_revision_id, r.event_update_policy_revision) == (
        EVENT_ID,
        'art-b',
        'art-b-r1',
        'event-update-policy-r1',
    )


def test_exact_repost_from_new_source_is_rejected_even_with_new_claim() -> None:
    uow, ids = _setup(A, C)
    r = _evaluate(uow, ids, C, FakeClaimProvider(CLAIMS))
    assert (r.state, r.is_new_development, r.reason) == (REJECTED_REPOST, False, 'repost_of_event_member')
    assert r.new_claim_refs == ()
    assert r.confidence == 1.0
    assert r.event_update_id is None
    assert r.event_update_revision is None
    assert r.domain_event_id is None
    assert uow.committed_outbox() == ()
    assert uow.records.list(EVENT_UPDATE_KIND) == ()


def test_near_duplicate_repost_is_rejected() -> None:
    uow, ids = _setup(A, N)
    r = _evaluate(uow, ids, N, FakeClaimProvider(CLAIMS))
    assert r.state == REJECTED_REPOST
    assert r.confidence == pytest.approx(9 / 11)
    assert r.new_claim_refs == ()


def test_new_source_with_known_claims_only_is_rejected_no_new_fact() -> None:
    uow, ids = _setup(A, S)
    r = _evaluate(uow, ids, S, FakeClaimProvider(CLAIMS))
    assert (r.state, r.reason, r.confidence, r.new_claim_refs, r.is_new_development) == (
        REJECTED_NO_NEW_FACT,
        'all_claims_known',
        0.0,
        (),
        False,
    )


def test_empty_claim_provider_is_uncertain() -> None:
    uow, ids = _setup(A, B)
    r = _evaluate(uow, ids, B, FakeClaimProvider({}))
    assert (r.state, r.reason, r.is_new_development, r.new_claim_refs) == (
        UNCERTAIN,
        'no_claim_candidate',
        False,
        (),
    )


def test_claims_without_evidence_on_subject_revision_are_ignored() -> None:
    uow, ids = _setup(A, B)
    r = _evaluate(uow, ids, B, FakeClaimProvider(CLAIMS, evidence='art-a-r1'))
    assert (r.state, r.reason) == (UNCERTAIN, 'no_claim_candidate')


def test_event_without_baseline_revision_is_uncertain() -> None:
    uow, ids = _setup(B)
    r = _evaluate(uow, ids, B, FakeClaimProvider(CLAIMS))
    assert (r.state, r.reason) == (UNCERTAIN, 'no_baseline_revision')
    assert r.source_revision_refs == ('art-b-r1',)


def test_non_member_subject_is_compared_with_all_members() -> None:
    uow, ids = _setup(A, C, members=(A,))
    r = _evaluate(uow, ids, C, FakeClaimProvider(CLAIMS))
    assert r.state == REJECTED_REPOST
    uow2, ids2 = _setup(A, B, members=(A,))
    r2 = _evaluate(uow2, ids2, B, FakeClaimProvider(CLAIMS))
    assert r2.state == ACCEPTED_NEW_DEVELOPMENT
    assert r2.source_revision_refs == ('art-b-r1', 'art-a-r1')


@pytest.mark.parametrize(
    ('subject', 'claims', 'expected'),
    [
        (B, CLAIMS, ACCEPTED_NEW_DEVELOPMENT),
        (C, CLAIMS, REJECTED_REPOST),
        (S, CLAIMS, REJECTED_NO_NEW_FACT),
        (B, {}, UNCERTAIN),
    ],
    ids=['accepted', 'repost', 'no_new_fact', 'uncertain'],
)
def test_only_accepted_writes_event_update_and_emits_event(
    subject: ArticleRevision,
    claims: Mapping[str, Sequence[str]],
    expected: str,
) -> None:
    uow, ids = _setup(A, subject)
    r = _evaluate(uow, ids, subject, FakeClaimProvider(claims))
    assert r.state == expected
    updates = uow.records.list(EVENT_UPDATE_KIND)
    outbox = uow.committed_outbox()
    if expected == ACCEPTED_NEW_DEVELOPMENT:
        assert len(updates) == 1
        assert [x.event_type for x in outbox] == [EVENT_UPDATE_ACCEPTED]
    else:
        assert updates == ()
        assert outbox == ()
        assert r.event_update_id is None
    record = uow.records.get(EVENT_UPDATE_CANDIDATE_KIND, r.event_update_candidate_id)
    assert record is not None
    assert record['state_history'] == (STATE_PROPOSED, expected)
    assert record['state'] == expected
    assert record['evaluated_at'] == NOW


def test_event_update_accepted_envelope_carries_refs_only() -> None:
    uow, ids = _setup(A, B)
    r = _evaluate(uow, ids, B, FakeClaimProvider(CLAIMS))
    (rec,) = uow.committed_outbox()
    env = rec.payload
    assert rec.aggregate_id == r.event_update_id
    assert rec.deduplication_id == f'EventUpdateAccepted:{r.event_update_candidate_id}'
    assert (env['event_name'], env['aggregate_type'], env['aggregate_id'], env['aggregate_revision']) == (
        'EventUpdateAccepted',
        'EventUpdate',
        r.event_update_id,
        1,
    )
    assert (env['producer'], env['recovery_epoch'], env['event_id']) == ('B', EPOCH, r.domain_event_id)
    assert env['payload'] == {
        'event_update_id': r.event_update_id,
        'event_id': EVENT_ID,
        'event_update_revision': 1,
        'article_revision_id': 'art-b-r1',
        'new_claim_refs': [CLAIM_BRIDGE],
        'source_revision_refs': ['art-b-r1', 'art-a-r1'],
        'event_update_policy_revision': 'event-update-policy-r1',
    }
    for text in (TEXT_BASE, TEXT_BRIDGE):
        assert text not in repr(uow.committed_outbox())


def test_event_update_record_matches_evaluation() -> None:
    uow, ids = _setup(A, B)
    r = _evaluate(uow, ids, B, FakeClaimProvider(CLAIMS))
    u = uow.records.get(EVENT_UPDATE_KIND, r.event_update_id)
    assert u is not None
    assert (u['event_id'], u['event_update_revision'], u['event_update_candidate_id'], u['article_revision_id']) == (
        EVENT_ID,
        1,
        r.event_update_candidate_id,
        'art-b-r1',
    )
    assert (u['new_claim_refs'], u['source_revision_refs'], u['state'], u['accepted_at']) == (
        (CLAIM_BRIDGE,),
        ('art-b-r1', 'art-a-r1'),
        ACCEPTED_NEW_DEVELOPMENT,
        NOW,
    )


def test_evaluation_never_changes_articles_or_event() -> None:
    uow, ids = _setup(A, B)
    before_articles = {a.article_id: a for a in uow.articles.list_all()}
    before_event = dict(uow.events.get(EVENT_ID))
    _evaluate(uow, ids, B, FakeClaimProvider(CLAIMS))
    assert {a.article_id: a for a in uow.articles.list_all()} == before_articles
    assert dict(uow.events.get(EVENT_ID)) == before_event


def test_later_member_is_not_baseline_and_update_revisions_increment() -> None:
    uow, ids = _setup(A, B, E)
    provider = FakeClaimProvider(CLAIMS)
    first = _evaluate(uow, ids, B, provider)
    second = _evaluate(uow, ids, E, provider)
    assert (first.state, first.new_claim_refs, first.event_update_revision, first.source_revision_refs) == (
        ACCEPTED_NEW_DEVELOPMENT,
        (CLAIM_BRIDGE,),
        1,
        ('art-b-r1', 'art-a-r1'),
    )
    assert (second.state, second.new_claim_refs, second.event_update_revision, second.source_revision_refs) == (
        ACCEPTED_NEW_DEVELOPMENT,
        (CLAIM_RESCUE,),
        2,
        ('art-e-r1', 'art-a-r1', 'art-b-r1'),
    )
    assert second.confidence == pytest.approx(1 / 3)
    assert first.event_update_id != second.event_update_id
    assert len(uow.committed_outbox()) == 2


def test_claim_from_accepted_update_is_known_for_new_source() -> None:
    uow, ids = _setup(A, B, D, members=(A, B))
    provider = FakeClaimProvider(CLAIMS)
    assert _evaluate(uow, ids, B, provider).state == ACCEPTED_NEW_DEVELOPMENT
    _save_members(uow, (A, D))
    r = _evaluate(uow, ids, D, provider)
    assert (r.state, r.reason) == (REJECTED_NO_NEW_FACT, 'all_claims_known')
    assert len(uow.committed_outbox()) == 1


def test_replay_with_same_policy_revision_writes_nothing() -> None:
    uow, ids = _setup(A, B)
    first = _evaluate(uow, ids, B, FakeClaimProvider(CLAIMS))
    outbox_before = uow.committed_outbox()
    assert _evaluate(uow, ids, B, FakeClaimProvider(CLAIMS)) == first
    assert uow.committed_outbox() == outbox_before
    assert len(uow.records.list(EVENT_UPDATE_CANDIDATE_KIND)) == 1
    assert len(uow.records.list(EVENT_UPDATE_KIND)) == 1


def test_new_policy_revision_never_accepts_same_claim_twice() -> None:
    uow, ids = _setup(A, B)
    assert _evaluate(uow, ids, B, FakeClaimProvider(CLAIMS), policy=POLICY).state == ACCEPTED_NEW_DEVELOPMENT
    r2 = _evaluate(
        uow,
        ids,
        B,
        FakeClaimProvider(CLAIMS),
        policy={**POLICY, 'event_update_policy_revision': 'event-update-policy-r2'},
    )
    assert (r2.state, r2.event_update_policy_revision) == (REJECTED_NO_NEW_FACT, 'event-update-policy-r2')
    assert len(uow.records.list(EVENT_UPDATE_CANDIDATE_KIND)) == 2
    assert len(uow.committed_outbox()) == 1


@pytest.mark.parametrize(
    ('overrides', 'expected'),
    [
        ({}, REJECTED_REPOST),
        ({'repost_jaccard': 0.85}, ACCEPTED_NEW_DEVELOPMENT),
        ({'shingle_size': 13}, ACCEPTED_NEW_DEVELOPMENT),
    ],
)
def test_repost_threshold_comes_from_policy(overrides: dict, expected: str) -> None:
    uow, ids = _setup(A, N)
    r = _evaluate(uow, ids, N, FakeClaimProvider(CLAIMS), policy={**POLICY, **overrides})
    assert r.state == expected


def test_exact_fingerprint_is_repost_at_strictest_threshold() -> None:
    uow, ids = _setup(A, C)
    r = _evaluate(uow, ids, C, FakeClaimProvider(CLAIMS), policy={**POLICY, 'repost_jaccard': 1.0})
    assert (r.state, r.confidence) == (REJECTED_REPOST, 1.0)


def test_thresholds_are_not_hard_coded_in_source() -> None:
    for path in SOURCES:
        assert not THRESHOLD_LITERAL_RE.search(path.read_text(encoding='utf-8')), path.name


@pytest.mark.parametrize(
    'overrides',
    [
        {'event_update_policy_revision': ''},
        {'event_update_policy_revision': 'event update r1'},
        {'repost_jaccard': 0},
        {'repost_jaccard': 1.5},
        {'repost_jaccard': True},
        {'repost_jaccard': '0.8'},
        {'repost_jaccard': float('nan')},
        {'shingle_size': 0},
        {'shingle_size': True},
        {'shingle_size': 2.5},
    ],
)
def test_invalid_policy_fails_closed_without_writes(overrides: dict) -> None:
    uow, ids = _setup(A, B)
    with pytest.raises(ValueError):
        _evaluate(uow, ids, B, FakeClaimProvider(CLAIMS), policy={**POLICY, **overrides})
    _assert_no_writes(uow)


@pytest.mark.parametrize('key', sorted(POLICY))
def test_policy_missing_key_fails_closed(key: str) -> None:
    with pytest.raises(ValueError):
        parse_event_update_policy({k: v for k, v in POLICY.items() if k != key})


def test_non_mapping_policy_fails_closed() -> None:
    with pytest.raises(ValueError):
        parse_event_update_policy(['event-update-policy-r1'])


@pytest.mark.parametrize(
    'ref',
    [
        'art-b-r1',
        ['art-b-r1'],
        {'article_id': 'art-b'},
        {'article_id': 'art-b', 'article_revision_id': ''},
    ],
)
def test_invalid_ref_fails_closed_without_writes(ref: object) -> None:
    uow, ids = _setup(A, B)
    with pytest.raises(ValueError):
        evaluate_event_update(EVENT_ID, ref, FakeClaimProvider(CLAIMS), POLICY, uow, _clock, ids, recovery_epoch=EPOCH)  # type: ignore[arg-type]
    _assert_no_writes(uow)


@pytest.mark.parametrize('event_id', ['', 'evt 1', None])
def test_invalid_event_id_fails_closed_without_writes(event_id: object) -> None:
    uow, ids = _setup(A, B)
    with pytest.raises(ValueError):
        evaluate_event_update(event_id, _ref(B), FakeClaimProvider(CLAIMS), POLICY, uow, _clock, ids, recovery_epoch=EPOCH)  # type: ignore[arg-type]
    _assert_no_writes(uow)


@pytest.mark.parametrize('epoch', ['', 'epoch 1', None])
def test_invalid_recovery_epoch_fails_closed_without_writes(epoch: object) -> None:
    uow, ids = _setup(A, B)
    with pytest.raises(ValueError):
        evaluate_event_update(EVENT_ID, _ref(B), FakeClaimProvider(CLAIMS), POLICY, uow, _clock, ids, recovery_epoch=epoch)  # type: ignore[arg-type]
    _assert_no_writes(uow)


def test_provider_without_protocol_fails_closed() -> None:
    uow, ids = _setup(A, B)
    with pytest.raises(ValueError):
        evaluate_event_update(EVENT_ID, _ref(B), object(), POLICY, uow, _clock, ids, recovery_epoch=EPOCH)  # type: ignore[arg-type]
    _assert_no_writes(uow)


@pytest.mark.parametrize('raw', [None, 'claim-x', [CLAIM_BRIDGE], [{'claim_ref': CLAIM_BRIDGE}]])
def test_invalid_provider_output_fails_closed_without_writes(raw: object) -> None:
    uow, ids = _setup(A, B)
    with pytest.raises(ValueError):
        _evaluate(uow, ids, B, FakeClaimProvider(CLAIMS, raw=raw))
    _assert_no_writes(uow)


@pytest.mark.parametrize(
    ('claim_ref', 'evidence'),
    [
        ('', 'art-b-r1'),
        ('claim x', 'art-b-r1'),
        (1, 'art-b-r1'),
        (CLAIM_BRIDGE, ''),
    ],
)
def test_claim_candidate_rejects_invalid_refs(claim_ref: object, evidence: object) -> None:
    with pytest.raises(ValueError):
        ClaimCandidate(claim_ref, evidence)  # type: ignore[arg-type]


def test_unknown_event_or_revision_raises_lookup_error_without_writes() -> None:
    uow, ids = _setup(A, B)
    with pytest.raises(LookupError):
        evaluate_event_update('evt-missing', _ref(B), FakeClaimProvider(CLAIMS), POLICY, uow, _clock, ids, recovery_epoch=EPOCH)
    with pytest.raises(LookupError):
        evaluate_event_update(
            EVENT_ID,
            {'article_id': 'art-b', 'article_revision_id': 'art-b-r9'},
            FakeClaimProvider(CLAIMS),
            POLICY,
            uow,
            _clock,
            ids,
            recovery_epoch=EPOCH,
        )
    _assert_no_writes(uow)


def test_fake_provider_satisfies_protocol() -> None:
    assert isinstance(FakeClaimProvider({}), ClaimCandidateProvider) and not isinstance(object(), ClaimCandidateProvider)


def test_new_modules_respect_check_b_import_boundary() -> None:
    assert BOUNDARY_RE.search('from src.ingestion.domain import event_update')
    assert BOUNDARY_RE.search('import requests')
    for path in SOURCES:
        assert path.exists()
        assert not BOUNDARY_RE.search(path.read_text(encoding='utf-8'))
    assert not (ROOT / 'tests/unit/ingestion/__init__.py').exists()
    assert not (ROOT / 'tests/integration/ingestion/__init__.py').exists()
