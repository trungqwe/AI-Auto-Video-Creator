"""Independent, read-only verifier for the P5A implementation evidence run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


RUN = Path(__file__).parent
EXPECTED_ORACLE = "A9C809332309A934E83DE5AB37A8A2A29261E86E3E38386878CB765C7B70A1F8"


def junit(path: Path) -> tuple[int, int, int, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    total = sum(int(s.attrib.get("tests", 0)) for s in suites)
    failures = sum(int(s.attrib.get("failures", 0)) for s in suites)
    errors = sum(int(s.attrib.get("errors", 0)) for s in suites)
    skipped = sum(int(s.attrib.get("skipped", 0)) for s in suites)
    return total, total - failures - errors - skipped, failures + errors, skipped


def main() -> None:
    status = json.loads((RUN / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "READY_FOR_REVIEW"
    assert status["source_commit_sha"] == "0b862b9b75bbee32a61bc29b466f4d9b1f564dbf"
    assert status["oracle_sha256"] == EXPECTED_ORACLE
    expected = {
        "m2-p5a-tests.xml": (5, 5),
        "m2-p4-regression.xml": (9, 9),
        "m2-p3-regression.xml": (11, 11),
        "m2-p2-regression.xml": (11, 11),
        "m2-p1-regression.xml": (11, 11),
        "m2-p0-regression.xml": (33, 33),
        "m1-regression.xml": (93, 93),
    }
    for name, (total_expected, passed_expected) in expected.items():
        total, passed, failures_or_errors, skipped = junit(RUN / name)
        assert (total, passed, failures_or_errors, skipped) == (total_expected, passed_expected, 0, 0), name
    runtime = json.loads((RUN / "runtime-capability.json").read_text(encoding="utf-8"))
    assert runtime["python"] == "3.13.15"
    assert runtime["psycopg"] == "3.3.5"
    assert runtime["psycopg_pool"] == "3.3.1"
    assert runtime["postgresql"] == "18.6"
    assert runtime["createdb"] is True and runtime["disposable_db_orphans"] == 0
    scan = json.loads((RUN / "secret-scan.json").read_text(encoding="utf-8"))
    assert scan["verdict"] == "CLEAN" and scan["total_findings"] == 0
    print("VALIDATION: PASS")
    print("P5A=5/5 P4=9/9 P3=11/11 P2=11/11 P1=11/11 P0=33/33 M1=93/93")
    print("ORACLE_SHA256=" + EXPECTED_ORACLE)
    print("SOURCE_COMMIT_SHA=" + status["source_commit_sha"])


if __name__ == "__main__":
    main()
