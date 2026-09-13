import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[3]
EVIDENCE_DIRECTORY = (
    REPOSITORY_ROOT / "docs" / "milestones" / "m1-proof" / "evidence" / "m1-p0"
)
BOOTSTRAP_PATH = EVIDENCE_DIRECTORY / "bootstrap.json"
ENVIRONMENT_PATH = EVIDENCE_DIRECTORY / "environment.json"


def load_json(path: Path) -> dict[str, object]:
    assert path.is_file(), f"required evidence is missing: {path.relative_to(REPOSITORY_ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_environment_manifest_matches_locked_bootstrap() -> None:
    bootstrap = load_json(BOOTSTRAP_PATH)
    environment = load_json(ENVIRONMENT_PATH)

    assert environment["schema_version"] == "1.0"
    assert environment["record_kind"] == "captured_environment"
    assert environment["source_bootstrap_sha256"]
    assert environment["python"] == bootstrap["python"]
    assert environment["uv"] == bootstrap["uv"]
    assert environment["project"] == bootstrap["project"]


def test_environment_manifest_contains_successful_postgresql_preflight() -> None:
    bootstrap = load_json(BOOTSTRAP_PATH)
    environment = load_json(ENVIRONMENT_PATH)

    assert environment["postgresql"] == bootstrap["postgresql"]
    assert environment["postgresql"]["observed"] == "18.6"
    assert environment["postgresql"]["client_version"] == "3.3.5"
    assert environment["postgresql"]["select_one"] is True
    assert environment["postgresql"]["rollback_absent"] is True
    assert environment["postgresql"]["utf8_round_trip"] is True
