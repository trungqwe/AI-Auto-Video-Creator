"""F-16: RenderRepository append-only, UoW in-memory, outbox và event của F (CT-EVT-002, CT-EVT-003).

coveredIds: CT-EVT-002, CT-EVT-003, TST-CTR-INV-002, TST-SEC-INV-012
"""
import ast
import copy
import dataclasses
import json
import pathlib
import re
from datetime import datetime, timedelta, timezone
import pytest
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.events import contracts
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.domain.interfaces.uow import IUnitOfWork
from controlplane.domain.statemachine import OperationState
from render.adapters import memory
from render.domain import events
from render.domain.package_contract import validate_render_package_payload
from render.domain.quality_report import GATE_KINDS, GateKind, GateName, GateResult, QualityPolicy, build_quality_report
from render.domain.render_attempt import ProbeEvidence, fail_attempt, mark_outcome_unknown, prepare_attempt, reconcile_attempt, start_attempt, succeed_attempt
from render.domain.render_command import RenderCommandSpec, ToolIdentity
from render.ports import repositories

ROOT = pathlib.Path(__file__).resolve().parents[3]
ENVELOPE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'domain-event-envelope' / 'payloads.json'
BINDING = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'domain-event-envelope.json'
PACKAGE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'
SOURCES = (
    ROOT / 'src' / 'render' / 'ports' / 'repositories.py',
    ROOT / 'src' / 'render' / 'adapters' / 'memory.py',
    ROOT / 'src' / 'render' / 'domain' / 'events.py',
)
CANARY = 'CANARY-7f3a9c-SECRET'
NOW = datetime(2026, 10, 19, 8, 0, 0, tzinfo=timezone.utc)
OUTPUT_REF = 'artifact/render/attempt-1/out.mp4'
SECOND_REF = 'artifact/render/attempt-2/out.mp4'


def at(seconds: int) -> datetime:
    return NOW + timedelta(seconds=seconds)


def spec() -> RenderCommandSpec:
    return RenderCommandSpec(
        kind='render',
        argv=('C:/tools/ffmpeg.exe', '-i', f'C:/staging/{CANARY}/a.mp4'),
        redacted_argv=('{:tool}', '-i', '{asset:0}'),
        spec_fingerprint='f' * 64,
        tool_identity=ToolIdentity(name='ffmpeg', version='6.1', build='test-build', executable='C:/tools/ffmpeg.exe'),
    )


def prepared(attempt_id: str = 'attempt-1', output: str = OUTPUT_REF, fingerprint: str = 'a' * 64):
    return prepare_attempt(
        render_attempt_id=attempt_id,
        package_fingerprint=fingerprint,
        output_artifact_ref=output,
        command_spec=spec(),
        receipt_ref='receipt-1',
    )


def started(**kw):
    return start_attempt(prepared(**kw), expected_revision=0, started_at=at(0))


def succeeded(**kw):
    return succeed_attempt(
        started(**kw),
        expected_revision=1,
        finished_at=at(60),
        wall_time_ms=60000,
        warnings=[f'password={CANARY}', f'note {CANARY}'],
        secret_values=[CANARY],
    )


def failed(**kw):
    return fail_attempt(started(**kw), expected_revision=1, finished_at=at(30), error='ffmpeg exited with code 1')


def unknown(**kw):
    return mark_outcome_unknown(started(**kw), expected_revision=1, reason='worker timeout after render')


def reconciled():
    return reconcile_attempt(
        unknown(),
        ProbeEvidence(
            output_artifact_ref=OUTPUT_REF,
            exists=True,
            sha256='b' * 64,
            expected_sha256='b' * 64,
            playable=True,
            evidence_ref='probe-1',
            observed_at=at(90),
        ),
    )


def package(pid: str = 'pkg-1', char: str = 'a'):
    raw = json.loads(PACKAGE_FIXTURE.read_text(encoding='utf-8'))['entities']['RenderPackage']['valid'][0]
    return dataclasses.replace(
        validate_render_package_payload(raw),
        render_package_id=pid,
        package_fingerprint=char * 64,
    )


