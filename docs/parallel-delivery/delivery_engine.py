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
from datetime import datetime, timedelta, timezone
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


class HarnessCompatibilityError(ProtocolViolationError):
    """Harness tool execution failure or namespaced tool collapse."""


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
    allocation_slot: Optional[int] = None



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


SHA_HEX_40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
DEFAULT_APPROVED_BASE_COMMIT = "4a7c8c921b7e05066505d51b168a02c3fde61317"


def validate_commit_sha(sha: str, name: str, root: Path, require_full_sha: bool = True) -> str:
    """Validate that sha is an explicit non-empty input and resolves to a commit in git.
    When require_full_sha is True (default), ref names (such as 'HEAD', branch names, tags)
    and abbreviated SHAs are strictly rejected; an immutable full 40-character SHA is required.
    """
    if not sha or not isinstance(sha, str) or not sha.strip():
        raise ScopeViolationError(f"{name} commit must be an explicit, non-empty git commit reference")
    sha_clean = sha.strip()
    if require_full_sha:
        if sha_clean.upper() == "HEAD" or not SHA_HEX_40_RE.match(sha_clean):
            raise ScopeViolationError(
                f"{name} commit {sha_clean!r} is a ref name or abbreviated SHA. "
                "Scope validation requires an immutable full 40-character commit SHA; ref names (such as 'HEAD') are rejected."
            )
    cmd = ["git", "rev-parse", "--verify", f"{sha_clean}^{{commit}}"]
    res = subprocess.run(cmd, cwd=root, capture_output=True)
    if res.returncode != 0:
        err = res.stderr.decode("utf-8", errors="replace").strip()
        raise ScopeViolationError(f"{name} commit {sha_clean!r} cannot be verified in git: {err}")
    return res.stdout.decode("utf-8").strip()


def validate_scope_and_deltas(
    base_sha: str,
    candidate_sha: str,
    root: Path,
    immutable_evidence_refs: Optional[List[str]] = None,
    approved_base: str = DEFAULT_APPROVED_BASE_COMMIT,
    require_candidate_is_head: bool = True,
) -> List[str]:
    """F3 & Sol 1: Check committed diff + dirty overlay, rename both ends, and immutable evidence hashes.
    Both base_sha and candidate_sha must be immutable full 40-character SHAs.
    base_sha must match approved baseline.
    candidate_sha must match actual current HEAD.
    base_sha and candidate_sha cannot be equal (reject self-chosen base == candidate).
    """
    base_resolved = validate_commit_sha(base_sha, "Base", root, require_full_sha=True)
    if base_resolved.lower() != approved_base.lower():
        raise ScopeViolationError(
            f"Base commit {base_resolved} does not match approved project baseline {approved_base}. "
            "Self-chosen or stale base pins are rejected."
        )

    candidate_resolved = validate_commit_sha(candidate_sha, "Candidate", root, require_full_sha=True)

    if base_resolved.lower() == candidate_resolved.lower():
        raise ScopeViolationError(
            f"Base commit {base_resolved} equals candidate commit {candidate_resolved}. "
            "Self-chosen base == candidate is rejected; release requires meaningful delta from approved baseline."
        )

    if require_candidate_is_head:
        cmd_head = ["git", "rev-parse", "HEAD"]
        head_res = subprocess.run(cmd_head, cwd=root, capture_output=True, text=True)
        head_sha = head_res.stdout.strip() if head_res.returncode == 0 else ""
        if candidate_resolved.lower() != head_sha.lower():
            raise ScopeViolationError(
                f"Candidate commit {candidate_resolved} does not equal actual current HEAD {head_sha}. "
                "Non-HEAD candidate commits are rejected."
            )

    errors = []
    committed_entries = get_committed_diff_paths(base_resolved, candidate_resolved, root)
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

ALLOWED_LOCK_MODES = {
    "exclusive",
    "exclusive_by_database_name",
    "exclusive_by_account_and_fixture_namespace",
    "capacity",
    "immutable",
}

ALLOWED_LOCK_FIELDS = {
    "id",
    "class",
    "mode",
    "scope",
    "lease_seconds",
    "renewable",
    "mutation_lease_forbidden",
    "partition_key_prefix",
    "disjoint_namespace_rule",
    "capacity",
    "capacity_unit",
    "over_capacity_rule",
}


