"""Capture the approved M1 bootstrap record as immutable environment evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


CAPTURED_SECTIONS = ("python", "uv", "project", "postgresql")
EXPECTED_VERSIONS = {
    "python": "3.13.15",
    "uv": "0.12.13",
    "postgresql": "18.6",
}
FORBIDDEN_KEY_PARTS = ("authorization", "credential", "password", "secret", "token")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _find_forbidden_key(value: object, path: str = "$") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).casefold()
            if any(part in normalized_key for part in FORBIDDEN_KEY_PARTS):
                return f"{path}.{key}"
            found = _find_forbidden_key(child, f"{path}.{key}")
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_forbidden_key(child, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def validate_bootstrap(bootstrap: dict[str, object]) -> None:
    forbidden_path = _find_forbidden_key(bootstrap)
    if forbidden_path is not None:
        raise ValueError(f"forbidden sensitive key at {forbidden_path}")

    for section, expected_version in EXPECTED_VERSIONS.items():
        section_value = bootstrap.get(section)
        if not isinstance(section_value, dict):
            raise ValueError(f"missing {section} section")
        if section_value.get("requested") != expected_version:
            raise ValueError(f"{section} requested version mismatch")
        if section_value.get("observed") != expected_version:
            raise ValueError(f"{section} observed version mismatch")

    project = bootstrap.get("project")
    if not isinstance(project, dict) or project.get("frozen_sync") is not True:
        raise ValueError("project was not synchronized in frozen mode")


def capture_environment(bootstrap_path: Path, output_path: Path) -> dict[str, object]:
    bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
    validate_bootstrap(bootstrap)
    environment: dict[str, object] = {
        "schema_version": "1.0",
        "milestone": "M1",
        "package": "M1-P0",
        "record_kind": "captured_environment",
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "source_bootstrap_sha256": sha256_file(bootstrap_path),
    }
    for section in CAPTURED_SECTIONS:
        environment[section] = bootstrap[section]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(environment, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, output_path)
    return environment


def validate_environment_manifest(
    bootstrap_path: Path, environment_path: Path
) -> dict[str, object]:
    bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
    validate_bootstrap(bootstrap)
    environment = json.loads(environment_path.read_text(encoding="utf-8"))

    forbidden_path = _find_forbidden_key(environment)
    if forbidden_path is not None:
        raise ValueError(f"forbidden sensitive key at {forbidden_path}")
    if environment.get("source_bootstrap_sha256") != sha256_file(bootstrap_path):
        raise ValueError("bootstrap hash mismatch")
    if environment.get("schema_version") != "1.0":
        raise ValueError("environment schema version mismatch")
    if environment.get("record_kind") != "captured_environment":
        raise ValueError("environment record kind mismatch")

    for section in CAPTURED_SECTIONS:
        if environment.get(section) != bootstrap.get(section):
            raise ValueError(f"{section} section mismatch")
    return environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bootstrap", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    capture_environment(arguments.bootstrap, arguments.output)


if __name__ == "__main__":
    main()
