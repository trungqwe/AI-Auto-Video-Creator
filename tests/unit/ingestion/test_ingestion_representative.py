"""B-5: representative selection by Tier (CT-CNT-002, D8-B-05)."""
import itertools

import pytest

from ingestion.domain.representative import (
    HIGHER_TIER,
    KEEP_INCUMBENT_SAME_TIER,
    SELECTION_REASONS,
    TIE_BREAK_SOURCE_ID,
    RepresentativeCandidate as C,
    RepresentativeSelection as S,
    select_representative,
)


def test_selection_reasons_are_the_contract_values() -> None:
    assert SELECTION_REASONS == ('higher_tier', 'keep_incumbent_same_tier', 'tie_break_source_id')


def test_lower_tier_replaces_incumbent_for_future_production() -> None:
    result = select_representative(C('src-b', 2), [C('src-z', 1), C('src-b', 2)])
    assert result == S(C('src-z', 1), HIGHER_TIER, True, True)


def test_tier_three_never_beats_tier_one() -> None:
    assert select_representative(C('src-z', 1), [C('src-a', 3)]) == S(C('src-z', 1), KEEP_INCUMBENT_SAME_TIER, False, False)
    assert select_representative(None, [C('src-a', 3), C('src-z', 1)]) == S(C('src-z', 1), HIGHER_TIER, False, False)


def test_same_tier_keeps_incumbent_even_with_smaller_source_id() -> None:
    result = select_representative(C('src-m', 2), [C('src-a', 2), C('src-m', 2)])
    assert result == S(C('src-m', 2), KEEP_INCUMBENT_SAME_TIER, False, False)


def test_same_tier_arrivals_do_not_oscillate() -> None:
    current = select_representative(None, [C('src-k', 2)]).representative
    for arrival in (C('src-a', 2), C('src-z', 2), C('src-b', 2)):
        result = select_representative(current, [arrival])
        assert result == S(C('src-k', 2), KEEP_INCUMBENT_SAME_TIER, False, False), arrival
        current = result.representative


def test_worse_tier_candidates_keep_incumbent() -> None:
    result = select_representative(C('src-m', 1), [C('src-a', 2), C('src-b', 3)])
    assert result == S(C('src-m', 1), KEEP_INCUMBENT_SAME_TIER, False, False)


def test_empty_candidates_keep_incumbent() -> None:
    assert select_representative(C('src-m', 2), []) == S(C('src-m', 2), KEEP_INCUMBENT_SAME_TIER, False, False)


def test_higher_tier_tie_breaks_on_smallest_source_id() -> None:
    result = select_representative(C('src-m', 3), [C('src-y', 1), C('src-c', 1), C('src-a', 2)])
    assert result == S(C('src-c', 1), HIGHER_TIER, True, True)


def test_without_incumbent_smallest_source_id_wins_in_best_tier() -> None:
    result = select_representative(None, [C('src-c', 1), C('src-a', 1), C('src-0', 2)])
    assert result == S(C('src-a', 1), TIE_BREAK_SOURCE_ID, False, False)


def test_without_incumbent_tie_break_uses_string_order() -> None:
    assert select_representative(None, [C('src-9', 2), C('src-10', 2)]).representative == C('src-10', 2)


def test_without_incumbent_single_candidate() -> None:
    assert select_representative(None, [C('src-x', 3)]) == S(C('src-x', 3), TIE_BREAK_SOURCE_ID, False, False)


def test_plain_tuples_are_accepted() -> None:
    result = select_representative(('src-b', 2), [('src-z', 1)])
    assert result == S(C('src-z', 1), HIGHER_TIER, True, True)
    assert type(result.representative) is C


SCENARIOS = [
    (None, [C('src-d', 2), C('src-b', 1), C('src-c', 1), C('src-a', 3)], S(C('src-b', 1), TIE_BREAK_SOURCE_ID, False, False)),
    (C('src-m', 2), [C('src-a', 2), C('src-m', 2), C('src-c', 3), C('src-q', 2)], S(C('src-m', 2), KEEP_INCUMBENT_SAME_TIER, False, False)),
    (C('src-m', 2), [C('src-x', 1), C('src-b', 1), C('src-a', 3), C('src-m', 2)], S(C('src-b', 1), HIGHER_TIER, True, True)),
]


@pytest.mark.parametrize(('incumbent', 'candidates', 'expected'), SCENARIOS)
def test_result_is_independent_of_input_order(incumbent, candidates, expected) -> None:
    for order in itertools.permutations(candidates):
        assert select_representative(incumbent, list(order)) == expected, order
        assert select_representative(incumbent, iter(order)) == expected, order


@pytest.mark.parametrize(
    ('incumbent', 'candidates'),
    [
        (None, []),
        (None, [('src-a', 0)]),
        (None, [('src-a', 4)]),
        (None, [('src-a', True)]),
        (None, [('src-a', '1')]),
        (None, [('', 1)]),
        (None, [(1, 1)]),
        (None, [('src-a',)]),
        (None, [['src-a', 1]]),
        (None, [('src-a', 1), ('src-a', 2)]),
        (('src-a', 1), [('src-a', 2)]),
        (('src-a', 5), []),
    ],
)
def test_invalid_input_fails_closed(incumbent, candidates) -> None:
    with pytest.raises(ValueError):
        select_representative(incumbent, candidates)
