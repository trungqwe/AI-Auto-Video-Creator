"""PW-W2-FIX6: QC production đo VOICE_AUDIBLE thật bằng build_qc_probe (FFmpeg ghim, cửa sổ lời từ ASS).

coveredIds: CT-QC-001, PW-F2-01
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import shutil

from controlplane.api.wiring.render import StagingResolvingProbe, build_qc_probe
from render.adapters.real_output_inspector import InspectionInputs, RealOutputInspector
from render.domain.technical_gates import evaluate_technical_gates
from tests.integration.prod_wiring.test_pw_f2_inspector_audio import (
    FFMPEG,
    FLAT_POLICY,
    GOOD_LANGUAGE,
    LOCK_PATH,
    PROFILE,
    SETTINGS,
    build_sample,
    require_ffmpeg,
)
from tests.integration.prod_wiring.test_pw_w2_launcher_def import make_runtime

ROOT = pathlib.Path(__file__).resolve().parents[3]
WIRING = ROOT / 'src' / 'controlplane' / 'api' / 'wiring' / 'render.py'
REF = 'out/qc-fix6.mp4'


def staged(tmp_path):
    require_ffmpeg()
    sample = build_sample(tmp_path / 'sample', audio='voice')
    staging = sample['root'] / 'staging'
    (staging / 'out').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sample['output_ref'], staging / 'out' / 'qc-fix6.mp4')
    runtime = dataclasses.replace(
        make_runtime(tmp_path),
        ffmpeg_path=FFMPEG,
        ffprobe_path=FFMPEG.with_name('ffprobe.exe'),
        runtime_lock_path=LOCK_PATH,
        staging_root=staging,
    )
    inspector = RealOutputInspector(
        inputs=InspectionInputs(staging_root=staging, ass_ref='ref-ass', segments=[], language=GOOD_LANGUAGE),
        settings=SETTINGS,
        lock_path=LOCK_PATH,
    )
    return runtime, inspector.speech_windows(sample['package'])


def voice_gate(runtime, windows):
    probe = build_qc_probe(runtime, timeout_seconds=60.0, voice_windows=windows)
    assert isinstance(probe, StagingResolvingProbe)
    technical = evaluate_technical_gates(probe, REF, policy=FLAT_POLICY, expected_profile=PROFILE, threshold_revision='pw-w2-fix6')
    return {g.gate.value: g for g in technical}['VOICE_AUDIBLE']


def test_qc_probe_measures_voice_over_the_speech_windows(tmp_path):
    runtime, windows = staged(tmp_path)
    assert windows
    gate = voice_gate(runtime, windows)
    assert gate.status.value == 'passed'
    assert gate.reason is None
    assert isinstance(gate.measured_value, (int, float)) and not isinstance(gate.measured_value, bool)


def test_qc_probe_without_speech_windows_measures_the_whole_stream_and_fails(tmp_path):
    runtime, _ = staged(tmp_path)
    gate = voice_gate(runtime, ())
    assert gate.status.value == 'failed'
    assert gate.reason == 'voice_below_min_level'
    assert isinstance(gate.measured_value, (int, float)) and not isinstance(gate.measured_value, bool)


def test_render_activity_deps_builds_the_qc_probe_per_package():
    tree = ast.parse(WIRING.read_text(encoding='utf-8'))
    deps = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'render_activity_deps')
    calls = [n for n in ast.walk(deps) if isinstance(n, ast.Call)]
    pipes = [c for c in calls if isinstance(c.func, ast.Name) and c.func.id == 'OutputPipeline']
    assert len(pipes) == 1
    assert 'probe_for' in {k.arg for k in pipes[0].keywords}
    assert 'build_qc_probe' in {c.func.id for c in calls if isinstance(c.func, ast.Name)}
    assert 'speech_windows' in {c.func.attr for c in calls if isinstance(c.func, ast.Attribute)}
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or '')
    assert not [m for m in modules if m == 'src' or m.startswith('src.')]
