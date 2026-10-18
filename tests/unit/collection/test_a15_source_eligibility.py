"""A-15: deterministic Tier-ordered source eligibility and Tier-expansion stop decision.

coveredIds: A-RULE-006, A-RULE-007
"""
import ast
import dataclasses
import inspect
import itertools
import pathlib
import unittest
from datetime import UTC, date, datetime

from source_ingestion.application import source_eligibility as eligibility_module
from source_ingestion.application.source_eligibility import (
    EligibilityPlan,
    EligibilityReason,
    SourceEligibility,
    TierExpansionAction,
    TierExpansionDecision,
    UniqueArticleCount,
    decide_tier_expansion,
    rank_eligible_sources,
)
from source_ingestion.domain.collection_run import CollectionPurpose, CollectionRun, RetryPolicy, schedule_run
from source_ingestion.domain.source import Source, SourcePolicy, disable_source, register_source, remove_source

MODULE_FILE = pathlib.Path(eligibility_module.__file__).resolve()
POLICY = SourcePolicy(
    policy_revision='policy-r1',
    source_kinds=frozenset({'rss_feed'}),
    tiers=frozenset({'T1', 'T2', 'T3'}),
    admin_metadata_keys=frozenset(),
)
TIER_ORDER = ('T1', 'T2', 'T3')
TOPIC = 'tech'
BUSINESS_DATE = date(2026, 10, 19)
T0 = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)


def make_source(source_id: str, tier: str, *, topics: tuple[str, ...] = (TOPIC,), workspace_id: str = 'ws-1') -> Source:
    return register_source(
        source_id=source_id, workspace_id=workspace_id, canonical_locator=f'https://example.test/{source_id}',
        name=source_id, source_kind='rss_feed', tier=tier, topics=topics, notes='', collection_enabled=True,
        admin_metadata={}, actor='user-a', at=T0, policy=POLICY,
    )


def make_run(
    source_id: str, *, purpose: CollectionPurpose = CollectionPurpose.PERIODIC, business_date: date = BUSINESS_DATE
) -> CollectionRun:
    return schedule_run(
        run_id=f'run-{source_id}-{purpose.value}', workspace_id='ws-1', source_id=source_id,
        business_date=business_date, purpose=purpose, retry_policy=RetryPolicy(revision='retry-r1', max_attempts=3),
    )


def rank(sources, runs=(), *, tier_order=TIER_ORDER) -> EligibilityPlan:
    return rank_eligible_sources(
        sources=sources, existing_runs=runs, workspace_id='ws-1', topic=TOPIC,
        business_date=BUSINESS_DATE, tier_order=tier_order,
    )


def ids(entries) -> list[str]:
    return [entry.source_id for entry in entries]


def counter(count: int, *, topic: str = TOPIC, business_date: date = BUSINESS_DATE) -> UniqueArticleCount:
    return UniqueArticleCount(topic=topic, business_date=business_date, unique_article_count=count)


MIXED = (
    make_source('s-c', 'T2'),
    make_source('s-a', 'T3'),
    make_source('s-b', 'T1'),
    make_source('s-d', 'T1'),
    make_source('s-e', 'T2'),
)


class RankingOrderTests(unittest.TestCase):
    """Counterexample: the order depends on input or dict insertion order."""

    def test_orders_by_tier_then_source_id(self) -> None:
        plan = rank(MIXED)
        self.assertEqual(ids(plan.selected), ['s-b', 's-d', 's-c', 's-e', 's-a'])
        self.assertTrue(all(e.selected and e.reason is EligibilityReason.SELECTED for e in plan.selected))
        self.assertEqual(plan.skipped, ())
        self.assertEqual(plan.tier_order, TIER_ORDER)

    def test_order_is_independent_of_input_and_dict_order(self) -> None:
        baseline = rank(MIXED[:4])
        for permutation in itertools.permutations(MIXED[:4]):
            with self.subTest(order=ids(permutation)):
                self.assertEqual(rank(permutation), baseline)
        forward = {source.source_id: source for source in MIXED}
        backward = dict(reversed(list(forward.items())))
        self.assertEqual(rank(forward.values()), rank(backward.values()))
        self.assertEqual(rank(backward.values()), rank(MIXED))

    def test_tier_order_is_an_input(self) -> None:
        self.assertEqual(ids(rank(MIXED, tier_order=('T3', 'T1', 'T2')).selected), ['s-a', 's-b', 's-d', 's-c', 's-e'])
        self.assertEqual(rank(MIXED, tier_order=list(TIER_ORDER)).tier_order, TIER_ORDER)

    def test_module_hard_codes_no_tier_literal(self) -> None:
        tree = ast.parse(MODULE_FILE.read_text(encoding='utf-8'), filename=str(MODULE_FILE))
        literals = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertEqual(literals & set(TIER_ORDER), set())

    def test_tier_order_must_be_unique_ordered_sequence(self) -> None:
        for bad in (frozenset(TIER_ORDER), (), ('T1', 'T1'), 'T1', ('T1', '')):
            with self.subTest(tier_order=bad):
                with self.assertRaises(ValueError):
                    rank(MIXED, tier_order=bad)