def report(failing=(), policy=None):
    hard = [n for n in GateName if GATE_KINDS[n] is GateKind.HARD]
    results = [
        GateResult(
            gate=n,
            status='failed' if n in failing else 'passed',
            reason='gate_failed' if n in failing else None,
        )
        for n in hard
    ]
    return build_quality_report(results, {GateName.INFERENCE_DISCLOSURE_PRESENT: False}, policy=policy)


def new_uow():
    return memory.InMemoryUnitOfWork()


# Phần 1: RenderRepository append-only


def test_append_latest_and_revisions():
    u = new_uow()
    a1 = prepared()
    a2 = started()
    with u:
        u.renders.append('render_attempt', 'attempt-1', 1, a1)
        u.renders.append('render_attempt', 'attempt-1', 2, a2)
        u.commit()

    latest = u.renders.latest('render_attempt', 'attempt-1')
    assert latest is not None
    assert latest.revision == 2
    assert latest.record is a2

    revs = u.renders.revisions('render_attempt', 'attempt-1')
    assert len(revs) == 2
    assert revs[0].revision == 1
    assert revs[0].record is a1
    assert revs[1].revision == 2
    assert revs[1].record is a2

    assert u.renders.latest('render_attempt', 'none') is None
    assert u.renders.revisions('render_attempt', 'none') == ()


def test_same_or_skipped_revision_is_rejected_and_keeps_old():
    u = new_uow()
    a1 = prepared()
    a2 = started()
    with u:
        u.renders.append('render_attempt', 'attempt-1', 1, a1)
        u.commit()

    with u:
        with pytest.raises(RevisionConflictError) as exc_same:
            u.renders.append('render_attempt', 'attempt-1', 1, a2)
        assert exc_same.value.current_revision == 1

        with pytest.raises(RevisionConflictError) as exc_skip:
            u.renders.append('render_attempt', 'attempt-1', 3, a2)
        assert exc_skip.value.current_revision == 1

        with pytest.raises(RevisionConflictError) as exc_nonexistent:
            u.renders.append('render_attempt', 'attempt-9', 2, prepared(attempt_id='attempt-9', output=SECOND_REF))
        assert exc_nonexistent.value.current_revision == 0

    assert len(u.renders.revisions('render_attempt', 'attempt-1')) == 1
    assert u.renders.latest('render_attempt', 'attempt-1').record is a1


def test_duplicate_package_fingerprint_is_rejected():
    u = new_uow()
    p1 = package('pkg-1', 'a')
    with u:
        u.renders.append('render_package', 'pkg-1', 1, p1)
        u.commit()

    with u:
        with pytest.raises(repositories.DuplicateRecordError):
            u.renders.append('render_package', 'pkg-2', 1, package('pkg-2', 'a'))

        with pytest.raises(repositories.DuplicateRecordError):
            u.renders.append('render_package', 'pkg-1', 2, package('pkg-1', 'a'))

        with pytest.raises(repositories.ImmutableFieldError):
            u.renders.append('render_package', 'pkg-1', 2, package('pkg-1', 'b'))

    assert u.renders.revisions('render_package', 'pkg-2') == ()


def test_duplicate_output_artifact_ref_is_rejected():
    u = new_uow()
    a1 = prepared()
    with u:
        u.renders.append('render_attempt', 'attempt-1', 1, a1)
        u.commit()

    with u:
        with pytest.raises(repositories.DuplicateRecordError):
            u.renders.append('render_attempt', 'attempt-2', 1, prepared(attempt_id='attempt-2'))

        u.renders.append('render_attempt', 'attempt-2', 1, prepared(attempt_id='attempt-2', output=SECOND_REF))
        u.commit()

    assert u.renders.latest('render_attempt', 'attempt-1').record.package_fingerprint == 'a' * 64
    assert u.renders.latest('render_attempt', 'attempt-2').record.package_fingerprint == 'a' * 64


