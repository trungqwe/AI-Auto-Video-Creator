#!/usr/bin/env python3
"""Delivery engine and validation logic for parallel delivery control plane.

Implements remediation for Astra audit round 1:
- F1: Exact contract binding (registry, source, owner, hash verification)
- F2: Ownership & path safety (reject absolute/traversal/aliases, check owned vs forbidden, immutable evidence)
- F3: Scope & candidate delta (pin approved base/candidate, committed diff + dirty overlay, rename both ends, immutable evidence)
- F4: Orca mapping & lifecycle (separate delivery task ID from Orca execution, worker_done CLI outcome, fresh dispatch on resume, duplicate/stale rejection)
- F5: Readiness & traceability (validate real refs, readiness predicate, reject fake IDs and locked->ready)
- F6: Locks & leases (active lease schema vs declaration, integrated tasks hold no lease, disjoint DB namespaces, capacity bounds)
"""
from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ParallelDeliveryError(Exception):
    """Base error for parallel delivery validation and runtime checks."""


class ContractBindingError(ParallelDeliveryError):
    """F1: Exact contract binding violation."""


class OwnershipPathError(ParallelDeliveryError):
    """F2: Path safety or ownership conflict."""


class ScopeViolationError(ParallelDeliveryError):
    """F3: Changed path outside approved scope or touching forbidden paths."""


class ProtocolViolationError(ParallelDeliveryError):
    """F4: Orca protocol or lifecycle transition violation."""


class DuplicateResultError(ProtocolViolationError):
    """F4: Duplicate worker_done received for an already settled dispatch."""


class StaleResultError(ProtocolViolationError):
    """F4: Result received with a stale fencing token or obsolete dispatch ID."""


class ReadinessTraceabilityError(ParallelDeliveryError):
    """F5: Readiness predicate or traceability reference violation."""


class LockLeaseError(ParallelDeliveryError):
    """F6: Resource lock or active lease acquisition conflict."""


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ContractBinding:
    id: str
    registry_id: str
    source_path: str
    owner: str
    co_owners: List[str]
    source_sha256: str
    revision: str


@dataclass
class ActiveLease:
    lease_id: str
    lock_id: str
    resource_key: str
    units: int
    fencing_token: int
    delivery_task_id: str
    dispatch_id: str
    acquired_at: str
    expires_at: Optional[str] = None
    is_active: bool = True


# ---------------------------------------------------------------------------
# Path Helper Functions (F2 & F3)
# ---------------------------------------------------------------------------

def validate_path_syntax(path: str) -> None:
    """Validate path syntax. Reject absolute paths, traversal, and canonical aliases."""
    if not path:
        raise OwnershipPathError("Empty path is invalid")
    # Reject backslashes
    if "\\" in path:
        raise OwnershipPathError(f"Path {path!r} contains forbidden backslash; must use '/'")
    # Reject absolute paths (Unix or Windows drive)
    if path.startswith("/"):
        raise OwnershipPathError(f"Path {path!r} is absolute; absolute paths are forbidden")
    if re.match(r"^[a-zA-Z]:", path):
        raise OwnershipPathError(f"Path {path!r} is absolute Windows drive path; forbidden")
    # Reject traversal (..)
    parts = path.split("/")
    if ".." in parts:
        raise OwnershipPathError(f"Path {path!r} contains directory traversal '..'; forbidden")
    # Reject canonical aliases: ./ or // or trailing /.
    if path.startswith("./"):
        raise OwnershipPathError(f"Path {path!r} starts with redundant './'; forbidden")
    if "//" in path:
        raise OwnershipPathError(f"Path {path!r} contains redundant '//'; forbidden")
    if "." in parts:
        raise OwnershipPathError(f"Path {path!r} contains redundant '.' segment; forbidden")


def compile_glob(pattern: str) -> re.Pattern[str]:
    translated = re.escape(pattern)
    translated = translated.replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.compile(f"^{translated}$")