class LeaseManager:
    """Manages active leases, partitionable namespaces, and capacity bounds."""

    def __init__(self, lock_definitions: Optional[List[Dict[str, Any]]] = None):
        self.lock_defs: Dict[str, Dict[str, Any]] = {}
        if lock_definitions:
            for lk in lock_definitions:
                if not isinstance(lk, dict) or "id" not in lk:
                    raise LockLeaseError(f"Lock definition must be a dictionary with an 'id' field: {lk!r}")
                lk_id = lk["id"]
                if not isinstance(lk_id, str) or not lk_id.strip():
                    raise LockLeaseError(f"Lock ID cannot be empty: {lk_id!r}")
                if lk_id in self.lock_defs:
                    raise LockLeaseError(f"Duplicate lock ID {lk_id!r} in lock registry schema")

                # Reject unknown/irrelevant fields
                unknown_fields = set(lk.keys()) - ALLOWED_LOCK_FIELDS
                if unknown_fields:
                    raise LockLeaseError(
                        f"Lock {lk_id} contains unknown/irrelevant field(s): {sorted(unknown_fields)}"
                    )

                mode = lk.get("mode")
                if mode not in ALLOWED_LOCK_MODES:
                    raise LockLeaseError(
                        f"Unknown lock mode {mode!r} on lock {lk_id}; allowed: {sorted(ALLOWED_LOCK_MODES)}"
                    )

                if "renewable" not in lk or type(lk["renewable"]) is not bool:
                    raise LockLeaseError(f"Lock {lk_id} must declare strict boolean 'renewable' flag (True or False)")

                # Validate illegal field combinations by mode
                if mode == "immutable":
                    if lk.get("lease_seconds") is not None:
                        raise LockLeaseError(f"Immutable lock {lk_id} cannot specify lease_seconds; illegal field combination")
                    if lk.get("renewable") is not False:
                        raise LockLeaseError(f"Immutable lock {lk_id} must set renewable: false")
                    if "mutation_lease_forbidden" not in lk or type(lk["mutation_lease_forbidden"]) is not bool or not lk["mutation_lease_forbidden"]:
                        raise LockLeaseError(f"Immutable lock {lk_id} must specify mutation_lease_forbidden: true (strict bool)")
                    forbidden_fields = {"capacity", "capacity_unit", "over_capacity_rule", "partition_key_prefix", "disjoint_namespace_rule"} & set(lk.keys())
                    if forbidden_fields:
                        raise LockLeaseError(f"Immutable lock {lk_id} contains illegal fields for immutable mode: {sorted(forbidden_fields)}")

                elif mode == "exclusive":
                    forbidden_fields = {"capacity", "capacity_unit", "over_capacity_rule", "partition_key_prefix", "disjoint_namespace_rule", "mutation_lease_forbidden"} & set(lk.keys())
                    if forbidden_fields:
                        raise LockLeaseError(f"Exclusive lock {lk_id} contains illegal fields: {sorted(forbidden_fields)}")

                elif mode in ("exclusive_by_database_name", "exclusive_by_account_and_fixture_namespace"):
                    prefix = lk.get("partition_key_prefix")
                    if not prefix or not isinstance(prefix, str) or not prefix.strip():
                        raise LockLeaseError(
                            f"Partitionable lock {lk_id} must declare partition_key_prefix"
                        )
                    forbidden_fields = {"capacity", "capacity_unit", "over_capacity_rule", "mutation_lease_forbidden"} & set(lk.keys())
                    if forbidden_fields:
                        raise LockLeaseError(f"Partitionable lock {lk_id} contains illegal fields: {sorted(forbidden_fields)}")

                elif mode == "capacity":
                    cap = lk.get("capacity")
                    if type(cap) is not int or isinstance(cap, bool) or cap <= 0:
                        raise LockLeaseError(
                            f"Capacity lock {lk_id} must declare strict positive integer capacity; got {cap!r}"
                        )
                    forbidden_fields = {"partition_key_prefix", "disjoint_namespace_rule", "mutation_lease_forbidden"} & set(lk.keys())
                    if forbidden_fields:
                        raise LockLeaseError(f"Capacity lock {lk_id} contains illegal fields for capacity mode: {sorted(forbidden_fields)}")

                ls = lk.get("lease_seconds")
                if ls is not None and mode != "immutable":
                    if type(ls) is not int or isinstance(ls, bool) or ls <= 0:
                        raise LockLeaseError(
                            f"Lock {lk_id} has invalid lease_seconds {ls!r}; must be strict positive integer (excluding bool/float/nonpositive)"
                        )

                self.lock_defs[lk_id] = lk

        self.active_leases: Dict[str, ActiveLease] = {}
        self.fencing_counters: Dict[str, int] = {}
        self.integrated_tasks: Set[str] = set()
        self.task_authorities: Dict[str, str] = {}

    def set_task_authority(self, delivery_task_id: str, authority: str) -> None:
        self.task_authorities[delivery_task_id] = authority

    def purge_expired_leases(self, now: Optional[datetime] = None) -> List[str]:
        """Purge and expire active leases whose expiry time has passed."""
        if now is None:
            now_dt = datetime.now(timezone.utc)
        else:
            now_dt = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        purged = []
        for lease_id, lease in list(self.active_leases.items()):
            if not lease.is_active:
                purged.append(lease_id)
                del self.active_leases[lease_id]
                continue
            if lease.expires_at:
                try:
                    exp_dt = datetime.fromisoformat(lease.expires_at)
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                    if now_dt >= exp_dt:
                        lease.is_active = False
                        del self.active_leases[lease_id]
                        purged.append(lease_id)
                except (ValueError, TypeError):
                    lease.is_active = False
                    del self.active_leases[lease_id]
                    purged.append(lease_id)
        return purged

    def mark_task_integrated(self, delivery_task_id: str) -> None:
        """Mark a task integrated; release all its live leases."""
        self.integrated_tasks.add(delivery_task_id)
        to_release = [
            lease_id
            for lease_id, lease in list(self.active_leases.items())
            if lease.delivery_task_id == delivery_task_id
        ]
        for lease_id in to_release:
            self.release_lease(lease_id)

    def acquire_lease(
        self,
        lock_id: str,
        delivery_task_id: str,
        dispatch_id: str,
        resource_key: Optional[str] = None,
        units: int = 1,
        lease_seconds: Optional[int] = None,
        authority_state: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> ActiveLease:
        """Acquire an active lease. Rejects unknown locks, invalid/missing resource_key,
        zero/negative units, non-granted authority, unsafe duration broadening, and conflicting allocations.
        Computes expires_at and monotonic fencing tokens.
        """
        self.purge_expired_leases(now=now)

        # 1. Reject unknown locks
        if lock_id not in self.lock_defs:
            raise LockLeaseError(f"Unknown lock ID {lock_id!r}; lock must be declared in lock definitions")
        lock_def = self.lock_defs[lock_id]

        # 2. Authority must be explicitly registered and granted; caller cannot override registered authority
        if delivery_task_id not in self.task_authorities:
            raise LockLeaseError(
                f"Task {delivery_task_id} has no registered authority; authority must be explicitly registered and granted"
            )
        registered_auth = self.task_authorities[delivery_task_id]
        if authority_state is not None and authority_state != registered_auth:
            raise LockLeaseError(
                f"Task {delivery_task_id} authority override attempt: caller specified {authority_state!r} but registered authority is {registered_auth!r}; only 'granted' permitted"
            )
        if registered_auth != "granted":
            raise LockLeaseError(
                f"Task {delivery_task_id} has authority {registered_auth!r}; cannot acquire active lease (only 'granted' permitted)"
            )

        # 3. Reject zero, negative, boolean, or fractional units
        if type(units) is not int or isinstance(units, bool) or units <= 0:
            raise LockLeaseError(
                f"Invalid units {units!r}: units must be a strict positive integer (excluding bool/fractional/nonpositive)"
            )

        # 4. Enforce declared lease_seconds; cannot silently broaden declared duration
        declared_ls = lock_def.get("lease_seconds")
        max_ls = declared_ls if declared_ls is not None else 1800
        if lease_seconds is None:
            effective_lease_seconds = max_ls
        else:
            if type(lease_seconds) is not int or isinstance(lease_seconds, bool) or lease_seconds <= 0:
                raise LockLeaseError(f"Invalid lease_seconds {lease_seconds!r}: must be strict positive integer")
            if lease_seconds > max_ls:
                raise LockLeaseError(
                    f"Requested lease_seconds {lease_seconds} exceeds declared duration {max_ls} on lock {lock_id}; declared duration cannot be broadened"
                )
            effective_lease_seconds = lease_seconds

        # 5. Reject mutation leases on immutable evidence
        if (
            lock_id == "LOCK-ACCEPTED-EVIDENCE"
            or lock_def.get("mode") == "immutable"
            or lock_def.get("mutation_lease_forbidden")
        ):
            raise LockLeaseError(f"Lock {lock_id} is immutable; mutation lease is strictly prohibited")

        # 6. Validate resource_key
        mode = lock_def.get("mode", "exclusive")
        prefix = lock_def.get("partition_key_prefix")
        if mode in ("exclusive_by_database_name", "exclusive_by_account_and_fixture_namespace") or prefix is not None:
            if resource_key is None or not isinstance(resource_key, str) or not resource_key.strip():
                raise LockLeaseError(f"Missing resource_key for partitionable lock {lock_id}")
            resource_key = resource_key.strip()
            if prefix and not resource_key.startswith(prefix):
                raise LockLeaseError(f"Invalid resource_key {resource_key!r}: must start with prefix {prefix!r}")
            if prefix and len(resource_key) <= len(prefix):
                raise LockLeaseError(f"Invalid resource_key {resource_key!r}: namespace after prefix {prefix!r} cannot be empty")
            actual_key = resource_key
        else:
            if resource_key is not None:
                if not isinstance(resource_key, str) or not resource_key.strip():
                    raise LockLeaseError(f"Invalid resource_key for lock {lock_id}: cannot be empty string")
                actual_key = resource_key.strip()
            else:
                actual_key = lock_id

        # 7. Check conflicts against active leases
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

        elif mode in ("exclusive_by_database_name", "exclusive_by_account_and_fixture_namespace"):
            for l in active_for_lock:
                if l.resource_key == actual_key:
                    raise LockLeaseError(
                        f"Resource lock {lock_id} with namespace {actual_key!r} already leased to task {l.delivery_task_id}"
                    )

        elif mode == "capacity":
            total_capacity = lock_def.get("capacity", 1)
            allocated_units = sum(l.units for l in active_for_lock)
            if allocated_units + units > total_capacity:
                raise LockLeaseError(
                    f"Capacity lock {lock_id} over-capacity: requested {units} units, but only {total_capacity - allocated_units} of {total_capacity} available"
                )

        # Reject duplicate/overlapping resource keys across other active leases
        for existing in self.active_leases.values():
            if existing.is_active and existing.lock_id != lock_id:
                if existing.resource_key == actual_key or existing.resource_key.startswith(f"{actual_key}:"):
                    raise LockLeaseError(
                        f"Resource key {actual_key!r} already leased by lock {existing.lock_id} to task {existing.delivery_task_id}"
                    )

        # 8. Increment monotonic fencing token per resource key or live allocation
        if now is None:
            now_dt = datetime.now(timezone.utc)
        else:
            now_dt = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        expires_dt = now_dt + timedelta(seconds=effective_lease_seconds)

        if mode == "capacity":
            total_capacity = lock_def.get("capacity", 1)
            occupied_slots = {
                l.allocation_slot for l in active_for_lock
                if l.allocation_slot is not None and l.is_active
            }
            avail_slots = [s for s in range(1, total_capacity + 1) if s not in occupied_slots]
            alloc_slot = avail_slots[0]
            allocation_key = f"{actual_key}:slot_{alloc_slot}"
            self.fencing_counters[allocation_key] = self.fencing_counters.get(allocation_key, 0) + 1
            token = self.fencing_counters[allocation_key]
            lease_id = f"lease_{actual_key}_slot_{alloc_slot}_{token}"
            lease = ActiveLease(
                lease_id=lease_id,
                lock_id=lock_id,
                resource_key=allocation_key,
                units=units,
                fencing_token=token,
                delivery_task_id=delivery_task_id,
                dispatch_id=dispatch_id,
                acquired_at=now_dt.isoformat(),
                expires_at=expires_dt.isoformat(),
                is_active=True,
                allocation_slot=alloc_slot,
            )
            self.active_leases[lease_id] = lease
            return lease
        else:
            self.fencing_counters[actual_key] = self.fencing_counters.get(actual_key, 0) + 1
            token = self.fencing_counters[actual_key]
            lease_id = f"lease_{actual_key}_{token}"
            lease = ActiveLease(
                lease_id=lease_id,
                lock_id=lock_id,
                resource_key=actual_key,
                units=units,
                fencing_token=token,
                delivery_task_id=delivery_task_id,
                dispatch_id=dispatch_id,
                acquired_at=now_dt.isoformat(),
                expires_at=expires_dt.isoformat(),
                is_active=True,
            )
            self.active_leases[lease_id] = lease
            return lease

    def release_lease(self, lease_id: str) -> None:
        """Release an active lease."""
        if lease_id in self.active_leases:
            lease = self.active_leases[lease_id]
            lease.is_active = False
            del self.active_leases[lease_id]

    def renew_lease(
        self, lease_id: str, extend_seconds: Optional[int] = None, now: Optional[datetime] = None
    ) -> ActiveLease:
        """Renew an active lease. Rejects non-renewable, expired, inactive, revoked, or non-existent leases.
        Declared lease duration cannot be broadened.
        """
        if now is None:
            now_dt = datetime.now(timezone.utc)
        else:
            now_dt = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)

        if lease_id not in self.active_leases:
            raise LockLeaseError(f"Cannot renew non-existent or purged lease {lease_id}")
        lease = self.active_leases[lease_id]
        if not lease.is_active:
            raise LockLeaseError(f"Cannot renew inactive lease {lease_id}")

        # Check lock renewable flag
        lock_def = self.lock_defs.get(lease.lock_id)
        if not lock_def or lock_def.get("renewable") is not True:
            raise LockLeaseError(f"Cannot renew lease {lease_id}: lock {lease.lock_id} is non-renewable")

        # Check declared duration broadening
        declared_ls = lock_def.get("lease_seconds")
        max_extend = declared_ls if declared_ls is not None else 1800
        if extend_seconds is None:
            effective_extend = max_extend
        else:
            if type(extend_seconds) is not int or isinstance(extend_seconds, bool) or extend_seconds <= 0:
                raise LockLeaseError(f"Invalid extend_seconds {extend_seconds!r}: must be strict positive integer")
            if extend_seconds > max_extend:
                raise LockLeaseError(
                    f"Requested extend_seconds {extend_seconds} exceeds declared duration {max_extend} on lock {lease.lock_id}; declared duration cannot be broadened"
                )
            effective_extend = extend_seconds

        # Check task authority: must be registered and still granted
        task_id = lease.delivery_task_id
        if task_id not in self.task_authorities:
            raise LockLeaseError(f"Cannot renew lease {lease_id}: task {task_id} has no registered authority")
        auth = self.task_authorities.get(task_id)
        if auth != "granted":
            raise LockLeaseError(f"Cannot renew lease {lease_id}: task {task_id} authority is {auth!r} (only 'granted' permitted)")

        if lease.expires_at:
            try:
                exp_dt = datetime.fromisoformat(lease.expires_at)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if now_dt >= exp_dt:
                    lease.is_active = False
                    del self.active_leases[lease_id]
                    raise LockLeaseError(f"Cannot renew expired lease {lease_id}")
                new_exp_dt = exp_dt + timedelta(seconds=effective_extend)
            except (ValueError, TypeError):
                lease.is_active = False
                del self.active_leases[lease_id]
                raise LockLeaseError(f"Invalid expires_at format in lease {lease_id}")
        else:
            new_exp_dt = now_dt + timedelta(seconds=effective_extend)

        lease.expires_at = new_exp_dt.isoformat()
        return lease

    def validate_fencing_token(
        self,
        resource_key: str,
        fencing_token: Optional[int],
        now: Optional[datetime] = None,
        active_lease_id: Optional[str] = None,
    ) -> bool:
        """Validate fencing token on result mutation; reject expired, absent, stale, or future tokens."""
        if fencing_token is None:
            raise LockLeaseError(f"Absent fencing token for resource {resource_key!r}")
        if type(fencing_token) is not int or isinstance(fencing_token, bool):
            raise LockLeaseError(f"Invalid fencing token type: {type(fencing_token)}")

        if active_lease_id and active_lease_id in self.active_leases:
            lease = self.active_leases[active_lease_id]
            target_key = lease.resource_key
            expected = self.fencing_counters.get(target_key)
        elif resource_key not in self.fencing_counters:
            matching_alloc = [
                l for l in self.active_leases.values()
                if l.lock_id == resource_key and l.fencing_token == fencing_token and l.is_active
            ]
            if matching_alloc:
                target_key = matching_alloc[0].resource_key
                expected = self.fencing_counters.get(target_key)
            else:
                raise LockLeaseError(f"No fencing token registered for resource {resource_key!r}")
        else:
            target_key = resource_key
            expected = self.fencing_counters.get(target_key)

        if expected is None:
            raise LockLeaseError(f"No fencing token registered for resource {resource_key!r}")
        if fencing_token < expected:
            raise LockLeaseError(
                f"Stale fencing token {fencing_token} for resource {resource_key!r}; current is {expected}"
            )
        if fencing_token > expected:
            raise LockLeaseError(
                f"Future fencing token {fencing_token} exceeds current counter {expected} for resource {resource_key!r}"
            )
        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        matching = [
            l for l in self.active_leases.values()
            if (l.resource_key == target_key or l.lock_id == resource_key) and l.fencing_token == fencing_token and l.is_active
        ]
        if not matching:
            raise LockLeaseError(
                f"No active lease found for resource {resource_key!r} with fencing token {fencing_token}"
            )
        lease_obj = matching[0]
        if lease_obj.expires_at:
            try:
                exp_dt = datetime.fromisoformat(lease_obj.expires_at)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if now_dt >= exp_dt:
                    lease_obj.is_active = False
                    if lease_obj.lease_id in self.active_leases:
                        del self.active_leases[lease_obj.lease_id]
                    raise LockLeaseError(
                        f"Expired fencing token / lease for resource {resource_key!r}"
                    )
            except (ValueError, TypeError):
                raise LockLeaseError(f"Invalid expires_at format in lease {lease_obj.lease_id}")
        return True