def test_key_must_match_record_id():
    u = new_uow()
    with u:
        with pytest.raises(ValueError):
            u.renders.append('render_attempt', 'attempt-2', 1, prepared())

        with pytest.raises(ValueError):
            u.renders.append('render_package', 'pkg-x', 1, package('pkg-1', 'a'))

    assert u.renders.revisions('render_attempt', 'attempt-2') == ()
    assert u.renders.revisions('render_package', 'pkg-x') == ()


def test_new_revision_cannot_change_identity_fields():
    u = new_uow()
    with u:
        u.renders.append('render_attempt', 'attempt-1', 1, prepared())
        u.commit()

    with u:
        with pytest.raises(repositories.ImmutableFieldError):
            u.renders.append('render_attempt', 'attempt-1', 2, started(output=SECOND_REF))

        with pytest.raises(repositories.ImmutableFieldError):
            u.renders.append('render_attempt', 'attempt-1', 2, started(fingerprint='c' * 64))

        u.renders.append('render_attempt', 'attempt-1', 2, started())
        u.commit()


def test_quality_report_kind_appends_revisions():
    u = new_uow()
    r1 = report()
    r2 = report(failing=(GateName.FILE_PLAYABLE,))
    with u:
        u.renders.append('quality_report', 'attempt-1', 1, r1)
        u.renders.append('quality_report', 'attempt-1', 2, r2)
        u.commit()

    latest = u.renders.latest('quality_report', 'attempt-1')
    assert latest is not None
    assert latest.record is r2

    with u:
        with pytest.raises(TypeError):
            u.renders.append('quality_report', 'k', 1, prepared())


def test_record_type_revision_and_names_are_validated():
    u = new_uow()
    with u:
        with pytest.raises(TypeError):
            u.renders.append('render_attempt', 'k', 1, object())

        with pytest.raises(TypeError):
            u.renders.append('render_package', 'k', 1, prepared())

        with pytest.raises(ValueError):
            u.renders.append('video', 'k', 1, prepared())

        for rev in (0, '1', True, None, -1):
            with pytest.raises(ValueError):
                u.renders.append('render_attempt', 'attempt-1', rev, prepared())

        for bad in ('', ' ', None):
            with pytest.raises(ValueError):
                u.renders.append(bad, 'attempt-1', 1, prepared())
            with pytest.raises(ValueError):
                u.renders.append('render_attempt', bad, 1, prepared())


def test_repository_has_no_overwrite_or_delete_api():
    u = new_uow()
    for name in ('delete', 'remove', 'save', 'update', 'overwrite', 'put', 'clear', 'pop'):
        assert not hasattr(u.renders, name)
    assert isinstance(u.renders, repositories.RenderRepository)


def test_write_outside_transaction_is_rejected():
    u = new_uow()
    with pytest.raises(memory.TransactionNotActiveError):
        u.renders.append('render_attempt', 'attempt-1', 1, prepared())
    assert u.renders.latest('render_attempt', 'attempt-1') is None
    assert u.renders.revisions('render_attempt', 'attempt-1') == ()


def test_stored_record_is_frozen():
    rec = repositories.StoredRecord('render_attempt', 'k', 1, 'rec')
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.revision = 9


# Phần 2: Unit of Work và outbox


def append_event(u, dedup='d-1', payload=None):
    return u.outbox.append_event(
        'RenderCompleted',
        'attempt-1',
        payload or {'output_artifact_ref': OUTPUT_REF},
        dedup,
    )


def test_uow_and_outbox_implement_controlplane_interfaces():
    u = new_uow()
    assert issubclass(memory.InMemoryUnitOfWork, IUnitOfWork)
    assert isinstance(u, IUnitOfWork)
    assert isinstance(u.outbox, IOutboxWriter)
    assert isinstance(u.renders, repositories.RenderRepository)


def test_commit_persists_records_and_outbox():
    u = new_uow()
    with u:
        u.renders.append('render_attempt', 'attempt-1', 1, prepared())
        append_event(u)
        u.commit()
    assert u.active is False
    assert u.renders.latest('render_attempt', 'attempt-1') is not None
    assert len(u.outbox.records()) == 1