def patterns_overlap(left: str, right: str) -> bool:
    """Determine whether two glob patterns can match the same path."""
    if left == right or left == "**" or right == "**":
        return True
    left_wild = any(c in left for c in "*?")
    right_wild = any(c in right for c in "*?")
    if not left_wild and compile_glob(right).fullmatch(left):
        return True
    if not right_wild and compile_glob(left).fullmatch(right):
        return True
    if left_wild and right_wild:
        left_samples = [
            left.replace("**", "probe/deep").replace("*", "probe").replace("?", "x"),
            left.replace("**", "probe").replace("*", "probe").replace("?", "x"),
        ]
        right_samples = [
            right.replace("**", "probe/deep").replace("*", "probe").replace("?", "x"),
            right.replace("**", "probe").replace("*", "probe").replace("?", "x"),
        ]
        if any(compile_glob(right).fullmatch(s) for s in left_samples):
            return True
        if any(compile_glob(left).fullmatch(s) for s in right_samples):
            return True
    left_prefix = left.split("*", 1)[0].split("?", 1)[0].rstrip("/")
    right_prefix = right.split("*", 1)[0].split("?", 1)[0].rstrip("/")
    return bool(
        left_prefix and right_prefix and (
            left_prefix == right_prefix
            or left_prefix.startswith(right_prefix + "/")
            or right_prefix.startswith(left_prefix + "/")
        )
    )


def check_owned_vs_forbidden(owned_paths: List[str], forbidden_paths: List[str]) -> List[str]:
    """Check that owned paths and forbidden paths have an empty intersection."""
    errors = []
    for owned in owned_paths:
        validate_path_syntax(owned)
        for forbidden in forbidden_paths:
            validate_path_syntax(forbidden)
            if patterns_overlap(owned, forbidden):
                errors.append(f"Owned path {owned!r} intersects forbidden path {forbidden!r}")
    return errors


# ---------------------------------------------------------------------------
# Contract Catalog & Exact Binding (F1)
# ---------------------------------------------------------------------------

def extract_contract_ids_from_source(source_path: Path) -> List[str]:
    """Extract all contract IDs declared as '### (CT-[A-Z0-9-]+)' in markdown."""
    text = source_path.read_text(encoding="utf-8")
    return re.findall(r"^### (CT-[A-Z0-9-]+)\b", text, re.MULTILINE)


def build_contract_catalog(contract_registry_path: Path, root: Path) -> Dict[str, ContractBinding]:
    """Parse contract-registry.yaml and bind every contract ID to its defining registry/source."""
    data = yaml.safe_load(contract_registry_path.read_text(encoding="utf-8"))
    contracts_data = data.get("contracts", [])
    catalog: Dict[str, ContractBinding] = {}
    seen_ids: Dict[str, str] = {}

    for entry in contracts_data:
        reg_id = entry.get("id")
        source_rel = entry.get("source")
        source_file = root / source_rel
        if not source_file.is_file():
            raise ContractBindingError(f"Registry {reg_id}: source file {source_rel} not found")
        real_hash = hashlib.sha256(source_file.read_bytes()).hexdigest()
        declared_hash = entry.get("source_sha256")
        if real_hash != declared_hash:
            raise ContractBindingError(
                f"Registry {reg_id}: source_sha256 mismatch (real {real_hash} != declared {declared_hash})"
            )
        owner = entry.get("owner")
        co_owners = entry.get("co_owners", [])
        revision = entry.get("current_revision", f"sha256:{declared_hash}")

        ids_in_file = extract_contract_ids_from_source(source_file)
        for c_id in ids_in_file:
            if c_id in seen_ids:
                raise ContractBindingError(
                    f"Contract {c_id} defined in multiple registries: {seen_ids[c_id]} and {reg_id}"
                )
            seen_ids[c_id] = reg_id
            catalog[c_id] = ContractBinding(
                id=c_id,
                registry_id=reg_id,
                source_path=source_rel,
                owner=owner,
                co_owners=co_owners,
                source_sha256=declared_hash,
                revision=revision,
            )

    return catalog


