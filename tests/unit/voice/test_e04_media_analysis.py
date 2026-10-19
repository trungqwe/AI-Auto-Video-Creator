"""E-04: versioned media analysis result and append-only history (CT-PROC-004).

coveredIds: CT-PROC-004
"""
import ast
import dataclasses
import enum
import math
import pathlib
import re

import pytest

from voice.domain import media_analysis as ma
from voice.domain import processing as proc

KINDS = (
    'keyframes_shots',
    'transcript_ocr',
    'entities_faces_objects',
    'motion_scene_audio_energy',
    'semantic_tags',
)
TEXT_FIELDS = ('analysis_id', 'model', 'model_version', 'spec_revision')


def sha(ch: str) -> str:
    return ch * 64


def clip_ref(name: str = 'clip-1', ch: str = 'a') -> proc.ArtifactRef:
    return proc.ArtifactRef(name, sha(ch))


def analysis_kwargs(**over) -> dict:
    base = {
        'analysis_id': 'an-1',
        'input_ref': clip_ref(),
        'analysis_kind': 'transcript_ocr',
        'model': 'whisper-fake',
        'model_version': '1.0',
        'spec_revision': 'spec-1',
        'confidence': 0.8,
        'coverage': 0.5,
        'failure_flags': [],
    }
    base.update(over)
    return base


def make(**over) -> ma.AnalysisResult:
    return ma.AnalysisResult(**analysis_kwargs(**over))


def err(exc_info, code: str, field: str) -> None:
    assert exc_info.value.code == code
    assert exc_info.value.field == field


def test_analysis_kind_is_strenum_with_five_values() -> None:
    assert issubclass(ma.AnalysisKind, enum.StrEnum)
    assert tuple(e.value for e in ma.AnalysisKind) == KINDS
    assert ma.AnalysisKind('transcript_ocr') is ma.AnalysisKind.TRANSCRIPT_OCR


def test_field_constants_match_dataclass() -> None:
    expected = (
        'analysis_id', 'input_ref', 'analysis_kind', 'model', 'model_version',
        'spec_revision', 'confidence', 'coverage', 'failure_flags',
    )
    assert ma.ANALYSIS_FIELDS == expected
    assert tuple(f.name for f in dataclasses.fields(ma.AnalysisResult)) == expected


def test_result_is_frozen_and_normalized() -> None:
    r = make(
        analysis_kind='semantic_tags', confidence=1, coverage=0, failure_flags=['a', 'b'],
        input_ref={'ref': 'clip-1', 'content_sha256': sha('a')},
    )
    assert r.analysis_kind is ma.AnalysisKind.SEMANTIC_TAGS
    assert r.input_ref == clip_ref()
    assert r.confidence == 1.0 and isinstance(r.confidence, float)
    assert r.coverage == 0.0 and isinstance(r.coverage, float)
    assert r.failure_flags == ('a', 'b')
    for name in ma.ANALYSIS_FIELDS:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(r, name, 'x')
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.input_ref.ref = 'other'  # type: ignore[misc]


@pytest.mark.parametrize('field', ('confidence', 'coverage'))
@pytest.mark.parametrize('value', (0, 0.0, 0.25, 1, 1.0))
def test_unit_interval_accepts_bounds(field: str, value: object) -> None:
    assert getattr(make(**{field: value}), field) == float(value)


@pytest.mark.parametrize('field', ('confidence', 'coverage'))
@pytest.mark.parametrize('value', (1.5, -0.1, 1.0000001, 2, -1, math.nan, math.inf, -math.inf, 10 ** 400))
def test_unit_interval_rejects_out_of_range(field: str, value: object) -> None:
    with pytest.raises(proc.ProcessingContractError) as exc:
        make(**{field: value})
    err(exc, 'constraint_violation', field)


@pytest.mark.parametrize('field', ('confidence', 'coverage'))
@pytest.mark.parametrize('value', (True, False, '0.5', [0.5], {'v': 0.5}))
def test_unit_interval_rejects_wrong_type(field: str, value: object) -> None:
    with pytest.raises(proc.ProcessingContractError) as exc:
        make(**{field: value})
    err(exc, 'wrong_type', field)


