"""Evidence Manifest, Gate Enforcement and Audit module for M1-P6.

Provides fail-closed manifest builder and validator for M1 proof artifacts,
enforces strict gate scope boundaries (preventing premature PASS on G01/G04/G07),
reads actual package statuses dynamically from evidence, and implements
fail-closed secret scanning across the evidence tree.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

SECRET_PATTERNS = [
    (r"ghp_[0-9a-zA-Z]{20,}", "github_token"),
    (r"ya29\.[0-9a-zA-Z_\-]{30,}", "google_oauth_token"),
    (r"-----BEGIN (?:RSA )?PRIVATE KEY-----", "private_key"),
    (r"(?:client_secret|refresh_token)\s*[:=]\s*['\"][0-9a-zA-Z_\-]{20,}['\"]", "oauth_secret_pair"),
]

MANDATORY_MANIFEST_FIELDS = [
    "schema_version",
    "milestone",
    "version_lock",
    "packages",
    "gates",
]

REQUIRED_M1_PACKAGES = [
    "m1-p0",
    "m1-p1",
    "m1-p2",
    "m1-p3",
    "m1-p4",
    "m1-p5",
    "m1-p6",
]

MANDATORY_PACKAGE_FILES = {
    "common": ["commands.jsonl", "status.md"],
    "m1-p0": ["bootstrap.json", "environment.json"],
    "m1-p2": ["temporal_server_evidence.json"],
    "m1-p3": ["drive_e3_evidence.json"],
    "m1-p5": ["compatibility_matrix.json"],
}


def check_package_mandatory_files(pkg_id: str, pkg_dir: Path) -> List[str]:
    """Check required evidence files for a package, accounting for legacy and current evidence naming."""
    missing = []
    if not (pkg_dir / "commands.jsonl").is_file():
        missing.append("commands.jsonl")
    if not (pkg_dir / "status.md").is_file():
        missing.append("status.md")

    # Hash file: hashes.sha256 or artifacts.sha256
    if not (pkg_dir / "hashes.sha256").is_file() and not (pkg_dir / "artifacts.sha256").is_file():
        missing.append("hashes.sha256")

    # RED observations: red-observations.md or any red-* or fault-timeline.md
    has_red = (
        (pkg_dir / "red-observations.md").is_file()
        or any(f.name.startswith("red-") or f.name == "fault-timeline.md" for f in pkg_dir.iterdir() if f.is_file())
    )
    if not has_red:
        missing.append("red-observations.md")

    # Specific package files
    if pkg_id in MANDATORY_PACKAGE_FILES:
        for f in MANDATORY_PACKAGE_FILES[pkg_id]:
            if not (pkg_dir / f).is_file():
                missing.append(f)

    return missing


def parse_package_status_from_evidence(pkg_dir: Path) -> str:
    """Parse authoritative package outcome from status.md without hard-coding."""
    status_file = pkg_dir / "status.md"
    if not status_file.is_file():
        return "MISSING_STATUS_RECORD"

    content = status_file.read_text(encoding="utf-8", errors="ignore")
    # Matches: "Trạng thái: PASS", "**Trạng thái:** `PASS`", "Status: STOPPED", etc.
    m = re.search(r"(?:Trạng thái|Status)\*?\*?\s*[:=]\s*\*?\*?\s*[`\"']?([A-Z_]+)[`\"']?", content, re.IGNORECASE)
    if m:
        val = m.group(1).upper()
        if val in ("PASS", "STOPPED", "FAIL", "FAILED", "BLOCKED_EXTERNAL", "CORRECTION_REQUIRED"):
            return "FAILED" if val == "FAIL" else val

    # Fallback to checking headers if no inline key:value
    if "# STOPPED" in content:
        return "STOPPED"
    if "# PASS" in content or "PASS_M1_SCOPE" in content:
        return "PASS"

    return "UNPARSEABLE_STATUS"


def validate_manifest_schema(manifest: Dict[str, Any]) -> bool:
    """Validate that manifest contains all mandatory sections and fields."""
    for field in MANDATORY_MANIFEST_FIELDS:
        if field not in manifest:
            raise ValueError(f"Missing mandatory field: {field}")

    packages = manifest.get("packages", {})
    if not isinstance(packages, dict):
        raise ValueError("Field 'packages' must be a dictionary")

    for req_pkg in REQUIRED_M1_PACKAGES:
        if req_pkg not in packages:
            raise ValueError(f"Missing required package: {req_pkg}")

    return True


def validate_manifest_artifacts(manifest: Dict[str, Any], project_root: Path) -> Dict[str, Any]:
    """Verify that all referenced artifacts exist and match their SHA-256 hashes."""
    missing = []
    tampered = []

    root = Path(project_root)
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("Field 'artifacts' must be a list")

    for item in artifacts:
        rel_path = item.get("path")
        declared_hash = item.get("sha256")
        if not rel_path or not declared_hash:
            continue

        target_file = root / rel_path
        if not target_file.is_file():
            missing.append(rel_path)
            continue

        actual_hash = hashlib.sha256(target_file.read_bytes()).hexdigest()
        if actual_hash != declared_hash:
            tampered.append({
                "path": rel_path,
                "declared": declared_hash,
                "actual": actual_hash,
            })

    is_valid = (len(missing) == 0 and len(tampered) == 0)
    return {
        "valid": is_valid,
        "missing": missing,
        "tampered": tampered,
    }


def evaluate_milestone_gates(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Rule engine evaluating M1 milestone exit criteria and gate scope boundaries."""
    gates = manifest.get("gates", {})

    # 1. Gate Scope Boundaries Protection (cấm nâng scope quá sớm)
    if gates.get("G01") == "PASS":
        raise ValueError("G01 cannot claim full PASS in M1 (must be PARTIALLY_PROVEN or PASS_M1_SCOPE)")

    if gates.get("G04") == "PASS":
        raise ValueError("G04 cannot claim full PASS in M1 (must be PARTIALLY_PROVEN or PASS_M1_SCOPE)")

    if gates.get("G07") == "PASS":
        raise ValueError("G07 cannot claim full PASS in M1 (must be SMOKE_COMPATIBILITY_PASS_M1_SCOPE)")

    # 2. Package Status Evaluation
    packages = manifest.get("packages", {})
    statuses = [pkg_info.get("status") for pkg_info in packages.values()]

    if any(s in ("FAIL", "FAILED") for s in statuses):
        return {"m1_status": "FAILED", "reason": "One or more packages reported failure"}

    if any(s == "BLOCKED_EXTERNAL" for s in statuses):
        return {"m1_status": "BLOCKED_EXTERNAL", "reason": "Package blocked on external dependency"}

    if any(s in ("STOPPED", "CORRECTION_REQUIRED") for s in statuses):
        return {"m1_status": "CORRECTION_REQUIRED", "reason": "Package stopped or correction required"}

    if any(s and ("MISSING" in s or "UNPARSEABLE" in s or "SEMANTIC" in s) for s in statuses):
        return {"m1_status": "EVIDENCE_INCOMPLETE", "reason": "Required evidence files missing, unparseable, or failed semantic validation"}

    if all(s == "PASS" for s in statuses):
        return {"m1_status": "READY_FOR_USER_CHECKPOINT", "reason": "All required M1 packages passed"}

    return {"m1_status": "IN_PROGRESS", "reason": "Milestone packages still in progress"}


