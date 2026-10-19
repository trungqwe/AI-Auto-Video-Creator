"""F-21: projection truy vết read-only của F (CT-RND-004, CT-QC-001, TST-E2E-001).

coveredIds: CT-RND-004, CT-QC-001 (truy vết), TST-E2E-001 (truy vết ngược từ output)
"""
import ast
import dataclasses
import inspect
import json
import pathlib
from datetime import datetime, timedelta, timezone

import pytest
from controlplane.domain.statemachine import OperationState
from render.adapters import memory
from render.domain.package_contract import validate_render_package_payload
from render.domain.quality_report import GATE_KINDS, GateKind, GateName, GateResult, build_quality_report
from render.domain.render_attempt import fail_attempt, prepare_attempt, start_attempt, succeed_attempt
from render.domain.render_command import RenderCommandSpec, ToolIdentity
from render.projections import trace_queries as tq

ROOT = pathlib.Path(__file__).resolve().parents[3]
PACKAGE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'
SOURCE = ROOT / 'src' / 'render' / 'projections' / 'trace_queries.py'
CANARY = 'CANARY-7f3a9c-SECRET'
NOW = datetime(2026, 10, 19, 8, 0, 0, tzinfo=timezone.utc)
OUT1 = 'artifact/render/attempt-1/out.mp4'
OUT2 = 'artifact/render/attempt-2/out.mp4'
OUT9 = 'artifact/render/attempt-9/out.mp4'


def at(seconds: int) -> datetime:
    return NOW + timedelta(seconds=seconds)


def raw_package() -> dict:
    return json.loads(PACKAGE_FIXTURE.read_text(encoding='utf-8'))['entities']['RenderPackage']['valid'][0]


def package(pid: str = 'pkg-1', char: str = 'a'):
    return dataclasses.replace(validate_render_package_payload(raw_package()), render_package_id=pid, package_fingerprint=char * 64)


def spec() -> RenderCommandSpec:
    return RenderCommandSpec(
        kind='render',
        argv=('C:/tools/ffmpeg.exe', '-i', f'C:/staging/{CANARY}/a.mp4'),
        redacted_argv=('{:tool}', '-i', '{asset:0}'),
        spec_fingerprint='f' * 64,
        tool_identity=ToolIdentity(name='ffmpeg', version='6.1', build='test-build', executable='C:/tools/ffmpeg.exe'),
    )


def attempt_chain(attempt_id: str, fingerprint: str = 'a' * 64, fail: bool = False):
    """PREPARED, STARTED and the final revision of one attempt; the output ref is derived from the attempt id."""
    prepared = prepare_attempt(
        render_attempt_id=attempt_id,
        package_fingerprint=fingerprint,
        output_artifact_ref=f'artifact/render/{attempt_id}/out.mp4',
        command_spec=spec(),
        receipt_ref=f'receipt-{attempt_id}',
    )
    running = start_attempt(prepared, expected_revision=0, started_at=at(0))
    if fail:
        final = fail_attempt(running, expected_revision=1, finished_at=at(30), error=f'ffmpeg exited with code 1 password={CANARY}')
    else:
        final = succeed_attempt(
            running, expected_revision=1, finished_at=at(60), wall_time_ms=60000,
            warnings=[f'note {CANARY}'], secret_values=[CANARY],
        )
    return prepared, running, final


def quality(failing=(), reason='gate_failed'):
    results = [
        GateResult(
            gate=name,
            status='failed' if name in failing else 'passed',
            evidence_ref=f'evidence-{name.value.lower()}',
            reason=reason if name in failing else None,
        )
        for name in GateName
        if GATE_KINDS[name] is GateKind.HARD
    ]
    return build_quality_report(results, {GateName.INFERENCE_DISCLOSURE_PRESENT: False})


def seed(*, failing=(), reason='gate_failed', final=None, package_char='a', with_package=True, with_report=True):
    """In-memory store: pkg-1 with attempt-1 (failed), attempt-2 (succeeded) and report qr-1, plus pkg-9 and attempt-9 of another workspace."""
    uow = memory.InMemoryUnitOfWork()
    chains = {
        'attempt-1': attempt_chain('attempt-1', fail=True),
        'attempt-2': attempt_chain('attempt-2'),
        'attempt-9': attempt_chain('attempt-9', 'b' * 64),
    }
    if final is not None:
        chains['attempt-2'] = (*chains['attempt-2'][:2], final)
    with uow:
        if with_package:
            uow.renders.append('render_package', 'pkg-1', 1, package('pkg-1', package_char))
        uow.renders.append('render_package', 'pkg-9', 1, package('pkg-9', 'b'))
        for key, chain in chains.items():
            for number, record in enumerate(chain, 1):
                uow.renders.append('render_attempt', key, number, record)
        if with_report:
            uow.renders.append('quality_report', 'qr-1', 1, quality(failing, reason))
        uow.commit()
    return uow


