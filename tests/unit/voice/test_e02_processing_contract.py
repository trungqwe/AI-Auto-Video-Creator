"""E-02: processing request/result contract and ready condition (CT-PROC-001/002/008).

coveredIds: CT-PROC-001, CT-PROC-002, CT-PROC-008, TST-INT-INV-008 (domain level)
"""
import ast
import dataclasses
import re
import enum
import json
import pathlib
import pytest

from controlplane.application.idempotency import canonicalization as canon
from voice.domain import processing as proc

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'contracts' / 'i-artifact-version' / 'payloads.json').read_text(encoding='utf-8'))


def sha(ch: str) -> str:
    return ch * 64


def ref(name: str, ch: str) -> proc.ArtifactRef:
    return proc.ArtifactRef(name, sha(ch))


def request_kwargs() -> dict:
    return {
        'input_artifact_refs': [ref('in-1', 'a'), ref('in-2', 'b')],
        'execution_grant': {'grant_id': 'g-1'},
        'expected_output_profile': {'codec': 'h264', 'width': 1080},
        'resource_limits': {'cpu': 1},
        'output_storage_intent': 'staging',
        'processing_operation_id': 'op-1',
        'stage_run_id': 'run-1',
        'operation_spec_revision': 'spec-1',
    }


def result_kwargs(**over) -> dict:
    base = {
        'disposition': 'succeeded',
        'output_artifact_refs': [ref('out-1', 'c')],
        'processor_identity': {'tool': 'fake', 'version': '1'},
        'input_fingerprint': sha('d'),
        'output_hashes': [sha('c')],
        'technical_report': {},
        'warnings': [],
        'operation_receipt_ref': 'rcpt-1',
    }
    base.update(over)
    return base


def test_enums_are_strenum() -> None:
    assert issubclass(proc.Disposition, enum.StrEnum)
    assert issubclass(proc.OutputClass, enum.StrEnum)
    assert {e.value for e in proc.Disposition} == {'succeeded', 'failed', 'waiting', 'outcome_unknown'}
    assert {e.value for e in proc.OutputClass} == {'reusable', 'per_video', 'diagnostic'}


def test_request_and_result_field_constants() -> None:
    expected_request_fields = (
        'processing_operation_id',
        'stage_run_id',
        'execution_grant',
        'input_artifact_refs',
        'operation_spec_revision',
        'expected_output_profile',
        'resource_limits',
        'output_storage_intent',
    )
    expected_result_fields = (
        'disposition',
        'output_artifact_refs',
        'processor_identity',
        'input_fingerprint',
        'output_hashes',
        'technical_report',
        'warnings',
        'operation_receipt_ref',
    )
    assert proc.REQUEST_FIELDS == expected_request_fields
    assert proc.RESULT_FIELDS == expected_result_fields
    assert tuple(f.name for f in dataclasses.fields(proc.ProcessingRequest)) == expected_request_fields
    assert tuple(f.name for f in dataclasses.fields(proc.ProcessingResult)) == expected_result_fields


def test_input_fingerprint_uses_controlplane_request_hash() -> None:
    assert proc.request_hash is canon.request_hash
    kw = request_kwargs()
    refs = kw['input_artifact_refs']
    profile = kw['expected_output_profile']
    computed = proc.compute_input_fingerprint(refs, 'spec-1', profile)
    expected = canon.request_hash({
        'input_artifact_refs': [
            {'ref': 'in-1', 'content_sha256': sha('a')},
            {'ref': 'in-2', 'content_sha256': sha('b')},
        ],
        'operation_spec_revision': 'spec-1',
        'expected_output_profile': profile,
    })
    assert computed == expected
    assert proc.ProcessingRequest(**kw).input_fingerprint == expected


def test_input_fingerprint_ignores_dict_key_order() -> None:
    kw = request_kwargs()
    refs = kw['input_artifact_refs']
    p1 = {'codec': 'h264', 'width': 1080, 'nested': {'x': 1, 'y': 2}}
    p2 = {'nested': {'y': 2, 'x': 1}, 'width': 1080, 'codec': 'h264'}
    fp1 = proc.compute_input_fingerprint(refs, 'spec-1', p1)
    fp2 = proc.compute_input_fingerprint(refs, 'spec-1', p2)
    assert fp1 == fp2