def validate_contract_ref(
    ref: Dict[str, Any], catalog: Dict[str, ContractBinding]
) -> ContractBinding:
    """Verify that a contract ref binds to the exact registry, owner, and source hash."""
    c_id = ref.get("id")
    if not c_id:
        raise ContractBindingError("Contract ref missing 'id'")
    binding = catalog.get(c_id)
    if binding is None:
        raise ContractBindingError(f"Unknown exact contract ID: {c_id!r}")
    declared_reg = ref.get("registry")
    if declared_reg != binding.registry_id:
        raise ContractBindingError(
            f"Contract {c_id}: declared registry {declared_reg!r} does not match defining registry {binding.registry_id!r}"
        )
    declared_rev = ref.get("revision")
    if declared_rev != binding.revision:
        raise ContractBindingError(
            f"Contract {c_id}: declared revision {declared_rev!r} does not match frozen revision {binding.revision!r}"
        )
    declared_owner = ref.get("owner")
    if declared_owner and declared_owner != binding.owner and declared_owner not in binding.co_owners:
        raise ContractBindingError(
            f"Contract {c_id}: declared owner {declared_owner!r} does not match registry owner {binding.owner!r}"
        )
    return binding


# ---------------------------------------------------------------------------
# Scope & Committed Delta Validation (F3)
# ---------------------------------------------------------------------------

ALLOWED_CHANGED_ROOT = {
    "AGENTS.md",
    "CLAUDE.md",
    "HANDOFF.md",
    "README.md",
    "CHANGELOG.md",
    "docs/11-roadmap.md",
    "docs/12-pre-code-checklist.md",
}


def check_path_scope(path: str) -> Optional[str]:
    """Check if a path is allowed within the proposed architecture docs/config scope."""
    validate_path_syntax(path)
    if path == "docs/parallel-delivery/.validation-report.json":
        return None
    if path in ALLOWED_CHANGED_ROOT or path.startswith("docs/parallel-delivery/"):
        return None
    if path.startswith(("src/", "tests/")) or path.endswith((".sql", "pyproject.toml", "uv.lock")):
        return f"Forbidden path changed: {path}"
    if "/evidence/" in path:
        return f"Historical evidence changed: {path}"
    return f"Changed path outside docs/config scope: {path}"


def get_committed_diff_paths(base_sha: str, candidate_sha: str, root: Path) -> List[Tuple[str, str, Optional[str]]]:
    """Return list of (status, path1, path2) from git diff --name-status -z.
    For renames/copies, path1 is old_path and path2 is new_path.
    """
    cmd = ["git", "diff", "--name-status", "-z", base_sha, candidate_sha]
    res = subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    raw = res.stdout.decode("utf-8", errors="strict")
    tokens = raw.split("\0")
    entries: List[Tuple[str, str, Optional[str]]] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token:
            break
        status = token
        i += 1
        if i >= len(tokens):
            break
        path1 = tokens[i].replace("\\", "/")
        i += 1
        if status.startswith(("R", "C")):
            if i >= len(tokens):
                break
            path2 = tokens[i].replace("\\", "/")
            i += 1
            entries.append((status, path1, path2))
        else:
            entries.append((status, path1, None))
    return entries


def get_dirty_overlay_paths(root: Path) -> List[Tuple[str, str, Optional[str]]]:
    """Return list of dirty/untracked paths from git status --porcelain=v1 -z."""
    cmd = ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]
    res = subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    raw = res.stdout.decode("utf-8", errors="strict")
    tokens = raw.split("\0")
    entries: List[Tuple[str, str, Optional[str]]] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token:
            break
        status = token[:2]
        path1 = token[3:].replace("\\", "/")
        i += 1
        if "R" in status:
            if i < len(tokens) and tokens[i]:
                path2 = tokens[i].replace("\\", "/")
                i += 1
                entries.append((status, path1, path2))
            else:
                entries.append((status, path1, None))
        else:
            entries.append((status, path1, None))
    return entries


def validate_scope_and_deltas(
    base_sha: str,
    candidate_sha: str,
    root: Path,
    immutable_evidence_refs: Optional[List[str]] = None,
) -> List[str]:
    """F3: Check committed diff + dirty overlay, rename both ends, and immutable evidence hashes."""
    errors = []
    committed_entries = get_committed_diff_paths(base_sha, candidate_sha, root)
    dirty_entries = get_dirty_overlay_paths(root)

    for status, path1, path2 in committed_entries + dirty_entries:
        err1 = check_path_scope(path1)
        if err1:
            errors.append(f"Committed/dirty path1 ({status}): {err1}")
        if path2 is not None:
            err2 = check_path_scope(path2)
            if err2:
                errors.append(f"Committed/dirty path2 rename ({status}): {err2}")

    # Check immutable evidence references
    if immutable_evidence_refs:
        for ref in immutable_evidence_refs:
            ref_path = root / ref
            if not ref_path.exists():
                errors.append(f"Immutable evidence path missing: {ref}")
            # Ensure no changes touched immutable evidence
            for _, p1, p2 in committed_entries + dirty_entries:
                for target_path in (p1, p2):
                    if target_path and target_path.startswith(ref):
                        errors.append(f"Forbidden mutation to immutable evidence: {target_path}")

    return errors


