"""G-11: chính sách retry/backoff (CT-WF-007; D8-G-07).

coveredIds: CT-WF-007
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import math
import pathlib

import pytest

from controlplane.domain.orchestration.retry_policy import (
    RetryPolicy,
    TimeoutKind,
    attempts_after_timeout,
    consumes_attempt,
    next_delay,
    should_retry,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'retry_policy.py'
P = RetryPolicy(max_attempts=5, initial_delay_seconds=1, multiplier=2, max_delay_seconds=4)


def test_delay_sequence_is_exponential_and_capped():
    assert [next_delay(n, P) for n in range(1, 7)] == [1, 2, 4, 4, 4, 4]


def test_delay_with_fractional_values():
    p = RetryPolicy(max_attempts=4, initial_delay_seconds=0.5, multiplier=3, max_delay_seconds=100)
    assert [next_delay(n, p) for n in range(1, 5)] == [0.5, 1.5, 4.5, 13.5]


def test_delay_is_deterministic():
    results = [next_delay(3, P) for _ in range(20)]
    assert len(set(results)) == 1


def test_delay_never_exceeds_cap():
    for n in range(1, 201):
        assert 0 < next_delay(n, P) <= 4


def test_delay_huge_attempt_returns_cap_without_overflow():
    assert next_delay(10**9, P) == 4
    p_mult1 = RetryPolicy(3, 2, 1, 9)
    assert next_delay(10**9, p_mult1) == 2


def test_delay_rejects_invalid_attempt():
    for bad in (0, -1):
        with pytest.raises(ValueError):
            next_delay(bad, P)
    for bad in (True, 1.5, '1', None):
        with pytest.raises(TypeError):
            next_delay(bad, P)
    with pytest.raises(TypeError):
        next_delay(1, 'x')


def test_policy_requires_every_parameter():
    with pytest.raises(TypeError):
        RetryPolicy()
    kwargs = {'max_attempts': 3, 'initial_delay_seconds': 1, 'multiplier': 2, 'max_delay_seconds': 8}
    for field_name in kwargs:
        kw = dict(kwargs)
        del kw[field_name]
        with pytest.raises(TypeError):
            RetryPolicy(**kw)


def test_no_default_values():
    for f in dataclasses.fields(RetryPolicy):
        assert f.default is dataclasses.MISSING
        assert f.default_factory is dataclasses.MISSING
    for fn in (next_delay, should_retry, consumes_attempt, attempts_after_timeout):
        for param in inspect.signature(fn).parameters.values():
            assert param.default is inspect.Parameter.empty


@pytest.mark.parametrize(
    ('override_kwargs', 'expected_exc'),
    [
        ({'max_attempts': 0}, ValueError),
        ({'max_attempts': -1}, ValueError),
        ({'max_attempts': True}, TypeError),
        ({'max_attempts': 2.5}, TypeError),
        ({'max_attempts': '3'}, TypeError),
        ({'initial_delay_seconds': 0}, ValueError),
        ({'initial_delay_seconds': -1}, ValueError),
        ({'initial_delay_seconds': math.nan}, ValueError),
        ({'initial_delay_seconds': math.inf}, ValueError),
        ({'initial_delay_seconds': True}, TypeError),
        ({'initial_delay_seconds': '1'}, TypeError),
        ({'initial_delay_seconds': None}, TypeError),
        ({'multiplier': 0.5}, ValueError),
        ({'multiplier': 0}, ValueError),
        ({'multiplier': math.nan}, ValueError),
        ({'multiplier': True}, TypeError),
        ({'multiplier': '2'}, TypeError),
        ({'max_delay_seconds': 0.5}, ValueError),
        ({'max_delay_seconds': math.inf}, ValueError),
        ({'max_delay_seconds': '8'}, TypeError),
    ],
)
def test_policy_rejects_invalid_values(override_kwargs, expected_exc):
    base = {'max_attempts': 3, 'initial_delay_seconds': 1, 'multiplier': 2, 'max_delay_seconds': 8}
    kwargs = {**base, **override_kwargs}
    with pytest.raises(expected_exc):
        RetryPolicy(**kwargs)


def test_policy_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        P.max_attempts = 9


@pytest.mark.parametrize(
    ('attempt', 'retryable', 'max_attempts', 'expected'),
    [
        (1, True, 3, True),
        (2, True, 3, True),
        (3, True, 3, False),
        (4, True, 3, False),
        (1, False, 3, False),
        (2, False, 3, False),
        (1, True, 1, False),
    ],
)
def test_should_retry_table(attempt, retryable, max_attempts, expected):
    policy = RetryPolicy(max_attempts, 1, 2, 8)
    assert should_retry(attempt, retryable, policy) is expected


def test_should_retry_rejects_invalid_arguments():
    with pytest.raises(ValueError):
        should_retry(0, True, P)
    with pytest.raises(TypeError):
        should_retry(True, True, P)
    for bad in (1, None, 'yes'):
        with pytest.raises(TypeError):
            should_retry(1, bad, P)
    with pytest.raises(TypeError):
        should_retry(1, True, 'x')


def test_schedule_to_start_timeout_does_not_consume_attempt():
    assert consumes_attempt(TimeoutKind.SCHEDULE_TO_START) is False
    assert consumes_attempt('schedule_to_start') is False
    assert consumes_attempt(TimeoutKind.START_TO_CLOSE) is True
    assert consumes_attempt('heartbeat') is True
    with pytest.raises(ValueError):
        consumes_attempt('foo')
    with pytest.raises(ValueError):
        consumes_attempt(5)


def test_repeated_schedule_to_start_never_exhausts_retries():
    consumed = 2
    for _ in range(50):
        consumed = attempts_after_timeout(consumed, 'schedule_to_start')
    assert consumed == 2
    assert should_retry(consumed, True, P) is True
    assert attempts_after_timeout(2, TimeoutKind.START_TO_CLOSE) == 3
    assert attempts_after_timeout(0, 'heartbeat') == 1
    with pytest.raises(ValueError):
        attempts_after_timeout(-1, 'heartbeat')
    with pytest.raises(TypeError):
        attempts_after_timeout(True, 'heartbeat')


def test_no_hard_coded_numeric_defaults():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    numbers = {
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)
    }
    assert numbers <= {0, 1}


def test_module_has_no_unbounded_loop():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    while_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.While)]
    assert len(while_nodes) == 0


def test_module_imports_only_stdlib():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or '').split('.')[0])
    assert roots <= {'__future__', 'dataclasses', 'enum', 'math'}