@pytest.mark.parametrize('field', ma.ANALYSIS_FIELDS)
def test_none_field_is_missing_required(field: str) -> None:
    with pytest.raises(proc.ProcessingContractError) as exc:
        make(**{field: None})
    err(exc, 'missing_required', field)


@pytest.mark.parametrize('field', ma.ANALYSIS_FIELDS)
def test_from_mapping_missing_field(field: str) -> None:
    payload = analysis_kwargs()
    del payload[field]
    with pytest.raises(proc.ProcessingContractError) as exc:
        ma.AnalysisResult.from_mapping(payload)
    err(exc, 'missing_required', field)


def test_from_mapping_builds_result_and_rejects_non_mapping() -> None:
    assert ma.AnalysisResult.from_mapping(analysis_kwargs()) == make()
    with pytest.raises(proc.ProcessingContractError) as exc:
        ma.AnalysisResult.from_mapping([])  # type: ignore[arg-type]
    err(exc, 'wrong_type', 'payload')


@pytest.mark.parametrize('field', TEXT_FIELDS)
def test_text_fields_reject_blank_and_wrong_type(field: str) -> None:
    for blank in ('', '   '):
        with pytest.raises(proc.ProcessingContractError) as exc:
            make(**{field: blank})
        err(exc, 'constraint_violation', field)
    with pytest.raises(proc.ProcessingContractError) as exc:
        make(**{field: 5})
    err(exc, 'wrong_type', field)


def test_kind_rejects_unknown_and_wrong_type() -> None:
    for bad in ('image_safety', 'Transcript_OCR', 'ocr'):
        with pytest.raises(proc.ProcessingContractError) as exc:
            make(analysis_kind=bad)
        err(exc, 'enum_violation', 'analysis_kind')
    with pytest.raises(proc.ProcessingContractError) as exc:
        make(analysis_kind=5)
    err(exc, 'wrong_type', 'analysis_kind')


def test_input_ref_rules() -> None:
    with pytest.raises(proc.ProcessingContractError) as exc:
        make(input_ref={'ref': 'clip-1', 'content_sha256': 'A' * 64})
    err(exc, 'wrong_type', 'content_sha256')
    with pytest.raises(proc.ProcessingContractError) as exc:
        make(input_ref='clip-1')
    err(exc, 'wrong_type', 'input_ref')
    with pytest.raises(proc.ProcessingContractError) as exc:
        make(input_ref={'ref': 'clip-1'})
    err(exc, 'missing_required', 'content_sha256')
    with pytest.raises(proc.ProcessingContractError) as exc:
        make(input_ref={'content_sha256': sha('a')})
    err(exc, 'missing_required', 'ref')


def test_failure_flags_rules() -> None:
    assert make(failure_flags=[]).failure_flags == ()
    assert make(failure_flags=('ocr_failed', 'low_light')).failure_flags == ('ocr_failed', 'low_light')
    for bad in ('ocr_failed', b'x', {'a': 1}, [''], ['  '], [1], 5):
        with pytest.raises(proc.ProcessingContractError) as exc:
            make(failure_flags=bad)
        err(exc, 'wrong_type', 'failure_flags')


@pytest.mark.parametrize('kind', KINDS)
def test_clip_analysis_has_no_safety_state(kind: str) -> None:
    r = make(analysis_kind=kind, input_ref=clip_ref('clip-video-1'))
    assert not [n for n in dir(r) if 'safety' in n.lower()]
    assert not [f.name for f in dataclasses.fields(ma.AnalysisResult) if 'safety' in f.name.lower()]
    with pytest.raises(TypeError):
        ma.AnalysisResult(**analysis_kwargs(analysis_kind=kind), safety_state='safe')
    h = ma.AnalysisHistory().append(r)
    assert not [n for n in dir(h) if 'safety' in n.lower()]
    assert not [n for n in dir(h.entries[0]) if 'safety' in n.lower()]


