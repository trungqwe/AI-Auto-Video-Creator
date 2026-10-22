"""Static AST tests for deterministic workflow modules (D8-G-07, CT-WF-001, CT-WF-002, CT-WF-009).

coveredIds: CP-6-WORKFLOW-STATIC
"""
from __future__ import annotations

import ast
import pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = ROOT / 'src' / 'controlplane' / 'application' / 'orchestration' / 'workflows'
MODULES = sorted(WORKFLOWS_DIR.glob('*.py'))

BANNED_MODULE_ROOTS = frozenset({
    'time',
    'random',
    'socket',
    'uuid',
    'secrets',
    'os',
    'subprocess',
    'threading',
    'asyncio',
    'urllib',
    'http',
    'requests',
    'httpx',
    'aiohttp',
})

CLOCK_ATTRS = frozenset({'now', 'utcnow', 'today', 'fromtimestamp', 'monotonic', 'perf_counter'})
CLOCK_NAMES = frozenset({'datetime', 'date', 'time'})

TIMING_KEYWORDS = frozenset({
    'start_to_close_timeout',
    'schedule_to_close_timeout',
    'schedule_to_start_timeout',
    'heartbeat_timeout',
    'initial_interval',
    'maximum_interval',
    'maximum_attempts',
    'backoff_coefficient',
    'seconds',
    'minutes',
    'hours',
})
TIMING_CLASSES = frozenset({'timedelta', 'RetryPolicy', 'TemporalRetryPolicy'})
TIMING_NAME_SUBSTRINGS = (
    'TIMEOUT',
    'RETRY',
    'BACKOFF',
    'ATTEMPT',
    'DELAY',
    'INTERVAL',
    'HEARTBEAT',
    'TTL',
)


def _is_numeric_constant(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    return False


def banned_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split('.')[0]
                if root in BANNED_MODULE_ROOTS:
                    violations.append(f'import {alias.name}')
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split('.')[0]
            if root in BANNED_MODULE_ROOTS:
                violations.append(f'from {node.module} import ...')
    return violations


def clock_calls(source: str) -> list[str]:
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {'open', 'print'}:
                violations.append(f'call to {func.id}()')
            elif isinstance(func, ast.Attribute):
                if func.attr in CLOCK_ATTRS:
                    if isinstance(func.value, ast.Name) and func.value.id in CLOCK_NAMES:
                        violations.append(f'{func.value.id}.{func.attr}()')
                    elif isinstance(func.value, ast.Attribute) and func.value.attr in CLOCK_NAMES:
                        violations.append(f'{func.value.attr}.{func.attr}()')
    return violations


def hardcoded_timing(source: str) -> list[str]:
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg in TIMING_KEYWORDS and _is_numeric_constant(kw.value):
                    violations.append(f'hardcoded keyword {kw.arg}={kw.value.value}')
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name in TIMING_CLASSES:
                for arg in node.args:
                    if _is_numeric_constant(arg):
                        violations.append(f'{func_name} positional numeric constant {arg.value}')
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id
                    if name.isupper() and any(sub in name for sub in TIMING_NAME_SUBSTRINGS):
                        if _is_numeric_constant(node.value):
                            violations.append(f'hardcoded module constant {name}={node.value.value}')
    return violations


def test_workflow_modules_exist():
    expected = {'settings.py', 'activities.py', 'flow.py', 'batch.py', 'definitions.py'}
    found = {p.name for p in MODULES if p.name != '__init__.py'}
    assert expected.issubset(found)


def test_init_is_untouched_and_empty():
    init_path = WORKFLOWS_DIR / '__init__.py'
    assert init_path.exists()
    assert init_path.stat().st_size == 0


@pytest.mark.parametrize('module_path', MODULES, ids=lambda p: p.name)
def test_workflow_modules_are_deterministic(module_path: pathlib.Path):
    source = module_path.read_text(encoding='utf-8')
    assert banned_imports(source) == []
    assert clock_calls(source) == []
    assert hardcoded_timing(source) == []


def test_checkers_catch_counterexamples():
    assert banned_imports('import time') != []
    assert banned_imports('from random import random') != []
    assert banned_imports('import socket') != []
    assert clock_calls('datetime.now()') != []
    assert hardcoded_timing('timedelta(seconds=30)') != []
    assert hardcoded_timing('TemporalRetryPolicy(maximum_attempts=3)') != []
    assert hardcoded_timing('START_TO_CLOSE_TIMEOUT = 60') != []
    assert hardcoded_timing('timedelta(seconds=settings.x)') == []
