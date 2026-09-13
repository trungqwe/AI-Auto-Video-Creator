"""Semantic Gate Evaluator for Milestone M2.

Performs deep semantic validation of test reports, secret scans, and capability artifacts.
Does not trust self-reported numbers in status.json.
Extracts actual execution results directly from machine-readable JUnit XML and JSON artifacts.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SemanticEvaluationError(Exception):
    """Raised when semantic gate validation fails."""
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


def evaluate_package_semantics(package_dir: Path, status_data: dict[str, Any]) -> dict[str, Any]:
    """Perform semantic evaluation of M2 package gates against actual evidence artifacts.

    Policy for M2-P0:
    - M2-P0 test suite (m2-p0-tests.xml): 0 failures, 0 errors, 0 skipped, total > 0.
    - M1 regression suite (m1-regression.xml): exactly 93 passed, 0 failures, 0 errors, 0 skipped.
    - Secret scan (secret-scan.json): verdict == "CLEAN", total_findings == 0.
    - Consistency: Numbers declared in status.json MUST match actual parsed JUnit metrics.
    """
    overall_status = status_data.get("status")
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

    # Check consistency with status.json summary
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

    # 4. Check for prohibited text patterns in test reports (e.g. FAILED lines masquerading as PASS)
    for report_file in package_dir.glob("*.txt"):
        content = report_file.read_text(encoding="utf-8", errors="ignore")
        if "=== FAILURES ===" in content or "=== SHORT TEST SUMMARY INFO ===" in content and "FAILED " in content:
            raise SemanticEvaluationError(
                f"Failed test summary detected inside {report_file.name}. Failed reports cannot be used as PASS evidence."
            )

    return {
        "p0_tests": p0_metrics,
        "m1_tests": m1_metrics,
        "secret_scan": secret_data.get("verdict"),
        "semantic_verdict": "PASS",
    }
