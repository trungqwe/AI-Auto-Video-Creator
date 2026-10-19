"""E-19: read-only trace projection of voice, word timing and processed media.

coveredIds: acceptance section 10 item 1 of contract 07
"""
from __future__ import annotations

import ast
import dataclasses
import json
import pathlib

import pytest
from voice.domain.language_evidence import LanguageEvidence, LanguageFinding
from voice.domain.processing import ArtifactRef, ProcessingContractError, ProcessingRequest, ProcessingResult
from voice.domain.voice_track import VoiceTrack
from voice.domain.word_timing import validate_word_timing
from voice.projections import trace_queries as tq

ROOT = pathlib.Path(__file__).resolve().parents[3]
VOICE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
SOURCE = ROOT / 'src' / 'voice' / 'projections' / 'trace_queries.py'
CANARY = 'CANARY-9f3a'


def _fixture(entity: str) -> dict:
    data = json.loads(VOICE_FIXTURE.read_text(encoding='utf-8'))
    return data['entities'][entity]['valid'][0]


def _track(char: str = 'a', ref: str = 'voice-1', **over) -> VoiceTrack:
    return VoiceTrack.from_payload({**_fixture('VoiceTrackResult'), 'voice_hash': char * 64, 'voice_artifact_ref': ref, **over})


def _voice_entry(workspace: str = 'ws-a', key: str = 'video-1', revision: int = 1, **over) -> tq.VoiceEntry:
    fields = {'provider_route_ref': 'route-1', 'provider': 'fake-tts', 'model': 'fake-model-1', 'track': _track(), **over}
    return tq.VoiceEntry(workspace_id=workspace, key=key, revision=revision, **fields)


def _timing(ref: str = 'timing-1'):
    return dataclasses.replace(validate_word_timing(_fixture('WordTiming')), timing_artifact_ref=ref)


def _evidence(timing, **over) -> LanguageEvidence:
    fields = dict(
        script_version_id=timing.script_version_id, script_fingerprint=timing.script_fingerprint, voice_hash=timing.voice_hash,
        voice_locale_reported='vi-VN', subtitle_text_hash='b' * 64, timing_artifact_ref=timing.timing_artifact_ref,
        expected_language='vi', evidence_ref='e' * 64,
    )
    return LanguageEvidence(**{**fields, **over})


def _timing_entry(workspace: str = 'ws-a', key: str = 'video-1', revision: int = 1, timing=None, **over) -> tq.TimingEntry:
    timing = timing or _timing()
    fields = {'language_evidence': _evidence(timing), **over}
    return tq.TimingEntry(workspace_id=workspace, key=key, revision=revision, timing=timing, **fields)


def _request(**over) -> ProcessingRequest:
    fields = {
        'processing_operation_id': 'op-1', 'stage_run_id': 'run-1', 'execution_grant': {'grant_id': 'g-1', 'secret': CANARY},
        'input_artifact_refs': [ArtifactRef('in-1', 'a' * 64), ArtifactRef('in-2', 'b' * 64)],
        'operation_spec_revision': 'spec-3', 'expected_output_profile': {'codec': 'h264'},
        'resource_limits': {'cpu': 1}, 'output_storage_intent': 'staging', **over,
    }
    return ProcessingRequest(**fields)


def _result(request: ProcessingRequest, **over) -> ProcessingResult:
    fields = {
        'disposition': 'succeeded', 'output_artifact_refs': [ArtifactRef('out-1', 'c' * 64)],
        'processor_identity': {'tool': 'ffmpeg', 'version': '7.1'}, 'input_fingerprint': request.input_fingerprint,
        'output_hashes': ['c' * 64], 'technical_report': {'stderr': CANARY}, 'warnings': [],
        'operation_receipt_ref': 'rcpt-1', **over,
    }
    return ProcessingResult(**fields)


def _media_entry(workspace: str = 'ws-a', operation: str = 'op-1', revision: int = 1, kind: str = 'rendition', result=None) -> tq.MediaEntry:
    request = _request()
    result = _result(request) if result is None else result
    return tq.MediaEntry(workspace_id=workspace, operation_id=operation, revision=revision, request=request, result=result, output_kind=kind)


class _Tts:
    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, *args, **kwargs):
        self.calls += 1