def test_input_fingerprint_changes_with_one_hash_or_revision() -> None:
    kw = request_kwargs()
    refs = kw['input_artifact_refs']
    profile = kw['expected_output_profile']
    base_fp = proc.compute_input_fingerprint(refs, 'spec-1', profile)
    altered_refs = [proc.ArtifactRef('in-1', 'f' + 'a' * 63), refs[1]]
    fp_alt_ref = proc.compute_input_fingerprint(altered_refs, 'spec-1', profile)
    assert fp_alt_ref != base_fp
    fp_alt_rev = proc.compute_input_fingerprint(refs, 'spec-2', profile)
    assert fp_alt_rev != base_fp

def test_artifact_ref_accepts_lowercase_sha256_from_fixture() -> None:
    valid = FIXTURE['entities']['DeclareArtifactVersionRequest']['valid'][0]['content_sha256']
    ref_obj = proc.ArtifactRef('r1', valid)
    assert ref_obj.ref == 'r1'
    assert ref_obj.content_sha256 == valid


def test_artifact_ref_rejects_uppercase_sha256_from_fixture() -> None:
    invalid_case = next(
        c for c in FIXTURE['entities']['DeclareArtifactVersionRequest']['invalid']
        if c.get('case') == 'content_hash_uppercase'
    )
    bad_sha = invalid_case['payload']['content_sha256']
    expected_error = invalid_case['expected_error']
    with pytest.raises(proc.ProcessingContractError) as exc_info:
        proc.ArtifactRef('r1', bad_sha)
    assert exc_info.value.code == expected_error['code']
    assert exc_info.value.field == expected_error['field']


@pytest.mark.parametrize(
    ('bad_val', 'expected_code'),
    [
        ('a' * 63, 'wrong_type'),
        ('a' * 65, 'wrong_type'),
        ('g' * 64, 'wrong_type'),
        (' ' + 'a' * 63, 'wrong_type'),
        (123, 'wrong_type'),
        (None, 'missing_required'),
    ],
)
def test_artifact_ref_rejects_bad_sha256(bad_val: object, expected_code: str) -> None:
    with pytest.raises(proc.ProcessingContractError) as exc_info:
        proc.ArtifactRef('r1', bad_val)  # type: ignore[arg-type]
    assert exc_info.value.code == expected_code
    assert exc_info.value.field == 'content_sha256'


@pytest.mark.parametrize('field_name', proc.REQUEST_FIELDS)
def test_request_missing_field_from_mapping(field_name: str) -> None:
    payload = request_kwargs()
    del payload[field_name]
    with pytest.raises(proc.ProcessingContractError) as exc_info:
        proc.ProcessingRequest.from_mapping(payload)
    assert exc_info.value.code == 'missing_required'
    assert exc_info.value.field == field_name


@pytest.mark.parametrize('field_name', proc.REQUEST_FIELDS)
def test_request_none_field_in_constructor(field_name: str) -> None:
    kw = request_kwargs()
    kw[field_name] = None
    with pytest.raises(proc.ProcessingContractError) as exc_info:
        proc.ProcessingRequest(**kw)
    assert exc_info.value.code == 'missing_required'
    assert exc_info.value.field == field_name


@pytest.mark.parametrize('field_name', proc.RESULT_FIELDS)
def test_result_missing_field_from_mapping(field_name: str) -> None:
    payload = result_kwargs()
    del payload[field_name]
    with pytest.raises(proc.ProcessingContractError) as exc_info:
        proc.ProcessingResult.from_mapping(payload)
    assert exc_info.value.code == 'missing_required'
    assert exc_info.value.field == field_name


@pytest.mark.parametrize('field_name', proc.RESULT_FIELDS)
def test_result_none_field_in_constructor(field_name: str) -> None:
    kw = result_kwargs()
    kw[field_name] = None
    with pytest.raises(proc.ProcessingContractError) as exc_info:
        proc.ProcessingResult(**kw)
    assert exc_info.value.code == 'missing_required'
    assert exc_info.value.field == field_name