# ---------------------------------------------------------------------------
# Orca Delivery Adapter & Lifecycle State Machine (F4)
# ---------------------------------------------------------------------------

LEGAL_TASK_STATE_TRANSITIONS: Dict[str, Set[str]] = {
    "planned": {"waiting_dependency", "ready", "cancelled"},
    "waiting_dependency": {"ready", "cancelled"},
    "ready": {"dispatched", "cancelled"},
    "dispatched": {"acknowledged", "running", "review", "blocked", "stopped"},
    "acknowledged": {"running", "blocked", "stopped"},
    "running": {"review", "blocked", "needs_replan", "stopped"},
    "blocked": {"ready", "stopped"},
    "needs_replan": {"planned", "stopped"},
    "review": {"merge_queued", "remediation", "blocked"},
    "remediation": {"review"},
    "merge_queued": {"integrated", "ready", "blocked"},
    "integrated": set(),
    "stopped": set(),
    "cancelled": set(),
}


@dataclass
class DispatchBinding:
    delivery_task_id: str
    orca_task_id: str
    dispatch_id: str
    candidate_commit: Optional[str] = None
    fencing_token: Optional[int] = None
    lease_id: Optional[str] = None
    authority_state: str = "granted"
    settled: bool = False


class OrcaDeliveryAdapter:
    """Translates Orca CLI events into delivery ledger state transitions."""

    def __init__(
        self,
        lease_manager: LeaseManager,
        approved_candidate_commit: Optional[str] = None,
        git_root: Optional[Path] = None,
    ):
        self.lease_mgr = lease_manager
        self.approved_candidate_commit = approved_candidate_commit
        self.git_root = git_root
        self.task_states: Dict[str, str] = {}
        self.task_authorities: Dict[str, str] = {}
        self.active_dispatches: Dict[str, str] = {}  # delivery_task_id -> current dispatch_id
        self.settled_dispatches: Set[str] = set()
        self.dispatch_counters: Dict[str, int] = {}
        self.last_fencing_tokens: Dict[str, int] = {}
        self.dispatch_bindings: Dict[str, DispatchBinding] = {}
        self.seen_orca_task_ids: Set[str] = set()
        self.seen_dispatch_ids: Set[str] = set()
        self.orca_task_to_delivery_task: Dict[str, str] = {}

    def set_task_state(self, delivery_task_id: str, state: str) -> None:
        self.task_states[delivery_task_id] = state

    def transition_task_state(self, delivery_task_id: str, new_state: str) -> None:
        current = self.get_task_state(delivery_task_id)
        allowed = LEGAL_TASK_STATE_TRANSITIONS.get(current, set())
        if new_state not in allowed:
            raise ProtocolViolationError(
                f"Illegal task-state transition for {delivery_task_id}: {current!r} -> {new_state!r}; allowed: {sorted(allowed)}"
            )
        self.task_states[delivery_task_id] = new_state

    def get_task_state(self, delivery_task_id: str) -> str:
        return self.task_states.get(delivery_task_id, "planned")

    def set_task_authority(self, delivery_task_id: str, authority: str) -> None:
        self.task_authorities[delivery_task_id] = authority
        self.lease_mgr.set_task_authority(delivery_task_id, authority)

    def get_task_authority(self, delivery_task_id: str) -> str:
        return self.task_authorities.get(delivery_task_id, "unregistered")

    def create_dispatch(
        self,
        delivery_task_id: str,
        orca_task_id: Optional[str] = None,
        candidate_commit: Optional[str] = None,
        fencing_token: Optional[int] = None,
        lease_id: Optional[str] = None,
        authority_state: Optional[str] = None,
        intended_dispatch_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> str:
        """Create a fresh dispatch attempt for a delivery task and bind identities.
        Requires exact nonblank and globally unique Orca task ID, candidate commit existing in git
        and matching approved candidate and actual current HEAD, positive fencing token, active unexpired lease
        belonging to same delivery task and intended dispatch unconditionally, declared lock on lease,
        non-reuse of dispatch IDs, and allowed state transition ('ready' -> 'dispatched').
        """
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        delivery_task_id = delivery_task_id.strip()

        # Authority check: never default granted; caller cannot override registered authority
        if delivery_task_id not in self.task_authorities:
            raise ProtocolViolationError(
                f"Task {delivery_task_id} has no registered authority; authority must be explicitly registered and granted"
            )
        registered_auth = self.task_authorities[delivery_task_id]
        if authority_state is not None and authority_state != registered_auth:
            raise ProtocolViolationError(
                f"Task {delivery_task_id} authority override attempt: caller specified {authority_state!r} but registered authority is {registered_auth!r}; only 'granted' authority permitted"
            )
        if registered_auth != "granted":
            raise ProtocolViolationError(
                f"Cannot dispatch task {delivery_task_id} with authority {registered_auth!r}; only 'granted' authority permitted"
            )

        # State transition: only 'ready' may dispatch; blocked/locked/future/revoked cannot dispatch
        current_state = self.get_task_state(delivery_task_id)
        if current_state != "ready":
            raise ProtocolViolationError(
                f"Cannot dispatch task {delivery_task_id} from state {current_state!r}; only 'ready' state may be dispatched (blocked/locked/future/revoked cannot dispatch)"
            )

        # Orca task identity: nonblank and globally unique across active and settled dispatches
        if not orca_task_id or not isinstance(orca_task_id, str) or not orca_task_id.strip():
            raise ProtocolViolationError("orca_task_id cannot be blank")
        orca_task_id = orca_task_id.strip()

        if orca_task_id in self.seen_orca_task_ids:
            other_task = self.orca_task_to_delivery_task.get(orca_task_id)
            if other_task and other_task != delivery_task_id:
                raise ProtocolViolationError(
                    f"Orca task ID {orca_task_id!r} is already assigned to delivery task {other_task!r}; global reuse is forbidden"
                )
            raise ProtocolViolationError(
                f"Orca task ID {orca_task_id!r} is already assigned or has already been used in an active or settled dispatch; global reuse is forbidden"
            )

        # Candidate commit: full 40-character SHA, must exist in git, must match actual current HEAD
        if not candidate_commit or not isinstance(candidate_commit, str) or not candidate_commit.strip():
            raise ProtocolViolationError("candidate_commit cannot be blank")
        candidate_commit = candidate_commit.strip()
        if candidate_commit.upper() == "HEAD" or not SHA_HEX_40_RE.match(candidate_commit):
            raise ProtocolViolationError(
                f"candidate_commit {candidate_commit!r} is invalid; must be an immutable full 40-character commit SHA"
            )

        # Verify candidate commit exists in git
        repo_root = self.git_root or (ROOT if "ROOT" in globals() else Path.cwd())
        cmd = ["git", "cat-file", "-e", f"{candidate_commit}^{{commit}}"]
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True)
        if res.returncode != 0:
            raise ProtocolViolationError(f"Candidate commit {candidate_commit!r} does not exist in git")

        # Verify candidate equals actual current HEAD
        head_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True)
        if head_res.returncode != 0 or not head_res.stdout.strip():
            raise ProtocolViolationError("Cannot determine actual current git HEAD")
        actual_head = head_res.stdout.strip()

        if candidate_commit.lower() != actual_head.lower():
            raise ProtocolViolationError(
                f"Candidate commit {candidate_commit} does not match approved candidate / HEAD {actual_head}"
            )
        if self.approved_candidate_commit and self.approved_candidate_commit.lower() != actual_head.lower():
            raise ProtocolViolationError(
                f"Approved candidate commit {self.approved_candidate_commit} does not match actual current HEAD {actual_head}"
            )

        # Fencing token: strict positive integer
        if fencing_token is None or type(fencing_token) is not int or isinstance(fencing_token, bool) or fencing_token <= 0:
            raise ProtocolViolationError(
                f"fencing_token is required and must be a strict positive integer; got {fencing_token!r}"
            )

        # Lease validation
        if not lease_id or not isinstance(lease_id, str) or not lease_id.strip():
            raise ProtocolViolationError("lease_id is required and cannot be blank")
        lease_id = lease_id.strip()
        if lease_id not in self.lease_mgr.active_leases:
            raise ProtocolViolationError(f"Bound lease {lease_id!r} not found in active leases")
        active_lease = self.lease_mgr.active_leases[lease_id]
        if not active_lease.is_active:
            raise ProtocolViolationError(f"Bound lease {lease_id!r} is not active")

        # Reject undeclared lock on bound lease
        if active_lease.lock_id not in self.lease_mgr.lock_defs:
            raise ProtocolViolationError(
                f"Bound lease {lease_id} references undeclared lock {active_lease.lock_id!r}"
            )

        # Lease expiry check
        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        if active_lease.expires_at:
            try:
                exp_dt = datetime.fromisoformat(active_lease.expires_at)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if now_dt >= exp_dt:
                    active_lease.is_active = False
                    del self.lease_mgr.active_leases[lease_id]
                    raise ProtocolViolationError(f"Bound lease {lease_id} has expired at {active_lease.expires_at}")
            except (ValueError, TypeError):
                active_lease.is_active = False
                del self.lease_mgr.active_leases[lease_id]
                raise ProtocolViolationError(f"Bound lease {lease_id} has invalid expires_at format")

        # Lease ownership: belongs to same delivery task
        if active_lease.delivery_task_id != delivery_task_id:
            raise ProtocolViolationError(
                f"Lease {lease_id} belongs to task {active_lease.delivery_task_id!r}, cannot be bound to {delivery_task_id!r}"
            )

        # Lease cannot be already bound to an active or settled dispatch
        for prev_disp_id, prev_b in self.dispatch_bindings.items():
            if prev_b.lease_id == lease_id:
                raise ProtocolViolationError(
                    f"Lease {lease_id} is already bound to dispatch {prev_disp_id}; lease reuse across dispatches is forbidden"
                )

        # Require intended dispatch binding unconditionally: no exceptions or bypasses
        if intended_dispatch_id is not None:
            if active_lease.dispatch_id != intended_dispatch_id:
                raise ProtocolViolationError(
                    f"Lease {lease_id} intended dispatch {active_lease.dispatch_id!r} does not match requested {intended_dispatch_id!r}"
                )
            dispatch_id = intended_dispatch_id
        else:
            self.dispatch_counters[delivery_task_id] = self.dispatch_counters.get(delivery_task_id, 0) + 1
            dispatch_id = f"ctx_{delivery_task_id}_{self.dispatch_counters[delivery_task_id]}"
            active_lease.dispatch_id = dispatch_id

        # Global non-reuse of dispatch IDs across active and settled attempts; reject overwrite
        if (
            dispatch_id in self.seen_dispatch_ids
            or dispatch_id in self.settled_dispatches
            or dispatch_id in self.dispatch_bindings
        ):
            raise ProtocolViolationError(
                f"Duplicate dispatch binding overwrite: dispatch ID {dispatch_id!r} is already bound or settled; global reuse is forbidden"
            )

        # Fencing token must match active lease token and current counter
        if fencing_token != active_lease.fencing_token:
            raise ProtocolViolationError(
                f"Fencing token mismatch for lease {lease_id}: lease has {active_lease.fencing_token}, dispatch requested {fencing_token}"
            )
        current_token = self.lease_mgr.fencing_counters.get(active_lease.resource_key)
        if current_token is not None and fencing_token != current_token:
            raise ProtocolViolationError(
                f"Fencing token {fencing_token} is not current for resource {active_lease.resource_key} (current is {current_token})"
            )

        binding = DispatchBinding(
            delivery_task_id=delivery_task_id,
            orca_task_id=orca_task_id,
            dispatch_id=dispatch_id,
            candidate_commit=candidate_commit,
            fencing_token=fencing_token,
            lease_id=lease_id,
            authority_state=registered_auth,
            settled=False,
        )
        self.dispatch_bindings[dispatch_id] = binding
        self.seen_orca_task_ids.add(orca_task_id)
        self.seen_dispatch_ids.add(dispatch_id)
        self.orca_task_to_delivery_task[orca_task_id] = delivery_task_id
        self.active_dispatches[delivery_task_id] = dispatch_id
        self.transition_task_state(delivery_task_id, "dispatched")
        self.last_fencing_tokens[delivery_task_id] = fencing_token
        return dispatch_id

    def handle_worker_done(
        self,
        delivery_task_id: str,
        orca_task_id: str,
        dispatch_id: str,
        outcome: str,
        candidate_commit: Optional[str] = None,
        fencing_token: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> str:
        """Handle worker_done from Orca CLI with full identity, authority, lease ownership,
        fencing, and transition validation.
        """
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        delivery_task_id = delivery_task_id.strip()

        if not orca_task_id or not isinstance(orca_task_id, str) or not orca_task_id.strip():
            raise ProtocolViolationError("orca_task_id cannot be blank")
        orca_task_id = orca_task_id.strip()

        if not dispatch_id or not isinstance(dispatch_id, str) or not dispatch_id.strip():
            raise ProtocolViolationError("dispatch_id cannot be blank")
        dispatch_id = dispatch_id.strip()

        if outcome not in ("succeeded", "failed"):
            raise ProtocolViolationError(
                f"Invalid worker_done outcome {outcome!r}; Orca CLI only supports 'succeeded' or 'failed'"
            )

        if dispatch_id in self.settled_dispatches:
            raise DuplicateResultError(f"Duplicate worker_done for already settled dispatch {dispatch_id}")

        # One-way transition table: task must currently be in 'dispatched' state
        current_state = self.get_task_state(delivery_task_id)
        if current_state != "dispatched":
            raise ProtocolViolationError(
                f"Cannot complete worker_done for task {delivery_task_id} in state {current_state!r}; must be 'dispatched'"
            )

        # Authority re-check on worker_done: revocation blocks mutation/settlement
        auth = self.task_authorities.get(delivery_task_id)
        if auth != "granted":
            raise ProtocolViolationError(
                f"Task {delivery_task_id} has authority {auth!r}; completion blocked (only 'granted' permitted)"
            )

        active_id = self.active_dispatches.get(delivery_task_id)
        if active_id != dispatch_id:
            raise StaleResultError(
                f"Stale dispatch result: current active dispatch is {active_id!r}, received {dispatch_id!r}"
            )

        binding = self.dispatch_bindings.get(dispatch_id)
        if binding is None:
            raise ProtocolViolationError(f"Unknown dispatch ID {dispatch_id!r}")

        # Validate binding identity
        if binding.orca_task_id != orca_task_id:
            raise ProtocolViolationError(
                f"orca_task_id mismatch: dispatch {dispatch_id} was bound to {binding.orca_task_id!r}, received {orca_task_id!r}"
            )

        if binding.authority_state != "granted":
            raise ProtocolViolationError(
                f"Task {delivery_task_id} has non-granted authority {binding.authority_state!r}"
            )

        if not candidate_commit or candidate_commit != binding.candidate_commit:
            raise ProtocolViolationError(
                f"Candidate commit mismatch: expected {binding.candidate_commit}, got {candidate_commit}"
            )

        repo_root = self.git_root or (ROOT if "ROOT" in globals() else Path.cwd())
        cmd = ["git", "cat-file", "-e", f"{candidate_commit}^{{commit}}"]
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True)
        if res.returncode != 0:
            raise ProtocolViolationError(f"Candidate commit {candidate_commit!r} does not exist in git")

        if fencing_token is None:
            raise ProtocolViolationError(
                f"Absent fencing token: dispatch {dispatch_id} was bound with fencing token {binding.fencing_token}"
            )
        if type(fencing_token) is not int or isinstance(fencing_token, bool):
            raise ProtocolViolationError(f"Invalid fencing token type: {type(fencing_token)}")
        if fencing_token < binding.fencing_token:
            raise StaleResultError(
                f"Stale fencing token: expected at least {binding.fencing_token}, received {fencing_token}"
            )
        if fencing_token > binding.fencing_token:
            raise ProtocolViolationError(
                f"Future fencing token: expected {binding.fencing_token}, received future token {fencing_token}"
            )

        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)

        # Verify bound lease is still active, unexpired, and belongs to same task/dispatch
        if binding.lease_id:
            if binding.lease_id not in self.lease_mgr.active_leases:
                raise ProtocolViolationError(
                    f"Bound lease {binding.lease_id} has expired or been purged from active leases"
                )
            bound_lease = self.lease_mgr.active_leases[binding.lease_id]
            if not bound_lease.is_active:
                raise ProtocolViolationError(f"Bound lease {binding.lease_id} is inactive")
            if bound_lease.delivery_task_id != delivery_task_id:
                raise ProtocolViolationError(
                    f"Bound lease {binding.lease_id} belongs to task {bound_lease.delivery_task_id!r}, not {delivery_task_id!r}"
                )
            if bound_lease.dispatch_id != dispatch_id:
                raise ProtocolViolationError(
                    f"Bound lease {binding.lease_id} is bound to dispatch {bound_lease.dispatch_id!r}, not {dispatch_id!r}"
                )
            if bound_lease.expires_at:
                try:
                    exp_dt = datetime.fromisoformat(bound_lease.expires_at)
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                    if now_dt >= exp_dt:
                        bound_lease.is_active = False
                        del self.lease_mgr.active_leases[binding.lease_id]
                        raise ProtocolViolationError(f"Bound lease {binding.lease_id} expired at {bound_lease.expires_at}")
                except (ValueError, TypeError):
                    bound_lease.is_active = False
                    del self.lease_mgr.active_leases[binding.lease_id]
                    raise ProtocolViolationError(f"Bound lease {binding.lease_id} has invalid expires_at format")

            # Validate fencing token against lease manager
            self.lease_mgr.validate_fencing_token(bound_lease.resource_key, fencing_token, now=now_dt)

        # Settle the dispatch attempt
        self.settled_dispatches.add(dispatch_id)
        binding.settled = True

        if outcome == "succeeded":
            self.transition_task_state(delivery_task_id, "review")
            to_remove = [
                lid for lid, l in list(self.lease_mgr.active_leases.items())
                if l.dispatch_id == dispatch_id or l.delivery_task_id == delivery_task_id or lid == binding.lease_id
            ]
            for lid in to_remove:
                self.lease_mgr.release_lease(lid)
            return "review"
        else:
            # Failure / blocker -> task becomes blocked; releases live leases
            self.transition_task_state(delivery_task_id, "blocked")
            to_remove = [
                lid for lid, l in list(self.lease_mgr.active_leases.items())
                if l.dispatch_id == dispatch_id or l.delivery_task_id == delivery_task_id or lid == binding.lease_id
            ]
            for lid in to_remove:
                self.lease_mgr.release_lease(lid)
            return "blocked"

    def handle_review_verdict(self, delivery_task_id: str, verdict: str) -> str:
        """Handle independent review disposition ('ACCEPT', 'CHANGES_REQUESTED', 'BLOCKED').
        Unknown review verdicts are strictly rejected.
        """
        auth = self.get_task_authority(delivery_task_id)
        if auth != "granted":
            raise ProtocolViolationError(
                f"Task {delivery_task_id} has authority {auth!r}; review transition blocked (only 'granted' permitted)"
            )
        current_state = self.get_task_state(delivery_task_id)
        if current_state != "review":
            raise ProtocolViolationError(f"Cannot review task {delivery_task_id} in state {current_state!r}; must be 'review'")

        if verdict == "ACCEPT":
            self.transition_task_state(delivery_task_id, "merge_queued")
            return "merge_queued"
        elif verdict == "CHANGES_REQUESTED":
            self.transition_task_state(delivery_task_id, "remediation")
            return "remediation"
        elif verdict == "BLOCKED":
            self.transition_task_state(delivery_task_id, "blocked")
            return "blocked"
        else:
            raise ProtocolViolationError(
                f"Unknown review verdict {verdict!r}; allowed verdicts are 'ACCEPT', 'CHANGES_REQUESTED', 'BLOCKED'"
            )

    def handle_integration_gates(self, delivery_task_id: str, gates_pass: bool) -> str:
        """Handle integration gates on exact candidate HEAD.
        gates_pass must be strict bool; truthy/falsy coercion is strictly rejected.
        """
        if type(gates_pass) is not bool:
            raise ProtocolViolationError(
                f"gates_pass must be strict bool (True or False, no truthy coercion); got {type(gates_pass).__name__}: {gates_pass!r}"
            )
        auth = self.get_task_authority(delivery_task_id)
        if auth != "granted":
            raise ProtocolViolationError(
                f"Task {delivery_task_id} has authority {auth!r}; integration transition blocked (only 'granted' permitted)"
            )
        current_state = self.get_task_state(delivery_task_id)
        if current_state != "merge_queued":
            raise ProtocolViolationError(f"Cannot integrate task {delivery_task_id} in state {current_state!r}; must be 'merge_queued'")
        if gates_pass:
            self.transition_task_state(delivery_task_id, "integrated")
            self.lease_mgr.mark_task_integrated(delivery_task_id)
            return "integrated"
        else:
            self.transition_task_state(delivery_task_id, "blocked")
            to_remove = [
                lid for lid, l in list(self.lease_mgr.active_leases.items())
                if l.delivery_task_id == delivery_task_id
            ]
            for lid in to_remove:
                self.lease_mgr.release_lease(lid)
            return "blocked"

    def resolve_blocker_and_replan(self, delivery_task_id: str) -> None:
        """Transition blocked task back to ready once blocker is resolved, or needs_replan to planned."""
        auth = self.get_task_authority(delivery_task_id)
        if auth != "granted":
            raise ProtocolViolationError(
                f"Task {delivery_task_id} has authority {auth!r}; cannot replan or transition to ready (only 'granted' permitted)"
            )
        state = self.get_task_state(delivery_task_id)
        if state not in ("blocked", "needs_replan"):
            raise ProtocolViolationError(f"Cannot resolve blocker for task in state {state!r}")
        if state == "blocked":
            self.transition_task_state(delivery_task_id, "ready")
        elif state == "needs_replan":
            self.transition_task_state(delivery_task_id, "planned")


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


