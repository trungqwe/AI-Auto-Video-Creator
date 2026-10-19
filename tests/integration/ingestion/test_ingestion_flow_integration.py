"""B-12: integrated A -> B flow with fakes A/G/C/D/J, InMemoryUnitOfWork and a synthetic corpus.

Covers TST-INT-INV-005, TST-E2E-002, TST-E2E-003, TST-E2E-004, TST-CTR-INV-006, TST-SEC-INV-012 and TST-SEC-INV-020.
Fakes: A collector (package loader), G workflow (ActivityRequest and grant), C catalog (media), D creative (drafts and timeline gate), J secret broker.
"""
import copy
import itertools
import json
import pathlib
import re
from datetime import datetime, timezone

import pytest

from ingestion.application.activity_handler import ACTIVITY_NAME, ResolveActivityDeps, handle_resolve_activity
from ingestion.application.evaluate_event_update import evaluate_event_update
from ingestion.application.resolve_document import attached_media_refs
from ingestion.application.resolve_event_link import resolve_event_link
from ingestion.application.source_set import (
    FROM_THEN_TO_NOW,
    MULTI_ARTICLE_EVENT,
    SINGLE_ARTICLE,
    SourceSetRejected,
    build_source_set,
    fingerprint_source_refs,
)
from ingestion.domain.event_update import ClaimCandidate
from ingestion.infrastructure.memory import InMemorySourceTierLookup, InMemoryUnitOfWork

HERE = pathlib.Path(__file__).resolve().parent
CORPUS_PATH = HERE / 'fixtures' / 'ingestion_corpus_v1.json'
RECOVERY_EPOCH = 'epoch-b12-0001'
ACCEPTED = ('NEW_ARTICLE', 'NEW_REVISION')
ACCEPTED_UPDATE = 'ACCEPTED_NEW_DEVELOPMENT'
RESOLUTIONS = frozenset({'NEW_ARTICLE', 'NEW_REVISION', 'DUPLICATE_MEDIA_ONLY', 'DUPLICATE_NO_NEW_VALUE', 'REJECTED_INCOMPLETE'})
LINKS = frozenset({'linked', 'kept_separate', 'needs_more_evidence'})
UPDATES = frozenset({'ACCEPTED_NEW_DEVELOPMENT', 'REJECTED_REPOST', 'REJECTED_NO_NEW_FACT', 'UNCERTAIN'})
CLUSTER_KINDS = frozenset({'exact', 'near', 'repost_new_media', 'revision'})
SCENARIOS = frozenset({'first', 'no_new_fact', 'separate', 'repost', 'real_update'})
REVISION_KEYS = {'dedup_policy_revision': 'dedup', 'event_link_policy_revision': 'event_link', 'event_update_policy_revision': 'event_update'}
URL_RE = re.compile(r'https://[a-z0-9.-]+\.invalid/\S*', re.IGNORECASE)


def _corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding='utf-8'))


def _entries(corpus: dict) -> list[dict]:
    entries = [dict(item, group='news', scenario='news') for item in corpus['news']]
    for cluster in corpus['duplicate_clusters']:
        entries += [dict(item, group='duplicate', scenario=cluster['kind']) for item in cluster['items']]
    return entries + [dict(item, group='timeline') for item in corpus['event_timeline_set']]


def _request(document_id: str) -> dict:
    return {
        'workflow_id': 'workflow-b12',
        'workflow_run_id': 'workflow-run-b12',
        'stage_run_id': 'stage-run-b12',
        'activity_name': ACTIVITY_NAME,
        'activity_version': '1.0.0',
        'input_refs': [{'ref_type': 'collected_document_package', 'ref_id': document_id}],
        'operation_key': 'op-resolve-' + document_id,
        'capability_requirements': {},
        'retry_policy_ref': 'retry-policy-b12',
        'execution_grant': {'grant_id': 'grant-b12', 'execution_generation': 1, 'recovery_epoch': RECOVERY_EPOCH},
    }


def _package(item: dict, corpus: dict) -> dict:
    return {
        'collected_document_id': item['id'],
        'source_id': corpus['sources'][item['source']]['source_id'],
        'source_revision': 1,
        'collection_run_id': 'collection-run-b12',
        'requested_url': item['url'],
        'final_url': item['url'],
        'fetched_at': item['published_at'],
        'http_observation': {'status': 200, 'media_type': 'text/html'},
        'extraction_disposition': 'SUCCESS',
        'extractor_version': '1.0.0',
        'provenance_chain': [{'step': 'final_fetch', 'url': item['url']}],
        'warnings': [],
        'content_eligibility': item.get('eligibility', 'candidate'),
        'published_at_candidate': item['published_at'],
        'extracted_content_candidate': {'title': item['title'], 'text': item['text'], 'language': 'en'},
        'media_discoveries': copy.deepcopy(item.get('media', [])),
    }