class EligibilityFilterTests(unittest.TestCase):
    """Counterexample: a DISABLED or tombstoned source is selected."""

    @staticmethod
    def reasons(plan: EligibilityPlan) -> dict[str, EligibilityReason]:
        return {entry.source_id: entry.reason for entry in (*plan.selected, *plan.skipped)}

    def test_only_active_sources_are_selected(self) -> None:
        disabled = disable_source(make_source('s-2', 'T1'), expected_revision=1, actor='user-b', at=T0)
        removed = remove_source(make_source('s-3', 'T1'), expected_revision=1, actor='user-b', at=T0)
        plan = rank((disabled, removed, make_source('s-1', 'T1')))
        self.assertEqual(ids(plan.selected), ['s-1'])
        self.assertEqual(ids(plan.skipped), ['s-2', 's-3'])
        self.assertEqual({entry.reason for entry in plan.skipped}, {EligibilityReason.SOURCE_NOT_ACTIVE})
        self.assertFalse(any(entry.selected for entry in plan.skipped))

    def test_scope_and_tier_reasons(self) -> None:
        sources = (
            make_source('s-4', 'T3'),
            make_source('s-3', 'T1', workspace_id='ws-2'),
            make_source('s-2', 'T1', topics=('sport',)),
            make_source('s-1', 'T1'),
        )
        plan = rank(sources, tier_order=('T1', 'T2'))
        self.assertEqual(self.reasons(plan), {
            's-1': EligibilityReason.SELECTED,
            's-2': EligibilityReason.TOPIC_OUT_OF_SCOPE,
            's-3': EligibilityReason.WORKSPACE_OUT_OF_SCOPE,
            's-4': EligibilityReason.TIER_NOT_RANKED,
        })
        self.assertEqual(ids(plan.skipped), ['s-2', 's-3', 's-4'])

    def test_periodic_run_in_business_date_excludes_source(self) -> None:
        sources = tuple(make_source(f's-{n}', 'T1') for n in range(1, 5))
        runs = [
            make_run('s-1'),
            make_run('s-2', business_date=date(2026, 10, 18)),
            make_run('s-3', purpose=CollectionPurpose.SUPPLEMENTAL),
            make_run('s-4', purpose=CollectionPurpose.SOURCE_TEST),
        ]
        self.assertEqual(self.reasons(rank(sources, runs)), {
            's-1': EligibilityReason.PERIODIC_RUN_EXISTS,
            's-2': EligibilityReason.SELECTED,
            's-3': EligibilityReason.SELECTED,
            's-4': EligibilityReason.SELECTED,
        })

    def test_rejects_malformed_snapshot(self) -> None:
        cases = {
            'duplicate_source_id': (lambda: rank((make_source('s-1', 'T1'), make_source('s-1', 'T2'))), ValueError),
            'not_a_source': (lambda: rank(({'source_id': 's-1', 'status': 'ACTIVE'},)), TypeError),
            'not_a_run': (lambda: rank((make_source('s-1', 'T1'),), ({'source_id': 's-1'},)), TypeError),
            'datetime_business_date': (
                lambda: rank_eligible_sources(
                    sources=MIXED, existing_runs=(), workspace_id='ws-1', topic=TOPIC,
                    business_date=T0, tier_order=TIER_ORDER,
                ),
                TypeError,
            ),
        }
        for name, (call, error) in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(error):
                    call()

    def test_ranking_is_pure_and_repeatable(self) -> None:
        runs = [make_run('s-b')]
        first = rank(MIXED, runs)
        self.assertEqual(rank(MIXED, runs), first)
        self.assertEqual(runs, [make_run('s-b')])
        self.assertIn('s-b', ids(first.skipped))
        self.assertTrue(all(isinstance(entry, SourceEligibility) for entry in (*first.selected, *first.skipped)))