def test_processor_identity_rules() -> None:
    kw = result_kwargs(processor_identity={})
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.ProcessingResult(**kw)
    assert exc.value.code == 'missing_required'
    assert exc.value.field == 'processor_identity'

    kw = result_kwargs(processor_identity={'tool': 'fake'})
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.ProcessingResult(**kw)
    assert exc.value.code == 'missing_required'
    assert exc.value.field == 'processor_identity.version'

    kw = result_kwargs(processor_identity={'version': '1'})
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.ProcessingResult(**kw)
    assert exc.value.code == 'missing_required'
    assert exc.value.field == 'processor_identity.tool'

    kw = result_kwargs(processor_identity='fake')
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.ProcessingResult(**kw)
    assert exc.value.code == 'wrong_type'
    assert exc.value.field == 'processor_identity'

    valid_id = {'tool': 'ffmpeg', 'version': '7.1', 'build': 'x'}
    res = proc.ProcessingResult(**result_kwargs(processor_identity=valid_id))
    assert res.processor_identity == valid_id


def test_disposition_coercion_and_enum_violation() -> None:
    res = proc.ProcessingResult(**result_kwargs(disposition='succeeded'))
    assert res.disposition == proc.Disposition.SUCCEEDED
    assert isinstance(res.disposition, proc.Disposition)

    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.ProcessingResult(**result_kwargs(disposition='done'))
    assert exc.value.code == 'enum_violation'
    assert exc.value.field == 'disposition'


def test_models_are_frozen() -> None:
    r = proc.ArtifactRef('r1', sha('a'))
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.ref = 'other'  # type: ignore[misc]

    req = proc.ProcessingRequest(**request_kwargs())
    with pytest.raises(dataclasses.FrozenInstanceError):
        req.stage_run_id = 'run-2'  # type: ignore[misc]
    assert isinstance(req.input_artifact_refs, tuple)

    res = proc.ProcessingResult(**result_kwargs())
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.disposition = proc.Disposition.FAILED  # type: ignore[misc]
    assert isinstance(res.output_artifact_refs, tuple)
    assert isinstance(res.output_hashes, tuple)
    assert isinstance(res.warnings, tuple)

def test_result_cross_field_constraints() -> None:
    kw = result_kwargs(
        output_artifact_refs=[ref('out-1', 'c')],
        output_hashes=[sha('e')],
    )
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.ProcessingResult(**kw)
    assert exc.value.code == 'constraint_violation'
    assert exc.value.field == 'output_hashes'

    kw_empty = result_kwargs(
        output_artifact_refs=[],
        output_hashes=[],
    )
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.ProcessingResult(**kw_empty)
    assert exc.value.code == 'constraint_violation'
    assert exc.value.field == 'output_artifact_refs'

    kw_unknown = result_kwargs(
        disposition='outcome_unknown',
        operation_receipt_ref=None,
    )
    res_unknown = proc.ProcessingResult(**kw_unknown)
    assert res_unknown.operation_receipt_ref is None

    kw_succ_no_rcpt = result_kwargs(
        disposition='succeeded',
        operation_receipt_ref=None,
    )
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.ProcessingResult(**kw_succ_no_rcpt)
    assert exc.value.code == 'missing_required'
    assert exc.value.field == 'operation_receipt_ref'

    upper_sha = 'C' * 64
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.ProcessingResult(**result_kwargs(
            output_artifact_refs=[{'ref': 'out-1', 'content_sha256': upper_sha}],
            output_hashes=[upper_sha],
        ))
    assert exc.value.code == 'wrong_type'
    assert exc.value.field == 'content_sha256'


def test_validate_result_for_request() -> None:
    req = proc.ProcessingRequest(**request_kwargs())
    res = proc.ProcessingResult(**result_kwargs(input_fingerprint=req.input_fingerprint))
    assert proc.validate_result_for_request(req, res) is None

    res_overlap = proc.ProcessingResult(**result_kwargs(
        input_fingerprint=req.input_fingerprint,
        output_artifact_refs=[ref('in-1', 'c')],
        output_hashes=[sha('c')],
    ))
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.validate_result_for_request(req, res_overlap)
    assert exc.value.code == 'constraint_violation'
    assert exc.value.field == 'output_artifact_refs'

    res_diff_fp = proc.ProcessingResult(**result_kwargs(
        input_fingerprint=sha('e'),
        output_artifact_refs=[ref('out-1', 'c')],
        output_hashes=[sha('c')],
    ))
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.validate_result_for_request(req, res_diff_fp)
    assert exc.value.code == 'constraint_violation'
    assert exc.value.field == 'input_fingerprint'


