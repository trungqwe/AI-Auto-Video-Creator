"""Evidence Validator for Milestone M2.

Source of Truth Authority:
- `status.json` with schema `m2_package_status_v1` is the authoritative machine-readable manifest.
- `status.md` is a human-readable derivative, never used as parser source of truth.
- `hashes.sha256` forms an acyclic DAG excluding itself. Self-referential hashes are rejected.
- Fail-closed gate verification: any mismatch, missing file, untracked file, or semantic test failure halts execution.

Two-tier verification:
1. Integrity Tier: Validates JSON schema, file completeness, and SHA-256 DAG hashes.
2. Semantic Tier: Validates actual test metrics from JUnit XML, secret scan results, and capability reports.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from controlplane.infrastructure.evidence.evaluator import (
    SemanticEvaluationError,
    evaluate_package_semantics,
)


EXPECTED_SCHEMA_VERSION = "m2_package_status_v1"
VALID_STATUSES = frozenset({"IN_PROGRESS", "PASS", "FAIL", "READY_FOR_REVIEW"})
VALID_GATE_OUTCOMES = frozenset({"PASS", "FAIL", "BLOCKED"})
HASH_FILENAME = "hashes.sha256"
STATUS_JSON_FILENAME = "status.json"


class EvidenceValidationError(Exception):
    """Raised when evidence verification fails."""
    pass


class SelfReferentialHashError(EvidenceValidationError):
    """Raised when hashes.sha256 contains an entry for itself."""
    pass


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    name: str
    status: str
    evidence_files: list[str]


@dataclass(frozen=True)
class PackageEvidenceReport:
    milestone: str
    package: str
    schema_version: str
    status: str
    gates: list[GateResult]
    verified_files: list[str]
    is_valid: bool
    semantic_summary: dict[str, Any] | None = None


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_hashes_sha256(hash_file_path: Path) -> dict[str, str]:
    """Parse hashes.sha256 into a dict of {rel_path: expected_hash}.

    Enforces that hashes.sha256 MUST NOT contain itself (no self-referential hash).
    """
    if not hash_file_path.is_file():
        raise EvidenceValidationError(f"Hash file missing: {hash_file_path}")

    hashes: dict[str, str] = {}
    lines = hash_file_path.read_text(encoding="utf-8").splitlines()
    for line_idx, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise EvidenceValidationError(
                f"Malformed line {line_idx} in {hash_file_path.name}: '{line}'"
            )
        digest, filename = parts[0], parts[1].lstrip("*").strip()
        if filename == HASH_FILENAME or Path(filename).name == HASH_FILENAME:
            raise SelfReferentialHashError(
                f"Self-referential hash detected on line {line_idx}: '{HASH_FILENAME}' cannot hash itself."
            )
        hashes[filename] = digest.lower()
    return hashes


def validate_status_json(status_path: Path) -> dict[str, Any]:
    """Validate status.json against the m2_package_status_v1 schema."""
    if not status_path.is_file():
        raise EvidenceValidationError(f"Authoritative status.json missing: {status_path}")

    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvidenceValidationError(f"status.json is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise EvidenceValidationError("status.json root must be a JSON object")

    if data.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise EvidenceValidationError(
            f"Invalid schema_version: expected '{EXPECTED_SCHEMA_VERSION}', got '{data.get('schema_version')}'"
        )

    if data.get("milestone") != "M2":
        raise EvidenceValidationError(
            f"Invalid milestone: expected 'M2', got '{data.get('milestone')}'"
        )

    package = data.get("package")
    if not isinstance(package, str) or not package.strip():
        raise EvidenceValidationError("Package identifier must be a non-empty string")

    status = data.get("status")
    if status not in VALID_STATUSES:
        raise EvidenceValidationError(
            f"Invalid status '{status}': must be one of {sorted(VALID_STATUSES)}"
        )

    gates = data.get("gates")
    if not isinstance(gates, list) or len(gates) == 0:
        raise EvidenceValidationError("Gates list must be a non-empty list of gate objects")

    for idx, gate in enumerate(gates):
        if not isinstance(gate, dict):
            raise EvidenceValidationError(f"Gate at index {idx} must be an object")
        if not gate.get("gate_id") or not gate.get("status"):
            raise EvidenceValidationError(f"Gate at index {idx} missing 'gate_id' or 'status'")
        if gate["status"] not in VALID_GATE_OUTCOMES:
            raise EvidenceValidationError(
                f"Gate {gate['gate_id']} has invalid status '{gate['status']}'"
            )

    return data


def validate_package_integrity(package_evidence_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Tier 1: Validate physical integrity, schema validity, and hash DAG completeness."""
    if not package_evidence_dir.is_dir():
        raise EvidenceValidationError(f"Evidence directory does not exist: {package_evidence_dir}")

    status_path = package_evidence_dir / STATUS_JSON_FILENAME
    status_data = validate_status_json(status_path)

    hash_path = package_evidence_dir / HASH_FILENAME
    expected_hashes = parse_hashes_sha256(hash_path)

    # Verify all expected files match on disk
    verified_files: list[str] = []
    for rel_filename, expected_digest in expected_hashes.items():
        file_path = package_evidence_dir / rel_filename
        if not file_path.is_file():
            raise EvidenceValidationError(
                f"Evidence file declared in {HASH_FILENAME} missing on disk: {rel_filename}"
            )
        actual_digest = sha256_file(file_path).lower()
        if actual_digest != expected_digest:
            raise EvidenceValidationError(
                f"Hash mismatch for '{rel_filename}': expected {expected_digest}, got {actual_digest}"
            )
        verified_files.append(rel_filename)

    # Verify no un-hashed files exist in evidence dir (excluding hashes.sha256)
    for disk_file in package_evidence_dir.glob("*"):
        if disk_file.is_file() and disk_file.name != HASH_FILENAME:
            if disk_file.name not in expected_hashes:
                raise EvidenceValidationError(
                    f"Untracked evidence file found on disk: '{disk_file.name}' not in {HASH_FILENAME}"
                )

    # Verify gate declared files
    for g in status_data["gates"]:
        gate_files = g.get("evidence_files", [])
        for gf in gate_files:
            if gf not in expected_hashes:
                raise EvidenceValidationError(
                    f"Gate {g['gate_id']} references unverified evidence file: '{gf}'"
                )

    return status_data, verified_files