def test_exit_without_commit_rolls_back_records_and_outbox():
    u = new_uow()
    with u:
        u.renders.append('render_attempt', 'attempt-1', 1, prepared())
        append_event(u)
    assert u.renders.latest('render_attempt', 'attempt-1') is None
    assert u.outbox.records() == ()
    assert u.active is False


def test_exception_in_block_rolls_back_everything():
    u = new_uow()
    with pytest.raises(RuntimeError):
        with u:
            u.renders.append('render_attempt', 'attempt-1', 1, prepared())
            append_event(u)
            raise RuntimeError('boom')
    assert u.renders.latest('render_attempt', 'attempt-1') is None
    assert u.outbox.records() == ()
    assert u.active is False


def test_explicit_rollback_removes_new_revision_but_keeps_committed():
    u = new_uow()
    with u:
        u.renders.append('render_attempt', 'attempt-1', 1, prepared())
        append_event(u, 'd-1')
        u.commit()

    with u:
        u.renders.append('render_attempt', 'attempt-1', 2, started())
        append_event(u, 'd-2')
        u.rollback()

    revs = u.renders.revisions('render_attempt', 'attempt-1')
    assert len(revs) == 1
    assert revs[0].revision == 1
    recs = u.outbox.records()
    assert len(recs) == 1
    assert recs[0].deduplication_id == 'd-1'


def test_begin_twice_and_finish_without_begin():
    u = new_uow()
    u.begin()
    with pytest.raises(memory.TransactionAlreadyActiveError):
        u.begin()
    u.rollback()
    with pytest.raises(memory.TransactionNotActiveError):
        u.commit()
    with pytest.raises(memory.TransactionNotActiveError):
        u.rollback()


def test_outbox_dedups_by_deduplication_id():
    u = new_uow()
    with u:
        e1 = append_event(u, 'd-1', {'output_artifact_ref': OUTPUT_REF})
        e2 = append_event(u, 'd-1', {'output_artifact_ref': 'ignored'})
        assert e1 == e2
        assert len(u.outbox.records()) == 1
        assert u.outbox.records()[0].payload['output_artifact_ref'] == OUTPUT_REF

        e3 = append_event(u, 'd-2', {'output_artifact_ref': OUTPUT_REF})
        assert e3 != e1
        assert len(u.outbox.records()) == 2
        u.commit()

    with u:
        assert append_event(u, 'd-1') == e1
        assert len(u.outbox.records()) == 2


def test_redelivered_event_commits_side_effect_once():
    first = events.build_render_completed(context(), attempt=succeeded())
    redelivered = events.build_render_completed(context(event_id='evt-2', message_id='msg-2'), attempt=succeeded())
    dedup = events.deduplication_id_for(first)
    assert events.deduplication_id_for(redelivered) == dedup

    def deliver(u, ev):
        return u.outbox.append_event(ev.event_name, ev.aggregate_id, dataclasses.asdict(ev), dedup)

    u = new_uow()
    with u:
        first_id = deliver(u, first)
        assert deliver(u, redelivered) == first_id
        assert len(u.outbox.records()) == 1
        u.commit()

    with u:
        assert deliver(u, redelivered) == first_id
        u.commit()
    assert len(u.outbox.records()) == 1
    assert u.outbox.records()[0].payload['event_id'] == 'evt-1'

    crashed = new_uow()
    with crashed:
        deliver(crashed, first)
    assert crashed.outbox.records() == ()
    with crashed:
        deliver(crashed, redelivered)
        crashed.commit()
    assert len(crashed.outbox.records()) == 1


