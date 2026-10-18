"""A-03: Source aggregate lifecycle (CT-SRC-001..003).

coveredIds: CT-STATE-001, A-RULE-003
"""
import ast
import dataclasses
import inspect
import pathlib
import unittest
from datetime import UTC, datetime, timedelta

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.statemachine import ForbiddenTransitionError
from source_ingestion.domain import source as source_module
from source_ingestion.domain.source import (
    RESTORE_POLICY_DISALLOWED,
    Source,
    SourcePolicy,
    SourceStatus,
    disable_source,
    enable_source,
    register_source,
    remove_source,
    restore_source,
    update_source_metadata,
)

SOURCE_FILE = pathlib.Path(__file__).resolve().parents[3] / 'src' / 'source_ingestion' / 'domain' / 'source.py'
POLICY = SourcePolicy(
    policy_revision='policy-r1',
    source_kinds=frozenset({'rss_feed', 'web_page'}),
    tiers=frozenset({'T1', 'T2'}),
    admin_metadata_keys=frozenset({'owner_team'}),
)
FIXTURE_LITERALS = frozenset({'rss_feed', 'web_page', 'T1', 'T2', 'owner_team'})
LIFECYCLE_FIELDS = frozenset(
    {'status', 'status_reason', 'previous_status', 'policy_revision', 'revision', 'updated_by', 'updated_at'}
)
T0 = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def register(**overrides: object) -> Source:
    params: dict[str, object] = {
        'source_id': 'src-1', 'workspace_id': 'ws-1', 'canonical_locator': 'https://example.test/feed',
        'name': 'Example', 'source_kind': 'rss_feed', 'tier': 'T1', 'topics': frozenset({'tech'}),
        'notes': '', 'collection_enabled': True, 'admin_metadata': {}, 'actor': 'user-a', 'at': T0,
        'policy': POLICY,
    }
    params.update(overrides)
    return register_source(**params)


def removed_from(status: SourceStatus) -> Source:
    source = register(collection_enabled=status is SourceStatus.ACTIVE)
    return remove_source(source, expected_revision=source.revision, actor='user-b', at=at(1))


class SourceShapeTests(unittest.TestCase):
    def test_source_is_frozen_dataclass_with_three_statuses(self) -> None:
        source = register()
        self.assertTrue(dataclasses.is_dataclass(Source))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            source.status = SourceStatus.DISABLED
        self.assertEqual({s.value for s in SourceStatus}, {'ACTIVE', 'DISABLED', 'REMOVED_TOMBSTONE'})

    def test_register_records_revision_actor_time_and_initial_status(self) -> None:
        for enabled, expected in ((True, SourceStatus.ACTIVE), (False, SourceStatus.DISABLED)):
            with self.subTest(collection_enabled=enabled):
                source = register(collection_enabled=enabled)
                self.assertEqual((source.status, source.revision, source.policy_revision), (expected, 1, 'policy-r1'))
                self.assertEqual(
                    (source.created_by, source.created_at, source.updated_by, source.updated_at),
                    ('user-a', T0, 'user-a', T0),
                )
                self.assertIsNone(source.previous_status)