# ---------------------------------------------------------------------------
# Locks & Leases (F6)
# ---------------------------------------------------------------------------

class LeaseManager:
    """Manages active leases, partitionable namespaces, and capacity bounds."""

    def __init__(self, lock_definitions: Optional[List[Dict[str, Any]]] = None):
        self.lock_defs: Dict[str, Dict[str, Any]] = {}
        if lock_definitions:
            for lk in lock_definitions:
                self.lock_defs[lk["id"]] = lk
        self.active_leases: Dict[str, ActiveLease] = {}
        self.fencing_counters: Dict[str, int] = {}
        self.integrated_tasks: Set[str] = set()

    def mark_task_integrated(self, delivery_task_id: str) -> None:
        """Mark a task integrated; release all its live leases."""
        self.integrated_tasks.add(delivery_task_id)
        to_release = [
            lease_id
            for lease_id, lease in self.active_leases.items()
            if lease.delivery_task_id == delivery_task_id
        ]
        for lease_id in to_release:
            del self.active_leases[lease_id]

    def acquire_lease(
        self,
        lock_id: str,
        delivery_task_id: str,
        dispatch_id: str,
        resource_key: Optional[str] = None,
        units: int = 1,
        lease_seconds: int = 1800,
    ) -> ActiveLease:
        """Acquire an active lease. Rejects conflicts, over-capacity, and immutable leases."""
        lock_def = self.lock_defs.get(lock_id, {})
        # F2: Reject mutation leases on immutable evidence
        if (
            lock_id == "LOCK-ACCEPTED-EVIDENCE"
            or lock_def.get("mode") == "immutable"
            or lock_def.get("mutation_lease_forbidden")
        ):
            raise LockLeaseError(f"Lock {lock_id} is immutable; mutation lease is strictly prohibited")

        mode = lock_def.get("mode", "exclusive")
        actual_key = resource_key or lock_id

        # F6: Integrated tasks hold no lease and do not block
        active_for_lock = [
            l for l in self.active_leases.values()
            if l.lock_id == lock_id and l.is_active
        ]

        if mode == "exclusive":
            if active_for_lock:
                holder = active_for_lock[0]
                raise LockLeaseError(
                    f"Exclusive lock {lock_id} already leased to task {holder.delivery_task_id} (dispatch {holder.dispatch_id})"
                )

        elif mode == "exclusive_by_database_name":
            # Disjoint database namespaces grant concurrently; same namespace conflicts
            for l in active_for_lock:
                if l.resource_key == actual_key:
                    raise LockLeaseError(
                        f"Database lock {lock_id} with namespace {actual_key!r} already leased to task {l.delivery_task_id}"
                    )

        elif mode == "capacity":
            total_capacity = lock_def.get("capacity", 1)
            allocated_units = sum(l.units for l in active_for_lock)
            if allocated_units + units > total_capacity:
                raise LockLeaseError(
                    f"Capacity lock {lock_id} over-capacity: requested {units} units, but only {total_capacity - allocated_units} of {total_capacity} available"
                )

        # Increment monotonic fencing token
        self.fencing_counters[actual_key] = self.fencing_counters.get(actual_key, 0) + 1
        token = self.fencing_counters[actual_key]

        lease_id = f"lease_{actual_key}_{token}"
        now_str = datetime.now(timezone.utc).isoformat()
        lease = ActiveLease(
            lease_id=lease_id,
            lock_id=lock_id,
            resource_key=actual_key,
            units=units,
            fencing_token=token,
            delivery_task_id=delivery_task_id,
            dispatch_id=dispatch_id,
            acquired_at=now_str,
        )
        self.active_leases[lease_id] = lease
        return lease

    def release_lease(self, lease_id: str) -> None:
        if lease_id in self.active_leases:
            del self.active_leases[lease_id]