class FakeCollector:  # fake A: serves packages built from the corpus
    def __init__(self, packages: dict) -> None:
        self.packages = packages
        self.calls: list[str] = []
        self.failures: dict[str, Exception] = {}

    def __call__(self, ref: dict) -> dict:
        self.calls.append(ref['ref_id'])
        failure = self.failures.pop(ref['ref_id'], None)
        if failure is not None:
            raise failure
        return copy.deepcopy(self.packages[ref['ref_id']])


class FakeClaims:  # claim provider port used by event update
    def __init__(self, claims: dict) -> None:
        self.claims = claims

    def claim_candidates(self, revision):
        refs = self.claims.get(revision.collected_document_id, ())
        return tuple(ClaimCandidate(ref, revision.article_revision_id) for ref in refs)


class _OutboxConsumer:
    def __init__(self) -> None:
        self.seen: set[str] = set()

    def new_records(self, outbox, event_type: str) -> list:
        fresh = [r for r in outbox if r.event_type == event_type and r.event_id not in self.seen]
        self.seen.update(r.event_id for r in fresh)
        return fresh


class FakeCatalog(_OutboxConsumer):  # fake C: keeps media discoveries announced by duplicate events
    def __init__(self) -> None:
        super().__init__()
        self.media_by_article: dict[str, list[str]] = {}

    def consume(self, outbox) -> None:
        for record in self.new_records(outbox, 'DuplicateDocumentResolved'):
            payload = record.payload['payload']
            self.media_by_article.setdefault(payload['article_id'], []).extend(payload.get('new_media_discovery_refs', []))


class FakeCreative(_OutboxConsumer):  # fake D: one draft per accepted revision, timeline gate over source sets
    def __init__(self, uow) -> None:
        super().__init__()
        self.uow = uow
        self.drafts: list[str] = []

    def consume(self, outbox) -> None:
        self.drafts += [r.payload['payload']['article_revision_id'] for r in self.new_records(outbox, 'ArticleRevisionAccepted')]

    def request_timeline(self, event_id: str):
        try:
            return 'authorized', build_source_set(FROM_THEN_TO_NOW, event_id, self.uow)
        except SourceSetRejected as exc:
            return 'rejected', exc.reason


class FakeSecretBroker:  # fake J: owns the canary and reports which artifacts leak it
    def __init__(self, secrets) -> None:
        self._secrets = tuple(secrets)

    def leaks(self, **artifacts) -> list[str]:
        return [name for name, artifact in artifacts.items() if any(secret in repr(artifact) for secret in self._secrets)]


class Flow:
    def __init__(self) -> None:
        self.corpus = corpus = _corpus()
        outbox_ids, ids = itertools.count(1), itertools.count(1)
        self.uow = InMemoryUnitOfWork(id_factory=lambda: f'outbox-{next(outbox_ids)}')
        self.new_id = lambda: f'b12-{next(ids):05d}'
        self.clock = lambda: datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
        self.entries = _entries(corpus)
        tiers = {source['source_id']: source['tier'] for source in corpus['sources'].values()}
        self.collector = FakeCollector({entry['id']: _package(entry, corpus) for entry in self.entries})
        self.deps = ResolveActivityDeps(
            self.uow, InMemorySourceTierLookup(tiers), self.new_id, copy.deepcopy(corpus['policies']['dedup']), corpus['topic_rules'],
        )
        self.claims = FakeClaims({entry['id']: entry.get('claims', []) for entry in self.entries})
        self.catalog, self.creative = FakeCatalog(), FakeCreative(self.uow)
        self.broker = FakeSecretBroker([corpus['canary']])
        self.requests: list[dict] = []
        self.results: dict[str, dict] = {}
        self.resolutions: dict[str, dict] = {}
        self.links: dict = {}
        self.updates: dict = {}

    def handle(self, request: dict) -> dict:
        return handle_resolve_activity(request, self.collector, self.deps, self.clock)

    def run(self) -> 'Flow':
        policies = self.corpus['policies']
        revision = policies['dedup']['dedup_policy_revision']
        for entry in self.entries:
            request = _request(entry['id'])
            self.requests.append(request)
            self.results[entry['id']] = self.handle(request)
            resolution = dict(self.uow.resolutions.get(entry['id'], revision))
            self.resolutions[entry['id']] = resolution
            if entry['group'] == 'timeline' and resolution['disposition'] in ACCEPTED:
                ref = {'article_id': resolution['article_id'], 'article_revision_id': resolution['article_revision_id']}
                (link,) = resolve_event_link(
                    [ref], policies['event_link'], self.uow, self.clock, self.new_id, recovery_epoch=RECOVERY_EPOCH,
                )
                self.links[entry['id']] = link
                if 'update' in entry['expected']:
                    self.updates[entry['id']] = evaluate_event_update(
                        link.event_id, ref, self.claims, policies['event_update'], self.uow, self.clock, self.new_id,
                        recovery_epoch=RECOVERY_EPOCH,
                    )
        outbox = self.uow.committed_outbox()
        self.catalog.consume(outbox)
        self.creative.consume(outbox)
        return self

    def anchors(self) -> dict[str, str]:
        return {
            entry['event']: self.links[entry['id']].event_id
            for entry in self.entries
            if entry['group'] == 'timeline' and self.links[entry['id']].is_new_event
        }