def test_outbox_rejects_unsafe_blank_or_non_mapping_input():
    u = new_uow()
    with u:
        for bad_payload in ({'video': b'RIFF....'}, {'note': 'token=abc'}, [1, 2, 3], 'not-mapping'):
            with pytest.raises(ValueError):
                u.outbox.append_event('RenderCompleted', 'attempt-1', bad_payload, 'd-bad')

        for bad in ('', ' '):
            with pytest.raises(ValueError):
                u.outbox.append_event(bad, 'attempt-1', {'output_artifact_ref': OUTPUT_REF}, 'd-1')
            with pytest.raises(ValueError):
                u.outbox.append_event('RenderCompleted', bad, {'output_artifact_ref': OUTPUT_REF}, 'd-1')
            with pytest.raises(ValueError):
                u.outbox.append_event('RenderCompleted', 'attempt-1', {'output_artifact_ref': OUTPUT_REF}, bad)

    assert u.outbox.records() == ()

    with pytest.raises(memory.TransactionNotActiveError):
        u.outbox.append_event('RenderCompleted', 'attempt-1', {'output_artifact_ref': OUTPUT_REF}, 'd-1')


def test_outbox_record_is_read_only_deep_copy():
    u = new_uow()
    lst = ['a']
    with u:
        u.outbox.append_event('RenderCompleted', 'attempt-1', {'refs': lst}, 'd-copy')
        u.commit()
    lst.append('b')
    recs = u.outbox.records()
    assert list(recs[0].payload['refs']) == ['a']
    with pytest.raises(TypeError):
        recs[0].payload['x'] = 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        recs[0].event_id = 'new-id'


# Phần 3: builder event


def context(**over):
    values = dict(
        workspace_id='ws-1',
        correlation_id='corr-1',
        actor='worker-f',
        occurred_at='2026-10-19T00:00:00Z',
        recovery_epoch='epoch-0001',
        event_id='evt-1',
        message_id='msg-1',
    )
    values.update(over)
    return events.EventContext(**values)


RENDER_PAYLOAD = {
    'render_attempt_id': 'attempt-1',
    'package_fingerprint': 'a' * 64,
    'output_artifact_ref': OUTPUT_REF,
    'receipt_ref': 'receipt-1',
    'revision': 2,
}


def qc(rep=None, attempt=None, revision=3):
    return events.build_output_quality_checked(
        context(),
        attempt=attempt or succeeded(),
        report=rep or report(),
        aggregate_revision=revision,
    )


def test_render_completed_is_a_controlplane_domain_event():
    ev = events.build_render_completed(context(), attempt=succeeded())
    assert type(ev) is contracts.DomainEvent
    assert events.DomainEvent is contracts.DomainEvent
    assert ev.event_name == 'RenderCompleted'
    assert ev.aggregate_type == 'RenderAttempt'
    assert ev.aggregate_id == 'attempt-1'
    assert ev.aggregate_revision == 2
    assert ev.producer == 'F'
    assert ev.schema_version == '1.0.0'
    assert ev.sensitivity == 'internal'
    assert ev.contract_name == 'render.events'
    assert ev.recovery_epoch == 'epoch-0001'
    assert ev.event_id == 'evt-1'
    assert ev.message_id == 'msg-1'
    assert ev.workspace_id == 'ws-1'
    assert ev.payload == RENDER_PAYLOAD
    assert json.dumps(ev.payload) is not None
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.event_name = 'Other'

    ev_reconciled = events.build_render_completed(context(), attempt=reconciled())
    assert ev_reconciled.aggregate_revision == 3
    assert ev_reconciled.payload['revision'] == 3


@pytest.mark.parametrize('attempt_factory', [prepared, started, failed, unknown])
def test_render_completed_rejects_attempt_that_is_not_succeeded(attempt_factory):
    with pytest.raises(events.AttemptNotSucceededError) as exc:
        events.build_render_completed(context(), attempt=attempt_factory())
    assert exc.value.code == 'ATTEMPT_NOT_SUCCEEDED'

    with pytest.raises(TypeError):
        events.build_render_completed(context(), attempt=object())