class _Counter:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *args, **kwargs) -> None:
        self.calls += 1


class _Reads:
    """Read-only view of the repository: it has no append, so a query that writes raises AttributeError."""

    def __init__(self, repo) -> None:
        self._repo = repo
        self.calls = []

    def latest(self, kind, key):
        self.calls.append('latest')
        return self._repo.latest(kind, key)

    def revisions(self, kind, key):
        self.calls.append('revisions')
        return self._repo.revisions(kind, key)


class FakeStore:
    def __init__(self, uow) -> None:
        self.renders = _Reads(uow.renders)
        self.renderer = _Counter()
        self.probe = _Counter()


def link(attempt='attempt-2', package_id='pkg-1', workspace='ws-a', report='qr-1', **over):
    return tq.TraceLink(
        workspace_id=workspace, render_package_id=package_id, render_attempt_id=attempt, quality_report_key=report, **over,
    )


def links(**over):
    return [link('attempt-1', report=None), link(**over), link('attempt-9', 'pkg-9', 'ws-b', None)]


def store(**kw) -> FakeStore:
    return FakeStore(seed(**kw))


def test_trace_output_walks_back_to_attempt_package_inputs_tool_command_and_gates():
    trace = tq.trace_output(store(), links(), workspace_id='ws-a', output_artifact_ref=OUT2)
    raw = raw_package()
    assert (trace.workspace_id, trace.output_artifact_ref) == ('ws-a', OUT2)
    assert trace.attempt.render_attempt_id == 'attempt-2'
    assert trace.attempt.package_fingerprint == trace.package.package_fingerprint == 'a' * 64
    for name in (
        'production_snapshot_ref', 'script_version_ref', 'production_plan_ref', 'preset_revision_ref',
        'voice_artifact_ref', 'word_timing_ref', 'output_metadata_revision', 'output_profile_revision',
    ):
        assert getattr(trace.package, name) == raw[name]
    assert trace.package.language_validation_refs == tuple(raw['language_validation_refs'])
    assert [dataclasses.asdict(item) for item in trace.package.input_artifacts] == raw['input_artifacts']
    attempt = trace.attempt
    assert (attempt.tool_name, attempt.tool_version, attempt.build_version) == ('ffmpeg', '6.1', 'test-build')
    assert attempt.command_spec.kind == 'render'
    assert attempt.command_spec.redacted_argv == ('{:tool}', '-i', '{asset:0}')
    assert attempt.command_spec.spec_fingerprint == 'f' * 64
    assert attempt.receipt_state == OperationState.SUCCEEDED.value
    assert attempt.receipt_ref == 'receipt-attempt-2'
    gates = trace.quality.gates
    assert [item.gate for item in gates] == [name.value for name in GateName]
    assert all(item.evidence_ref == f'evidence-{item.gate.lower()}' for item in gates if item.kind == 'hard')


def test_history_lists_every_revision_and_attempt_without_overwriting():
    s = store()
    states = [OperationState.PREPARED.value, OperationState.STARTED.value, OperationState.SUCCEEDED.value]
    latest = tq.trace_attempt(s, links(), workspace_id='ws-a', render_attempt_id='attempt-2')
    assert [(item.revision, item.receipt_state) for item in latest.history] == list(zip((1, 2, 3), states))
    assert (latest.revision, latest.attempt_revision) == (3, 2)
    first = tq.trace_attempt(s, links(), workspace_id='ws-a', render_attempt_id='attempt-2', revision=1)
    assert (first.revision, first.attempt_revision, first.receipt_state) == (1, 0, states[0])
    assert first.history == latest.history
    with pytest.raises(tq.TraceNotFound):
        tq.trace_attempt(s, links(), workspace_id='ws-a', render_attempt_id='attempt-2', revision=9)
    package_trace = tq.trace_render_package(s, links(), workspace_id='ws-a', render_package_id='pkg-1')
    assert [(item.render_attempt_id, item.receipt_state, item.output_artifact_ref) for item in package_trace.attempts] == [
        ('attempt-1', OperationState.FAILED.value, OUT1),
        ('attempt-2', OperationState.SUCCEEDED.value, OUT2),
    ]
    assert [item.revision for item in package_trace.history] == [1]


@pytest.mark.parametrize('upload', [False, True])
@pytest.mark.parametrize('completion', [False, True])
def test_four_milestones_stay_four_independent_facts(upload, completion):
    trace = tq.trace_output(
        store(), links(upload_verified=upload, completion_committed=completion), workspace_id='ws-a', output_artifact_ref=OUT2,
    )
    assert dataclasses.asdict(trace.milestones) == {
        'render_succeeded': True, 'qc_passed': True, 'upload_verified': upload, 'completion_committed': completion,
    }
    assert set(trace.to_payload()['milestones']) == {'render_succeeded', 'qc_passed', 'upload_verified', 'completion_committed'}