@pytest.fixture(scope='module')
def flow() -> Flow:
    return Flow().run()


def _cluster(flow: Flow, kind: str) -> list[dict]:
    return next(item for item in flow.corpus['duplicate_clusters'] if item['kind'] == kind)['items']


def test_corpus_is_synthetic_and_covers_required_groups() -> None:
    corpus = _corpus()
    assert corpus['corpus_version'] == 'ingestion-corpus-v1'
    assert corpus['synthetic'] is True
    assert corpus['news']
    assert {cluster['kind'] for cluster in corpus['duplicate_clusters']} == CLUSTER_KINDS
    assert {item['scenario'] for item in corpus['event_timeline_set']} >= SCENARIOS
    entries = _entries(corpus)
    assert len({entry['id'] for entry in entries}) == len(entries)
    for entry in entries:
        assert URL_RE.fullmatch(entry['url']), entry['id']
        assert entry['source'] in corpus['sources'], entry['id']


def test_every_corpus_item_has_expected_disposition() -> None:
    for entry in _entries(_corpus()):
        expected = entry['expected']
        assert expected['resolution'] in RESOLUTIONS, entry['id']
        if entry['group'] == 'timeline':
            assert expected['link'] in LINKS, entry['id']
            assert isinstance(expected['is_new_event'], bool), entry['id']
            assert ('update' in expected) == (entry['scenario'] in {'repost', 'real_update', 'no_new_fact'}), entry['id']
            assert expected.get('update', 'UNCERTAIN') in UPDATES, entry['id']


def test_resolution_dispositions_match_the_corpus_for_every_item(flow: Flow) -> None:
    revision = flow.corpus['policies']['dedup']['dedup_policy_revision']
    for entry in flow.entries:
        result, resolution, expected = flow.results[entry['id']], flow.resolutions[entry['id']], entry['expected']
        assert result['disposition'] == 'succeeded', entry['id']
        assert result['output_refs'] == [{'ref_type': 'collected_document_resolution', 'ref_id': entry['id'] + ':' + revision}]
        assert resolution['disposition'] == expected['resolution'], entry['id']
        assert resolution.get('reason') == expected.get('reason'), entry['id']


def test_chain_runs_through_every_stage_and_fake(flow: Flow) -> None:
    timeline = [entry for entry in flow.entries if entry['group'] == 'timeline']
    assert flow.collector.calls == [entry['id'] for entry in flow.entries]
    assert [request['input_refs'][0]['ref_id'] for request in flow.requests] == flow.collector.calls
    assert set(flow.links) == {entry['id'] for entry in timeline}
    assert set(flow.updates) == {entry['id'] for entry in timeline if 'update' in entry['expected']}
    assert len(flow.uow.committed('event_link_candidate')) == len(flow.links)
    assert len(flow.uow.committed('event_update_candidate')) == len(flow.updates)
    assert flow.creative.drafts and flow.catalog.media_by_article
    for mode in (MULTI_ARTICLE_EVENT, FROM_THEN_TO_NOW):
        assert build_source_set(mode, flow.anchors()['flood'], flow.uow).source_refs