def test_output_quality_checked_is_emitted_for_pass_and_fail():
    rep = report()
    ev = qc(rep)
    assert type(ev) is contracts.DomainEvent
    assert ev.event_name == 'OutputQualityChecked'
    assert ev.aggregate_type == 'QualityReport'
    assert ev.aggregate_id == rep.report_id
    assert ev.aggregate_revision == 3
    assert ev.producer == 'F'

    expected_payload = {
        'quality_report_ref': rep.report_id,
        'render_attempt_id': 'attempt-1',
        'output_artifact_ref': OUTPUT_REF,
        'passed': True,
        'blocking_gates': [],
        'gate_statuses': {g.gate.value: g.status.value for g in rep.gates},
    }
    assert ev.payload == expected_payload
    assert len(ev.payload['gate_statuses']) == 13

    bad = report(failing=(GateName.FILE_PLAYABLE, GateName.DURATION_RANGE))
    ev_bad = qc(bad)
    assert ev_bad is not None
    assert ev_bad.payload['passed'] is False
    assert ev_bad.payload['blocking_gates'] == ['FILE_PLAYABLE', 'DURATION_RANGE']
    assert ev_bad.payload['gate_statuses']['FILE_PLAYABLE'] == 'failed'

    pol_rep = report(policy=QualityPolicy(revision='policy-r1', thresholds={}))
    ev_pol = qc(pol_rep)
    assert ev_pol.payload['policy_revision'] == 'policy-r1'
    assert 'policy_revision' not in ev.payload


def test_output_quality_checked_input_validation():
    with pytest.raises(events.AttemptNotSucceededError):
        qc(attempt=failed())
    with pytest.raises(TypeError):
        events.build_output_quality_checked(context(), attempt=succeeded(), report='x', aggregate_revision=3)
    for bad_rev in (0, '3', True, None, -1):
        with pytest.raises(events.EventEnvelopeError):
            qc(revision=bad_rev)


def test_payload_holds_only_refs_hashes_revisions_and_gate_summary():
    ref_pattern = re.compile(r'^[A-Za-z]:[/\\]|^/|^\\\\|[ ]')
    for ev in (events.build_render_completed(context(), attempt=succeeded()), qc()):
        serialized = json.dumps(ev.payload)
        for key in ev.payload:
            for forbidden in ('argv', 'command', 'path', 'spec', 'error', 'warning', 'secret', 'token'):
                assert forbidden not in key.lower()
        for ref_field in ('render_attempt_id', 'package_fingerprint', 'output_artifact_ref', 'receipt_ref', 'quality_report_ref'):
            if ref_field in ev.payload:
                val = ev.payload[ref_field]
                assert isinstance(val, str)
                assert ref_pattern.search(val) is None
        for val in ev.payload.values():
            assert not isinstance(val, (bytes, bytearray))
        assert 'ffmpeg.exe' not in serialized
        assert 'C:/staging' not in serialized


def test_unsafe_refs_are_rejected():
    bad_refs = ('C:/out/a.mp4', '/abs/a.mp4', chr(92) * 2 + 'srv' + chr(92) + 'a.mp4', '../a.mp4', 'ffmpeg -i a.mp4', 'token=abc')
    for bad in bad_refs:
        att = dataclasses.replace(succeeded(), output_artifact_ref=bad)
        with pytest.raises(ValueError):
            events.build_render_completed(context(), attempt=att)
        with pytest.raises(ValueError):
            qc(attempt=att)

    att_bad_receipt = dataclasses.replace(succeeded(), receipt_ref='traceback')
    with pytest.raises(ValueError, match='unsafe domain event payload'):
        events.build_render_completed(context(), attempt=att_bad_receipt)


def test_builder_calls_contract_payload_guard(monkeypatch):
    spy_list = []

    def spy(payload):
        spy_list.append(dict(payload))
        return contracts.ensure_safe_event_payload(payload)

    monkeypatch.setattr(events, 'ensure_safe_event_payload', spy)
    events.build_render_completed(context(), attempt=succeeded())
    assert len(spy_list) > 0
    assert spy_list[0] == RENDER_PAYLOAD


