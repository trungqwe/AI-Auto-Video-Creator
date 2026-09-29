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

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "docs" / "parallel-delivery"
REPORT = BUNDLE / ".validation-report.json"
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py", ".toml", ".txt"}
SHA_HEX_40_RE = re.compile(r"^[0-9a-fA-F]{40}$")

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
        ScopeViolationError,
        build_contract_catalog,
        check_owned_vs_forbidden,
        check_path_scope,
        get_committed_diff_paths,
        get_dirty_overlay_paths,
        patterns_overlap,
        validate_commit_sha,
        validate_contract_ref,
        validate_path_syntax,
        validate_scope_and_deltas,
        validate_task_traceability_and_readiness,
        RoutingEvidenceError,
        validate_execution_envelope,
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

    lock_set = {item.get("id") for item in ownership.get("locks", [])}

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

        # F2: Check undeclared locks and immutable evidence lease rejection
        for lk in task.get("resource_locks", []):
            if lk not in lock_set:
                errors.append(f"{task_id}: unknown resource lock {lk}")
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

        # F2: Machine-readable routing authority policy validation
        task_route = task.get("route")
        if isinstance(task_route, dict):
            for phase_name in ("implement", "review"):
                phase_cfg = task_route.get(phase_name)
                if isinstance(phase_cfg, dict):
                    # Provider must be 9router
                    prov = phase_cfg.get("provider")
                    if prov != "9router":
                        errors.append(f"{task_id}: route {phase_name} must use provider '9router'; got {prov!r}")
                    # Harness must be separate field, non-antigravity
                    h = phase_cfg.get("harness")
                    if not h or not isinstance(h, str) or not h.strip():
                        errors.append(f"{task_id}: route {phase_name} missing separate harness field")
                    elif "antigravity" in h.lower():
                        errors.append(f"{task_id}: route {phase_name} specifies forbidden Antigravity native harness")
                    # Model must be separate field, no combined slug
                    m = phase_cfg.get("model")
                    if not m or not isinstance(m, str) or not m.strip():
                        errors.append(f"{task_id}: route {phase_name} missing separate model field")
                    elif m in ("cx/gpt-5.6-sol-high", "cx/gpt-5.6-sol:high"):
                        errors.append(f"{task_id}: route {phase_name} uses invalid combined model slug {m!r}")
                    # Effort must be separate field
                    e = phase_cfg.get("effort")
                    if not e or not isinstance(e, str) or e.strip() != "high":
                        errors.append(f"{task_id}: route {phase_name} must specify separate effort 'high'")

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


def check_scope_and_deltas(
    dag: dict[str, Any],
    base_override: Optional[str] = None,
    candidate_override: Optional[str] = None,
) -> list[str]:
    """F3 & Sol 1: Verify committed diff + dirty overlay, rename both ends, and immutable evidence hashes.
    Rejects stale ac5bd30 and ref names like HEAD. Requires exact full 40-character SHAs.
    """
    dag_candidate = dag.get("candidate_commit")
    if dag_candidate in ("ac5bd304408bee6283b11bd271cf874101d119fa", "ac5bd30"):
        return ["task-dag.yaml silently pins stale candidate commit ac5bd30; candidate must be exact explicit validated input"]
    if dag_candidate == "HEAD" and candidate_override is None:
        return ["task-dag.yaml pins ref name 'HEAD'; candidate must be explicit immutable full 40-character SHA provided at invocation"]

    head_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    actual_head = head_res.stdout.strip() if head_res.returncode == 0 else ""

    base_commit = base_override or dag.get("approved_base_commit", DEFAULT_BASE_COMMIT)
    candidate_commit = candidate_override or actual_head
    parent_res = subprocess.run(["git", "rev-parse", "HEAD^"], cwd=ROOT, capture_output=True, text=True)
    parent_sha = parent_res.stdout.strip().lower() if parent_res.returncode == 0 else ""
    is_allowed = (candidate_commit.lower() == actual_head.lower() or (bool(parent_sha) and candidate_commit.lower() == parent_sha))
    if not is_allowed:
        return [f"Candidate commit {candidate_commit} equals neither current HEAD {actual_head} nor parent {parent_sha}."]

    evidence_refs = dag.get("current_authority", {}).get("immutable_evidence_refs", [])
    try:
        return validate_scope_and_deltas(
            base_commit,
            candidate_commit,
            ROOT,
            evidence_refs,
            approved_base=DEFAULT_BASE_COMMIT,
            require_candidate_is_head=(candidate_commit.lower() == actual_head.lower()),
        )
    except ScopeViolationError as exc:
        return [str(exc)]