def test_duplicates_add_no_article_or_draft_and_keep_new_media(flow: Flow) -> None:
    # TST-INT-INV-005, TST-E2E-002
    articles = flow.uow.committed('article')
    revisions = [revision for article in articles for revision in article.revisions]
    drafted = {revision.collected_document_id for revision in revisions}
    duplicates = [e for e in flow.entries if flow.resolutions[e['id']]['disposition'].startswith('DUPLICATE')]
    assert duplicates
    for entry in flow.entries:
        assert (entry['id'] in drafted) == (flow.resolutions[entry['id']]['disposition'] in ACCEPTED), entry['id']
    assert sorted(flow.creative.drafts) == sorted(revision.article_revision_id for revision in revisions)
    assert len(flow.uow.committed('dedup_evidence')) == len(duplicates)
    first, with_media, repeat = _cluster(flow, 'repost_new_media')
    article_id = flow.resolutions[first['id']]['article_id']
    new_ref = with_media['media'][0]['ref']
    assert flow.resolutions[with_media['id']]['article_id'] == flow.resolutions[repeat['id']]['article_id'] == article_id
    assert flow.catalog.media_by_article[article_id] == [new_ref]
    assert attached_media_refs(flow.uow, article_id) == (new_ref,)
    assert len(flow.uow.articles.get(article_id).revisions) == 1
    original, mirror, wire = _cluster(flow, 'exact')
    attachment = flow.uow.records.get('article_media_attachment', flow.resolutions[original['id']]['article_id'])
    assert flow.corpus['sources'][wire['source']]['source_id'] in attachment['source_ids']
    base, near = _cluster(flow, 'near')
    assert flow.resolutions[near['id']]['article_id'] == flow.resolutions[base['id']]['article_id']


def test_changed_text_at_the_same_identity_is_a_new_revision(flow: Flow) -> None:
    first, changed, repeat = _cluster(flow, 'revision')
    article = flow.uow.articles.get(flow.resolutions[first['id']]['article_id'])
    assert flow.resolutions[changed['id']]['article_id'] == article.article_id
    assert [revision.revision_number for revision in article.revisions] == [1, 2]
    assert flow.resolutions[changed['id']]['article_revision_id'] == article.revisions[1].article_revision_id
    assert flow.resolutions[repeat['id']]['disposition'] == 'DUPLICATE_NO_NEW_VALUE'


def test_event_link_dispositions_match_the_corpus(flow: Flow) -> None:
    timeline = [entry for entry in flow.entries if entry['group'] == 'timeline']
    anchors = flow.anchors()
    assert len(set(anchors.values())) == len(anchors) == len({entry['event'] for entry in timeline})
    for entry in timeline:
        link, expected = flow.links[entry['id']], entry['expected']
        assert link.disposition == expected['link'], entry['id']
        assert link.is_new_event is expected['is_new_event'], entry['id']
        assert link.event_id == anchors[entry['event']], entry['id']
        assert link.event_link_policy_revision == flow.corpus['policies']['event_link']['event_link_policy_revision']


def test_event_update_dispositions_match_the_corpus(flow: Flow) -> None:
    # TST-E2E-003, TST-E2E-004
    timeline = [entry for entry in flow.entries if 'update' in entry['expected']]
    for entry in timeline:
        evaluation = flow.updates[entry['id']]
        assert evaluation.state == entry['expected']['update'], entry['id']
        assert evaluation.is_new_development is (evaluation.state == ACCEPTED_UPDATE), entry['id']
    accepted = [r for r in flow.uow.committed_outbox() if r.event_type == 'EventUpdateAccepted']
    accepted_revisions = {r.payload['payload']['article_revision_id'] for r in accepted}
    real = [e for e in timeline if e['expected']['update'] == ACCEPTED_UPDATE]
    assert {e['scenario'] for e in real} == {'real_update'}
    assert accepted_revisions == {flow.links[e['id']].article_revision_id for e in real}
    assert len(flow.uow.committed('event_update')) == len(accepted)
    for entry in timeline:
        if entry['scenario'] in ('repost', 'no_new_fact'):
            assert flow.links[entry['id']].article_revision_id not in accepted_revisions
            assert flow.updates[entry['id']].event_update_id is None


def test_timeline_mode_needs_an_accepted_update(flow: Flow) -> None:
    # TST-CTR-INV-006, TST-E2E-003, TST-E2E-004
    anchors = flow.anchors()
    decision, source_set = flow.creative.request_timeline(anchors['flood'])
    assert decision == 'authorized'
    assert source_set.eligibility_reason == 'from_then_to_now_eligible'
    assert source_set.source_set_fingerprint == fingerprint_source_refs(source_set.source_refs)
    assert flow.creative.request_timeline(anchors['flood'])[1].source_set_fingerprint == source_set.source_set_fingerprint
    flood = [e for e in flow.entries if e['group'] == 'timeline' and e['event'] == 'flood']
    by_revision = {flow.links[e['id']].article_revision_id: e for e in flood}
    assert {ref['article_revision_id'] for ref in source_set.source_refs} == set(by_revision)
    for ref in source_set.source_refs:
        assert ref['source_id'] == flow.corpus['sources'][by_revision[ref['article_revision_id']]['source']]['source_id']
    for label in ('harbour', 'drought'):
        assert flow.creative.request_timeline(anchors[label]) == ('rejected', 'event_update_not_accepted')


