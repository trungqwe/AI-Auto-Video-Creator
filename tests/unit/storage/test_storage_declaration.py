"""I-01: validator DeclareArtifactVersionRequest/Result bám BINDING-I-ARTIFACT-VERSION 1.0.0 (CT-STO-001)."""
import copy
import dataclasses
import json
import pathlib
import pytest
from controlplane.domain.storage_meta.declaration import (
    BINDING_VERSION,
    DeclareArtifactVersionRequest,
    DeclareArtifactVersionResult,
    validate_declare_request,
    validate_declare_result,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / "docs" / "parallel-delivery" / "bindings" / "i-artifact-version.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "contracts" / "i-artifact-version" / "payloads.json"
REQUEST = "DeclareArtifactVersionRequest"
RESULT = "DeclareArtifactVersionResult"
ENTITIES = (REQUEST, RESULT)
CLASSES = {REQUEST: DeclareArtifactVersionRequest, RESULT: DeclareArtifactVersionResult}
VALIDATORS = {REQUEST: validate_declare_request, RESULT: validate_declare_result}
PY_TYPES = {"string": str, "sha256": str, "integer": int, "boolean": bool, "array": list}
REQUEST_NAMES = (
    "artifact_kind",
    "owner_resource_ref",
    "content_sha256",
    "size_bytes",
    "media_type",
    "lineage_refs",
    "retention_class",
    "sensitivity_class",
    "intended_storage_class",
    "producer_operation_ref",
)
RESULT_NAMES = (
    "artifact_id",
    "artifact_version_id",
    "matched_existing",
    "policy_decision",
    "required_operation",
)


def _binding_fields(entity: str) -> list[dict]:
    data = json.loads(BINDING_PATH.read_text(encoding="utf-8"))
    for item in data["entities"]:
        if item["name"] == entity:
            return list(item["fields"])
    raise ValueError(f"Unknown entity {entity}")


def _fixture(entity: str) -> dict:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["entities"][entity]


def _valid(entity: str) -> dict:
    return copy.deepcopy(_fixture(entity)["valid"][0])


def _invalid_cases(entity: str) -> list[dict]:
    return list(_fixture(entity)["invalid"])


def test_binding_version_constant() -> None:
    binding_data = json.loads(BINDING_PATH.read_text(encoding="utf-8"))
    assert BINDING_VERSION == binding_data["binding_version"] == "1.0.0"


@pytest.mark.parametrize("entity", ENTITIES)
def test_dataclass_fields_match_binding(entity: str) -> None:
    expected_names = REQUEST_NAMES if entity == REQUEST else RESULT_NAMES
    binding_fields = _binding_fields(entity)
    actual_fields = dataclasses.fields(CLASSES[entity])

    assert [f.name for f in actual_fields] == list(expected_names) == [f["name"] for f in binding_fields]

    fields_map = {f.name: f for f in actual_fields}
    for bf in binding_fields:
        name = bf["name"]
        req = bf["required"]
        btype = bf["type"]
        df = fields_map[name]
        is_required = df.default is dataclasses.MISSING and df.default_factory is dataclasses.MISSING
        assert is_required == req
        expected_type = PY_TYPES[btype] if req else (PY_TYPES[btype] | None)
        assert df.type == expected_type


@pytest.mark.parametrize("entity", ENTITIES)
def test_dataclass_is_frozen(entity: str) -> None:
    instance = CLASSES[entity](**_valid(entity))
    first_field = dataclasses.fields(CLASSES[entity])[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, first_field, "mutated_value")


@pytest.mark.parametrize("entity", ENTITIES)
def test_valid_fixture_payloads_have_no_errors(entity: str) -> None:
    for payload in _fixture(entity)["valid"]:
        assert VALIDATORS[entity](payload) == []


_ALL_INVALID_CASES = [
    (e, case)
    for e in ENTITIES
    for case in _invalid_cases(e)
]


@pytest.mark.parametrize("entity,case", _ALL_INVALID_CASES, ids=[c["case"] for _, c in _ALL_INVALID_CASES])
def test_invalid_fixture_cases_return_expected_error(entity: str, case: dict) -> None:
    assert VALIDATORS[entity](case["payload"]) == [case["expected_error"]]


WRONG_VALUES = {"string": 123, "sha256": 123, "integer": "1024", "boolean": "yes", "array": "not-a-list"}


@pytest.mark.parametrize("entity", ENTITIES)
def test_unknown_fields_are_ignored(entity: str) -> None:
    payload = _valid(entity)
    payload["future_field"] = 1
    payload["sha256_hash"] = "x"
    assert VALIDATORS[entity](payload) == []


@pytest.mark.parametrize("value", [True, False])
def test_size_bytes_bool_is_wrong_type(value: bool) -> None:
    payload = _valid(REQUEST)
    payload["size_bytes"] = value
    assert VALIDATORS[REQUEST](payload) == [{"code": "wrong_type", "field": "size_bytes"}]


@pytest.mark.parametrize("value", [0, 1])
def test_matched_existing_integer_is_wrong_type(value: int) -> None:
    payload = _valid(RESULT)
    payload["matched_existing"] = value
    assert VALIDATORS[RESULT](payload) == [{"code": "wrong_type", "field": "matched_existing"}]


_ALL_REQUIRED_FIELDS = [
    (e, f["name"])
    for e in ENTITIES
    for f in _binding_fields(e)
    if f["required"]
]


@pytest.mark.parametrize(
    "entity,field_name",
    _ALL_REQUIRED_FIELDS,
    ids=[f"{e}-{f}" for e, f in _ALL_REQUIRED_FIELDS],
)
def test_missing_each_field(entity: str, field_name: str) -> None:
    payload = _valid(entity)
    payload.pop(field_name, None)
    assert VALIDATORS[entity](payload) == [{"code": "missing_required", "field": field_name}]


_ALL_FIELDS_WITH_TYPE = [
    (e, f["name"], f["type"])
    for e in ENTITIES
    for f in _binding_fields(e)
]


@pytest.mark.parametrize(
    "entity,field_name,binding_type",
    _ALL_FIELDS_WITH_TYPE,
    ids=[f"{e}-{f}" for e, f, _ in _ALL_FIELDS_WITH_TYPE],
)
def test_wrong_type_each_field(entity: str, field_name: str, binding_type: str) -> None:
    payload = _valid(entity)
    payload[field_name] = WRONG_VALUES[binding_type]
    assert VALIDATORS[entity](payload) == [{"code": "wrong_type", "field": field_name}]


_VALID_HASH = _valid(REQUEST)["content_sha256"]
_INVALID_HASHES = [
    _VALID_HASH.upper(),
    _VALID_HASH[:63],
    _VALID_HASH + "0",
    "g" * 64,
    _VALID_HASH + "\n",
    " " + _VALID_HASH[1:],
    "",
]


@pytest.mark.parametrize("bad_hash", _INVALID_HASHES)
def test_sha256_must_be_64_lowercase_hex(bad_hash: str) -> None:
    payload = _valid(REQUEST)
    payload["content_sha256"] = bad_hash
    assert VALIDATORS[REQUEST](payload) == [{"code": "wrong_type", "field": "content_sha256"}]


def test_renamed_sha256_field_is_not_accepted() -> None:
    payload = _valid(REQUEST)
    hash_val = payload.pop("content_sha256")
    payload["sha256_hash"] = hash_val
    assert VALIDATORS[REQUEST](payload) == [{"code": "missing_required", "field": "content_sha256"}]


@pytest.mark.parametrize("entity", ENTITIES)
def test_empty_payload_reports_all_required_fields_in_binding_order(entity: str) -> None:
    expected_fields = [f["name"] for f in _binding_fields(entity) if f["required"]]
    expected = [{"code": "missing_required", "field": n} for n in expected_fields]
    assert VALIDATORS[entity]({}) == expected


def test_required_operation_is_optional() -> None:
    payload = _valid(RESULT)
    payload.pop("required_operation", None)
    assert VALIDATORS[RESULT](payload) == []
    payload["required_operation"] = None
    assert VALIDATORS[RESULT](payload) == [{"code": "wrong_type", "field": "required_operation"}]


@pytest.mark.parametrize("entity", ENTITIES)
@pytest.mark.parametrize("bad_payload", [None, [], "x", 5])
def test_non_dict_payload_is_wrong_type(entity: str, bad_payload: object) -> None:
    assert VALIDATORS[entity](bad_payload) == [{"code": "wrong_type", "field": "payload"}]


def test_validator_does_not_mutate_payload_and_returns_plain_dicts() -> None:
    payload = _valid(REQUEST)
    payload.pop("retention_class", None)
    payload["size_bytes"] = True
    payload_copy = copy.deepcopy(payload)
    errors = VALIDATORS[REQUEST](payload)
    assert payload == payload_copy
    assert len(errors) > 0
    for e in errors:
        assert type(e) is dict
        assert set(e.keys()) == {"code", "field"}