class TierExpansionDecisionTests(unittest.TestCase):
    """A-RULE-006: a later Tier opens only while the G/B unique counter is below the input target."""

    def setUp(self) -> None:
        self.plan = rank(MIXED)

    def decide(self, completed_tier: str, count: int, target: int) -> TierExpansionDecision:
        return decide_tier_expansion(
            plan=self.plan, completed_tier=completed_tier, counter=counter(count), fresh_unique_article_target=target
        )

    def test_below_target_opens_next_tier(self) -> None:
        decision = self.decide('T1', 2, 5)
        self.assertIs(decision.action, TierExpansionAction.OPEN_NEXT_TIER)
        self.assertEqual(decision.next_tier, 'T2')
        self.assertEqual(decision.unopened_tiers, ('T3',))
        self.assertEqual(decision.unscanned_source_ids, ())
        self.assertEqual((decision.unique_article_count, decision.fresh_unique_article_target), (2, 5))

    def test_reaching_target_stops_expansion_for_g_to_record(self) -> None:
        for count in (5, 9):
            with self.subTest(count=count):
                decision = self.decide('T1', count, 5)
                self.assertIs(decision.action, TierExpansionAction.STOP_SUFFICIENT)
                self.assertIsNone(decision.next_tier)
                self.assertEqual(decision.unopened_tiers, ('T2', 'T3'))
                self.assertEqual(decision.unscanned_source_ids, ('s-c', 's-e', 's-a'))

    def test_threshold_is_an_input(self) -> None:
        self.assertIs(self.decide('T2', 5, 5).action, TierExpansionAction.STOP_SUFFICIENT)
        reopened = self.decide('T2', 5, 6)
        self.assertIs(reopened.action, TierExpansionAction.OPEN_NEXT_TIER)
        self.assertEqual(reopened.next_tier, 'T3')

    def test_last_tier_below_target_has_no_more_tiers(self) -> None:
        decision = self.decide('T3', 1, 5)
        self.assertIs(decision.action, TierExpansionAction.NO_MORE_TIERS)
        self.assertIsNone(decision.next_tier)
        self.assertEqual((decision.unopened_tiers, decision.unscanned_source_ids), ((), ()))

    def test_rejects_invalid_decision_input(self) -> None:
        cases = {
            'target_zero': ('T1', counter(1), 0),
            'target_bool': ('T1', counter(1), True),
            'target_text': ('T1', counter(1), '5'),
            'unknown_tier': ('T9', counter(1), 5),
            'other_topic': ('T1', counter(1, topic='sport'), 5),
            'other_business_date': ('T1', counter(1, business_date=date(2026, 10, 18)), 5),
        }
        for name, (tier, count, target) in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(ValueError):
                    decide_tier_expansion(
                        plan=self.plan, completed_tier=tier, counter=count, fresh_unique_article_target=target
                    )


class UniqueCounterOnlyTests(unittest.TestCase):
    """A-RULE-007 counterexample: a URL or item count replaces the unique article count."""

    def test_raw_url_or_item_counts_are_rejected(self) -> None:
        plan = rank(MIXED)
        for raw in (50, {'url_count': 50}, {'item_count': 50}):
            with self.subTest(raw=raw):
                with self.assertRaises(TypeError):
                    decide_tier_expansion(plan=plan, completed_tier='T1', counter=raw, fresh_unique_article_target=5)

    def test_counter_carries_only_unique_article_count(self) -> None:
        self.assertEqual(
            {field.name for field in dataclasses.fields(UniqueArticleCount)},
            {'topic', 'business_date', 'unique_article_count'},
        )
        with self.assertRaises(TypeError):
            UniqueArticleCount(topic=TOPIC, business_date=BUSINESS_DATE, url_count=50)
        params = set(inspect.signature(decide_tier_expansion).parameters)
        self.assertEqual(params, {'plan', 'completed_tier', 'counter', 'fresh_unique_article_target'})
        self.assertEqual([name for name in params if 'url' in name or 'item' in name], [])

    def test_counter_values_are_validated(self) -> None:
        cases = (
            ({'unique_article_count': -1}, ValueError),
            ({'unique_article_count': True}, ValueError),
            ({'unique_article_count': 1.0}, ValueError),
            ({'topic': ''}, ValueError),
            ({'business_date': T0}, TypeError),
        )
        for overrides, error in cases:
            fields = {'topic': TOPIC, 'business_date': BUSINESS_DATE, 'unique_article_count': 1, **overrides}
            with self.subTest(overrides=overrides):
                with self.assertRaises(error):
                    UniqueArticleCount(**fields)


class NoFakeRunTests(unittest.TestCase):
    """Counterexample: a CollectionRun is created for a source skipped by eligibility or sufficiency."""

    def test_outputs_carry_no_collection_run(self) -> None:
        runs = [make_run('s-b')]
        plan = rank(MIXED, runs)
        decision = decide_tier_expansion(
            plan=plan, completed_tier='T1', counter=counter(5), fresh_unique_article_target=5
        )
        self.assertIs(decision.action, TierExpansionAction.STOP_SUFFICIENT)
        self.assertEqual(decision.unscanned_source_ids, ('s-c', 's-e', 's-a'))
        values = [
            getattr(obj, field.name)
            for obj in (plan, decision, *plan.selected, *plan.skipped)
            for field in dataclasses.fields(obj)
        ]
        flat = [item for value in values for item in (value if isinstance(value, tuple) else (value,))]
        self.assertEqual([item for item in flat if isinstance(item, CollectionRun)], [])
        self.assertEqual(len(runs), 1)

    def test_module_never_builds_runs_or_decisions(self) -> None:
        tree = ast.parse(MODULE_FILE.read_text(encoding='utf-8'), filename=str(MODULE_FILE))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, (ast.alias, ast.FunctionDef, ast.ClassDef)):
                names.add(node.name)
        self.assertEqual(names & {'schedule_run', 'start_run', 'ensure_periodic_unique', 'CollectionDecision'}, set())
        calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertNotIn('CollectionRun', calls)