class LifecycleTests(unittest.TestCase):
    def test_active_and_disabled_transition_both_ways(self) -> None:
        disabled = disable_source(register(), expected_revision=1, actor='user-b', at=at(1), reason='maintenance')
        self.assertEqual(
            (disabled.status, disabled.status_reason, disabled.revision), (SourceStatus.DISABLED, 'maintenance', 2)
        )
        enabled = enable_source(disabled, expected_revision=2, actor='user-c', at=at(2))
        self.assertEqual((enabled.status, enabled.status_reason, enabled.revision), (SourceStatus.ACTIVE, None, 3))
        self.assertEqual((enabled.updated_by, enabled.updated_at), ('user-c', at(2)))

    def test_remove_from_active_or_disabled_creates_tombstone(self) -> None:
        for status in (SourceStatus.ACTIVE, SourceStatus.DISABLED):
            with self.subTest(previous=status):
                removed = removed_from(status)
                self.assertEqual(
                    (removed.status, removed.previous_status, removed.revision),
                    (SourceStatus.REMOVED_TOMBSTONE, status, 2),
                )
                self.assertEqual((removed.updated_by, removed.updated_at), ('user-b', at(1)))

    def test_restore_returns_to_status_before_remove_when_policy_allows(self) -> None:
        for status in (SourceStatus.ACTIVE, SourceStatus.DISABLED):
            with self.subTest(previous=status):
                restored = restore_source(
                    removed_from(status), expected_revision=2, actor='user-c', at=at(2), policy=POLICY
                )
                self.assertEqual(
                    (restored.status, restored.status_reason, restored.previous_status, restored.revision),
                    (status, None, None, 3),
                )

    def test_restore_falls_back_to_disabled_with_reason_when_policy_disallows(self) -> None:
        narrowed = {
            'tier': dataclasses.replace(POLICY, policy_revision='policy-r2', tiers=frozenset({'T2'})),
            'source_kind': dataclasses.replace(POLICY, policy_revision='policy-r2', source_kinds=frozenset({'web_page'})),
        }
        for field, policy in narrowed.items():
            with self.subTest(disallowed=field):
                restored = restore_source(
                    removed_from(SourceStatus.ACTIVE), expected_revision=2, actor='user-c', at=at(2), policy=policy
                )
                self.assertEqual(
                    (restored.status, restored.status_reason, restored.policy_revision),
                    (SourceStatus.DISABLED, RESTORE_POLICY_DISALLOWED, 'policy-r2'),
                )

    def test_tombstone_leaves_only_through_restore(self) -> None:
        removed = removed_from(SourceStatus.ACTIVE)
        attempts = {
            'enable': lambda: enable_source(removed, expected_revision=2, actor='u', at=at(2)),
            'disable': lambda: disable_source(removed, expected_revision=2, actor='u', at=at(2)),
            'remove': lambda: remove_source(removed, expected_revision=2, actor='u', at=at(2)),
            'update': lambda: update_source_metadata(
                removed, expected_revision=2, actor='u', at=at(2), policy=POLICY, notes='x'
            ),
        }
        for name, attempt in attempts.items():
            with self.subTest(command=name), self.assertRaises(ForbiddenTransitionError):
                attempt()

    def test_edges_outside_the_state_graph_are_forbidden(self) -> None:
        active, disabled = register(), register(collection_enabled=False)
        attempts = {
            'enable_active': lambda: enable_source(active, expected_revision=1, actor='u', at=at(1)),
            'disable_disabled': lambda: disable_source(disabled, expected_revision=1, actor='u', at=at(1)),
            'restore_active': lambda: restore_source(active, expected_revision=1, actor='u', at=at(1), policy=POLICY),
            'restore_disabled': lambda: restore_source(
                disabled, expected_revision=1, actor='u', at=at(1), policy=POLICY
            ),
        }
        for name, attempt in attempts.items():
            with self.subTest(command=name), self.assertRaises(ForbiddenTransitionError):
                attempt()


class RevisionTests(unittest.TestCase):
    def test_every_mutation_increments_revision_and_records_actor_time(self) -> None:
        steps = (
            lambda s, n: update_source_metadata(
                s, expected_revision=s.revision, actor=f'user-{n}', at=at(n), policy=POLICY, notes=f'note {n}'
            ),
            lambda s, n: disable_source(s, expected_revision=s.revision, actor=f'user-{n}', at=at(n)),
            lambda s, n: enable_source(s, expected_revision=s.revision, actor=f'user-{n}', at=at(n)),
            lambda s, n: remove_source(s, expected_revision=s.revision, actor=f'user-{n}', at=at(n)),
            lambda s, n: restore_source(s, expected_revision=s.revision, actor=f'user-{n}', at=at(n), policy=POLICY),
        )
        source = register()
        for n, step in enumerate(steps, start=1):
            mutated = step(source, n)
            self.assertEqual(
                (mutated.revision, mutated.updated_by, mutated.updated_at), (source.revision + 1, f'user-{n}', at(n))
            )
            self.assertEqual((mutated.created_by, mutated.created_at), ('user-a', T0))
            source = mutated
        self.assertEqual((source.status, source.revision), (SourceStatus.ACTIVE, 6))

    def test_stale_expected_revision_raises_shared_conflict_error(self) -> None:
        current = update_source_metadata(
            register(), expected_revision=1, actor='user-b', at=at(1), policy=POLICY, notes='fresh'
        )
        disabled = disable_source(current, expected_revision=2, actor='user-b', at=at(2))
        removed = remove_source(disabled, expected_revision=3, actor='user-b', at=at(3))
        attempts = {
            'update': (lambda: update_source_metadata(
                current, expected_revision=1, actor='u', at=at(9), policy=POLICY, notes='stale'
            ), 2),
            'disable': (lambda: disable_source(current, expected_revision=1, actor='u', at=at(9)), 2),
            'enable': (lambda: enable_source(disabled, expected_revision=2, actor='u', at=at(9)), 3),
            'remove': (lambda: remove_source(current, expected_revision=1, actor='u', at=at(9)), 2),
            'restore': (lambda: restore_source(removed, expected_revision=3, actor='u', at=at(9), policy=POLICY), 4),
        }
        for name, (attempt, current_revision) in attempts.items():
            with self.subTest(command=name):
                with self.assertRaises(RevisionConflictError) as caught:
                    attempt()
                self.assertIs(type(caught.exception), RevisionConflictError)
                self.assertEqual(caught.exception.current_revision, current_revision)
        self.assertEqual((current.notes, current.revision), ('fresh', 2))

    def test_module_reuses_shared_conflict_error_and_defines_no_error_class(self) -> None:
        self.assertIs(source_module.RevisionConflictError, RevisionConflictError)
        local_errors = [
            name for name, obj in vars(source_module).items()
            if isinstance(obj, type) and issubclass(obj, BaseException) and obj.__module__ == source_module.__name__
        ]
        self.assertEqual(local_errors, [])