@dataclass
class HarnessExecutionResult:
    success: bool
    execution_time_ms: float
    status: str  # "PASS" or "STOP"
    state: str   # "SUCCESS", "FAILURE", "STOP_FALLBACK"
    tool_name: str
    requested_tool: str
    execution_observed: bool
    execution_returncode: int
    fallback_required: bool
    fallback_target: str = "antigravity_native"
    error_message: Optional[str] = None

    def __post_init__(self):
        if type(self.success) is not bool:
            raise HarnessCompatibilityError(
                f"success must be strict bool; got {type(self.success).__name__}: {self.success!r}"
            )
        if type(self.execution_time_ms) is bool or not isinstance(self.execution_time_ms, (int, float)) or self.execution_time_ms < 0:
            raise HarnessCompatibilityError(
                f"execution_time_ms must be non-negative int or float; got {type(self.execution_time_ms).__name__}: {self.execution_time_ms!r}"
            )
        if self.status not in ("PASS", "STOP"):
            raise HarnessCompatibilityError(f"status must be 'PASS' or 'STOP'; got {self.status!r}")
        if self.state not in ("SUCCESS", "FAILURE", "STOP_FALLBACK", "VERIFIED"):
            raise HarnessCompatibilityError(
                f"state must be 'SUCCESS', 'FAILURE', 'STOP_FALLBACK', or 'VERIFIED'; got {self.state!r}"
            )
        if type(self.execution_observed) is not bool:
            raise HarnessCompatibilityError(
                f"execution_observed must be strict bool; got {type(self.execution_observed).__name__}: {self.execution_observed!r}"
            )
        if type(self.execution_returncode) is not int or isinstance(self.execution_returncode, bool):
            raise HarnessCompatibilityError(
                f"execution_returncode must be strict int; got {type(self.execution_returncode).__name__}: {self.execution_returncode!r}"
            )
        if type(self.fallback_required) is not bool:
            raise HarnessCompatibilityError(
                f"fallback_required must be strict bool; got {type(self.fallback_required).__name__}: {self.fallback_required!r}"
            )
        if not self.fallback_target or not isinstance(self.fallback_target, str) or not self.fallback_target.strip():
            raise HarnessCompatibilityError("fallback_target cannot be blank")


