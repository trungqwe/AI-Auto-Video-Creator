"""E-18: worker activity handler of E for workflow G (CT-WF-003, CT-WF-006).

coveredIds: CT-WF-003, CT-WF-006, TST-E2E-014 (phía E)
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import datetime
import io
import json
import pathlib
import wave

import pytest
from controlplane.domain.orchestration import ExecutionGrant
from voice.adapters.fake_aligner import FakeAligner
from voice.adapters.fake_tts import FakeFailure, FakeTtsEngine, FakeVoiceRoute
from voice.adapters.memory import InMemoryUnitOfWork
from voice.application.media_pipeline import MediaPipeline, VerifiedOutput
from voice.application.voice_pipeline import CreateVoiceTrackCommand, CreateWordTimingCommand, VoicePipeline
from voice.domain.normalize import NormalizeSpec, NormalizeStep, plan_rendition
from voice.domain.processing import ArtifactRef, Disposition
from voice.domain.timing_coverage import TokenizationPolicy
from voice.ports.media_tool import ToolOutcome
from voice.ports.repositories import EventContext
from voice.ports.script_text import ScriptText
from voice.worker import activity_handler as ah
from voice.worker.activity_handler import (
    ActivityRequestError,
    VoiceActivityDeps,
    handle_activity,
    validate_activity_request,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'voice' / 'worker' / 'activity_handler.py'
VOICE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
ROUTE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'j-provider-route' / 'payloads.json'
BINDING_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-activity-execution' / 'payloads.json'
BINDING = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'g-activity-execution.json'
WORKSPACE = 'ws-1'
TRACK = 'track-1'
TEXT = 'Breaking news today'
NOW = datetime.datetime(2026, 10, 19, 8, 0, 0, tzinfo=datetime.timezone.utc)
SECRET = 'hunter2-SECRET'
OTHER_SHA = 'fedcba9876543210' * 4
SHA_A, SHA_B = 'a' * 64, 'b' * 64
IMAGE_REF = ArtifactRef('img-1', SHA_A)
GRANT = ExecutionGrant(WORKSPACE, 'op-1', 'job-1', 'stage-1', 3, 1)
OLD_GENERATION = dataclasses.replace(GRANT, execution_generation=2)
OLD_EPOCH = dataclasses.replace(GRANT, recovery_epoch=0)
NEW_GENERATION = dataclasses.replace(GRANT, execution_generation=4)


IMAGE_RAW = {
    'format': {'format_name': 'png_pipe'},
    'streams': [{'codec_type': 'image', 'codec_name': 'png', 'width': 640, 'height': 480}],
}
RESIZE_SPEC = NormalizeSpec(
    operations=(NormalizeStep('resize', {'width': 1080, 'height': 1920}),), tool_version='ffmpeg-fake-1', spec_revision='spec-1'
)
# test-only policy inputs (GIẢ ĐỊNH, IMPL-PLAN-E §7): src/ has no default for any of them
ATTEMPTS = {'max_attempts': 2, 'max_attempts_per_provider': 2}
DURATION_RANGE = (500, 70000)
TOKENIZATION = TokenizationPolicy(
    revision='tok-test-v1',
    unicode_form='NFC',
    casefold=True,
    edge_strip_categories=('P',),
    gap_tolerance_ms=500,
    min_confidence=0.5,
)


def voice_request(**extra) -> dict:
    data = json.loads(VOICE_FIXTURE.read_text(encoding='utf-8'))
    return {**data['entities']['VoiceTrackRequest']['valid'][0], **extra}


def route_request() -> dict:
    data = json.loads(ROUTE_FIXTURE.read_text(encoding='utf-8'))
    base = copy.deepcopy(data['entities']['ProviderRouteRequest']['valid'][0])
    return {**base, 'ai_role': 'voice_synthesis', 'allowed_fallbacks': []}


def context_of(name: str, grant: ExecutionGrant) -> EventContext:
    return EventContext(
        workspace_id=grant.workspace_id,
        correlation_id='corr-1',
        actor='worker-e',
        occurred_at='2026-10-19T08:00:00+00:00',
        recovery_epoch=str(grant.recovery_epoch),
        event_id=f'evt-{name}',
        message_id=f'msg-{name}',
    )


def wav_duration_ms(audio: bytes) -> int:
    with wave.open(io.BytesIO(audio), 'rb') as wav:
        return wav.getnframes() * 1000 // wav.getframerate()


class ScriptPort:
    def __init__(self, text: ScriptText) -> None:
        self._text = text

    def get_text(self, script_version_id: str) -> ScriptText:
        assert script_version_id == self._text.script_version_id
        return self._text


class FakeGrants:
    """Test-only GrantCurrencyPort: a grant is current only when it equals one of the given grants."""

    def __init__(self, *current: ExecutionGrant) -> None:
        self.current = set(current)
        self.calls = 0

    def is_grant_current(self, grant: ExecutionGrant) -> bool:
        self.calls += 1
        return grant in self.current


class FakeProbe:
    def __init__(self) -> None:
        self.calls: list[ArtifactRef] = []

    def probe(self, artifact_ref: ArtifactRef) -> dict:
        self.calls.append(artifact_ref)
        return IMAGE_RAW


class FakeTool:
    def __init__(self, outcome: ToolOutcome | None = None, raises: Exception | None = None) -> None:
        self.outcome = outcome
        self.raises = raises
        self.calls: list = []

    def run(self, plan):
        self.calls.append(plan)
        if self.raises is not None:
            raise self.raises
        if self.outcome is not None:
            return self.outcome
        return ToolOutcome(Disposition.SUCCEEDED, output_ref=plan.output_ref, output_sha256=SHA_B)


class FakeInputs:
    """Test-only ActivityInputPort: maps every activity to the E command arguments built from fixed fixtures."""

    def __init__(self, *, voice_operation_key: str | None = None) -> None:
        self.voice_operation_key = voice_operation_key
        self.voice_extra: dict = {}
        self.raises: Exception | None = None
        self.calls: list[str] = []

    def resolve(self, activity_name, request, grant):
        self.calls.append(activity_name)
        if self.raises is not None:
            raise self.raises
        key = request['operation_key']
        context = context_of(key, grant)
        voice = voice_request(operation_key=self.voice_operation_key or key, **self.voice_extra)
        if activity_name == 'CreateVoiceTrack':
            return {'command': CreateVoiceTrackCommand(
                track_key=TRACK,
                voice_request=voice,
                route_request=route_request(),
                attempt_policy=ATTEMPTS,
                duration_policy=DURATION_RANGE,
                context=context,
            )}
        if activity_name == 'CreateWordTiming':
            return {'command': CreateWordTimingCommand(
                track_key=TRACK, voice_request=voice, tokenization_policy=TOKENIZATION, context=context
            )}
        if activity_name == 'ProbeMedia':
            return {'artifact_ref': IMAGE_REF, 'observed_size': 2048}
        if activity_name == 'NormalizeMedia':
            output = plan_rendition(IMAGE_REF, RESIZE_SPEC, 'image').output_ref
            return {
                'context': context,
                'input_ref': IMAGE_REF,
                'spec': RESIZE_SPEC,
                'media_kind': 'image',
                'verified_outputs': {output: VerifiedOutput(SHA_B, 2048)},
            }
        raise KeyError(activity_name)


class Rig:
    def __init__(self, *, grants=(GRANT,), inputs=None, tts_scripts=None, tool=None) -> None:
        request = voice_request()
        script = ScriptText(
            script_version_id=request['script_version_id'], text=TEXT, script_fingerprint=request['script_fingerprint']
        )
        self.uow = InMemoryUnitOfWork()
        self.route = FakeVoiceRoute()
        self.engine = FakeTtsEngine(self.route, scripts=tts_scripts)
        self.aligner = FakeAligner()
        self.tool = FakeTool() if tool is None else tool
        self.grants = FakeGrants(*grants)
        self.inputs = FakeInputs() if inputs is None else inputs
        voice = VoicePipeline(
            uow=self.uow,
            script_port=ScriptPort(script),
            route_port=self.route,
            tts_engine=self.engine,
            aligner=self.aligner,
            measure_duration_ms=wav_duration_ms,
        )
        media = MediaPipeline(self.uow, probe=FakeProbe(), tool=self.tool)
        self.deps = VoiceActivityDeps(
            voice=voice, media=media, grants=self.grants, inputs=self.inputs, clock=lambda: NOW
        )

    def events(self) -> list[str]:
        return [record.event_type for record in self.uow.outbox.records()]

    def stored(self, kind: str, key: str = TRACK):
        item = self.uow.outputs.latest(kind, key)
        return None if item is None else item.record

    def untouched(self) -> bool:
        counters = (self.engine.synthesize_calls, self.route.resolve_calls, self.aligner.align_calls, len(self.tool.calls))
        return counters == (0, 0, 0, 0) and self.stored('voice') is None and self.events() == []


def request_of(activity: str = 'CreateVoiceTrack', operation_key: str = 'op-key-1', **extra) -> dict:
    request = {
        'workflow_id': 'wf-1',
        'workflow_run_id': 'wfr-1',
        'stage_run_id': 'stage-1',
        'activity_name': activity,
        'activity_version': '1',
        'input_refs': [{'ref_type': 'script_version', 'ref_id': voice_request()['script_version_id']}],
        'operation_key': operation_key,
        'capability_requirements': {'provider': 'tts'},
        'retry_policy_ref': 'retry-r1',
    }
    return {**request, **extra}


def handle(rig: Rig, request: dict | None = None, grant: ExecutionGrant = GRANT):
    return handle_activity(request if request is not None else request_of(), grant, rig.deps)


def test_create_voice_track_activity_returns_a_succeeded_activity_result():
    rig = Rig()
    result = handle(rig)
    voice = rig.stored('voice')
    assert result['disposition'] == 'succeeded'
    assert (result['stage_run_id'], result['grant_id']) == ('stage-1', 'op-1')
    assert (result['execution_generation'], result['recovery_epoch']) == (3, '1')
    assert result['completed_at'] == '2026-10-19T08:00:00Z'
    assert result['output_refs'] == [{'ref_type': 'voice_artifact', 'ref_id': voice.voice_artifact_ref}]
    assert result['metrics'] == {'actual_duration_ms': 1000, 'replayed': False}
    assert result['warnings'] == []
    assert result['operation_receipt_ref'] == voice.receipt_ref
    assert 'problem' not in result
    assert rig.engine.synthesize_calls == 1
    assert rig.events() == ['VoiceReady']
    assert rig.inputs.calls == ['CreateVoiceTrack']


def test_create_word_timing_activity_runs_only_when_its_own_request_arrives():
    rig = Rig()
    handle(rig)
    assert rig.stored('word_timing') is None and rig.aligner.align_calls == 0
    result = handle(rig, request_of('CreateWordTiming', 'op-key-2'))
    timing = rig.stored('word_timing')
    assert result['disposition'] == 'succeeded'
    assert result['output_refs'] == [
        {'ref_type': 'word_timing_artifact', 'ref_id': timing.timing_artifact_ref},
        {'ref_type': 'timing_validation_report', 'ref_id': timing.validation_report_ref},
    ]
    assert result['metrics'] == {'word_count': 3, 'replayed': False}
    assert (rig.engine.synthesize_calls, rig.aligner.align_calls) == (1, 1)
    assert rig.events() == ['VoiceReady', 'WordTimingReady']


def test_a_finished_stage_never_starts_the_next_stage():
    rig = Rig()
    result = handle(rig)
    assert result['disposition'] == 'succeeded'
    assert rig.inputs.calls == ['CreateVoiceTrack']
    assert (rig.aligner.align_calls, len(rig.tool.calls)) == (0, 0)
    assert rig.stored('word_timing') is None
    assert [ref['ref_type'] for ref in result['output_refs']] == ['voice_artifact']


def test_media_activity_runs_only_its_own_command():
    rig = Rig()
    result = handle(rig, request_of('NormalizeMedia', 'op-key-3'))
    assert result['disposition'] == 'succeeded'
    assert (rig.engine.synthesize_calls, rig.route.resolve_calls, rig.aligner.align_calls) == (0, 0, 0)
    assert len(rig.tool.calls) == 1


def test_desktop_capability_is_never_waited_for_by_e():
    rig = Rig()
    result = handle(rig, request_of(capability_requirements={'desktop': 'required'}))
    assert result['disposition'] == 'succeeded'
    assert 'problem' not in result


@pytest.mark.parametrize('stale', [OLD_GENERATION, OLD_EPOCH], ids=['old_generation', 'old_recovery_epoch'])
def test_stale_grant_is_rejected_before_any_input_lookup_or_commit(stale):
    rig = Rig()
    result = handle(rig, grant=stale)
    assert result['disposition'] == 'stale'
    assert result['problem']['code'] == 'STALE_GRANT'
    assert result['problem']['retryable'] is False
    assert result['output_refs'] == []
    assert (result['execution_generation'], result['recovery_epoch']) == (
        stale.execution_generation,
        str(stale.recovery_epoch),
    )
    assert rig.inputs.calls == [] and rig.untouched()
    assert rig.deps.results.get(WORKSPACE, 'op-key-1') is None


def test_stale_grant_cannot_write_a_new_voice_after_a_current_one_committed():
    rig = Rig()
    assert handle(rig)['disposition'] == 'succeeded'
    before = rig.stored('voice')
    result = handle(rig, request_of(operation_key='op-key-2'), OLD_GENERATION)
    assert result['disposition'] == 'stale'
    assert len(rig.uow.outputs.revisions('voice', TRACK)) == 1 and rig.stored('voice') is before
    assert rig.engine.synthesize_calls == 1 and rig.events() == ['VoiceReady']


def test_stale_grant_does_not_receive_the_stored_result_of_a_newer_generation():
    rig = Rig()
    handle(rig)
    result = handle(rig, grant=OLD_GENERATION)
    assert result['disposition'] == 'stale' and result['output_refs'] == []


def test_same_operation_key_returns_the_stored_result_without_running_again():
    rig = Rig()
    first = handle(rig)
    second = handle(rig)
    assert second == first
    assert rig.engine.synthesize_calls == 1 and rig.events() == ['VoiceReady']
    assert rig.inputs.calls == ['CreateVoiceTrack']
    second['metrics']['replayed'] = True
    assert handle(rig) == first


def test_same_operation_key_under_a_newer_current_generation_keeps_outputs_and_takes_the_new_identity():
    rig = Rig(grants=(GRANT, NEW_GENERATION))
    first = handle(rig)
    second = handle(rig, grant=NEW_GENERATION)
    assert (first['execution_generation'], second['execution_generation']) == (3, 4)
    assert second['disposition'] == 'succeeded' and second['output_refs'] == first['output_refs']
    assert rig.engine.synthesize_calls == 1


def test_same_operation_key_for_a_different_activity_is_a_conflict():
    rig = Rig()
    first = handle(rig)
    conflict = handle(rig, request_of('CreateWordTiming'))
    assert conflict['disposition'] == 'failed'
    assert conflict['problem']['code'] == 'OPERATION_KEY_CONFLICT'
    assert conflict['output_refs'] == [] and rig.aligner.align_calls == 0
    assert handle(rig) == first


def test_unknown_activity_name_returns_a_structured_problem_without_running_anything():
    rig = Rig()
    result = handle(rig, request_of('RenderVideo'))
    assert result['disposition'] == 'failed' and result['output_refs'] == []
    problem = result['problem']
    assert (problem['code'], problem['retryable'], problem['category']) == ('UNKNOWN_ACTIVITY', False, 'validation')
    assert problem['correlation_id'] == 'wfr-1' and problem['instance'] == 'urn:stage-run:stage-1'
    assert rig.inputs.calls == [] and rig.untouched()
    assert rig.deps.results.get(WORKSPACE, 'op-key-1') is None


def test_supported_activity_names_are_the_e16_and_e17_commands():
    assert ah.ACTIVITY_NAMES == (
        'CreateVoiceTrack',
        'CreateWordTiming',
        'ProbeMedia',
        'AssessImageSafety',
        'TransformSensitiveImage',
        'NormalizeMedia',
        'PrepareAudioBed',
    )


def test_operation_key_inside_the_command_must_match_the_request():
    rig = Rig(inputs=FakeInputs(voice_operation_key='op-other'))
    result = handle(rig)
    assert result['disposition'] == 'failed'
    assert (result['problem']['code'], result['problem']['retryable']) == ('OPERATION_KEY_MISMATCH', False)
    assert rig.untouched()


def test_a_command_rejection_is_a_failed_result_with_its_code_and_nothing_committed():
    rig = Rig()
    rig.inputs.voice_extra = {'script_fingerprint': OTHER_SHA}
    result = handle(rig)
    problem = result['problem']
    assert result['disposition'] == 'failed'
    assert (problem['code'], problem['retryable'], problem['category']) == ('script_fingerprint_mismatch', False, 'validation')
    assert rig.untouched()


def test_provider_failure_is_a_failed_result_with_a_code_only_problem():
    leak = FakeFailure('timeout', f'upstream token={SECRET}', True)
    rig = Rig(tts_scripts={'fake-tts-provider': (leak,)})
    result = handle(rig)
    assert result['disposition'] == 'failed'
    assert (result['problem']['code'], result['problem']['retryable']) == ('timeout', True)
    assert result['problem']['category'] == 'dependency'
    assert SECRET not in repr(result)
    assert rig.stored('voice') is None and rig.events() == []
    assert rig.deps.results.get(WORKSPACE, 'op-key-1') is None


def test_unexpected_exceptions_become_redacted_failed_results():
    class LeakyCode(Exception):
        code = f'token={SECRET}'

    for error in (RuntimeError(f'db password={SECRET} lost'), LeakyCode(f'Bearer {SECRET}')):
        rig = Rig()
        rig.inputs.raises = error
        result = handle(rig)
        assert result['disposition'] == 'failed'
        assert (result['problem']['code'], result['problem']['retryable']) == ('ACTIVITY_ABORTED', True)
        assert SECRET not in repr(result)
        assert rig.deps.results.get(WORKSPACE, 'op-key-1') is None
        assert rig.untouched()


def test_probe_media_activity_succeeds_without_output_refs():
    rig = Rig()
    result = handle(rig, request_of('ProbeMedia', 'op-key-4'))
    assert result['disposition'] == 'succeeded' and result['output_refs'] == []
    assert result['operation_receipt_ref'] == 'receipt:op-key-4'
    assert result['metrics'] == {'output_count': 0, 'replayed': False}


def test_normalize_media_activity_returns_the_new_rendition_and_replays_from_its_result():
    rig = Rig()
    ref = plan_rendition(IMAGE_REF, RESIZE_SPEC, 'image').output_ref
    first = handle(rig, request_of('NormalizeMedia', 'op-key-3'))
    assert first['output_refs'] == [{'ref_type': 'media_artifact', 'ref_id': ref}]
    assert first['metrics'] == {'output_count': 1, 'replayed': False}
    assert handle(rig, request_of('NormalizeMedia', 'op-key-3')) == first
    assert len(rig.tool.calls) == 1 and rig.events() == ['MediaProcessingCompleted']


def test_media_tool_crash_is_a_failed_result_that_stays_terminal_for_its_operation_key():
    rig = Rig(tool=FakeTool(raises=RuntimeError(f'ffmpeg token={SECRET}')))
    first = handle(rig, request_of('NormalizeMedia', 'op-key-3'))
    assert first['disposition'] == 'failed'
    assert (first['problem']['code'], first['problem']['retryable']) == ('RuntimeError', False)
    assert first['operation_receipt_ref'] == 'receipt:op-key-3'
    assert SECRET not in repr(first)
    again = handle(rig, request_of('NormalizeMedia', 'op-key-3'))
    assert again['disposition'] == 'failed'
    assert len(rig.tool.calls) == 1 and rig.deps.results.get(WORKSPACE, 'op-key-3') is None


@pytest.mark.parametrize(
    ('outcome', 'disposition', 'code'),
    [
        (ToolOutcome(Disposition.FAILED, error='ffmpeg exit 1'), 'failed', 'MEDIA_COMMAND_FAILED'),
        (ToolOutcome(Disposition.FAILED, error=f'token={SECRET}'), 'failed', 'MEDIA_COMMAND_FAILED'),
        (ToolOutcome(Disposition.OUTCOME_UNKNOWN), 'outcome_unknown', 'tool_outcome_unknown'),
    ],
    ids=['free_text_error', 'secret_error', 'outcome_unknown'],
)
def test_media_receipt_errors_become_code_tokens(outcome, disposition, code):
    rig = Rig(tool=FakeTool(outcome=outcome))
    result = handle(rig, request_of('NormalizeMedia', 'op-key-3'))
    assert result['disposition'] == disposition and result['output_refs'] == []
    assert result['problem']['code'] == code and result['problem']['retryable'] is False
    assert SECRET not in repr(result) and 'ffmpeg exit' not in repr(result)


def test_a_direct_retry_after_outcome_unknown_is_reported_as_outcome_unknown():
    rig = Rig(tool=FakeTool(outcome=ToolOutcome(Disposition.OUTCOME_UNKNOWN)))
    handle(rig, request_of('NormalizeMedia', 'op-key-3'))
    retry = handle(rig, request_of('NormalizeMedia', 'op-key-5'))
    assert retry['disposition'] == 'outcome_unknown'
    assert retry['problem']['code'] == 'OUTCOME_UNKNOWN_RETRY_NOT_ALLOWED'
    assert len(rig.tool.calls) == 1


INVALID_REQUESTS = (
    ('missing_operation_key', lambda r: r.pop('operation_key'), ('missing_required', 'operation_key')),
    ('secret_in_payload', lambda r: r.update(secret_value=SECRET), ('forbidden_field', 'secret_value')),
    ('raw_blob_in_payload', lambda r: r.update(raw_blob='x'), ('forbidden_field', 'raw_blob')),
    ('blank_activity_name', lambda r: r.update(activity_name=' '), ('invalid_value', 'activity_name')),
    ('empty_input_refs', lambda r: r.update(input_refs=[]), ('invalid_value', 'input_refs')),
    ('input_ref_without_id', lambda r: r.update(input_refs=[{'ref_type': 'script_version'}]), ('invalid_value', 'input_refs')),
    ('input_refs_as_string', lambda r: r.update(input_refs='ref-1'), ('wrong_type', 'input_refs')),
    ('other_stage_run', lambda r: r.update(stage_run_id='stage-2'), ('invalid_value', 'execution_grant.stage_run_id')),
)
INVALID_GRANTS = (
    ('not_an_execution_grant', {'workspace_id': WORKSPACE}, ('wrong_type', 'execution_grant')),
    (
        'negative_generation',
        dataclasses.replace(GRANT, execution_generation=-1),
        ('invalid_value', 'execution_grant.execution_generation'),
    ),
    ('blank_workspace', dataclasses.replace(GRANT, workspace_id=' '), ('invalid_value', 'execution_grant.workspace_id')),
)


@pytest.mark.parametrize(
    ('mutate', 'issue'), [case[1:] for case in INVALID_REQUESTS], ids=[case[0] for case in INVALID_REQUESTS]
)
def test_invalid_request_raises_before_any_grant_check_lookup_or_write(mutate, issue):
    rig = Rig()
    request = request_of()
    mutate(request)
    with pytest.raises(ActivityRequestError) as raised:
        handle(rig, request)
    assert raised.value.code == 'VALIDATION_ERROR' and issue in raised.value.issues
    assert SECRET not in repr(raised.value)
    assert (rig.grants.calls, rig.inputs.calls) == (0, []) and rig.untouched()


@pytest.mark.parametrize(
    ('grant', 'issue'), [case[1:] for case in INVALID_GRANTS], ids=[case[0] for case in INVALID_GRANTS]
)
def test_invalid_grant_raises_validation_error_before_any_grant_check(grant, issue):
    rig = Rig()
    with pytest.raises(ActivityRequestError) as raised:
        handle(rig, grant=grant)
    assert raised.value.code == 'VALIDATION_ERROR' and issue in raised.value.issues
    assert (rig.grants.calls, rig.inputs.calls) == (0, []) and rig.untouched()


def test_results_carry_every_required_binding_field_and_a_contract_disposition():
    binding = json.loads(BINDING.read_text(encoding='utf-8'))
    entity = next(item for item in binding['entities'] if item['name'] == 'ActivityResult')
    required = {item['name'] for item in entity['fields'] if item['required']}
    dispositions = next(item for item in entity['fields'] if item['name'] == 'disposition')['enum']
    results = [handle(Rig()), handle(Rig(), grant=OLD_EPOCH), handle(Rig(), request_of('RenderVideo'))]
    for result in results:
        assert required <= set(result)
        assert result['disposition'] in dispositions
        assert type(result['execution_generation']) is int and isinstance(result['recovery_epoch'], str)
        assert isinstance(result['output_refs'], list)


def test_binding_fixture_requests_are_valid_and_invalid_cases_report_their_expected_error():
    entity = json.loads(BINDING_FIXTURE.read_text(encoding='utf-8'))['entities']['ActivityRequest']
    valid = entity['valid'][0]
    grant = dataclasses.replace(GRANT, stage_run_id=valid['stage_run_id'])
    assert validate_activity_request(valid, grant) == []
    assert valid['activity_name'] in ah.ACTIVITY_NAMES
    for case in entity['invalid']:
        expected = (case['expected_error']['code'], case['expected_error']['field'])
        assert expected in validate_activity_request(case['payload'], grant), case['case']


def imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_handler_imports_no_temporalio_ui_api_creative_render_or_catalog_code():
    banned_parts = {'temporalio', 'creative', 'render', 'catalog'}
    banned = sorted(
        name
        for name in imported_modules(MODULE_PATH)
        if banned_parts & set(name.split('.')) or name.startswith(('controlplane.ui', 'controlplane.api'))
    )
    assert banned == []


def test_handler_imports_only_stdlib_controlplane_domain_and_voice_layers():
    stdlib = {'__future__', 'copy', 'datetime', 're', 'collections.abc', 'dataclasses', 'types', 'typing'}
    allowed = ('controlplane.domain', 'voice.application', 'voice.domain', 'voice.ports')
    unexpected = sorted(
        name for name in imported_modules(MODULE_PATH) if name not in stdlib and not name.startswith(allowed)
    )
    assert unexpected == []


def test_handler_never_waits_sleeps_or_opens_io():
    waiting = {'time', 'asyncio', 'threading', 'sched', 'subprocess', 'socket', 'os'}
    assert sorted(name for name in imported_modules(MODULE_PATH) if name.split('.')[0] in waiting) == []


def test_handler_registers_no_workflow_or_activity_through_decorators():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    assert [node.name for node in ast.walk(tree) if isinstance(node, functions) and node.decorator_list] == []


def test_handler_uses_the_controlplane_execution_grant_and_defines_no_grant_class():
    assert ah.ExecutionGrant is ExecutionGrant
    defined = [name for name, value in vars(ah).items() if isinstance(value, type) and value.__module__ == ah.__name__]
    assert [name for name in defined if name.endswith('Grant')] == []


def test_module_docstring_lists_the_covered_ids():
    docstring = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: CT-WF-003, CT-WF-006, TST-E2E-014' in docstring
