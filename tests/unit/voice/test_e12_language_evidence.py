"""E-12: LanguageEvidence gắn exact revision (CT-RND-002).

coveredIds: TST-QC-INV-019 (phía E), CT-RND-002 language_validation_refs
"""
import ast
import copy
import dataclasses
import hashlib
import json
import pathlib

import pytest

from controlplane.application.idempotency.canonicalization import request_hash
from voice.domain.language_evidence import (
    LANGUAGE_MISMATCH,
    REVISION_MISMATCH,
    LanguageEvidence,
    LanguageEvidenceRejected,
    LanguageFinding,
    RevisionMismatchError,
    build_language_evidence,
)
from voice.domain.voice_track import INPUT_NOT_READY, VoiceTrack, VoiceTrackValidationError
from voice.domain.word_timing import WordTimingError, validate_word_timing

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
MODULE_SOURCE = ROOT / 'src' / 'voice' / 'domain' / 'language_evidence.py'
OTHER_SHA = 'fedcba9876543210' * 4
LOCALE_REPORT = {'voice_locale_reported': 'en-US'}


def _valid(entity: str) -> dict:
    payload = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][entity]['valid'][0]
    return copy.deepcopy(payload)


def _request(**changes) -> dict:
    return {**_valid('VoiceTrackRequest'), **changes}


def _voice(**changes) -> VoiceTrack:
    return VoiceTrack.from_payload({**_valid('VoiceTrackResult'), **changes})


def _timing(**changes):
    return validate_word_timing({**_valid('WordTiming'), **changes})


def _timing_texts(*texts):
    payload = _valid('WordTiming')
    for word, text in zip(payload['words'], texts):
        if text is None:
            word.pop('text')
        else:
            word['text'] = text
    return validate_word_timing(payload)


def _kwargs(**overrides) -> dict:
    kwargs = {'request': _request(), 'voice_track': _voice(), 'locale_report': dict(LOCALE_REPORT), 'timing': _timing()}
    kwargs.update(overrides)
    return kwargs


def test_valid_inputs_build_frozen_evidence():
    kwargs = _kwargs()
    before = (copy.deepcopy(kwargs['request']), copy.deepcopy(kwargs['locale_report']))
    evidence = build_language_evidence(**kwargs)
    assert isinstance(evidence, LanguageEvidence)
    assert LanguageEvidence.__dataclass_params__.frozen
    assert evidence.script_version_id == '00000000-0000-4000-8000-000000000030'
    assert evidence.script_fingerprint == '0123456789abcdef' * 4
    assert evidence.voice_hash == '0123456789abcdef' * 4
    assert evidence.voice_locale_reported == 'en-US'
    assert evidence.expected_language == 'en'
    assert evidence.timing_artifact_ref == '00000000-0000-4000-8000-000000000036'
    assert evidence.findings == ()
    assert (kwargs['request'], kwargs['locale_report']) == before
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.voice_hash = OTHER_SHA


def test_subtitle_text_hash_is_sha256_of_word_texts_in_order():
    evidence = build_language_evidence(**_kwargs())
    assert evidence.subtitle_text_hash == hashlib.sha256('Breaking news'.encode('utf-8')).hexdigest()
    swapped = build_language_evidence(**_kwargs(timing=_timing_texts('news', 'Breaking')))
    assert swapped.subtitle_text_hash == hashlib.sha256('news Breaking'.encode('utf-8')).hexdigest()
    assert swapped.subtitle_text_hash != evidence.subtitle_text_hash


def test_evidence_ref_is_request_hash_of_bound_fields():
    evidence = build_language_evidence(**_kwargs())
    names = (
        'script_version_id',
        'script_fingerprint',
        'voice_hash',
        'voice_locale_reported',
        'subtitle_text_hash',
        'timing_artifact_ref',
        'expected_language',
    )
    assert evidence.evidence_ref == request_hash({name: getattr(evidence, name) for name in names})
    assert build_language_evidence(**_kwargs()) == evidence


