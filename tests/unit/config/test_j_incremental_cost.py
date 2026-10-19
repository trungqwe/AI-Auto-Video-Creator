"""J-08: IncrementalCostRecord và dự báo ngân sách 80% (CT-COST-001, QR-COST-001).

coveredIds: CT-COST-001, QR-COST-001
"""
import dataclasses
import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from controlplane.domain.config_security import incremental_cost
from controlplane.domain.config_security.incremental_cost import (
    BudgetLevel, BudgetPolicy, BudgetStatus, CurrencyMismatchError, IncrementalCostRecord, InvalidAmountError,
    NotIncrementalCostError, evaluate_budget, should_block,
)

D = Decimal
UTC = timezone.utc
START = datetime(2026, 10, 1, tzinfo=UTC)
END = START + timedelta(days=30)
HALF = START + timedelta(days=15)
EXPECTED_FIELDS = [
    'record_id', 'provider', 'service', 'operation_ref', 'job_ref', 'batch_ref', 'quantity', 'unit', 'estimated_cost',
    'actual_cost', 'currency', 'source', 'occurred_at', 'cost_category',
]


def _record(**overrides) -> IncrementalCostRecord:
    values = {
        'record_id': 'rec-1', 'provider': 'prov-a', 'service': 'svc-a', 'operation_ref': 'op-1', 'job_ref': 'job-1',
        'batch_ref': None, 'quantity': D('1000'), 'unit': 'token', 'estimated_cost': D('1.5'), 'actual_cost': None,
        'currency': 'USD', 'source': 'fake-meter', 'occurred_at': '2026-10-05T00:00:00+00:00', 'cost_category': 'api_paid',
    }
    values.update(overrides)
    return IncrementalCostRecord(**values)


def _policy(**overrides) -> BudgetPolicy:
    values = {'monthly_limit': D('50')}
    values.update(overrides)
    return BudgetPolicy(**values)


def _spend(amount, when='2026-10-05T00:00:00+00:00', **overrides) -> IncrementalCostRecord:
    return _record(estimated_cost=D(str(amount)), occurred_at=when, **overrides)


def test_record_is_frozen_dataclass_with_fourteen_declared_fields():
    assert dataclasses.is_dataclass(IncrementalCostRecord)
    assert [f.name for f in dataclasses.fields(IncrementalCostRecord)] == EXPECTED_FIELDS
    record = _record()
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.estimated_cost = D('9')


def test_policy_and_status_are_frozen_with_declared_defaults():
    policy = BudgetPolicy(monthly_limit=None)
    assert (policy.monthly_limit, policy.warn_ratio, policy.hard_stop, policy.currency) == (None, D('0.8'), False, 'USD')
    assert [f.name for f in dataclasses.fields(BudgetStatus)] == ['spent', 'forecast', 'level', 'reason_codes']
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.hard_stop = True
    status = evaluate_budget([], policy, START, END, HALF)
    with pytest.raises(dataclasses.FrozenInstanceError):
        status.spent = D('1')


def test_category_sets_are_exact():
    assert incremental_cost.ALLOWED_COST_CATEGORIES == frozenset({'api_paid', 'background_service', 'extra_storage', 'other_direct'})
    assert incremental_cost.EXCLUDED_COST_CATEGORIES == frozenset({'existing_plan', 'electricity', 'internet', 'hardware'})


@pytest.mark.parametrize('category', ['api_paid', 'background_service', 'extra_storage', 'other_direct'])
def test_incremental_categories_are_accepted(category):
    assert _record(cost_category=category).cost_category == category


@pytest.mark.parametrize('category', ['existing_plan', 'electricity', 'internet', 'hardware', 'gemini_plan', '', None])
def test_non_incremental_or_unknown_category_is_rejected(category):
    with pytest.raises(NotIncrementalCostError):
        _record(cost_category=category)


BAD_AMOUNTS = [1.5, 0.0, 1, True, False, '1.5', D('-0.01'), D('-1'), D('NaN'), D('sNaN'), D('Infinity'), D('-Infinity')]


@pytest.mark.parametrize('field', ['quantity', 'estimated_cost', 'actual_cost'])
@pytest.mark.parametrize('bad', BAD_AMOUNTS)
def test_record_rejects_non_decimal_negative_or_nan_amounts(field, bad):
    with pytest.raises(InvalidAmountError):
        _record(**{field: bad})


def test_record_accepts_valid_decimal_amounts_and_actual_none():
    record = _record(quantity=D('0'), estimated_cost=D('0'), actual_cost=D('2.25'))
    assert record.actual_cost == D('2.25')
    assert _record(actual_cost=None).actual_cost is None


@pytest.mark.parametrize('bad', ['2026-10-05T00:00:00', 'not-a-date', '', None])
def test_record_rejects_naive_or_unparsable_occurred_at(bad):
    with pytest.raises(ValueError):
        _record(occurred_at=bad)