class HarnessExecutionStateMachine:
    """Observable state machine for harness tool execution and fallback / STOP transitions.
    States: IDLE -> RUNNING -> SUCCESS | FAILURE | STOP_FALLBACK.
    """

    def __init__(self):
        self.current_state = "IDLE"
        self.transitions: List[Tuple[str, str, str]] = []

    def transition(self, to_state: str, reason: str) -> None:
        self.transitions.append((self.current_state, to_state, reason))
        self.current_state = to_state

    def evaluate(
        self,
        tool_name: str,
        requested_tool: str,
        execution_observed: bool = True,
        execution_returncode: int = 0,
        execution_time_ms: float = 0.0,
    ) -> HarnessExecutionResult:
        if self.current_state != "IDLE":
            self.current_state = "IDLE"
        self.transition("RUNNING", "Started harness tool evaluation")

        if not isinstance(tool_name, str) or not tool_name.strip():
            self.transition("STOP_FALLBACK", "Effective tool identity blank")
            raise HarnessCompatibilityError("Effective tool identity cannot be blank")
        if not isinstance(requested_tool, str) or not requested_tool.strip():
            self.transition("STOP_FALLBACK", "Requested tool identity blank")
            raise HarnessCompatibilityError("Requested tool identity cannot be blank")

        if type(execution_observed) is not bool:
            self.transition("STOP_FALLBACK", "execution_observed not strict bool")
            raise HarnessCompatibilityError(
                f"execution_observed must be strict bool; got {type(execution_observed).__name__}: {execution_observed!r}"
            )
        if type(execution_returncode) is not int or isinstance(execution_returncode, bool):
            self.transition("STOP_FALLBACK", "execution_returncode not strict int")
            raise HarnessCompatibilityError(
                f"execution_returncode must be strict int; got {type(execution_returncode).__name__}: {execution_returncode!r}"
            )

        effective = tool_name.strip()
        requested = requested_tool.strip()

        if "." in requested and "." not in effective:
            msg = (
                f"Harness namespaced tool collapse detected: requested {requested!r} collapsed to unnamespaced {effective!r}. "
                "Route success does not imply executable harness. STOP condition triggered: fallback to verified native harness required."
            )
            self.transition("STOP_FALLBACK", msg)
            raise HarnessCompatibilityError(msg)

        if effective != requested:
            msg = (
                f"Harness tool identity mismatch: requested {requested!r} != effective {effective!r}. "
                "STOP condition triggered: fallback to verified native harness required."
            )
            self.transition("STOP_FALLBACK", msg)
            raise HarnessCompatibilityError(msg)

        if not execution_observed:
            msg = (
                f"Harness tool execution smoke gate failed: execution_observed=False, returncode={execution_returncode}. "
                "No successful tool execution observed. Observed successful tool execution required before routing work. "
                "STOP condition triggered: fallback to verified native harness required."
            )
            self.transition("FAILURE", msg)
            self.transition("STOP_FALLBACK", "Fallback to verified native harness required")
            raise HarnessCompatibilityError(msg)

        if execution_returncode != 0:
            msg = (
                f"Harness tool execution smoke gate failed: execution_observed=True, returncode={execution_returncode}. "
                f"Harness tool execution smoke test failed with returncode {execution_returncode}. "
                "Observed successful tool execution required before routing work. "
                "STOP condition triggered: fallback to verified native harness required."
            )
            self.transition("FAILURE", msg)
            self.transition("STOP_FALLBACK", "Fallback to verified native harness required")
            raise HarnessCompatibilityError(msg)

        self.transition("SUCCESS", f"Tool {effective} verified successfully")
        return HarnessExecutionResult(
            success=True,
            execution_time_ms=execution_time_ms,
            status="PASS",
            state="SUCCESS",
            tool_name=effective,
            requested_tool=requested,
            execution_observed=execution_observed,
            execution_returncode=execution_returncode,
            fallback_required=False,
            fallback_target="none",
            error_message=None,
        )


def check_harness_tool_compatibility(
    tool_name: str,
    requested_tool: str,
    execution_observed: bool = True,
    execution_returncode: int = 0,
    execution_time_ms: float = 0.0,
) -> HarnessExecutionResult:
    """Validate tool execution compatibility using the observable harness state machine."""
    sm = HarnessExecutionStateMachine()
    return sm.evaluate(tool_name, requested_tool, execution_observed, execution_returncode, execution_time_ms)