def test_canary_never_reaches_events_or_outbox():
    attempt = succeeded()
    ev1 = events.build_render_completed(context(), attempt=attempt)
    ev2 = qc(attempt=attempt)

    text = (
        json.dumps(dataclasses.asdict(ev1), default=str)
        + repr(ev1)
        + json.dumps(dataclasses.asdict(ev2), default=str)
        + repr(ev2)
    )
    assert CANARY not in text

    u = new_uow()
    with u:
        u.outbox.append_event(ev1.event_name, ev1.aggregate_id, dataclasses.asdict(ev1), events.deduplication_id_for(ev1))
        u.outbox.append_event(ev2.event_name, ev2.aggregate_id, dataclasses.asdict(ev2), events.deduplication_id_for(ev2))
        u.commit()

    assert CANARY not in repr(u.outbox.records())

    initial_len = len(u.outbox.records())
    with u:
        with pytest.raises(ValueError):
            u.outbox.append_event('RenderCompleted', 'attempt-1', {'note': f'token={CANARY}'}, 'd-canary')
    assert len(u.outbox.records()) == initial_len


# Phần 4: context, dedup, envelope fixture, ranh giới


def test_invalid_context_and_revision_are_rejected():
    with pytest.raises(events.EventEnvelopeError) as exc_epoch_none:
        events.build_render_completed(context(recovery_epoch=None), attempt=succeeded())
    assert ('wrong_type', 'recovery_epoch') in exc_epoch_none.value.issues

    with pytest.raises(events.EventEnvelopeError) as exc_epoch_empty:
        events.build_render_completed(context(recovery_epoch=''), attempt=succeeded())
    assert ('constraint_violation', 'recovery_epoch') in exc_epoch_empty.value.issues

    with pytest.raises(events.EventEnvelopeError) as exc_id_empty:
        events.build_render_completed(context(event_id=''), attempt=succeeded())
    assert ('constraint_violation', 'event_id') in exc_id_empty.value.issues

    for bad_dict in (
        {'workspace_id': ' '},
        {'actor': ''},
        {'message_id': ''},
        {'correlation_id': ''},
        {'occurred_at': 'không-phải-ngày'},
        {'causation_id': ''},
    ):
        with pytest.raises(ValueError):
            context(**bad_dict)

    assert context(causation_id=None).causation_id is None


def test_deduplication_id_for_is_stable():
    ev = events.build_render_completed(context(), attempt=succeeded())
    assert events.deduplication_id_for(ev) == 'ws-1:RenderCompleted:attempt-1:2'

    ev_rec = events.build_render_completed(context(), attempt=reconciled())
    assert events.deduplication_id_for(ev_rec).endswith(':3')
    assert events.deduplication_id_for(ev_rec) != events.deduplication_id_for(ev)

    with pytest.raises(TypeError):
        events.deduplication_id_for('x')


def test_fixture_envelopes():
    data = json.loads(ENVELOPE_FIXTURE.read_text(encoding='utf-8'))
    entity = data['entities']['DomainEvent']
    assert len(entity['valid']) >= 1
    assert {'producer_outside_modules', 'aggregate_revision_as_string', 'stack_trace_in_event', 'missing_recovery_epoch'} <= {c['case'] for c in entity['invalid']}
    for case in entity['valid']:
        assert events.envelope_issues(case) == ()
    for case in entity['invalid']:
        expected = ((case['expected_error']['code'], case['expected_error']['field']),)
        actual = events.envelope_issues(case['payload'])
        assert actual == expected, f"Failed case {case['case']}: expected {expected}, got {actual}"


def test_builder_envelopes_are_valid():
    for ev in (events.build_render_completed(context(), attempt=succeeded()), qc()):
        envelope = {n: getattr(ev, n) for n in events.ENVELOPE_FIELDS}
        assert events.envelope_issues(envelope) == ()
        assert events.envelope_issues(dataclasses.asdict(ev)) == ()