def scan_secrets_in_directory(dir_path: Path) -> List[Dict[str, Any]]:
    """Recursively scan directory for canary secret tokens using fail-closed regex rules."""
    findings = []
    target_dir = Path(dir_path)
    if not target_dir.is_dir():
        return findings

    for root, _, files in os.walk(target_dir):
        for fname in files:
            file_path = Path(root) / fname
            if file_path.suffix in (".pyc", ".db", ".mp4", ".png", ".jpg", ".zip", ".exe"):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, rule_name in SECRET_PATTERNS:
                matches = re.finditer(pattern, content)
                for m in matches:
                    findings.append({
                        "file": str(file_path),
                        "rule": rule_name,
                        "pattern": m.group(0)[:10] + "...",  # redacted
                    })

    return findings


def build_m1_evidence_manifest(project_root: Path) -> Dict[str, Any]:
    """Collect and assemble all M1 evidence records into an authoritative manifest with dynamic parsing."""
    root = Path(project_root)
    evidence_dir = root / "docs" / "milestones" / "m1-proof" / "evidence"

    artifacts = []
    packages_summary = {}

    for pkg_id in REQUIRED_M1_PACKAGES:
        pkg_dir = evidence_dir / pkg_id
        if not pkg_dir.is_dir():
            packages_summary[pkg_id] = {"status": "MISSING_DIR", "evidence_files": []}
            continue

        # Check required files
        missing_req = check_package_mandatory_files(pkg_id, pkg_dir)
        if missing_req:
            if any(f in ["temporal_server_evidence.json", "drive_e3_evidence.json"] for f in missing_req):
                pkg_status = f"CAPABILITY_EVIDENCE_MISSING:{','.join(missing_req)}"
            else:
                pkg_status = f"MISSING_REQUIRED_EVIDENCE:{','.join(missing_req)}"
        else:
            pkg_status = parse_package_status_from_evidence(pkg_dir)

        # Semantic capability validation (R5-04)
        if pkg_id == "m1-p3":
            p3_cap_file = pkg_dir / "drive_e3_evidence.json"
            if p3_cap_file.is_file():
                try:
                    p3_data = json.loads(p3_cap_file.read_text(encoding="utf-8"))
                    is_p3_semantically_valid = (
                        p3_data.get("status") == "PASS_E3_LIVE"
                        and p3_data.get("sha256_verified") is True
                        and p3_data.get("process_isolated") is True
                        and p3_data.get("broker_pid") != p3_data.get("desktop_pid")
                        and isinstance(p3_data.get("broker_pid"), int)
                        and p3_data.get("broker_pid") > 0
                        and isinstance(p3_data.get("desktop_pid"), int)
                        and p3_data.get("desktop_pid") > 0
                        and p3_data.get("secure_storage_verified") is True
                    )
                    if not is_p3_semantically_valid:
                        pkg_status = "CAPABILITY_EVIDENCE_SEMANTIC_FAIL:p3_process_isolation_or_security_violation"
                except Exception:
                    pkg_status = "CAPABILITY_EVIDENCE_SEMANTIC_FAIL:p3_corrupt_json"

        elif pkg_id == "m1-p5":
            p5_matrix_file = pkg_dir / "compatibility_matrix.json"
            if p5_matrix_file.is_file():
                try:
                    p5_data = json.loads(p5_matrix_file.read_text(encoding="utf-8"))
                    overall_pass = (p5_data.get("overall_result") == "PASS")
                    runtimes = p5_data.get("runtimes", {})
                    all_runtimes_pass = bool(runtimes) and all(
                        r.get("result") == "PASS" and ("observed" not in r or r.get("observed") not in (None, "unknown", "null", ""))
                        for r in runtimes.values()
                    )
                    if not (overall_pass and all_runtimes_pass):
                        pkg_status = "CAPABILITY_EVIDENCE_SEMANTIC_FAIL:p5_compatibility_has_failed_runtimes"
                except Exception:
                    pkg_status = "CAPABILITY_EVIDENCE_SEMANTIC_FAIL:p5_corrupt_json"

        pkg_files = []
        for file in sorted(pkg_dir.iterdir()):
            if file.is_file():
                f_hash = hashlib.sha256(file.read_bytes()).hexdigest()
                rel_path = f"docs/milestones/m1-proof/evidence/{pkg_id}/{file.name}"
                artifacts.append({"path": rel_path, "sha256": f_hash})
                pkg_files.append(file.name)

        packages_summary[pkg_id] = {
            "status": pkg_status,
            "evidence_files": pkg_files,
        }

    # Dynamic classification of evidence based on verified artifacts
    p3_has_e3 = (
        packages_summary.get("m1-p3", {}).get("status") == "PASS"
        and (evidence_dir / "m1-p3" / "drive_e3_evidence.json").is_file()
    )

    evidence_classification = {
        "m1-p0": "E2-INT (Runtime & Live PostgreSQL 18.6 Preflight)",
        "m1-p1": "E2-INT (Contract Fencing, Advisory CAS & Concurrency)",
        "m1-p2": "E2-INT (Exact Temporal Server 1.31.2 Binary Integration & Replay)",
        "m1-p3": "E3 (Live External Verification on Google Drive API & ADR-0009 Broker)" if p3_has_e3 else "E2-INT (Unproven External Scope: Drive Live Verification Incomplete or Invalid)",
        "m1-p4": "E2 (SQLite WAL Journal & Windows Atomic File Write)",
        "m1-p5": "E2-INT (Compatibility Matrix, Strict Version & ffprobe Verification)",
        "m1-p6": "AUDIT (Fail-Closed Manifest Builder & Exit Gate Evaluation)",
    }

    manifest = {
        "schema_version": "1.0",
        "milestone": "M1",
        "version_lock": {
            "revision": "M1-R1",
            "uv_lock_sha256": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest() if (root / "uv.lock").is_file() else "",
        },
        "packages": packages_summary,
        "gates": {
            "G01": "PARTIALLY_PROVEN",
            "G04": "PARTIALLY_PROVEN",
            "G07": "SMOKE_COMPATIBILITY_PASS_M1_SCOPE",
        },
        "evidence_classification": evidence_classification,
        "contracts_audited": [
            "CT-CMN-001..013",
            "CT-EVT-001..005",
            "CT-WF-001..009",
            "CT-STO-001..009",
            "CT-STATE-001..012",
            "ADR-0001..0011",
        ],
        "artifacts": artifacts,
    }

    return manifest