def test_append_first_result_creates_revision_one() -> None:
    empty = ma.AnalysisHistory()
    assert empty.entries == ()
    r = make()
    h1 = empty.append(r)
    assert empty.entries == ()
    assert h1.entries == (ma.AnalysisRevision(1, r),)
    assert h1.get('an-1') == ma.AnalysisRevision(1, r)
    assert h1.get('missing') is None


def test_same_input_model_version_spec_returns_old_history() -> None:
    h1 = ma.AnalysisHistory().append(make())
    dup = make(analysis_id='an-2', confidence=0.1, coverage=0.9, failure_flags=['late'])
    h2 = h1.append(dup)
    assert h2 is h1
    assert len(h2.entries) == 1
    assert h2.entries[0].result.confidence == 0.8
    assert h2.get('an-2') is None
    assert h1.append(make()) is h1


@pytest.mark.parametrize(
    'over',
    ({'model': 'whisper-other'}, {'model_version': '2.0'}, {'spec_revision': 'spec-2'}),
)
def test_new_model_version_or_spec_adds_revision_and_keeps_old(over: dict) -> None:
    h1 = ma.AnalysisHistory().append(make())
    old = h1.entries[0]
    h2 = h1.append(make(analysis_id='an-2', **over))
    assert len(h1.entries) == 1 and h1.entries[0] is old
    assert len(h2.entries) == 2
    assert h2.entries[0] is old
    assert h2.entries[1].revision == 2
    assert h2.entries[1].result.analysis_id == 'an-2'
    assert h2.get('an-1') is old
    assert h2.get('an-1').result.model == 'whisper-fake'
    assert h2.revisions(clip_ref(), 'transcript_ocr') == h2.entries


def test_history_never_shrinks_and_keeps_prefix() -> None:
    sequence = [
        make(analysis_id='an-1'),
        make(analysis_id='an-2', model='m2'),
        make(analysis_id='an-3'),
        make(analysis_id='an-4', model='m2', model_version='9'),
        make(analysis_id='an-5', model='m2'),
        make(analysis_id='an-6', spec_revision='spec-2'),
    ]
    history = ma.AnalysisHistory()
    for result in sequence:
        before = history.entries
        history = history.append(result)
        assert len(history.entries) >= len(before)
        assert history.entries[:len(before)] == before
    assert [e.result.analysis_id for e in history.entries] == ['an-1', 'an-2', 'an-4', 'an-6']
    assert [e.revision for e in history.entries] == [1, 2, 3, 4]


def test_revisions_are_isolated_per_input_hash_and_kind() -> None:
    h = ma.AnalysisHistory()
    h = h.append(make(analysis_id='an-1'))
    h = h.append(make(analysis_id='an-2', model='m2'))
    h = h.append(make(analysis_id='an-3', input_ref=clip_ref('clip-1', 'b')))
    h = h.append(make(analysis_id='an-4', analysis_kind='semantic_tags'))
    h = h.append(make(analysis_id='an-5', input_ref=clip_ref('clip-2')))
    assert [e.revision for e in h.entries] == [1, 2, 1, 1, 1]
    assert [e.result.analysis_id for e in h.revisions(clip_ref(), 'transcript_ocr')] == ['an-1', 'an-2']
    other = h.revisions(clip_ref('clip-1', 'b'), ma.AnalysisKind.TRANSCRIPT_OCR)
    assert [e.result.analysis_id for e in other] == ['an-3']
    assert h.revisions(clip_ref('clip-9'), 'transcript_ocr') == ()
    with pytest.raises(proc.ProcessingContractError) as exc:
        h.revisions(clip_ref(), 'image_safety')
    err(exc, 'enum_violation', 'analysis_kind')


def test_returning_to_earlier_model_does_not_create_duplicate() -> None:
    h = ma.AnalysisHistory().append(make(analysis_id='an-1'))
    h = h.append(make(analysis_id='an-2', model='m2'))
    assert h.append(make(analysis_id='an-3')) is h
    assert len(h.entries) == 2


