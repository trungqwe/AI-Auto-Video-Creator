"""G-12: resource admission (D8-G-06, D8-G-07; CT-WF-007).

coveredIds: D8-G-06, D8-G-07, CT-WF-007
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from controlplane.domain.orchestration.job_waiting import Wait, WaitReason, plan_job_transition
from controlplane.domain.orchestration.resource_admission import (
    AdmissionLimits, Admitted, DeferralCode, Deferred, ResourceNeed, ResourceSnapshot, decide_admission,
)
from controlplane.domain.statemachine import JobState

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'resource_admission.py'
LIMITS = AdmissionLimits(cpu_max_percent=90, ram_reserve_mb=1024, disk_reserve_mb=2048)
OK = ResourceSnapshot(cpu=40, gpu_slots_free=1, ram_free_mb=8192, disk_free_mb=50000, network_ok=True)
NEED = ResourceNeed(gpu_slots=1, ram_mb=4096, disk_mb=10000, needs_network=True)
DISK_WAIT = Wait(WaitReason.INSUFFICIENT_DISK)


def _snap(**changes):
    return dataclasses.replace(OK, **changes)


def test_enough_resources_is_admitted():
    assert decide_admission(LIMITS, OK, NEED) == Admitted()


@pytest.mark.parametrize('changes, code', [
    ({'cpu': 95}, DeferralCode.CPU_SATURATED),
    ({'cpu': 90}, DeferralCode.CPU_SATURATED),
    ({'gpu_slots_free': 0}, DeferralCode.GPU_BUSY),
    ({'ram_free_mb': 5000}, DeferralCode.RAM_LOW),
    ({'network_ok': False}, DeferralCode.NETWORK_DOWN),
])
def test_saturation_is_deferred_not_waiting(changes, code):
    result = decide_admission(LIMITS, _snap(**changes), NEED)
    assert result == Deferred(code)
    assert not isinstance(result, Wait)


def test_deferral_codes_are_exactly_the_four_d8_g_06_values():
    assert [c.value for c in DeferralCode] == ['CPU_SATURATED', 'GPU_BUSY', 'RAM_LOW', 'NETWORK_DOWN']


@pytest.mark.parametrize('changes', [{'cpu': 89.9}, {'ram_free_mb': 5120}, {'disk_free_mb': 12048}, {'gpu_slots_free': 3}])
def test_exact_threshold_boundaries_are_admitted(changes):
    assert decide_admission(LIMITS, _snap(**changes), NEED) == Admitted()


def test_unneeded_gpu_and_network_do_not_block():
    need = ResourceNeed(gpu_slots=0, ram_mb=4096, disk_mb=10000, needs_network=False)
    assert decide_admission(LIMITS, _snap(gpu_slots_free=0, network_ok=False), need) == Admitted()


@pytest.mark.parametrize('disk_free_mb', [0, 11000, 12047])
def test_insufficient_disk_is_wait_not_deferral(disk_free_mb):
    result = decide_admission(LIMITS, _snap(disk_free_mb=disk_free_mb), NEED)
    assert result == DISK_WAIT
    assert result.reason.value == 'insufficient_disk'


def test_check_order_is_network_cpu_gpu_ram_then_disk():
    low = {'network_ok': False, 'cpu': 99, 'gpu_slots_free': 0, 'ram_free_mb': 0, 'disk_free_mb': 0}
    assert decide_admission(LIMITS, _snap(**low), NEED) == Deferred(DeferralCode.NETWORK_DOWN)
    for dropped, code in [('network_ok', DeferralCode.CPU_SATURATED), ('cpu', DeferralCode.GPU_BUSY), ('gpu_slots_free', DeferralCode.RAM_LOW)]:
        low.pop(dropped)
        assert decide_admission(LIMITS, _snap(**low), NEED) == Deferred(code)
    low.pop('ram_free_mb')
    assert decide_admission(LIMITS, _snap(**low), NEED) == DISK_WAIT


def test_saturation_never_fails_the_job_and_disk_wait_maps_to_job_waiting():
    for changes in ({'cpu': 95}, {'gpu_slots_free': 0}, {'ram_free_mb': 1}, {'network_ok': False}):
        assert not isinstance(decide_admission(LIMITS, _snap(**changes), NEED), Wait)
    plan = plan_job_transition(current_state=JobState.ACTIVE, current_revision=3, expected_revision=3, decision=DISK_WAIT)
    assert plan.state == JobState.WAITING
    assert 'FAILED_FINAL' not in MODULE_PATH.read_text(encoding='utf-8')


LIMIT_FIELDS = {'cpu_max_percent': 90, 'ram_reserve_mb': 1024, 'disk_reserve_mb': 2048}
SNAPSHOT_FIELDS = {'cpu': 40, 'gpu_slots_free': 1, 'ram_free_mb': 8192, 'disk_free_mb': 50000, 'network_ok': True}
NEED_FIELDS = {'gpu_slots': 1, 'ram_mb': 4096, 'disk_mb': 10000, 'needs_network': True}
CASES = [(AdmissionLimits, LIMIT_FIELDS), (ResourceSnapshot, SNAPSHOT_FIELDS), (ResourceNeed, NEED_FIELDS)]


@pytest.mark.parametrize('cls, fields', CASES)
def test_every_field_is_required_without_default(cls, fields):
    with pytest.raises(TypeError):
        cls()
    for name in fields:
        with pytest.raises(TypeError):
            cls(**{k: v for k, v in fields.items() if k != name})
    for f in dataclasses.fields(cls):
        assert f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING


@pytest.mark.parametrize('cls, fields', CASES)
def test_types_and_ranges_are_validated(cls, fields):
    for name, good in fields.items():
        if isinstance(good, bool):
            bads = [None, 'x', [1], 1, 0]
        else:
            bads = [None, 'x', [1], True]
        for bad in bads:
            with pytest.raises(TypeError):
                cls(**dict(fields, **{name: bad}))
        if not isinstance(good, bool):
            with pytest.raises(ValueError):
                cls(**dict(fields, **{name: -1}))


@pytest.mark.parametrize('bad', [100.1, -0.1, float('nan')])
def test_cpu_percent_must_be_within_range(bad):
    with pytest.raises(ValueError):
        AdmissionLimits(**dict(LIMIT_FIELDS, cpu_max_percent=bad))
    with pytest.raises(ValueError):
        ResourceSnapshot(**dict(SNAPSHOT_FIELDS, cpu=bad))


@pytest.mark.parametrize('cls, fields', CASES)
def test_value_objects_are_frozen(cls, fields):
    obj = cls(**fields)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, next(iter(fields)), 0)


def test_decide_admission_rejects_wrong_argument_types():
    for args in [(OK, LIMITS, NEED), (LIMITS, OK, LIMITS), (LIMITS, OK, None), ({}, OK, NEED)]:
        with pytest.raises(TypeError):
            decide_admission(*args)


def test_deferred_requires_a_deferral_code():
    with pytest.raises(TypeError):
        Deferred('GPU_BUSY')


def test_thresholds_are_not_read_from_policy_files_or_environment():
    text = MODULE_PATH.read_text(encoding='utf-8')
    for banned in ('schedule-policy', 'yaml', 'open(', 'environ'):
        assert banned not in text


def test_module_imports_only_stdlib_and_controlplane_domain():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots, internal = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or '').split('.')[0])
            if (node.module or '').startswith('controlplane'):
                internal.add(node.module)
    assert roots <= {'__future__', 'dataclasses', 'enum', 'controlplane'}
    assert internal == {'controlplane.domain.orchestration.job_waiting'}
