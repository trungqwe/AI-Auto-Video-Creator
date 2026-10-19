"""F-17: integration ResolveRenderPackage và ValidateRenderPackage trong tiến trình (CT-RND-002, CT-RND-003).

coveredIds: TST-CTR-INV-001, TST-INT-INV-008, TST-MEDIA-INV-007, CT-RND-002, CT-RND-003, TST-E2E-001 (đoạn resolve và validate)
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
import pathlib
from types import SimpleNamespace

import pytest

from controlplane.domain.common.contracts import ProblemDetail
from controlplane.domain.orchestration import ExecutionGrant
from controlplane.domain.statemachine import ArtifactLocationState, OperationState
from render.adapters.memory import TransactionNotActiveError
from render.application.package_pipeline import (
    COMMAND_RESOLVE, COMMAND_VALIDATE, CommandContext, CommandReceipt, CommandTrace, IdempotencyConflict,
    InMemoryPackageUnitOfWork, PackagePipeline, RenderPackageNotFound, ResolveRenderPackageCommand, StaleGrant,
    ValidateRenderPackageCommand, ValidationReportMissing,
)
from render.domain.package_fingerprint import HASHED_FIELDS
from render.domain.preconditions_artifacts import (
    IssuedOutputPath, LanguageEvidencePolicy, LanguageEvidenceView, ToolCapability, VerifiedArtifact,
)
from render.domain.preconditions_media import VoiceTrackInfo, WordTimingInfo
from render.domain.resolve_package import ResolveError
from render.domain.validate_package import PackageNotRenderable, ValidationContext
from render.ports.inputs import ResolveInputs, ResolvedAsset
from render.ports.repositories import KIND_PACKAGE

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'
MODULE_PATH = ROOT / 'src' / 'render' / 'application' / 'package_pipeline.py'
WORKSPACE = 'ws-1'
VOICE_ID = '00000000-0000-4000-8000-000000000034'
TIMING_ID = '00000000-0000-4000-8000-000000000036'
IMAGE_ID = '00000000-0000-4000-8000-000000000053'
HOOK_IDS = ('00000000-0000-4000-8000-000000000054', '00000000-0000-4000-8000-000000000055', '00000000-0000-4000-8000-000000000056')
OUTPUT_REF = '00000000-0000-4000-8000-000000000057'
EVIDENCE_REF = 'lang-val-0001'
VOICE_SHA, TIMING_SHA, IMAGE_SHA = 'a' * 64, 'b' * 64, 'c' * 64
SCRIPT_FP, VOICE_HASH, SUBTITLE_HASH = 'd' * 64, 'e' * 64, 'f' * 64
STAGING_ROOT = 'D:/render-staging'
OUTPUT_PATH = 'D:/render-staging/out/video.mp4'


def _fixture() -> dict:
    return copy.deepcopy(json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities']['RenderPackage']['valid'][0])


def _asset(version: str, sha: str, size: int, media: str, role: str) -> ResolvedAsset:
    return ResolvedAsset(artifact_version_id=version, sha256=sha, size_bytes=size, media_type=media, role=role)


def _inputs(*, hook_drop=(), placement=None, **changes):
    valid = _fixture()
    for name in hook_drop:
        valid['hook_placement'].pop(name)
    valid['hook_placement'].update(placement or {})
    values = {name: valid[name] for name in HASHED_FIELDS}
    values.update(
        language_validation_refs=tuple(valid['language_validation_refs']),
        input_artifacts=(
            _asset(VOICE_ID, VOICE_SHA, 100, 'audio/wav', 'voice'),
            _asset(TIMING_ID, TIMING_SHA, 50, 'application/json', 'timing'),
            _asset(IMAGE_ID, IMAGE_SHA, 2048, 'image/png', 'visual'),
        ),
        allowed_fallbacks=tuple(valid['allowed_fallbacks']),
        materialization_manifest=(),
    )
    values.update(changes)
    return ResolveInputs(**values)


def _voice() -> VoiceTrackInfo:
    return VoiceTrackInfo(voice_artifact_ref=VOICE_ID, script_version_id=_fixture()['script_version_ref'], script_fingerprint=SCRIPT_FP, voice_hash=VOICE_HASH)


def _timing(**changes) -> WordTimingInfo:
    base = WordTimingInfo(timing_artifact_ref=TIMING_ID, script_version_id=_fixture()['script_version_ref'], script_fingerprint=SCRIPT_FP, voice_hash=VOICE_HASH)
    return dataclasses.replace(base, **changes)


def _evidence(**changes) -> LanguageEvidenceView:
    base = LanguageEvidenceView(evidence_ref=EVIDENCE_REF, script_fingerprint=SCRIPT_FP, voice_hash=VOICE_HASH, subtitle_text_hash=SUBTITLE_HASH, output_metadata_revision='out-meta-v1', voice_locale_reported='en-US')
    return dataclasses.replace(base, **changes)


def _policy(**changes) -> LanguageEvidencePolicy:
    base = LanguageEvidencePolicy(required_language='en', script_fingerprint=SCRIPT_FP, voice_hash=VOICE_HASH, subtitle_text_hash=SUBTITLE_HASH)
    return dataclasses.replace(base, **changes)


def _verified(overrides=None) -> dict:
    entries = {
        VOICE_ID: VerifiedArtifact(VOICE_SHA, 100, ArtifactLocationState.VERIFIED),
        TIMING_ID: VerifiedArtifact(TIMING_SHA, 50, ArtifactLocationState.VERIFIED),
        IMAGE_ID: VerifiedArtifact(IMAGE_SHA, 2048, ArtifactLocationState.VERIFIED),
    }
    entries.update(overrides or {})
    return entries


def _validation_context(**changes) -> ValidationContext:
    values = {
        'voice': _voice(), 'word_timing': _timing(), 'verified': _verified(),
        'issued_paths': {OUTPUT_REF: IssuedOutputPath(STAGING_ROOT, OUTPUT_PATH)},
        'language_evidence': {EVIDENCE_REF: _evidence()},
        'language_policy': _policy(),
        'preset': SimpleNamespace(compatibility_requirements={'required_filters': ['subtitles'], 'required_encoders': ['libx264']}),
        'capability': ToolCapability(filters=frozenset({'subtitles', 'scale'}), encoders=frozenset({'libx264'})),
    }
    values.update(changes)
    return ValidationContext(**values)


class FakePlan:
    def __init__(self, refs) -> None:
        self.refs = tuple(refs)
        self.calls: list[str] = []

    def asset_refs(self, production_plan_ref):
        self.calls.append(production_plan_ref)
        return self.refs


class FakeGrants:
    def __init__(self, *current) -> None:
        self.current = set(current)

    def is_grant_current(self, grant) -> bool:
        return grant in self.current


class FakeRenderer:
    def __init__(self) -> None:
        self.calls = 0

    def render(self, record):
        self.calls += 1
        return 'rendered'


class SpyUnitOfWork(InMemoryPackageUnitOfWork):
    def __init__(self) -> None:
        super().__init__()
        self.begins = 0
        self.commits = 0

    def begin(self) -> None:
        self.begins += 1
        super().begin()

    def commit(self) -> None:
        self.commits += 1
        super().commit()


def _grant(**changes) -> ExecutionGrant:
    values = {'workspace_id': WORKSPACE, 'operation_id': 'op-grant-1', 'job_id': 'job-1', 'stage_run_id': 'stage-1', 'execution_generation': 2, 'recovery_epoch': 1}
    return ExecutionGrant(**{**values, **changes})


def _context() -> CommandContext:
    return CommandContext(workspace_id=WORKSPACE, correlation_id='corr-1', actor='tester', occurred_at='2026-01-01T00:00:00+00:00')


class Rig:
    def __init__(self, uow=None) -> None:
        self.uow = InMemoryPackageUnitOfWork() if uow is None else uow
        self.plan = FakePlan((IMAGE_ID, *HOOK_IDS))
        self.grant = _grant()
        self.grants = FakeGrants(self.grant)
        self.pipeline = PackagePipeline(uow=self.uow, plan_assets=self.plan, grants=self.grants)

    def resolve(self, key='op-resolve-1', inputs=None):
        return self.pipeline.resolve_render_package(ResolveRenderPackageCommand(
            operation_key=key, grant=self.grant, inputs=_inputs() if inputs is None else inputs, context=_context(),
        ))

    def validate(self, package_id, key='op-validate-1', context=None):
        return self.pipeline.validate_render_package(ValidateRenderPackageCommand(
            operation_key=key, grant=self.grant, render_package_id=package_id, validation_context=context, context=_context(),
        ))


def _snapshot(uow) -> tuple:
    return tuple(dict(table._rows) for table in uow._tables)


def _render_if_valid(pipeline, package_id, renderer):
    return renderer.render(pipeline.require_renderable(package_id))


def test_resolve_stores_one_package_with_succeeded_receipt_and_trace():
    rig = Rig()
    outcome = rig.resolve()
    package, receipt = outcome.package, outcome.receipt
    assert outcome.replayed is False and isinstance(receipt, CommandReceipt)
    assert [item.record for item in rig.uow.renders.revisions(KIND_PACKAGE, package.render_package_id)] == [package]
    assert receipt.state is OperationState.SUCCEEDED and receipt.revision == 2
    assert (receipt.command, receipt.operation_key) == (COMMAND_RESOLVE, 'op-resolve-1')
    assert (receipt.render_package_id, receipt.package_fingerprint) == (package.render_package_id, package.package_fingerprint)
    assert rig.uow.receipts.get(WORKSPACE, COMMAND_RESOLVE, 'op-resolve-1') == receipt
    (trace,) = rig.uow.traces.records()
    assert isinstance(trace, CommandTrace) and trace.sequence == 1 and trace.receipt_ref == receipt.receipt_ref
    assert (trace.command, trace.outcome, trace.subject_ref) == (COMMAND_RESOLVE, 'package_resolved', package.render_package_id)
    assert (trace.grant_id, trace.execution_generation) == ('op-grant-1', 2)
    assert rig.plan.calls == [package.production_plan_ref] and rig.uow.outbox.records() == () and rig.uow.active is False


@pytest.mark.parametrize('changes, code', [
    ({'output_path_ref': None}, 'missing_required'),
    ({'input_artifacts': (_asset('00000000-0000-4000-8000-000000000099', IMAGE_SHA, 5, 'image/png', 'visual'),)}, 'asset_outside_plan_or_fallback'),
])
def test_resolve_error_raises_and_writes_nothing(changes, code):
    rig = Rig()
    before = _snapshot(rig.uow)
    with pytest.raises(ResolveError) as caught:
        rig.resolve(inputs=_inputs(**changes))
    assert caught.value.code == code
    assert _snapshot(rig.uow) == before and rig.uow.active is False


def test_same_key_and_payload_replays_the_first_receipt_without_a_second_package():
    rig = Rig()
    first = rig.resolve()
    second = rig.resolve()
    assert second.replayed is True and second.receipt == first.receipt and second.package == first.package
    assert len(rig.uow.renders.revisions(KIND_PACKAGE, first.package.render_package_id)) == 1
    assert len(rig.uow.receipts.records()) == 1 and len(rig.uow.traces.records()) == 1
    assert rig.plan.calls == [first.package.production_plan_ref]


def test_same_key_with_another_payload_is_idempotency_conflict_problem():
    rig = Rig()
    rig.resolve()
    before = _snapshot(rig.uow)
    with pytest.raises(IdempotencyConflict) as caught:
        rig.resolve(inputs=_inputs(output_profile_revision='out-prof-v2'))
    problem = caught.value.problem
    assert isinstance(problem, ProblemDetail) and caught.value.code == 'IDEMPOTENCY_CONFLICT'
    assert (problem.code, problem.category, problem.retryable, problem.status) == ('IDEMPOTENCY_CONFLICT', 'conflict', False, 409)
    assert problem.correlation_id == 'corr-1'
    assert _snapshot(rig.uow) == before and len(rig.plan.calls) == 1


def test_new_key_with_same_inputs_reuses_the_package():
    rig = Rig()
    first = rig.resolve('op-a')
    second = rig.resolve('op-b')
    assert second.replayed is False and second.package == first.package
    assert second.receipt.receipt_ref != first.receipt.receipt_ref
    assert len(rig.uow.renders.revisions(KIND_PACKAGE, first.package.render_package_id)) == 1
    assert len(rig.uow.receipts.records()) == 2 and len(rig.uow.traces.records()) == 2


@pytest.mark.parametrize('case', ['old_generation', 'old_recovery_epoch', 'expired_or_revoked', 'other_workspace', 'not_a_grant'])
def test_refused_grant_blocks_both_commands_before_any_read_or_write(case):
    rig = Rig()
    package = rig.resolve().package
    before, plan_calls = _snapshot(rig.uow), len(rig.plan.calls)
    grant = {
        'old_generation': _grant(execution_generation=1),
        'old_recovery_epoch': _grant(recovery_epoch=0),
        'expired_or_revoked': rig.grant,
        'other_workspace': _grant(workspace_id='ws-other'),
        'not_a_grant': None,
    }[case]
    if case == 'expired_or_revoked':
        rig.grants.current.clear()
    if case == 'other_workspace':
        rig.grants.current.add(grant)
    resolve_command = ResolveRenderPackageCommand(operation_key='op-new-resolve', grant=grant, inputs=_inputs(output_profile_revision='out-prof-v2'), context=_context())
    validate_command = ValidateRenderPackageCommand(operation_key='op-new-validate', grant=grant, render_package_id=package.render_package_id, validation_context=_validation_context(), context=_context())
    for call, command in ((rig.pipeline.resolve_render_package, resolve_command), (rig.pipeline.validate_render_package, validate_command)):
        with pytest.raises(StaleGrant) as caught:
            call(command)
        assert caught.value.code == 'STALE_GRANT' and caught.value.problem.code == 'STALE_GRANT'
        assert (caught.value.problem.category, caught.value.problem.retryable, caught.value.problem.status) == ('conflict', False, 409)
    assert _snapshot(rig.uow) == before and len(rig.plan.calls) == plan_calls
    assert rig.uow.reports.latest(package.package_fingerprint) is None


def test_refused_grant_does_not_replay_a_stored_receipt():
    rig = Rig()
    rig.resolve()
    rig.grants.current.clear()
    with pytest.raises(StaleGrant):
        rig.resolve()


def test_each_command_is_one_unit_of_work():
    uow = SpyUnitOfWork()
    rig = Rig(uow)
    package = rig.resolve().package
    assert (uow.begins, uow.commits) == (1, 1)
    rig.validate(package.render_package_id, context=_validation_context())
    assert (uow.begins, uow.commits) == (2, 2)
    rig.resolve()
    rig.validate(package.render_package_id, context=_validation_context())
    assert uow.commits == 2 and uow.active is False


def test_failure_after_the_record_write_rolls_back_record_receipt_and_trace():
    def boom(trace):
        raise RuntimeError('trace store down')

    rig = Rig()
    rig.uow.traces.append = boom
    with pytest.raises(RuntimeError):
        rig.resolve()
    assert _snapshot(rig.uow) == tuple({} for _ in range(5)) and rig.uow.active is False
    other = Rig()
    package = other.resolve().package
    other.uow.traces.append = boom
    before = _snapshot(other.uow)
    with pytest.raises(RuntimeError):
        other.validate(package.render_package_id, context=_validation_context())
    assert _snapshot(other.uow) == before and other.uow.active is False
    assert other.uow.reports.latest(package.package_fingerprint) is None
    assert other.uow.receipts.get(WORKSPACE, COMMAND_VALIDATE, 'op-validate-1') is None


def test_tables_refuse_writes_outside_a_unit_of_work():
    rig = Rig()
    package = rig.resolve().package
    outcome = rig.validate(package.render_package_id, context=_validation_context())
    uow, before = rig.uow, _snapshot(rig.uow)
    writes = (
        lambda: uow.renders.append(KIND_PACKAGE, package.render_package_id, 2, package),
        lambda: uow.reports.append(outcome.report),
        lambda: uow.receipts.add(outcome.receipt),
        lambda: uow.traces.append(uow.traces.records()[0]),
        lambda: uow.outbox.append_event('X', 'aggregate', {}, 'dedup'),
    )
    for write in writes:
        with pytest.raises(TransactionNotActiveError):
            write()
    assert _snapshot(uow) == before


def test_resolve_and_validate_write_only_f_tables_and_no_outbox_event():
    rig = Rig()
    package = rig.resolve().package
    rig.validate(package.render_package_id, context=_validation_context())
    names = {name for name, value in vars(rig.uow).items() if hasattr(value, '_rows')}
    assert names == {'renders', 'outbox', 'reports', 'receipts', 'traces'}
    assert rig.uow.outbox.records() == ()


ALLOWED_IMPORTS = frozenset({
    '__future__', 'collections.abc', 'dataclasses', 'enum', 'typing',
    'controlplane.application.idempotency.canonicalization', 'controlplane.domain.common.contracts',
    'controlplane.domain.interfaces.outbox', 'controlplane.domain.orchestration', 'controlplane.domain.statemachine',
    'render.adapters.memory', 'render.domain.package_contract', 'render.domain.resolve_package',
    'render.domain.validate_package', 'render.ports.inputs', 'render.ports.repositories',
})


def test_module_imports_only_f_and_controlplane_contracts():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module)
    assert names <= ALLOWED_IMPORTS


FAILING_PACKAGES = [
    ('visual_hook_missing', {'hook_drop': ('visual_hook_ref',)}, {}),
    ('audio_hook_missing', {'hook_drop': ('audio_hook_ref',)}, {}),
    ('thumbnail_missing', {'hook_drop': ('thumbnail_ref',)}, {}),
    ('thumbnail_outside_hook_range', {'placement': {'thumbnail_time_range': {'start_ms': 2500, 'end_ms': 3500}}}, {}),
    ('voice_missing', {}, {'voice': None}),
    ('word_timing_missing', {}, {'word_timing': None}),
    ('artifact_not_verified', {}, {'verified': _verified({IMAGE_ID: VerifiedArtifact(IMAGE_SHA, 2048, ArtifactLocationState.AVAILABLE_UNVERIFIED)})}),
    ('output_path_outside_staging_root', {}, {'issued_paths': {OUTPUT_REF: IssuedOutputPath(STAGING_ROOT, 'D:/other/video.mp4')}}),
    ('language_mismatch', {}, {'language_evidence': {EVIDENCE_REF: _evidence(voice_locale_reported='fr-FR')}}),
]


def test_valid_package_passes_is_stored_and_reaches_the_renderer_once():
    rig = Rig()
    package = rig.resolve().package
    outcome = rig.validate(package.render_package_id, context=_validation_context())
    report = outcome.report
    assert report.passed is True and report.findings == () and outcome.replayed is False
    assert rig.uow.reports.revisions(package.package_fingerprint) == (report,)
    assert (outcome.receipt.command, outcome.receipt.state, outcome.receipt.revision) == (COMMAND_VALIDATE, OperationState.SUCCEEDED, 2)
    assert outcome.receipt.report_id == report.report_id
    assert rig.uow.receipts.get(WORKSPACE, COMMAND_VALIDATE, 'op-validate-1') == outcome.receipt
    assert rig.uow.traces.records()[-1].outcome == 'validation_passed'
    renderer = FakeRenderer()
    assert _render_if_valid(rig.pipeline, package.render_package_id, renderer) == 'rendered'
    assert renderer.calls == 1


@pytest.mark.parametrize('code, input_changes, context_changes', FAILING_PACKAGES)
def test_invalid_package_gives_failed_report_and_the_renderer_is_never_called(code, input_changes, context_changes):
    rig = Rig()
    package = rig.resolve(inputs=_inputs(**input_changes)).package
    outcome = rig.validate(package.render_package_id, context=_validation_context(**context_changes))
    assert [item.code for item in outcome.report.findings] == [code] and outcome.report.passed is False
    assert outcome.receipt.state is OperationState.SUCCEEDED and outcome.receipt.report_id == outcome.report.report_id
    assert rig.uow.reports.latest(package.package_fingerprint) == outcome.report
    assert rig.uow.traces.records()[-1].outcome == 'validation_failed'
    renderer = FakeRenderer()
    with pytest.raises(PackageNotRenderable) as caught:
        _render_if_valid(rig.pipeline, package.render_package_id, renderer)
    assert caught.value.report == outcome.report and renderer.calls == 0


MEDIA_BINDING_CHANGES = [
    ('timing_script_fingerprint', {'word_timing': _timing(script_fingerprint='0' * 64)}, ('voice_timing_binding_mismatch', 'script_fingerprint')),
    ('voice_hash', {'voice': dataclasses.replace(_voice(), voice_hash='0' * 64)}, ('voice_timing_binding_mismatch', 'voice_hash')),
    ('policy_script_fingerprint', {'language_policy': _policy(script_fingerprint='9' * 64)}, ('language_evidence_revision_mismatch', 'language_validation_refs[0].script_fingerprint')),
    ('policy_voice_hash', {'language_policy': _policy(voice_hash='9' * 64)}, ('language_evidence_revision_mismatch', 'language_validation_refs[0].voice_hash')),
]


@pytest.mark.parametrize('name, changes, expected', MEDIA_BINDING_CHANGES)
def test_changed_script_fingerprint_or_voice_hash_after_the_package_fails_validation(name, changes, expected):
    rig = Rig()
    package = rig.resolve().package
    first = rig.validate(package.render_package_id, 'op-validate-1', _validation_context())
    assert first.report.passed is True
    second = rig.validate(package.render_package_id, 'op-validate-2', _validation_context(**changes))
    assert [(item.code, item.field) for item in second.report.findings] == [expected] and second.report.passed is False
    assert rig.uow.reports.revisions(package.package_fingerprint) == (first.report, second.report)
    renderer = FakeRenderer()
    with pytest.raises(PackageNotRenderable):
        _render_if_valid(rig.pipeline, package.render_package_id, renderer)
    assert renderer.calls == 0


def test_validate_replays_by_operation_key_and_conflicts_on_another_context():
    rig = Rig()
    package = rig.resolve().package
    first = rig.validate(package.render_package_id, 'op-validate-1', _validation_context())
    again = rig.validate(package.render_package_id, 'op-validate-1', _validation_context())
    assert again.replayed is True and again.receipt == first.receipt and again.report == first.report
    assert len(rig.uow.reports.revisions(package.package_fingerprint)) == 1
    assert len(rig.uow.receipts.records()) == 2 and len(rig.uow.traces.records()) == 2
    before = _snapshot(rig.uow)
    with pytest.raises(IdempotencyConflict) as caught:
        rig.validate(package.render_package_id, 'op-validate-1', _validation_context(voice=None))
    assert caught.value.problem.code == 'IDEMPOTENCY_CONFLICT' and _snapshot(rig.uow) == before


def test_new_key_with_the_same_context_reuses_the_stored_report():
    rig = Rig()
    package = rig.resolve().package
    first = rig.validate(package.render_package_id, 'op-validate-1', _validation_context())
    second = rig.validate(package.render_package_id, 'op-validate-2', _validation_context())
    assert second.replayed is False and second.report == first.report
    assert second.receipt.receipt_ref != first.receipt.receipt_ref
    assert len(rig.uow.reports.revisions(package.package_fingerprint)) == 1 and len(rig.uow.receipts.records()) == 3


def test_operation_key_scope_is_per_command():
    rig = Rig()
    package = rig.resolve('shared-key').package
    outcome = rig.validate(package.render_package_id, 'shared-key', _validation_context())
    assert outcome.replayed is False and len(rig.uow.receipts.records()) == 2


def test_unknown_package_and_missing_report_are_refused_without_writes():
    rig = Rig()
    before = _snapshot(rig.uow)
    with pytest.raises(RenderPackageNotFound):
        rig.validate('missing-package', context=_validation_context())
    with pytest.raises(RenderPackageNotFound):
        rig.pipeline.require_renderable('missing-package')
    assert _snapshot(rig.uow) == before
    package = rig.resolve().package
    with pytest.raises(ValidationReportMissing):
        rig.pipeline.require_renderable(package.render_package_id)


def test_test_module_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert any(line.startswith('coveredIds:') for line in (doc or '').splitlines())
