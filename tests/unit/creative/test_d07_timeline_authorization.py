"""D-07: chặn narrative "từ lúc đó đến nay" khi thiếu EventUpdateAccepted (CT-AI-005).

coveredIds: CT-AI-005, TST-CTR-INV-006
"""
import ast
import dataclasses
import pathlib

import pytest

from creative.domain.snapshot import PRODUCTION_MODES, ProductionSnapshot, build_production_snapshot
from creative.domain.timeline_mode import (
    EVENT_UPDATE_MISSING,
    EVENT_UPDATE_REVISION_MISSING,
    POLICY_VIOLATION,
    TIMELINE_MODE,
    TimelineAuthorization,
    TimelinePolicy,
    TimelinePolicyViolation,
    authorize_timeline_narrative,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'creative' / 'domain' / 'timeline_mode.py'
CONTENT_TYPES = ('article_revision', 'event_update_accepted', 'repost', 'new_source', 'new_media')
POLICY = TimelinePolicy(frozenset({'event_update_accepted'}))
UPDATE = ('event_update_accepted', 'u-1', 'rev-1')
NON_UPDATE_REFS = {
    'repost_only': [('repost', 'r-1', 'rev-1')],
    'new_source_only': [('new_source', 's-1', 'rev-1')],
    'new_media_only': [('new_media', 'm-1', 'rev-1')],
    'article_revision_only': [('article_revision', 'a-1', 'rev-2')],
    'all_non_update_types': [
        ('repost', 'r-1', 'rev-1'),
        ('new_source', 's-1', 'rev-1'),
        ('new_media', 'm-1', 'rev-1'),
        ('article_revision', 'a-1', 'rev-2'),
    ],
}
ALLOWED_IMPORTS = frozenset({'__future__', 'collections.abc', 'dataclasses', 'creative.domain.snapshot'})


def _snapshot(mode: str, refs: list) -> ProductionSnapshot:
    return build_production_snapshot(
        snapshot_id='snap-7',
        production_mode=mode,
        source_refs=[{'ref_type': t, 'ref_id': i, 'revision_id': r} for t, i, r in refs],
        index_revision_refs=[],
        configuration_revision_refs=[{'ref_type': 'prompt', 'ref_id': 'p-1', 'revision_id': 'cfg-1'}],
        content_ref_types=CONTENT_TYPES,
        eligibility_reason=f'{mode}_eligible',
        snapshot_timestamp='2026-10-19T08:00:00Z',
    )


def _with_refs(snapshot: ProductionSnapshot, refs: list) -> ProductionSnapshot:
    return dataclasses.replace(snapshot, source_refs=tuple(refs))


def _violation(snapshot: ProductionSnapshot, policy: TimelinePolicy = POLICY) -> TimelinePolicyViolation:
    with pytest.raises(TimelinePolicyViolation) as caught:
        authorize_timeline_narrative(snapshot, policy)
    return caught.value

def test_event_update_with_revision_authorizes_timeline() -> None:
    snapshot = _snapshot('from_then_to_now', [('article_revision', 'a-1', 'rev-2'), UPDATE])
    result = authorize_timeline_narrative(snapshot, POLICY)
    assert isinstance(result, TimelineAuthorization)
    assert (result.snapshot_id, result.production_mode) == ('snap-7', 'from_then_to_now')
    assert [dict(ref) for ref in result.event_update_refs] == [
        {'ref_type': 'event_update_accepted', 'ref_id': 'u-1', 'revision_id': 'rev-1'}
    ]


@pytest.mark.parametrize('refs', NON_UPDATE_REFS.values(), ids=list(NON_UPDATE_REFS))
def test_refs_without_event_update_are_policy_violation(refs: list) -> None:
    error = _violation(_snapshot('from_then_to_now', refs))
    assert (error.code, error.reason) == (POLICY_VIOLATION, EVENT_UPDATE_MISSING)
    assert str(error) == f'{POLICY_VIOLATION}: {EVENT_UPDATE_MISSING}'


def test_accepted_type_name_comes_only_from_policy() -> None:
    update_only = _snapshot('from_then_to_now', [UPDATE])
    assert _violation(update_only, TimelinePolicy(frozenset({'other_update'}))).reason == EVENT_UPDATE_MISSING
    repost_only = _snapshot('from_then_to_now', NON_UPDATE_REFS['repost_only'])
    assert authorize_timeline_narrative(repost_only, TimelinePolicy(frozenset({'repost'}))).event_update_refs


def test_accepted_ref_without_usable_revision_is_policy_violation() -> None:
    base = _snapshot('from_then_to_now', [UPDATE])
    for revision in ('', None, 5):
        ref = {'ref_type': 'event_update_accepted', 'ref_id': 'u-1', 'revision_id': revision}
        assert _violation(_with_refs(base, [ref])).reason == EVENT_UPDATE_REVISION_MISSING, revision
    absent = {'ref_type': 'event_update_accepted', 'ref_id': 'u-1'}
    assert _violation(_with_refs(base, [absent])).reason == EVENT_UPDATE_REVISION_MISSING


def test_only_event_updates_with_revision_are_returned() -> None:
    base = _snapshot('from_then_to_now', [UPDATE])
    refs = [dict(base.source_refs[0]), {'ref_type': 'event_update_accepted', 'ref_id': 'u-2', 'revision_id': ''}]
    result = authorize_timeline_narrative(_with_refs(base, refs), POLICY)
    assert [ref['ref_id'] for ref in result.event_update_refs] == ['u-1']

@pytest.mark.parametrize('mode', ['single_article', 'multi_article_event'])
@pytest.mark.parametrize('refs', NON_UPDATE_REFS.values(), ids=list(NON_UPDATE_REFS))
def test_other_modes_are_not_affected(mode: str, refs: list) -> None:
    for source_refs in (refs, [*refs, UPDATE]):
        result = authorize_timeline_narrative(_snapshot(mode, source_refs), POLICY)
        assert (result.production_mode, result.event_update_refs) == (mode, ())


def test_violation_never_changes_the_mode() -> None:
    snapshot = _snapshot('from_then_to_now', NON_UPDATE_REFS['repost_only'])
    before = snapshot.to_payload()
    _violation(snapshot)
    assert snapshot.production_mode == 'from_then_to_now'
    assert snapshot.to_payload() == before


def test_module_has_no_fallback_mode_or_mode_rewrite() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not literals & {'single_article', 'multi_article_event'}
    imported = {alias.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for alias in n.names}
    assert 'replace' not in imported


def test_module_imports_only_allowlist() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    modules |= {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
    assert modules <= ALLOWED_IMPORTS


def test_timeline_mode_is_a_binding_mode() -> None:
    assert TIMELINE_MODE == 'from_then_to_now'
    assert TIMELINE_MODE in PRODUCTION_MODES


def test_malformed_arguments_raise_value_error() -> None:
    good = _snapshot('from_then_to_now', [UPDATE])
    for snapshot, policy in ((good.to_payload(), POLICY), (None, POLICY), (good, None), (good, {'event_update_accepted'})):
        with pytest.raises(ValueError):
            authorize_timeline_narrative(snapshot, policy)
    with pytest.raises(ValueError):
        authorize_timeline_narrative(dataclasses.replace(good, production_mode='timeline'), POLICY)


@pytest.mark.parametrize('types', [frozenset(), {'a'}, ('a',), 'event_update_accepted', frozenset({''}), frozenset({1})])
def test_policy_requires_non_empty_frozenset_of_names(types: object) -> None:
    with pytest.raises(ValueError):
        TimelinePolicy(types)


def test_policy_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        POLICY.event_update_ref_types = frozenset({'x'})


def test_docstrings_declare_covered_ids() -> None:
    for path in (pathlib.Path(__file__), MODULE_PATH):
        doc = ast.get_docstring(ast.parse(path.read_text(encoding='utf-8')))
        assert 'coveredIds: CT-AI-005, TST-CTR-INV-006' in (doc or '').splitlines(), path.name
