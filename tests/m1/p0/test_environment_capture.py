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


def load_bootstrap() -> dict[str, object]:
    return json.loads(BOOTSTRAP_PATH.read_text(encoding="utf-8"))


def write_fixture(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_capture_rejects_observed_version_mismatch(tmp_path: Path) -> None:
    payload = copy.deepcopy(load_bootstrap())
    payload["python"]["observed"] = "3.13.14"
    fixture_path = tmp_path / "bootstrap.json"
    output_path = tmp_path / "environment.json"
    write_fixture(fixture_path, payload)

    with pytest.raises(ValueError, match="python.*version"):
        environment.capture_environment(fixture_path, output_path)

    assert not output_path.exists()


def test_capture_rejects_secret_like_keys(tmp_path: Path) -> None:
    payload = copy.deepcopy(load_bootstrap())
    secret_key = "refresh" + "_token"
    payload["postgresql"][secret_key] = "M1_CANARY_VALUE"
    fixture_path = tmp_path / "bootstrap.json"
    output_path = tmp_path / "environment.json"
    write_fixture(fixture_path, payload)

    with pytest.raises(ValueError, match="forbidden sensitive key"):
        environment.capture_environment(fixture_path, output_path)

    assert not output_path.exists()