class _LeakyReader:
    """Returns every entry it holds whatever workspace and key were asked; counts reads and provider calls."""

    def __init__(self, voices=(), timings=(), media=()) -> None:
        self._voices, self._timings, self._media = tuple(voices), tuple(timings), tuple(media)
        self.tts = _Tts()
        self.reads = []

    def voice_entries(self, workspace_id, key):
        self.reads.append(('voice', workspace_id, key))
        return self._voices

    def timing_entries(self, workspace_id, key):
        self.reads.append(('timing', workspace_id, key))
        return self._timings

    def media_entries(self, workspace_id, operation_id):
        self.reads.append(('media', workspace_id, operation_id))
        return self._media


def test_trace_voice_traces_script_route_provider_model_revision_and_receipt():
    trace = tq.trace_voice(_LeakyReader(voices=[_voice_entry()]), 'ws-a', 'video-1')
    fixture = _fixture('VoiceTrackResult')
    assert (trace.workspace_id, trace.key, trace.revision) == ('ws-a', 'video-1', 1)
    assert trace.script_fingerprint == fixture['script_fingerprint']
    assert trace.script_version_id == fixture['script_version_id']
    assert (trace.provider_route_ref, trace.provider, trace.model) == ('route-1', 'fake-tts', 'fake-model-1')
    assert trace.voice_revision == 'tts-v1'
    assert trace.receipt_ref == fixture['receipt_ref']
    assert trace.voice_hash == 'a' * 64 and trace.voice_artifact_ref == 'voice-1'
    assert trace.retention_class == 'per_video'
    assert trace.usage_metrics == (('billed_characters', 120),)


def test_trace_voice_without_route_facts_keeps_none_instead_of_inventing_values():
    entry = _voice_entry(provider_route_ref=None, provider=None, model=None)
    trace = tq.trace_voice(_LeakyReader(voices=[entry]), 'ws-a', 'video-1')
    assert (trace.provider_route_ref, trace.provider, trace.model) == (None, None, None)


def test_trace_voice_lists_revision_history_and_selects_revision():
    entries = [_voice_entry(revision=n, track=_track(char, f'voice-{n}')) for n, char in ((3, 'c'), (1, 'a'), (2, 'b'))]
    reader = _LeakyReader(voices=entries)
    latest = tq.trace_voice(reader, 'ws-a', 'video-1')
    assert latest.revision == 3 and latest.voice_hash == 'c' * 64
    assert [(item.revision, item.ref) for item in latest.history] == [(1, 'voice-1'), (2, 'voice-2'), (3, 'voice-3')]
    first = tq.trace_voice(reader, 'ws-a', 'video-1', revision=1)
    assert first.revision == 1 and first.voice_hash == 'a' * 64 and first.history == latest.history
    assert tq.trace_voice(reader, 'ws-a', 'video-1', revision=9) is None
    assert reader._voices == tuple(entries)


def test_trace_voice_returns_only_entries_of_the_asked_workspace_and_key():
    other_ws = _voice_entry(workspace='ws-b', revision=2, track=_track('d', 'voice-b'))
    other_key = _voice_entry(key='video-2', revision=5, track=_track('e', 'voice-k'))
    reader = _LeakyReader(voices=[other_ws, other_key, _voice_entry(revision=1)])
    trace = tq.trace_voice(reader, 'ws-a', 'video-1')
    assert trace.revision == 1 and [item.ref for item in trace.history] == ['voice-1']
    assert tq.trace_voice(reader, 'ws-c', 'video-1') is None
    assert tq.trace_voice(_LeakyReader(voices=[other_ws]), 'ws-a', 'video-1') is None


def test_trace_voice_redacts_secret_and_unredacted_error_text():
    track = _track(
        warnings=[f'provider failed: token={CANARY}', 'Traceback (most recent call last): boom', 'see https://user:pw@host.example/path?key=v', 'rate limited'],
        usage_metrics={'billed_characters': 120, 'api_token': 7, 'note': CANARY, 'flag': True},
    )
    entry = _voice_entry(track=track, provider=f'api_key={CANARY}', model='fake model')
    trace = tq.trace_voice(_LeakyReader(voices=[entry]), 'ws-a', 'video-1')
    assert trace.warnings == (tq.REDACTED, tq.REDACTED, 'see https://host.example/path', 'rate limited')
    assert trace.usage_metrics == (('billed_characters', 120),)
    assert trace.provider == tq.REDACTED and trace.model == tq.REDACTED
    assert CANARY not in repr(trace) and 'Traceback' not in repr(trace) and 'user:pw' not in repr(trace)