def test_evidence_ref_changes_with_each_bound_field():
    base = build_language_evidence(**_kwargs()).evidence_ref
    renamed = {**_valid('WordTiming'), 'timing_artifact_ref': 'other-timing'}
    variants = [
        _kwargs(locale_report={'voice_locale_reported': 'en-GB'}),
        _kwargs(request=_request(expected_language='en-US')),
        _kwargs(timing=validate_word_timing(renamed)),
        _kwargs(timing=_timing_texts('Alert', 'news')),
        _kwargs(
            request=_request(script_version_id='v2'),
            voice_track=_voice(script_version_id='v2'),
            timing=_timing(script_version_id='v2'),
        ),
        _kwargs(
            request=_request(script_fingerprint=OTHER_SHA),
            voice_track=_voice(script_fingerprint=OTHER_SHA),
            timing=_timing(script_fingerprint=OTHER_SHA),
        ),
        _kwargs(voice_track=_voice(voice_hash=OTHER_SHA), timing=_timing(voice_hash=OTHER_SHA)),
    ]
    refs = {build_language_evidence(**variant).evidence_ref for variant in variants}
    assert len(refs) == len(variants)
    assert base not in refs


@pytest.mark.parametrize(
    ('overrides', 'fields'),
    [
        pytest.param(lambda: {'voice_track': _voice(voice_hash=OTHER_SHA)}, ('voice_hash',), id='voice_differs_from_timing'),
        pytest.param(lambda: {'timing': _timing(voice_hash=OTHER_SHA)}, ('voice_hash',), id='timing_voice_differs'),
        pytest.param(lambda: {'request': _request(script_fingerprint=OTHER_SHA)}, ('script_fingerprint',), id='request_fingerprint_differs'),
        pytest.param(lambda: {'voice_track': _voice(script_fingerprint=OTHER_SHA)}, ('script_fingerprint',), id='voice_fingerprint_differs'),
        pytest.param(lambda: {'timing': _timing(script_fingerprint=OTHER_SHA)}, ('script_fingerprint',), id='timing_fingerprint_differs'),
        pytest.param(lambda: {'timing': _timing(script_version_id='other-version')}, ('script_version_id',), id='script_version_differs'),
        pytest.param(
            lambda: {'voice_track': _voice(script_fingerprint=OTHER_SHA, voice_hash=OTHER_SHA)},
            ('script_fingerprint', 'voice_hash'),
            id='fingerprint_and_voice_differ',
        ),
    ],
)
def test_revision_mismatch_is_raised(overrides, fields):
    with pytest.raises(RevisionMismatchError) as excinfo:
        build_language_evidence(**_kwargs(**overrides()))
    assert REVISION_MISMATCH == 'revision_mismatch'
    assert excinfo.value.code == 'revision_mismatch'
    assert excinfo.value.fields == fields


def test_revision_mismatch_wins_over_locale_mismatch():
    with pytest.raises(RevisionMismatchError):
        build_language_evidence(
            **_kwargs(voice_track=_voice(voice_hash=OTHER_SHA), locale_report={'voice_locale_reported': 'fr-FR'})
        )


@pytest.mark.parametrize(
    ('locale_report', 'reason'),
    [
        (None, 'missing_locale_report'),
        ({}, 'missing_locale_report'),
        ({'locale': 'en'}, 'missing_locale_report'),
        ({'voice_locale_reported': None}, 'missing_locale_report'),
        ({'voice_locale_reported': '  '}, 'missing_locale_report'),
        ('en-US', 'invalid_locale_report'),
        ({'voice_locale_reported': 5}, 'invalid_locale_report'),
    ],
)
def test_missing_or_invalid_locale_report_is_input_not_ready(locale_report, reason):
    with pytest.raises(LanguageEvidenceRejected) as excinfo:
        build_language_evidence(**_kwargs(locale_report=locale_report))
    assert INPUT_NOT_READY == 'INPUT_NOT_READY'
    assert excinfo.value.code == INPUT_NOT_READY
    assert excinfo.value.reason == reason