def validate_package_evidence(
    package_evidence_dir: Path,
    enforce_semantics: bool = True,
) -> PackageEvidenceReport:
    """Validate a package evidence directory fail-closed across both Integrity and Semantic tiers.

    1. Integrity Tier: Validates status.json schema, file completeness, and hash DAG.
    2. Semantic Tier: Extracts actual test metrics from JUnit XML and verifies gates.
    3. Gate Enforcement: If status is PASS or READY_FOR_REVIEW, all gates must be PASS.
    """
    status_data, verified_files = validate_package_integrity(package_evidence_dir)
    overall_status = status_data["status"]

    gate_results = [
        GateResult(
            gate_id=g["gate_id"],
            name=g.get("name", g["gate_id"]),
            status=g["status"],
            evidence_files=g.get("evidence_files", []),
        )
        for g in status_data["gates"]
    ]

    semantic_summary: dict[str, Any] | None = None
    if enforce_semantics and overall_status in ("PASS", "READY_FOR_REVIEW"):
        # Semantic evaluation will raise SemanticEvaluationError if any test failed, was skipped, or numbers mismatch
        try:
            semantic_summary = evaluate_package_semantics(package_evidence_dir, status_data)
        except SemanticEvaluationError as exc:
            raise EvidenceValidationError(f"Semantic gate evaluation failed: {exc}") from exc

        # All gates must be PASS
        for gr in gate_results:
            if gr.status != "PASS":
                raise EvidenceValidationError(
                    f"Cannot have status '{overall_status}' while gate '{gr.gate_id}' is '{gr.status}'"
                )

    return PackageEvidenceReport(
        milestone=status_data["milestone"],
        package=status_data["package"],
        schema_version=status_data["schema_version"],
        status=overall_status,
        gates=gate_results,
        verified_files=verified_files,
        is_valid=True,
        semantic_summary=semantic_summary,
    )
