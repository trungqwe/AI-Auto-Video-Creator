"""I-02: DeclareArtifactVersionService bảo đảm version bất biến (CT-STO-001, ADR-0006)."""
import copy
import dataclasses
import itertools
import json
import pathlib
import pytest
from controlplane.application.storage_meta.declare_version import (
    ArtifactVersionCatalogPort,
    ArtifactVersionRef,
    DeclareArtifactVersionService,
    DeclareRequestInvalidError,
)
from controlplane.domain.storage_meta.declaration import DeclareArtifactVersionResult, validate_declare_result

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "contracts" / "i-artifact-version" / "payloads.json"
REQUEST = "DeclareArtifactVersionRequest"
OTHER_HASH = "f" * 64


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["entities"][REQUEST]


def _valid() -> dict:
    return copy.deepcopy(_fixture()["valid"][0])


def _result_payload(result: DeclareArtifactVersionResult) -> dict:
    return {k: v for k, v in dataclasses.asdict(result).items() if v is not None}


class FakeCatalog:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.calls: list[str] = []

    def find_matching(self, owner_resource_ref: str, artifact_kind: str, content_sha256: str) -> ArtifactVersionRef | None:
        self.calls.append("find_matching")
        for row in self.rows:
            if (row["owner_resource_ref"], row["artifact_kind"], row["content_sha256"]) == (owner_resource_ref, artifact_kind, content_sha256):
                return ArtifactVersionRef(row["artifact_id"], row["artifact_version_id"])
        return None

    def find_artifact_id(self, owner_resource_ref: str, artifact_kind: str) -> str | None:
        self.calls.append("find_artifact_id")
        for row in self.rows:
            if (row["owner_resource_ref"], row["artifact_kind"]) == (owner_resource_ref, artifact_kind):
                return row["artifact_id"]
        return None

    def insert_version(self, artifact_id: str, artifact_version_id: str, request: object) -> None:
        self.calls.append("insert_version")
        key = (request.owner_resource_ref, request.artifact_kind, request.content_sha256)
        duplicate = any((r["owner_resource_ref"], r["artifact_kind"], r["content_sha256"]) == key for r in self.rows)
        assert not duplicate, "version is immutable: duplicate insert"
        self.rows.append({"artifact_id": artifact_id, "artifact_version_id": artifact_version_id, **dataclasses.asdict(request)})


def _service(catalog: FakeCatalog) -> DeclareArtifactVersionService:
    counter = itertools.count(1)
    return DeclareArtifactVersionService(catalog, id_factory=lambda: f"id-{next(counter)}")


def test_first_declare_creates_new_artifact_and_version() -> None:
    catalog = FakeCatalog()
    result = _service(catalog).declare(_valid())
    assert result == DeclareArtifactVersionResult("id-1", "id-2", False, "new_version", "upload")
    assert type(result.matched_existing) is bool
    assert validate_declare_result(_result_payload(result)) == []
    assert len(catalog.rows) == 1


def test_same_bytes_twice_keeps_one_version() -> None:
    catalog = FakeCatalog()
    service = _service(catalog)
    first = service.declare(_valid())
    second = service.declare(_valid())
    assert len(catalog.rows) == 1
    assert catalog.calls.count("insert_version") == 1
    assert second == DeclareArtifactVersionResult(first.artifact_id, first.artifact_version_id, True, "matched_existing")
    assert second.matched_existing is True
    assert second.required_operation is None
    assert validate_declare_result(_result_payload(second)) == []


def test_different_bytes_add_second_version_and_keep_first_unchanged() -> None:
    catalog = FakeCatalog()
    service = _service(catalog)
    first = service.declare(_valid())
    before = copy.deepcopy(catalog.rows[0])
    payload = _valid()
    payload["content_sha256"] = OTHER_HASH
    second = service.declare(payload)
    assert len(catalog.rows) == 2
    assert catalog.rows[0] == before
    assert second.artifact_id == first.artifact_id
    assert second.artifact_version_id != first.artifact_version_id
    assert (second.matched_existing, second.policy_decision, second.required_operation) == (False, "new_version", "upload")
    assert validate_declare_result(_result_payload(second)) == []
    assert service.declare(_valid()).artifact_version_id == first.artifact_version_id
    assert len(catalog.rows) == 2


@pytest.mark.parametrize("field,value", [("owner_resource_ref", "00000000-0000-4000-8000-0000000000aa"), ("artifact_kind", "video")])
def test_other_owner_or_kind_gets_new_artifact_id(field: str, value: str) -> None:
    catalog = FakeCatalog()
    service = _service(catalog)
    first = service.declare(_valid())
    payload = _valid()
    payload[field] = value
    second = service.declare(payload)
    assert second.artifact_id != first.artifact_id
    assert second.policy_decision == "new_version"
    assert len(catalog.rows) == 2


def test_unknown_fields_ignored_and_payload_not_mutated() -> None:
    catalog = FakeCatalog()
    payload = _valid()
    payload["future_field"] = 1
    snapshot = copy.deepcopy(payload)
    _service(catalog).declare(payload)
    assert payload == snapshot
    assert "future_field" not in catalog.rows[0]


@pytest.mark.parametrize("case", _fixture()["invalid"], ids=lambda c: c["case"])
def test_invalid_fixture_payload_raises_value_error_with_code_and_field(case: dict) -> None:
    catalog = FakeCatalog()
    with pytest.raises(ValueError) as info:
        _service(catalog).declare(case["payload"])
    assert isinstance(info.value, DeclareRequestInvalidError)
    assert {"code": info.value.code, "field": info.value.field} == case["expected_error"]
    assert catalog.calls == []


@pytest.mark.parametrize("field", list(_valid()))
def test_missing_each_field_raises_missing_required(field: str) -> None:
    catalog = FakeCatalog()
    payload = _valid()
    del payload[field]
    with pytest.raises(DeclareRequestInvalidError) as info:
        _service(catalog).declare(payload)
    assert (info.value.code, info.value.field) == ("missing_required", field)
    assert catalog.calls == []


def test_wrong_type_raises_with_field() -> None:
    catalog = FakeCatalog()
    payload = _valid()
    payload["size_bytes"] = True
    with pytest.raises(DeclareRequestInvalidError) as info:
        _service(catalog).declare(payload)
    assert (info.value.code, info.value.field) == ("wrong_type", "size_bytes")
    assert catalog.calls == []


@pytest.mark.parametrize("bad", [None, [], "x", 5])
def test_non_dict_payload_raises_wrong_type_payload(bad: object) -> None:
    catalog = FakeCatalog()
    with pytest.raises(DeclareRequestInvalidError) as info:
        _service(catalog).declare(bad)
    assert (info.value.code, info.value.field) == ("wrong_type", "payload")
    assert catalog.calls == []


def test_port_and_service_expose_no_overwrite_api() -> None:
    names = sorted(n for n in vars(ArtifactVersionCatalogPort) if not n.startswith("_"))
    assert names == ["find_artifact_id", "find_matching", "insert_version"]
    assert not [n for n in dir(DeclareArtifactVersionService) if n.startswith(("update", "overwrite", "replace", "delete"))]