def test_other_production_modes_pin_the_stored_revisions(flow: Flow) -> None:
    anchors = flow.anchors()
    assert len(build_source_set(MULTI_ARTICLE_EVENT, anchors['flood'], flow.uow).source_refs) == 3
    assert len(build_source_set(MULTI_ARTICLE_EVENT, anchors['harbour'], flow.uow).source_refs) == 2
    with pytest.raises(SourceSetRejected) as rejected:
        build_source_set(MULTI_ARTICLE_EVENT, anchors['drought'], flow.uow)
    assert rejected.value.reason == 'event_needs_two_linked_articles'
    first, changed, _ = _cluster(flow, 'revision')
    single = build_source_set(SINGLE_ARTICLE, flow.resolutions[first['id']]['article_id'], flow.uow)
    assert [ref['article_revision_id'] for ref in single.source_refs] == [flow.resolutions[changed['id']]['article_revision_id']]


def test_canary_never_reaches_outbox_events_or_results(flow: Flow) -> None:
    # TST-SEC-INV-012
    canary = flow.corpus['canary']
    carrier = next(entry for entry in flow.entries if canary in entry['text'])
    resolution = flow.resolutions[carrier['id']]
    assert resolution['disposition'] == 'NEW_ARTICLE'
    assert canary in flow.uow.articles.get(resolution['article_id']).latest_revision.normalized_text
    assert flow.broker.leaks(sample=canary) == ['sample']
    assert flow.uow.committed_outbox()
    assert flow.broker.leaks(
        outbox=flow.uow.committed_outbox(), results=flow.results, resolutions=flow.resolutions,
        evidence=flow.uow.committed('dedup_evidence'), links=flow.links, updates=flow.updates,
        stored_results=flow.uow.committed('activity_result'),
    ) == []


def test_canary_in_a_loader_failure_never_reaches_the_failed_result() -> None:
    fresh = Flow()
    canary = fresh.corpus['canary']
    carrier = next(entry for entry in fresh.entries if canary in entry['text'])
    fresh.collector.failures[carrier['id']] = OSError('fetch failed with ' + canary)
    failed = fresh.handle(_request(carrier['id']))
    assert failed['disposition'] == 'failed'
    assert failed['problem']['retryable'] is True
    assert fresh.broker.leaks(result=failed, outbox=fresh.uow.committed_outbox(), stored=fresh.uow.committed('activity_result')) == []
    assert fresh.handle(_request(carrier['id']))['disposition'] == 'succeeded'


def test_system_instruction_text_changes_neither_policy_nor_disposition(flow: Flow) -> None:
    # TST-SEC-INV-020
    policies = _corpus()['policies']
    injected = next(entry for entry in flow.entries if 'SYSTEM INSTRUCTION' in entry['text'])
    assert flow.deps.dedup_policy == policies['dedup']
    assert flow.resolutions[injected['id']]['disposition'] == injected['expected']['resolution'] == 'NEW_ARTICLE'
    assert {r['dedup_policy_revision'] for r in flow.resolutions.values()} == {policies['dedup']['dedup_policy_revision']}
    for record in flow.uow.committed_outbox():
        payload = record.payload['payload']
        for key, name in REVISION_KEYS.items():
            assert payload.get(key, policies[name][key]) == policies[name][key]
    assert 'dedup-policy-evil' not in repr((flow.uow.committed_outbox(), flow.resolutions, flow.links))
    later = flow.entries[flow.entries.index(injected) + 1:]
    assert any(flow.resolutions[entry['id']]['disposition'] == 'NEW_ARTICLE' for entry in later)


def test_replaying_an_activity_request_writes_nothing_new() -> None:
    fresh = Flow().run()
    first = fresh.entries[0]
    before = (fresh.uow.committed_outbox(), len(fresh.uow.committed('article')), len(fresh.collector.calls))
    assert fresh.handle(_request(first['id'])) == fresh.results[first['id']]
    assert (fresh.uow.committed_outbox(), len(fresh.uow.committed('article')), len(fresh.collector.calls)) == before


def test_integration_test_directory_is_not_a_package() -> None:
    assert not (HERE / '__init__.py').exists()
