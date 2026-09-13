"""Semantic Gate Evaluator for Milestone M2.

Performs deep semantic validation of test reports, secret scans, and capability artifacts.
Does not trust self-reported numbers in status.json.
Extracts actual execution results directly from machine-readable JUnit XML and JSON artifacts.

Architecture:
- Fail-Closed Profile Registry / Dispatch Pattern.
- Integrity Validator remains generic across all packages.
- Semantic Evaluator dispatches to registered PackageSemanticProfile instances.
- Unknown or unregistered profiles fail closed (BLOCK).
- Cross-package profile spoofing is strictly prevented.
- Packages P1+ can register their profiles via the registry extension point without altering core validator logic.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SemanticEvaluationError(Exception):
    """Raised when semantic gate validation fails."""
    pass


class UnknownSemanticProfileError(SemanticEvaluationError):
    """Raised when a package declares an unregistered semantic profile."""
    pass


class ProfileSpoofingError(SemanticEvaluationError):
    """Raised when a package attempts to declare an incompatible profile from another package."""
    pass


@dataclass(frozen=True)
class JUnitSummary:
    total: int
    passed: int
    failures: int
    errors: int
    skipped: int


def parse_junit_xml(xml_path: Path) -> JUnitSummary:
    """Parse a JUnit XML test report and extract verified test execution metrics."""
    if not xml_path.is_file():
        raise SemanticEvaluationError(f"JUnit XML test report missing: {xml_path}")

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        raise SemanticEvaluationError(f"Malformed JUnit XML at {xml_path}: {exc}") from exc

    root = tree.getroot()

    # JUnit XML can have <testsuites> as root or <testsuite>
    if root.tag == "testsuite":
        suites = [root]
    elif root.tag == "testsuites":
        suites = list(root.findall("testsuite"))
    else:
        raise SemanticEvaluationError(f"Unexpected root tag '{root.tag}' in {xml_path}")

    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0

    for suite in suites:
        total_tests += int(suite.attrib.get("tests", 0))
        total_failures += int(suite.attrib.get("failures", 0))
        total_errors += int(suite.attrib.get("errors", 0))
        total_skipped += int(suite.attrib.get("skipped", 0))

    passed = total_tests - total_failures - total_errors - total_skipped
    return JUnitSummary(
        total=total_tests,
        passed=passed,
        failures=total_failures,
        errors=total_errors,
        skipped=total_skipped,
    )


def parse_secret_scan_json(scan_path: Path) -> dict[str, Any]:
    """Parse and verify machine-readable secret scan report."""
    if not scan_path.is_file():
        raise SemanticEvaluationError(f"Secret scan report missing: {scan_path}")

    try:
        data = json.loads(scan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SemanticEvaluationError(f"Malformed secret scan JSON at {scan_path}: {exc}") from exc

    if data.get("schema_version") != "m2_secret_scan_v1":
        raise SemanticEvaluationError(f"Invalid secret scan schema_version: {data.get('schema_version')}")

    return data


class PackageSemanticProfile(ABC):
    """Abstract base class for package-specific semantic evaluation profiles."""

    @property
    @abstractmethod
    def profile_id(self) -> str:
        """Unique identifier of the profile, e.g. 'm2-p0'."""
        pass

    @property
    @abstractmethod
    def target_package(self) -> str:
        """The canonical package identifier this profile belongs to, e.g. 'M2-P0'."""
        pass

    @abstractmethod
    def evaluate(self, package_dir: Path, status_data: dict[str, Any]) -> dict[str, Any]:
        """Perform package-specific semantic evaluation.
        
        Must raise SemanticEvaluationError on any policy violation.
        Returns a dictionary summarizing verified semantic metrics.
        """
        pass


class M2P0SemanticProfile(PackageSemanticProfile):
    """Semantic Profile for Milestone M2-P0: Foundation, Toolchain & Evidence Protocol.
    
    Policies:
    - M2-P0 test suite (m2-p0-tests.xml): 0 failures, 0 errors, 0 skipped, total > 0.
    - M1 regression suite (m1-regression.xml): exactly 93 passed, 0 failures, 0 errors, 0 skipped.
    - Secret scan (secret-scan.json): verdict == "CLEAN", total_findings == 0.
    - Text reports: no failure banners (=== FAILURES === or FAILED ).
    - Consistency: Numbers declared in status.json MUST match actual parsed JUnit metrics.
    """

    @property
    def profile_id(self) -> str:
        return "m2-p0"

    @property
    def target_package(self) -> str:
        return "M2-P0"

    def evaluate(self, package_dir: Path, status_data: dict[str, Any]) -> dict[str, Any]:
        summary = status_data.get("evidence_summary", {})

        # 1. Evaluate M2-P0 JUnit XML
        p0_xml = package_dir / "m2-p0-tests.xml"
        p0_metrics = parse_junit_xml(p0_xml)

        if p0_metrics.failures > 0 or p0_metrics.errors > 0:
            raise SemanticEvaluationError(
                f"M2-P0 test suite failed: {p0_metrics.failures} failures, {p0_metrics.errors} errors in {p0_xml.name}"
            )
        if p0_metrics.skipped > 0:
            raise SemanticEvaluationError(
                f"M2-P0 test suite policy forbids skipped tests: {p0_metrics.skipped} skipped in {p0_xml.name}"
            )
        if p0_metrics.total <= 0:
            raise SemanticEvaluationError(f"M2-P0 test suite has no collected tests in {p0_xml.name}")

        reported_p0 = summary.get("m2_p0_tests", {})
        if reported_p0.get("total") != p0_metrics.total or reported_p0.get("passed") != p0_metrics.passed:
            raise SemanticEvaluationError(
                f"status.json m2_p0_tests mismatch: reported {reported_p0} vs actual XML {p0_metrics}"
            )

        # 2. Evaluate M1 Regression JUnit XML
        m1_xml = package_dir / "m1-regression.xml"
        m1_metrics = parse_junit_xml(m1_xml)

        if m1_metrics.total != 93:
            raise SemanticEvaluationError(
                f"M1 regression suite total mismatch: expected exactly 93, got {m1_metrics.total} in {m1_xml.name}"
            )
        if m1_metrics.passed != 93 or m1_metrics.failures > 0 or m1_metrics.errors > 0 or m1_metrics.skipped > 0:
            raise SemanticEvaluationError(
                f"M1 regression suite did not pass 100%: passed={m1_metrics.passed}, failures={m1_metrics.failures}, errors={m1_metrics.errors}, skipped={m1_metrics.skipped}"
            )

        reported_m1 = summary.get("m1_regression_tests", {})
        if reported_m1.get("total") != 93 or reported_m1.get("passed") != 93:
            raise SemanticEvaluationError(
                f"status.json m1_regression_tests mismatch: reported {reported_m1} vs actual XML {m1_metrics}"
            )

        # 3. Evaluate Secret Scan Report
        secret_json = package_dir / "secret-scan.json"
        secret_data = parse_secret_scan_json(secret_json)

        if secret_data.get("verdict") != "CLEAN" or secret_data.get("total_findings", 0) != 0:
            raise SemanticEvaluationError(
                f"Secret scan failed: verdict={secret_data.get('verdict')}, findings={secret_data.get('total_findings')}"
            )

        if summary.get("secret_scan_violations") != 0:
            raise SemanticEvaluationError(
                f"status.json reported secret_scan_violations={summary.get('secret_scan_violations')}, expected 0"
            )

        # 4. Check for prohibited text patterns in text reports
        for report_file in package_dir.glob("*.txt"):
            content = report_file.read_text(encoding="utf-8", errors="ignore")
            if "=== FAILURES ===" in content or ("=== SHORT TEST SUMMARY INFO ===" in content and "FAILED " in content):
                raise SemanticEvaluationError(
                    f"Failed test summary detected inside {report_file.name}. Failed reports cannot be used as PASS evidence."
                )

        # 5. Verify Provenance Integrity across run_id, commands, and artifacts
        provenance = verify_package_provenance(package_dir, status_data)

        return {
            "profile": self.profile_id,
            "p0_tests": p0_metrics,
            "m1_tests": m1_metrics,
            "secret_scan": secret_data.get("verdict"),
            "provenance": provenance,
            "semantic_verdict": "PASS",
        }


def verify_package_provenance(package_dir: Path, status_data: dict[str, Any]) -> dict[str, Any]:
    """Verify deterministic provenance: run_id consistency, artifact producers, and timestamps."""
    import datetime

    status_run_id = status_data.get("run_id")
    if not status_run_id or not isinstance(status_run_id, str):
        raise SemanticEvaluationError("status.json missing mandatory 'run_id' for provenance tracking")

    cmd_file = package_dir / "commands.jsonl"
    if not cmd_file.is_file():
        raise SemanticEvaluationError("commands.jsonl missing for provenance verification")

    records: list[dict[str, Any]] = []
    for line_idx, line in enumerate(cmd_file.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SemanticEvaluationError(f"Malformed JSON in commands.jsonl line {line_idx}: {exc}") from exc

    if not records:
        raise SemanticEvaluationError("commands.jsonl contains no command records")

    # 1. All records must share the exact same run_id as status.json
    for idx, rec in enumerate(records):
        rec_run_id = rec.get("run_id")
        if rec_run_id != status_run_id:
            raise SemanticEvaluationError(
                f"Command record sequence {rec.get('sequence_idx', idx + 1)} run_id mismatch: "
                f"expected '{status_run_id}', got '{rec_run_id}'"
            )

    # 2. secret-scan.json must share status.run_id
    secret_file = package_dir / "secret-scan.json"
    secret_data = parse_secret_scan_json(secret_file)
    secret_run_id = secret_data.get("run_id")
    if secret_run_id != status_run_id:
        raise SemanticEvaluationError(
            f"secret-scan.json run_id mismatch: expected '{status_run_id}', got '{secret_run_id}'"
        )

    # 3. Producer record for secret-scan.json must exist and match timestamps
    secret_records = [r for r in records if "secret-scan.json" in r.get("created_artifacts", [])]
    if not secret_records:
        raise SemanticEvaluationError("No command record found declaring 'secret-scan.json' in created_artifacts")

    final_secret_rec = secret_records[-1]
    rec_ts = final_secret_rec.get("timestamp_utc", "")
    art_ts = secret_data.get("timestamp_utc", "")

    if rec_ts and art_ts:
        try:
            t_rec = datetime.datetime.fromisoformat(rec_ts)
            t_art = datetime.datetime.fromisoformat(art_ts)
            diff = abs((t_rec - t_art).total_seconds())
            if diff > 5.0:
                raise SemanticEvaluationError(
                    f"Provenance timestamp drift: secret-scan.json ({art_ts}) differs from command record ({rec_ts}) "
                    f"by {diff:.2f}s > 5.0s. Artifact was likely modified or generated outside of recorded execution."
                )
        except ValueError:
            if rec_ts != art_ts:
                raise SemanticEvaluationError(
                    f"Provenance timestamp mismatch: secret-scan.json ({art_ts}) vs command record ({rec_ts})"
                )

    return {
        "run_id": status_run_id,
        "total_command_records": len(records),
        "provenance_verdict": "VERIFIED",
    }



class SemanticProfileRegistry:
    """Registry managing package semantic profiles for Milestone M2."""

    def __init__(self) -> None:
        self._profiles: dict[str, PackageSemanticProfile] = {}

    def register(self, profile: PackageSemanticProfile, allow_override: bool = False) -> None:
        """Register a semantic evaluation profile."""
        key = profile.profile_id.strip().lower()
        if key in self._profiles and not allow_override:
            raise ValueError(f"Semantic profile '{key}' is already registered.")
        self._profiles[key] = profile

    def get(self, profile_id: str) -> PackageSemanticProfile:
        """Retrieve a registered semantic profile by ID. Fails closed if not found."""
        key = profile_id.strip().lower()
        if key not in self._profiles:
            raise UnknownSemanticProfileError(
                f"Unknown or unregistered semantic profile: '{profile_id}'. Fail-closed: evaluation blocked."
            )
        return self._profiles[key]

    def clear(self) -> None:
        """Clear all registered profiles."""
        self._profiles.clear()


# Default global registry instance
_GLOBAL_REGISTRY = SemanticProfileRegistry()
_GLOBAL_REGISTRY.register(M2P0SemanticProfile())


def get_profile_registry() -> SemanticProfileRegistry:
    """Access the global semantic profile registry."""
    return _GLOBAL_REGISTRY


def register_semantic_profile(profile: PackageSemanticProfile, allow_override: bool = False) -> None:
    """Extension point for P1-P8 packages to register their semantic profiles."""
    _GLOBAL_REGISTRY.register(profile, allow_override=allow_override)


def evaluate_package_semantics(package_dir: Path, status_data: dict[str, Any]) -> dict[str, Any]:
    """Perform semantic evaluation of M2 package gates via Profile Dispatch.
    
    Fail-closed semantics:
    1. Extracts profile_id from status_data['semantic_profile'] or status_data['package'].
    2. Validates package compatibility to block cross-package spoofing.
    3. Dispatches to registered PackageSemanticProfile.
    4. Blocks execution with UnknownSemanticProfileError if profile is not registered.
    """
    package = status_data.get("package", "")
    if not isinstance(package, str) or not package.strip():
        raise SemanticEvaluationError("status.json missing or invalid 'package' field")

    declared_profile = status_data.get("semantic_profile")
    profile_id = declared_profile or package.lower()

    if not isinstance(profile_id, str) or not profile_id.strip():
        raise SemanticEvaluationError(f"Missing semantic_profile for package '{package}'")

    profile = _GLOBAL_REGISTRY.get(profile_id)

    # Cross-package spoofing guard: target package must match
    if profile.target_package.upper() != package.strip().upper():
        raise ProfileSpoofingError(
            f"Package '{package}' cannot declare profile '{profile_id}' belonging to '{profile.target_package}'. "
            "Cross-package profile spoofing blocked."
        )

    return profile.evaluate(package_dir, status_data)