def test_trace_timing_traces_voice_hash_script_fingerprint_report_and_language_evidence():
    timing = _timing()
    trace = tq.trace_timing(_LeakyReader(timings=[_timing_entry(timing=timing)]), 'ws-a', 'video-1')
    assert trace.voice_hash == timing.voice_hash and trace.script_fingerprint == timing.script_fingerprint
    assert trace.script_version_id == timing.script_version_id
    assert trace.timing_artifact_ref == 'timing-1' and trace.validation_report_ref == timing.validation_report_ref
    assert (trace.word_count, trace.voice_duration_ms, trace.retention_class) == (2, 65000, 'per_video')
    evidence = trace.language_evidence
    assert (evidence.evidence_ref, evidence.expected_language, evidence.voice_locale_reported) == ('e' * 64, 'vi', 'vi-VN')
    assert evidence.subtitle_text_hash == 'b' * 64 and evidence.finding_codes == ()


def test_trace_timing_reports_language_findings():
    timing = _timing()
    evidence = _evidence(timing, voice_locale_reported='en-US', findings=(LanguageFinding('language_mismatch', 'vi', 'en-US'),))
    trace = tq.trace_timing(_LeakyReader(timings=[_timing_entry(timing=timing, language_evidence=evidence)]), 'ws-a', 'video-1')
    assert trace.language_evidence.finding_codes == ('language_mismatch',)
    assert trace.language_evidence.voice_locale_reported == 'en-US'


@pytest.mark.parametrize('case', ['none', 'other_voice', 'other_timing'])
def test_trace_timing_attaches_language_evidence_only_when_bound_to_this_timing(case):
    timing = _timing()
    evidence = {
        'none': None,
        'other_voice': _evidence(timing, voice_hash='f' * 64),
        'other_timing': _evidence(timing, timing_artifact_ref='timing-other'),
    }[case]
    entry = _timing_entry(timing=timing, language_evidence=evidence)
    assert tq.trace_timing(_LeakyReader(timings=[entry]), 'ws-a', 'video-1').language_evidence is None


def test_trace_timing_lists_history_and_filters_workspace():
    own = [_timing_entry(revision=n, timing=_timing(f'timing-{n}')) for n in (2, 1)]
    foreign = _timing_entry(workspace='ws-b', revision=3, timing=_timing('timing-b'))
    reader = _LeakyReader(timings=[*own, foreign])
    trace = tq.trace_timing(reader, 'ws-a', 'video-1')
    assert trace.revision == 2
    assert [(item.revision, item.ref) for item in trace.history] == [(1, 'timing-1'), (2, 'timing-2')]
    assert tq.trace_timing(reader, 'ws-a', 'video-1', revision=1).timing_artifact_ref == 'timing-1'
    assert tq.trace_timing(_LeakyReader(timings=[foreign]), 'ws-a', 'video-1') is None


def test_trace_processed_media_traces_inputs_spec_revision_and_processor_identity():
    trace = tq.trace_processed_media(_LeakyReader(media=[_media_entry()]), 'ws-a', 'op-1')
    assert [(item.ref, item.content_sha256) for item in trace.input_artifact_refs] == [('in-1', 'a' * 64), ('in-2', 'b' * 64)]
    assert trace.operation_spec_revision == 'spec-3'
    assert (trace.processor_tool, trace.processor_version) == ('ffmpeg', '7.1')
    assert trace.output_artifact_refs == ('out-1',) and trace.operation_receipt_ref == 'rcpt-1'
    assert trace.disposition == 'succeeded' and trace.input_fingerprint == _request().input_fingerprint
    assert trace.output_kind == 'rendition'


def test_trace_processed_media_leaks_no_grant_or_technical_report():
    trace = tq.trace_processed_media(_LeakyReader(media=[_media_entry()]), 'ws-a', 'op-1')
    dumped = repr(trace) + json.dumps(dataclasses.asdict(trace))
    assert CANARY not in dumped and 'grant_id' not in dumped and 'stderr' not in dumped


@pytest.mark.parametrize('identity', [{}, {'tool': 'ffmpeg'}, {'version': '7.1'}, {'tool': ' ', 'version': '7.1'}])
def test_result_without_processor_identity_cannot_become_a_trace_entry(identity):
    with pytest.raises(ProcessingContractError):
        _result(_request(), processor_identity=identity)