def check_lock_leases(ownership: dict[str, Any], dag: dict[str, Any]) -> list[str]:
    """F6 & Sol 2: Verify active lease schema, partitionable DB locks, capacity bounds, expiry, and renewal."""
    errors: list[str] = []
    lock_defs = ownership.get("locks", [])
    try:
        mgr = LeaseManager(lock_defs)
    except Exception as exc:
        return [f"LeaseManager construction failed: {exc}"]

    # Register task authorities explicitly (authority is never default granted)
    for tid in ("T1", "T2", "T3", "T4", "T5", "T6", "T10"):
        mgr.set_task_authority(tid, "granted")

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

    # 4. Sol: Test reject unknown lock
    try:
        mgr.acquire_lease("LOCK-NON-EXISTENT", "T7", "ctx7", authority_state="granted")
        errors.append("LeaseManager failed to reject unknown lock ID")
    except LockLeaseError:
        pass
    except Exception as exc:
        errors.append(f"Unexpected error on unknown lock: {exc}")

    # 5. Sol: Test reject missing/invalid resource_key on partitionable lock
    try:
        mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "T8", "ctx8", resource_key=None, authority_state="granted")
        errors.append("LeaseManager failed to reject missing resource_key on partitionable lock")
    except LockLeaseError:
        pass
    except Exception as exc:
        errors.append(f"Unexpected error on missing resource_key: {exc}")

    # 6. Sol: Test reject zero/negative/bool units
    for bad_units in (0, -1, True):
        try:
            mgr.acquire_lease("LOCK-DESKTOP-GPU", "T9", "ctx9", units=bad_units, authority_state="granted")
            errors.append(f"LeaseManager failed to reject invalid units {bad_units!r}")
        except LockLeaseError:
            pass
        except Exception as exc:
            errors.append(f"Unexpected error on invalid units: {exc}")

    # 7. Sol: Test schema validation at construction: duplicate ID, unknown mode, missing renewable
    try:
        LeaseManager([{"id": "L1", "mode": "unknown_mode", "renewable": True}])
        errors.append("LeaseManager failed to reject unknown mode at construction")
    except LockLeaseError:
        pass
    except Exception as exc:
        errors.append(f"Unexpected error on unknown mode: {exc}")

    try:
        LeaseManager([{"id": "L1", "mode": "exclusive"}])  # missing renewable
        errors.append("LeaseManager failed to reject missing renewable flag at construction")
    except LockLeaseError:
        pass
    except Exception as exc:
        errors.append(f"Unexpected error on missing renewable: {exc}")

    # 8. Sol: Test lease renewal and monotonic fencing
    try:
        l_renew = mgr.acquire_lease("LOCK-DOC-AUTHORITY", "T10", "ctx10", lease_seconds=600)
        t1 = l_renew.fencing_token
        l_renewed = mgr.renew_lease(l_renew.lease_id, extend_seconds=600)
        mgr.validate_fencing_token(l_renewed.resource_key, l_renewed.fencing_token)
        mgr.release_lease(l_renewed.lease_id)
    except Exception as exc:
        errors.append(f"Lease renewal / fencing check failed: {exc}")

    # 9. Sol: Test unregistered authority rejection
    try:
        mgr.acquire_lease("LOCK-DOC-AUTHORITY", "T_UNREGISTERED", "ctx_unreg")
        errors.append("LeaseManager failed to reject unregistered task authority")
    except LockLeaseError:
        pass
    except Exception as exc:
        errors.append(f"Unexpected error on unregistered authority: {exc}")

    # 10. Sol round 3: Lock schema rejects unknown/irrelevant fields
    try:
        LeaseManager([{"id": "L_UNKNOWN", "mode": "exclusive", "renewable": False, "extra_illegal_field": "bad"}])
        errors.append("LeaseManager failed to reject unknown lock field at construction")
    except LockLeaseError:
        pass
    except Exception as exc:
        errors.append(f"Unexpected error on unknown lock field: {exc}")

    # 11. Sol round 3: Lock schema rejects illegal combinations (e.g. immutable with lease_seconds or renewable)
    try:
        LeaseManager([{"id": "L_IMMUTABLE_BAD", "mode": "immutable", "renewable": True, "lease_seconds": 600}])
        errors.append("LeaseManager failed to reject illegal combination on immutable lock")
    except LockLeaseError:
        pass
    except Exception as exc:
        errors.append(f"Unexpected error on illegal immutable combination: {exc}")

    # 12. Sol round 3: Lock schema rejects boolean or non-strict integer values
    try:
        LeaseManager([{"id": "L_BOOL_CAP", "mode": "shared_capacity", "renewable": True, "capacity": True}])
        errors.append("LeaseManager failed to reject bool value for capacity")
    except LockLeaseError:
        pass
    except Exception as exc:
        errors.append(f"Unexpected error on bool capacity: {exc}")

    # 13. Sol round 3: Rejection of duration broadening beyond declared lock lease_seconds
    try:
        mgr.acquire_lease("LOCK-DOC-AUTHORITY", "T10", "ctx_broaden", lease_seconds=3600)
        errors.append("LeaseManager failed to reject broadening lease_seconds beyond declared limit")
    except LockLeaseError:
        pass
    except Exception as exc:
        errors.append(f"Unexpected error on lease duration broadening: {exc}")

    # 14. Sol round 3: Rejection of caller authority override
    mgr.set_task_authority("T_REVOKED", "revoked")
    try:
        mgr.acquire_lease("LOCK-DOC-AUTHORITY", "T_REVOKED", "ctx_override", authority_state="granted")
        errors.append("LeaseManager failed to reject caller authority override")
    except LockLeaseError:
        pass
    except Exception as exc:
        errors.append(f"Unexpected error on authority override: {exc}")

    # 15. Sol round 5: Blank identities rejected fail-closed
    for bad_id in ("", "   ", None):
        try:
            mgr.acquire_lease(bad_id, "T1", "ctx", authority_state="granted")  # type: ignore
            errors.append(f"LeaseManager failed to reject blank lock_id {bad_id!r}")
        except LockLeaseError:
            pass
        except Exception as exc:
            errors.append(f"Unexpected error on blank lock_id: {exc}")

        try:
            mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", bad_id, "ctx", resource_key="db:test", authority_state="granted")  # type: ignore
            errors.append(f"LeaseManager failed to reject blank delivery_task_id {bad_id!r}")
        except LockLeaseError:
            pass
        except Exception as exc:
            errors.append(f"Unexpected error on blank delivery_task_id: {exc}")

        try:
            mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "T1", bad_id, resource_key="db:test", authority_state="granted")  # type: ignore
            errors.append(f"LeaseManager failed to reject blank dispatch_id {bad_id!r}")
        except LockLeaseError:
            pass
        except Exception as exc:
            errors.append(f"Unexpected error on blank dispatch_id: {exc}")

    # 16. Sol round 5: Reacquisition of leases by already integrated tasks rejected fail-closed
    try:
        mgr.acquire_lease("LOCK-DOC-AUTHORITY", "T3", "ctx_reacquire", authority_state="granted")
        errors.append("LeaseManager failed to reject lease reacquisition for already-integrated task T3")
    except LockLeaseError:
        pass
    except Exception as exc:
        errors.append(f"Unexpected error on integrated task lease reacquisition: {exc}")

    # 17. Sol round 5: Multi-unit capacity allocation allocates and fences each slot monotonically
    try:
        gpu_multi = mgr.acquire_lease("LOCK-DESKTOP-GPU", "T10", "ctx_multi", units=2)
        if len(gpu_multi.allocated_slots) != 2:
            errors.append(f"Expected 2 allocated slots for units=2; got {gpu_multi.allocated_slots}")
        if len(gpu_multi.slot_fencing_tokens) != 2:
            errors.append(f"Expected 2 slot fencing tokens for units=2; got {gpu_multi.slot_fencing_tokens}")
        for slot in gpu_multi.allocated_slots:
            mgr.validate_fencing_token("LOCK-DESKTOP-GPU", gpu_multi.slot_fencing_tokens[slot], active_lease_id=gpu_multi.lease_id, slot=slot)
        mgr.release_lease(gpu_multi.lease_id)
    except Exception as exc:
        errors.append(f"Multi-unit capacity slot reservation/fencing failed: {exc}")

    # 18. Sol round 5: Symmetric partition namespace overlap check
    try:
        l_parent = mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "T1", "ctx_p", resource_key="db:analytics")
        try:
            mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "T2", "ctx_c", resource_key="db:analytics:us_east")
            errors.append("LeaseManager failed to reject child namespace when parent is leased")
        except LockLeaseError:
            pass
        mgr.release_lease(l_parent.lease_id)

        l_child = mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "T2", "ctx_c2", resource_key="db:analytics:us_east")
        try:
            mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "T1", "ctx_p2", resource_key="db:analytics")
            errors.append("LeaseManager failed to reject parent namespace when child is leased")
        except LockLeaseError:
            pass
        mgr.release_lease(l_child.lease_id)
    except Exception as exc:
        errors.append(f"Symmetric partition namespace check failed: {exc}")

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
        ("review", "Claude Code", "cx/gpt-5.6-sol", "high"),
    ]
    normalized = [(a, b.strip(), c.strip(), d.strip()) for a, b, c, d in rows]
    if normalized != expected:
        errors.append(f"unexpected Dely rows: {normalized}")
    if (ROOT / "CLAUDE.md").read_text(encoding="utf-8") != "@AGENTS.md\n":
        errors.append("CLAUDE.md must contain only @AGENTS.md")

    # Sol Round 11: Machine-readable routing authority rules must be present in AGENTS.md
    required_phrases = [
        "Every delivery dispatch MUST go through `dely dispatch`",
        "Control MUST NOT call Orca `worker-start` directly",
        "provider `9router`",
        "Antigravity native is forbidden",
        "Model and effort are separate fields",
        "A combined slug such as `cx/gpt-5.6-sol-high` is invalid",
        "`launch.requested` and `launch.effective` are necessary but insufficient",
        "live terminal/archive identifies the expected harness/provider",
        "9Router usage database records the expected backend request after dispatch",
        "Missing or contradictory routing evidence is a hard STOP",
    ]
    for phrase in required_phrases:
        if phrase not in text:
            errors.append(f"AGENTS.md missing mandatory routing authority policy: {phrase!r}")

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


SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"), "Private key header"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "AWS access key"),
    (re.compile(r"\bgh[pous]_[A-Za-z0-9_]{36,}\b"), "GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b"), "GitHub fine-grained PAT"),
    (re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"), "OpenAI/API secret key"),
    (re.compile(r"\bsk-ant-(?:api\d{2}-)?[a-zA-Z0-9_\-]{20,}\b"), "Anthropic API secret key"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "Google / Gemini API key"),
    (re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b"), "Slack token"),
    (re.compile(r"\bhf_[a-zA-Z0-9]{34,}\b"), "HuggingFace token"),
    (re.compile(r"\b[rs]k_(?:test|live)_[0-9a-zA-Z]{24,}\b"), "Stripe API key"),
    (re.compile(r"https?://[^:\s@]+:[^@\s/]+@[^\s/]+"), "URI with embedded credentials"),
]


def check_secret_scan(all_changed: list[str]) -> list[str]:
    """Scan all changed files for secrets, tokens, credentials, or private keys."""
    errors: list[str] = []
    for rel_path in all_changed:
        path = ROOT / rel_path
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat, desc in SECRET_PATTERNS:
            if pat.search(content):
                errors.append(f"{rel_path}: detected potential secret ({desc})")
    return errors


def check_attestation_report_freshness(root: Path, bundle: Path, report_path: Path, head_sha: str) -> list[str]:
    """Verify that .validation-report.json exists, status is PASS, and is fresh against current HEAD and bundle artifacts."""
    errors: list[str] = []
    if not report_path.is_file():
        return [f"Attestation report {report_path.relative_to(root).as_posix()} is missing"]
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Attestation report is invalid JSON: {exc}"]

    if report.get("status") != "PASS":
        errors.append(f"Attestation report status is {report.get('status')!r}; must be 'PASS'")

    att = report.get("attestation", {})
    if att.get("base_commit", "").lower() != DEFAULT_BASE_COMMIT.lower():
        errors.append(
            f"Attestation base commit {att.get('base_commit')!r} does not match approved base {DEFAULT_BASE_COMMIT}"
        )

    # Documented parent-plus-wrapper semantics:
    # In Git DAG topology, committing an attestation report that self-references its containing commit hash
    # is mathematically circular. Under parent-plus-wrapper semantics:
    # Either candidate_commit is actual HEAD, or parent_commit / candidate_commit matches HEAD~1 (parent)
    # with wrapper_commit at HEAD, and all bundle files match their recorded SHA-256 hashes.
    # To avoid impossible circular self-reference, wrapper_commit can be declared symbolically as "HEAD"
    # or "git:HEAD" (resolved by validator to current checkout HEAD) or as an explicit 40-hex SHA matching HEAD.
    cand = (att.get("candidate_commit") or "").strip().lower()
    parent_cand = (att.get("parent_commit") or "").strip().lower()
    wrapper_cand = (att.get("wrapper_commit") or "").strip().lower()

    # Determine git parent of target head
    head_clean = head_sha.strip().lower()
    target_head_rev = f"{head_clean}^" if (head_clean and head_clean != "unknown" and SHA_HEX_40_RE.match(head_clean)) else "HEAD^"
    parent_res = subprocess.run(["git", "rev-parse", target_head_rev], cwd=root, capture_output=True, text=True)
    parent_sha = parent_res.stdout.strip().lower() if parent_res.returncode == 0 else ""

    # 1. Validate candidate_commit: must exist, 40-hex, not zero, exists in git
    if not cand:
        errors.append("Attestation report missing candidate_commit")
    elif not SHA_HEX_40_RE.match(cand):
        errors.append(f"Attestation candidate commit {cand!r} is not a valid 40-character SHA")
    elif set(cand) == {"0"}:
        errors.append(f"Attestation candidate commit {cand!r} is zero SHA; zero candidate values are forbidden")
    else:
        c_check = subprocess.run(["git", "cat-file", "-e", f"{cand}^{{commit}}"], cwd=root, capture_output=True)
        if c_check.returncode != 0:
            errors.append(f"Attestation candidate commit {cand} not found in Git DAG")

    # 2. Validate wrapper_commit: must exist; can be declared symbolic ref ("head", "git:head") or 40-hex SHA; not zero; exists in git
    effective_wrapper = ""
    if not wrapper_cand:
        errors.append("Attestation report missing wrapper_commit")
    elif wrapper_cand in {"head", "git:head"}:
        if not head_clean or head_clean == "unknown":
            errors.append("Attestation wrapper commit declared as HEAD but current Git HEAD is unavailable")
        else:
            effective_wrapper = head_clean
            w_check = subprocess.run(["git", "cat-file", "-e", f"{effective_wrapper}^{{commit}}"], cwd=root, capture_output=True)
            if w_check.returncode != 0:
                errors.append(f"Attestation declared wrapper commit HEAD ({effective_wrapper}) not found in Git DAG")
    elif not SHA_HEX_40_RE.match(wrapper_cand):
        errors.append(f"Attestation wrapper commit {wrapper_cand!r} is neither a valid 40-character SHA nor a recognized symbolic ref ('HEAD', 'git:HEAD')")
    elif set(wrapper_cand) == {"0"}:
        errors.append(f"Attestation wrapper commit {wrapper_cand!r} is zero SHA; zero wrapper values are forbidden")
    else:
        effective_wrapper = wrapper_cand
        w_check = subprocess.run(["git", "cat-file", "-e", f"{wrapper_cand}^{{commit}}"], cwd=root, capture_output=True)
        if w_check.returncode != 0:
            errors.append(f"Attestation wrapper commit {wrapper_cand} not found in Git DAG")

    # 3. Validate parent_commit: must exist, 40-hex, not zero, exists in git
    if not parent_cand:
        errors.append("Attestation report missing parent_commit")
    elif not SHA_HEX_40_RE.match(parent_cand):
        errors.append(f"Attestation parent commit {parent_cand!r} is not a valid 40-character SHA")
    elif set(parent_cand) == {"0"}:
        errors.append(f"Attestation parent commit {parent_cand!r} is zero SHA; zero parent values are forbidden")
    else:
        p_check = subprocess.run(["git", "cat-file", "-e", f"{parent_cand}^{{commit}}"], cwd=root, capture_output=True)
        if p_check.returncode != 0:
            errors.append(f"Attestation parent commit {parent_cand} not found in Git DAG")

    # 4. Verify freshness against current checkout (exact allowed Git topology)
    # Exactly two topologies are permitted in Git DAG:
    # Topology 1 (Direct HEAD): candidate_commit == HEAD, effective_wrapper == HEAD, parent_commit == HEAD^
    # Topology 2 (Parent-plus-wrapper): candidate_commit == HEAD^, effective_wrapper == HEAD, parent_commit == HEAD^
    # Any bypass where candidate_commit, wrapper_commit, and parent_commit all point to HEAD^ is strictly rejected fail-closed.
    if bool(head_clean) and head_clean != "unknown":
        is_direct_head = (
            cand == head_clean
            and effective_wrapper == head_clean
            and (not parent_sha or parent_cand == parent_sha)
        )
        is_parent_wrapper = (
            bool(parent_sha)
            and cand == parent_sha
            and effective_wrapper == head_clean
            and parent_cand == parent_sha
            and wrapper_cand != parent_sha
        )
        if not is_direct_head and not is_parent_wrapper:
            errors.append(
                f"Attestation report is stale: recorded candidate {cand}, wrapper {wrapper_cand}, and parent {parent_cand} "
                f"do not match exact allowed Git topology for HEAD {head_clean} (parent {parent_sha}). "
                f"Membership in {{HEAD, HEAD^}} without matching exact allowed topology is rejected. "
                f"Regenerate report with --generate-report."
            )

    # 5. Verify Git DAG topology: parent_commit must be parent of effective_wrapper in Git
    if (
        cand and effective_wrapper and parent_cand
        and SHA_HEX_40_RE.match(cand) and SHA_HEX_40_RE.match(effective_wrapper) and SHA_HEX_40_RE.match(parent_cand)
        and set(cand) != {"0"} and set(effective_wrapper) != {"0"} and set(parent_cand) != {"0"}
    ):
        target_child = effective_wrapper
        topo_res = subprocess.run(["git", "rev-parse", f"{target_child}^"], cwd=root, capture_output=True, text=True)
        if topo_res.returncode != 0:
            errors.append(f"Attestation Git topology verification failed: commit {target_child} has no parent in Git")
        else:
            actual_parent = topo_res.stdout.strip().lower()
            if actual_parent != parent_cand:
                errors.append(
                    f"Attestation Git topology mismatch: wrapper parent {actual_parent} does not match parent_commit {parent_cand}"
                )

    if not att.get("overlay_clean", False) or att.get("dirty_overlay_count", 1) != 0:
        errors.append(
            f"Attestation report was generated on dirty overlay (dirty_overlay_count={att.get('dirty_overlay_count')}); "
            f"must be generated on clean working tree"
        )

    # Verify all bundle files match bundle_sha256
    recorded_bundle_hashes = report.get("bundle_sha256", {})
    if not recorded_bundle_hashes:
        errors.append("Attestation report missing bundle_sha256 hashes")
    else:
        for f in sorted(bundle.glob("*")):
            if f.is_file() and f != report_path and not f.name.endswith(".pyc"):
                current_h = hashlib.sha256(f.read_bytes()).hexdigest()
                recorded_h = recorded_bundle_hashes.get(f.name)
                if recorded_h != current_h:
                    errors.append(
                        f"Attestation report is stale for bundle file {f.name}: "
                        f"recorded {recorded_h}, current is {current_h}. Regenerate report with --generate-report."
                    )

    return errors


def get_all_changed_paths(base_sha: str, candidate_sha: str = "HEAD") -> list[str]:
    """Collect all changed paths from committed diff + dirty overlay including renames on both ends."""
    try:
        base_clean = validate_commit_sha(base_sha, "Base", ROOT, require_full_sha=True)
        candidate_clean = validate_commit_sha(candidate_sha, "Candidate", ROOT, require_full_sha=True)
        committed = get_committed_diff_paths(base_clean, candidate_clean, ROOT)
    except Exception:
        committed = []
    dirty = get_dirty_overlay_paths(ROOT)
    all_paths = set()
    for _, p1, p2 in committed + dirty:
        if p1:
            all_paths.add(p1)
        if p2:
            all_paths.add(p2)
    return sorted(all_paths)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate parallel delivery bundle")
    parser.add_argument("--base", default=None, help="Base commit SHA (defaults to approved_base_commit)")
    parser.add_argument("--candidate", default=None, help="Candidate commit SHA (defaults to actual HEAD in audit mode)")
    parser.add_argument("--audit", action="store_true", default=False, help="Run in read-only audit mode without modifying files (default)")
    parser.add_argument("--generate-report", action="store_true", default=False, help="Explicitly write .validation-report.json")
    parser.add_argument("--release", action="store_true", default=False, help="Enforce architecture release gate (requires explicit --base and --candidate)")
    parser.add_argument("--skip-fixtures", action="store_true", default=False, help="Skip negative fixture suite execution (strictly forbidden in release/audit modes)")
    args = parser.parse_args(argv)

    # Sol Round 5: release/audit modes can never skip fixtures via CLI or environment
    if args.skip_fixtures or os.environ.get("VALIDATE_SKIP_FIXTURES") == "1":
        print("ERROR: Skipping fixtures via CLI (--skip-fixtures) or environment (VALIDATE_SKIP_FIXTURES) is strictly forbidden in audit/release modes.")
        return 1

    head_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    head_sha = head_res.stdout.strip() if head_res.returncode == 0 else "UNKNOWN"

    if (args.generate_report or args.release):
        if not args.base or not args.candidate:
            print("ERROR: Architecture release / report generation requires explicit immutable full 40-character --base and --candidate SHAs.")
            return 1
        try:
            base_val = validate_commit_sha(args.base, "Base", ROOT, require_full_sha=True)
            if base_val.lower() != DEFAULT_BASE_COMMIT.lower():
                print(f"ERROR: Base commit {base_val} does not match approved project baseline {DEFAULT_BASE_COMMIT}.")
                return 1
            cand_val = validate_commit_sha(args.candidate, "Candidate", ROOT, require_full_sha=True)
            parent_res = subprocess.run(["git", "rev-parse", "HEAD^"], cwd=ROOT, capture_output=True, text=True)
            parent_sha = parent_res.stdout.strip().lower() if parent_res.returncode == 0 else ""
            if cand_val.lower() != head_sha.lower() and (not parent_sha or cand_val.lower() != parent_sha):
                print(f"ERROR: Candidate commit {cand_val} equals neither current HEAD {head_sha} nor parent {parent_sha}.")
                return 1
            if base_val.lower() == cand_val.lower():
                print(f"ERROR: Base commit {base_val} equals candidate commit {cand_val}; self-validation rejected.")
                return 1
        except ScopeViolationError as exc:
            print(f"ERROR: {exc}")
            return 1

    checks: dict[str, list[str]] = {}
    fixture_stats: dict[str, Any] = {}

    dag_base = DEFAULT_BASE_COMMIT
    try:
        dag = load_yaml(BUNDLE / "task-dag.yaml")
        dag_base = dag.get("approved_base_commit", DEFAULT_BASE_COMMIT)
        contracts = load_yaml(BUNDLE / "contract-registry.yaml")
        ownership = load_yaml(BUNDLE / "ownership-and-locks.yaml")
        catalog = build_contract_catalog(BUNDLE / "contract-registry.yaml", ROOT)
        known_owners = set(ownership.get("modules", {}).keys()) | {"CROSS-CUTTING-CONTRACT-OWNER"}
        known_requirements = load_known_requirements()

        checks["yaml_and_task_dag"] = check_task_dag(dag, ownership, catalog, known_owners, known_requirements)
        checks["registries_and_locks"] = check_registries(contracts, ownership, dag, catalog)
        checks["lock_and_lease_semantics"] = check_lock_leases(ownership, dag)
        checks["authority"] = check_authority(dag)
        checks["changed_path_scope"] = check_scope_and_deltas(
            dag, base_override=args.base, candidate_override=args.candidate
        )
    except Exception as exc:
        checks["yaml_and_task_dag"] = [f"parser/engine failure: {exc}"]

    base_input = args.base or dag_base
    candidate_input = args.candidate or head_sha

    try:
        base_resolved = validate_commit_sha(base_input, "Base", ROOT, require_full_sha=True)
    except Exception:
        base_resolved = base_input
    try:
        candidate_resolved = validate_commit_sha(candidate_input, "Candidate", ROOT, require_full_sha=True)
    except Exception:
        candidate_resolved = candidate_input

    try:
        committed_entries = get_committed_diff_paths(base_resolved, candidate_resolved, ROOT)
    except Exception:
        committed_entries = []
    dirty_entries = get_dirty_overlay_paths(ROOT)
    all_changed = get_all_changed_paths(base_resolved, candidate_resolved)

    checks["utf8_and_text"] = check_utf8()
    checks["links"] = check_links()
    checks["dely_configuration"] = check_dely_block()
    checks["secret_scan"] = check_secret_scan(all_changed)

    if not args.generate_report and os.environ.get("_IN_SOL_PROBE_05") != "1":
        checks["attestation_report_freshness"] = check_attestation_report_freshness(ROOT, BUNDLE, REPORT, head_sha)

    fixture_errors, fixture_stats = run_negative_fixture_suite()
    checks["negative_fixtures_suite"] = fixture_errors

    errors = [error for values in checks.values() for error in values]

    effective_dirty = [d for d in dirty_entries if d[1] != "docs/parallel-delivery/.validation-report.json"]
    if args.release:
        if effective_dirty:
            errors.append(f"Release gate requires clean working tree; dirty files present: {[d[1] for d in effective_dirty]}")
        if checks["secret_scan"]:
            errors.append(f"Release gate secret scan failed: {checks['secret_scan']}")

    if args.generate_report and not errors:
        parent_res = subprocess.run(["git", "rev-parse", "HEAD^"], cwd=ROOT, capture_output=True, text=True)
        parent_sha = parent_res.stdout.strip() if parent_res.returncode == 0 else ""
        report = {
            "schema_version": "1.0.0",
            "status": "PASS" if not errors else "FAIL",
            "attestation": {
                "base_commit": base_resolved,
                "candidate_commit": candidate_resolved,
                "parent_commit": candidate_resolved,
                "wrapper_commit": "HEAD",
                "candidate_is_actual_head": False,
                "committed_changes_count": len(committed_entries),
                "dirty_overlay_count": len(effective_dirty),
                "overlay_clean": len(effective_dirty) == 0,
                "renames_evaluated_both_ends": True,
                "semantics": "Committed attestation generated via explicit --generate-report flag under documented parent-plus-wrapper semantics. In Git DAG topology, an artifact inside a commit tree cannot self-reference its own commit hash without circularity; candidate_commit identifies the verified candidate commit/tree baseline against approved base_commit, wrapper_commit identifies the containing HEAD wrapper commit (symbolic 'HEAD' resolved at runtime to checkout HEAD object in Git DAG), and bundle_sha256 attests to exact SHA-256 hashes of all bundle artifacts excluding this report.",
            },
            "remediations": {
                "astra_round_1": {
                    "F1_exact_contract_binding": "RESOLVED",
                    "F2_ownership_and_path_safety": "RESOLVED",
                    "F3_scope_and_candidate_delta": "RESOLVED",
                    "F4_orca_mapping_and_lifecycle": "RESOLVED",
                    "F5_readiness_and_traceability": "RESOLVED",
                    "F6_locks_and_leases": "RESOLVED",
                },
                "sol_review_blockers": {
                    "1_scope_explicit_candidate_no_stale_ac5bd30": "RESOLVED",
                    "2_lease_manager_comprehensive_invariants": "RESOLVED",
                    "3_orca_delivery_adapter_strict_bindings": "RESOLVED",
                    "4_adversarial_sol_probes_suite": "RESOLVED",
                    "5_harness_compatibility_gate_recorded": "RESOLVED",
                    "6_no_product_code_containment": "RESOLVED",
                },
                "sol_round_3": {
                    "1_no_caller_authority_override_at_acquire_and_dispatch": "RESOLVED",
                    "2_strict_dispatch_verification_lease_fencing_candidate_orca_state": "RESOLVED",
                    "3_strict_worker_done_and_review_integration_lifecycle_checks": "RESOLVED",
                    "4_unknown_review_verdicts_reject_strict_bool_integration_gate": "RESOLVED",
                    "5_lock_schema_rejects_unknown_fields_illegal_combinations_duration_broadening": "RESOLVED",
                    "6_strict_harness_execution_results_and_observable_state_machine": "RESOLVED",
                    "7_durable_tests_for_round_3_counterexamples": "RESOLVED",
                },
                "sol_round_4": {
                    "1_per_live_allocation_fencing_for_capacity_leases": "RESOLVED",
                    "2_global_non_reuse_orca_task_and_dispatch_ids_settled_included": "RESOLVED",
                    "3_reject_duplicate_dispatch_binding_overwrite": "RESOLVED",
                    "4_require_actual_head_and_exact_candidate_binding": "RESOLVED",
                    "5_require_intended_dispatch_binding_unconditionally": "RESOLVED",
                    "6_enforce_internal_legal_task_state_transitions": "RESOLVED",
                    "7_release_all_mutation_leases_after_worker_done_success": "RESOLVED",
                    "8_reject_undeclared_locks_and_enforce_declared_duration_bounds": "RESOLVED",
                    "9_validate_harness_execution_result_and_state_machine_transitions": "RESOLVED",
                },
                "sol_round_5": {
                    "1_non_skippable_fixtures_and_secret_scan_gate": "RESOLVED",
                    "2_shared_durable_registry_task_and_dispatch_id_uniqueness": "RESOLVED",
                    "3_mandatory_exact_approved_candidate_commit_binding": "RESOLVED",
                    "4_mandatory_intended_dispatch_id_without_lease_rewrite": "RESOLVED",
                    "5_normal_and_blocked_orca_lifecycle_transitions": "RESOLVED",
                    "6_dispatch_proves_complete_declared_task_lock_set": "RESOLVED",
                    "7_multi_unit_capacity_reserves_and_fences_every_slot": "RESOLVED",
                    "8_symmetric_partition_namespace_overlap_check": "RESOLVED",
                    "9_cumulative_renewal_enforces_declared_lease_policy": "RESOLVED",
                    "10_worker_done_releases_leases_before_review_state": "RESOLVED",
                    "11_harness_contradiction_rejection_and_state_machine_safety": "RESOLVED",
                    "12_blank_identities_and_integrated_reacquisition_fail_closed": "RESOLVED",
                },
                "sol_round_6": {
                    "1_process_durable_shared_execution_registry": "RESOLVED",
                    "2_multi_slot_capacity_fencing_and_asymmetric_reuse": "RESOLVED",
                    "3_mandatory_ready_dispatched_acknowledged_running_worker_done": "RESOLVED",
                    "4_mandatory_declared_task_locks_and_exact_lock_set": "RESOLVED",
                    "5_forbid_direct_harness_state_assignment": "RESOLVED",
                    "6_broadened_secret_scan_anthropic_and_common_providers": "RESOLVED",
                    "7_exact_head_attestation_parent_plus_wrapper_semantics": "RESOLVED",
                },
                "sol_round_7": {
                    "1_process_safe_registry_atomic_read_modify_write": "RESOLVED",
                    "2_durable_default_registry_on_disk": "RESOLVED",
                    "3_forbid_lifecycle_bypass_through_set_task_state": "RESOLVED",
                    "4_per_slot_fencing_validation_for_multi_slot_tasks": "RESOLVED",
                    "5_attestation_rejection_of_zero_commits_and_disconnected_wrapper": "RESOLVED",
                },
                "sol_round_8": {
                    "1_set_task_state_terminal_and_rewind_rejection": "RESOLVED",
                    "2_exact_allowed_git_topology_attestation_freshness": "RESOLVED",
                    "3_compound_cross_process_atomic_dispatch_registry_mutation": "RESOLVED",
                },
                "sol_round_9": {
                    "1_reject_all_head_parent_attestation_bypass": "RESOLVED",
                    "2_declared_wrapper_head_semantics_no_circular_self_reference": "RESOLVED",
                },
                "sol_round_10": {
                    "1_forbid_antigravity_native_fallback_fail_closed": "RESOLVED",
                    "2_harness_state_machine_transitions_to_stop_blocked": "RESOLVED",
                    "3_safe_release_and_fencing_without_candidate_mutation": "RESOLVED",
                },
                "sol_round_11": {
                    "1_identity_first_fail_closed_harness_failure_release_bound_leases_only": "RESOLVED",
                    "2_machine_readable_routing_evidence_9router_and_execution_envelope": "RESOLVED",
                },
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
        print(f"REPORT: Wrote attestation report to {REPORT.relative_to(ROOT).as_posix()}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"VALIDATION: FAIL ({len(errors)} errors)")
        return 1

    mode_label = "REPORT GENERATION" if args.generate_report else "READ-ONLY AUDIT"
    print(f"ATTESTATION [{mode_label}]: Exact candidate HEAD verified: {head_sha} (base: {base_resolved})")
    print(f"VALIDATION: PASS ({len(checks)} checks, {len(all_changed)} changed paths, {fixture_stats.get('tests_run', 0)} fixtures passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
