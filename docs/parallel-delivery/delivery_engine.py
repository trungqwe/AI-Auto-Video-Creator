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
import hmac
import json
import os
import re
import secrets
import subprocess
import threading
import sys
import time
import uuid
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from collections.abc import Mapping

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


class RoutingEvidenceError(ProtocolViolationError):
    """F2: Provider routing policy or execution envelope validation failure."""


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
    allocated_slots: List[int] = field(default_factory=list)
    slot_fencing_tokens: Dict[int, int] = field(default_factory=dict)
    cumulative_extension_seconds: int = 0
    renewal_count: int = 0


def namespaces_overlap(ns1: str, ns2: str) -> bool:
    """Symmetric parent/child namespace overlap detection.
    Returns True if ns1 == ns2 or ns1 is parent of ns2 or ns2 is parent of ns1.
    Respects hierarchy delimiters (':', '/', '.').
    """
    if not ns1 or not ns2:
        return False
    if ns1 == ns2:
        return True
    for d in (":", "/", "."):
        if ns1.startswith(ns2 + d) or ns2.startswith(ns1 + d):
            return True
    return False



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
    if path.startswith((".agy-", ".astra-", ".sol-")) and path.endswith("-spec.md"):
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
                if not (path1.startswith((".agy-", ".astra-", ".sol-")) and path1.endswith("-spec.md")):
                    entries.append((status, path1, path2))
            else:
                if not (path1.startswith((".agy-", ".astra-", ".sol-")) and path1.endswith("-spec.md")):
                    entries.append((status, path1, None))
        else:
            if not (path1.startswith((".agy-", ".astra-", ".sol-")) and path1.endswith("-spec.md")):
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
    "max_cumulative_seconds",
    "max_renewals",
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
                    forbidden_fields = {"capacity", "capacity_unit", "over_capacity_rule", "partition_key_prefix", "disjoint_namespace_rule", "max_cumulative_seconds", "max_renewals"} & set(lk.keys())
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

                mcs = lk.get("max_cumulative_seconds")
                if mcs is not None and mode != "immutable":
                    if type(mcs) is not int or isinstance(mcs, bool) or mcs <= 0:
                        raise LockLeaseError(
                            f"Lock {lk_id} has invalid max_cumulative_seconds {mcs!r}; must be strict positive integer (excluding bool/float/nonpositive)"
                        )

                mr = lk.get("max_renewals")
                if mr is not None and mode != "immutable":
                    if type(mr) is not int or isinstance(mr, bool) or mr < 0:
                        raise LockLeaseError(
                            f"Lock {lk_id} has invalid max_renewals {mr!r}; must be non-negative integer (excluding bool/float/negative)"
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
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise LockLeaseError("delivery_task_id cannot be blank")
        clean_tid = delivery_task_id.strip()
        self.integrated_tasks.add(clean_tid)
        to_release = [
            lease_id
            for lease_id, lease in list(self.active_leases.items())
            if lease.delivery_task_id == clean_tid
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

        # 0. Validate non-blank identities
        if not lock_id or not isinstance(lock_id, str) or not lock_id.strip():
            raise LockLeaseError("lock_id cannot be blank")
        lock_id = lock_id.strip()
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise LockLeaseError("delivery_task_id cannot be blank")
        delivery_task_id = delivery_task_id.strip()
        if not dispatch_id or not isinstance(dispatch_id, str) or not dispatch_id.strip():
            raise LockLeaseError("dispatch_id cannot be blank")
        dispatch_id = dispatch_id.strip()

        # Reject reacquisition of leases for already integrated tasks
        if delivery_task_id in self.integrated_tasks:
            raise LockLeaseError(
                f"Task {delivery_task_id} has already integrated; reacquisition of leases is strictly prohibited"
            )

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
                if namespaces_overlap(l.resource_key, actual_key):
                    raise LockLeaseError(
                        f"Resource lock {lock_id} with namespace {actual_key!r} is already leased / conflicts with existing lease {l.resource_key!r} held by task {l.delivery_task_id} (symmetric parent/child overlap)"
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
                if namespaces_overlap(existing.resource_key, actual_key):
                    raise LockLeaseError(
                        f"Resource key {actual_key!r} conflicts with existing lease {existing.resource_key!r} of lock {existing.lock_id} held by task {existing.delivery_task_id} (symmetric parent/child overlap)"
                    )

        # 8. Increment monotonic fencing token per resource key or live allocation
        if now is None:
            now_dt = datetime.now(timezone.utc)
        else:
            now_dt = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        expires_dt = now_dt + timedelta(seconds=effective_lease_seconds)

        if mode == "capacity":
            total_capacity = lock_def.get("capacity", 1)
            occupied_slots = set()
            for l in active_for_lock:
                if l.is_active:
                    if getattr(l, "allocated_slots", None):
                        occupied_slots.update(l.allocated_slots)
                    elif l.allocation_slot is not None:
                        occupied_slots.add(l.allocation_slot)
            avail_slots = [s for s in range(1, total_capacity + 1) if s not in occupied_slots]
            if len(avail_slots) < units:
                raise LockLeaseError(
                    f"Capacity lock {lock_id} over-capacity: requested {units} units, but only {len(avail_slots)} of {total_capacity} slots available"
                )
            allocated_slots = avail_slots[:units]
            slot_tokens = {}
            for slot in allocated_slots:
                allocation_key = f"{actual_key}:slot_{slot}"
                self.fencing_counters[allocation_key] = self.fencing_counters.get(allocation_key, 0) + 1
                slot_tokens[slot] = self.fencing_counters[allocation_key]
            primary_slot = allocated_slots[0]
            token = slot_tokens[primary_slot]
            lease_id = f"lease_{actual_key}_slots_{'_'.join(str(s) for s in allocated_slots)}_{token}"
            lease = ActiveLease(
                lease_id=lease_id,
                lock_id=lock_id,
                resource_key=f"{actual_key}:slot_{primary_slot}",
                units=units,
                fencing_token=token,
                delivery_task_id=delivery_task_id,
                dispatch_id=dispatch_id,
                acquired_at=now_dt.isoformat(),
                expires_at=expires_dt.isoformat(),
                is_active=True,
                allocation_slot=primary_slot,
                allocated_slots=allocated_slots,
                slot_fencing_tokens=slot_tokens,
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
        if not lease_id or not isinstance(lease_id, str) or not lease_id.strip():
            raise LockLeaseError("lease_id cannot be blank")
        clean_lid = lease_id.strip()
        if clean_lid in self.active_leases:
            lease = self.active_leases[clean_lid]
            lease.is_active = False
            del self.active_leases[clean_lid]

    def renew_lease(
        self, lease_id: str, extend_seconds: Optional[int] = None, now: Optional[datetime] = None
    ) -> ActiveLease:
        """Renew an active lease. Rejects non-renewable, expired, inactive, revoked, or non-existent leases.
        Declared lease duration cannot be broadened. Renewals cannot cumulatively exceed declared lease policy.
        """
        if not lease_id or not isinstance(lease_id, str) or not lease_id.strip():
            raise LockLeaseError("lease_id cannot be blank")
        clean_lid = lease_id.strip()

        if now is None:
            now_dt = datetime.now(timezone.utc)
        else:
            now_dt = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)

        if clean_lid not in self.active_leases:
            raise LockLeaseError(f"Cannot renew non-existent or purged lease {clean_lid}")
        lease = self.active_leases[clean_lid]
        if not lease.is_active:
            raise LockLeaseError(f"Cannot renew inactive lease {clean_lid}")

        # Check lock renewable flag
        lock_def = self.lock_defs.get(lease.lock_id)
        if not lock_def or lock_def.get("renewable") is not True:
            raise LockLeaseError(f"Cannot renew lease {clean_lid}: lock {lease.lock_id} is non-renewable")

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

        # Check cumulative renewal policy against declared lease policy
        max_cumulative = lock_def.get("max_cumulative_seconds")
        if max_cumulative is None:
            max_cumulative = max_extend
        max_renewals = lock_def.get("max_renewals")
        if max_renewals is not None and lease.renewal_count >= max_renewals:
            raise LockLeaseError(
                f"Cannot renew lease {clean_lid}: renewal count {lease.renewal_count} reached maximum allowed renewals ({max_renewals})"
            )
        if lease.cumulative_extension_seconds + effective_extend > max_cumulative:
            raise LockLeaseError(
                f"Cannot renew lease {clean_lid}: cumulative extensions ({lease.cumulative_extension_seconds + effective_extend}s) would exceed declared lease policy ({max_cumulative}s)"
            )

        # Check task authority: must be registered and still granted
        task_id = lease.delivery_task_id
        if task_id not in self.task_authorities:
            raise LockLeaseError(f"Cannot renew lease {clean_lid}: task {task_id} has no registered authority")
        auth = self.task_authorities.get(task_id)
        if auth != "granted":
            raise LockLeaseError(f"Cannot renew lease {clean_lid}: task {task_id} authority is {auth!r} (only 'granted' permitted)")

        if lease.expires_at:
            try:
                exp_dt = datetime.fromisoformat(lease.expires_at)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if now_dt >= exp_dt:
                    lease.is_active = False
                    del self.active_leases[clean_lid]
                    raise LockLeaseError(f"Cannot renew expired lease {clean_lid}")
                new_exp_dt = exp_dt + timedelta(seconds=effective_extend)
            except (ValueError, TypeError):
                lease.is_active = False
                del self.active_leases[clean_lid]
                raise LockLeaseError(f"Invalid expires_at format in lease {clean_lid}")
        else:
            new_exp_dt = now_dt + timedelta(seconds=effective_extend)

        lease.expires_at = new_exp_dt.isoformat()
        lease.cumulative_extension_seconds += effective_extend
        lease.renewal_count += 1
        return lease

    def validate_fencing_token(
        self,
        resource_key: str,
        fencing_token: Optional[int],
        now: Optional[datetime] = None,
        active_lease_id: Optional[str] = None,
        slot: Optional[int] = None,
    ) -> bool:
        """Validate fencing token on result mutation; reject expired, absent, stale, or future tokens."""
        if not resource_key or not isinstance(resource_key, str) or not resource_key.strip():
            raise LockLeaseError("resource_key cannot be blank")
        resource_key = resource_key.strip()
        if fencing_token is None:
            raise LockLeaseError(f"Absent fencing token for resource {resource_key!r}")
        if type(fencing_token) is not int or isinstance(fencing_token, bool):
            raise LockLeaseError(f"Invalid fencing token type: {type(fencing_token)}")

        # Resolve active lease object
        lease_obj: Optional[ActiveLease] = None
        base_key = resource_key.rsplit(":slot_", 1)[0] if ":slot_" in resource_key else resource_key
        if active_lease_id and active_lease_id in self.active_leases:
            lease_obj = self.active_leases[active_lease_id]
        else:
            matching = [
                l for l in self.active_leases.values()
                if (l.resource_key == resource_key or l.lock_id == resource_key or l.lock_id == base_key or (":slot_" in l.resource_key and l.resource_key.rsplit(":slot_", 1)[0] == base_key))
                and l.is_active
            ]
            if matching:
                token_matching = [
                    l for l in matching
                    if l.fencing_token == fencing_token or (l.allocated_slots and slot in l.slot_fencing_tokens and l.slot_fencing_tokens[slot] == fencing_token)
                ]
                lease_obj = token_matching[0] if token_matching else matching[0]

        if lease_obj is not None:
            if slot is not None:
                if lease_obj.allocated_slots:
                    if slot not in lease_obj.slot_fencing_tokens:
                        raise LockLeaseError(f"Slot {slot} was not allocated to lease {lease_obj.lease_id}")
                    prefix = lease_obj.resource_key.rsplit(":slot_", 1)[0] if ":slot_" in lease_obj.resource_key else lease_obj.lock_id
                    target_key = f"{prefix}:slot_{slot}"
                    expected = self.fencing_counters.get(target_key)
                    rec_target = lease_obj.slot_fencing_tokens.get(slot)
                    if rec_target is not None and fencing_token != rec_target:
                        raise LockLeaseError(
                            f"Slot token mismatch for slot {slot} in capacity lock {lease_obj.lock_id}: "
                            f"lease recorded {rec_target}, query specified {fencing_token}"
                        )
                else:
                    target_key = f"{base_key}:slot_{slot}"
                    expected = self.fencing_counters.get(target_key)
            elif active_lease_id:
                target_key = lease_obj.resource_key
                expected = self.fencing_counters.get(target_key)
            elif resource_key in self.fencing_counters:
                target_key = resource_key
                expected = self.fencing_counters.get(target_key)
            else:
                target_key = lease_obj.resource_key
                expected = self.fencing_counters.get(target_key)
        else:
            if slot is not None:
                target_key = f"{base_key}:slot_{slot}"
                expected = self.fencing_counters.get(target_key)
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
        if not lease_obj:
            raise LockLeaseError(
                f"No active lease found for resource {resource_key!r} with fencing token {fencing_token}"
            )

        # Multi-slot capacity validation: every slot has its own monotonic generation.
        # A lease remains valid only when all its exact slot tokens are current, including asymmetric reuse.
        if lease_obj.allocated_slots:
            prefix = lease_obj.resource_key.rsplit(":slot_", 1)[0] if ":slot_" in lease_obj.resource_key else lease_obj.lock_id
            for s in lease_obj.allocated_slots:
                s_key = f"{prefix}:slot_{s}"
                exp_s = self.fencing_counters.get(s_key)
                rec_s = lease_obj.slot_fencing_tokens.get(s)
                if exp_s is None or rec_s is None or rec_s != exp_s:
                    raise LockLeaseError(
                        f"Stale slot token for slot {s} in capacity lock {lease_obj.lock_id}: "
                        f"lease recorded {rec_s}, current counter is {exp_s} (asymmetric slot reallocation detected)"
                    )
            if slot is not None:
                if slot not in lease_obj.slot_fencing_tokens:
                    raise LockLeaseError(f"Slot {slot} was not allocated to lease {lease_obj.lease_id}")
                rec_target = lease_obj.slot_fencing_tokens.get(slot)
                if rec_target is not None and fencing_token != rec_target:
                    raise LockLeaseError(
                        f"Slot token mismatch for slot {slot} in capacity lock {lease_obj.lock_id}: "
                        f"lease recorded {rec_target}, query specified {fencing_token}"
                    )

        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
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
    "dispatched": {"acknowledged", "blocked", "stopped", "needs_replan", "cancelled"},
    "acknowledged": {"running", "blocked", "stopped", "needs_replan", "cancelled"},
    "running": {"review", "needs_replan", "blocked", "stopped", "cancelled"},
    "blocked": {"ready", "stopped"},
    "needs_replan": {"planned", "stopped"},
    "review": {"merge_queued", "remediation", "blocked"},
    "remediation": {"review"},
    "merge_queued": {"integrated", "ready", "blocked"},
    "integrated": set(),
    "stopped": set(),
    "cancelled": set(),
}


_BUNDLE_DIR = Path(__file__).resolve().parent
_WORKSPACE_ROOT = _BUNDLE_DIR.parents[1]
DEFAULT_PRODUCTION_REGISTRY_PATH = Path(
    os.environ.get(
        "ORCA_EXECUTION_REGISTRY_PATH",
        str(_WORKSPACE_ROOT / "runtime" / "orca-execution-registry.json"),
    )
)


@dataclass(init=False)
class LiveTerminalEvidence:
    harness: str
    provider: str
    route: str
    archive_reference: Optional[str] = None
    verified: bool = True
    dispatch_id: Optional[str] = None
    delivery_task_id: Optional[str] = None
    effort: Optional[str] = None

    def __init__(
        self,
        harness: str,
        provider: str,
        route: str,
        archive_reference: Optional[str] = None,
        verified: bool = True,
        dispatch_id: Optional[str] = None,
        terminal_id: Optional[str] = None,
        delivery_task_id: Optional[str] = None,
        effort: Optional[str] = None,
    ):
        self.harness = harness
        self.provider = provider
        self.route = route
        self.archive_reference = archive_reference if archive_reference is not None else terminal_id
        self.verified = verified
        self.dispatch_id = dispatch_id
        self.delivery_task_id = delivery_task_id
        self.effort = effort

    @property
    def terminal_id(self) -> Optional[str]:
        return self.archive_reference

    @terminal_id.setter
    def terminal_id(self, val: Optional[str]):
        self.archive_reference = val


@dataclass
class UsageEvidence:
    backend_provider: str
    backend_model: str
    recorded_after_dispatch: bool = True
    timestamp: Optional[str] = None
    request_id: Optional[str] = None
    dispatch_id: Optional[str] = None
    delivery_task_id: Optional[str] = None
    router: str = "9router"


@dataclass
class ExecutionEnvelope:
    delivery_task_id: str
    dispatch_id: str
    dispatch_origin: str
    phase: str
    route: Dict[str, Any]
    orca_task_id: Optional[str] = None
    live_terminal_evidence: Optional[Union[Dict[str, Any], LiveTerminalEvidence]] = None
    usage_evidence: Optional[Union[Dict[str, Any], UsageEvidence]] = None
    launch_requested: Optional[Any] = None
    launch_effective: Optional[Any] = None


@dataclass
class ReviewEvidence:
    review_dispatch_id: str
    delivery_task_id: str
    candidate_commit: str
    verdict: str
    reviewer_route: str = "cx/gpt-5.6-sol"
    reviewer_harness: str = "Claude Code"
    evidence_hash: Optional[str] = None
    summary: Optional[str] = None
    timestamp: Optional[str] = None
    evidence_id: Optional[str] = None
    signature: Optional[str] = None
    authority_id: Optional[int] = None


@dataclass
class IntegrationEvidence:
    delivery_task_id: str
    candidate_commit: str
    base_commit: str
    gates_pass: bool
    gate_results: Dict[str, bool] = field(default_factory=dict)
    evidence_hash: Optional[str] = None
    integrated_by: Optional[str] = None
    timestamp: Optional[str] = None
    evidence_id: Optional[str] = None
    signature: Optional[str] = None
    authority_id: Optional[int] = None


@dataclass(frozen=True)
class _TransitionAuthToken:
    token_id: str
    task_id: str
    from_state: str
    new_state: str
    handler: str
    adapter_id: int
    created_at: float
    signature: str = ""

    @property
    def to_state(self) -> str:
        return self.new_state

@dataclass(frozen=True)
class _InternalLifecycleToken:
    token_id: str
    handler: str
    task_id: str
    adapter_id: int
    created_at: float
    signature: str = ""

    def __post_init__(self):
        for field_name in ("token_id", "handler", "task_id", "signature"):
            val = getattr(self, field_name, None)
            if not isinstance(val, str) or not val.strip() or val != val.strip():
                raise ProtocolViolationError(f"_InternalLifecycleToken field {field_name!r} must be non-empty unpadded string")


@dataclass(frozen=True)
class ReviewerCapability:
    capability_id: str
    delivery_task_id: str
    review_dispatch_id: str
    candidate_commit: str
    reviewer_route: str
    reviewer_harness: str
    authority_id: int
    created_at: float
    signature: str = ""

    def __post_init__(self):
        for field_name in (
            "capability_id",
            "delivery_task_id",
            "review_dispatch_id",
            "candidate_commit",
            "reviewer_route",
            "reviewer_harness",
            "signature",
        ):
            val = getattr(self, field_name, None)
            if not isinstance(val, str) or not val.strip() or val != val.strip():
                raise ProtocolViolationError(f"ReviewerCapability field {field_name!r} must be non-empty unpadded string")


@dataclass(frozen=True)
class ControlCapability:
    capability_id: str
    role: str  # "Control"
    delivery_task_id: Optional[str]
    authority_id: int
    created_at: float
    signature: str = ""

    def __post_init__(self):
        if not isinstance(self.capability_id, str) or not self.capability_id.strip() or self.capability_id != self.capability_id.strip():
            raise ProtocolViolationError("ControlCapability capability_id must be non-empty unpadded string")
        if self.role != "Control":
            raise ProtocolViolationError(f"ControlCapability role must be 'Control'; got {self.role!r}")
        if self.delivery_task_id is not None:
            if not isinstance(self.delivery_task_id, str) or not self.delivery_task_id.strip() or self.delivery_task_id != self.delivery_task_id.strip():
                raise ProtocolViolationError("ControlCapability delivery_task_id must be non-empty unpadded string when provided")
        if not isinstance(self.signature, str) or not self.signature.strip() or self.signature != self.signature.strip():
            raise ProtocolViolationError("ControlCapability signature must be non-empty unpadded string")



MANDATORY_INTEGRATION_GATES: Tuple[str, ...] = (
    "authority",
    "candidate",
    "scope",
    "encoding",
    "security",
    "contract",
    "migration",
    "focused_tests",
    "regression",
    "evidence",
    "independent_review",
)


class EvidenceAuthority:
    """Internal authority component responsible for issuing and verifying cryptographically-bound,
    unforgeable, freshness-checked review and integration evidence. Public constructors or caller-computed
    hashes do not confer authority.
    """
    MAX_EVIDENCE_AGE_SECONDS: float = 300.0  # 5 minutes freshness window
    MAX_FUTURE_SKEW_SECONDS: float = 10.0

    def __init__(self, adapter: Optional[Any] = None, control_secret: Optional[str] = None) -> None:
        self._secret: bytes = secrets.token_bytes(32)
        self._control_secret: bytes = control_secret.encode("utf-8") if control_secret else secrets.token_bytes(32)
        self._issued_evidence_ids: Set[str] = set()
        self._consumed_evidence_ids: Set[str] = set()
        self._issued_capabilities: Set[str] = set()
        self._consumed_capabilities: Set[str] = set()
        self.adapter = adapter
        self._lock = threading.Lock()

    def _sign_control_capability(self, cap_id: str, role: str, tid: str, created_at: float) -> str:
        payload = f"CONTROL_CAPABILITY:{cap_id}:{tid}:{role}:{id(self)}:{created_at}".encode("utf-8")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _sign_reviewer_capability(
        self, cap_id: str, tid: str, disp_id: str, commit: str, route: str, harness: str, created_at: float
    ) -> str:
        payload = f"REVIEWER_CAPABILITY:{cap_id}:{tid}:{disp_id}:{commit}:{route}:{harness}:{id(self)}:{created_at}".encode("utf-8")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()


    def _mint_reviewer_capability_internal(
        self, delivery_task_id: str, review_dispatch_id: str, candidate_commit: str,
        reviewer_route: str = "cx/gpt-5.6-sol", reviewer_harness: str = "Claude Code"
    ) -> ReviewerCapability:
        cap_id = f"rev_cap_{uuid.uuid4().hex}"
        created_at = time.time()
        sig = self._sign_reviewer_capability(
            cap_id, delivery_task_id.strip(), review_dispatch_id.strip(),
            candidate_commit.strip(), reviewer_route.strip(), reviewer_harness.strip(), created_at
        )
        cap = ReviewerCapability(
            capability_id=cap_id,
            delivery_task_id=delivery_task_id.strip(),
            review_dispatch_id=review_dispatch_id.strip(),
            candidate_commit=candidate_commit.strip(),
            reviewer_route=reviewer_route.strip(),
            reviewer_harness=reviewer_harness.strip(),
            authority_id=id(self),
            created_at=created_at,
            signature=sig,
        )
        with self._lock:
            self._issued_capabilities.add(cap_id)
        return cap

    def issue_control_capability(
        self, control_secret: str, delivery_task_id: Optional[str] = None
    ) -> ControlCapability:
        if not control_secret or not isinstance(control_secret, str):
            raise ProtocolViolationError("control_secret is required to issue ControlCapability")
        if not hmac.compare_digest(control_secret.encode("utf-8"), self._control_secret):
            raise ProtocolViolationError("Invalid control secret; cannot issue ControlCapability")

        cap_id = f"ctrl_cap_{uuid.uuid4().hex}"
        created_at = time.time()
        tid = delivery_task_id.strip() if (delivery_task_id and isinstance(delivery_task_id, str)) else "*"
        sig = self._sign_control_capability(cap_id, "Control", tid, created_at)
        cap = ControlCapability(
            capability_id=cap_id,
            role="Control",
            delivery_task_id=delivery_task_id.strip() if delivery_task_id else None,
            authority_id=id(self),
            created_at=created_at,
            signature=sig,
        )
        with self._lock:
            self._issued_capabilities.add(cap_id)
        return cap

    def issue_reviewer_capability(
        self,
        delivery_task_id: str,
        review_dispatch_id: str,
        candidate_commit: str,
        reviewer_route: str = "cx/gpt-5.6-sol",
        reviewer_harness: str = "Claude Code",
        control_capability: Optional[ControlCapability] = None,
        control_secret: Optional[str] = None,
    ) -> ReviewerCapability:
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        if not review_dispatch_id or not isinstance(review_dispatch_id, str) or not review_dispatch_id.strip():
            raise ProtocolViolationError("review_dispatch_id cannot be blank")
        if not candidate_commit or not isinstance(candidate_commit, str) or not candidate_commit.strip():
            raise ProtocolViolationError("candidate_commit cannot be blank")
        if reviewer_route != "cx/gpt-5.6-sol":
            raise ProtocolViolationError(f"Invalid reviewer route {reviewer_route!r}; expected 'cx/gpt-5.6-sol'")
        if reviewer_harness != "Claude Code":
            raise ProtocolViolationError(f"Invalid reviewer harness {reviewer_harness!r}; expected 'Claude Code'")

        authenticated = False
        if control_secret and isinstance(control_secret, str):
            if hmac.compare_digest(control_secret.encode("utf-8"), self._control_secret):
                authenticated = True
        if not authenticated and control_capability is not None:
            self.verify_capability(control_capability, expected_role="Control", expected_task_id=delivery_task_id.strip())
            authenticated = True

        if not authenticated:
            raise ProtocolViolationError(
                "Unauthorized: issuing ReviewerCapability requires authenticated Control authority (valid ControlCapability or control_secret)"
            )

        return self._mint_reviewer_capability_internal(
            delivery_task_id=delivery_task_id,
            review_dispatch_id=review_dispatch_id,
            candidate_commit=candidate_commit,
            reviewer_route=reviewer_route,
            reviewer_harness=reviewer_harness,
        )

    def get_reviewer_capability(
        self, review_dispatch_id: str, control_capability: Optional[ControlCapability] = None, control_secret: Optional[str] = None
    ) -> ReviewerCapability:
        if self.adapter is None:
            raise ProtocolViolationError("No adapter attached to evidence authority")
        return self.adapter.get_reviewer_capability(review_dispatch_id, control_capability=control_capability, control_secret=control_secret)

    def issue_review_evidence(
        self,
        delivery_task_id: str,
        review_dispatch_id: str,
        candidate_commit: str,
        verdict: str = "ACCEPT",
        reviewer_route: str = "cx/gpt-5.6-sol",
        reviewer_harness: str = "Claude Code",
        summary: str = "Independent review accepted on exact candidate HEAD",
        now: Optional[datetime] = None,
        capability: Optional[Union[ReviewerCapability, ControlCapability]] = None,
        reviewer_capability: Optional[ReviewerCapability] = None,
    ) -> ReviewEvidence:
        effective_cap = reviewer_capability if reviewer_capability is not None else capability
        if effective_cap is None:
            raise ProtocolViolationError(
                "Review evidence issuance requires an independently authenticated Reviewer or Control capability; "
                "unprivileged callers cannot obtain authoritative review evidence"
            )
        if getattr(effective_cap, "capability_id", "").startswith("adapter_internal_"):
            raise ProtocolViolationError(
                "Internal wildcard capability cannot be used to issue review evidence; independently authenticated capability required"
            )
        self.verify_capability(
            effective_cap,
            expected_task_id=delivery_task_id.strip() if delivery_task_id else "",
            expected_dispatch_id=review_dispatch_id.strip() if review_dispatch_id else "",
            expected_commit=candidate_commit.strip() if candidate_commit else "",
        )

        with self._lock:
            self._consumed_capabilities.add(effective_cap.capability_id)
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        if not review_dispatch_id or not isinstance(review_dispatch_id, str) or not review_dispatch_id.strip():
            raise ProtocolViolationError("review_dispatch_id cannot be blank")
        if not candidate_commit or not isinstance(candidate_commit, str) or not candidate_commit.strip():
            raise ProtocolViolationError("candidate_commit cannot be blank")
        if verdict not in ("ACCEPT", "CHANGES_REQUESTED", "BLOCKED"):
            raise ProtocolViolationError(f"Invalid review verdict {verdict!r}")
        if reviewer_route != "cx/gpt-5.6-sol":
            raise ProtocolViolationError(f"Invalid reviewer route {reviewer_route!r}; expected 'cx/gpt-5.6-sol'")
        if reviewer_harness != "Claude Code":
            raise ProtocolViolationError(f"Invalid reviewer harness {reviewer_harness!r}; expected 'Claude Code'")

        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        ts = now_dt.isoformat()
        ev_id = f"rev_ev_{uuid.uuid4().hex}"

        payload = f"REVIEW_EVIDENCE:{ev_id}:{delivery_task_id.strip()}:{review_dispatch_id.strip()}:{candidate_commit.strip()}:{verdict.strip()}:{reviewer_route.strip()}:{reviewer_harness.strip()}:{ts}".encode("utf-8")
        sig = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

        with self._lock:
            self._issued_evidence_ids.add(ev_id)

        return ReviewEvidence(
            review_dispatch_id=review_dispatch_id.strip(),
            delivery_task_id=delivery_task_id.strip(),
            candidate_commit=candidate_commit.strip(),
            verdict=verdict.strip(),
            reviewer_route=reviewer_route.strip(),
            reviewer_harness=reviewer_harness.strip(),
            evidence_hash=sig,
            signature=sig,
            summary=summary,
            timestamp=ts,
            evidence_id=ev_id,
            authority_id=id(self),
        )

    def issue_integration_evidence(
        self,
        delivery_task_id: str,
        candidate_commit: str,
        base_commit: str,
        gates_pass: bool = True,
        gate_results: Optional[Dict[str, bool]] = None,
        integrated_by: str = "Control",
        now: Optional[datetime] = None,
        capability: Optional[ControlCapability] = None,
        control_capability: Optional[ControlCapability] = None,
    ) -> IntegrationEvidence:
        effective_cap = control_capability if control_capability is not None else capability
        if effective_cap is None:
            raise ProtocolViolationError(
                "Integration evidence issuance requires an independently authenticated Control capability; "
                "unprivileged callers cannot obtain authoritative integration evidence"
            )
        if getattr(effective_cap, "capability_id", "").startswith("adapter_internal_"):
            raise ProtocolViolationError(
                "Internal wildcard capability cannot be used to issue integration evidence; independently authenticated Control capability required"
            )
        self.verify_capability(effective_cap, expected_role="Control", expected_task_id=delivery_task_id.strip() if delivery_task_id else "")

        with self._lock:
            self._consumed_capabilities.add(effective_cap.capability_id)
        if type(gates_pass) is not bool:
            raise ProtocolViolationError("gates_pass must be strict bool")
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        if not candidate_commit or not isinstance(candidate_commit, str) or not candidate_commit.strip():
            raise ProtocolViolationError("candidate_commit cannot be blank")
        if not base_commit or not isinstance(base_commit, str) or not base_commit.strip():
            raise ProtocolViolationError("base_commit cannot be blank")
        if not integrated_by or not isinstance(integrated_by, str) or not integrated_by.strip():
            raise ProtocolViolationError("integrated_by cannot be blank")

        if gate_results is None:
            gate_results = {g: gates_pass for g in MANDATORY_INTEGRATION_GATES}
        if not isinstance(gate_results, dict) or not gate_results:
            raise ProtocolViolationError("gate_results cannot be empty")
        for g in MANDATORY_INTEGRATION_GATES:
            if g not in gate_results:
                raise ProtocolViolationError(f"Missing mandatory integration gate {g!r}")

        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        ts = now_dt.isoformat()
        ev_id = f"int_ev_{uuid.uuid4().hex}"

        sorted_gates_json = json.dumps(gate_results, sort_keys=True)
        payload = f"INTEGRATION_EVIDENCE:{ev_id}:{delivery_task_id.strip()}:{candidate_commit.strip()}:{base_commit.strip()}:{gates_pass}:{sorted_gates_json}:{integrated_by.strip()}:{ts}".encode("utf-8")
        sig = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

        with self._lock:
            self._issued_evidence_ids.add(ev_id)

        return IntegrationEvidence(
            delivery_task_id=delivery_task_id.strip(),
            candidate_commit=candidate_commit.strip(),
            base_commit=base_commit.strip(),
            gates_pass=gates_pass,
            gate_results=gate_results,
            evidence_hash=sig,
            signature=sig,
            integrated_by=integrated_by.strip(),
            timestamp=ts,
            evidence_id=ev_id,
            authority_id=id(self),
        )

    def verify_capability(
        self,
        capability: Any,
        expected_role: Optional[str] = None,
        expected_task_id: Optional[str] = None,
        expected_dispatch_id: Optional[str] = None,
        expected_commit: Optional[str] = None,
    ) -> None:
        if capability is None:
            raise ProtocolViolationError("Capability cannot be None")

        if isinstance(capability, ControlCapability):
            if expected_role is not None and expected_role != "Control":
                raise ProtocolViolationError(f"Expected role {expected_role!r}, got ControlCapability")
            if getattr(capability, "capability_id", "").startswith("adapter_internal_"):
                raise ProtocolViolationError("Internal wildcard capability cannot be verified or used across external surfaces")
            with self._lock:
                if capability.capability_id in self._consumed_capabilities:
                    raise ProtocolViolationError(f"ControlCapability {capability.capability_id!r} has already been consumed")
                if capability.capability_id not in self._issued_capabilities:
                    raise ProtocolViolationError(f"ControlCapability {capability.capability_id!r} was not issued by internal evidence authority")
            if capability.authority_id != id(self):
                raise ProtocolViolationError("ControlCapability authority_id mismatch")
            tid_for_sig = capability.delivery_task_id.strip() if capability.delivery_task_id else "*"
            expected_sig = self._sign_control_capability(
                capability.capability_id, capability.role, tid_for_sig, capability.created_at
            )
            if not hmac.compare_digest(capability.signature, expected_sig):
                raise ProtocolViolationError("ControlCapability cryptographic signature mismatch; tampered or forged capability rejected")
            if capability.delivery_task_id is not None and expected_task_id is not None and expected_task_id != "*":
                if capability.delivery_task_id != expected_task_id:
                    raise ProtocolViolationError(
                        f"ControlCapability delivery_task_id mismatch: expected {expected_task_id!r}, got {capability.delivery_task_id!r}"
                    )
            return

        elif isinstance(capability, ReviewerCapability):
            if expected_role is not None and expected_role != "Reviewer":
                raise ProtocolViolationError(f"Expected role {expected_role!r}, got ReviewerCapability")
            if getattr(capability, "capability_id", "").startswith("adapter_internal_"):
                raise ProtocolViolationError("Internal wildcard capability cannot be verified or used across external surfaces")
            with self._lock:
                if capability.capability_id in self._consumed_capabilities:
                    raise ProtocolViolationError(f"ReviewerCapability {capability.capability_id!r} has already been consumed")
                if capability.capability_id not in self._issued_capabilities:
                    raise ProtocolViolationError(f"ReviewerCapability {capability.capability_id!r} was not issued by internal evidence authority")
            if capability.authority_id != id(self):
                raise ProtocolViolationError("ReviewerCapability authority_id mismatch")
            expected_sig = self._sign_reviewer_capability(
                capability.capability_id,
                capability.delivery_task_id,
                capability.review_dispatch_id,
                capability.candidate_commit,
                capability.reviewer_route,
                capability.reviewer_harness,
                capability.created_at,
            )
            if not hmac.compare_digest(capability.signature, expected_sig):
                raise ProtocolViolationError("ReviewerCapability cryptographic signature mismatch; tampered or forged capability rejected")
            if expected_task_id is not None and capability.delivery_task_id != expected_task_id:
                raise ProtocolViolationError(f"ReviewerCapability delivery_task_id mismatch: expected {expected_task_id!r}, got {capability.delivery_task_id!r}")
            if expected_dispatch_id is not None and capability.review_dispatch_id != expected_dispatch_id:
                raise ProtocolViolationError(f"ReviewerCapability review_dispatch_id mismatch: expected {expected_dispatch_id!r}, got {capability.review_dispatch_id!r}")
            if expected_commit is not None and capability.candidate_commit.lower() != expected_commit.lower():
                raise ProtocolViolationError(f"ReviewerCapability candidate_commit mismatch: expected {expected_commit!r}, got {capability.candidate_commit!r}")
            return

        raise ProtocolViolationError(f"Invalid capability type: expected ControlCapability or ReviewerCapability, got {type(capability).__name__}")

    def verify_and_consume_review_evidence(
        self,
        evidence: Any,
        expected_task_id: str,
        expected_dispatch_id: str,
        expected_candidate: str,
        expected_verdict: str,
        now: Optional[datetime] = None,
    ) -> None:
        if not isinstance(evidence, ReviewEvidence):
            raise ProtocolViolationError(
                f"Review evidence must be an instance of ReviewEvidence issued by internal authority; got {type(evidence).__name__}"
            )
        if not getattr(evidence, "signature", None) or not getattr(evidence, "evidence_id", None) or not getattr(evidence, "timestamp", None):
            raise ProtocolViolationError(
                "Review evidence missing mandatory cryptographic signature, evidence_id, or timestamp; plain caller values confer no authority"
            )

        with self._lock:
            if evidence.evidence_id in self._consumed_evidence_ids:
                raise ProtocolViolationError(
                    f"Review evidence {evidence.evidence_id!r} has already been consumed; replay attempt rejected fail closed"
                )
            if evidence.evidence_id not in self._issued_evidence_ids:
                raise ProtocolViolationError(
                    f"Review evidence {evidence.evidence_id!r} was not issued by internal evidence authority; provenance check failed"
                )

        # Freshness verification
        try:
            ev_dt = datetime.fromisoformat(evidence.timestamp)
        except Exception as ex:
            raise ProtocolViolationError(f"Malformed review evidence timestamp {evidence.timestamp!r}: {ex}")

        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        if ev_dt.tzinfo is None:
            ev_dt = ev_dt.replace(tzinfo=timezone.utc)

        age = (now_dt - ev_dt).total_seconds()
        if age > self.MAX_EVIDENCE_AGE_SECONDS:
            raise ProtocolViolationError(
                f"Review evidence is stale/expired: age {age:.1f}s exceeds limit {self.MAX_EVIDENCE_AGE_SECONDS}s; timestamp={evidence.timestamp!r}"
            )
        if (ev_dt - now_dt).total_seconds() > self.MAX_FUTURE_SKEW_SECONDS:
            raise ProtocolViolationError(
                f"Review evidence timestamp is in the future: {evidence.timestamp!r}"
            )

        # Recompute HMAC signature
        payload = f"REVIEW_EVIDENCE:{evidence.evidence_id}:{evidence.delivery_task_id}:{evidence.review_dispatch_id}:{evidence.candidate_commit}:{evidence.verdict}:{evidence.reviewer_route}:{evidence.reviewer_harness}:{evidence.timestamp}".encode("utf-8")
        expected_sig = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(evidence.signature, expected_sig):
            raise ProtocolViolationError("Review evidence cryptographic signature mismatch; tampered or forged evidence rejected")

        # Exact bindings
        if evidence.delivery_task_id != expected_task_id:
            raise ProtocolViolationError(f"Review evidence delivery_task_id mismatch: expected {expected_task_id!r}, got {evidence.delivery_task_id!r}")
        if evidence.review_dispatch_id != expected_dispatch_id:
            raise ProtocolViolationError(f"Review evidence review_dispatch_id mismatch: expected {expected_dispatch_id!r}, got {evidence.review_dispatch_id!r}")
        if evidence.candidate_commit.lower() != expected_candidate.lower():
            raise ProtocolViolationError(f"Review evidence candidate_commit mismatch: expected {expected_candidate!r}, got {evidence.candidate_commit!r}")
        if evidence.verdict != expected_verdict:
            raise ProtocolViolationError(f"Review evidence verdict mismatch: expected {expected_verdict!r}, got {evidence.verdict!r}")
        if evidence.reviewer_route != "cx/gpt-5.6-sol":
            raise ProtocolViolationError("Review evidence reviewer_route mismatch")
        if evidence.reviewer_harness != "Claude Code":
            raise ProtocolViolationError("Review evidence reviewer_harness mismatch")

        # Mark consumed
        with self._lock:
            self._consumed_evidence_ids.add(evidence.evidence_id)

    def verify_and_consume_integration_evidence(
        self,
        evidence: Any,
        expected_task_id: str,
        expected_candidate: str,
        expected_base: str,
        expected_gates_pass: bool,
        now: Optional[datetime] = None,
    ) -> None:
        if not isinstance(evidence, IntegrationEvidence):
            raise ProtocolViolationError(
                f"Integration evidence must be an instance of IntegrationEvidence issued by internal authority; got {type(evidence).__name__}"
            )
        if not getattr(evidence, "signature", None) or not getattr(evidence, "evidence_id", None) or not getattr(evidence, "timestamp", None):
            raise ProtocolViolationError(
                "Integration evidence missing mandatory cryptographic signature, evidence_id, or timestamp; plain caller values confer no authority"
            )

        with self._lock:
            if evidence.evidence_id in self._consumed_evidence_ids:
                raise ProtocolViolationError(
                    f"Integration evidence {evidence.evidence_id!r} has already been consumed; replay attempt rejected fail closed"
                )
            if evidence.evidence_id not in self._issued_evidence_ids:
                raise ProtocolViolationError(
                    f"Integration evidence {evidence.evidence_id!r} was not issued by internal evidence authority; provenance check failed"
                )

        # Freshness verification
        try:
            ev_dt = datetime.fromisoformat(evidence.timestamp)
        except Exception as ex:
            raise ProtocolViolationError(f"Malformed integration evidence timestamp {evidence.timestamp!r}: {ex}")

        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        if ev_dt.tzinfo is None:
            ev_dt = ev_dt.replace(tzinfo=timezone.utc)

        age = (now_dt - ev_dt).total_seconds()
        if age > self.MAX_EVIDENCE_AGE_SECONDS:
            raise ProtocolViolationError(
                f"Integration evidence is stale/expired: age {age:.1f}s exceeds limit {self.MAX_EVIDENCE_AGE_SECONDS}s; timestamp={evidence.timestamp!r}"
            )
        if (ev_dt - now_dt).total_seconds() > self.MAX_FUTURE_SKEW_SECONDS:
            raise ProtocolViolationError(
                f"Integration evidence timestamp is in the future: {evidence.timestamp!r}"
            )

        # Recompute HMAC signature
        sorted_gates_json = json.dumps(evidence.gate_results, sort_keys=True)
        payload = f"INTEGRATION_EVIDENCE:{evidence.evidence_id}:{evidence.delivery_task_id}:{evidence.candidate_commit}:{evidence.base_commit}:{evidence.gates_pass}:{sorted_gates_json}:{evidence.integrated_by}:{evidence.timestamp}".encode("utf-8")
        expected_sig = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(evidence.signature, expected_sig):
            raise ProtocolViolationError("Integration evidence cryptographic signature mismatch; tampered or forged evidence rejected")

        # Exact bindings
        if evidence.delivery_task_id != expected_task_id:
            raise ProtocolViolationError(f"Integration evidence delivery_task_id mismatch: expected {expected_task_id!r}, got {evidence.delivery_task_id!r}")
        if evidence.candidate_commit.lower() != expected_candidate.lower():
            raise ProtocolViolationError(f"Integration evidence candidate_commit mismatch: expected {expected_candidate!r}, got {evidence.candidate_commit!r}")
        if evidence.base_commit.lower() != expected_base.lower():
            raise ProtocolViolationError(f"Integration evidence base_commit mismatch: expected {expected_base!r}, got {evidence.base_commit!r}")
        if evidence.gates_pass is not expected_gates_pass:
            raise ProtocolViolationError(f"Integration evidence gates_pass mismatch: expected {expected_gates_pass!r}, got {evidence.gates_pass!r}")
        if evidence.integrated_by != "Control":
            raise ProtocolViolationError(f"Integration evidence integrated_by mismatch: expected 'Control', got {evidence.integrated_by!r}")

        # Gate completeness
        for g in MANDATORY_INTEGRATION_GATES:
            if g not in evidence.gate_results or (expected_gates_pass and evidence.gate_results[g] is not True):
                raise ProtocolViolationError(f"Mandatory gate {g!r} missing or failing in integration evidence")

        # Mark consumed
        with self._lock:
            self._consumed_evidence_ids.add(evidence.evidence_id)


def make_review_evidence(
    delivery_task_id: str,
    review_dispatch_id: str,
    candidate_commit: str,
    verdict: str = "ACCEPT",
    reviewer_route: str = "cx/gpt-5.6-sol",
    reviewer_harness: str = "Claude Code",
    summary: str = "Independent review accepted on exact candidate HEAD",
    now: Optional[datetime] = None,
    authority: Optional[Any] = None,
    capability: Optional[Any] = None,
    reviewer_capability: Optional[Any] = None,
) -> ReviewEvidence:
    """Public review evidence factory. When called without an internal authority component,
    it produces unauthenticated evidence that cannot confer lifecycle transition authority."""
    if authority is not None:
        if hasattr(authority, "evidence_authority"):
            authority = authority.evidence_authority
        return authority.issue_review_evidence(
            delivery_task_id=delivery_task_id,
            review_dispatch_id=review_dispatch_id,
            candidate_commit=candidate_commit,
            verdict=verdict,
            reviewer_route=reviewer_route,
            reviewer_harness=reviewer_harness,
            summary=summary,
            now=now,
            capability=capability,
            reviewer_capability=reviewer_capability,
        )
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    ev_bytes = f"{delivery_task_id}:{review_dispatch_id}:{candidate_commit}:{verdict}:{reviewer_route}:{now_dt.isoformat()}".encode("utf-8")
    ev_hash = hashlib.sha256(ev_bytes).hexdigest()
    return ReviewEvidence(
        review_dispatch_id=review_dispatch_id.strip() if review_dispatch_id else "",
        delivery_task_id=delivery_task_id.strip() if delivery_task_id else "",
        candidate_commit=candidate_commit.strip() if candidate_commit else "",
        verdict=verdict.strip() if verdict else "",
        reviewer_route=reviewer_route.strip() if reviewer_route else "",
        reviewer_harness=reviewer_harness.strip() if reviewer_harness else "",
        evidence_hash=ev_hash,
        signature="",
        summary=summary,
        timestamp=now_dt.isoformat(),
        evidence_id=f"caller_unauth_{uuid.uuid4().hex}",
    )


def make_integration_evidence(
    delivery_task_id: str,
    candidate_commit: str,
    base_commit: str,
    gates_pass: bool = True,
    gate_results: Optional[Dict[str, bool]] = None,
    integrated_by: str = "Control",
    now: Optional[datetime] = None,
    authority: Optional[Any] = None,
    capability: Optional[Any] = None,
    control_capability: Optional[Any] = None,
) -> IntegrationEvidence:
    """Public integration evidence factory. When called without an internal authority component,
    it produces unauthenticated evidence that cannot confer lifecycle transition authority."""
    if authority is not None:
        if hasattr(authority, "evidence_authority"):
            authority = authority.evidence_authority
        return authority.issue_integration_evidence(
            delivery_task_id=delivery_task_id,
            candidate_commit=candidate_commit,
            base_commit=base_commit,
            gates_pass=gates_pass,
            gate_results=gate_results,
            integrated_by=integrated_by,
            now=now,
            capability=capability,
            control_capability=control_capability,
        )
    if gate_results is None:
        gate_results = {
            "authority": gates_pass,
            "candidate": gates_pass,
            "scope": gates_pass,
            "encoding": gates_pass,
            "security": gates_pass,
            "contract": gates_pass,
            "migration": gates_pass,
            "focused_tests": gates_pass,
            "regression": gates_pass,
            "evidence": gates_pass,
            "independent_review": gates_pass,
        }
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    ev_bytes = f"{delivery_task_id}:{candidate_commit}:{base_commit}:{gates_pass}:{json.dumps(gate_results, sort_keys=True)}".encode("utf-8")
    ev_hash = hashlib.sha256(ev_bytes).hexdigest()
    return IntegrationEvidence(
        delivery_task_id=delivery_task_id.strip() if delivery_task_id else "",
        candidate_commit=candidate_commit.strip() if candidate_commit else "",
        base_commit=base_commit.strip() if base_commit else "",
        gates_pass=gates_pass,
        gate_results=gate_results,
        evidence_hash=ev_hash,
        signature="",
        integrated_by=integrated_by,
        timestamp=now_dt.isoformat(),
        evidence_id=f"caller_unauth_{uuid.uuid4().hex}",
    )


def _validate_unpadded_identity(
    val: Any,
    field_name: str,
    container_name: str,
    required: bool = True,
    allowed_values: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Validate that an identity field on a dataclass or evidence object is a non-blank,
    unpadded string matching optional allowed values. Fails closed with RoutingEvidenceError."""
    desc = f"field {field_name!r}"
    if field_name == "archive_reference":
        desc = "archive reference"
    elif field_name == "timestamp":
        desc = "machine-readable timestamp"

    if val is None:
        if required:
            raise RoutingEvidenceError(
                f"{container_name} missing {desc}; must be a non-blank string; got NoneType: None; fails closed"
            )
        return None
    if not isinstance(val, str):
        raise RoutingEvidenceError(
            f"{container_name} {desc} must be a non-blank string; got {type(val).__name__}: {val!r}; fails closed"
        )
    if not val.strip():
        raise RoutingEvidenceError(
            f"{container_name} {desc} cannot be blank; fails closed"
        )
    if val != val.strip():
        raise RoutingEvidenceError(
            f"{container_name} {desc} {val!r} has invalid whitespace padding; fails closed"
        )
    if allowed_values is not None and val not in allowed_values:
        if "model" in desc:
            raise RoutingEvidenceError(
                f"{container_name} {desc} {val!r} does not match expected model; exact routed or canonical backend identity required, got {val!r}; expected one of {allowed_values!r}"
            )
        raise RoutingEvidenceError(
            f"{container_name} {desc} {val!r} is invalid; expected one of {allowed_values!r}"
        )
    return val


_SECRET_PATTERNS = [
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
_MUTABLE_DB_PATH_RE = re.compile(
    r"(\b[A-Za-z]:[/\\]|\b/(?:var|tmp|home|etc|usr)/)[^\s]+\.(?:db|sqlite|sqlite3)\b",
    re.IGNORECASE,
)


_DEFAULT_LAUNCH = object()



def _extract_and_validate_alias(
    mapping: Mapping[str, Any],
    aliases: Sequence[str],
    field_label: str,
    container_label: str,
    required: bool = True,
    exact_raw: Optional[str] = None,
    allowed_values: Optional[Sequence[str]] = None,
    disallowed_substrings: Optional[Sequence[str]] = None,
    blank_or_missing_hint: Optional[str] = None,
) -> Optional[str]:
    """Validate all present aliases for type (must be non-blank string), exactness,
    disallowed substrings, and mutual semantic consistency before choosing a canonical value."""
    # Blocker 3: Do not silently exclude present None. Every present alias key must be checked.
    present_keys = [k for k in aliases if k in mapping]
    if not present_keys:
        if required:
            msg = f"{container_label} missing required field {field_label!r}; fails closed"
            if blank_or_missing_hint:
                msg += f"; {blank_or_missing_hint}"
            raise RoutingEvidenceError(msg)
        return None

    # Check each present alias for type, None, non-blank form, and whitespace padding
    for k in present_keys:
        val = mapping[k]
        if val is None:
            msg = f"{container_label} field {k!r} must be a non-blank string; got NoneType: None; fails closed"
            if blank_or_missing_hint:
                msg += f"; {blank_or_missing_hint}"
            raise RoutingEvidenceError(msg)
        if not isinstance(val, str):
            raise RoutingEvidenceError(
                f"{container_label} field {k!r} must be a non-blank string; got {type(val).__name__}: {val!r}; fails closed"
            )
        if not val.strip():
            msg = f"{container_label} field {k!r} must be a non-blank string; cannot be blank; fails closed"
            if blank_or_missing_hint:
                msg += f"; {blank_or_missing_hint}"
            raise RoutingEvidenceError(msg)
        if val != val.strip():
            raise RoutingEvidenceError(
                f"{container_label} field {k!r} {val!r} has invalid whitespace padding; fails closed"
            )

    # Check mutual semantic consistency across all present aliases before checking exact_raw
    cleaned_values = {mapping[k].strip() for k in present_keys}
    if len(cleaned_values) > 1:
        conflicts = ", ".join(f"{k}={mapping[k]!r}" for k in sorted(present_keys))
        raise RoutingEvidenceError(
            f"Contradictory {field_label} aliases in {container_label}: {conflicts}"
        )

    if exact_raw is not None:
        for k in present_keys:
            if mapping[k] != exact_raw:
                raise RoutingEvidenceError(
                    f"{container_label} field {k!r} {mapping[k]!r} is invalid; must be exact raw {exact_raw!r}"
                )

    if allowed_values is not None:
        for k in present_keys:
            if mapping[k] not in allowed_values:
                if "model" in field_label or "model" in k:
                    raise RoutingEvidenceError(
                        f"{container_label} field {k!r} {mapping[k]!r} is invalid; does not match expected model (exact routed or canonical); expected one of {list(allowed_values)!r}"
                    )
                raise RoutingEvidenceError(
                    f"{container_label} field {k!r} {mapping[k]!r} is invalid; expected one of {list(allowed_values)!r}"
                )

    if disallowed_substrings:
        for k in present_keys:
            for sub in disallowed_substrings:
                if sub.lower() in mapping[k].lower():
                    raise RoutingEvidenceError(
                        f"Forbidden {sub!r} in {container_label} field {k!r}: {mapping[k]!r}"
                    )

    if exact_raw is not None:
        return exact_raw
    return mapping[present_keys[0]].strip()

def _validate_launch_mapping(
    mapping: Any,
    label: str,
) -> Tuple[str, str, str, str]:
    """Validate a launch evidence mapping (launch_requested or launch_effective).
    Returns normalized (harness, provider, model, effort)."""
    if mapping is None:
        raise RoutingEvidenceError(f"Execution envelope missing required field {label!r}; fails closed")
    if not isinstance(mapping, Mapping):
        raise RoutingEvidenceError(
            f"Execution envelope {label!r} must be a machine-readable mapping; got {type(mapping).__name__}"
        )
    if not mapping:
        raise RoutingEvidenceError(f"Execution envelope {label!r} is empty; fails closed")

    # 1. Harness check
    clean_h = _extract_and_validate_alias(
        mapping, ("harness",), "harness", label, required=True, disallowed_substrings=["antigravity"]
    )

    # 2. Provider / Router check: exact raw '9router'
    clean_p = _extract_and_validate_alias(
        mapping, ("provider", "router", "route_provider", "source"), "provider", label,
        required=True, exact_raw="9router", disallowed_substrings=["antigravity"]
    )

    # 3. Model / Route check
    clean_m = _extract_and_validate_alias(
        mapping, ("model", "route"), "model", label, required=True
    )
    if clean_m in ("cx/gpt-5.6-sol-high", "cx/gpt-5.6-sol:high", "ag/gemini-3.8-flash-high-high"):
        raise RoutingEvidenceError(
            f"Combined model/effort slug {clean_m!r} in {label} is invalid; model and effort MUST be separate fields"
        )

    # 4. Effort check: exact raw canonical spelling
    clean_e = _extract_and_validate_alias(
        mapping, ("effort",), "effort", label, required=True, exact_raw="high"
    )

    return clean_h, clean_p, clean_m, clean_e


def make_execution_envelope(
    delivery_task_id: str,
    dispatch_id: str,
    phase: str = "implement",
    harness: Optional[str] = None,
    model: Optional[str] = None,
    effort: str = "high",
    provider: str = "9router",
    archive_reference: str = "term_archive_default",
    request_id: str = "req_default_01",
    timestamp: Optional[str] = None,
    verified: bool = True,
    recorded_after_dispatch: bool = True,
    now: Optional[datetime] = None,
    orca_task_id: Optional[str] = None,
    launch_requested: Any = _DEFAULT_LAUNCH,
    launch_effective: Any = _DEFAULT_LAUNCH,
) -> ExecutionEnvelope:
    """Factory to build a valid, machine-readable execution envelope anchored to
    exact delivery_task_id, dispatch_id, and phase."""
    clean_phase = (phase or "implement").strip()
    if clean_phase not in ("implement", "review"):
        raise RoutingEvidenceError(f"Invalid phase {phase!r}; must be 'implement' or 'review'")

    if clean_phase == "implement":
        harness = harness or "Codex CLI"
        model = model or "ag/gemini-3.8-flash-high"
        backend_provider = "google"
        backend_model = "ag/gemini-3.8-flash-high"
    else:
        harness = harness or "Claude Code"
        model = model or "cx/gpt-5.6-sol"
        backend_provider = "openai"
        backend_model = "cx/gpt-5.6-sol"

    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    ts = timestamp or (now_dt + timedelta(seconds=1)).isoformat()

    route = {
        "provider": provider,
        "harness": harness,
        "model": model,
        "effort": effort,
    }
    live_ev = LiveTerminalEvidence(
        harness=harness,
        provider=provider,
        route=model,
        archive_reference=archive_reference,
        verified=verified,
        dispatch_id=dispatch_id,
        delivery_task_id=delivery_task_id,
        effort=effort,
    )
    usage_ev = UsageEvidence(
        backend_provider=backend_provider,
        backend_model=backend_model,
        recorded_after_dispatch=recorded_after_dispatch,
        timestamp=ts,
        request_id=request_id,
        dispatch_id=dispatch_id,
        delivery_task_id=delivery_task_id,
        router="9router",
    )
    clean_orca_tid = (
        orca_task_id.strip()
        if (orca_task_id is not None and isinstance(orca_task_id, str))
        else (orca_task_id if orca_task_id is not None else f"orca-{delivery_task_id.lower()}")
    )
    if launch_requested is _DEFAULT_LAUNCH:
        launch_requested = {
            "harness": harness,
            "provider": provider,
            "route": model,
            "model": model,
            "effort": effort,
        }
    if launch_effective is _DEFAULT_LAUNCH:
        launch_effective = {
            "harness": harness,
            "provider": provider,
            "route": model,
            "model": model,
            "effort": effort,
        }
    return ExecutionEnvelope(
        delivery_task_id=delivery_task_id,
        dispatch_id=dispatch_id,
        dispatch_origin="dely dispatch",
        phase=clean_phase,
        route=route,
        orca_task_id=clean_orca_tid,
        live_terminal_evidence=live_ev,
        usage_evidence=usage_ev,
        launch_requested=launch_requested,
        launch_effective=launch_effective,
    )


def validate_execution_envelope(
    envelope: Union[ExecutionEnvelope, Dict[str, Any]],
    expected_phase: Optional[str] = None,
    expected_delivery_task_id: Optional[str] = None,
    expected_dispatch_id: Optional[str] = None,
    expected_orca_task_id: Optional[str] = None,
    dispatch_time: Optional[datetime] = None,
) -> List[str]:
    """Validate a dispatch execution envelope machine-readably according to repository
    routing authority policy in AGENTS.md:
    - dispatch origin MUST be 'dely dispatch', never direct Orca worker-start;
    - delivery_task_id and dispatch_id are mandatory required identity fields;
    - bound identities must match expected delivery task and dispatch attempt;
    - route provider MUST be '9router' for implement and review routes;
    - expected harness, model, and effort MUST be separate fields;
    - combined slugs (such as 'cx/gpt-5.6-sol-high') are strictly invalid;
    - launch requested and effective evidence alone are insufficient;
    - live terminal/archive evidence MUST be verified (verified is True) and identify
      expected harness/provider route anchored to exact dispatch attempt;
    - 9Router usage evidence MUST identify expected backend provider/model per phase,
      prove route via 9router, anchored to exact dispatch, and machine-readable timestamp
      actually not earlier than dispatch time;
    - evidence references MUST NOT contain raw secrets, credentials, or mutable local db paths;
    - missing, contradictory, or unanchored evidence fails closed.
    """
    if isinstance(envelope, ExecutionEnvelope):
        data = {
            "delivery_task_id": envelope.delivery_task_id,
            "dispatch_id": envelope.dispatch_id,
            "dispatch_origin": envelope.dispatch_origin,
            "phase": envelope.phase,
            "route": envelope.route,
            "orca_task_id": envelope.orca_task_id,
            "live_terminal_evidence": envelope.live_terminal_evidence,
            "usage_evidence": envelope.usage_evidence,
            "launch_requested": envelope.launch_requested,
            "launch_effective": envelope.launch_effective,
        }
    elif isinstance(envelope, dict):
        data = envelope
    else:
        raise RoutingEvidenceError(
            f"Execution envelope must be dict or ExecutionEnvelope; got {type(envelope).__name__}"
        )

    # 1. Delivery Task ID: mandatory and non-blank
    clean_dtid = _extract_and_validate_alias(
        data, ("delivery_task_id", "task_id", "delivery_task"), "delivery_task_id",
        "Execution envelope", required=True
    )
    if expected_delivery_task_id is not None:
        clean_exp_dtid = expected_delivery_task_id.strip()
        if clean_dtid != clean_exp_dtid:
            raise RoutingEvidenceError(
                f"Envelope delivery_task_id mismatch: expected {clean_exp_dtid!r}, got {clean_dtid!r}"
            )

    # 2. Dispatch ID: mandatory and non-blank
    clean_disp_id = _extract_and_validate_alias(
        data, ("dispatch_id", "dispatch"), "dispatch_id",
        "Execution envelope", required=True
    )
    if expected_dispatch_id is not None:
        clean_exp_disp = expected_dispatch_id.strip()
        if clean_disp_id != clean_exp_disp:
            raise RoutingEvidenceError(
                f"Envelope dispatch_id mismatch: expected {clean_exp_disp!r}, got {clean_disp_id!r}"
            )

    # 3. Orca Task ID: mandatory and non-blank
    clean_otid = _extract_and_validate_alias(
        data, ("orca_task_id",), "orca_task_id",
        "Execution envelope", required=True
    )
    if expected_orca_task_id is not None:
        clean_exp_otid = expected_orca_task_id.strip()
        if clean_otid != clean_exp_otid:
            raise RoutingEvidenceError(
                f"Envelope orca_task_id mismatch: expected {clean_exp_otid!r}, got {clean_otid!r}"
            )

    # 4. Dispatch origin: MUST be 'dely dispatch'
    clean_origin = _extract_and_validate_alias(
        data, ("dispatch_origin", "origin"), "dispatch_origin",
        "Execution envelope", required=True, blank_or_missing_hint="every delivery dispatch MUST go through 'dely dispatch'"
    )
    if clean_origin != "dely dispatch":
        clean_lower = clean_origin.lower()
        if "worker-start" in clean_lower or clean_lower in ("worker-start", "orca worker-start", "direct worker-start", "orca"):
            raise RoutingEvidenceError(
                f"Direct Orca worker-start dispatch origin {clean_origin!r} is strictly forbidden; "
                f"every delivery dispatch MUST go through 'dely dispatch'"
            )
        raise RoutingEvidenceError(
            f"Invalid dispatch origin {clean_origin!r}; every delivery dispatch MUST go through 'dely dispatch'"
        )

    # 4. Phase: must be 'implement' or 'review'
    phase = data.get("phase")
    clean_phase = (phase or "").strip() if isinstance(phase, str) else ""
    if clean_phase not in ("implement", "review"):
        raise RoutingEvidenceError(f"Invalid execution envelope phase {phase!r}; must be 'implement' or 'review'")
    if expected_phase is not None and clean_phase != expected_phase.strip():
        raise RoutingEvidenceError(f"Phase mismatch: expected {expected_phase!r}, got {clean_phase!r}")

    # 5. Route
    route = data.get("route")
    if not isinstance(route, dict):
        raise RoutingEvidenceError(f"Execution envelope route must be a dict; got {type(route).__name__}")

    # Provider check: must be exact raw '9router'
    clean_p = _extract_and_validate_alias(
        route, ("provider", "router", "route_provider", "source"), "provider",
        "Execution envelope route", required=True, exact_raw="9router", disallowed_substrings=["antigravity"]
    )

    # Harness check: separate field
    clean_h = _extract_and_validate_alias(
        route, ("harness",), "harness", "Execution envelope route", required=True, disallowed_substrings=["antigravity"]
    )
    expected_harness = "Codex CLI" if clean_phase == "implement" else "Claude Code"
    if clean_h != expected_harness:
        raise RoutingEvidenceError(
            f"Harness mismatch for phase {clean_phase!r}: expected {expected_harness!r}, got {clean_h!r}"
        )

    # Model check: separate field
    clean_m = _extract_and_validate_alias(
        route, ("model", "route"), "model", "Execution envelope route", required=True
    )
    if clean_m in ("cx/gpt-5.6-sol-high", "cx/gpt-5.6-sol:high", "ag/gemini-3.8-flash-high-high"):
        raise RoutingEvidenceError(
            f"Combined model/effort slug {clean_m!r} is invalid; "
            f"model and effort MUST be separate fields (e.g. model='cx/gpt-5.6-sol', effort='high')"
        )
    expected_model = "ag/gemini-3.8-flash-high" if clean_phase == "implement" else "cx/gpt-5.6-sol"
    if clean_m != expected_model:
        raise RoutingEvidenceError(
            f"Model mismatch for phase {clean_phase!r}: expected {expected_model!r}, got {clean_m!r}"
        )

    # Effort check: separate field, exact raw canonical spelling
    clean_e = _extract_and_validate_alias(
        route, ("effort",), "effort", "Execution envelope route", required=True, exact_raw="high"
    )

    # 6. Launch requested and launch effective validation & mutual binding
    launch_req = data.get("launch_requested")
    if "launch_requested" not in data or launch_req is None:
        raise RoutingEvidenceError("Execution envelope missing required field 'launch_requested'; fails closed")
    req_h, req_p, req_m, req_e = _validate_launch_mapping(
        launch_req, "launch_requested"
    )

    launch_eff = data.get("launch_effective")
    if "launch_effective" not in data or launch_eff is None:
        raise RoutingEvidenceError("Execution envelope missing required field 'launch_effective'; fails closed")
    eff_h, eff_p, eff_m, eff_e = _validate_launch_mapping(
        launch_eff, "launch_effective"
    )


    # Phase-specific expected identity validation
    if req_h != expected_harness:
        raise RoutingEvidenceError(
            f"launch_requested identifies harness {req_h!r}, expected {expected_harness!r} for phase {clean_phase!r}"
        )
    if req_m != expected_model:
        raise RoutingEvidenceError(
            f"launch_requested model/route {req_m!r} does not match expected model {expected_model!r} for phase {clean_phase!r}"
        )

    # Requested vs Effective mutual consistency
    if req_h != eff_h:
        raise RoutingEvidenceError(
            f"Contradictory launch evidence: launch_requested harness {req_h!r} does not match launch_effective harness {eff_h!r}"
        )
    if req_p != eff_p:
        raise RoutingEvidenceError(
            f"Contradictory launch evidence: launch_requested provider {req_p!r} does not match launch_effective provider {eff_p!r}"
        )
    if req_m != eff_m:
        raise RoutingEvidenceError(
            f"Contradictory launch evidence: launch_requested model {req_m!r} does not match launch_effective model {eff_m!r}"
        )
    if req_e != eff_e:
        raise RoutingEvidenceError(
            f"Contradictory launch evidence: launch_requested effort {req_e!r} does not match launch_effective effort {eff_e!r}"
        )

    # Launch evidence vs Route consistency
    if req_h != clean_h:
        raise RoutingEvidenceError(
            f"Contradictory launch evidence: launch harness {req_h!r} does not match route harness {clean_h!r}"
        )
    if req_p != clean_p:
        raise RoutingEvidenceError(
            f"Contradictory launch evidence: launch provider {req_p!r} does not match route provider {clean_p!r}"
        )
    if req_m != clean_m:
        raise RoutingEvidenceError(
            f"Contradictory launch evidence: launch model {req_m!r} does not match route model {clean_m!r}"
        )
    if req_e != clean_e:
        raise RoutingEvidenceError(
            f"Contradictory launch evidence: launch effort {req_e!r} does not match route effort {clean_e!r}"
        )

    # Evidence sufficiency: launch evidence alone is insufficient
    live_terminal = data.get("live_terminal_evidence")
    usage_ev = data.get("usage_evidence")

    if not live_terminal or not usage_ev:
        raise RoutingEvidenceError(
            "launch.requested and launch.effective are necessary but insufficient; "
            "dispatch is valid only when live terminal/archive evidence identifies the expected harness/provider "
            "and 9Router usage evidence records the backend request after dispatch"
        )

    # 7. Live terminal evidence validation
    if isinstance(live_terminal, LiveTerminalEvidence):
        _validate_unpadded_identity(live_terminal.harness, "harness", "Live terminal evidence", required=True, allowed_values=(expected_harness,))
        _validate_unpadded_identity(live_terminal.provider, "provider", "Live terminal evidence", required=True, allowed_values=("9router",))
        _validate_unpadded_identity(live_terminal.route, "route", "Live terminal evidence", required=True, allowed_values=(expected_model,))
        _validate_unpadded_identity(live_terminal.archive_reference, "archive_reference", "Live terminal evidence", required=True)
        _validate_unpadded_identity(live_terminal.dispatch_id, "dispatch_id", "Live terminal evidence", required=True)
        _validate_unpadded_identity(live_terminal.delivery_task_id, "delivery_task_id", "Live terminal evidence", required=True)
        _validate_unpadded_identity(live_terminal.effort, "effort", "Live terminal evidence", required=True, allowed_values=("high",))
        live_h = live_terminal.harness
        live_p = live_terminal.provider
        live_r = live_terminal.route
        live_ver = live_terminal.verified
        live_ref = live_terminal.archive_reference or live_terminal.terminal_id
        live_disp = live_terminal.dispatch_id
        live_task = live_terminal.delivery_task_id
        live_eff = live_terminal.effort
    elif isinstance(live_terminal, dict):
        if not live_terminal:
            raise RoutingEvidenceError("Live terminal evidence is empty; fails closed")
        live_p = _extract_and_validate_alias(
            live_terminal, ("provider", "router", "route_provider", "source"), "provider",
            "Live terminal evidence", required=True, exact_raw="9router", disallowed_substrings=["antigravity"]
        )
        live_h = _extract_and_validate_alias(
            live_terminal, ("harness",), "harness", "Live terminal evidence", required=True, exact_raw=expected_harness, disallowed_substrings=["antigravity"]
        )
        live_r = _extract_and_validate_alias(
            live_terminal, ("route", "model"), "route", "Live terminal evidence", required=True, exact_raw=expected_model
        )
        live_ref = _extract_and_validate_alias(
            live_terminal, ("archive_reference", "terminal_id", "archive"), "archive_reference",
            "Live terminal evidence", required=True
        )
        live_disp = _extract_and_validate_alias(
            live_terminal, ("dispatch_id", "dispatch"), "dispatch_id", "Live terminal evidence", required=True
        )
        live_task = _extract_and_validate_alias(
            live_terminal, ("delivery_task_id", "task_id", "delivery_task"), "delivery_task_id",
            "Live terminal evidence", required=True
        )
        live_eff = _extract_and_validate_alias(
            live_terminal, ("effort",), "effort", "Live terminal evidence", required=True, exact_raw="high"
        )
        live_ver = live_terminal.get("verified")
    else:
        raise RoutingEvidenceError(f"Invalid live_terminal_evidence type: {type(live_terminal).__name__}")

    if live_ver is not True:
        raise RoutingEvidenceError(
            f"Live terminal evidence verified must be strictly True (got {live_ver!r}); unverified terminal fails closed"
        )
    if not live_h or live_h != expected_harness:
        raise RoutingEvidenceError(
            f"Live terminal evidence identifies harness {live_h!r}, expected {expected_harness!r}"
        )
    if not live_p or live_p != "9router":
        raise RoutingEvidenceError(
            f"Live terminal evidence identifies provider {live_p!r}, expected '9router'"
        )
    if not live_r or live_r != expected_model:
        raise RoutingEvidenceError(
            f"Live terminal evidence identifies route {live_r!r}, expected {expected_model!r}"
        )
    clean_live_eff = (live_eff or "").strip() if isinstance(live_eff, str) else ""
    if not clean_live_eff:
        raise RoutingEvidenceError(
            "Live terminal evidence missing required effort field; fails closed"
        )
    if clean_live_eff != "high":
        raise RoutingEvidenceError(
            f"Live terminal evidence identifies effort {live_eff!r}, expected 'high'"
        )
    if not live_ref or not str(live_ref).strip():
        raise RoutingEvidenceError("Live terminal evidence missing terminal/archive reference")

    clean_live_disp = (live_disp or "").strip() if isinstance(live_disp, str) else ""
    if not clean_live_disp:
        raise RoutingEvidenceError(
            "Live terminal evidence missing required dispatch_id anchor; fails closed"
        )
    if clean_live_disp != clean_disp_id:
        raise RoutingEvidenceError(
            f"Live terminal evidence dispatch ID {live_disp!r} does not match dispatch {clean_disp_id!r}"
        )

    clean_live_task = (live_task or "").strip() if isinstance(live_task, str) else ""
    if not clean_live_task:
        raise RoutingEvidenceError(
            "Live terminal evidence missing required delivery_task_id anchor; fails closed"
        )
    if clean_live_task != clean_dtid:
        raise RoutingEvidenceError(
            f"Live terminal evidence task ID {live_task!r} does not match task {clean_dtid!r}"
        )

    # Mutual consistency between live terminal evidence and launch evidence
    if live_h != req_h:
        raise RoutingEvidenceError(
            f"Contradictory evidence: live terminal harness {live_h!r} does not match launch harness {req_h!r}"
        )
    if live_p != req_p:
        raise RoutingEvidenceError(
            f"Contradictory evidence: live terminal provider {live_p!r} does not match launch provider {req_p!r}"
        )
    if live_r != req_m:
        raise RoutingEvidenceError(
            f"Contradictory evidence: live terminal route {live_r!r} does not match launch model {req_m!r}"
        )
    if clean_live_eff != req_e:
        raise RoutingEvidenceError(
            f"Contradictory evidence: live terminal effort {clean_live_eff!r} does not match launch effort {req_e!r}"
        )

    # 8. Usage evidence validation
    allowed_u_providers = ("google",) if clean_phase == "implement" else ("openai",)
    allowed_u_models = ("ag/gemini-3.8-flash-high",) if clean_phase == "implement" else ("cx/gpt-5.6-sol",)

    if isinstance(usage_ev, UsageEvidence):
        _validate_unpadded_identity(usage_ev.backend_provider, "backend_provider", "9Router usage evidence", required=True, allowed_values=allowed_u_providers)
        _validate_unpadded_identity(usage_ev.backend_model, "backend_model", "9Router usage evidence", required=True, allowed_values=allowed_u_models)
        _validate_unpadded_identity(usage_ev.timestamp, "timestamp", "9Router usage evidence", required=True)
        _validate_unpadded_identity(usage_ev.request_id, "request_id", "9Router usage evidence", required=True)
        _validate_unpadded_identity(usage_ev.dispatch_id, "dispatch_id", "9Router usage evidence", required=True)
        _validate_unpadded_identity(usage_ev.delivery_task_id, "delivery_task_id", "9Router usage evidence", required=True)
        _validate_unpadded_identity(usage_ev.router, "router", "9Router usage evidence", required=True, allowed_values=("9router",))
        u_p = usage_ev.backend_provider
        u_m = usage_ev.backend_model
        u_after = usage_ev.recorded_after_dispatch
        u_ts = usage_ev.timestamp
        u_disp = usage_ev.dispatch_id
        u_task = usage_ev.delivery_task_id
        u_router = usage_ev.router

        if u_router is None or not isinstance(u_router, str) or not u_router.strip():
            raise RoutingEvidenceError(
                f"9Router usage evidence missing required non-blank field 'router'; got {u_router!r}"
            )
        if "antigravity" in u_router.lower():
            raise RoutingEvidenceError(
                f"Antigravity native router {u_router!r} in usage evidence is strictly forbidden; fails closed"
            )
        # Exact raw router identity: do not normalize whitespace into validity
        if u_router != "9router":
            raise RoutingEvidenceError(
                f"9Router usage evidence route source {u_router!r} is invalid; route MUST be via '9router'"
            )
        clean_u_router = u_router
    elif isinstance(usage_ev, Mapping):
        if not usage_ev:
            raise RoutingEvidenceError("Usage evidence is empty; fails closed")

        # Valid router aliases: "router", "route_provider", "source"
        valid_router_aliases = ("router", "route_provider", "source")

        # Reject any foreign or unrecognized keys purporting to define router/route
        for k in usage_ev.keys():
            if isinstance(k, str):
                k_lower = k.strip().lower()
                if ("router" in k_lower or "route" in k_lower or "source" in k_lower) and k not in valid_router_aliases:
                    raise RoutingEvidenceError(
                        f"Foreign or unrecognized router alias {k!r} in usage evidence; fails closed"
                    )

        # Explicit router identity in mapping: no implicit default allowed! Exact raw '9router'.
        clean_u_router = _extract_and_validate_alias(
            usage_ev, valid_router_aliases, "router", "Usage evidence",
            required=True, exact_raw="9router", disallowed_substrings=["antigravity"]
        )

        clean_u_p_raw = _extract_and_validate_alias(
            usage_ev, ("backend_provider", "provider"), "backend_provider", "Usage evidence", required=True, allowed_values=allowed_u_providers
        )
        u_p = clean_u_p_raw

        clean_u_m = _extract_and_validate_alias(
            usage_ev, ("backend_model", "model"), "backend_model", "Usage evidence", required=True, allowed_values=allowed_u_models
        )
        u_m = clean_u_m

        clean_u_task = _extract_and_validate_alias(
            usage_ev, ("delivery_task_id", "task_id", "delivery_task"), "delivery_task_id", "Usage evidence", required=True
        )
        u_task = clean_u_task

        clean_u_disp = _extract_and_validate_alias(
            usage_ev, ("dispatch_id", "dispatch"), "dispatch_id", "Usage evidence", required=True
        )
        u_disp = clean_u_disp

        u_ts = _extract_and_validate_alias(
            usage_ev, ("timestamp", "ts"), "timestamp", "Usage evidence", required=True
        )
        u_after = usage_ev.get("recorded_after_dispatch")
    else:
        raise RoutingEvidenceError(f"Invalid usage_evidence type: {type(usage_ev).__name__}")

    # Mutual bindings for explicit usage router to route.provider, launch mappings, live-terminal provider, and phase
    if clean_u_router != clean_p:
        raise RoutingEvidenceError(
            f"Contradictory evidence: usage router {clean_u_router!r} does not match route provider {clean_p!r}"
        )
    if clean_u_router != req_p:
        raise RoutingEvidenceError(
            f"Contradictory evidence: usage router {clean_u_router!r} does not match launch_requested provider {req_p!r}"
        )
    if clean_u_router != eff_p:
        raise RoutingEvidenceError(
            f"Contradictory evidence: usage router {clean_u_router!r} does not match launch_effective provider {eff_p!r}"
        )
    if clean_u_router != live_p:
        raise RoutingEvidenceError(
            f"Contradictory evidence: usage router {clean_u_router!r} does not match live terminal provider {live_p!r}"
        )
    if clean_phase not in ("implement", "review") or clean_u_router != "9router":
        raise RoutingEvidenceError(
            f"Usage evidence router {clean_u_router!r} invalid for phase {clean_phase!r}; expected '9router'"
        )

    if u_after is not True:
        raise RoutingEvidenceError(
            "9Router usage evidence must record backend request after dispatch (recorded_after_dispatch=True); "
            "pre-dispatch or stale usage records are insufficient"
        )
    if not u_p:
        raise RoutingEvidenceError("9Router usage evidence missing backend_provider")
    if not u_m:
        raise RoutingEvidenceError("9Router usage evidence missing backend_model")

    clean_u_p = (u_p or "").strip()
    clean_u_m = (u_m or "").strip()

    if clean_phase == "implement":
        if clean_u_p != "google":
            raise RoutingEvidenceError(
                f"9Router usage backend_provider {u_p!r} invalid for phase 'implement'; expected 'google'"
            )
        if clean_u_m != "ag/gemini-3.8-flash-high":
            raise RoutingEvidenceError(
                f"9Router usage backend_model {u_m!r} does not match expected model {expected_model!r}; "
                f"exact canonical backend identity required, got {u_m!r}"
            )
    elif clean_phase == "review":
        if clean_u_p != "openai":
            raise RoutingEvidenceError(
                f"9Router usage backend_provider {u_p!r} invalid for phase 'review'; expected 'openai'"
            )
        if clean_u_m != "cx/gpt-5.6-sol":
            raise RoutingEvidenceError(
                f"9Router usage backend_model {u_m!r} does not match expected model {expected_model!r}; "
                f"exact canonical backend identity required, got {u_m!r}"
            )

    clean_u_disp = (u_disp or "").strip() if isinstance(u_disp, str) else ""
    if not clean_u_disp:
        raise RoutingEvidenceError(
            "9Router usage evidence missing required dispatch_id anchor; fails closed"
        )
    if clean_u_disp != clean_disp_id:
        raise RoutingEvidenceError(
            f"Usage evidence dispatch ID {u_disp!r} does not match dispatch {clean_disp_id!r}"
        )

    clean_u_task = (u_task or "").strip() if isinstance(u_task, str) else ""
    if not clean_u_task:
        raise RoutingEvidenceError(
            "9Router usage evidence missing required delivery_task_id anchor; fails closed"
        )
    if clean_u_task != clean_dtid:
        raise RoutingEvidenceError(
            f"Usage evidence task ID {u_task!r} does not match task {clean_dtid!r}"
        )

    # Timestamp machine-readable validation & freshness
    if not u_ts or not isinstance(u_ts, (str, int, float)) or (isinstance(u_ts, str) and not u_ts.strip()):
        raise RoutingEvidenceError(
            "9Router usage evidence missing machine-readable timestamp; cannot rely solely on recorded_after_dispatch"
        )
    try:
        if isinstance(u_ts, (int, float)):
            u_dt = datetime.fromtimestamp(u_ts, tz=timezone.utc)
        else:
            ts_str = u_ts.strip()
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            u_dt = datetime.fromisoformat(ts_str)
            if u_dt.tzinfo is None:
                u_dt = u_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError) as exc:
        raise RoutingEvidenceError(
            f"9Router usage evidence timestamp {u_ts!r} is not a valid ISO 8601 machine-readable format"
        ) from exc

    if dispatch_time is not None:
        dt_comp = dispatch_time
        if dt_comp.tzinfo is None:
            dt_comp = dt_comp.replace(tzinfo=timezone.utc)
        if u_dt < dt_comp:
            raise RoutingEvidenceError(
                f"9Router usage evidence timestamp {u_ts!r} ({u_dt.isoformat()}) is earlier than dispatch time "
                f"{dt_comp.isoformat()}; stale timestamp rejected"
            )

    # 9. Credential and mutable path safety
    all_strings = []
    for item in (launch_req, launch_eff, live_terminal, usage_ev, data.get("evidence_outputs", [])):
        if isinstance(item, Mapping):
            all_strings.extend(str(v) for v in item.values())
        elif hasattr(item, "__dict__"):
            all_strings.extend(str(v) for v in item.__dict__.values())
        elif isinstance(item, (list, tuple)):
            all_strings.extend(str(v) for v in item)

    for s in all_strings:
        for pat, desc in _SECRET_PATTERNS:
            if pat.search(s):
                raise RoutingEvidenceError(
                    f"Evidence reference contains forbidden potential secret ({desc}): {s!r}"
                )
        if _MUTABLE_DB_PATH_RE.search(s) or ((".db" in s.lower() or ".sqlite" in s.lower()) and (":\\" in s or s.startswith("/"))):
            raise RoutingEvidenceError(
                f"Evidence reference contains forbidden mutable local database path: {s!r}"
            )

    return []


@dataclass
class DispatchBinding:
    delivery_task_id: str
    orca_task_id: str
    dispatch_id: str
    candidate_commit: Optional[str] = None
    fencing_token: Optional[int] = None
    lease_id: Optional[str] = None
    lease_ids: List[str] = field(default_factory=list)
    authority_state: str = "granted"
    settled: bool = False
    slot_fencing_tokens: Dict[str, Dict[int, int]] = field(default_factory=dict)


class _FileLock:
    """Portable atomic file locking mechanism for cross-process registry safety."""

    _process_locks: Dict[Path, Tuple[int, int, int]] = {}
    _class_lock: threading.RLock = threading.RLock()

    def __init__(self, lock_path: Path, timeout: float = 5.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self.fd: Optional[int] = None

    def __enter__(self):
        canonical_path = self.lock_path.resolve()
        current_thread = threading.get_ident()

        with _FileLock._class_lock:
            if canonical_path in _FileLock._process_locks:
                owner_thread, count, fd = _FileLock._process_locks[canonical_path]
                if owner_thread == current_thread:
                    _FileLock._process_locks[canonical_path] = (owner_thread, count + 1, fd)
                    self.fd = fd
                    return self

        start = time.time()
        while True:
            try:
                self.lock_path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                with _FileLock._class_lock:
                    _FileLock._process_locks[canonical_path] = (current_thread, 1, fd)
                self.fd = fd
                return self
            except (FileExistsError, PermissionError):
                elapsed = time.time() - start
                if elapsed > self.timeout:
                    try:
                        mtime = self.lock_path.stat().st_mtime
                        if time.time() - mtime > self.timeout * 2:
                            self.lock_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                if elapsed > self.timeout * 3:
                    raise TimeoutError(f"Timed out waiting for registry file lock {self.lock_path} after {self.timeout}s")
                time.sleep(0.01)

    def __exit__(self, exc_type, exc_val, exc_tb):
        canonical_path = self.lock_path.resolve()
        current_thread = threading.get_ident()

        with _FileLock._class_lock:
            if canonical_path in _FileLock._process_locks:
                owner_thread, count, fd = _FileLock._process_locks[canonical_path]
                if owner_thread == current_thread:
                    if count > 1:
                        _FileLock._process_locks[canonical_path] = (owner_thread, count - 1, fd)
                        return
                    else:
                        del _FileLock._process_locks[canonical_path]
                        try:
                            os.close(fd)
                        except OSError:
                            pass
                        self.fd = None
                        try:
                            self.lock_path.unlink(missing_ok=True)
                        except OSError:
                            pass


class SharedOrcaExecutionRegistry:
    """Process-durable ledger/registry tracking Orca task IDs and dispatch IDs globally
    across all OrcaDeliveryAdapter instances with explicit storage path, atomic persistence,
    and process-safe locking semantics.
    """
    _default_instance: Optional[SharedOrcaExecutionRegistry] = None
    _default_storage_path: Optional[Path] = DEFAULT_PRODUCTION_REGISTRY_PATH

    def __init__(
        self,
        storage_path: Optional[Union[str, Path]] = None,
        allow_ephemeral: bool = False,
    ):
        if storage_path is not None:
            self.storage_path: Optional[Path] = Path(storage_path)
        elif self._default_storage_path is not None:
            self.storage_path: Optional[Path] = Path(self._default_storage_path)
        elif allow_ephemeral:
            self.storage_path = None
        else:
            raise ProtocolViolationError(
                "Default execution registry cannot be ephemeral in production without explicit safe storage path; fail-closed contract enforced"
            )

        self._lock = threading.RLock()
        self.seen_orca_task_ids: Set[str] = set()
        self.seen_dispatch_ids: Set[str] = set()
        self.settled_dispatches: Set[str] = set()
        self.orca_task_to_delivery_task: Dict[str, str] = {}
        self.dispatch_bindings: Dict[str, DispatchBinding] = {}

        if self.storage_path and self.storage_path.is_file():
            self._load_from_storage()

    @classmethod
    def set_default_storage_path(cls, path: Optional[Union[str, Path]]) -> None:
        cls._default_storage_path = Path(path) if path else None

    @classmethod
    def get_default(
        cls,
        storage_path: Optional[Union[str, Path]] = None,
        allow_ephemeral: bool = False,
    ) -> SharedOrcaExecutionRegistry:
        effective_path = Path(storage_path) if storage_path else cls._default_storage_path
        if cls._default_instance is None or (storage_path and cls._default_instance.storage_path != effective_path):
            cls._default_instance = cls(storage_path=effective_path, allow_ephemeral=allow_ephemeral)
        return cls._default_instance

    @classmethod
    def reset_default(
        cls,
        storage_path: Optional[Union[str, Path]] = None,
        allow_ephemeral: bool = False,
    ) -> None:
        effective_path = Path(storage_path) if storage_path else cls._default_storage_path
        if effective_path and effective_path.is_file():
            try:
                effective_path.unlink()
            except OSError:
                pass
            lock_p = effective_path.with_name(f"{effective_path.name}.lock")
            if lock_p.is_file():
                try:
                    lock_p.unlink()
                except OSError:
                    pass
        cls._default_instance = cls(storage_path=effective_path, allow_ephemeral=allow_ephemeral)

    def _get_lock_path(self) -> Optional[Path]:
        if self.storage_path:
            return self.storage_path.with_name(f"{self.storage_path.name}.lock")
        return None

    @contextmanager
    def _transaction(self, write: bool = True):
        """Cross-process and intra-process atomic transaction context manager with rollback on failure."""
        lock_path = self._get_lock_path()
        lock_ctx = _FileLock(lock_path) if lock_path else None
        with self._lock:
            if lock_ctx:
                with lock_ctx:
                    if self.storage_path and self.storage_path.is_file():
                        self._load_from_storage()
                    snapshot = (
                        set(self.seen_orca_task_ids),
                        set(self.seen_dispatch_ids),
                        set(self.settled_dispatches),
                        dict(self.orca_task_to_delivery_task),
                        dict(self.dispatch_bindings),
                    )
                    try:
                        yield
                        if write and self.storage_path:
                            self._persist_atomic()
                    except Exception:
                        (
                            self.seen_orca_task_ids,
                            self.seen_dispatch_ids,
                            self.settled_dispatches,
                            self.orca_task_to_delivery_task,
                            self.dispatch_bindings,
                        ) = snapshot
                        raise
            else:
                if self.storage_path and self.storage_path.is_file():
                    self._load_from_storage()
                snapshot = (
                    set(self.seen_orca_task_ids),
                    set(self.seen_dispatch_ids),
                    set(self.settled_dispatches),
                    dict(self.orca_task_to_delivery_task),
                    dict(self.dispatch_bindings),
                )
                try:
                    yield
                    if write and self.storage_path:
                        self._persist_atomic()
                except Exception:
                    (
                        self.seen_orca_task_ids,
                        self.seen_dispatch_ids,
                        self.settled_dispatches,
                        self.orca_task_to_delivery_task,
                        self.dispatch_bindings,
                    ) = snapshot
                    raise

    def clear(self) -> None:
        with self._transaction(write=False):
            self.seen_orca_task_ids.clear()
            self.seen_dispatch_ids.clear()
            self.settled_dispatches.clear()
            self.orca_task_to_delivery_task.clear()
            self.dispatch_bindings.clear()
            if self.storage_path and self.storage_path.is_file():
                try:
                    self.storage_path.unlink()
                except OSError:
                    pass

    def _load_from_storage(self) -> None:
        if not self.storage_path or not self.storage_path.is_file():
            return
        with self._lock:
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self.seen_orca_task_ids = set(data.get("seen_orca_task_ids", []))
                self.seen_dispatch_ids = set(data.get("seen_dispatch_ids", []))
                self.settled_dispatches = set(data.get("settled_dispatches", []))
                self.orca_task_to_delivery_task = dict(data.get("orca_task_to_delivery_task", {}))
                self.dispatch_bindings = {}
                for d_id, b_data in data.get("dispatch_bindings", {}).items():
                    raw_slots = b_data.get("slot_fencing_tokens", {})
                    restored_slots = {
                        lid: {int(k): int(v) for k, v in slots.items()}
                        for lid, slots in raw_slots.items()
                    }
                    self.dispatch_bindings[d_id] = DispatchBinding(
                        delivery_task_id=b_data.get("delivery_task_id", ""),
                        orca_task_id=b_data.get("orca_task_id", ""),
                        dispatch_id=b_data.get("dispatch_id", d_id),
                        candidate_commit=b_data.get("candidate_commit"),
                        fencing_token=b_data.get("fencing_token"),
                        lease_id=b_data.get("lease_id"),
                        lease_ids=b_data.get("lease_ids", []),
                        authority_state=b_data.get("authority_state", "granted"),
                        settled=b_data.get("settled", False),
                        slot_fencing_tokens=restored_slots,
                    )
            except Exception as exc:
                raise ProtocolViolationError(f"Failed to load execution registry from {self.storage_path}: {exc}")

    def _persist(self) -> None:
        if not self.storage_path:
            return
        lock_path = self._get_lock_path()
        lock_ctx = _FileLock(lock_path) if lock_path else None
        with self._lock:
            if lock_ctx:
                with lock_ctx:
                    self._persist_atomic()
            else:
                self._persist_atomic()

    def _persist_atomic(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.storage_path.with_name(
            f"{self.storage_path.name}.tmp.{os.getpid()}_{time.time_ns()}"
        )
        data = {
            "seen_orca_task_ids": sorted(self.seen_orca_task_ids),
            "seen_dispatch_ids": sorted(self.seen_dispatch_ids),
            "settled_dispatches": sorted(self.settled_dispatches),
            "orca_task_to_delivery_task": self.orca_task_to_delivery_task,
            "dispatch_bindings": {
                d_id: {
                    "delivery_task_id": b.delivery_task_id,
                    "orca_task_id": b.orca_task_id,
                    "dispatch_id": b.dispatch_id,
                    "candidate_commit": b.candidate_commit,
                    "fencing_token": b.fencing_token,
                    "lease_id": b.lease_id,
                    "lease_ids": b.lease_ids,
                    "authority_state": b.authority_state,
                    "settled": b.settled,
                    "slot_fencing_tokens": getattr(b, "slot_fencing_tokens", {}),
                }
                for d_id, b in self.dispatch_bindings.items()
            },
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.storage_path)

    def register_orca_task(self, orca_task_id: str, delivery_task_id: str) -> None:
        if not orca_task_id or not isinstance(orca_task_id, str) or not orca_task_id.strip():
            raise ProtocolViolationError("orca_task_id cannot be blank")
        clean_id = orca_task_id.strip()
        with self._transaction(write=True):
            if clean_id in self.seen_orca_task_ids:
                other = self.orca_task_to_delivery_task.get(clean_id)
                if other and other != delivery_task_id:
                    raise ProtocolViolationError(
                        f"Orca task ID {clean_id!r} is already assigned to delivery task {other!r}; global reuse across adapter instances is forbidden"
                    )
                raise ProtocolViolationError(
                    f"Orca task ID {clean_id!r} has already been registered or used; global reuse across adapter instances is forbidden"
                )
            self.seen_orca_task_ids.add(clean_id)
            self.orca_task_to_delivery_task[clean_id] = delivery_task_id

    def register_dispatch_binding(self, dispatch_id: str, binding: DispatchBinding) -> None:
        if not dispatch_id or not isinstance(dispatch_id, str) or not dispatch_id.strip():
            raise ProtocolViolationError("dispatch_id cannot be blank")
        clean_id = dispatch_id.strip()
        with self._transaction(write=True):
            if (
                clean_id in self.seen_dispatch_ids
                or clean_id in self.settled_dispatches
                or clean_id in self.dispatch_bindings
            ):
                raise ProtocolViolationError(
                    f"Duplicate dispatch binding overwrite: dispatch ID {clean_id!r} is already bound or settled; global reuse is forbidden"
                )
            self.seen_dispatch_ids.add(clean_id)
            self.dispatch_bindings[clean_id] = binding

    def register_dispatch_and_orca_task(
        self,
        dispatch_id: str,
        binding: DispatchBinding,
        orca_task_id: str,
        delivery_task_id: str,
    ) -> None:
        """Atomic cross-process compound registration of dispatch binding and Orca task association.
        Guarantees either both are registered and persisted atomically to disk, or neither is;
        rolls back all in-memory mutations on any duplicate or conflict failure so no orphan
        dispatch bindings are ever left on disk or in memory.
        """
        if not dispatch_id or not isinstance(dispatch_id, str) or not dispatch_id.strip():
            raise ProtocolViolationError("dispatch_id cannot be blank")
        if not orca_task_id or not isinstance(orca_task_id, str) or not orca_task_id.strip():
            raise ProtocolViolationError("orca_task_id cannot be blank")
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        clean_disp_id = dispatch_id.strip()
        clean_orca_id = orca_task_id.strip()
        clean_delivery_id = delivery_task_id.strip()

        with self._transaction(write=True):
            # Check orca_task_id uniqueness first
            if clean_orca_id in self.seen_orca_task_ids:
                other = self.orca_task_to_delivery_task.get(clean_orca_id)
                if other and other != clean_delivery_id:
                    raise ProtocolViolationError(
                        f"Orca task ID {clean_orca_id!r} is already assigned to delivery task {other!r}; global reuse across adapter instances is forbidden"
                    )
                raise ProtocolViolationError(
                    f"Orca task ID {clean_orca_id!r} has already been registered or used; global reuse across adapter instances is forbidden"
                )

            # Check dispatch_id uniqueness
            if (
                clean_disp_id in self.seen_dispatch_ids
                or clean_disp_id in self.settled_dispatches
                or clean_disp_id in self.dispatch_bindings
            ):
                raise ProtocolViolationError(
                    f"Duplicate dispatch binding overwrite: dispatch ID {clean_disp_id!r} is already bound or settled; global reuse is forbidden"
                )

            # Both checks passed inside the locked cross-process transaction; mutate both
            self.seen_orca_task_ids.add(clean_orca_id)
            self.orca_task_to_delivery_task[clean_orca_id] = clean_delivery_id
            self.seen_dispatch_ids.add(clean_disp_id)
            self.dispatch_bindings[clean_disp_id] = binding

    def is_orca_task_registered(self, orca_task_id: str) -> bool:
        if not orca_task_id or not isinstance(orca_task_id, str):
            return False
        clean_id = orca_task_id.strip()
        with self._transaction(write=False):
            return clean_id in self.seen_orca_task_ids

    def get_orca_task_delivery_id(self, orca_task_id: str) -> Optional[str]:
        if not orca_task_id or not isinstance(orca_task_id, str):
            return None
        clean_id = orca_task_id.strip()
        with self._transaction(write=False):
            return self.orca_task_to_delivery_task.get(clean_id)

    def get_dispatch_binding(self, dispatch_id: str) -> Optional[DispatchBinding]:
        if not dispatch_id or not isinstance(dispatch_id, str):
            return None
        clean_id = dispatch_id.strip()
        with self._transaction(write=False):
            return self.dispatch_bindings.get(clean_id)

    def is_dispatch_settled(self, dispatch_id: str) -> bool:
        if not dispatch_id or not isinstance(dispatch_id, str) or not dispatch_id.strip():
            return False
        clean_id = dispatch_id.strip()
        with self._transaction(write=False):
            return clean_id in self.settled_dispatches

    def settle_dispatch(self, dispatch_id: str) -> None:
        if not dispatch_id or not isinstance(dispatch_id, str) or not dispatch_id.strip():
            raise ProtocolViolationError("dispatch_id cannot be blank")
        clean_id = dispatch_id.strip()
        with self._transaction(write=True):
            if clean_id in self.settled_dispatches:
                raise DuplicateResultError(f"Duplicate worker_done for already settled dispatch {clean_id}")
            self.settled_dispatches.add(clean_id)
            if clean_id in self.dispatch_bindings:
                self.dispatch_bindings[clean_id].settled = True



class OrcaDeliveryAdapter:
    """Translates Orca CLI events into delivery ledger state transitions."""

    def __init__(
        self,
        lease_manager: LeaseManager,
        approved_candidate_commit: str,
        git_root: Optional[Path] = None,
        registry: Optional[SharedOrcaExecutionRegistry] = None,
        declared_task_locks: Optional[Dict[str, List[str]]] = None,
        approved_base_commit: str = DEFAULT_APPROVED_BASE_COMMIT,
        control_secret: Optional[str] = None,
    ):
        if approved_candidate_commit is None:
            raise ProtocolViolationError("approved_candidate_commit is mandatory; cannot be None")
        if not isinstance(approved_candidate_commit, str) or not approved_candidate_commit.strip():
            raise ProtocolViolationError("approved_candidate_commit cannot be blank")
        clean_commit = approved_candidate_commit.strip()
        if len(clean_commit) != 40 or not all(c in "0123456789abcdefABCDEF" for c in clean_commit):
            raise ProtocolViolationError(
                f"approved_candidate_commit must be a full 40-character hex SHA; got {clean_commit!r}"
            )
        if approved_base_commit is None:
            raise ProtocolViolationError("approved_base_commit is mandatory; cannot be None")
        if not isinstance(approved_base_commit, str) or not approved_base_commit.strip():
            raise ProtocolViolationError("approved_base_commit cannot be blank")
        clean_base = approved_base_commit.strip()
        if len(clean_base) != 40 or not all(c in "0123456789abcdefABCDEF" for c in clean_base):
            raise ProtocolViolationError(
                f"approved_base_commit must be a full 40-character hex SHA; got {clean_base!r}"
            )
        self.lease_mgr = lease_manager
        self.approved_candidate_commit = clean_commit
        self.approved_base_commit = clean_base
        self._internal_transition_secret: bytes = secrets.token_bytes(32)
        self._internal_exec_secret: bytes = secrets.token_bytes(32)
        self._consumed_internal_tokens: Set[str] = set()
        self.git_root = git_root
        self.registry = registry if registry is not None else SharedOrcaExecutionRegistry.get_default()
        self._task_states: Dict[str, str] = {}
        self._task_state_lock = threading.RLock()
        self.task_authorities: Dict[str, str] = {}
        self.active_dispatches: Dict[str, str] = {}  # delivery_task_id -> current dispatch_id
        self.dispatch_counters: Dict[str, int] = {}
        self.last_fencing_tokens: Dict[str, int] = {}
        self.declared_task_locks: Dict[str, List[str]] = dict(declared_task_locks or {})
        self.task_phases: Dict[str, str] = {}
        self._lifecycle_handler_context: Optional[Dict[str, Any]] = None
        self.active_review_dispatches: Dict[str, str] = {}
        self.review_dispatch_bindings: Dict[str, DispatchBinding] = {}
        self._verified_review_evidence: Dict[str, Any] = {}
        self._verified_integration_evidence: Dict[str, Any] = {}
        self._active_transition_tokens: Dict[str, _TransitionAuthToken] = {}
        self.evidence_authority = EvidenceAuthority(adapter=self, control_secret=control_secret)
        self._dispatch_reviewer_capabilities: Dict[str, ReviewerCapability] = {}



        self._executing_lifecycle_handler: Optional[str] = None
        self._executing_lifecycle_task_id: Optional[str] = None
        self._authoritatively_settled_dispatches: Set[str] = set()
        self._authoritatively_released_tasks: Set[str] = set()
        self._consumed_transition_tokens: Set[str] = set()

    @contextmanager
    def _internal_lifecycle_execution(
        self,
        handler: str,
        task_id: str,
        capability: Optional[Union[ControlCapability, ReviewerCapability]] = None,
        _internal_token: Optional[_InternalLifecycleToken] = None,
    ):
        """Internal execution boundary for authoritative lifecycle handlers.
        External callers without an independently authenticated Control or Reviewer capability cannot enter.
        Wildcard capabilities cannot enter lifecycle execution boundary.
        """
        clean_tid = task_id.strip() if isinstance(task_id, str) else ""

        if _internal_token is not None:
            if not isinstance(_internal_token, _InternalLifecycleToken):
                raise ProtocolViolationError(
                    f"Invalid internal lifecycle execution token: expected _InternalLifecycleToken, got {type(_internal_token).__name__}"
                )
            if _internal_token.adapter_id != id(self):
                raise ProtocolViolationError("Internal lifecycle token adapter_id mismatch")
            if _internal_token.handler != handler or _internal_token.task_id != clean_tid:
                raise ProtocolViolationError(
                    f"Internal lifecycle token mismatch: token=({_internal_token.task_id}, {_internal_token.handler}) vs execution=({clean_tid}, {handler})"
                )
            if _internal_token.token_id in self._consumed_internal_tokens:
                raise ProtocolViolationError(
                    f"Internal lifecycle token {_internal_token.token_id} has already been consumed"
                )
            expected_sig_data = f"ILT:{_internal_token.token_id}:{_internal_token.task_id}:{_internal_token.handler}:{id(self)}:{_internal_token.created_at}".encode("utf-8")
            expected_sig = hmac.new(self._internal_exec_secret, expected_sig_data, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(_internal_token.signature, expected_sig):
                raise ProtocolViolationError("Internal lifecycle token signature mismatch; forged token rejected")
            self._consumed_internal_tokens.add(_internal_token.token_id)
        elif capability is not None:
            self._verify_lifecycle_capability(capability, handler, clean_tid)
            with self.evidence_authority._lock:
                self.evidence_authority._consumed_capabilities.add(capability.capability_id)
        else:
            raise ProtocolViolationError(
                "Lifecycle context entry requires an independently authenticated Control or Reviewer capability; "
                "ordinary callers cannot enter lifecycle execution boundary"
            )

        prev_handler = self._executing_lifecycle_handler
        prev_task = self._executing_lifecycle_task_id
        self._executing_lifecycle_handler = handler
        self._executing_lifecycle_task_id = clean_tid
        try:
            yield
        finally:
            self._executing_lifecycle_handler = prev_handler
            self._executing_lifecycle_task_id = prev_task

    def _mint_internal_lifecycle_token(self, handler: str, clean_tid: str) -> _InternalLifecycleToken:
        tok_id = f"ilt_{uuid.uuid4().hex}"
        created_at = time.time()
        sig_data = f"ILT:{tok_id}:{clean_tid}:{handler}:{id(self)}:{created_at}".encode("utf-8")
        sig = hmac.new(self._internal_exec_secret, sig_data, hashlib.sha256).hexdigest()
        return _InternalLifecycleToken(
            token_id=tok_id,
            handler=handler,
            task_id=clean_tid,
            adapter_id=id(self),
            created_at=created_at,
            signature=sig,
        )

    def _verify_lifecycle_capability(
        self,
        capability: Any,
        handler: str,
        clean_tid: str,
    ) -> None:
        if not capability or not isinstance(capability, (ControlCapability, ReviewerCapability)):
            raise ProtocolViolationError(
                f"Invalid lifecycle execution capability: expected ControlCapability or ReviewerCapability, got {type(capability).__name__}"
            )
        if getattr(capability, "capability_id", "").startswith("adapter_internal_"):
            raise ProtocolViolationError(
                "Internal wildcard capability cannot be passed across callable surface"
            )
        if getattr(capability, "delivery_task_id", None) is None or getattr(capability, "delivery_task_id", "") == "*":
            raise ProtocolViolationError(
                "Wildcard capability cannot be used for lifecycle execution; explicit task-scoped capability required"
            )
        if capability.delivery_task_id != clean_tid:
            raise ProtocolViolationError(
                f"Capability delivery_task_id mismatch: expected {clean_tid!r}, got {capability.delivery_task_id!r}"
            )
        if isinstance(capability, ReviewerCapability):
            if handler != "handle_review_verdict":
                raise ProtocolViolationError(
                    f"ReviewerCapability cannot authorize handler {handler!r}; Reviewer is restricted to review verdict handling"
                )
            self.evidence_authority.verify_capability(capability, expected_task_id=clean_tid)
        elif isinstance(capability, ControlCapability):
            self.evidence_authority.verify_capability(
                capability, expected_role="Control", expected_task_id=clean_tid
            )

    def issue_review_evidence(
        self,
        delivery_task_id: str,
        review_dispatch_id: str,
        candidate_commit: str,
        verdict: str = "ACCEPT",
        reviewer_route: str = "cx/gpt-5.6-sol",
        reviewer_harness: str = "Claude Code",
        summary: str = "Independent review accepted on exact candidate HEAD",
        now: Optional[datetime] = None,
        capability: Optional[Union[ReviewerCapability, ControlCapability]] = None,
        reviewer_capability: Optional[ReviewerCapability] = None,
    ) -> ReviewEvidence:
        effective_cap = reviewer_capability if reviewer_capability is not None else capability
        if effective_cap is None:
            raise ProtocolViolationError(
                "Review evidence issuance requires an independently authenticated Reviewer or Control capability; "
                "unprivileged callers cannot obtain authoritative review evidence"
            )
        if getattr(effective_cap, "capability_id", "").startswith("adapter_internal_"):
            raise ProtocolViolationError(
                "Internal wildcard capability cannot be used to issue review evidence; independently authenticated capability required"
            )
        return self.evidence_authority.issue_review_evidence(
            delivery_task_id=delivery_task_id,
            review_dispatch_id=review_dispatch_id,
            candidate_commit=candidate_commit,
            verdict=verdict,
            reviewer_route=reviewer_route,
            reviewer_harness=reviewer_harness,
            summary=summary,
            now=now,
            capability=capability,
            reviewer_capability=reviewer_capability,
        )

    def issue_integration_evidence(
        self,
        delivery_task_id: str,
        candidate_commit: str,
        base_commit: str,
        gates_pass: bool = True,
        gate_results: Optional[Dict[str, bool]] = None,
        integrated_by: str = "Control",
        now: Optional[datetime] = None,
        capability: Optional[ControlCapability] = None,
        control_capability: Optional[ControlCapability] = None,
    ) -> IntegrationEvidence:
        effective_cap = control_capability if control_capability is not None else capability
        if effective_cap is None:
            raise ProtocolViolationError(
                "Integration evidence issuance requires an independently authenticated Control capability; "
                "unprivileged callers cannot obtain authoritative integration evidence"
            )
        if getattr(effective_cap, "capability_id", "").startswith("adapter_internal_"):
            raise ProtocolViolationError(
                "Internal wildcard capability cannot be used to issue integration evidence; independently authenticated Control capability required"
            )
        return self.evidence_authority.issue_integration_evidence(
            delivery_task_id=delivery_task_id,
            candidate_commit=candidate_commit,
            base_commit=base_commit,
            gates_pass=gates_pass,
            gate_results=gate_results,
            integrated_by=integrated_by,
            now=now,
            capability=capability,
            control_capability=control_capability,
        )

    def issue_control_capability(
        self, control_secret: str, delivery_task_id: Optional[str] = None
    ) -> ControlCapability:
        return self.evidence_authority.issue_control_capability(
            control_secret=control_secret,
            delivery_task_id=delivery_task_id,
        )

    def issue_reviewer_capability(
        self,
        delivery_task_id: str,
        review_dispatch_id: str,
        candidate_commit: str,
        reviewer_route: str = "cx/gpt-5.6-sol",
        reviewer_harness: str = "Claude Code",
        control_capability: Optional[ControlCapability] = None,
        control_secret: Optional[str] = None,
    ) -> ReviewerCapability:
        return self.evidence_authority.issue_reviewer_capability(
            delivery_task_id=delivery_task_id,
            review_dispatch_id=review_dispatch_id,
            candidate_commit=candidate_commit,
            reviewer_route=reviewer_route,
            reviewer_harness=reviewer_harness,
            control_capability=control_capability,
            control_secret=control_secret,
        )

    def get_reviewer_capability(
        self,
        review_dispatch_id: str,
        control_capability: Optional[ControlCapability] = None,
        control_secret: Optional[str] = None,
    ) -> ReviewerCapability:
        clean_did = review_dispatch_id.strip() if isinstance(review_dispatch_id, str) else ""
        if clean_did not in self._dispatch_reviewer_capabilities:
            raise ProtocolViolationError(f"No ReviewerCapability registered for review dispatch {clean_did!r}")
        cap = self._dispatch_reviewer_capabilities[clean_did]
        authenticated = False
        if control_secret and isinstance(control_secret, str):
            if hmac.compare_digest(control_secret.encode("utf-8"), self.evidence_authority._control_secret):
                authenticated = True
        if not authenticated and control_capability is not None:
            self.evidence_authority.verify_capability(control_capability, expected_role="Control", expected_task_id=cap.delivery_task_id)
            authenticated = True
        if not authenticated:
            raise ProtocolViolationError("Unauthorized: retrieving ReviewerCapability requires authenticated Control authority")
        return cap

    def _mint_transition_token(self, handler: str, task_id: str, new_state: str) -> _TransitionAuthToken:
        if not task_id or not isinstance(task_id, str) or not task_id.strip():
            raise ProtocolViolationError("task_id cannot be blank")
        clean_tid = task_id.strip()

        # Close capability mint surface to external callers
        if self._executing_lifecycle_handler != handler or self._executing_lifecycle_task_id != clean_tid:
            raise ProtocolViolationError(
                f"Unauthorized transition capability minting: external callers cannot mint lifecycle capabilities; "
                f"capability issuance is strictly internal to authoritative handlers (attempted handler={handler!r}, executing={self._executing_lifecycle_handler!r})"
            )

        allowed_handlers = {
            'create_dispatch',
            'create_review_dispatch',
            'acknowledge_dispatch',
            'start_running',
            'handle_worker_done',
            'handle_harness_failure',
            'handle_review_verdict',
            'handle_integration_gates',
            'resolve_blocker_and_replan',
        }
        if handler not in allowed_handlers:
            raise ProtocolViolationError(f'Handler {handler!r} is not an authorized transition handler')

        current_state = self.get_task_state(clean_tid)
        allowed_targets = LEGAL_TASK_STATE_TRANSITIONS.get(current_state, set())
        if new_state not in allowed_targets:
            raise ProtocolViolationError(
                f"Illegal transition from {current_state!r} to {new_state!r} for task {clean_tid}"
            )

        auth = self.get_task_authority(clean_tid)
        if auth != "granted":
            raise ProtocolViolationError(
                f"Task {clean_tid} authority is {auth!r}; lifecycle transition to {new_state!r} forbidden"
            )

        # Enforce prerequisite invariants for transition authorization
        if handler == "create_dispatch":
            if new_state != "dispatched":
                raise ProtocolViolationError(f"create_dispatch cannot transition to {new_state!r}")
        elif handler == "acknowledge_dispatch":
            if new_state != "acknowledged":
                raise ProtocolViolationError(f"acknowledge_dispatch cannot transition to {new_state!r}")
            if current_state != "dispatched":
                raise ProtocolViolationError(f"Cannot transition to 'acknowledged' from {current_state!r}")
        elif handler == "start_running":
            if new_state != "running":
                raise ProtocolViolationError(f"start_running cannot transition to {new_state!r}")
            if current_state != "acknowledged":
                raise ProtocolViolationError(f"Cannot transition to 'running' from {current_state!r}")
        elif handler == "handle_worker_done":
            if new_state == "review":
                if current_state != "running":
                    raise ProtocolViolationError(f"Cannot transition to 'review' from {current_state!r}")
                disp_id = self.active_dispatches.get(clean_tid)
                if not disp_id:
                    raise ProtocolViolationError(
                        f"Cannot transition task {clean_tid} to 'review': no active dispatch found"
                    )
                if not self.registry.is_dispatch_settled(disp_id):
                    raise ProtocolViolationError(
                        f"Cannot transition task {clean_tid} to 'review': dispatch {disp_id!r} is unsettled in execution registry"
                    )
                if disp_id not in self._authoritatively_settled_dispatches:
                    raise ProtocolViolationError(
                        f"Dispatch {disp_id!r} was settled out-of-band or externally without authoritative worker_done execution; cannot mint transition capability"
                    )
                if clean_tid not in self._authoritatively_released_tasks:
                    raise ProtocolViolationError(
                        f"Task {clean_tid!r} leases were released out-of-band or externally without authoritative worker_done execution; cannot mint transition capability"
                    )
                active_task_leases = [
                    l.lease_id for l in self.lease_mgr.active_leases.values()
                    if l.is_active and (l.delivery_task_id == clean_tid or l.dispatch_id == disp_id)
                ]
                if active_task_leases:
                    raise ProtocolViolationError(
                        f"Cannot transition task {clean_tid} to 'review': active leases still held: {active_task_leases}"
                    )
            elif new_state == "blocked":
                if current_state != "running":
                    raise ProtocolViolationError(f"Cannot transition to 'blocked' from {current_state!r}")
            else:
                raise ProtocolViolationError(f"handle_worker_done cannot transition to {new_state!r}")
        elif handler == "handle_harness_failure":
            if new_state != "blocked":
                raise ProtocolViolationError(f"handle_harness_failure cannot transition to {new_state!r}")
        elif handler == "handle_review_verdict":
            if current_state != "review":
                raise ProtocolViolationError(f"handle_review_verdict cannot transition from {current_state!r}")
            if new_state not in ("merge_queued", "remediation", "blocked"):
                raise ProtocolViolationError(f"handle_review_verdict cannot transition to {new_state!r}")
            if new_state == "merge_queued":
                if clean_tid not in self._verified_review_evidence:
                    raise ProtocolViolationError(
                        f"Cannot transition task {clean_tid} to 'merge_queued' without verified review evidence"
                    )
        elif handler == "handle_integration_gates":
            if current_state != "merge_queued":
                raise ProtocolViolationError(f"handle_integration_gates cannot transition from {current_state!r}")
            if new_state not in ("integrated", "blocked"):
                raise ProtocolViolationError(f"handle_integration_gates cannot transition to {new_state!r}")
            if new_state == "integrated":
                if clean_tid not in self._verified_integration_evidence:
                    raise ProtocolViolationError(
                        f"Cannot transition task {clean_tid} to 'integrated' without verified integration evidence"
                    )
        elif handler == "resolve_blocker_and_replan":
            if current_state != "blocked":
                raise ProtocolViolationError(f"resolve_blocker_and_replan cannot transition from {current_state!r}")
            if new_state not in ("ready", "planned"):
                raise ProtocolViolationError(f"resolve_blocker_and_replan cannot transition to {new_state!r}")

        tok_id = str(uuid.uuid4())
        created_at = time.time()
        sig_data = f"{tok_id}:{clean_tid}:{current_state}:{new_state}:{handler}:{id(self)}:{created_at}".encode("utf-8")
        sig = hmac.new(self._internal_transition_secret, sig_data, hashlib.sha256).hexdigest()
        tok = _TransitionAuthToken(
            token_id=tok_id,
            task_id=clean_tid,
            from_state=current_state,
            new_state=new_state,
            handler=handler,
            adapter_id=id(self),
            created_at=created_at,
            signature=sig,
        )
        self._active_transition_tokens[tok.token_id] = tok
        return tok

    @contextmanager
    def _authorized_transition_scope(
        self,
        task_id: str,
        new_state: str,
        handler: str,
        _token: Optional[_TransitionAuthToken] = None,
        **evidence
    ):
        clean_tid = task_id.strip() if isinstance(task_id, str) else ""

        # Close transition scope surface to external callers
        if self._executing_lifecycle_handler != handler or self._executing_lifecycle_task_id != clean_tid:
            raise ProtocolViolationError(
                f"Unauthorized transition scope: external callers cannot enter authorized transition scope; "
                f"scope is strictly internal to authoritative handlers (attempted handler={handler!r}, executing={self._executing_lifecycle_handler!r})"
            )

        if _token is None:
            raise ProtocolViolationError(
                "Unauthorized transition scope: unforgeable token required; external callers cannot forge transition contexts"
            )
        if not isinstance(_token, _TransitionAuthToken):
            raise ProtocolViolationError(
                f"Invalid or forged transition token: expected _TransitionAuthToken, got {type(_token).__name__}; tokens cannot be forged"
            )
        if _token.adapter_id != id(self) or _token.token_id not in self._active_transition_tokens:
            raise ProtocolViolationError(
                "Invalid, forged, or already consumed transition token; token is unauthorized"
            )
        if _token.token_id in self._consumed_transition_tokens:
            raise ProtocolViolationError(
                f"Transition token {_token.token_id} has already been consumed; token reuse strictly forbidden"
            )
        expected_sig_data = f"{_token.token_id}:{_token.task_id}:{_token.from_state}:{_token.to_state}:{_token.handler}:{id(self)}:{_token.created_at}".encode("utf-8")
        expected_sig = hmac.new(self._internal_transition_secret, expected_sig_data, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(_token.signature, expected_sig):
            raise ProtocolViolationError("Invalid or forged transition token signature; token is unauthorized")

        if _token.task_id != clean_tid or _token.to_state != new_state or _token.handler != handler:
            raise ProtocolViolationError(
                f"Transition token mismatch: token=({_token.task_id}, {_token.to_state}, {_token.handler}) vs scope=({clean_tid}, {new_state}, {handler})"
            )
        if _token.from_state != self.get_task_state(clean_tid):
            raise ProtocolViolationError(
                f"Transition token from_state mismatch: token from_state={_token.from_state!r}, current task state={self.get_task_state(clean_tid)!r}"
            )

        prev = self._lifecycle_handler_context
        self._lifecycle_handler_context = {
            "task_id": clean_tid,
            "new_state": new_state,
            "handler": handler,
            "token": _token,
            "evidence": evidence,
        }
        try:
            yield
        finally:
            self._lifecycle_handler_context = prev

    def register_task_phase(self, delivery_task_id: str, phase: str) -> None:
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        if phase not in ("implement", "review"):
            raise ProtocolViolationError(f"Invalid task phase {phase!r}; must be 'implement' or 'review'")
        self.task_phases[delivery_task_id.strip()] = phase

    @property
    def task_states(self) -> Dict[str, str]:
        """Read-only view of internal task states to prevent direct bypass mutation."""
        with self._task_state_lock:
            return dict(self._task_states)

    @property
    def seen_orca_task_ids(self) -> Set[str]:
        return self.registry.seen_orca_task_ids

    @property
    def seen_dispatch_ids(self) -> Set[str]:
        return self.registry.seen_dispatch_ids

    @property
    def settled_dispatches(self) -> Set[str]:
        return self.registry.settled_dispatches

    @property
    def dispatch_bindings(self) -> Dict[str, DispatchBinding]:
        return self.registry.dispatch_bindings

    @property
    def orca_task_to_delivery_task(self) -> Dict[str, str]:
        return self.registry.orca_task_to_delivery_task

    def register_task_locks(self, delivery_task_id: str, locks: List[str]) -> None:
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        self.declared_task_locks[delivery_task_id.strip()] = list(locks)

    def set_task_state(self, delivery_task_id: str, state: str) -> None:
        """Constrained state setter restricted strictly to pre-dispatch planning/readiness states.
        Execution lifecycle states (dispatched -> acknowledged -> running -> review -> merge_queued -> integrated)
        cannot be bypassed, terminal states (integrated, cancelled, stopped) cannot be reopened or mutated,
        and illegal rewinds (e.g. review/merge_queued to planned) are strictly rejected.
        All transitions are aligned with protocol transition rules and mutations are atomic.
        """
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        clean_tid = delivery_task_id.strip()
        clean_state = state.strip() if isinstance(state, str) else ""

        forbidden_direct = {
            "dispatched", "acknowledged", "running", "review", "merge_queued", "integrated", "remediation"
        }
        allowed_set_states = {"planned", "waiting_dependency", "ready", "blocked", "locked", "cancelled"}

        if clean_state in forbidden_direct:
            raise ProtocolViolationError(
                f"Cannot directly set task {clean_tid!r} to execution lifecycle state {clean_state!r} via set_task_state; "
                f"mandatory lifecycle (ready -> dispatched -> acknowledged -> running -> worker_done) cannot be bypassed"
            )
        if clean_state not in allowed_set_states:
            raise ProtocolViolationError(
                f"Invalid or forbidden task state {clean_state!r} for set_task_state; "
                f"only planning/readiness states {sorted(allowed_set_states)} are permitted"
            )

        with self._task_state_lock:
            current = self.get_task_state(clean_tid)
            # Terminal states must never be reopened or mutated
            if current in {"integrated", "cancelled", "stopped"}:
                raise ProtocolViolationError(
                    f"Cannot mutate or reopen task {clean_tid!r} in terminal state {current!r}"
                )

            # Active lifecycle / verification states cannot be overwritten or bypassed
            if current in {"dispatched", "acknowledged", "running", "review", "merge_queued", "remediation"}:
                raise ProtocolViolationError(
                    f"Cannot overwrite state of task {clean_tid!r} via set_task_state while in active lifecycle state {current!r}"
                )

            self._task_states[clean_tid] = clean_state

    def transition_task_state(self, delivery_task_id: str, new_state: str) -> None:
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        clean_tid = delivery_task_id.strip()
        with self._task_state_lock:
            current = self.get_task_state(clean_tid)
            allowed = LEGAL_TASK_STATE_TRANSITIONS.get(current, set())
            if new_state not in allowed:
                raise ProtocolViolationError(
                    f"Illegal task-state transition for {clean_tid}: {current!r} -> {new_state!r}; allowed: {sorted(allowed)}"
                )

            # 1. Authority validation: task authority must be explicitly 'granted'
            auth = self.get_task_authority(clean_tid)
            if auth != "granted":
                raise ProtocolViolationError(
                    f"Task {clean_tid} authority is {auth!r}; lifecycle transition to {new_state!r} forbidden (only 'granted' permitted)"
                )

            # 2. Handler authorization check: every public lifecycle transition must be authorized by the appropriate handler
            ctx = self._lifecycle_handler_context
            if not ctx or ctx.get("task_id") != clean_tid or ctx.get("new_state") != new_state:
                raise ProtocolViolationError(
                    f"Direct lifecycle transition for task {clean_tid} to {new_state!r} is forbidden; "
                    f"all transitions must be invoked through authorized handlers with verified dispatch, lease, and evidence"
                )

            tok = ctx.get("token")
            if not tok or not isinstance(tok, _TransitionAuthToken) or tok.token_id not in self._active_transition_tokens:
                raise ProtocolViolationError(
                    "Transition authorization token missing, invalid, or already consumed; transition forbidden"
                )
            if tok.task_id != clean_tid or tok.to_state != new_state or tok.handler != ctx.get("handler"):
                raise ProtocolViolationError(
                    f"Transition authorization token parameters mismatch context: token=({tok.task_id}, {tok.to_state}, {tok.handler})"
                )
            if tok.from_state != current:
                raise ProtocolViolationError(
                    f"Transition authorization token from_state mismatch: token from={tok.from_state!r}, current={current!r}"
                )
            expected_sig_data = f"{tok.token_id}:{tok.task_id}:{tok.from_state}:{tok.to_state}:{tok.handler}:{id(self)}:{tok.created_at}".encode("utf-8")
            expected_sig = hmac.new(self._internal_transition_secret, expected_sig_data, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(tok.signature, expected_sig):
                raise ProtocolViolationError("Transition authorization token signature invalid; transition forbidden")

            handler = ctx.get("handler")
            evidence = ctx.get("evidence", {})

            # 3. Transition-specific evidence verification:
            if new_state == "dispatched":
                if handler != "create_dispatch":
                    raise ProtocolViolationError(f"Transition to 'dispatched' must be authorized by create_dispatch; got {handler!r}")
                disp_id = evidence.get("dispatch_id") or self.active_dispatches.get(clean_tid)
                if not disp_id:
                    raise ProtocolViolationError(f"Cannot transition task {clean_tid} to 'dispatched' without verified active dispatch")
                binding = self.dispatch_bindings.get(disp_id)
                if not binding:
                    raise ProtocolViolationError(f"No dispatch binding found for dispatch {disp_id!r}")
                leases = getattr(binding, "lease_ids", None) or ([binding.lease_id] if binding.lease_id else [])
                if not leases:
                    raise ProtocolViolationError(f"Dispatch {disp_id} has no bound leases")
                for lid in leases:
                    if lid not in self.lease_mgr.active_leases:
                        raise ProtocolViolationError(f"Bound lease {lid} is missing or has expired from active leases")
                    al = self.lease_mgr.active_leases[lid]
                    if not al.is_active:
                        raise ProtocolViolationError(f"Bound lease {lid} is inactive")

            elif new_state == "acknowledged":
                if handler != "acknowledge_dispatch":
                    raise ProtocolViolationError(f"Transition to 'acknowledged' must be authorized by acknowledge_dispatch; got {handler!r}")
                disp_id = evidence.get("dispatch_id") or self.active_dispatches.get(clean_tid)
                if not disp_id:
                    raise ProtocolViolationError(f"Cannot transition task {clean_tid} to 'acknowledged' without verified active dispatch")
                binding = self.dispatch_bindings.get(disp_id)
                if not binding:
                    raise ProtocolViolationError(f"No dispatch binding found for dispatch {disp_id!r}")
                leases = getattr(binding, "lease_ids", None) or ([binding.lease_id] if binding.lease_id else [])
                for lid in leases:
                    if lid not in self.lease_mgr.active_leases or not self.lease_mgr.active_leases[lid].is_active:
                        raise ProtocolViolationError(f"Bound lease {lid} is inactive or missing for transition to 'acknowledged'")

            elif new_state == "running":
                if handler != "start_running":
                    raise ProtocolViolationError(f"Transition to 'running' must be authorized by start_running; got {handler!r}")
                disp_id = evidence.get("dispatch_id") or self.active_dispatches.get(clean_tid)
                if not disp_id:
                    raise ProtocolViolationError(f"Cannot transition task {clean_tid} to 'running' without verified active dispatch")
                binding = self.dispatch_bindings.get(disp_id)
                if not binding:
                    raise ProtocolViolationError(f"No dispatch binding found for dispatch {disp_id!r}")
                leases = getattr(binding, "lease_ids", None) or ([binding.lease_id] if binding.lease_id else [])
                for lid in leases:
                    if lid not in self.lease_mgr.active_leases or not self.lease_mgr.active_leases[lid].is_active:
                        raise ProtocolViolationError(f"Bound lease {lid} is inactive or missing for transition to 'running'")

            elif new_state == "review":
                if handler != "handle_worker_done" or evidence.get("outcome") != "succeeded":
                    raise ProtocolViolationError(f"Transition to 'review' must be authorized by handle_worker_done with outcome='succeeded'; got {handler!r}")
                disp_id = evidence.get("dispatch_id") or self.active_dispatches.get(clean_tid)
                if not disp_id:
                    raise ProtocolViolationError(f"Cannot transition task {clean_tid} to 'review' without verified dispatch")
                if not self.registry.is_dispatch_settled(disp_id):
                    raise ProtocolViolationError(f"Cannot transition task {clean_tid} to 'review': dispatch {disp_id!r} is unsettled")
                active_task_leases = [
                    l.lease_id for l in self.lease_mgr.active_leases.values()
                    if l.is_active and (l.delivery_task_id == clean_tid or l.dispatch_id == disp_id)
                ]
                if active_task_leases:
                    raise ProtocolViolationError(f"Cannot transition task {clean_tid} to 'review': active leases still held: {active_task_leases}")

            elif new_state == "merge_queued":
                if handler != "handle_review_verdict" or evidence.get("verdict") != "ACCEPT":
                    raise ProtocolViolationError(f"Transition to 'merge_queued' must be authorized by handle_review_verdict with verdict='ACCEPT'; got {handler!r}")

            elif new_state == "remediation":
                if handler != "handle_review_verdict" or evidence.get("verdict") != "CHANGES_REQUESTED":
                    raise ProtocolViolationError(f"Transition to 'remediation' must be authorized by handle_review_verdict with verdict='CHANGES_REQUESTED'; got {handler!r}")

            elif new_state == "integrated":
                if handler != "handle_integration_gates" or evidence.get("gates_pass") is not True:
                    raise ProtocolViolationError(f"Transition to 'integrated' must be authorized by handle_integration_gates with gates_pass=True; got {handler!r}")

            elif new_state == "blocked":
                if handler not in ("handle_worker_done", "handle_harness_failure", "handle_review_verdict", "handle_integration_gates"):
                    raise ProtocolViolationError(f"Transition to 'blocked' must be authorized by an authorized failure handler; got {handler!r}")

            elif new_state in ("ready", "planned"):
                if handler != "resolve_blocker_and_replan":
                    raise ProtocolViolationError(f"Transition to {new_state!r} must be authorized by resolve_blocker_and_replan; got {handler!r}")

            # Strictly single-use token consumption
            if tok.token_id in self._active_transition_tokens:
                del self._active_transition_tokens[tok.token_id]
            self._consumed_transition_tokens.add(tok.token_id)

            self._task_states[clean_tid] = new_state

    def get_task_state(self, delivery_task_id: str) -> str:
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            return "planned"
        with self._task_state_lock:
            return self._task_states.get(delivery_task_id.strip(), "planned")

    def set_task_authority(self, delivery_task_id: str, authority: str) -> None:
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        clean_tid = delivery_task_id.strip()
        self.task_authorities[clean_tid] = authority
        self.lease_mgr.set_task_authority(clean_tid, authority)

    def get_task_authority(self, delivery_task_id: str) -> str:
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            return "unregistered"
        return self.task_authorities.get(delivery_task_id.strip(), "unregistered")

    def acknowledge_dispatch(self, delivery_task_id: str, dispatch_id: str) -> None:
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        if not dispatch_id or not isinstance(dispatch_id, str) or not dispatch_id.strip():
            raise ProtocolViolationError("dispatch_id cannot be blank")
        clean_tid = delivery_task_id.strip()
        clean_disp = dispatch_id.strip()
        active = self.active_dispatches.get(clean_tid)
        if active != clean_disp:
            raise ProtocolViolationError(
                f"Dispatch {clean_disp} is not the active dispatch for {clean_tid} (active is {active!r})"
            )
        current = self.get_task_state(clean_tid)
        if current != "dispatched":
            raise ProtocolViolationError(
                f"Cannot acknowledge dispatch for {clean_tid} in state {current!r}; must be 'dispatched'"
            )
        ilt = self._mint_internal_lifecycle_token("acknowledge_dispatch", clean_tid)
        with self._internal_lifecycle_execution("acknowledge_dispatch", clean_tid, _internal_token=ilt):
            token = self._mint_transition_token("acknowledge_dispatch", clean_tid, "acknowledged")
            with self._authorized_transition_scope(clean_tid, "acknowledged", handler="acknowledge_dispatch", _token=token, dispatch_id=clean_disp):
                self.transition_task_state(clean_tid, "acknowledged")

    def start_running(self, delivery_task_id: str, dispatch_id: str) -> None:
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        if not dispatch_id or not isinstance(dispatch_id, str) or not dispatch_id.strip():
            raise ProtocolViolationError("dispatch_id cannot be blank")
        clean_tid = delivery_task_id.strip()
        clean_disp = dispatch_id.strip()
        active = self.active_dispatches.get(clean_tid)
        if active != clean_disp:
            raise ProtocolViolationError(
                f"Dispatch {clean_disp} is not the active dispatch for {clean_tid} (active is {active!r})"
            )
        current = self.get_task_state(clean_tid)
        if current != "acknowledged":
            raise ProtocolViolationError(
                f"Cannot start running task {clean_tid} in state {current!r}; "
                f"mandatory lifecycle requires state 'acknowledged' (cannot skip acknowledged stage)"
            )
        ilt = self._mint_internal_lifecycle_token("start_running", clean_tid)
        with self._internal_lifecycle_execution("start_running", clean_tid, _internal_token=ilt):
            token = self._mint_transition_token("start_running", clean_tid, "running")
            with self._authorized_transition_scope(clean_tid, "running", handler="start_running", _token=token, dispatch_id=clean_disp):
                self.transition_task_state(clean_tid, "running")

    def create_dispatch(
        self,
        delivery_task_id: str,
        orca_task_id: Optional[str] = None,
        candidate_commit: Optional[str] = None,
        fencing_token: Optional[int] = None,
        lease_id: Optional[str] = None,
        lease_ids: Optional[Union[List[str], Set[str]]] = None,
        authority_state: Optional[str] = None,
        intended_dispatch_id: Optional[str] = None,
        now: Optional[datetime] = None,
        dispatch_origin: Optional[str] = None,
        execution_envelope: Optional[Union[ExecutionEnvelope, Dict[str, Any]]] = None,
        phase: Optional[str] = None,
    ) -> str:
        """Create a fresh dispatch attempt for a delivery task and bind identities.
        Requires exact nonblank and globally unique Orca task ID, candidate commit existing in git
        and matching approved candidate and actual current HEAD, positive fencing token, active unexpired leases
        proving the complete declared task lock set, mandatory intended dispatch without lease rewrite,
        and allowed state transition ('ready' -> 'dispatched').
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

        # Verify candidate equals actual current HEAD and approved candidate commit
        head_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True)
        if head_res.returncode != 0 or not head_res.stdout.strip():
            raise ProtocolViolationError("Cannot determine actual current git HEAD")
        actual_head = head_res.stdout.strip()

        if candidate_commit.lower() != actual_head.lower():
            raise ProtocolViolationError(
                f"Candidate commit {candidate_commit} does not match approved candidate / HEAD {actual_head}"
            )
        if self.approved_candidate_commit.lower() != actual_head.lower():
            raise ProtocolViolationError(
                f"Approved candidate commit {self.approved_candidate_commit} does not match actual current HEAD {actual_head}"
            )
        if candidate_commit.lower() != self.approved_candidate_commit.lower():
            raise ProtocolViolationError(
                f"Candidate commit {candidate_commit} does not match approved candidate {self.approved_candidate_commit}"
            )

        # Fencing token: strict positive integer
        if fencing_token is None or type(fencing_token) is not int or isinstance(fencing_token, bool) or fencing_token <= 0:
            raise ProtocolViolationError(
                f"fencing_token is required and must be a strict positive integer; got {fencing_token!r}"
            )

        # Intended dispatch binding is mandatory unconditionally: no lease rewrite!
        if intended_dispatch_id is None or not isinstance(intended_dispatch_id, str) or not intended_dispatch_id.strip():
            raise ProtocolViolationError("intended_dispatch_id is mandatory and cannot be blank")
        intended_dispatch_id = intended_dispatch_id.strip()

        # Mandatory fail-closed dispatch origin and execution envelope validation:
        # Every dispatch MUST go through 'dely dispatch' and provide a valid execution envelope.
        # Validation occurs BEFORE ANY side effects on task state, leases, or registry,
        # and specifically BEFORE any call that can purge, deactivate, rewrite, or persist lease/registry/task state.
        clean_orig = (dispatch_origin or "").strip() if isinstance(dispatch_origin, str) else ""
        if clean_orig != "dely dispatch":
            clean_lower = clean_orig.lower()
            if "worker-start" in clean_lower or clean_lower in ("worker-start", "orca worker-start", "direct worker-start", "orca"):
                raise RoutingEvidenceError(
                    f"Direct Orca worker-start dispatch origin {dispatch_origin!r} is strictly forbidden; "
                    f"every delivery dispatch MUST go through 'dely dispatch'"
                )
            raise RoutingEvidenceError(
                f"Invalid dispatch origin {dispatch_origin!r}; every delivery dispatch MUST go through 'dely dispatch'"
            )

        if execution_envelope is None:
            raise RoutingEvidenceError(
                "Missing execution_envelope; every delivery dispatch MUST provide an execution envelope"
            )

        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)

        expected_task_phase = phase or getattr(self, "task_phases", {}).get(delivery_task_id)

        validate_execution_envelope(
            envelope=execution_envelope,
            expected_phase=expected_task_phase,
            expected_delivery_task_id=delivery_task_id,
            expected_dispatch_id=intended_dispatch_id.strip(),
            expected_orca_task_id=orca_task_id,
            dispatch_time=now,
        )

        # Collect all provided lease IDs
        all_leases: List[str] = []
        if lease_ids:
            all_leases.extend([lid.strip() for lid in lease_ids if isinstance(lid, str) and lid.strip()])
        if lease_id and isinstance(lease_id, str) and lease_id.strip():
            clean_lid = lease_id.strip()
            if clean_lid not in all_leases:
                all_leases.append(clean_lid)
        if not all_leases:
            raise ProtocolViolationError("lease_id is required and cannot be blank")

        # Validate each lease
        for lid in all_leases:
            if lid not in self.lease_mgr.active_leases:
                raise ProtocolViolationError(f"Bound lease {lid!r} not found in active leases")
            active_lease = self.lease_mgr.active_leases[lid]
            if not active_lease.is_active:
                raise ProtocolViolationError(f"Bound lease {lid!r} is not active")

            # Reject undeclared lock on bound lease
            if active_lease.lock_id not in self.lease_mgr.lock_defs:
                raise ProtocolViolationError(
                    f"Bound lease {lid} references undeclared lock {active_lease.lock_id!r}"
                )

            # Lease ownership: belongs to same delivery task
            if active_lease.delivery_task_id != delivery_task_id:
                raise ProtocolViolationError(
                    f"Lease {lid} belongs to task {active_lease.delivery_task_id!r}, cannot be bound to {delivery_task_id!r}"
                )

            # Lease must match intended dispatch ID: NO LEASE REWRITE!
            if active_lease.dispatch_id != intended_dispatch_id:
                raise ProtocolViolationError(
                    f"Lease {lid} intended dispatch {active_lease.dispatch_id!r} does not match requested {intended_dispatch_id!r}"
                )

            # Lease expiry check
            if active_lease.expires_at:
                try:
                    exp_dt = datetime.fromisoformat(active_lease.expires_at)
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                    if now_dt >= exp_dt:
                        active_lease.is_active = False
                        del self.lease_mgr.active_leases[lid]
                        raise ProtocolViolationError(f"Bound lease {lid} has expired at {active_lease.expires_at}")
                except (ValueError, TypeError):
                    active_lease.is_active = False
                    del self.lease_mgr.active_leases[lid]
                    raise ProtocolViolationError(f"Bound lease {lid} has invalid expires_at format")

            # Lease cannot be already bound to an active or settled dispatch
            for prev_disp_id, prev_b in self.dispatch_bindings.items():
                if prev_b.lease_id == lid or (hasattr(prev_b, "lease_ids") and lid in prev_b.lease_ids):
                    raise ProtocolViolationError(
                        f"Lease {lid} is already bound to dispatch {prev_disp_id}; lease reuse across dispatches is forbidden"
                    )

        # Mandatory declared_task_locks registration and exact complete lock set before dispatch
        if delivery_task_id not in self.declared_task_locks:
            raise ProtocolViolationError(
                f"Task {delivery_task_id} has no registered declared_task_locks; "
                f"declared_task_locks registration is mandatory before dispatch"
            )
        declared_locks = set(self.declared_task_locks[delivery_task_id])
        if not declared_locks:
            raise ProtocolViolationError(
                f"Task {delivery_task_id} declared empty declared_task_locks; "
                f"tasks must declare at least one resource lock before dispatch"
            )
        leased_locks = {self.lease_mgr.active_leases[lid].lock_id for lid in all_leases}
        if leased_locks != declared_locks:
            missing = declared_locks - leased_locks
            extraneous = leased_locks - declared_locks
            err_parts = []
            if missing:
                err_parts.append(f"missing locks: {sorted(missing)}")
            if extraneous:
                err_parts.append(f"extraneous locks: {sorted(extraneous)}")
            raise ProtocolViolationError(
                f"Task {delivery_task_id} declared locks {sorted(declared_locks)} but dispatch proved {sorted(leased_locks)}; "
                f"{'; '.join(err_parts)}. Dispatch must prove the complete declared task lock set."
            )


        dispatch_id = intended_dispatch_id

        # Global non-reuse of dispatch IDs across active and settled attempts; reject overwrite
        if (
            dispatch_id in self.seen_dispatch_ids
            or dispatch_id in self.settled_dispatches
            or dispatch_id in self.dispatch_bindings
        ):
            raise ProtocolViolationError(
                f"Duplicate dispatch binding overwrite: dispatch ID {dispatch_id!r} is already bound or settled; global reuse is forbidden"
            )

        # Fencing token check on primary lease
        primary_lease = self.lease_mgr.active_leases[all_leases[0]]
        if fencing_token != primary_lease.fencing_token:
            raise ProtocolViolationError(
                f"Fencing token mismatch for lease {all_leases[0]}: lease has {primary_lease.fencing_token}, dispatch requested {fencing_token}"
            )
        current_token = self.lease_mgr.fencing_counters.get(primary_lease.resource_key)
        if current_token is not None and fencing_token != current_token:
            raise ProtocolViolationError(
                f"Fencing token {fencing_token} is not current for resource {primary_lease.resource_key} (current is {current_token})"
            )

        # Multi-slot capacity validation: every slot in every bound lease must match its generation token
        for lid in all_leases:
            lease_obj = self.lease_mgr.active_leases[lid]
            if lease_obj.allocated_slots:
                prefix = lease_obj.resource_key.rsplit(":slot_", 1)[0] if ":slot_" in lease_obj.resource_key else lease_obj.lock_id
                for s in lease_obj.allocated_slots:
                    s_key = f"{prefix}:slot_{s}"
                    exp_s = self.lease_mgr.fencing_counters.get(s_key)
                    rec_s = lease_obj.slot_fencing_tokens.get(s)
                    if exp_s is None or rec_s is None or rec_s != exp_s:
                        raise ProtocolViolationError(
                            f"Stale slot token for slot {s} in capacity lock {lease_obj.lock_id}: "
                            f"lease recorded {rec_s}, current counter is {exp_s} (capacity slot reallocation detected)"
                        )

        slot_fencing_map = {}
        for lid in all_leases:
            l = self.lease_mgr.active_leases[lid]
            if l.allocated_slots:
                slot_fencing_map[lid] = dict(l.slot_fencing_tokens)

        binding = DispatchBinding(
            delivery_task_id=delivery_task_id,
            orca_task_id=orca_task_id,
            dispatch_id=dispatch_id,
            candidate_commit=candidate_commit,
            fencing_token=fencing_token,
            lease_id=all_leases[0],
            lease_ids=all_leases,
            authority_state=registered_auth,
            settled=False,
            slot_fencing_tokens=slot_fencing_map,
        )
        self.registry.register_dispatch_and_orca_task(
            dispatch_id=dispatch_id,
            binding=binding,
            orca_task_id=orca_task_id,
            delivery_task_id=delivery_task_id,
        )
        with self._task_state_lock:
            self.active_dispatches[delivery_task_id] = dispatch_id
            ilt = self._mint_internal_lifecycle_token("create_dispatch", delivery_task_id)
            with self._internal_lifecycle_execution("create_dispatch", delivery_task_id, _internal_token=ilt):
                token = self._mint_transition_token("create_dispatch", delivery_task_id, "dispatched")
                with self._authorized_transition_scope(
                    delivery_task_id, "dispatched", handler="create_dispatch", _token=token,
                    dispatch_id=dispatch_id, lease_ids=all_leases, fencing_token=fencing_token
                ):
                    self.transition_task_state(delivery_task_id, "dispatched")
            self.last_fencing_tokens[delivery_task_id] = fencing_token
        return dispatch_id

    def create_review_dispatch(
        self,
        delivery_task_id: str,
        orca_task_id: Optional[str] = None,
        candidate_commit: Optional[str] = None,
        intended_dispatch_id: Optional[str] = None,
        now: Optional[datetime] = None,
        dispatch_origin: Optional[str] = None,
        execution_envelope: Optional[Union[ExecutionEnvelope, Dict[str, Any]]] = None,
    ) -> str:
        """Create an independent review dispatch for a delivery task in 'review' state.
        Reviewer is strictly read-only and does not hold mutation leases.
        Review route MUST be cx/gpt-5.6-sol on Claude Code harness through 9router.
        """
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        delivery_task_id = delivery_task_id.strip()

        # Authority check
        if delivery_task_id not in self.task_authorities:
            raise ProtocolViolationError(
                f"Task {delivery_task_id} has no registered authority; authority must be explicitly registered and granted"
            )
        registered_auth = self.task_authorities[delivery_task_id]
        if registered_auth != "granted":
            raise ProtocolViolationError(
                f"Cannot dispatch review for task {delivery_task_id} with authority {registered_auth!r}; only 'granted' authority permitted"
            )

        # State check: task MUST be in 'review' state
        current_state = self.get_task_state(delivery_task_id)
        if current_state != "review":
            raise ProtocolViolationError(
                f"Cannot dispatch review for task {delivery_task_id} from state {current_state!r}; task must be in 'review' state"
            )

        # Orca task identity
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

        # Candidate commit validation
        if not candidate_commit or not isinstance(candidate_commit, str) or not candidate_commit.strip():
            raise ProtocolViolationError("candidate_commit cannot be blank")
        candidate_commit = candidate_commit.strip()
        if candidate_commit.upper() == "HEAD" or not SHA_HEX_40_RE.match(candidate_commit):
            raise ProtocolViolationError(
                f"candidate_commit {candidate_commit!r} is invalid; must be an immutable full 40-character commit SHA"
            )

        repo_root = self.git_root or (ROOT if "ROOT" in globals() else Path.cwd())
        cmd = ["git", "cat-file", "-e", f"{candidate_commit}^{{commit}}"]
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True)
        if res.returncode != 0:
            raise ProtocolViolationError(f"Candidate commit {candidate_commit!r} does not exist in git")

        head_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True)
        if head_res.returncode != 0 or not head_res.stdout.strip():
            raise ProtocolViolationError("Cannot determine actual current git HEAD")
        actual_head = head_res.stdout.strip()

        if candidate_commit.lower() != actual_head.lower():
            raise ProtocolViolationError(
                f"Candidate commit {candidate_commit} does not match approved candidate / HEAD {actual_head}"
            )
        if self.approved_candidate_commit.lower() != actual_head.lower():
            raise ProtocolViolationError(
                f"Approved candidate commit {self.approved_candidate_commit} does not match actual current HEAD {actual_head}"
            )
        if candidate_commit.lower() != self.approved_candidate_commit.lower():
            raise ProtocolViolationError(
                f"Candidate commit {candidate_commit} does not match approved candidate {self.approved_candidate_commit}"
            )

        # Intended dispatch ID
        if intended_dispatch_id is None or not isinstance(intended_dispatch_id, str) or not intended_dispatch_id.strip():
            raise ProtocolViolationError("intended_dispatch_id is mandatory and cannot be blank")
        intended_dispatch_id = intended_dispatch_id.strip()

        # Origin
        clean_orig = (dispatch_origin or "").strip() if isinstance(dispatch_origin, str) else ""
        if clean_orig != "dely dispatch":
            raise RoutingEvidenceError(
                f"Invalid dispatch origin {dispatch_origin!r}; every delivery dispatch MUST go through 'dely dispatch'"
            )

        # Execution envelope validation
        if execution_envelope is None:
            raise RoutingEvidenceError(
                "Missing execution_envelope; every delivery dispatch MUST provide an execution envelope"
            )

        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)

        validate_execution_envelope(
            envelope=execution_envelope,
            expected_phase="review",
            expected_delivery_task_id=delivery_task_id,
            expected_dispatch_id=intended_dispatch_id,
            expected_orca_task_id=orca_task_id,
            dispatch_time=now_dt,
        )

        dispatch_id = intended_dispatch_id
        if (
            dispatch_id in self.seen_dispatch_ids
            or dispatch_id in self.settled_dispatches
            or dispatch_id in self.dispatch_bindings
            or dispatch_id in self.review_dispatch_bindings
        ):
            raise ProtocolViolationError(
                f"Duplicate dispatch binding overwrite: dispatch ID {dispatch_id!r} is already bound or settled; global reuse is forbidden"
            )

        binding = DispatchBinding(
            delivery_task_id=delivery_task_id,
            orca_task_id=orca_task_id,
            dispatch_id=dispatch_id,
            candidate_commit=candidate_commit,
            fencing_token=None,
            lease_id=None,
            lease_ids=[],
            authority_state=registered_auth,
            settled=False,
        )

        self.registry.register_dispatch_and_orca_task(
            dispatch_id=dispatch_id,
            binding=binding,
            orca_task_id=orca_task_id,
            delivery_task_id=delivery_task_id,
        )
        self.active_review_dispatches[delivery_task_id] = dispatch_id
        self.review_dispatch_bindings[dispatch_id] = binding

        # Mint ReviewerCapability bound to this dispatch
        rev_cap = self.evidence_authority._mint_reviewer_capability_internal(
            delivery_task_id=delivery_task_id,
            review_dispatch_id=dispatch_id,
            candidate_commit=candidate_commit,
        )
        self._dispatch_reviewer_capabilities[dispatch_id] = rev_cap
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

        if self.registry.is_dispatch_settled(dispatch_id):
            raise DuplicateResultError(f"Duplicate worker_done for already settled dispatch {dispatch_id}")

        # Mandatory lifecycle path: task must be in 'running' state
        current_state = self.get_task_state(delivery_task_id)
        if current_state != "running":
            raise ProtocolViolationError(
                f"Cannot complete worker_done for task {delivery_task_id} in state {current_state!r}; "
                f"mandatory lifecycle requires state 'running' (cannot skip acknowledged/running stages; "
                f"previously must be 'dispatched', 'acknowledged', or 'running')"
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

        # Verify all bound leases are still active, unexpired, and belong to same task/dispatch
        binding_leases = getattr(binding, "lease_ids", None) or ([binding.lease_id] if binding.lease_id else [])
        for lid in binding_leases:
            if lid not in self.lease_mgr.active_leases:
                raise ProtocolViolationError(
                    f"Bound lease {lid} has expired or been purged from active leases"
                )
            bound_lease = self.lease_mgr.active_leases[lid]
            if not bound_lease.is_active:
                raise ProtocolViolationError(f"Bound lease {lid} is inactive")
            if bound_lease.delivery_task_id != delivery_task_id:
                raise ProtocolViolationError(
                    f"Bound lease {lid} belongs to task {bound_lease.delivery_task_id!r}, not {delivery_task_id!r}"
                )
            if bound_lease.dispatch_id != dispatch_id:
                raise ProtocolViolationError(
                    f"Bound lease {lid} is bound to dispatch {bound_lease.dispatch_id!r}, not {dispatch_id!r}"
                )
            if bound_lease.expires_at:
                try:
                    exp_dt = datetime.fromisoformat(bound_lease.expires_at)
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                    if now_dt >= exp_dt:
                        bound_lease.is_active = False
                        del self.lease_mgr.active_leases[lid]
                        raise ProtocolViolationError(f"Bound lease {lid} expired at {bound_lease.expires_at}")
                except (ValueError, TypeError):
                    bound_lease.is_active = False
                    del self.lease_mgr.active_leases[lid]
                    raise ProtocolViolationError(f"Bound lease {lid} has invalid expires_at format")

        for lid in binding_leases:
            if lid in self.lease_mgr.active_leases:
                bound_lease = self.lease_mgr.active_leases[lid]
                # Validate every capacity lease slot against that slot's own generation token
                if bound_lease.allocated_slots:
                    prefix = bound_lease.resource_key.rsplit(":slot_", 1)[0] if ":slot_" in bound_lease.resource_key else bound_lease.lock_id
                    recorded_map = getattr(binding, "slot_fencing_tokens", {}).get(lid) or bound_lease.slot_fencing_tokens
                    for s in bound_lease.allocated_slots:
                        s_key = f"{prefix}:slot_{s}"
                        exp_s = self.lease_mgr.fencing_counters.get(s_key)
                        rec_s = recorded_map.get(s)
                        if exp_s is None or rec_s is None or rec_s != exp_s:
                            raise StaleResultError(
                                f"Stale slot fencing token for slot {s} in capacity lock {bound_lease.lock_id}: "
                                f"dispatch recorded {rec_s}, current counter is {exp_s} (capacity slot reallocation detected)"
                            )
                self.lease_mgr.validate_fencing_token(
                    bound_lease.resource_key,
                    fencing_token if lid == binding.lease_id else bound_lease.fencing_token,
                    now=now_dt,
                    active_lease_id=lid,
                )

        # Settle the dispatch attempt in durable registry
        self.registry.settle_dispatch(dispatch_id)
        self._authoritatively_settled_dispatches.add(dispatch_id)

        if outcome == "succeeded":
            # Item 10: Successful worker_done releases all mutation leases BEFORE exposing review state
            to_remove = [
                lid for lid, l in list(self.lease_mgr.active_leases.items())
                if l.dispatch_id == dispatch_id or l.delivery_task_id == delivery_task_id or lid in binding_leases
            ]
            for lid in to_remove:
                self.lease_mgr.release_lease(lid)
            self._authoritatively_released_tasks.add(delivery_task_id)
            ilt = self._mint_internal_lifecycle_token("handle_worker_done", delivery_task_id)
            with self._internal_lifecycle_execution("handle_worker_done", delivery_task_id, _internal_token=ilt):
                token = self._mint_transition_token("handle_worker_done", delivery_task_id, "review")
                with self._authorized_transition_scope(
                    delivery_task_id, "review", handler="handle_worker_done", _token=token,
                    dispatch_id=dispatch_id, outcome="succeeded", candidate_commit=candidate_commit
                ):
                    self.transition_task_state(delivery_task_id, "review")
            return "review"
        else:
            # Failure / blocker -> task becomes blocked; releases live leases
            to_remove = [
                lid for lid, l in list(self.lease_mgr.active_leases.items())
                if l.dispatch_id == dispatch_id or l.delivery_task_id == delivery_task_id or lid in binding_leases
            ]
            for lid in to_remove:
                self.lease_mgr.release_lease(lid)
            self._authoritatively_released_tasks.add(delivery_task_id)
            ilt = self._mint_internal_lifecycle_token("handle_worker_done", delivery_task_id)
            with self._internal_lifecycle_execution("handle_worker_done", delivery_task_id, _internal_token=ilt):
                token = self._mint_transition_token("handle_worker_done", delivery_task_id, "blocked")
                with self._authorized_transition_scope(
                    delivery_task_id, "blocked", handler="handle_worker_done", _token=token,
                    dispatch_id=dispatch_id, outcome="failed"
                ):
                    self.transition_task_state(delivery_task_id, "blocked")
            return "blocked"

    def handle_harness_failure(
        self,
        delivery_task_id: str,
        dispatch_id: str,
        reason: str = "Harness compatibility failure",
    ) -> str:
        """Handle harness compatibility or execution failure fail-closed:
        identity-first fail-closed validation with no side effects until all
        dispatch/task/binding/active-state checks succeed.
        Stops/blocks task, safely releases ONLY leases exactly bound to the verified dispatch,
        settles dispatch in durable registry, and halts execution without candidate mutation
        or harness switching.
        Requires external recovery or human intervention to resolve.
        """
        clean_tid = delivery_task_id.strip() if isinstance(delivery_task_id, str) else ""
        clean_did = dispatch_id.strip() if isinstance(dispatch_id, str) else ""
        if not clean_tid or not clean_did:
            raise ProtocolViolationError("delivery_task_id and dispatch_id cannot be blank")

        # 1. Identity check: dispatch must exist in durable registry
        binding = self.registry.get_dispatch_binding(clean_did)
        if binding is None:
            raise ProtocolViolationError(f"Unknown dispatch ID {clean_did!r}")

        # 2. Task binding check: dispatch must belong to the specified delivery task
        if binding.delivery_task_id != clean_tid:
            raise ProtocolViolationError(
                f"Dispatch {clean_did!r} is bound to delivery task {binding.delivery_task_id!r}, not {clean_tid!r}"
            )

        # 3. Settlement check: reject already settled / duplicate dispatch
        if self.registry.is_dispatch_settled(clean_did) or getattr(binding, "settled", False):
            raise DuplicateResultError(
                f"Duplicate harness failure for already settled dispatch {clean_did!r}"
            )

        # 4. Active dispatch check: must be current active dispatch for this delivery task
        active_disp = self.active_dispatches.get(clean_tid)
        if active_disp != clean_did:
            raise StaleResultError(
                f"Stale dispatch failure: current active dispatch for {clean_tid!r} is {active_disp!r}, received {clean_did!r}"
            )

        # 5. Task state check: task must be in an active execution lifecycle state
        current_state = self.get_task_state(clean_tid)
        if current_state not in ("dispatched", "acknowledged", "running"):
            raise ProtocolViolationError(
                f"Cannot handle harness failure for task {clean_tid} in state {current_state!r}; "
                f"task must be in an active execution state ('dispatched', 'acknowledged', 'running')"
            )
        allowed_transitions = LEGAL_TASK_STATE_TRANSITIONS.get(current_state, set())
        if "blocked" not in allowed_transitions:
            raise ProtocolViolationError(
                f"Illegal task-state transition for {clean_tid}: {current_state!r} -> 'blocked'"
            )

        # All identity, binding, settled, and active-state validations passed.
        # 6. Settle dispatch in durable registry FIRST (transactional rollback on persistence failure)
        self.registry.settle_dispatch(clean_did)

        # 7. Release ONLY leases exactly bound to the verified dispatch
        binding_leases = getattr(binding, "lease_ids", None) or ([binding.lease_id] if binding.lease_id else [])
        if self.lease_mgr is not None:
            to_remove = [
                lid for lid, l in list(self.lease_mgr.active_leases.items())
                if l.dispatch_id == clean_did and (lid in binding_leases if binding_leases else True)
            ]
            for lid in to_remove:
                self.lease_mgr.release_lease(lid)

        # 8. Transition task state to blocked
        ilt = self._mint_internal_lifecycle_token("handle_harness_failure", clean_tid)
        with self._internal_lifecycle_execution("handle_harness_failure", clean_tid, _internal_token=ilt):
            token = self._mint_transition_token("handle_harness_failure", clean_tid, "blocked")
            with self._authorized_transition_scope(
                clean_tid, "blocked", handler="handle_harness_failure", _token=token,
                dispatch_id=clean_did
            ):
                self.transition_task_state(clean_tid, "blocked")
        return "blocked"

    def handle_review_verdict(
        self,
        delivery_task_id: str,
        verdict: str,
        review_dispatch_id: Optional[str] = None,
        review_evidence: Optional[Union[ReviewEvidence, Dict[str, Any]]] = None,
        now: Optional[datetime] = None,
    ) -> str:
        """Handle independent review disposition ('ACCEPT', 'CHANGES_REQUESTED', 'BLOCKED').
        Unknown review verdicts are strictly rejected.
        Requires valid review dispatch and verified review evidence.
        Caller-supplied strings alone are never authority.
        """
        allowed_verdicts = {"ACCEPT", "CHANGES_REQUESTED", "BLOCKED"}
        if not isinstance(verdict, str) or verdict not in allowed_verdicts:
            raise ProtocolViolationError(
                f"Unknown review verdict {verdict!r}; allowed verdicts are 'ACCEPT', 'CHANGES_REQUESTED', 'BLOCKED'"
            )

        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        clean_tid = delivery_task_id.strip()

        auth = self.get_task_authority(clean_tid)
        if auth != "granted":
            raise ProtocolViolationError(
                f"Task {clean_tid} has authority {auth!r}; review transition blocked (only 'granted' permitted)"
            )
        current_state = self.get_task_state(clean_tid)
        if current_state != "review":
            raise ProtocolViolationError(f"Cannot review task {clean_tid} in state {current_state!r}; must be 'review'")

        # Blocker 1: Review dispatch and verified evidence are mandatory
        if not review_dispatch_id or not isinstance(review_dispatch_id, str) or not review_dispatch_id.strip():
            raise ProtocolViolationError(
                "handle_review_verdict requires a valid review dispatch; caller-supplied string alone is not authority"
            )
        clean_did = review_dispatch_id.strip()

        if review_evidence is None:
            raise ProtocolViolationError(
                "handle_review_verdict requires verified review evidence; caller-supplied string alone is not authority"
            )

        binding = self.review_dispatch_bindings.get(clean_did) or self.registry.get_dispatch_binding(clean_did)
        if binding is None:
            raise ProtocolViolationError(f"Unknown review dispatch ID {clean_did!r}")
        if binding.delivery_task_id != clean_tid:
            raise ProtocolViolationError(
                f"Review dispatch {clean_did!r} is bound to delivery task {binding.delivery_task_id!r}, not {clean_tid!r}"
            )
        if clean_did in self.registry.settled_dispatches:
            raise ProtocolViolationError(f"Review dispatch {clean_did!r} has already been settled")

        # Validate review evidence
        if not isinstance(review_evidence, ReviewEvidence):
            raise ProtocolViolationError(
                f"Review evidence must be an instance of ReviewEvidence with verifiable provenance; plain caller dictionary is rejected (type mismatch: got {type(review_evidence).__name__})"
            )

        for fld in ("review_dispatch_id", "delivery_task_id", "candidate_commit", "verdict", "reviewer_route", "reviewer_harness"):
            val = getattr(review_evidence, fld, None)
            if not isinstance(val, str) or not val.strip():
                raise ProtocolViolationError(f"Review evidence field {fld!r} must be a non-blank string")
            if val != val.strip():
                raise ProtocolViolationError(f"Review evidence field {fld!r} {val!r} has invalid whitespace padding")

        ev_disp_id = review_evidence.review_dispatch_id
        ev_task_id = review_evidence.delivery_task_id
        ev_commit = review_evidence.candidate_commit
        ev_verdict = review_evidence.verdict
        ev_route = review_evidence.reviewer_route
        ev_harness = review_evidence.reviewer_harness

        if not ev_disp_id or ev_disp_id.strip() != clean_did:
            raise ProtocolViolationError(
                f"Review evidence dispatch ID {ev_disp_id!r} does not match review dispatch {clean_did!r}"
            )
        if not ev_task_id or ev_task_id.strip() != clean_tid:
            raise ProtocolViolationError(
                f"Review evidence delivery task ID {ev_task_id!r} does not match task {clean_tid!r}"
            )
        if not ev_verdict or ev_verdict.strip() != verdict:
            raise ProtocolViolationError(
                f"Review evidence verdict {ev_verdict!r} does not match disposition verdict {verdict!r}"
            )
        if not ev_commit or ev_commit.strip().lower() != self.approved_candidate_commit.lower():
            raise ProtocolViolationError(
                f"Review evidence candidate commit {ev_commit!r} does not match approved candidate {self.approved_candidate_commit}"
            )

        repo_root = self.git_root or (ROOT if "ROOT" in globals() else Path.cwd())
        head_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True)
        if head_res.returncode == 0 and head_res.stdout.strip():
            actual_head = head_res.stdout.strip()
            if ev_commit.strip().lower() != actual_head.lower():
                raise ProtocolViolationError(
                    f"Review evidence candidate commit {ev_commit!r} does not match current HEAD {actual_head}"
                )

        if (ev_route or "").strip() != "cx/gpt-5.6-sol":
            raise ProtocolViolationError(
                f"Review evidence reviewer route {ev_route!r} does not match required reviewer route 'cx/gpt-5.6-sol'"
            )
        if (ev_harness or "").strip() != "Claude Code":
            raise ProtocolViolationError(
                f"Review evidence reviewer harness {ev_harness!r} does not match required reviewer harness 'Claude Code'"
            )

        # Verify evidence authority BEFORE settling or mutating state (invalid evidence has zero side effects)
        self.evidence_authority.verify_and_consume_review_evidence(
            review_evidence,
            expected_task_id=clean_tid,
            expected_dispatch_id=clean_did,
            expected_candidate=self.approved_candidate_commit,
            expected_verdict=verdict,
            now=now,
        )

        # Settle review dispatch
        self.registry.settle_dispatch(clean_did)
        if clean_tid in self.active_review_dispatches:
            del self.active_review_dispatches[clean_tid]

        if verdict == "ACCEPT":
            self._verified_review_evidence[clean_tid] = review_evidence
            ilt = self._mint_internal_lifecycle_token("handle_review_verdict", clean_tid)
            with self._internal_lifecycle_execution("handle_review_verdict", clean_tid, _internal_token=ilt):
                token = self._mint_transition_token("handle_review_verdict", clean_tid, "merge_queued")
                with self._authorized_transition_scope(
                    clean_tid, "merge_queued", handler="handle_review_verdict", _token=token,
                    verdict="ACCEPT", review_dispatch_id=clean_did
                ):
                    self.transition_task_state(clean_tid, "merge_queued")
            return "merge_queued"
        elif verdict == "CHANGES_REQUESTED":
            ilt = self._mint_internal_lifecycle_token("handle_review_verdict", clean_tid)
            with self._internal_lifecycle_execution("handle_review_verdict", clean_tid, _internal_token=ilt):
                token = self._mint_transition_token("handle_review_verdict", clean_tid, "remediation")
                with self._authorized_transition_scope(
                    clean_tid, "remediation", handler="handle_review_verdict", _token=token,
                    verdict="CHANGES_REQUESTED", review_dispatch_id=clean_did
                ):
                    self.transition_task_state(clean_tid, "remediation")
            return "remediation"
        elif verdict == "BLOCKED":
            ilt = self._mint_internal_lifecycle_token("handle_review_verdict", clean_tid)
            with self._internal_lifecycle_execution("handle_review_verdict", clean_tid, _internal_token=ilt):
                token = self._mint_transition_token("handle_review_verdict", clean_tid, "blocked")
                with self._authorized_transition_scope(
                    clean_tid, "blocked", handler="handle_review_verdict", _token=token,
                    verdict="BLOCKED", review_dispatch_id=clean_did
                ):
                    self.transition_task_state(clean_tid, "blocked")
            return "blocked"

    def handle_integration_gates(
        self,
        delivery_task_id: str,
        gates_pass: bool,
        integration_evidence: Optional[Union[IntegrationEvidence, Dict[str, Any]]] = None,
        now: Optional[datetime] = None,
    ) -> str:
        """Handle integration gates on exact candidate HEAD.
        gates_pass must be strict bool; truthy/falsy coercion is strictly rejected.
        Requires verified integration evidence and verified prior independent review ACCEPT.
        Caller-supplied booleans alone are never authority.
        """
        if type(gates_pass) is not bool:
            raise ProtocolViolationError(
                f"gates_pass must be strict bool (True or False, no truthy coercion); got {type(gates_pass).__name__}: {gates_pass!r}"
            )
        if not delivery_task_id or not isinstance(delivery_task_id, str) or not delivery_task_id.strip():
            raise ProtocolViolationError("delivery_task_id cannot be blank")
        clean_tid = delivery_task_id.strip()

        auth = self.get_task_authority(clean_tid)
        if auth != "granted":
            raise ProtocolViolationError(
                f"Task {clean_tid} has authority {auth!r}; integration transition blocked (only 'granted' permitted)"
            )
        current_state = self.get_task_state(clean_tid)
        if current_state != "merge_queued":
            raise ProtocolViolationError(f"Cannot integrate task {clean_tid} in state {current_state!r}; must be 'merge_queued'")

        if integration_evidence is None:
            raise ProtocolViolationError(
                "handle_integration_gates requires verified integration evidence; caller-supplied boolean alone is not authority"
            )

        # Extract and validate integration evidence
        if not isinstance(integration_evidence, IntegrationEvidence):
            raise ProtocolViolationError(
                f"Integration evidence must be an instance of IntegrationEvidence with verifiable provenance; plain caller dictionary is rejected (type mismatch: got {type(integration_evidence).__name__})"
            )

        for fld in ("delivery_task_id", "candidate_commit", "base_commit"):
            val = getattr(integration_evidence, fld, None)
            if not isinstance(val, str) or not val.strip():
                raise ProtocolViolationError(f"Integration evidence field {fld!r} must be a non-blank string")
            if val != val.strip():
                raise ProtocolViolationError(f"Integration evidence field {fld!r} {val!r} has invalid whitespace padding")

        ev_task_id = integration_evidence.delivery_task_id
        ev_commit = integration_evidence.candidate_commit
        ev_base = integration_evidence.base_commit
        ev_gates_pass = integration_evidence.gates_pass
        gate_results = integration_evidence.gate_results

        if not ev_task_id or ev_task_id.strip() != clean_tid:
            raise ProtocolViolationError(
                f"Integration evidence delivery task ID {ev_task_id!r} does not match task {clean_tid!r}"
            )
        if type(ev_gates_pass) is not bool or ev_gates_pass != gates_pass:
            raise ProtocolViolationError(
                f"Integration evidence gates_pass ({ev_gates_pass!r}) does not match argument gates_pass ({gates_pass!r})"
            )
        if not ev_commit or ev_commit.strip().lower() != self.approved_candidate_commit.lower():
            raise ProtocolViolationError(
                f"Integration evidence candidate commit {ev_commit!r} does not match approved candidate {self.approved_candidate_commit}"
            )

        repo_root = self.git_root or (ROOT if "ROOT" in globals() else Path.cwd())
        head_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True)
        if head_res.returncode == 0 and head_res.stdout.strip():
            actual_head = head_res.stdout.strip()
            if ev_commit.strip().lower() != actual_head.lower():
                raise ProtocolViolationError(
                    f"Integration evidence candidate commit {ev_commit!r} does not match current HEAD {actual_head}"
                )

        if not ev_base or ev_base.strip().lower() != self.approved_base_commit.lower():
            raise ProtocolViolationError(
                f"Integration evidence base commit {ev_base!r} does not match approved base {self.approved_base_commit}"
            )

        if not isinstance(gate_results, dict) or len(gate_results) == 0:
            raise ProtocolViolationError(
                "Integration evidence gate_results must be a non-empty dictionary of integration gate results (gate_count == 0); fails closed"
            )

        if gates_pass:
            failing_gates = [k for k, v in gate_results.items() if not v]
            if failing_gates:
                raise ProtocolViolationError(
                    f"Contradictory integration evidence: gates_pass=True but individual gate(s) failing: {failing_gates}"
                )
            missing_mandatory = [g for g in MANDATORY_INTEGRATION_GATES if g not in gate_results or gate_results[g] is not True]
            if missing_mandatory:
                raise ProtocolViolationError(
                    f"Mandatory integration gate(s) missing or failing in integration evidence: {missing_mandatory}"
                )
            if clean_tid not in self._verified_review_evidence:
                raise ProtocolViolationError(
                    f"Task {clean_tid} cannot reach integration without prior verified independent review ACCEPT evidence; binding mismatch"
                )

            # Verify integration evidence authority BEFORE mutating state (invalid evidence has zero side effects)
            self.evidence_authority.verify_and_consume_integration_evidence(
                integration_evidence,
                expected_task_id=clean_tid,
                expected_candidate=self.approved_candidate_commit,
                expected_base=self.approved_base_commit,
                expected_gates_pass=gates_pass,
                now=now,
            )
            self._verified_integration_evidence[clean_tid] = integration_evidence
            ilt = self._mint_internal_lifecycle_token("handle_integration_gates", clean_tid)
            with self._internal_lifecycle_execution("handle_integration_gates", clean_tid, _internal_token=ilt):
                token = self._mint_transition_token("handle_integration_gates", clean_tid, "integrated")
                with self._authorized_transition_scope(
                    clean_tid, "integrated", handler="handle_integration_gates", _token=token, gates_pass=True
                ):
                    self.transition_task_state(clean_tid, "integrated")
            self.lease_mgr.mark_task_integrated(clean_tid)
            return "integrated"
        else:
            ilt = self._mint_internal_lifecycle_token("handle_integration_gates", clean_tid)
            with self._internal_lifecycle_execution("handle_integration_gates", clean_tid, _internal_token=ilt):
                token = self._mint_transition_token("handle_integration_gates", clean_tid, "blocked")
                with self._authorized_transition_scope(
                    clean_tid, "blocked", handler="handle_integration_gates", _token=token, gates_pass=False
                ):
                    self.transition_task_state(clean_tid, "blocked")
            to_remove = [
                lid for lid, l in list(self.lease_mgr.active_leases.items())
                if l.delivery_task_id == clean_tid
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
            ilt = self._mint_internal_lifecycle_token("resolve_blocker_and_replan", delivery_task_id)
            with self._internal_lifecycle_execution("resolve_blocker_and_replan", delivery_task_id, _internal_token=ilt):
                token = self._mint_transition_token("resolve_blocker_and_replan", delivery_task_id, "ready")
                with self._authorized_transition_scope(
                    delivery_task_id, "ready", handler="resolve_blocker_and_replan", _token=token
                ):
                    self.transition_task_state(delivery_task_id, "ready")
        elif state == "needs_replan":
            ilt = self._mint_internal_lifecycle_token("resolve_blocker_and_replan", delivery_task_id)
            with self._internal_lifecycle_execution("resolve_blocker_and_replan", delivery_task_id, _internal_token=ilt):
                token = self._mint_transition_token("resolve_blocker_and_replan", delivery_task_id, "planned")
                with self._authorized_transition_scope(
                    delivery_task_id, "planned", handler="resolve_blocker_and_replan", _token=token
                ):
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
    state: str   # "SUCCESS", "FAILURE", "STOP_BLOCKED"
    tool_name: str
    requested_tool: str
    execution_observed: bool
    execution_returncode: int
    fallback_required: bool = False
    fallback_target: str = "none"
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

        # Explicitly reject native-provider fallback states
        if self.state in ("STOP_FALLBACK", "FALLBACK") or "fallback" in str(self.state).lower():
            raise HarnessCompatibilityError(
                f"state {self.state!r} is forbidden: native-provider fallback state is strictly rejected fail-closed; "
                f"repository routing policy in AGENTS.md forbids Antigravity native fallback; task must STOP/BLOCKED without fallback"
            )

        if self.state not in ("SUCCESS", "FAILURE", "STOP_BLOCKED", "BLOCKED", "VERIFIED"):
            raise HarnessCompatibilityError(
                f"state must be 'SUCCESS', 'FAILURE', 'STOP_BLOCKED', or 'VERIFIED'; got {self.state!r}"
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

        clean_ft = (self.fallback_target or "").strip().lower()

        # Reject contradictory field combinations fail-closed
        if self.success:
            if self.status != "PASS":
                raise HarnessCompatibilityError(
                    f"Contradictory fields: success=True but status={self.status!r}; expected 'PASS'"
                )
            if self.state not in ("SUCCESS", "VERIFIED"):
                raise HarnessCompatibilityError(
                    f"Contradictory fields: success=True but state={self.state!r}; expected 'SUCCESS' or 'VERIFIED'"
                )
            if self.fallback_required:
                raise HarnessCompatibilityError(
                    "Contradictory fields: success=True but fallback_required=True; native-provider fallback is forbidden"
                )
            if self.execution_returncode != 0:
                raise HarnessCompatibilityError(
                    f"Contradictory fields: success=True but execution_returncode={self.execution_returncode}; expected 0"
                )
            if not self.execution_observed:
                raise HarnessCompatibilityError(
                    "Contradictory fields: success=True but execution_observed=False"
                )
            if clean_ft not in ("none", ""):
                raise HarnessCompatibilityError(
                    f"Contradictory fields: success=True but fallback_target={self.fallback_target!r}; expected 'none'"
                )
        else:
            if self.status != "STOP":
                raise HarnessCompatibilityError(
                    f"Contradictory fields: success=False but status={self.status!r}; expected 'STOP'"
                )
            if self.state in ("SUCCESS", "VERIFIED"):
                raise HarnessCompatibilityError(
                    f"Contradictory fields: success=False but state={self.state!r}; cannot be success state"
                )
            if self.fallback_required:
                raise HarnessCompatibilityError(
                    "Contradictory fields: fallback_required=True is forbidden; native-provider fallback is rejected fail-closed; "
                    "repository routing policy in AGENTS.md forbids Antigravity native fallback; task must STOP/BLOCKED without fallback"
                )
            if clean_ft in ("antigravity_native", "antigravity", "native_fallback", "native") or "antigravity" in clean_ft:
                raise HarnessCompatibilityError(
                    f"Contradictory fields: fallback_target={self.fallback_target!r} specifies forbidden native-provider fallback; "
                    "native-provider fallback is rejected fail-closed; task must STOP/BLOCKED without fallback"
                )
            if clean_ft not in ("none", ""):
                raise HarnessCompatibilityError(
                    f"Contradictory fields: fallback_target={self.fallback_target!r} is forbidden; fail-closed STOP/BLOCKED required without provider fallback"
                )


class HarnessExecutionStateMachine:
    """Observable state machine for harness tool execution and fail-closed STOP / BLOCKED transitions.
    States: IDLE -> RUNNING -> SUCCESS | FAILURE | STOP_BLOCKED.
    """

    LEGAL_STATES = {"IDLE", "RUNNING", "SUCCESS", "FAILURE", "STOP_BLOCKED"}
    LEGAL_TRANSITIONS = {
        "IDLE": {"RUNNING"},
        "RUNNING": {"SUCCESS", "FAILURE", "STOP_BLOCKED"},
        "FAILURE": {"STOP_BLOCKED", "IDLE"},
        "STOP_BLOCKED": {"IDLE"},
        "SUCCESS": {"IDLE"},
    }

    def __init__(self):
        self._current_state = "IDLE"
        self.transitions: List[Tuple[str, str, str]] = []

    @property
    def current_state(self) -> str:
        return self._current_state

    @current_state.setter
    def current_state(self, val: str) -> None:
        raise HarnessCompatibilityError(
            f"Illegal direct state assignment to {val!r}: direct harness state assignment is forbidden; "
            f"transitions must occur only through legal methods (transition())"
        )

    def reset(self) -> None:
        """Reset state machine to IDLE through legal transition method."""
        if self._current_state in ("SUCCESS", "FAILURE", "STOP_BLOCKED"):
            self.transition("IDLE", "Reset to IDLE")
        else:
            self._current_state = "IDLE"
            self.transitions.clear()

    def transition(self, to_state: str, reason: str) -> None:
        if to_state in ("STOP_FALLBACK", "FALLBACK") or "fallback" in str(to_state).lower():
            raise HarnessCompatibilityError(
                f"Illegal target state {to_state!r}: native-provider fallback state is strictly rejected fail-closed; "
                f"repository routing policy in AGENTS.md forbids Antigravity native fallback; "
                f"harness failures must stop/block as 'STOP_BLOCKED' without switching provider/harness"
            )
        if to_state not in self.LEGAL_STATES:
            raise HarnessCompatibilityError(
                f"Illegal target state {to_state!r}; legal states: {sorted(self.LEGAL_STATES)}"
            )
        allowed = self.LEGAL_TRANSITIONS.get(self._current_state, set())
        if to_state not in allowed:
            raise HarnessCompatibilityError(
                f"Illegal harness state transition from {self._current_state!r} to {to_state!r}"
            )
        self.transitions.append((self._current_state, to_state, reason))
        self._current_state = to_state

    def evaluate(
        self,
        tool_name: str,
        requested_tool: str,
        execution_observed: bool = True,
        execution_returncode: int = 0,
        execution_time_ms: float = 0.0,
    ) -> HarnessExecutionResult:
        if self._current_state != "IDLE":
            self.reset()
        self.transition("RUNNING", "Started harness tool evaluation")

        if not isinstance(tool_name, str) or not tool_name.strip():
            self.transition("STOP_BLOCKED", "Effective tool identity blank")
            raise HarnessCompatibilityError("Effective tool identity cannot be blank")
        if not isinstance(requested_tool, str) or not requested_tool.strip():
            self.transition("STOP_BLOCKED", "Requested tool identity blank")
            raise HarnessCompatibilityError("Requested tool identity cannot be blank")

        if type(execution_observed) is not bool:
            self.transition("STOP_BLOCKED", "execution_observed not strict bool")
            raise HarnessCompatibilityError(
                f"execution_observed must be strict bool; got {type(execution_observed).__name__}: {execution_observed!r}"
            )
        if type(execution_returncode) is not int or isinstance(execution_returncode, bool):
            self.transition("STOP_BLOCKED", "execution_returncode not strict int")
            raise HarnessCompatibilityError(
                f"execution_returncode must be strict int; got {type(execution_returncode).__name__}: {execution_returncode!r}"
            )

        effective = tool_name.strip()
        requested = requested_tool.strip()

        if "." in requested and "." not in effective:
            msg = (
                f"Harness namespaced tool collapse detected: requested {requested!r} collapsed to unnamespaced {effective!r}. "
                "Route success does not imply executable harness. STOP condition triggered: fail-closed STOP/BLOCKED required without native provider fallback."
            )
            self.transition("STOP_BLOCKED", msg)
            raise HarnessCompatibilityError(msg)

        if effective != requested:
            msg = (
                f"Harness tool identity mismatch: requested {requested!r} != effective {effective!r}. "
                "STOP condition triggered: fail-closed STOP/BLOCKED required without native provider fallback."
            )
            self.transition("STOP_BLOCKED", msg)
            raise HarnessCompatibilityError(msg)

        if not execution_observed:
            msg = (
                f"Harness tool execution smoke gate failed: execution_observed=False, returncode={execution_returncode}. "
                "No successful tool execution observed. Observed successful tool execution required before routing work. "
                "STOP condition triggered: fail-closed STOP/BLOCKED required without native provider fallback."
            )
            self.transition("FAILURE", msg)
            self.transition("STOP_BLOCKED", "Fail-closed STOP/BLOCKED required without native provider fallback")
            raise HarnessCompatibilityError(msg)

        if execution_returncode != 0:
            msg = (
                f"Harness tool execution smoke gate failed: execution_observed=True, returncode={execution_returncode}. "
                f"Harness tool execution smoke test failed with returncode {execution_returncode}. "
                "Observed successful tool execution required before routing work. "
                "STOP condition triggered: fail-closed STOP/BLOCKED required without native provider fallback."
            )
            self.transition("FAILURE", msg)
            self.transition("STOP_BLOCKED", "Fail-closed STOP/BLOCKED required without native provider fallback")
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
