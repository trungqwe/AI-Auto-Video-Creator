import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from m1proof import environment


REPOSITORY_ROOT = Path(__file__).parents[3]
BOOTSTRAP_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "milestones"
    / "m1-proof"
    / "evidence"
    / "m1-p0"
    / "bootstrap.json"
)
ENVIRONMENT_PATH = BOOTSTRAP_PATH.with_name("environment.json")


def require_validator():
    validator = getattr(environment, "validate_environment_manifest", None)
    assert callable(validator), "environment manifest validator is not implemented"
    return validator


def write_fixture(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_validator_accepts_untampered_environment_manifest() -> None:
    validator = require_validator()
    validator(BOOTSTRAP_PATH, ENVIRONMENT_PATH)


def test_validator_rejects_tampered_bootstrap_hash(tmp_path: Path) -> None:
    validator = require_validator()
    payload = json.loads(ENVIRONMENT_PATH.read_text(encoding="utf-8"))
    payload["source_bootstrap_sha256"] = "0" * 64
    fixture_path = tmp_path / "environment.json"
    write_fixture(fixture_path, payload)

    with pytest.raises(ValueError, match="bootstrap hash mismatch"):
        validator(BOOTSTRAP_PATH, fixture_path)


def test_validator_rejects_tampered_locked_section(tmp_path: Path) -> None:
    validator = require_validator()
    payload = copy.deepcopy(json.loads(ENVIRONMENT_PATH.read_text(encoding="utf-8")))
    payload["project"]["uv_lock_sha256"] = "0" * 64
    fixture_path = tmp_path / "environment.json"
    write_fixture(fixture_path, payload)

    with pytest.raises(ValueError, match="uv.lock live hash mismatch"):
        validator(BOOTSTRAP_PATH, fixture_path)