def test_render_succeeded_qc_failed_and_failed_render_are_reported_separately():
    qc_failed = tq.trace_output(
        store(failing=(GateName.FILE_PLAYABLE,)), links(upload_verified=True), workspace_id='ws-a', output_artifact_ref=OUT2,
    )
    assert dataclasses.asdict(qc_failed.milestones) == {
        'render_succeeded': True, 'qc_passed': False, 'upload_verified': True, 'completion_committed': False,
    }
    only = [link('attempt-1', report=None, upload_verified=True, completion_committed=True)]
    render_failed = tq.trace_output(store(), only, workspace_id='ws-a', output_artifact_ref=OUT1)
    assert render_failed.quality is None
    assert dataclasses.asdict(render_failed.milestones) == {
        'render_succeeded': False, 'qc_passed': False, 'upload_verified': True, 'completion_committed': True,
    }


def test_every_query_returns_not_found_for_another_workspace():
    s = store()
    calls = (
        lambda ws: tq.trace_render_package(s, links(), workspace_id=ws, render_package_id='pkg-1'),
        lambda ws: tq.trace_attempt(s, links(), workspace_id=ws, render_attempt_id='attempt-2'),
        lambda ws: tq.trace_quality_report(s, links(), workspace_id=ws, quality_report_key='qr-1'),
        lambda ws: tq.trace_output(s, links(), workspace_id=ws, output_artifact_ref=OUT2),
    )
    for call in calls:
        assert call('ws-a') is not None
        for other in ('ws-b', 'ws-unknown'):
            with pytest.raises(tq.TraceNotFound):
                call(other)


def test_workspace_b_trace_holds_nothing_of_workspace_a():
    trace = tq.trace_output(store(), links(), workspace_id='ws-b', output_artifact_ref=OUT9)
    payload = json.dumps(trace.to_payload())
    assert trace.attempt.render_attempt_id == 'attempt-9'
    for text in ('attempt-1', 'attempt-2', 'pkg-1', OUT1, OUT2, 'qr-1', 'a' * 64):
        assert text not in payload


def test_links_reject_duplicate_attempt_and_package_or_report_shared_by_two_workspaces():
    s = store()
    bad = (
        [link(), link()],
        [link(), link('attempt-3', workspace='ws-b', report=None)],
        [link(), link('attempt-3', 'pkg-3', 'ws-b', 'qr-1')],
    )
    for items in bad:
        with pytest.raises(ValueError):
            tq.trace_attempt(s, items, workspace_id='ws-a', render_attempt_id='attempt-2')


def test_queries_never_call_renderer_or_probe_and_only_read():
    uow = seed()
    s = FakeStore(uow)
    tq.trace_render_package(s, links(), workspace_id='ws-a', render_package_id='pkg-1')
    tq.trace_attempt(s, links(), workspace_id='ws-a', render_attempt_id='attempt-2')
    tq.trace_quality_report(s, links(), workspace_id='ws-a', quality_report_key='qr-1')
    tq.trace_output(s, links(), workspace_id='ws-a', output_artifact_ref=OUT2)
    assert s.renderer.calls == 0 and s.probe.calls == 0
    assert s.renders.calls and set(s.renders.calls) <= {'latest', 'revisions'}
    assert len(uow.renders.revisions('render_attempt', 'attempt-2')) == 3
    forbidden = {'renderer', 'probe', 'inspector', 'adapter', 'route', 'uow'}
    for name in ('trace_render_package', 'trace_attempt', 'trace_quality_report', 'trace_output'):
        assert not forbidden & set(inspect.signature(getattr(tq, name)).parameters)


def test_trace_quality_report_lists_gates_with_evidence_and_blocking_gates():
    ok = tq.trace_quality_report(store(), links(), workspace_id='ws-a', quality_report_key='qr-1')
    assert ok.passed is True and ok.blocking_gates == () and ok.policy_revision is None
    assert [item.revision for item in ok.history] == [1]
    bad = tq.trace_quality_report(store(failing=(GateName.FILE_PLAYABLE,)), links(), workspace_id='ws-a', quality_report_key='qr-1')
    assert bad.passed is False and bad.blocking_gates == ('FILE_PLAYABLE',)
    gate = next(item for item in bad.gates if item.gate == 'FILE_PLAYABLE')
    assert (gate.status, gate.reason, gate.evidence_ref) == ('failed', 'gate_failed', 'evidence-file_playable')
    assert ok.report_id and ok.report_id != bad.report_id