@pytest.mark.parametrize(
    ('expected', 'reported', 'mismatch'),
    [
        ('en', 'en', False),
        ('en', 'en-US', False),
        ('en', 'EN_us', False),
        ('en-US', 'en-US', False),
        ('en-US', 'en-GB', True),
        ('en-US', 'en', True),
        ('en', 'fr-FR', True),
        ('en', 'english', True),
        ('en', 'eng', True),
    ],
)
def test_locale_is_compared_with_expected_language(expected, reported, mismatch):
    evidence = build_language_evidence(
        **_kwargs(request=_request(expected_language=expected), locale_report={'voice_locale_reported': reported})
    )
    assert evidence.voice_locale_reported == reported
    assert evidence.expected_language == expected
    finding = LanguageFinding(LANGUAGE_MISMATCH, expected, reported)
    assert evidence.findings == ((finding,) if mismatch else ())


def test_locale_mismatch_still_creates_evidence_with_finding():
    evidence = build_language_evidence(**_kwargs(locale_report={'voice_locale_reported': 'fr-FR'}))
    assert LANGUAGE_MISMATCH == 'language_mismatch'
    assert evidence.voice_locale_reported == 'fr-FR'
    assert evidence.voice_locale_reported != evidence.expected_language
    assert [finding.code for finding in evidence.findings] == ['language_mismatch']
    assert len(evidence.evidence_ref) == 64


def test_evidence_never_declares_english_valid():
    names = {field.name for field in dataclasses.fields(LanguageEvidence)}
    assert names == {
        'script_version_id',
        'script_fingerprint',
        'voice_hash',
        'voice_locale_reported',
        'subtitle_text_hash',
        'timing_artifact_ref',
        'expected_language',
        'evidence_ref',
        'findings',
    }
    assert not any('valid' in name for name in names)
    source = MODULE_SOURCE.read_text(encoding='utf-8')
    assert 'ENGLISH_OUTPUT_VALID' not in source
    strings = {
        node.value.casefold()
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not {'en', 'english'} & strings


@pytest.mark.parametrize('texts', [('Breaking', None), ('Breaking', '  ')])
def test_word_without_text_is_input_not_ready(texts):
    with pytest.raises(LanguageEvidenceRejected) as excinfo:
        build_language_evidence(**_kwargs(timing=_timing_texts(*texts)))
    assert excinfo.value.code == INPUT_NOT_READY
    assert excinfo.value.reason == 'missing_word_text'


def test_blank_expected_language_is_input_not_ready():
    with pytest.raises(LanguageEvidenceRejected) as excinfo:
        build_language_evidence(**_kwargs(request=_request(expected_language='  ')))
    assert excinfo.value.code == INPUT_NOT_READY
    assert excinfo.value.reason == 'missing_expected_language'


def test_boundary_errors_and_mapping_inputs():
    broken_request = _valid('VoiceTrackRequest')
    del broken_request['script_fingerprint']
    with pytest.raises(VoiceTrackValidationError):
        build_language_evidence(**_kwargs(request=broken_request))
    broken_voice = _valid('VoiceTrackResult')
    del broken_voice['voice_hash']
    with pytest.raises(VoiceTrackValidationError):
        build_language_evidence(**_kwargs(voice_track=broken_voice))
    broken_timing = _valid('WordTiming')
    broken_timing['words'] = []
    with pytest.raises(WordTimingError):
        build_language_evidence(**_kwargs(timing=broken_timing))
    from_mappings = build_language_evidence(**_kwargs(voice_track=_valid('VoiceTrackResult'), timing=_valid('WordTiming')))
    assert from_mappings == build_language_evidence(**_kwargs())


def test_module_imports_only_allowed_modules():
    imported = set()
    for node in ast.walk(ast.parse(MODULE_SOURCE.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    assert imported <= {
        '__future__',
        'hashlib',
        'collections.abc',
        'dataclasses',
        'controlplane.application.idempotency.canonicalization',
        'voice.domain.voice_track',
        'voice.domain.word_timing',
    }