def test_analysis_id_reuse_is_rejected_without_overwrite() -> None:
    h = ma.AnalysisHistory().append(make(analysis_id='an-1'))
    with pytest.raises(proc.ProcessingContractError) as exc:
        h.append(make(analysis_id='an-1', model='m2'))
    err(exc, 'constraint_violation', 'analysis_id')
    assert len(h.entries) == 1 and h.entries[0].result.model == 'whisper-fake'


def test_append_rejects_non_result() -> None:
    h = ma.AnalysisHistory()
    for bad in (None, analysis_kwargs(), 'an-1'):
        with pytest.raises(proc.ProcessingContractError) as exc:
            h.append(bad)
        err(exc, 'wrong_type', 'result')


def test_revision_and_history_constructor_validation() -> None:
    r = make()
    r2 = make(analysis_id='an-2')
    with pytest.raises(proc.ProcessingContractError) as exc:
        ma.AnalysisRevision(0, r)
    err(exc, 'constraint_violation', 'revision')
    for bad in (True, '1', 1.0):
        with pytest.raises(proc.ProcessingContractError) as exc:
            ma.AnalysisRevision(bad, r)  # type: ignore[arg-type]
        err(exc, 'wrong_type', 'revision')
    with pytest.raises(proc.ProcessingContractError) as exc:
        ma.AnalysisRevision(1, 'x')  # type: ignore[arg-type]
    err(exc, 'wrong_type', 'result')
    cases = (
        ([ma.AnalysisRevision(2, r)], 'constraint_violation', 'revision'),
        ([ma.AnalysisRevision(1, r), ma.AnalysisRevision(2, r)], 'constraint_violation', 'analysis_id'),
        ([ma.AnalysisRevision(1, r), ma.AnalysisRevision(2, r2)], 'constraint_violation', 'entries'),
        (['x'], 'wrong_type', 'entries'),
        ('abc', 'wrong_type', 'entries'),
        (5, 'wrong_type', 'entries'),
    )
    for entries, code, field in cases:
        with pytest.raises(proc.ProcessingContractError) as exc:
            ma.AnalysisHistory(entries=entries)  # type: ignore[arg-type]
        err(exc, code, field)
    ok = ma.AnalysisHistory(entries=[ma.AnalysisRevision(1, r)])  # type: ignore[arg-type]
    assert isinstance(ok.entries, tuple)


def test_history_is_immutable() -> None:
    h = ma.AnalysisHistory().append(make())
    with pytest.raises(dataclasses.FrozenInstanceError):
        h.entries = ()  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        h.entries[0].revision = 9  # type: ignore[misc]
    with pytest.raises(AttributeError):
        h.entries.append(h.entries[0])  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        h.entries[0] = h.entries[0]  # type: ignore[index]


def test_public_api_has_no_edit_or_delete() -> None:
    history_api = {n for n in vars(ma.AnalysisHistory) if not n.startswith('_')}
    assert history_api == {'entries', 'append', 'revisions', 'get'}
    assert {n for n in vars(ma.AnalysisResult) if not n.startswith('_')} == {'from_mapping'}
    assert {n for n in vars(ma.AnalysisRevision) if not n.startswith('_')} == set()


def test_module_source_has_no_mutation_safety_or_io() -> None:
    source = pathlib.Path(ma.__file__).read_text(encoding='utf-8')
    tree = ast.parse(source, filename=ma.__file__)
    forbidden = re.compile(r'delete|remove|cleanup|clean_up|purge|unlink|rmtree|evict|overwrite|update|discard|truncate', re.I)
    allowed_imports = {'__future__', 'collections.abc', 'dataclasses', 'enum', 'math', 'voice.domain.processing'}
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in allowed_imports, f'Forbidden import: {alias.name}'
        elif isinstance(node, ast.ImportFrom):
            assert node.module in allowed_imports, f'Forbidden import from: {node.module}'
    for name in names:
        assert not forbidden.search(name), f'Forbidden symbol name: {name}'
    assert 'safety' not in source.lower()