def test_traces_are_frozen_json_safe_and_deterministic():
    s = store()
    first = tq.trace_output(s, links(), workspace_id='ws-a', output_artifact_ref=OUT2)
    second = tq.trace_output(s, links(), workspace_id='ws-a', output_artifact_ref=OUT2)
    assert first == second
    json.dumps(first.to_payload())
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.attempt.error = None


def test_unredacted_stored_values_never_reach_a_trace():
    raw_spec = json.dumps({
        'kind': 'render',
        'redacted_argv': [
            'C:/tools/ffmpeg.exe', '-i', f'C:/staging/{CANARY}/a.mp4', f'token={CANARY}', f'/home/user/{CANARY}/out.mp4',
        ],
        'spec_fingerprint': 'f' * 64,
    })
    dirty = dataclasses.replace(
        attempt_chain('attempt-2')[2],
        command_spec=raw_spec,
        error=f'boom password={CANARY} at C:/Users/x/y.log',
        warnings=(f'Authorization: Bearer {CANARY}', f'see /home/user/{CANARY}/out.log'),
    )
    s = store(final=dirty, failing=(GateName.FILE_PLAYABLE,), reason=f'stack trace password={CANARY}')
    output = tq.trace_output(s, links(), workspace_id='ws-a', output_artifact_ref=OUT2)
    attempt = tq.trace_attempt(s, links(), workspace_id='ws-a', render_attempt_id='attempt-2')
    report = tq.trace_quality_report(s, links(), workspace_id='ws-a', quality_report_key='qr-1')
    for trace in (output, attempt, report):
        text = json.dumps(trace.to_payload())
        assert CANARY not in text
        assert 'C:/' not in text and '/home/' not in text
    assert attempt.command_spec.redacted_argv == ('[PATH]', '-i', '[PATH]', '[REDACTED]', '[PATH]')
    assert attempt.error == '[REDACTED]'
    assert attempt.warnings == ('[REDACTED]', 'see [PATH]')
    assert next(item for item in report.gates if item.gate == 'FILE_PLAYABLE').reason == '[REDACTED]'


def test_broken_chains_fail_closed_with_fixed_codes():
    cases = (
        (dict(with_package=False), 'package_missing', 'render_package_id'),
        (dict(package_char='c'), 'package_fingerprint_mismatch', 'package_fingerprint'),
        (dict(with_report=False), 'quality_report_missing', 'quality_report_key'),
    )
    for kw, reason, field in cases:
        with pytest.raises(tq.TraceIncomplete) as info:
            tq.trace_output(store(**kw), links(), workspace_id='ws-a', output_artifact_ref=OUT2)
        assert (info.value.reason, info.value.field) == (reason, field)
    broken = dataclasses.replace(attempt_chain('attempt-2')[2], command_spec='not json')
    with pytest.raises(tq.TraceIncomplete) as info:
        tq.trace_attempt(store(final=broken), links(), workspace_id='ws-a', render_attempt_id='attempt-2')
    assert info.value.reason == 'command_spec_invalid'


def test_invalid_query_arguments_are_rejected():
    s = store()
    with pytest.raises(ValueError):
        tq.trace_attempt(s, links(), workspace_id=' ', render_attempt_id='attempt-2')
    with pytest.raises(ValueError):
        tq.trace_attempt(s, links(), workspace_id='ws-a', render_attempt_id='attempt-2', revision=0)
    with pytest.raises(TypeError):
        tq.trace_attempt(s, None, workspace_id='ws-a', render_attempt_id='attempt-2')
    with pytest.raises(TypeError):
        tq.trace_attempt(s, ['not-a-link'], workspace_id='ws-a', render_attempt_id='attempt-2')
    with pytest.raises(ValueError):
        tq.TraceLink(workspace_id='ws-a', render_package_id='pkg-1', render_attempt_id='attempt-2', upload_verified=1)


def test_source_has_no_write_render_or_probe_capability():
    banned_attrs = {
        'append', 'append_event', 'commit', 'rollback', 'write', 'render', 'probe', 'inspect', 'run', 'execute',
        'start', 'submit', 'unlink', 'remove', 'rename',
    }
    banned_roots = (
        'render.worker', 'render.adapters', 'render.application', 'render.ports.output_probe', 'render.ports.output_inspector',
        'render.ports.inputs', 'os', 'subprocess', 'shutil', 'socket', 'time', 'random', 'uuid', 'creative', 'voice', 'catalog',
        'controlplane.infrastructure', 'controlplane.api', 'controlplane.ui',
    )
    for node in ast.walk(ast.parse(SOURCE.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in banned_attrs
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module or '']
        else:
            continue
        for name in names:
            assert not name.startswith('src.')
            assert not any(name == root or name.startswith(root + '.') for root in banned_roots)