def test_is_ready_only_when_succeeded_and_all_outputs_verified() -> None:
    res = proc.ProcessingResult(**result_kwargs(
        output_artifact_refs=[ref('out-1', 'c'), ref('out-2', 'd')],
        output_hashes=[sha('c'), sha('d')],
    ))
    assert proc.is_ready(res, {'out-1', 'out-2'}) is True
    assert proc.is_ready(res, frozenset({'out-1', 'out-2'})) is True
    assert proc.is_ready(res, ['out-1', 'out-2']) is True

    assert proc.is_ready(res, {'out-1'}) is False
    assert proc.is_ready(res, set()) is False
    assert proc.is_ready(res, {'out-1', 'out-3'}) is False


@pytest.mark.parametrize('disp', ['waiting', 'failed', 'outcome_unknown'])
def test_non_succeeded_never_ready(disp: str) -> None:
    res = proc.ProcessingResult(**result_kwargs(
        disposition=disp,
        output_artifact_refs=[ref('out-1', 'c')],
        output_hashes=[sha('c')],
        operation_receipt_ref=None,
    ))
    assert proc.is_ready(res, {'out-1'}) is False


def test_is_ready_rejects_bare_string_verified_refs() -> None:
    res = proc.ProcessingResult(**result_kwargs())
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.is_ready(res, 'out-1')
    assert exc.value.code == 'wrong_type'
    assert exc.value.field == 'verified_refs'

    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.is_ready(res, None)
    assert exc.value.code == 'missing_required'
    assert exc.value.field == 'verified_refs'


@pytest.mark.parametrize(
    ('kind', 'expected_class'),
    [
        ('rendition', proc.OutputClass.REUSABLE),
        ('analysis', proc.OutputClass.REUSABLE),
        ('voice', proc.OutputClass.PER_VIDEO),
        ('word_timing', proc.OutputClass.PER_VIDEO),
        ('mix_temp', proc.OutputClass.PER_VIDEO),
        ('frame', proc.OutputClass.DIAGNOSTIC),
        ('log', proc.OutputClass.DIAGNOSTIC),
        ('debug_report', proc.OutputClass.DIAGNOSTIC),
    ],
)
def test_retention_intent_plan_section_7(kind: str, expected_class: proc.OutputClass) -> None:
    assert proc.retention_intent(kind) == expected_class
    assert proc.retention_intent('voice') != proc.OutputClass.REUSABLE


def test_retention_intent_invalid_kind() -> None:
    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.retention_intent('unknown_kind')
    assert exc.value.code == 'constraint_violation'
    assert exc.value.field == 'output_kind'

    with pytest.raises(proc.ProcessingContractError) as exc:
        proc.retention_intent(5)
    assert exc.value.code == 'wrong_type'
    assert exc.value.field == 'output_kind'


def test_module_has_no_delete_or_cleanup() -> None:
    source = pathlib.Path(proc.__file__).read_text(encoding='utf-8')
    tree = ast.parse(source, filename=proc.__file__)
    forbidden_pattern = re.compile(r'delete|remove|cleanup|clean_up|purge|unlink|rmtree|evict', re.I)

    collected_names = set()
    allowed_import_modules = {
        '__future__',
        'dataclasses',
        'enum',
        're',
        'collections.abc',
        'types',
        'typing',
        'controlplane.application.idempotency.canonicalization',
    }

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            collected_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    collected_names.add(target.id)
        elif isinstance(node, ast.Attribute):
            collected_names.add(node.attr)
        elif isinstance(node, ast.Name):
            collected_names.add(node.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in allowed_import_modules, f"Forbidden import: {alias.name}"
                assert alias.name not in {'os', 'shutil', 'pathlib', 'subprocess', 'socket'}
        elif isinstance(node, ast.ImportFrom):
            assert node.module in allowed_import_modules, f"Forbidden import from: {node.module}"
            assert node.module not in {'os', 'shutil', 'pathlib', 'subprocess', 'socket'}

    for name in collected_names:
        assert not forbidden_pattern.search(name), f"Forbidden symbol or attribute name found: {name}"