def test_envelope_issues_edge_cases():
    fixture_data = json.loads(ENVELOPE_FIXTURE.read_text(encoding='utf-8'))
    valid = copy.deepcopy(fixture_data['entities']['DomainEvent']['valid'][0])
    assert events.envelope_issues([]) == (('wrong_type', '$'),)

    c1 = copy.deepcopy(valid)
    c1['payload'] = {'a': {'blob': 'x'}}
    assert ('forbidden_field', 'blob') in events.envelope_issues(c1)

    c2 = copy.deepcopy(valid)
    c2['payload'] = {'b': b'x'}
    assert ('forbidden_field', 'payload') in events.envelope_issues(c2)

    c3 = copy.deepcopy(valid)
    c3['aggregate_revision'] = True
    assert events.envelope_issues(c3) == (('wrong_type', 'aggregate_revision'),)

    c4 = copy.deepcopy(valid)
    c4['aggregate_revision'] = 0
    assert events.envelope_issues(c4) == (('constraint_violation', 'aggregate_revision'),)

    c5 = copy.deepcopy(valid)
    c5['event_id'] = ' '
    assert events.envelope_issues(c5) == (('constraint_violation', 'event_id'),)

    c6 = copy.deepcopy(valid)
    c6['producer'] = 'f'
    assert events.envelope_issues(c6) == (('enum_violation', 'producer'),)

    c7 = copy.deepcopy(valid)
    c7['producer'] = 5
    assert events.envelope_issues(c7) == (('wrong_type', 'producer'),)

    c8 = copy.deepcopy(valid)
    c8['workspace_id'] = 'ws-1'
    assert events.envelope_issues(c8) == ()


def test_constants_match_binding():
    binding = json.loads(BINDING.read_text(encoding='utf-8'))
    entity = next(e for e in binding['entities'] if e['name'] == 'DomainEvent')
    assert {f['name']: f['type'] for f in entity['fields']} == dict(events.ENVELOPE_FIELDS)
    producer_field = next(f for f in entity['fields'] if f['name'] == 'producer')
    assert producer_field['enum'] == list(events.MODULE_IDS)
    assert set(entity['forbidden_fields']) == events.FORBIDDEN_ENVELOPE_FIELDS
    assert events.PRODUCER == 'F'
    assert 'F' in events.MODULE_IDS


def test_sources_reuse_controlplane_types_and_respect_boundaries():
    forbidden_roots = {
        'os', 'socket', 'subprocess', 'shutil', 'tempfile', 'time', 'random', 'uuid',
        'requests', 'urllib', 'http', 'psycopg', 'creative', 'voice', 'catalog', 'ingestion', 'source_ingestion',
    }
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in ('IUnitOfWork', 'IOutboxWriter', 'DomainEvent')
            elif isinstance(node, ast.FunctionDef):
                assert not node.name.startswith(('delete_', 'remove_', 'cleanup_'))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split('.')[0]
                    assert not alias.name.startswith('src.')
                    assert root not in forbidden_roots
                    assert not alias.name.startswith(('controlplane.config', 'controlplane.infrastructure'))
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    root = node.module.split('.')[0]
                    assert not node.module.startswith('src.')
                    assert root not in forbidden_roots
                    assert not node.module.startswith(('controlplane.config', 'controlplane.infrastructure'))

    def get_from_imports(p):
        mapping = {}
        tree = ast.parse(p.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [alias.name for alias in node.names]
                mapping.setdefault(node.module, []).extend(names)
        return mapping

    mem_map = get_from_imports(ROOT / 'src' / 'render' / 'adapters' / 'memory.py')
    assert 'IUnitOfWork' in mem_map.get('controlplane.domain.interfaces.uow', [])
    assert 'IOutboxWriter' in mem_map.get('controlplane.domain.interfaces.outbox', [])
    assert 'RevisionConflictError' in mem_map.get('controlplane.domain.concurrency', [])

    evt_map = get_from_imports(ROOT / 'src' / 'render' / 'domain' / 'events.py')
    assert 'DomainEvent' in evt_map.get('controlplane.domain.events.contracts', [])
    assert 'ensure_safe_event_payload' in evt_map.get('controlplane.domain.events.contracts', [])

    assert IUnitOfWork in memory.InMemoryUnitOfWork.__mro__
    assert IOutboxWriter in memory.InMemoryOutboxWriter.__mro__
