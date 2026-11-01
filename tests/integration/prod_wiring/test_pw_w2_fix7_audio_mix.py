"""PW-W2-FIX7: AudioMixGate đo AUDIO_MIX_QUALITY trên FFmpeg ghim (mẫu lavfi của PW-F2, không DB).

coveredIds: CT-QC-001, PW-F2-01
"""
from __future__ import annotations

import ast
import json
import pathlib
import shutil

import pytest

from render.adapters.audio_mix_gate import AudioMixGate
from render.adapters.real_ffprobe_probe import measure_loudness
from render.domain.quality_report import GateName, QualityPolicy
from tests.integration.prod_wiring.test_pw_f2_inspector_audio import FFMPEG, LOCK_PATH, build_sample, require_ffmpeg

ROOT = pathlib.Path(__file__).resolve().parents[3]
WIRING = ROOT / 'src' / 'controlplane' / 'api' / 'wiring' / 'render.py'
REVISION = 'pw-w2-fix7'
REF = 'out/qc-fix7.mp4'


def policy_of(**entry) -> QualityPolicy:
    return QualityPolicy(revision=REVISION, thresholds={'AUDIO_MIX_QUALITY': entry})


def staged(tmp_path):
    require_ffmpeg()
    sample = build_sample(tmp_path / 'sample', audio='voice')
    staging = sample['root'] / 'staging'
    (staging / 'out').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sample['output_ref'], staging / 'out' / 'qc-fix7.mp4')
    stats = measure_loudness(FFMPEG, pathlib.Path(sample['output_ref']))
    assert stats.integrated_lufs is not None and stats.true_peak_dbtp is not None
    print(f'AUDIO_MIX_EVIDENCE measured integrated_lufs={stats.integrated_lufs} true_peak_dbtp={stats.true_peak_dbtp}')
    return sample, staging, stats


def gate_of(staging, lock_path=LOCK_PATH) -> AudioMixGate:
    return AudioMixGate(ffmpeg_path=FFMPEG, lock_path=lock_path, staging_root=staging, timeout_seconds=60)


def only(results):
    assert len(results) == 1
    (item,) = results
    print(f'AUDIO_MIX_EVIDENCE gate status={item.status.value} reason={item.reason} measured_value={item.measured_value} evidence_ref={item.evidence_ref}')
    assert item.gate is GateName.AUDIO_MIX_QUALITY and item.threshold_revision == REVISION
    return item


def passing_policy(stats) -> QualityPolicy:
    return policy_of(target_lufs=stats.integrated_lufs, tolerance_lu=0.5, max_true_peak_dbtp=stats.true_peak_dbtp + 1.0)


def test_measured_loudness_inside_the_limits_passes(tmp_path):
    sample, staging, stats = staged(tmp_path)
    item = only(gate_of(staging)(sample['output_ref'], sample['package'], passing_policy(stats)))
    assert item.status.value == 'passed' and item.reason is None
    assert isinstance(item.measured_value, float) and item.measured_value == pytest.approx(stats.integrated_lufs, abs=0.1)
    assert item.evidence_ref.startswith(sample['output_ref']) and 'LUFS' in item.evidence_ref and 'dBTP' in item.evidence_ref


def test_loudness_far_from_target_is_a_failed_warning(tmp_path):
    sample, staging, stats = staged(tmp_path)
    policy = policy_of(target_lufs=stats.integrated_lufs - 10.0, tolerance_lu=0.5, max_true_peak_dbtp=stats.true_peak_dbtp + 1.0)
    item = only(gate_of(staging)(sample['output_ref'], sample['package'], policy))
    assert (item.status.value, item.reason) == ('failed', 'loudness_out_of_target')


def test_true_peak_above_the_limit_is_a_failed_warning(tmp_path):
    sample, staging, stats = staged(tmp_path)
    policy = policy_of(target_lufs=stats.integrated_lufs, tolerance_lu=0.5, max_true_peak_dbtp=stats.true_peak_dbtp - 1.0)
    item = only(gate_of(staging)(sample['output_ref'], sample['package'], policy))
    assert (item.status.value, item.reason) == ('failed', 'true_peak_above_limit')


def test_a_relative_ref_resolves_under_the_staging_root(tmp_path):
    sample, staging, stats = staged(tmp_path)
    item = only(gate_of(staging)(REF, sample['package'], passing_policy(stats)))
    assert item.status.value == 'passed' and isinstance(item.measured_value, float)
    assert item.evidence_ref.startswith(REF) and 'LUFS' in item.evidence_ref


def test_a_wrong_pin_or_a_missing_file_is_not_evaluated_and_never_raises(tmp_path):
    sample, staging, stats = staged(tmp_path)
    bad = tmp_path / 'bad.lock.json'
    bad.write_text(json.dumps({'pins': {'ffmpeg': {'status': 'PINNED', 'sha256': '0' * 64}}}), encoding='utf-8')
    wrong_pin = only(gate_of(staging, bad)(sample['output_ref'], sample['package'], passing_policy(stats)))
    no_file = only(gate_of(staging)(str(tmp_path / 'missing.mp4'), sample['package'], passing_policy(stats)))
    for item in (wrong_pin, no_file):
        assert (item.status.value, item.reason, item.measured_value) == ('not_evaluated', 'loudness_not_measured', None)


def test_missing_or_partial_thresholds_give_no_result(tmp_path):
    sample, staging, _ = staged(tmp_path)
    gate = gate_of(staging)
    cases = (
        {},
        {'AUDIO_MIX_QUALITY': {}},
        {'AUDIO_MIX_QUALITY': {'target_lufs': -14.0}},
        {'AUDIO_MIX_QUALITY': {'target_lufs': -14.0, 'tolerance_lu': 0.5}},
    )
    for thresholds in cases:
        assert gate(sample['output_ref'], sample['package'], QualityPolicy(revision=REVISION, thresholds=thresholds)) == ()


def test_render_activity_deps_wires_the_audio_mix_gate_into_the_output_pipeline():
    tree = ast.parse(WIRING.read_text(encoding='utf-8'))
    deps = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'render_activity_deps')
    pipes = [n for n in ast.walk(deps) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'OutputPipeline']
    assert len(pipes) == 1
    gates = [k.value for k in pipes[0].keywords if k.arg == 'warning_gates']
    assert len(gates) == 1 and isinstance(gates[0], ast.Call) and isinstance(gates[0].func, ast.Name) and gates[0].func.id == 'AudioMixGate'
    assert {k.arg for k in gates[0].keywords} == {'ffmpeg_path', 'lock_path', 'staging_root', 'timeout_seconds'}


def test_module_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: CT-QC-001, PW-F2-01' in (doc or '').splitlines()