# ---------------------------------------------------------------------------
# Orca Delivery Adapter & Lifecycle State Machine (F4)
# ---------------------------------------------------------------------------

class OrcaDeliveryAdapter:
    """Translates Orca CLI events into delivery ledger state transitions."""

    def __init__(self, lease_manager: LeaseManager):
        self.lease_mgr = lease_manager
        self.task_states: Dict[str, str] = {}
        self.active_dispatches: Dict[str, str] = {}  # delivery_task_id -> current dispatch_id
        self.settled_dispatches: Set[str] = set()
        self.dispatch_counters: Dict[str, int] = {}
        self.last_fencing_tokens: Dict[str, int] = {}

    def set_task_state(self, delivery_task_id: str, state: str) -> None:
        self.task_states[delivery_task_id] = state

    def get_task_state(self, delivery_task_id: str) -> str:
        return self.task_states.get(delivery_task_id, "planned")

    def create_dispatch(self, delivery_task_id: str) -> str:
        """Create a fresh dispatch attempt for a delivery task."""
        current_state = self.get_task_state(delivery_task_id)
        if current_state not in ("ready", "blocked", "needs_replan"):
            raise ProtocolViolationError(
                f"Cannot dispatch task {delivery_task_id} from state {current_state!r}; must be ready/blocked/needs_replan"
            )
        self.dispatch_counters[delivery_task_id] = self.dispatch_counters.get(delivery_task_id, 0) + 1
        dispatch_id = f"ctx_{delivery_task_id}_{self.dispatch_counters[delivery_task_id]}"
        self.active_dispatches[delivery_task_id] = dispatch_id
        self.task_states[delivery_task_id] = "dispatched"
        return dispatch_id

    def handle_worker_done(
        self,
        delivery_task_id: str,
        orca_task_id: str,
        dispatch_id: str,
        outcome: str,
        candidate_commit: Optional[str] = None,
        fencing_token: Optional[int] = None,
    ) -> str:
        """Handle worker_done from Orca CLI.
        - outcome must be 'succeeded' or 'failed'.
        - rejects duplicates and stale results.
        - succeeded -> moves delivery task to 'review'.
        - failed -> moves delivery task to 'blocked'.
        """
        # Orca CLI constraint: only 'succeeded' or 'failed'
        if outcome not in ("succeeded", "failed"):
            raise ProtocolViolationError(
                f"Invalid worker_done outcome {outcome!r}; Orca CLI only supports 'succeeded' or 'failed'"
            )

        if dispatch_id in self.settled_dispatches:
            raise DuplicateResultError(f"Duplicate worker_done for already settled dispatch {dispatch_id}")

        active_id = self.active_dispatches.get(delivery_task_id)
        if active_id != dispatch_id:
            raise StaleResultError(
                f"Stale dispatch result: current active dispatch is {active_id!r}, received {dispatch_id!r}"
            )

        if fencing_token is not None:
            expected_token = self.last_fencing_tokens.get(delivery_task_id)
            if expected_token is not None and fencing_token < expected_token:
                raise StaleResultError(
                    f"Stale fencing token: current token is {expected_token}, received {fencing_token}"
                )

        # Settle the dispatch attempt
        self.settled_dispatches.add(dispatch_id)

        if outcome == "succeeded":
            self.task_states[delivery_task_id] = "review"
            return "review"
        else:
            # Failure / blocker -> task becomes blocked; releases live leases
            self.task_states[delivery_task_id] = "blocked"
            # Release leases for this dispatch
            to_remove = [
                lid for lid, l in self.lease_mgr.active_leases.items()
                if l.dispatch_id == dispatch_id
            ]
            for lid in to_remove:
                self.lease_mgr.release_lease(lid)
            return "blocked"

    def handle_review_verdict(self, delivery_task_id: str, verdict: str) -> str:
        """Handle independent review disposition ('ACCEPT', 'CHANGES_REQUESTED', 'BLOCKED')."""
        if self.get_task_state(delivery_task_id) != "review":
            raise ProtocolViolationError(f"Cannot review task {delivery_task_id} not in 'review' state")
        if verdict == "ACCEPT":
            self.task_states[delivery_task_id] = "merge_queued"
            return "merge_queued"
        elif verdict == "CHANGES_REQUESTED":
            self.task_states[delivery_task_id] = "remediation"
            return "remediation"
        else:
            self.task_states[delivery_task_id] = "blocked"
            return "blocked"

    def handle_integration_gates(self, delivery_task_id: str, gates_pass: bool) -> str:
        """Handle integration gates on exact candidate HEAD."""
        if self.get_task_state(delivery_task_id) != "merge_queued":
            raise ProtocolViolationError(f"Cannot integrate task {delivery_task_id} not in 'merge_queued' state")
        if gates_pass:
            self.task_states[delivery_task_id] = "integrated"
            self.lease_mgr.mark_task_integrated(delivery_task_id)
            return "integrated"
        else:
            self.task_states[delivery_task_id] = "blocked"
            return "blocked"

    def resolve_blocker_and_replan(self, delivery_task_id: str) -> None:
        """Transition blocked task back to ready once blocker is resolved."""
        state = self.get_task_state(delivery_task_id)
        if state not in ("blocked", "needs_replan"):
            raise ProtocolViolationError(f"Cannot resolve blocker for task in state {state!r}")
        self.task_states[delivery_task_id] = "ready"