@pytest.mark.parametrize('field', ['record_id', 'provider', 'service', 'operation_ref', 'unit', 'currency', 'source'])
@pytest.mark.parametrize('bad', ['', '  ', None, 5])
def test_record_rejects_blank_or_non_string_text_fields(field, bad):
    with pytest.raises(ValueError):
        _record(**{field: bad})


@pytest.mark.parametrize('field', ['job_ref', 'batch_ref'])
def test_record_rejects_blank_optional_refs(field):
    with pytest.raises(ValueError):
        _record(**{field: ''})


@pytest.mark.parametrize('bad', [50, 50.0, True, D('0'), D('-1'), D('NaN'), D('Infinity')])
def test_policy_rejects_invalid_monthly_limit(bad):
    with pytest.raises(InvalidAmountError):
        BudgetPolicy(monthly_limit=bad)


@pytest.mark.parametrize('bad', [0.8, D('0'), D('-0.1'), D('1.01'), D('NaN')])
def test_policy_rejects_invalid_warn_ratio(bad):
    with pytest.raises(InvalidAmountError):
        BudgetPolicy(monthly_limit=D('50'), warn_ratio=bad)


def test_policy_accepts_ratio_one_and_rejects_non_bool_hard_stop_or_blank_currency():
    assert BudgetPolicy(monthly_limit=D('50'), warn_ratio=D('1')).warn_ratio == D('1')
    with pytest.raises(ValueError):
        BudgetPolicy(monthly_limit=D('50'), hard_stop=1)
    with pytest.raises(ValueError):
        BudgetPolicy(monthly_limit=D('50'), currency='')


def test_spent_counts_only_records_inside_half_open_window():
    records = [
        _spend(1, '2026-09-30T23:59:59+00:00'), _spend(2, '2026-10-01T00:00:00+00:00'),
        _spend(4, '2026-10-30T23:59:59+00:00'), _spend(8, '2026-10-31T00:00:00+00:00'),
    ]
    assert evaluate_budget(iter(records), _policy(), START, END, HALF).spent == D('6')


def test_window_uses_absolute_instants_across_timezone_offsets():
    records = [_spend(3, '2026-10-01T06:30:00+07:00'), _spend(4, '2026-10-01T07:00:00+07:00')]
    assert evaluate_budget(records, _policy(), START, END, HALF).spent == D('4')


def test_spent_prefers_actual_cost_over_estimated_cost():
    records = [_spend(10, actual_cost=D('7')), _spend(3), _spend(5, actual_cost=D('0'))]
    assert evaluate_budget(records, _policy(), START, END, HALF).spent == D('10')


def test_empty_records_give_zero_spent_zero_forecast_and_ok():
    status = evaluate_budget([], _policy(), START, END, HALF)
    assert status.spent == D('0')
    assert status.forecast == D('0')
    assert status.level is BudgetLevel.OK
    assert status.reason_codes == ()


def test_forecast_is_linear_extrapolation_over_the_window():
    status = evaluate_budget([_spend(20)], _policy(), START, END, HALF)
    assert status.spent == D('20')
    assert status.forecast == D('40')
    quarter = START + timedelta(days=10)
    assert evaluate_budget([_spend(10)], _policy(), START, END, quarter).forecast == D('30')


@pytest.mark.parametrize('now', [START, START - timedelta(days=1)])
def test_forecast_is_none_when_no_time_has_elapsed(now):
    status = evaluate_budget([_spend(20)], _policy(), START, END, now)
    assert status.forecast is None
    assert status.spent == D('20')


def test_forecast_is_capped_at_window_length_after_the_window_ends():
    status = evaluate_budget([_spend(20)], _policy(), START, END, END + timedelta(days=15))
    assert status.forecast == D('20')


def test_no_limit_when_monthly_limit_is_none():
    status = evaluate_budget([_spend(9999)], BudgetPolicy(monthly_limit=None), START, END, HALF)
    assert status.level is BudgetLevel.NO_LIMIT
    assert status.reason_codes == ()
    assert status.spent == D('9999')


def test_forecast_41_against_limit_50_warns_with_forecast_reason():
    status = evaluate_budget([_spend('20.5')], _policy(), START, END, HALF)
    assert status.forecast == D('41')
    assert status.level is BudgetLevel.WARN_80
    assert status.reason_codes == ('FORECAST_80',)


def test_forecast_exactly_at_threshold_warns():
    status = evaluate_budget([_spend(20)], _policy(), START, END, HALF)
    assert status.forecast == D('40')
    assert status.level is BudgetLevel.WARN_80
    assert status.reason_codes == ('FORECAST_80',)


def test_spent_at_eighty_percent_without_forecast_warns_with_spent_reason():
    status = evaluate_budget([_spend(40)], _policy(), START, END, START)
    assert status.forecast is None
    assert status.level is BudgetLevel.WARN_80
    assert status.reason_codes == ('SPENT_80',)