def test_media_entry_rejects_result_that_is_not_a_processing_result():
    with pytest.raises(TypeError):
        tq.MediaEntry(
            workspace_id='ws-a', operation_id='op-1', revision=1, request=_request(),
            result={'processor_identity': {}}, output_kind='rendition',
        )


@pytest.mark.parametrize(
    'kind,expected',
    [('rendition', 'reusable'), ('analysis', 'reusable'), ('voice', 'per_video'), ('word_timing', 'per_video'), ('mix_temp', 'per_video'), ('frame', 'diagnostic')],
)
def test_processed_media_is_classified_per_video_or_reusable(kind, expected):
    trace = tq.trace_processed_media(_LeakyReader(media=[_media_entry(kind=kind)]), 'ws-a', 'op-1')
    assert trace.retention_class == expected


def test_media_entry_with_unknown_output_kind_is_rejected():
    with pytest.raises(ProcessingContractError):
        _media_entry(kind='mystery')


def test_trace_processed_media_lists_history_and_filters_workspace():
    own = [_media_entry(revision=n, result=_result(_request(), operation_receipt_ref=f'rcpt-{n}')) for n in (2, 1)]
    foreign = _media_entry(workspace='ws-b', revision=3)
    reader = _LeakyReader(media=[*own, foreign])
    trace = tq.trace_processed_media(reader, 'ws-a', 'op-1')
    assert trace.revision == 2 and trace.operation_receipt_ref == 'rcpt-2'
    assert [(item.revision, item.ref) for item in trace.history] == [(1, 'rcpt-1'), (2, 'rcpt-2')]
    assert tq.trace_processed_media(reader, 'ws-a', 'op-1', revision=1).operation_receipt_ref == 'rcpt-1'
    assert tq.trace_processed_media(_LeakyReader(media=[foreign]), 'ws-a', 'op-1') is None


FORBIDDEN_IMPORTS = (
    'src', 'voice.adapters', 'voice.application', 'voice.worker', 'voice.ports.tts',
    'socket', 'subprocess', 'os', 'pathlib', 'urllib.request', 'http',
)
FORBIDDEN_CALLS = frozenset({'append', 'append_event', 'commit', 'begin', 'rollback', 'synthesize', 'resolve', 'open', 'write_text', 'write_bytes', 'send'})


def _full_reader() -> _LeakyReader:
    return _LeakyReader(voices=[_voice_entry()], timings=[_timing_entry()], media=[_media_entry()])


def test_queries_never_call_provider_and_only_read():
    reader = _full_reader()
    tq.trace_voice(reader, 'ws-a', 'video-1')
    tq.trace_voice(reader, 'ws-a', 'missing')
    tq.trace_timing(reader, 'ws-a', 'video-1')
    tq.trace_processed_media(reader, 'ws-a', 'op-1')
    assert reader.tts.calls == 0
    assert reader.reads == [('voice', 'ws-a', 'video-1'), ('voice', 'ws-a', 'missing'), ('timing', 'ws-a', 'video-1'), ('media', 'ws-a', 'op-1')]


@pytest.mark.parametrize(
    'workspace,key,revision',
    [('', 'video-1', None), ('ws-a', ' ', None), ('ws-a', 'video-1', 0), ('ws-a', 'video-1', True), ('ws-a', 'video-1', '1')],
)
def test_invalid_query_arguments_are_rejected_before_any_read(workspace, key, revision):
    reader = _full_reader()
    for query in (tq.trace_voice, tq.trace_timing, tq.trace_processed_media):
        with pytest.raises(ValueError):
            query(reader, workspace, key, revision)
    assert reader.reads == []


def test_reader_must_provide_the_read_ports():
    with pytest.raises(TypeError):
        tq.trace_voice(object(), 'ws-a', 'video-1')


def test_traces_are_frozen_and_json_safe():
    reader = _full_reader()
    traces = (
        tq.trace_voice(reader, 'ws-a', 'video-1'),
        tq.trace_timing(reader, 'ws-a', 'video-1'),
        tq.trace_processed_media(reader, 'ws-a', 'op-1'),
    )
    for trace in traces:
        with pytest.raises(dataclasses.FrozenInstanceError):
            trace.workspace_id = 'ws-z'
        json.dumps(dataclasses.asdict(trace))


def test_module_is_read_only_and_isolated():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    imported, calls = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)
    bad = [name for name in imported if any(name == prefix or name.startswith(prefix + '.') for prefix in FORBIDDEN_IMPORTS)]
    assert bad == []
    assert not calls & FORBIDDEN_CALLS