# ---------------------------------------------------------------------------
# Readiness & Traceability Reference Validation (F5)
# ---------------------------------------------------------------------------

KNOWN_INVARIANTS = {f"INV-{i:03d}" for i in range(1, 21)}


def validate_task_traceability_and_readiness(
    task: Dict[str, Any],
    catalog: Dict[str, ContractBinding],
    known_owners: Set[str],
    known_requirements: Set[str],
    root: Path,
) -> List[str]:
    """F5: Validate real refs, readiness predicate, reject fake IDs and locked->ready."""
    errors = []
    task_id = task.get("id")
    authority_state = task.get("authority", {}).get("state")
    status = task.get("status")

    # 1. Authority refs check
    for auth_ref in task.get("authority_refs", []):
        validate_path_syntax(auth_ref)
        if not (root / auth_ref).is_file():
            errors.append(f"{task_id}: authority ref file missing on disk: {auth_ref}")

    # 2. Module owners check
    for owner in task.get("module_owners", []):
        if owner not in known_owners and owner != "CROSS-CUTTING-CONTRACT-OWNER":
            errors.append(f"{task_id}: unknown module owner {owner!r}")

    # 3. Invariant refs check
    for inv in task.get("invariant_refs", []):
        if inv not in KNOWN_INVARIANTS:
            errors.append(f"{task_id}: unknown/fake invariant ID {inv!r}")

    # 4. Requirement refs check (allow wildcards like 'FR-SRC-*' in future templates)
    for req in task.get("requirement_refs", []):
        if not req.endswith("*"):
            if req not in known_requirements:
                errors.append(f"{task_id}: unknown/fake requirement ID {req!r}")

    # 5. Contract refs check
    for ref in task.get("contract_refs", []):
        if isinstance(ref, dict):
            c_id = ref.get("id")
            if c_id not in catalog:
                errors.append(f"{task_id}: unknown exact contract ID {c_id!r}")
            else:
                binding = catalog[c_id]
                if ref.get("registry") != binding.registry_id:
                    errors.append(
                        f"{task_id}: contract {c_id} assigned to wrong registry {ref.get('registry')!r} (expected {binding.registry_id!r})"
                    )
                if ref.get("revision") != binding.revision:
                    errors.append(
                        f"{task_id}: contract {c_id} revision is not frozen ({ref.get('revision')!r} != {binding.revision!r})"
                    )

    # 6. Readiness predicate enforcement
    if status == "ready":
        if authority_state in ("locked", "future_template", "revoked"):
            errors.append(
                f"{task_id}: task with authority {authority_state!r} is forbidden from transitioning to 'ready'"
            )
        acceptance_rows = task.get("acceptance", [])
        if not acceptance_rows:
            errors.append(f"{task_id}: ready task must have at least one acceptance row")
        for row in acceptance_rows:
            obs = str(row.get("red_observation", "")).strip().lower()
            if not obs or obs in ("unknown", "tbd", "none", "pending"):
                errors.append(
                    f"{task_id}: ready task cannot have empty, missing, or 'unknown' red_observation: {obs!r}"
                )

    return errors