def test_spent_and_forecast_over_threshold_list_both_reasons_in_order():
    status = evaluate_budget([_spend(40)], _policy(), START, END, HALF)
    assert status.level is BudgetLevel.WARN_80
    assert status.reason_codes == ('SPENT_80', 'FORECAST_80')


@pytest.mark.parametrize('spent', ['50', '75'])
def test_spent_reaching_limit_is_exceeded(spent):
    status = evaluate_budget([_spend(spent)], _policy(), START, END, HALF)
    assert status.level is BudgetLevel.EXCEEDED
    assert status.reason_codes == ('LIMIT_REACHED',)


def test_below_threshold_is_ok():
    status = evaluate_budget([_spend(10)], _policy(), START, END, HALF)
    assert status.forecast == D('20')
    assert status.level is BudgetLevel.OK
    assert status.reason_codes == ()


def test_limit_100_and_25_are_evaluated_without_hard_coded_50():
    p100 = _policy(monthly_limit=D('100'))
    assert evaluate_budget([_spend(20)], p100, START, END, HALF).level is BudgetLevel.OK
    assert evaluate_budget([_spend(41)], p100, START, END, HALF).level is BudgetLevel.WARN_80
    assert evaluate_budget([_spend(50)], p100, START, END, HALF).level is BudgetLevel.WARN_80
    assert evaluate_budget([_spend(100)], p100, START, END, HALF).level is BudgetLevel.EXCEEDED
    assert evaluate_budget([_spend(25)], _policy(monthly_limit=D('25')), START, END, HALF).level is BudgetLevel.EXCEEDED


def test_custom_warn_ratio_changes_threshold_but_keeps_reason_code():
    policy = _policy(monthly_limit=D('100'), warn_ratio=D('0.5'))
    assert evaluate_budget([_spend(10)], policy, START, END, HALF).level is BudgetLevel.OK
    status = evaluate_budget([_spend(30)], policy, START, END, HALF)
    assert status.level is BudgetLevel.WARN_80
    assert status.reason_codes == ('FORECAST_80',)


def test_currency_mismatch_inside_window_raises():
    with pytest.raises(CurrencyMismatchError):
        evaluate_budget([_spend(1), _spend(1, currency='EUR')], _policy(), START, END, HALF)


def test_currency_is_checked_against_policy_currency():
    with pytest.raises(CurrencyMismatchError):
        evaluate_budget([_spend(1)], _policy(currency='EUR'), START, END, HALF)
    status = evaluate_budget([_spend(1, currency='EUR')], _policy(currency='EUR'), START, END, HALF)
    assert status.spent == D('1')


def test_currency_mismatch_outside_window_is_ignored():
    records = [_spend(1), _spend(5, '2026-09-01T00:00:00+00:00', currency='EUR')]
    assert evaluate_budget(records, _policy(), START, END, HALF).spent == D('1')


def test_naive_datetimes_or_empty_window_are_rejected():
    naive = datetime(2026, 10, 1)
    for args in [(naive, END, HALF), (START, naive, HALF), (START, END, naive), (END, START, HALF), (START, START, HALF)]:
        with pytest.raises(ValueError):
            evaluate_budget([], _policy(), *args)


def test_evaluate_budget_rejects_items_that_are_not_cost_records():
    with pytest.raises(TypeError):
        evaluate_budget([{'estimated_cost': 1}], _policy(), START, END, HALF)


def _status(spent: str) -> BudgetStatus:
    return BudgetStatus(spent=D(spent), forecast=None, level=BudgetLevel.OK, reason_codes=())


def test_should_block_is_false_when_hard_stop_is_off_even_if_exceeded():
    assert should_block(_status('60'), _policy(hard_stop=False), D('10')) is False


def test_should_block_is_true_only_when_hard_stop_and_total_exceeds_limit():
    policy = _policy(hard_stop=True)
    assert should_block(_status('45'), policy, D('5.01')) is True
    assert should_block(_status('45'), policy, D('5')) is False
    assert should_block(_status('60'), policy, D('0')) is True
    assert should_block(_status('10'), policy, D('5')) is False


def test_should_block_is_false_without_configured_limit():
    policy = BudgetPolicy(monthly_limit=None, hard_stop=True)
    assert should_block(_status('999999'), policy, D('999999')) is False


def test_should_block_uses_policy_limit_not_hard_coded_50():
    policy = _policy(monthly_limit=D('100'), hard_stop=True)
    assert should_block(_status('60'), policy, D('10')) is False
    assert should_block(_status('95'), policy, D('6')) is True


@pytest.mark.parametrize('bad', [1.5, 5, True, D('-1'), D('NaN')])
def test_should_block_rejects_invalid_additional_estimate(bad):
    with pytest.raises(InvalidAmountError):
        should_block(_status('1'), _policy(hard_stop=True), bad)


def test_module_never_reads_the_clock_or_uses_float():
    source = inspect.getsource(incremental_cost)
    for token in ('.now(', 'utcnow', 'today(', 'import time', 'float('):
        assert token not in source
