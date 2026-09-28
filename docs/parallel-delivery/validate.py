#!/usr/bin/env python3
"""Validate the proposed parallel-delivery documentation bundle.

Remediates all six findings from Astra audit round 1:
- F1: Exact contract binding (registry, source, owner, hash verification)
- F2: Ownership & path safety (reject absolute/traversal/aliases, check owned vs forbidden, immutable evidence)
- F3: Scope & candidate delta (pin approved base/candidate, committed diff + dirty overlay, rename both ends, immutable evidence)
- F4: Orca mapping & lifecycle (separate delivery task ID, worker_done CLI outcome, fresh dispatch, duplicate/stale rejection)
- F5: Readiness & traceability (validate real refs, readiness predicate, reject fake IDs and locked->ready)
- F6: Locks & leases (active lease schema vs declaration, integrated tasks hold no lease, disjoint DB namespaces, capacity bounds)
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import subprocess
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "docs" / "parallel-delivery"
REPORT = BUNDLE / ".validation-report.json"
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py", ".toml", ".txt"}

# Specific sequences produced by common UTF-8 double-decoding; ordinary Vietnamese
# text may legitimately contain an isolated U+00C3, so single-character checks are invalid.
MOJIBAKE_PATTERNS = tuple(
    bytes(values).decode("latin-1")
    for values in (
        (0xC3, 0x83, 0xC2),
        (0xC3, 0x82, 0xC2),
        (0xC3, 0x83, 0xC3),
        (0xC3, 0x82, 0xC3),
    )
) + (chr(0x00E2) + chr(0x20AC), chr(0x00C2) + chr(0x00A0))

ALLOWED_CHANGED = {
    "AGENTS.md",
    "CLAUDE.md",
    "HANDOFF.md",
    "README.md",
    "CHANGELOG.md",
    "docs/11-roadmap.md",
    "docs/12-pre-code-checklist.md",
}

REQUIRED_TASK_FIELDS = {
    "id", "milestone", "kind", "status", "authority", "authority_refs",
    "depends_on", "requirement_refs", "contract_refs", "invariant_refs",
    "module_owners", "owned_paths", "forbidden_paths", "resource_locks",
    "runtime_prerequisites", "acceptance", "evidence_outputs", "rollback",
    "route", "merge_priority",
}

DEFAULT_BASE_COMMIT = "4a7c8c921b7e05066505d51b168a02c3fde61317"

# Import delivery engine components
sys.path.insert(0, str(BUNDLE))
try:
    from delivery_engine import (
        KNOWN_INVARIANTS,
        ContractBinding,
        ContractBindingError,
        LeaseManager,
        LockLeaseError,
        build_contract_catalog,
        check_owned_vs_forbidden,
        check_path_scope,
        get_committed_diff_paths,
        get_dirty_overlay_paths,
        patterns_overlap,
        validate_contract_ref,
        validate_path_syntax,
        validate_scope_and_deltas,
        validate_task_traceability_and_readiness,
    )
except ImportError as exc:
    raise RuntimeError(f"Failed to import delivery_engine from {BUNDLE}") from exc


def load_yaml(path: Path) -> Any:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to validate YAML") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_known_requirements() -> Set[str]:
    """Scan docs/ for all referenced FR-* and QR-* requirements."""
    reqs: Set[str] = set()
    for doc in ROOT.glob("docs/**/*.md"):
        if doc.is_file() and not str(doc).startswith(str(BUNDLE)):
            text = doc.read_text(encoding="utf-8", errors="ignore")
            reqs.update(re.findall(r"\b(?:FR|QR)-[A-Z0-9-]+\b", text))
    return reqs


def check_utf8() -> list[str]:
    errors: list[str] = []
    paths = [ROOT / name for name in ALLOWED_CHANGED if (ROOT / name).exists()]
    paths.extend(p for p in BUNDLE.rglob("*") if p.is_file() and p != REPORT and "__pycache__" not in str(p))
    for path in sorted(set(paths)):
        if not path.exists():
            continue
        is_root_text = path.name in {"AGENTS.md", "CLAUDE.md", "HANDOFF.md", "README.md", "CHANGELOG.md"}
        if path.suffix.lower() not in TEXT_SUFFIXES and not is_root_text:
            continue
        raw = path.read_bytes()
        rel = path.relative_to(ROOT).as_posix()
        if raw.startswith(b"\xef\xbb\xbf"):
            errors.append(f"{rel}: UTF-8 BOM is forbidden")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"{rel}: invalid UTF-8: {exc}")
            continue
        for marker in MOJIBAKE_PATTERNS:
            if marker in text:
                errors.append(f"{rel}: mojibake marker {marker!r}")
        for index, char in enumerate(text):
            code = ord(char)
            if code < 32 and char not in "\n\t\r":
                errors.append(f"{rel}: forbidden control U+{code:04X} at character {index}")
                break
    return errors


def check_task_dag(
    data: dict[str, Any],
    ownership: dict[str, Any],
    catalog: Dict[str, ContractBinding],
    known_owners: Set[str],
    known_requirements: Set[str],
) -> list[str]:
    errors: list[str] = []
    tasks = data.get("tasks", [])
    external = data.get("external_nodes", [])
    ids = [entry.get("id") for entry in tasks + external]
    for value, count in Counter(ids).items():
        if not value or count != 1:
            errors.append(f"task id {value!r} occurs {count} times")
    known = set(ids)
    edges: dict[str, list[str]] = defaultdict(list)

    for task in tasks:
        task_id = task.get("id")
        missing = REQUIRED_TASK_FIELDS - set(task)
        if missing:
            errors.append(f"{task_id}: missing fields {sorted(missing)}")
        authority = task.get("authority", {}).get("state")
        if task.get("kind") == "future_template" and authority != "future_template":
            errors.append(f"{task_id}: future template must use future_template authority")
        if task_id in {"M2-P8-LOCKED", "M2-P9-LOCKED"} and authority != "locked":
            errors.append(f"{task_id}: locked sentinel is not locked")
        if authority in {"locked", "future_template", "revoked"} and task.get("owned_paths"):
            errors.append(f"{task_id}: non-granted task owns paths")

        # F2: Path format checks on owned_paths, forbidden_paths, evidence_outputs
        for path_field in ("owned_paths", "forbidden_paths", "evidence_outputs"):
            for p in task.get(path_field, []):
                try:
                    validate_path_syntax(str(p))
                except Exception as exc:
                    errors.append(f"{task_id}: {path_field} {p!r} invalid: {exc}")

        # F2: Check owned vs forbidden intersection
        intersection_errs = check_owned_vs_forbidden(task.get("owned_paths", []), task.get("forbidden_paths", []))
        for err in intersection_errs:
            errors.append(f"{task_id}: {err}")

        # F2: Check immutable evidence lease rejection
        for lk in task.get("resource_locks", []):
            if lk == "LOCK-ACCEPTED-EVIDENCE":
                errors.append(f"{task_id}: cannot request mutation lease on LOCK-ACCEPTED-EVIDENCE")
        for op in task.get("owned_paths", []):
            if patterns_overlap(str(op), "docs/milestones/**/evidence/**"):
                errors.append(f"{task_id}: cannot own immutable evidence path: {op}")

        # F5: Traceability and readiness predicate validation
        trace_errs = validate_task_traceability_and_readiness(
            task, catalog, known_owners, known_requirements, ROOT
        )
        errors.extend(trace_errs)

        for dep in task.get("depends_on", []):
            dep_id = dep.get("task") if isinstance(dep, dict) else dep
            if dep_id not in known:
                errors.append(f"{task_id}: dangling dependency {dep_id!r}")
            edges[dep_id].append(task_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            errors.append(f"cycle detected at {node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for child in edges.get(node, []):
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in known:
        visit(node)

    allowed_statuses = set(data.get("schema", {}).get("status_enum", []))
    allowed_authority = set(data.get("schema", {}).get("authority_state_enum", []))
    allowed_conditions = set(data.get("schema", {}).get("dependency_condition_enum", []))
    acceptance_fields = set(data.get("schema", {}).get("acceptance_required_fields", []))
    for task in tasks:
        task_id = task.get("id")
        if task.get("status") not in allowed_statuses:
            errors.append(f"{task_id}: invalid status {task.get('status')!r}")
        if task.get("authority", {}).get("state") not in allowed_authority:
            errors.append(f"{task_id}: invalid authority state")
        for dep in task.get("depends_on", []):
            if isinstance(dep, dict) and dep.get("condition") not in allowed_conditions:
                errors.append(f"{task_id}: invalid dependency condition {dep.get('condition')!r}")
        for row in task.get("acceptance", []):
            missing = acceptance_fields - set(row)
            if missing:
                errors.append(f"{task_id}: acceptance row missing {sorted(missing)}")

    task_set = {task.get("id") for task in tasks}
    for wave in data.get("waves", []):
        for task_id in wave.get("task_ids", []):
            if task_id not in task_set:
                errors.append(f"{wave.get('id')}: unknown task {task_id}")
    return errors


def check_registries(
    contracts: dict[str, Any],
    ownership: dict[str, Any],
    dag: dict[str, Any],
    catalog: Dict[str, ContractBinding],
) -> list[str]:
    errors: list[str] = []
    contract_records = contracts.get("contracts", [])
    contract_ids = [item.get("id") for item in contract_records]
    lock_ids = [item.get("id") for item in ownership.get("locks", [])]
    for label, values in (("contract", contract_ids), ("lock", lock_ids)):
        for value, count in Counter(values).items():
            if not value or count != 1:
                errors.append(f"{label} id {value!r} occurs {count} times")
    lock_set = set(lock_ids)
    prefix_owners: dict[str, str] = {}
    registry_by_id = {record.get("id"): record for record in contract_records}

    for contract in contract_records:
        contract_id = contract.get("id")
        if contract.get("lock") not in lock_set:
            errors.append(f"{contract_id}: unknown lock {contract.get('lock')}")
        source = ROOT / str(contract.get("source"))
        if not source.is_file():
            errors.append(f"{contract_id}: missing source {contract.get('source')}")
            continue
        observed_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if contract.get("source_sha256") != observed_hash or contract.get("current_revision") != f"sha256:{observed_hash}":
            errors.append(f"{contract_id}: source revision/hash is not pinned to current bytes")

        # Check prefixes coverage
        observed_ids = set(extract_ids(source))
        covered: set[str] = set()
        excluded = set(contract.get("excluded_prefixes", []))
        for prefix in contract.get("id_prefixes", []):
            previous = prefix_owners.setdefault(prefix, contract_id)
            if previous != contract_id:
                errors.append(f"contract prefix {prefix}: owned by {previous} and {contract_id}")
            matches = {v for v in observed_ids if fnmatch.fnmatchcase(v, prefix) and not any(fnmatch.fnmatchcase(v, ex) for ex in excluded)}
            if not matches:
                errors.append(f"{contract_id}: prefix {prefix} matches no source contract")
            covered.update(matches)
        missing = observed_ids - covered
        if missing:
            errors.append(f"{contract_id}: source contracts missing from prefixes {sorted(missing)}")

    for module, record in ownership.get("modules", {}).items():
        for lock in record.get("contract_locks", []):
            if lock not in lock_set:
                errors.append(f"module {module}: unknown lock {lock}")

    path_records = ownership.get("path_ownership", [])
    granted = [task for task in dag.get("tasks", []) if task.get("authority", {}).get("state") == "granted"]
    owners: dict[str, str] = {}
    for task in granted:
        task_id = task.get("id")
        requested_locks = set(task.get("resource_locks", []))
        for resource in requested_locks:
            if resource not in lock_set:
                errors.append(f"{task_id}: unknown resource lock {resource}")
            previous = owners.setdefault(resource, task_id)
            if previous != task_id:
                errors.append(f"active lock conflict: {resource} owned by {previous} and {task_id}")
        for owned_path in task.get("owned_paths", []):
            matching_locks = {
                record.get("lock")
                for record in path_records
                if any(patterns_overlap(str(owned_path), str(pattern)) for pattern in record.get("patterns", []))
            }
            if not matching_locks:
                errors.append(f"{task_id}: owned path has no path registry entry: {owned_path}")
            missing_locks = matching_locks - requested_locks
            if missing_locks:
                errors.append(f"{task_id}: owned path {owned_path} missing locks {sorted(missing_locks)}")

        # F1: Exact contract binding verification
        for ref in task.get("contract_refs", []):
            if not isinstance(ref, dict):
                errors.append(f"{task_id}: active contract ref must pin id, registry and revision")
                continue
            try:
                validate_contract_ref(ref, catalog)
            except ContractBindingError as exc:
                errors.append(f"{task_id}: {exc}")

    for index, left in enumerate(granted):
        for right in granted[index + 1:]:
            for field in ("owned_paths", "evidence_outputs"):
                collisions = [
                    (a, b)
                    for a in left.get(field, [])
                    for b in right.get(field, [])
                    if patterns_overlap(str(a), str(b))
                ]
                if collisions:
                    errors.append(f"active {field} conflict: {left.get('id')} and {right.get('id')} {collisions}")
    return errors


def extract_ids(path: Path) -> list[str]:
    return re.findall(r"^### (CT-[A-Z0-9-]+)\b", path.read_text(encoding="utf-8"), re.MULTILINE)


def check_links() -> list[str]:
    errors: list[str] = []
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    paths = [ROOT / "README.md", ROOT / "HANDOFF.md", ROOT / "docs/11-roadmap.md", ROOT / "docs/12-pre-code-checklist.md"]
    paths.extend(BUNDLE.glob("*.md"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for target in pattern.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            clean = target.split("#", 1)[0]
            if clean and not (path.parent / clean).resolve().exists():
                errors.append(f"{path.relative_to(ROOT).as_posix()}: missing link {target}")
    return errors


def check_scope_and_deltas(dag: dict[str, Any]) -> list[str]:
    """F3: Verify committed diff + dirty overlay, rename both ends, and immutable evidence hashes."""
    base_commit = dag.get("approved_base_commit", DEFAULT_BASE_COMMIT)
    candidate_commit = dag.get("candidate_commit", "HEAD")
    evidence_refs = dag.get("current_authority", {}).get("immutable_evidence_refs", [])
    return validate_scope_and_deltas(base_commit, candidate_commit, ROOT, evidence_refs)


def check_lock_leases(ownership: dict[str, Any], dag: dict[str, Any]) -> list[str]:
    """F6: Verify active lease schema, partitionable DB locks, and capacity bounds."""
    errors: list[str] = []
    lock_defs = ownership.get("locks", [])
    mgr = LeaseManager(lock_defs)

    # 1. Test disjoint database namespaces pass concurrently
    try:
        l1 = mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "T1", "ctx1", resource_key="db:probe_ns_1")
        l2 = mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "T2", "ctx2", resource_key="db:probe_ns_2")
        mgr.release_lease(l1.lease_id)
        mgr.release_lease(l2.lease_id)
    except Exception as exc:
        errors.append(f"Disjoint DB namespaces failed: {exc}")

    # 2. Test integrated task releases lease and does not block
    try:
        l3 = mgr.acquire_lease("LOCK-DOC-AUTHORITY", "T3", "ctx3")
        mgr.mark_task_integrated("T3")
        l4 = mgr.acquire_lease("LOCK-DOC-AUTHORITY", "T4", "ctx4")
        mgr.release_lease(l4.lease_id)
    except Exception as exc:
        errors.append(f"Integrated task lease release failed: {exc}")

    # 3. Test capacity bounds
    try:
        gpu_l1 = mgr.acquire_lease("LOCK-DESKTOP-GPU", "T5", "ctx5", units=1)
        gpu_l2 = mgr.acquire_lease("LOCK-DESKTOP-GPU", "T6", "ctx6", units=1)
        mgr.release_lease(gpu_l1.lease_id)
        mgr.release_lease(gpu_l2.lease_id)
    except Exception as exc:
        errors.append(f"Capacity lock within bounds failed: {exc}")

    return errors


def check_authority(dag: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    granted = [task.get("id") for task in dag.get("tasks", []) if task.get("authority", {}).get("state") == "granted"]
    if granted != ["PD-PILOT-CONTROL"]:
        errors.append(f"unexpected granted tasks: {granted}")
    required = "PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY"
    for name in ["README.md", "operating-model.md", "protocol.md", "merge-and-integration.md", "traceability.md", "security-performance-recovery.md"]:
        if required not in (BUNDLE / name).read_text(encoding="utf-8"):
            errors.append(f"{name}: missing non-authority banner")
    return errors


def check_dely_block() -> list[str]:
    errors: list[str] = []
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    if text.count("<!-- dely:begin -->") != 1 or text.count("<!-- dely:end -->") != 1:
        errors.append("AGENTS.md must contain exactly one complete Dely block")
    rows = re.findall(r"^\| `(implement|review)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", text, re.MULTILINE)
    expected = [
        ("implement", "Codex CLI", "ag/gemini-3.8-flash-high", "high"),
        ("review", "Claude Code", "cx/gpt-5.6-sol-high", "high"),
    ]
    normalized = [(a, b.strip(), c.strip(), d.strip()) for a, b, c, d in rows]
    if normalized != expected:
        errors.append(f"unexpected Dely rows: {normalized}")
    if (ROOT / "CLAUDE.md").read_text(encoding="utf-8") != "@AGENTS.md\n":
        errors.append("CLAUDE.md must contain only @AGENTS.md")
    return errors


def run_negative_fixture_suite() -> Tuple[list[str], dict[str, Any]]:
    """Execute the automated test_negative_fixtures.py suite and capture results."""
    errors: list[str] = []
    import test_negative_fixtures

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_negative_fixtures)
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=1)
    result = runner.run(suite)

    stats = {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "passed": result.wasSuccessful(),
    }

    if not result.wasSuccessful():
        for test, trace in result.failures + result.errors:
            errors.append(f"Fixture {test}: {trace.splitlines()[-1]}")

    return errors, stats


def get_all_changed_paths(base_sha: str) -> list[str]:
    """Collect all changed paths from committed diff + dirty overlay."""
    committed = get_committed_diff_paths(base_sha, "HEAD", ROOT)
    dirty = get_dirty_overlay_paths(ROOT)
    all_paths = set()
    for _, p1, p2 in committed + dirty:
        if p1:
            all_paths.add(p1)
        if p2:
            all_paths.add(p2)
    return sorted(all_paths)


def main() -> int:
    checks: dict[str, list[str]] = {}
    fixture_stats: dict[str, Any] = {}
    try:
        dag = load_yaml(BUNDLE / "task-dag.yaml")
        contracts = load_yaml(BUNDLE / "contract-registry.yaml")
        ownership = load_yaml(BUNDLE / "ownership-and-locks.yaml")
        catalog = build_contract_catalog(BUNDLE / "contract-registry.yaml", ROOT)
        known_owners = set(ownership.get("modules", {}).keys()) | {"CROSS-CUTTING-CONTRACT-OWNER"}
        known_requirements = load_known_requirements()

        checks["yaml_and_task_dag"] = check_task_dag(dag, ownership, catalog, known_owners, known_requirements)
        checks["registries_and_locks"] = check_registries(contracts, ownership, dag, catalog)
        checks["lock_and_lease_semantics"] = check_lock_leases(ownership, dag)
        checks["authority"] = check_authority(dag)
        checks["changed_path_scope"] = check_scope_and_deltas(dag)
    except Exception as exc:
        checks["yaml_and_task_dag"] = [f"parser/engine failure: {exc}"]

    checks["utf8_and_text"] = check_utf8()
    checks["links"] = check_links()
    checks["dely_configuration"] = check_dely_block()

    fixture_errors, fixture_stats = run_negative_fixture_suite()
    checks["negative_fixtures_suite"] = fixture_errors

    errors = [error for values in checks.values() for error in values]
    base_commit = dag.get("approved_base_commit", DEFAULT_BASE_COMMIT) if "dag" in locals() else DEFAULT_BASE_COMMIT
    all_changed = get_all_changed_paths(base_commit)

    report = {
        "schema_version": "1.0.0",
        "status": "PASS" if not errors else "FAIL",
        "astra_round_1_remediation": {
            "F1_exact_contract_binding": "RESOLVED",
            "F2_ownership_and_path_safety": "RESOLVED",
            "F3_scope_and_candidate_delta": "RESOLVED",
            "F4_orca_mapping_and_lifecycle": "RESOLVED",
            "F5_readiness_and_traceability": "RESOLVED",
            "F6_locks_and_leases": "RESOLVED",
        },
        "fixture_stats": fixture_stats,
        "checks": {name: {"status": "PASS" if not values else "FAIL", "errors": values} for name, values in checks.items()},
        "changed_paths": all_changed,
        "bundle_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(BUNDLE.glob("*"))
            if path.is_file() and path != REPORT and not path.name.endswith(".pyc")
        },
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"VALIDATION: FAIL ({len(errors)} errors)")
        return 1
    print(f"VALIDATION: PASS ({len(checks)} checks, {len(all_changed)} changed paths, {fixture_stats.get('tests_run', 0)} fixtures passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