class UpdateAndPolicyTests(unittest.TestCase):
    def test_update_changes_only_published_metadata(self) -> None:
        source = register()
        updated = update_source_metadata(
            source, expected_revision=1, actor='user-b', at=at(1), policy=POLICY, tier='T2',
            topics=frozenset({'tech', 'ai'}), notes='checked', collection_enabled=False,
            admin_metadata={'owner_team': 'news'},
        )
        self.assertEqual(
            (updated.tier, updated.topics, updated.notes, updated.status, updated.admin_metadata),
            ('T2', frozenset({'tech', 'ai'}), 'checked', SourceStatus.DISABLED, (('owner_team', 'news'),)),
        )
        identity = {f.name for f in dataclasses.fields(Source)} - LIFECYCLE_FIELDS - {'tier', 'topics', 'notes', 'admin_metadata'}
        for name in sorted(identity):
            with self.subTest(unchanged=name):
                self.assertEqual(getattr(updated, name), getattr(source, name))
        reenabled = update_source_metadata(
            updated, expected_revision=2, actor='user-c', at=at(2), policy=POLICY, collection_enabled=True
        )
        self.assertEqual(reenabled.status, SourceStatus.ACTIVE)
        self.assertEqual(
            set(inspect.signature(update_source_metadata).parameters),
            {'source', 'expected_revision', 'actor', 'at', 'policy', 'tier', 'topics', 'notes', 'collection_enabled', 'admin_metadata'},
        )
        for forbidden in ('source_kind', 'name', 'canonical_locator', 'status'):
            with self.subTest(forbidden=forbidden), self.assertRaises(TypeError):
                update_source_metadata(
                    source, expected_revision=1, actor='user-b', at=at(1), policy=POLICY, **{forbidden: 'x'}
                )

    def test_update_validates_values_against_supplied_policy(self) -> None:
        source = register()
        invalid = {'tier': {'tier': 'T9'}, 'admin_key': {'admin_metadata': {'unknown_key': 'v'}}, 'empty': {}}
        for name, changes in invalid.items():
            with self.subTest(case=name), self.assertRaises(ValueError):
                update_source_metadata(source, expected_revision=1, actor='user-b', at=at(1), policy=POLICY, **changes)

    def test_register_checks_source_kind_and_tier_against_policy_values(self) -> None:
        for name, overrides in {'source_kind': {'source_kind': 'podcast'}, 'tier': {'tier': 'T9'}}.items():
            with self.subTest(field=name), self.assertRaises(ValueError):
                register(**overrides)
        custom = SourcePolicy(
            policy_revision='policy-custom', source_kinds=frozenset({'podcast'}), tiers=frozenset({'T9'}),
            admin_metadata_keys=frozenset(),
        )
        source = register(source_kind='podcast', tier='T9', policy=custom)
        self.assertEqual((source.source_kind, source.tier, source.policy_revision), ('podcast', 'T9', 'policy-custom'))
        with self.assertRaises(ValueError):
            register(source_kind='rss_feed', tier='T9', policy=custom)

    def test_module_hard_codes_no_policy_values(self) -> None:
        tree = ast.parse(SOURCE_FILE.read_text(encoding='utf-8'), filename=str(SOURCE_FILE))
        literals = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertEqual(literals & FIXTURE_LITERALS, set())

    def test_mutations_require_actor_and_timezone_aware_time(self) -> None:
        source = register()
        for name, overrides in {'actor': {'actor': ''}, 'naive_time': {'at': datetime(2026, 10, 18, 9, 0)}}.items():
            with self.subTest(case=name):
                params: dict[str, object] = {'expected_revision': 1, 'actor': 'user-b', 'at': at(1), **overrides}
                with self.assertRaises(ValueError):
                    disable_source(source, **params)
                with self.assertRaises(ValueError):
                    register(**overrides)


class RetentionTests(unittest.TestCase):
    """A-RULE-003: removing a Source keeps its record so collected data stays traceable."""

    def test_remove_and_restore_keep_source_record_fields(self) -> None:
        source = update_source_metadata(
            register(), expected_revision=1, actor='user-a', at=at(1), policy=POLICY, notes='keep',
            admin_metadata={'owner_team': 'news'},
        )
        removed = remove_source(source, expected_revision=2, actor='user-b', at=at(2), reason='retired')
        restored = restore_source(removed, expected_revision=3, actor='user-c', at=at(3), policy=POLICY)
        self.assertEqual((removed.status_reason, restored.status), ('retired', SourceStatus.ACTIVE))
        for field in sorted({f.name for f in dataclasses.fields(Source)} - LIFECYCLE_FIELDS):
            with self.subTest(field=field):
                self.assertEqual(getattr(removed, field), getattr(source, field))
                self.assertEqual(getattr(restored, field), getattr(source, field))
