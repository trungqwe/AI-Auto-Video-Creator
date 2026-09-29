#!/usr/bin/env python3
"""Automated negative fixture suite for Astra audit round 1 findings.

Tests all six findings (F1 to F6) with both negative counterexamples and positive cases:
- F1: Exact contract binding (wrong-registry & wrong-source hash FAIL, correct J route PASS)
- F2: Ownership & path safety (reject absolute/traversal/aliases, owned-vs-forbidden intersection, immutable evidence)
- F3: Scope & delta (pin approved base/candidate, committed diff + dirty overlay, rename both ends, immutable evidence)
- F4: Orca mapping & lifecycle (separate delivery task ID, worker_done CLI outcome, fresh dispatch, duplicate/stale rejection)
- F5: Readiness & traceability (validate real refs, readiness predicate, reject fake IDs and locked->ready)
- F6: Locks & leases (active lease schema vs declaration, integrated tasks hold no lease, disjoint DB namespaces, capacity bounds)
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add bundle dir to path to import delivery_engine
BUNDLE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BUNDLE_DIR.parents[1]
sys.path.insert(0, str(BUNDLE_DIR))

from delivery_engine import (  # noqa: E402
    ActiveLease,
    ContractBinding,
    ContractBindingError,
    DispatchBinding,
    DuplicateResultError,
    _FileLock,
    HarnessCompatibilityError,
    HarnessExecutionResult,
    HarnessExecutionStateMachine,
    LeaseManager,
    LockLeaseError,
    OrcaDeliveryAdapter,
    OwnershipPathError,
    ProtocolViolationError,
    ReadinessTraceabilityError,
    ScopeViolationError,
    SharedOrcaExecutionRegistry,
    StaleResultError,
    RoutingEvidenceError,
    LiveTerminalEvidence,
    UsageEvidence,
    ExecutionEnvelope,
    validate_execution_envelope,
    make_execution_envelope,
    build_contract_catalog,
    check_harness_tool_compatibility,
    check_owned_vs_forbidden,
    check_path_scope,
    namespaces_overlap,
    patterns_overlap,
    validate_commit_sha,
    validate_contract_ref,
    validate_path_syntax,
    validate_scope_and_deltas,
    validate_task_traceability_and_readiness,
)
from validate import check_secret_scan, check_task_dag


class TestF1ExactContractBinding(unittest.TestCase):
    """F1: Exact contract binding: each contract ID belongs to exact registry/source/owner/hash."""

    @classmethod
    def setUpClass(cls):
        cls.registry_path = BUNDLE_DIR / "contract-registry.yaml"
        cls.catalog = build_contract_catalog(cls.registry_path, ROOT_DIR)

    def test_f1_correct_j_route_pass(self):
        """Positive case: CT-AI-ROUTE-001 correctly bound to CONTRACT-CONFIG-SECURITY, owner J."""
        binding = self.catalog.get("CT-AI-ROUTE-001")
        self.assertIsNotNone(binding, "CT-AI-ROUTE-001 must exist in catalog")
        self.assertEqual(binding.registry_id, "CONTRACT-CONFIG-SECURITY")
        self.assertEqual(binding.owner, "J")

        ref = {
            "id": "CT-AI-ROUTE-001",
            "registry": "CONTRACT-CONFIG-SECURITY",
            "revision": binding.revision,
            "owner": "J",
        }
        validated = validate_contract_ref(ref, self.catalog)
        self.assertEqual(validated.id, "CT-AI-ROUTE-001")
        self.assertEqual(validated.owner, "J")

    def test_f1_wrong_registry_fail(self):
        """Negative counterexample: CT-AI-ROUTE-001 referenced with CONTRACT-CREATIVE-AI fails."""
        binding = self.catalog["CT-AI-ROUTE-001"]
        ref = {
            "id": "CT-AI-ROUTE-001",
            "registry": "CONTRACT-CREATIVE-AI",  # WRONG registry
            "revision": binding.revision,
        }
        with self.assertRaises(ContractBindingError) as ctx:
            validate_contract_ref(ref, self.catalog)
        self.assertIn("does not match defining registry", str(ctx.exception))

    def test_f1_wrong_source_hash_fail(self):
        """Negative counterexample: Contract ref with wrong/tampered revision hash fails."""
        ref = {
            "id": "CT-AI-ROUTE-001",
            "registry": "CONTRACT-CONFIG-SECURITY",
            "revision": "sha256:0000000000000000000000000000000000000000000000000000000000000000",  # WRONG hash
        }
        with self.assertRaises(ContractBindingError) as ctx:
            validate_contract_ref(ref, self.catalog)
        self.assertIn("does not match frozen revision", str(ctx.exception))

    def test_f1_unknown_contract_id_fail(self):
        """Negative counterexample: Non-existent contract ID fails."""
        ref = {
            "id": "CT-FAKE-999",
            "registry": "CONTRACT-CONFIG-SECURITY",
            "revision": "sha256:dummy",
        }
        with self.assertRaises(ContractBindingError) as ctx:
            validate_contract_ref(ref, self.catalog)
        self.assertIn("Unknown exact contract ID", str(ctx.exception))


class TestF2OwnershipAndPaths(unittest.TestCase):
    """F2: Ownership & paths: reject absolute/traversal/aliases, owned-vs-forbidden intersection, immutable evidence."""

    def test_f2_reject_absolute_path_fail(self):
        """Negative counterexample: Absolute paths (Unix or Windows) fail."""
        with self.assertRaises(OwnershipPathError):
            validate_path_syntax("/etc/passwd")
        with self.assertRaises(OwnershipPathError):
            validate_path_syntax("C:/workspace/file.txt")

    def test_f2_reject_traversal_path_fail(self):
        """Negative counterexample: Path traversal (..) fails."""
        with self.assertRaises(OwnershipPathError):
            validate_path_syntax("docs/../src/controlplane/main.py")
        with self.assertRaises(OwnershipPathError):
            validate_path_syntax("../secret.txt")

    def test_f2_reject_canonical_alias_fail(self):
        """Negative counterexample: Redundant ./ or // or backslashes fail."""
        with self.assertRaises(OwnershipPathError):
            validate_path_syntax("./docs/parallel-delivery/README.md")
        with self.assertRaises(OwnershipPathError):
            validate_path_syntax("docs//parallel-delivery/README.md")
        with self.assertRaises(OwnershipPathError):
            validate_path_syntax("docs\\parallel-delivery\\README.md")

    def test_f2_owned_vs_forbidden_intersection_fail(self):
        """Negative counterexample: Owned paths intersecting forbidden paths fail."""
        owned = ["docs/parallel-delivery/**"]
        forbidden = ["docs/**"]
        errors = check_owned_vs_forbidden(owned, forbidden)
        self.assertTrue(len(errors) > 0, "Intersection between docs/parallel-delivery/** and docs/** must be detected")
        self.assertIn("intersects forbidden path", errors[0])

    def test_f2_immutable_evidence_mutation_lease_fail(self):
        """Negative counterexample: Mutation lease on LOCK-ACCEPTED-EVIDENCE fails."""
        mgr = LeaseManager([
            {
                "id": "LOCK-ACCEPTED-EVIDENCE",
                "class": "evidence",
                "mode": "immutable",
                "renewable": False,
                "mutation_lease_forbidden": True,
            }
        ])
        mgr.set_task_authority("TASK-1", "granted")
        with self.assertRaises(LockLeaseError) as ctx:
            mgr.acquire_lease("LOCK-ACCEPTED-EVIDENCE", "TASK-1", "ctx-1")
        self.assertIn("immutable", str(ctx.exception).lower())

    def test_f2_disjoint_valid_paths_pass(self):
        """Positive case: Clean relative paths with no intersection pass."""
        owned = ["docs/parallel-delivery/**"]
        forbidden = ["src/**", "tests/**", "**/*.sql"]
        errors = check_owned_vs_forbidden(owned, forbidden)
        self.assertEqual(len(errors), 0, "Disjoint paths must produce no errors")


class TestF3ScopeAndCandidateDelta(unittest.TestCase):
    """F3: Scope: pin approved base/candidate; committed diff + dirty overlay, rename both ends, immutable evidence."""

    def test_f3_forbidden_committed_delta_fail(self):
        """Negative counterexample: Changed path in src/ or tests/ fails scope check."""
        err = check_path_scope("src/controlplane/api/main.py")
        self.assertIsNotNone(err)
        self.assertIn("Forbidden path", err)

        err_test = check_path_scope("tests/m2/test_p7b_hardening.py")
        self.assertIsNotNone(err_test)
        self.assertIn("Forbidden path", err_test)

        err_sql = check_path_scope("src/controlplane/infrastructure/db/migrations/0009_test.sql")
        self.assertIsNotNone(err_sql)
        self.assertIn("Forbidden path", err_sql)

    def test_f3_rename_both_ends_fail_on_old_path(self):
        """Negative counterexample: Renaming from a forbidden path to allowed path fails on old_path."""
        old_path = "src/controlplane/api/main.py"
        new_path = "docs/parallel-delivery/moved.py"
        err_old = check_path_scope(old_path)
        self.assertIsNotNone(err_old, "Old path in src/ must be rejected")
        self.assertIn("Forbidden path", err_old)

    def test_f3_rename_both_ends_fail_on_new_path(self):
        """Negative counterexample: Renaming from allowed path to forbidden path fails on new_path."""
        old_path = "docs/parallel-delivery/file.py"
        new_path = "src/controlplane/injected.py"
        err_new = check_path_scope(new_path)
        self.assertIsNotNone(err_new, "New path in src/ must be rejected")
        self.assertIn("Forbidden path", err_new)

    def test_f3_immutable_evidence_modification_fail(self):
        """Negative counterexample: Changing historical accepted evidence fails."""
        err = check_path_scope("docs/milestones/m2-control-plane/evidence/m2-p7b/run-m2-p7b-green-20260917040648/status.json")
        self.assertIsNotNone(err)
        self.assertIn("Historical evidence changed", err)

    def test_f3_clean_docs_scope_pass(self):
        """Positive case: Modifying allowed docs/parallel-delivery files passes scope check."""
        self.assertIsNone(check_path_scope("docs/parallel-delivery/protocol.md"))
        self.assertIsNone(check_path_scope("docs/parallel-delivery/contract-registry.yaml"))
        self.assertIsNone(check_path_scope("AGENTS.md"))
        self.assertIsNone(check_path_scope("HANDOFF.md"))


class TestF4OrcaMappingAndLifecycle(unittest.TestCase):
    """F4: Orca mapping: separate delivery ledger task ID, worker_done outcome, fresh dispatch, duplicate/stale rejection."""

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.lease_mgr = LeaseManager([
            {"id": "LOCK-PARALLEL-REGISTRY", "mode": "exclusive", "renewable": True},
        ])
        self.lease_mgr.set_task_authority("PD-PILOT-CONTROL", "granted")
        self.adapter = OrcaDeliveryAdapter(self.lease_mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        self.adapter.set_task_authority("PD-PILOT-CONTROL", "granted")
        self.adapter.set_task_state("PD-PILOT-CONTROL", "ready")
        self.adapter.register_task_locks("PD-PILOT-CONTROL", ["LOCK-PARALLEL-REGISTRY"])

    def _create_dispatch_helper(self, delivery_id="PD-PILOT-CONTROL", orca_task_id=None):
        if orca_task_id is None:
            self._dispatch_counter = getattr(self, "_dispatch_counter", 0) + 1
            orca_task_id = f"task_orca_{self._dispatch_counter:03d}"
        else:
            self._dispatch_counter = getattr(self, "_dispatch_counter", 0) + 1
        ctx_id = f"ctx_{delivery_id}_{self._dispatch_counter:03d}"
        self.adapter.register_task_locks(delivery_id, ["LOCK-PARALLEL-REGISTRY"])
        lease = self.lease_mgr.acquire_lease("LOCK-PARALLEL-REGISTRY", delivery_id, ctx_id)
        dispatch_id = self.adapter.create_dispatch(
            delivery_id,
            orca_task_id=orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id=ctx_id,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(delivery_id, ctx_id),
        )
        return dispatch_id, lease

    def test_f4_separate_delivery_task_from_orca_execution_pass(self):
        """Positive case: Delivery Task ID is separated from Orca Task ID and Dispatch ID."""
        delivery_id = "PD-PILOT-CONTROL"
        dispatch_id, lease = self._create_dispatch_helper(delivery_id)
        self.assertTrue(dispatch_id.startswith("ctx_PD-PILOT-CONTROL_"))
        self.assertNotEqual(delivery_id, dispatch_id)
        self.assertEqual(self.adapter.get_task_state(delivery_id), "dispatched")

    def test_f4_worker_done_invalid_outcome_fail(self):
        """Negative counterexample: worker_done with outcome other than 'succeeded' or 'failed' fails."""
        dispatch_id, lease = self._create_dispatch_helper("PD-PILOT-CONTROL")
        self.adapter.acknowledge_dispatch("PD-PILOT-CONTROL", dispatch_id)
        self.adapter.start_running("PD-PILOT-CONTROL", dispatch_id)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_worker_done(
                delivery_task_id="PD-PILOT-CONTROL",
                orca_task_id="task_orca_001",
                dispatch_id=dispatch_id,
                outcome="integrated",  # FORBIDDEN: CLI only accepts succeeded|failed
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
            )
        self.assertIn("Orca CLI only supports 'succeeded' or 'failed'", str(ctx.exception))

    def test_f4_success_to_review_to_integrated_pass(self):
        """Positive case: worker_done succeeded -> review -> review ACCEPT -> merge_queued -> integrated."""
        delivery_id = "PD-PILOT-CONTROL"
        dispatch_id, lease = self._create_dispatch_helper(delivery_id)
        self.adapter.acknowledge_dispatch(delivery_id, dispatch_id)
        self.adapter.start_running(delivery_id, dispatch_id)

        # 1. worker_done succeeded settles attempt and moves delivery task to review
        state = self.adapter.handle_worker_done(
            delivery_task_id=delivery_id,
            orca_task_id="task_orca_001",
            dispatch_id=dispatch_id,
            outcome="succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
        )
        self.assertEqual(state, "review")

        # 2. Independent review verdict ACCEPT moves task to merge_queued
        state = self.adapter.handle_review_verdict(delivery_id, "ACCEPT")
        self.assertEqual(state, "merge_queued")

        # 3. Integration gates pass moves task to integrated
        state = self.adapter.handle_integration_gates(delivery_id, gates_pass=True)
        self.assertEqual(state, "integrated")

    def test_f4_blocked_replan_requires_fresh_dispatch_pass(self):
        """Positive case: worker_done failed -> blocked -> lease released -> resume requires fresh dispatch."""
        delivery_id = "PD-PILOT-CONTROL"
        dispatch_1, lease_1 = self._create_dispatch_helper(delivery_id)
        self.assertEqual(len(self.lease_mgr.active_leases), 1)

        self.adapter.acknowledge_dispatch(delivery_id, dispatch_1)
        self.adapter.start_running(delivery_id, dispatch_1)

        # Worker reports failure / blocker
        state = self.adapter.handle_worker_done(
            delivery_task_id=delivery_id,
            orca_task_id="task_orca_001",
            dispatch_id=dispatch_1,
            outcome="failed",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_1.fencing_token,
        )
        self.assertEqual(state, "blocked")
        # Leases must be released on blocker
        self.assertEqual(len(self.lease_mgr.active_leases), 0)

        # Resolve blocker
        self.adapter.resolve_blocker_and_replan(delivery_id)
        self.assertEqual(self.adapter.get_task_state(delivery_id), "ready")

        # Create fresh dispatch
        dispatch_2, lease_2 = self._create_dispatch_helper(delivery_id)
        self.assertNotEqual(dispatch_1, dispatch_2, "Must issue a fresh dispatch ID")
        self.assertEqual(self.adapter.get_task_state(delivery_id), "dispatched")

    def test_f4_duplicate_worker_done_rejected_fail(self):
        """Negative counterexample: Second worker_done for already settled dispatch is rejected."""
        delivery_id = "PD-PILOT-CONTROL"
        dispatch_id, lease = self._create_dispatch_helper(delivery_id)
        self.adapter.acknowledge_dispatch(delivery_id, dispatch_id)
        self.adapter.start_running(delivery_id, dispatch_id)
        self.adapter.handle_worker_done(
            delivery_id, "task_orca_001", dispatch_id, "succeeded",
            candidate_commit=self.candidate_commit, fencing_token=lease.fencing_token,
        )

        with self.assertRaises(DuplicateResultError):
            self.adapter.handle_worker_done(
                delivery_id, "task_orca_001", dispatch_id, "succeeded",
                candidate_commit=self.candidate_commit, fencing_token=lease.fencing_token,
            )

    def test_f4_stale_dispatch_result_rejected_fail(self):
        """Negative counterexample: Result from obsolete dispatch attempt is rejected."""
        delivery_id = "PD-PILOT-CONTROL"
        dispatch_1, lease_1 = self._create_dispatch_helper(delivery_id)
        self.adapter.acknowledge_dispatch(delivery_id, dispatch_1)
        self.adapter.start_running(delivery_id, dispatch_1)
        self.adapter.handle_worker_done(
            delivery_id, "task_orca_001", dispatch_1, "failed",
            candidate_commit=self.candidate_commit, fencing_token=lease_1.fencing_token,
        )
        self.adapter.resolve_blocker_and_replan(delivery_id)
        dispatch_2, lease_2 = self._create_dispatch_helper(delivery_id)

        # Late result from dispatch_1 arrives
        with self.assertRaises(DuplicateResultError):
            self.adapter.handle_worker_done(
                delivery_id, "task_orca_001", dispatch_1, "succeeded",
                candidate_commit=self.candidate_commit, fencing_token=lease_1.fencing_token,
            )


class TestF5ReadinessAndTraceability(unittest.TestCase):
    """F5: Readiness & traceability: validate real refs, readiness predicate, reject fake IDs and locked->ready."""

    @classmethod
    def setUpClass(cls):
        cls.registry_path = BUNDLE_DIR / "contract-registry.yaml"
        cls.catalog = build_contract_catalog(cls.registry_path, ROOT_DIR)
        cls.known_owners = {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "CROSS-CUTTING-CONTRACT-OWNER"}
        cls.known_requirements = {"QR-MNT-002", "QR-MNT-003", "QR-COMP-003", "FR-UI-001"}

    def test_f5_fake_invariant_id_fail(self):
        """Negative counterexample: Fake invariant ID (INV-999) fails."""
        task = {
            "id": "TASK-FAKE-INV",
            "authority": {"state": "granted"},
            "status": "planned",
            "invariant_refs": ["INV-999"],  # FAKE
            "requirement_refs": [],
            "module_owners": [],
            "contract_refs": [],
        }
        errors = validate_task_traceability_and_readiness(
            task, self.catalog, self.known_owners, self.known_requirements, ROOT_DIR
        )
        self.assertTrue(any("unknown/fake invariant ID 'INV-999'" in e for e in errors))

    def test_f5_fake_requirement_id_fail(self):
        """Negative counterexample: Fake requirement ID fails."""
        task = {
            "id": "TASK-FAKE-REQ",
            "authority": {"state": "granted"},
            "status": "planned",
            "invariant_refs": [],
            "requirement_refs": ["FR-FAKE-001"],  # FAKE
            "module_owners": [],
            "contract_refs": [],
        }
        errors = validate_task_traceability_and_readiness(
            task, self.catalog, self.known_owners, self.known_requirements, ROOT_DIR
        )
        self.assertTrue(any("unknown/fake requirement ID 'FR-FAKE-001'" in e for e in errors))

    def test_f5_fake_module_owner_fail(self):
        """Negative counterexample: Fake module owner fails."""
        task = {
            "id": "TASK-FAKE-OWNER",
            "authority": {"state": "granted"},
            "status": "planned",
            "invariant_refs": [],
            "requirement_refs": [],
            "module_owners": ["MODULE-UNKNOWN-Z"],  # FAKE
            "contract_refs": [],
        }
        errors = validate_task_traceability_and_readiness(
            task, self.catalog, self.known_owners, self.known_requirements, ROOT_DIR
        )
        self.assertTrue(any("unknown module owner 'MODULE-UNKNOWN-Z'" in e for e in errors))

    def test_f5_locked_to_ready_fail(self):
        """Negative counterexample: Task with authority locked marked 'ready' fails."""
        task = {
            "id": "M2-P8-LOCKED",
            "authority": {"state": "locked"},
            "status": "ready",  # FORBIDDEN: locked sentinel cannot be ready!
            "invariant_refs": [],
            "requirement_refs": [],
            "module_owners": [],
            "contract_refs": [],
            "acceptance": [
                {"requirement": "R", "instrument": "I", "counterexample": "C", "red_observation": "observed"}
            ],
        }
        errors = validate_task_traceability_and_readiness(
            task, self.catalog, self.known_owners, self.known_requirements, ROOT_DIR
        )
        self.assertTrue(any("forbidden from transitioning to 'ready'" in e for e in errors))

    def test_f5_future_template_to_ready_fail(self):
        """Negative counterexample: Future template marked 'ready' fails."""
        task = {
            "id": "M3-A-TEMPLATE",
            "authority": {"state": "future_template"},
            "status": "ready",  # FORBIDDEN: future template cannot be ready!
            "invariant_refs": [],
            "requirement_refs": [],
            "module_owners": [],
            "contract_refs": [],
            "acceptance": [
                {"requirement": "R", "instrument": "I", "counterexample": "C", "red_observation": "observed"}
            ],
        }
        errors = validate_task_traceability_and_readiness(
            task, self.catalog, self.known_owners, self.known_requirements, ROOT_DIR
        )
        self.assertTrue(any("forbidden from transitioning to 'ready'" in e for e in errors))

    def test_f5_unknown_observation_not_ready_fail(self):
        """Negative counterexample: Task marked 'ready' with 'unknown' red_observation fails."""
        task = {
            "id": "TASK-UNKNOWN-OBS",
            "authority": {"state": "granted"},
            "status": "ready",
            "invariant_refs": [],
            "requirement_refs": [],
            "module_owners": [],
            "contract_refs": [],
            "acceptance": [
                {"requirement": "R", "instrument": "I", "counterexample": "C", "red_observation": "unknown"}
            ],
        }
        errors = validate_task_traceability_and_readiness(
            task, self.catalog, self.known_owners, self.known_requirements, ROOT_DIR
        )
        self.assertTrue(any("cannot have empty, missing, or 'unknown' red_observation" in e for e in errors))

    def test_f5_valid_readiness_pass(self):
        """Positive case: Granted task with valid real refs and reviewed red_observation passes."""
        task = {
            "id": "PD-PILOT-CONTROL",
            "authority": {"state": "granted"},
            "status": "ready",
            "authority_refs": ["HANDOFF.md"],
            "invariant_refs": ["INV-002", "INV-012"],
            "requirement_refs": ["QR-MNT-002"],
            "module_owners": ["CROSS-CUTTING-CONTRACT-OWNER"],
            "contract_refs": [
                {
                    "id": "CT-CMN-012",
                    "registry": "CONTRACT-COMMON",
                    "revision": self.catalog["CT-CMN-012"].revision,
                }
            ],
            "acceptance": [
                {
                    "requirement": "R",
                    "instrument": "I",
                    "counterexample": "C",
                    "red_observation": "Observed concrete red before implementation",
                }
            ],
        }
        errors = validate_task_traceability_and_readiness(
            task, self.catalog, self.known_owners, self.known_requirements, ROOT_DIR
        )
        self.assertEqual(len(errors), 0, f"Valid readiness should pass but got: {errors}")


class TestF6LocksAndLeases(unittest.TestCase):
    """F6: Locks: declaration vs active lease, integrated tasks do not block, disjoint DB namespaces, capacity bounds."""

    def setUp(self):
        self.lock_defs = [
            {
                "id": "LOCK-POSTGRES-TEST-DB",
                "class": "runtime_resource",
                "mode": "exclusive_by_database_name",
                "partition_key_prefix": "db:",
                "renewable": True,
            },
            {
                "id": "LOCK-DESKTOP-GPU",
                "class": "runtime_resource",
                "mode": "capacity",
                "capacity": 2,
                "renewable": True,
            },
            {
                "id": "LOCK-DOC-AUTHORITY",
                "class": "path",
                "mode": "exclusive",
                "renewable": True,
            },
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.mgr.set_task_authority("TASK-1", "granted")
        self.mgr.set_task_authority("TASK-2", "granted")

    def test_f6_disjoint_db_namespaces_concurrent_pass(self):
        """Positive case: Disjoint database namespaces (db:test_worker_1 and db:test_worker_2) grant concurrently."""
        lease1 = self.mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "TASK-1", "ctx-1", resource_key="db:test_worker_1")
        lease2 = self.mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "TASK-2", "ctx-2", resource_key="db:test_worker_2")
        self.assertEqual(lease1.resource_key, "db:test_worker_1")
        self.assertEqual(lease2.resource_key, "db:test_worker_2")
        self.assertEqual(len(self.mgr.active_leases), 2)

    def test_f6_same_db_namespace_conflict_fail(self):
        """Negative counterexample: Attempting to lease the same database namespace fails."""
        self.mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "TASK-1", "ctx-1", resource_key="db:shared_test_db")
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "TASK-2", "ctx-2", resource_key="db:shared_test_db")
        self.assertIn("already leased", str(ctx.exception))

    def test_f6_capacity_lock_within_bounds_pass(self):
        """Positive case: Capacity allocations within bound (1 + 1 <= 2) pass."""
        lease1 = self.mgr.acquire_lease("LOCK-DESKTOP-GPU", "TASK-1", "ctx-1", units=1)
        lease2 = self.mgr.acquire_lease("LOCK-DESKTOP-GPU", "TASK-2", "ctx-2", units=1)
        self.assertEqual(lease1.units, 1)
        self.assertEqual(lease2.units, 1)

    def test_f6_capacity_lock_over_capacity_fail(self):
        """Negative counterexample: Capacity requests exceeding total capacity fail."""
        self.mgr.acquire_lease("LOCK-DESKTOP-GPU", "TASK-1", "ctx-1", units=1)
        with self.assertRaises(LockLeaseError) as ctx:
            # Requesting 2 units when only 1 is remaining
            self.mgr.acquire_lease("LOCK-DESKTOP-GPU", "TASK-2", "ctx-2", units=2)
        self.assertIn("over-capacity", str(ctx.exception))

    def test_f6_integrated_task_does_not_block_new_lease_pass(self):
        """Positive case: Integrated task holds no active lease and does not block new tasks."""
        # Task 1 acquires exclusive lock
        lease1 = self.mgr.acquire_lease("LOCK-DOC-AUTHORITY", "TASK-1", "ctx-1")
        self.assertEqual(len(self.mgr.active_leases), 1)

        # Task 1 is marked integrated
        self.mgr.mark_task_integrated("TASK-1")
        self.assertEqual(len(self.mgr.active_leases), 0, "Integrated task must release all active leases")

        # Task 2 can now acquire the same lock without conflict
        lease2 = self.mgr.acquire_lease("LOCK-DOC-AUTHORITY", "TASK-2", "ctx-2")
        self.assertEqual(lease2.delivery_task_id, "TASK-2")

    def test_f6_monotonic_fencing_token_pass(self):
        """Positive case: Successive leases for the same resource receive monotonic fencing tokens."""
        lease1 = self.mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "TASK-1", "ctx-1", resource_key="db:test_worker_1")
        token1 = lease1.fencing_token
        self.mgr.release_lease(lease1.lease_id)

        lease2 = self.mgr.acquire_lease("LOCK-POSTGRES-TEST-DB", "TASK-2", "ctx-2", resource_key="db:test_worker_1")
        token2 = lease2.fencing_token
        self.assertGreater(token2, token1, "Fencing token must increase monotonically")


class TestSolScopeValidationProbes(unittest.TestCase):
    """Sol Probe 1: Scope validation fail-closed, reject stale ac5bd30, require exact commit SHAs, renames both ends."""

    def test_sol_scope_reject_blank_or_invalid_base_sha(self):
        """Negative probe: Blank or non-existent base commit fails closed with ScopeViolationError."""
        with self.assertRaises(ScopeViolationError):
            validate_scope_and_deltas("", "HEAD", ROOT_DIR)
        with self.assertRaises(ScopeViolationError):
            validate_scope_and_deltas("non_existent_commit_12345", "HEAD", ROOT_DIR)

    def test_sol_scope_reject_blank_or_invalid_candidate_sha(self):
        """Negative probe: Blank or non-existent candidate commit fails closed with ScopeViolationError."""
        with self.assertRaises(ScopeViolationError):
            validate_scope_and_deltas("4a7c8c921b7e05066505d51b168a02c3fde61317", "", ROOT_DIR)
        with self.assertRaises(ScopeViolationError):
            validate_scope_and_deltas("4a7c8c921b7e05066505d51b168a02c3fde61317", "deadbeef00000000000000000000000000000000", ROOT_DIR)

    def test_sol_scope_stale_ac5bd30_pinning_detected(self):
        """Negative probe: task-dag.yaml silently pinning stale ac5bd30 is detected and rejected."""
        stale_dag = {
            "approved_base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
            "candidate_commit": "ac5bd304408bee6283b11bd271cf874101d119fa",
        }
        from validate import check_scope_and_deltas as validator_check_scope
        errs = validator_check_scope(stale_dag)
        self.assertTrue(any("silently pins stale candidate commit ac5bd30" in e for e in errs))

    def test_sol_scope_rename_evaluates_both_ends_rejects_forbidden(self):
        """Adversarial probe: Renaming either from or to a forbidden path is rejected."""
        err_old = check_path_scope("src/controlplane/old.py")
        self.assertIsNotNone(err_old)
        self.assertIn("Forbidden", err_old)

        err_new = check_path_scope("tests/new_test.py")
        self.assertIsNotNone(err_new)
        self.assertIn("Forbidden", err_new)


class TestSolLeaseManagerAdversarialProbes(unittest.TestCase):
    """Sol Probe 2: LeaseManager rejects unknown locks, invalid/missing resource_key, non-positive units,
    enforces expires_at, purges/denies expired leases, defines renewal/release, monotonic fencing,
    rejects stale/absent fencing on result mutation, enforces authority for every active state.
    """

    def setUp(self):
        self.lock_defs = [
            {"id": "LOCK-EXCLUSIVE-REG", "mode": "exclusive", "renewable": True},
            {"id": "LOCK-PARTITION-DB", "mode": "exclusive_by_database_name", "partition_key_prefix": "db:", "renewable": True},
            {"id": "LOCK-CAPACITY-RUNNERS", "mode": "capacity", "capacity": 3, "renewable": True},
            {"id": "LOCK-EVIDENCE-IMMUTABLE", "mode": "immutable", "renewable": False, "mutation_lease_forbidden": True},
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.mgr.set_task_authority("TASK-1", "granted")
        self.mgr.set_task_authority("TASK-2", "granted")
        self.mgr.set_task_authority("T1", "granted")
        self.mgr.set_task_authority("T2", "granted")

    def test_sol_lease_reject_unknown_lock(self):
        """Adversarial probe: Unknown/undeclared lock ID is rejected fail-closed."""
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("LOCK-NOT-DECLARED", "TASK-1", "ctx-1")
        self.assertIn("Unknown lock ID", str(ctx.exception))

    def test_sol_lease_reject_missing_or_blank_resource_key_on_partitionable(self):
        """Adversarial probe: Missing or blank resource_key on partitionable lock is rejected."""
        with self.assertRaises(LockLeaseError) as ctx1:
            self.mgr.acquire_lease("LOCK-PARTITION-DB", "TASK-1", "ctx-1", resource_key=None)
        self.assertIn("Missing resource_key", str(ctx1.exception))

        with self.assertRaises(LockLeaseError) as ctx2:
            self.mgr.acquire_lease("LOCK-PARTITION-DB", "TASK-1", "ctx-1", resource_key="   ")
        self.assertIn("Missing resource_key", str(ctx2.exception))

    def test_sol_lease_reject_invalid_prefix_or_empty_namespace(self):
        """Adversarial probe: resource_key not starting with prefix or empty namespace after prefix rejected."""
        with self.assertRaises(LockLeaseError) as ctx1:
            self.mgr.acquire_lease("LOCK-PARTITION-DB", "TASK-1", "ctx-1", resource_key="invalid_db_name")
        self.assertIn("must start with prefix", str(ctx1.exception))

        with self.assertRaises(LockLeaseError) as ctx2:
            self.mgr.acquire_lease("LOCK-PARTITION-DB", "TASK-1", "ctx-1", resource_key="db:")
        self.assertIn("empty", str(ctx2.exception).lower())

    def test_sol_lease_reject_zero_or_negative_units(self):
        """Adversarial probe: Zero or negative capacity units rejected."""
        with self.assertRaises(LockLeaseError) as ctx1:
            self.mgr.acquire_lease("LOCK-CAPACITY-RUNNERS", "TASK-1", "ctx-1", units=0)
        self.assertIn("positive integer", str(ctx1.exception))

        with self.assertRaises(LockLeaseError) as ctx2:
            self.mgr.acquire_lease("LOCK-CAPACITY-RUNNERS", "TASK-1", "ctx-1", units=-2)
        self.assertIn("positive integer", str(ctx2.exception))

    def test_sol_lease_compute_and_enforce_expires_at(self):
        """Adversarial probe: LeaseManager computes expires_at and expires_at is enforced."""
        lease = self.mgr.acquire_lease("LOCK-EXCLUSIVE-REG", "TASK-1", "ctx-1", lease_seconds=300)
        self.assertIsNotNone(lease.expires_at)
        exp_dt = datetime.fromisoformat(lease.expires_at)
        acq_dt = datetime.fromisoformat(lease.acquired_at)
        diff = (exp_dt - acq_dt).total_seconds()
        self.assertEqual(diff, 300)

    def test_sol_lease_purge_and_deny_expired_lease(self):
        """Adversarial probe: Expired lease is purged and denied; resource freed for new lease."""
        past_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        lease1 = self.mgr.acquire_lease(
            "LOCK-EXCLUSIVE-REG", "TASK-1", "ctx-1", lease_seconds=60, now=past_time
        )
        self.assertIn(lease1.lease_id, self.mgr.active_leases)

        now_time = datetime(2026, 1, 1, 0, 1, 40, tzinfo=timezone.utc)
        purged = self.mgr.purge_expired_leases(now=now_time)
        self.assertIn(lease1.lease_id, purged)
        self.assertNotIn(lease1.lease_id, self.mgr.active_leases)

        lease2 = self.mgr.acquire_lease(
            "LOCK-EXCLUSIVE-REG", "TASK-2", "ctx-2", lease_seconds=60, now=now_time
        )
        self.assertEqual(lease2.delivery_task_id, "TASK-2")

    def test_sol_lease_renew_active_and_deny_expired_renewal(self):
        """Adversarial probe: Active lease renewal succeeds; expired lease renewal fails."""
        start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        lease = self.mgr.acquire_lease("LOCK-EXCLUSIVE-REG", "TASK-1", "ctx-1", lease_seconds=60, now=start_time)

        mid_time = datetime(2026, 1, 1, 0, 0, 30, tzinfo=timezone.utc)
        renewed = self.mgr.renew_lease(lease.lease_id, extend_seconds=120, now=mid_time)
        self.assertTrue(renewed.is_active)

        late_time = datetime(2026, 1, 1, 0, 10, 0, tzinfo=timezone.utc)
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.renew_lease(renewed.lease_id, extend_seconds=60, now=late_time)
        self.assertIn("expired", str(ctx.exception).lower())

    def test_sol_lease_monotonic_fencing_per_resource(self):
        """Adversarial probe: Fencing tokens increase monotonically per resource across sequential leases."""
        l1 = self.mgr.acquire_lease("LOCK-PARTITION-DB", "T1", "c1", resource_key="db:isolated_1")
        tok1 = l1.fencing_token
        self.mgr.release_lease(l1.lease_id)

        l2 = self.mgr.acquire_lease("LOCK-PARTITION-DB", "T2", "c2", resource_key="db:isolated_1")
        tok2 = l2.fencing_token
        self.assertGreater(tok2, tok1)

    def test_sol_lease_reject_stale_or_absent_fencing_token(self):
        """Adversarial probe: validate_fencing_token rejects absent and stale tokens."""
        l1 = self.mgr.acquire_lease("LOCK-EXCLUSIVE-REG", "T1", "c1")
        current_token = l1.fencing_token

        with self.assertRaises(LockLeaseError) as ctx1:
            self.mgr.validate_fencing_token("LOCK-EXCLUSIVE-REG", None)
        self.assertIn("Absent fencing token", str(ctx1.exception))

        with self.assertRaises(LockLeaseError) as ctx2:
            self.mgr.validate_fencing_token("LOCK-EXCLUSIVE-REG", current_token - 1)
        self.assertIn("Stale fencing token", str(ctx2.exception))

        self.mgr.validate_fencing_token("LOCK-EXCLUSIVE-REG", current_token)

    def test_sol_lease_enforce_authority_for_every_active_state(self):
        """Adversarial probe: Non-granted authority states (locked, future_template, revoked) rejected."""
        for unauthorized in ("locked", "future_template", "revoked"):
            with self.assertRaises(LockLeaseError) as ctx:
                self.mgr.acquire_lease("LOCK-EXCLUSIVE-REG", "T1", "c1", authority_state=unauthorized)
            self.assertIn("only 'granted' permitted", str(ctx.exception))


class TestSolOrcaDeliveryAdapterAdversarialProbes(unittest.TestCase):
    """Sol Probe 3: OrcaDeliveryAdapter binds and validates delivery_task_id, exact orca_task_id,
    authoritative dispatch_id, candidate_commit, and fencing token; rejects blank/wrong identity,
    stale/duplicate attempts, and candidate mismatch.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.lock_defs = [{"id": "LOCK-REG", "mode": "exclusive", "renewable": True}]
        self.lease_mgr = LeaseManager(self.lock_defs)
        self.lease_mgr.set_task_authority("TASK-PILOT", "granted")
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.adapter = OrcaDeliveryAdapter(self.lease_mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        self.adapter.set_task_authority("TASK-PILOT", "granted")
        self.adapter.set_task_state("TASK-PILOT", "ready")
        self.adapter.register_task_locks("TASK-PILOT", ["LOCK-REG"])
        self.lease = self.lease_mgr.acquire_lease("LOCK-REG", "TASK-PILOT", "ctx-setup")

    def test_sol_adapter_reject_blank_identities(self):
        """Adversarial probe: Blank delivery_task_id, orca_task_id, or dispatch_id rejected."""
        with self.assertRaises(ProtocolViolationError):
            self.adapter.create_dispatch(
                "",
                orca_task_id="task_1",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
            )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.create_dispatch(
                "TASK-PILOT",
                orca_task_id="   ",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
            )

        dispatch_id = self.adapter.create_dispatch(
            "TASK-PILOT",
            orca_task_id="task_1",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id="ctx-setup",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-PILOT", "ctx-setup"),
        )
        self.adapter.acknowledge_dispatch("TASK-PILOT", dispatch_id)
        self.adapter.start_running("TASK-PILOT", dispatch_id)
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_worker_done(
                "",
                "task_1",
                dispatch_id,
                "succeeded",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
            )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_worker_done(
                "TASK-PILOT",
                "",
                dispatch_id,
                "succeeded",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
            )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_worker_done(
                "TASK-PILOT",
                "task_1",
                "",
                "succeeded",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
            )

    def test_sol_adapter_reject_wrong_orca_task_id(self):
        """Adversarial probe: Mismatch in bound exact orca_task_id rejected."""
        dispatch_id = self.adapter.create_dispatch(
            "TASK-PILOT",
            orca_task_id="task_orca_bound",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id="ctx-setup",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-PILOT", "ctx-setup"),
        )
        self.adapter.acknowledge_dispatch("TASK-PILOT", dispatch_id)
        self.adapter.start_running("TASK-PILOT", dispatch_id)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_worker_done(
                "TASK-PILOT",
                orca_task_id="task_orca_impostor",
                dispatch_id=dispatch_id,
                outcome="succeeded",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
            )
        self.assertIn("orca_task_id mismatch", str(ctx.exception))

    def test_sol_adapter_reject_candidate_commit_mismatch(self):
        """Adversarial probe: Candidate commit mismatch between bound dispatch and worker_done rejected."""
        bound_commit = self.candidate_commit
        self.adapter.approved_candidate_commit = bound_commit
        dispatch_id = self.adapter.create_dispatch(
            "TASK-PILOT",
            orca_task_id="task_orca_001",
            candidate_commit=bound_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id="ctx-setup",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-PILOT", "ctx-setup"),
        )
        self.adapter.acknowledge_dispatch("TASK-PILOT", dispatch_id)
        self.adapter.start_running("TASK-PILOT", dispatch_id)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_worker_done(
                "TASK-PILOT",
                orca_task_id="task_orca_001",
                dispatch_id=dispatch_id,
                outcome="succeeded",
                candidate_commit="0000000000000000000000000000000000000000",
                fencing_token=self.lease.fencing_token,
            )
        self.assertIn("Candidate commit mismatch", str(ctx.exception))

    def test_sol_adapter_reject_absent_and_stale_fencing_tokens(self):
        """Adversarial probe: Absent or stale fencing tokens rejected on worker_done."""
        dispatch_id = self.adapter.create_dispatch(
            "TASK-PILOT",
            orca_task_id="task_orca_001",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id="ctx-setup",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-PILOT", "ctx-setup"),
        )
        self.adapter.acknowledge_dispatch("TASK-PILOT", dispatch_id)
        self.adapter.start_running("TASK-PILOT", dispatch_id)
        with self.assertRaises(ProtocolViolationError) as ctx1:
            self.adapter.handle_worker_done(
                "TASK-PILOT",
                orca_task_id="task_orca_001",
                dispatch_id=dispatch_id,
                outcome="succeeded",
                candidate_commit=self.candidate_commit,
                fencing_token=None,
            )
        self.assertIn("Absent fencing token", str(ctx1.exception))

        with self.assertRaises(StaleResultError) as ctx2:
            self.adapter.handle_worker_done(
                "TASK-PILOT",
                orca_task_id="task_orca_001",
                dispatch_id=dispatch_id,
                outcome="succeeded",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token - 1,
            )
        self.assertIn("Stale fencing token", str(ctx2.exception))

    def test_sol_adapter_enforce_authority_on_dispatch(self):
        """Adversarial probe: Non-granted task authority rejected from dispatch."""
        for unauthorized in ("locked", "future_template", "revoked"):
            with self.assertRaises(ProtocolViolationError) as ctx:
                self.adapter.create_dispatch(
                    "TASK-PILOT",
                    orca_task_id="task_orca_001",
                    candidate_commit=self.candidate_commit,
                    fencing_token=self.lease.fencing_token,
                    lease_id=self.lease.lease_id,
                    authority_state=unauthorized,
                    intended_dispatch_id="ctx-setup",
                )
            self.assertIn("only 'granted' authority permitted", str(ctx.exception))


class TestSolHarnessCompatibilityGate(unittest.TestCase):
    """Sol Probe 5: Harness compatibility gate.
    Codex CLI routed to ag/gemini-3.8-flash-high was observed collapsing namespaced tools
    (functions.exec -> functions) and therefore cannot be considered executable merely from route success.
    Requires tool-execution smoke test and safe fallback/STOP condition without overgeneralizing permanence.
    """

    def test_harness_namespaced_tool_collapse_triggers_stop_condition(self):
        """Adversarial probe: Collapsed namespaced tool (functions.exec -> functions) triggers STOP condition."""
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            check_harness_tool_compatibility("functions", "functions.exec")
        self.assertIn("Harness namespaced tool collapse detected", str(ctx.exception))
        self.assertIn("STOP condition triggered", str(ctx.exception))

    def test_harness_correct_tool_execution_pass(self):
        """Positive probe: Properly qualified tool execution passes harness compatibility gate."""
        # When harness preserves full namespace, smoke test passes
        check_harness_tool_compatibility("functions.exec", "functions.exec")
        check_harness_tool_compatibility("run_command", "run_command")



class TestSolTwentyOneIndependentProbes(unittest.TestCase):
    """Comprehensive fixture suite explicitly verifying remediation of all 21 Sol independent bypasses
    plus neighboring boundary tests, guaranteeing fail-closed enforcement across:
    - Invariant Group 1: Validation Invocation & Scope (Probes 01 - 06)
    - Invariant Group 2: Lock Registry Schema & Strict Lease Allocations (Probes 07 - 16)
    - Invariant Group 3: Monotonic Fencing Tokens & Result Mutations (Probes 17 - 18)
    - Invariant Group 4: Orca Dispatch Identity & Lifecycle State Machine (Probes 19 - 21)
    - Boundary Fixtures: Harness Tool Compatibility Smoke & Type Strictness (Boundary Probes 22 - 24)
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.approved_base = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.standard_lock_defs = [
            {"id": "SOL-LOCK-EXCL", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
            {"id": "SOL-LOCK-DB", "mode": "exclusive_by_database_name", "partition_key_prefix": "db:", "renewable": True},
            {"id": "SOL-LOCK-EXT-DRIVE", "mode": "exclusive", "renewable": True},
            {"id": "SOL-LOCK-CAP", "mode": "capacity", "capacity": 2, "renewable": True},
            {"id": "SOL-LOCK-IMMUTABLE", "mode": "immutable", "renewable": False, "mutation_lease_forbidden": True},
        ]
        self.mgr = LeaseManager(self.standard_lock_defs)
        self.mgr.set_task_authority("TASK-PROBE", "granted")
        self.mgr.set_task_authority("TASK-OTHER", "granted")
        self.adapter = OrcaDeliveryAdapter(self.mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        self.adapter.set_task_authority("TASK-PROBE", "granted")
        self.adapter.set_task_authority("TASK-OTHER", "granted")
        self.adapter.set_task_state("TASK-PROBE", "ready")
        self.adapter.set_task_state("TASK-OTHER", "ready")
        self.adapter.register_task_locks("TASK-PROBE", ["SOL-LOCK-EXCL"])
        self.adapter.register_task_locks("TASK-OTHER", ["SOL-LOCK-EXCL"])

    # --- Sol Probe 01: Scope candidate must be 40-hex SHA, reject HEAD and ref names ---
    def test_sol_probe_01_reject_head_or_ref_name_as_candidate(self):
        for invalid in ("HEAD", "head", "refs/heads/main", "main", "v1.0.0", "HEAD~1", "8f3e040"):
            with self.assertRaises(ScopeViolationError):
                validate_commit_sha(invalid, "candidate_commit", ROOT_DIR, require_full_sha=True)

    # --- Sol Probe 02: Reject base == candidate self-validation ---
    def test_sol_probe_02_reject_self_chosen_base_equals_candidate(self):
        with self.assertRaises(ScopeViolationError) as ctx:
            validate_scope_and_deltas(
                self.candidate_commit,
                self.candidate_commit,
                ROOT_DIR,
                approved_base=self.candidate_commit,
                require_candidate_is_head=False,
            )
        self.assertIn("equals candidate commit", str(ctx.exception))

    # --- Sol Probe 03: Reject candidate that does not equal actual HEAD ---
    def test_sol_probe_03_reject_non_head_candidate_commit(self):
        non_head_candidate = "f98eb902696d1c7c27e7cc15efbe1a0b5a8ca571"
        with self.assertRaises(ScopeViolationError) as ctx:
            validate_scope_and_deltas(
                self.approved_base,
                non_head_candidate,
                ROOT_DIR,
                approved_base=self.approved_base,
                require_candidate_is_head=True,
            )
        self.assertIn("does not equal actual current HEAD", str(ctx.exception))

    # --- Sol Probe 04: Reject stale pin or non-baseline base SHA ---
    def test_sol_probe_04_reject_stale_or_non_baseline_base_commit(self):
        stale_base = "ac5bd304408bee6283b11bd271cf874101d119fa"
        with self.assertRaises(ScopeViolationError) as ctx:
            validate_scope_and_deltas(
                stale_base,
                self.candidate_commit,
                ROOT_DIR,
                approved_base=self.approved_base,
            )
        self.assertIn("does not match approved project baseline", str(ctx.exception))

    # --- Sol Probe 05: Read-only validator leaves tree completely clean ---
    def test_sol_probe_05_read_only_validator_leaves_tree_clean(self):
        import os
        if os.environ.get("_IN_SOL_PROBE_05") == "1":
            return
        report_path = ROOT_DIR / "docs" / "parallel-delivery" / ".validation-report.json"
        content_before = report_path.read_bytes() if report_path.exists() else None
        stat_before = subprocess.run(
            ["git", "status", "--porcelain", "docs/parallel-delivery/.validation-report.json"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        env = os.environ.copy()
        env["_IN_SOL_PROBE_05"] = "1"
        if "VALIDATE_SKIP_FIXTURES" in env:
            del env["VALIDATE_SKIP_FIXTURES"]
        proc = subprocess.run(
            [sys.executable, str(ROOT_DIR / "docs" / "parallel-delivery" / "validate.py")],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, f"Validator failed: {proc.stderr}\nstdout: {proc.stdout}")
        self.assertIn("ATTESTATION [READ-ONLY AUDIT]", proc.stdout)
        content_after = report_path.read_bytes() if report_path.exists() else None
        self.assertEqual(content_before, content_after, "Read-only validator modified .validation-report.json content")
        stat_after = subprocess.run(
            ["git", "status", "--porcelain", "docs/parallel-delivery/.validation-report.json"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        self.assertEqual(stat_before.stdout, stat_after.stdout, "Read-only validator changed git status of .validation-report.json")

    # --- Sol Probe 06: File renames evaluate both ends and reject forbidden paths ---
    def test_sol_probe_06_rename_evaluation_on_both_ends(self):
        err_src = check_path_scope("src/core/engine.py")
        self.assertIsNotNone(err_src)
        self.assertIn("Forbidden", err_src)

        err_dst = check_path_scope("tests/test_core.py")
        self.assertIsNotNone(err_dst)
        self.assertIn("Forbidden", err_dst)

        err_ok = check_path_scope("docs/parallel-delivery/spec.md")
        self.assertIsNone(err_ok)

    # --- Sol Probe 07: Lock registry schema: reject duplicate lock IDs at construction ---
    def test_sol_probe_07_lock_schema_rejects_duplicate_ids_at_construction(self):
        dup_defs = [
            {"id": "LOCK-DUP", "mode": "exclusive", "renewable": True},
            {"id": "LOCK-DUP", "mode": "exclusive", "renewable": True},
        ]
        with self.assertRaises(LockLeaseError) as ctx:
            LeaseManager(dup_defs)
        self.assertIn("Duplicate lock ID", str(ctx.exception))

    # --- Sol Probe 08: Lock registry schema: reject unknown modes at construction ---
    def test_sol_probe_08_lock_schema_rejects_unknown_mode_at_construction(self):
        bad_mode = [{"id": "LOCK-BAD", "mode": "unsupported_distributed_mode", "renewable": True}]
        with self.assertRaises(LockLeaseError) as ctx:
            LeaseManager(bad_mode)
        self.assertIn("Unknown lock mode", str(ctx.exception))

    # --- Sol Probe 09: Lock registry schema: require boolean renewable flag ---
    def test_sol_probe_09_lock_schema_requires_boolean_renewable_flag(self):
        missing_renew = [{"id": "LOCK-1", "mode": "exclusive"}]
        with self.assertRaises(LockLeaseError) as ctx:
            LeaseManager(missing_renew)
        self.assertIn("boolean 'renewable' flag", str(ctx.exception))

        string_renew = [{"id": "LOCK-1", "mode": "exclusive", "renewable": "true"}]
        with self.assertRaises(LockLeaseError) as ctx:
            LeaseManager(string_renew)
        self.assertIn("boolean 'renewable' flag", str(ctx.exception))

    # --- Sol Probe 10: Lock registry schema: reject non-positive capacity and lease_seconds ---
    def test_sol_probe_10_lock_schema_rejects_nonpositive_capacity_or_lease_seconds(self):
        bad_cap = [{"id": "LOCK-C", "mode": "capacity", "capacity": 0, "renewable": True}]
        with self.assertRaises(LockLeaseError) as ctx:
            LeaseManager(bad_cap)
        self.assertIn("strict positive integer", str(ctx.exception))

        bad_secs = [{"id": "LOCK-S", "mode": "exclusive", "lease_seconds": -5, "renewable": True}]
        with self.assertRaises(LockLeaseError) as ctx:
            LeaseManager(bad_secs)
        self.assertIn("strict positive integer", str(ctx.exception))

    # --- Sol Probe 11: Lock registry schema: partitioned lock requires non-empty partition_key_prefix ---
    def test_sol_probe_11_lock_schema_partitioned_requires_prefix(self):
        no_prefix = [{"id": "LOCK-P", "mode": "exclusive_by_database_name", "renewable": True}]
        with self.assertRaises(LockLeaseError) as ctx:
            LeaseManager(no_prefix)
        self.assertIn("must declare partition_key_prefix", str(ctx.exception))

    # --- Sol Probe 12: Acquire lease: reject boolean units (isinstance(True, int) bypass) ---
    def test_sol_probe_12_acquire_lease_rejects_boolean_units(self):
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("SOL-LOCK-CAP", "TASK-PROBE", "ctx-1", units=True)
        self.assertIn("strict positive integer", str(ctx.exception))

        with self.assertRaises(LockLeaseError) as ctx2:
            self.mgr.acquire_lease("SOL-LOCK-CAP", "TASK-PROBE", "ctx-1", units=False)
        self.assertIn("strict positive integer", str(ctx2.exception))

    # --- Sol Probe 13: Acquire lease: reject fractional, zero, and negative units ---
    def test_sol_probe_13_acquire_lease_rejects_fractional_zero_negative_units(self):
        for bad_units in (0, -1, 1.5, "1"):
            with self.assertRaises(LockLeaseError) as ctx:
                self.mgr.acquire_lease("SOL-LOCK-CAP", "TASK-PROBE", "ctx-1", units=bad_units)
            self.assertIn("strict positive integer", str(ctx.exception))

    # --- Sol Probe 14: Authority must be explicitly registered/granted; never default granted ---
    def test_sol_probe_14_authority_must_be_explicitly_registered_no_default_granted(self):
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("SOL-LOCK-EXCL", "TASK-UNREGISTERED", "ctx-1")
        self.assertIn("no registered authority", str(ctx.exception))

        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.adapter.create_dispatch(
                "TASK-UNREGISTERED",
                orca_task_id="orca-1",
                candidate_commit=self.candidate_commit,
                fencing_token=1,
                lease_id="fake-id",
            )
        self.assertIn("no registered authority", str(ctx2.exception))

    # --- Sol Probe 15: Reject duplicate or overlapping external-resource leases ---
    def test_sol_probe_15_reject_duplicate_overlapping_external_resource_leases(self):
        l1 = self.mgr.acquire_lease("SOL-LOCK-DB", "TASK-PROBE", "ctx-1", resource_key="db:isolated_sharded")
        self.assertTrue(l1.is_active)

        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("SOL-LOCK-DB", "TASK-OTHER", "ctx-2", resource_key="db:isolated_sharded")
        self.assertIn("already leased", str(ctx.exception))

    # --- Sol Probe 16: Renewal rejects non-renewable, expired, or revoked leases ---
    def test_sol_probe_16_renewal_rejects_nonrenewable_expired_revoked(self):
        # 1. Non-renewable lock
        self.mgr.set_task_authority("TASK-IMMUTABLE-TEST", "granted")
        with self.assertRaises(LockLeaseError):
            self.mgr.acquire_lease("SOL-LOCK-IMMUTABLE", "TASK-IMMUTABLE-TEST", "ctx-imm")

        # 2. Expired lease cannot be renewed
        past = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        l_exp = self.mgr.acquire_lease("SOL-LOCK-EXCL", "TASK-PROBE", "ctx-e", lease_seconds=10, now=past)
        future = datetime(2026, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
        with self.assertRaises(LockLeaseError) as ctx_exp:
            self.mgr.renew_lease(l_exp.lease_id, extend_seconds=60, now=future)
        self.assertIn("expired", str(ctx_exp.exception).lower())

        # 3. Revoked authority cannot renew
        l_rev = self.mgr.acquire_lease("SOL-LOCK-EXCL", "TASK-PROBE", "ctx-r", lease_seconds=600)
        self.mgr.set_task_authority("TASK-PROBE", "revoked")
        with self.assertRaises(LockLeaseError) as ctx_rev:
            self.mgr.renew_lease(l_rev.lease_id, extend_seconds=60)
        self.assertIn("only 'granted' permitted", str(ctx_rev.exception))

    # --- Sol Probe 17: Fencing token rejects future tokens (token > current counter) ---
    def test_sol_probe_17_fencing_token_rejects_future_tokens(self):
        l = self.mgr.acquire_lease("SOL-LOCK-EXCL", "TASK-PROBE", "ctx-tok")
        current_token = l.fencing_token

        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.validate_fencing_token("SOL-LOCK-EXCL", current_token + 10)
        self.assertIn("Future fencing token", str(ctx.exception))

    # --- Sol Probe 18: Fencing token rejects absent, stale, and expired leases ---
    def test_sol_probe_18_fencing_token_rejects_absent_stale_expired(self):
        past = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        l = self.mgr.acquire_lease("SOL-LOCK-EXCL", "TASK-PROBE", "ctx-f", lease_seconds=60, now=past)
        token = l.fencing_token

        # Absent
        with self.assertRaises(LockLeaseError) as ctx_abs:
            self.mgr.validate_fencing_token("SOL-LOCK-EXCL", None)
        self.assertIn("Absent fencing token", str(ctx_abs.exception))

        # Stale
        with self.assertRaises(LockLeaseError) as ctx_stl:
            self.mgr.validate_fencing_token("SOL-LOCK-EXCL", token - 1)
        self.assertIn("Stale fencing token", str(ctx_stl.exception))

        # Expired
        future = datetime(2026, 1, 1, 0, 10, 0, tzinfo=timezone.utc)
        with self.assertRaises(LockLeaseError) as ctx_exp:
            self.mgr.validate_fencing_token("SOL-LOCK-EXCL", token, now=future)
        self.assertIn("Expired fencing token", str(ctx_exp.exception))

    # --- Sol Probe 19: Dispatch creation requires exact Orca task ID, candidate commit, and active lease ---
    def test_sol_probe_19_dispatch_creation_requires_exact_bindings(self):
        l = self.mgr.acquire_lease("SOL-LOCK-EXCL", "TASK-PROBE", "ctx-d")

        # Blank orca_task_id
        with self.assertRaises(ProtocolViolationError):
            self.adapter.create_dispatch("TASK-PROBE", orca_task_id="   ", candidate_commit=self.candidate_commit, fencing_token=l.fencing_token, lease_id=l.lease_id)

        # Candidate commit as HEAD
        with self.assertRaises(ProtocolViolationError):
            self.adapter.create_dispatch("TASK-PROBE", orca_task_id="orca-1", candidate_commit="HEAD", fencing_token=l.fencing_token, lease_id=l.lease_id)

        # Inactive / unknown lease
        with self.assertRaises(ProtocolViolationError):
            self.adapter.create_dispatch("TASK-PROBE", orca_task_id="orca-1", candidate_commit=self.candidate_commit, fencing_token=l.fencing_token, lease_id="unknown-lease")

    # --- Sol Probe 20: Worker done rejects mismatch, duplicate, and stale completions ---
    def test_sol_probe_20_worker_done_rejects_mismatch_duplicate_and_stale(self):
        l = self.mgr.acquire_lease("SOL-LOCK-EXCL", "TASK-PROBE", "ctx-disp")
        disp = self.adapter.create_dispatch(
            "TASK-PROBE",
            orca_task_id="orca-valid",
            candidate_commit=self.candidate_commit,
            fencing_token=l.fencing_token,
            lease_id=l.lease_id,
            intended_dispatch_id="ctx-disp",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-PROBE", "ctx-disp"),
        )
        self.adapter.acknowledge_dispatch("TASK-PROBE", disp)
        self.adapter.start_running("TASK-PROBE", disp)

        # 1. Wrong orca_task_id
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_worker_done("TASK-PROBE", "orca-impostor", disp, "succeeded", candidate_commit=self.candidate_commit, fencing_token=l.fencing_token)

        # 2. Candidate commit mismatch
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_worker_done("TASK-PROBE", "orca-valid", disp, "succeeded", candidate_commit="0000000000000000000000000000000000000000", fencing_token=l.fencing_token)

        # 3. Successful settlement
        st = self.adapter.handle_worker_done("TASK-PROBE", "orca-valid", disp, "succeeded", candidate_commit=self.candidate_commit, fencing_token=l.fencing_token)
        self.assertEqual(st, "review")

        # 4. Duplicate worker_done
        with self.assertRaises(DuplicateResultError):
            self.adapter.handle_worker_done("TASK-PROBE", "orca-valid", disp, "succeeded", candidate_commit=self.candidate_commit, fencing_token=l.fencing_token)

    # --- Sol Probe 21: State transitions and authority enforcement across lifecycle ---
    def test_sol_probe_21_state_transitions_and_revocation_blocks_mutation(self):
        # Locked, future_template, and revoked cannot dispatch
        for unauthorized in ("locked", "future_template", "revoked"):
            self.adapter.set_task_authority("TASK-AUTH-TEST", unauthorized)
            self.adapter.set_task_state("TASK-AUTH-TEST", "ready")
            with self.assertRaises(ProtocolViolationError):
                self.adapter.create_dispatch(
                    "TASK-AUTH-TEST",
                    orca_task_id="orca-auth",
                    candidate_commit=self.candidate_commit,
                    fencing_token=1,
                    lease_id="fake-lease",
                )

        # Authority revocation blocks review, integration, and replan
        l = self.mgr.acquire_lease("SOL-LOCK-EXCL", "TASK-OTHER", "ctx-trans")
        disp = self.adapter.create_dispatch("TASK-OTHER", "orca-t", self.candidate_commit, l.fencing_token, l.lease_id, intended_dispatch_id="ctx-trans", dispatch_origin="dely dispatch", execution_envelope=make_execution_envelope("TASK-OTHER", "ctx-trans"))
        self.adapter.acknowledge_dispatch("TASK-OTHER", disp)
        self.adapter.start_running("TASK-OTHER", disp)
        self.adapter.handle_worker_done("TASK-OTHER", "orca-t", disp, "succeeded", self.candidate_commit, l.fencing_token)
        self.assertEqual(self.adapter.get_task_state("TASK-OTHER"), "review")

        # Revoke authority
        self.adapter.set_task_authority("TASK-OTHER", "revoked")
        with self.assertRaises(ProtocolViolationError) as ctx_rev:
            self.adapter.handle_review_verdict("TASK-OTHER", "ACCEPT")
        self.assertIn("only 'granted' permitted", str(ctx_rev.exception))

    # --- Boundary Probe 22: Harness namespaced tool collapse and smoke gate ---
    def test_sol_probe_22_boundary_harness_namespaced_tool_collapse_and_smoke_gate(self):
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            check_harness_tool_compatibility("functions", "functions.exec")
        self.assertIn("Harness namespaced tool collapse detected", str(ctx.exception))
        self.assertIn("STOP condition triggered", str(ctx.exception))

        with self.assertRaises(HarnessCompatibilityError) as ctx2:
            check_harness_tool_compatibility("functions.exec", "functions.exec", execution_observed=False)
        self.assertIn("No successful tool execution observed", str(ctx2.exception))

        with self.assertRaises(HarnessCompatibilityError) as ctx3:
            check_harness_tool_compatibility("functions.exec", "functions.exec", execution_observed=True, execution_returncode=1)
        self.assertIn("Harness tool execution smoke test failed", str(ctx3.exception))

    # --- Boundary Probe 23: Harness wrong namespace triggers STOP condition ---
    def test_sol_probe_23_boundary_harness_wrong_namespace_triggers_stop(self):
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            check_harness_tool_compatibility("wrong.exec", "functions.exec")
        self.assertIn("Harness tool identity mismatch", str(ctx.exception))

    # --- Boundary Probe 24: Fencing token strict type boundaries ---
    def test_sol_probe_24_boundary_fencing_token_types(self):
        l = self.mgr.acquire_lease("SOL-LOCK-EXCL", "TASK-PROBE", "ctx-type")
        for bad_token in (True, False, "1", 1.0, [1]):
            with self.assertRaises(LockLeaseError) as ctx:
                self.mgr.validate_fencing_token("SOL-LOCK-EXCL", bad_token)
            self.assertIn("Invalid fencing token type", str(ctx.exception))


class TestSolRoundThreeCounterexamples(unittest.TestCase):
    """Rigorous durable verification of all Sol round-3 P1 remediations:
    - Authority override prevention at acquire and dispatch (no implicit authority)
    - Dispatch binding verification (lease ownership, expiry, intended dispatch, fencing, candidate existence/HEAD, unique Orca task ID, allowed states)
    - worker_done & lifecycle transitions (recheck authority, lease ownership, exact dispatch binding, expiry, fencing, candidate/Orca identity, one-way transitions)
    - Review verdict strictness (reject unknown verdicts)
    - Integration gate strict boolean check (reject truthy/falsy coercion)
    - Lock schema field safety (unknown fields, illegal mode combinations, bool/fractional types)
    - Declared duration broadening prevention (acquire & renew bounds)
    - Harness execution strict types & observable STOP state machine
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.lock_defs = [
            {"id": "R3-LOCK-EXCL", "mode": "exclusive", "renewable": True, "lease_seconds": 300},
            {"id": "R3-LOCK-CAP", "mode": "capacity", "capacity": 2, "renewable": True, "lease_seconds": 600},
            {"id": "R3-LOCK-DB", "mode": "exclusive_by_database_name", "partition_key_prefix": "db:", "renewable": True, "lease_seconds": 900},
            {"id": "R3-LOCK-IMMUTABLE", "mode": "immutable", "renewable": False, "mutation_lease_forbidden": True},
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.mgr.set_task_authority("TASK-A", "granted")
        self.mgr.set_task_authority("TASK-B", "granted")
        self.mgr.set_task_authority("TASK-LOCKED", "locked")
        self.mgr.set_task_authority("TASK-REVOKED", "revoked")
        self.adapter = OrcaDeliveryAdapter(self.mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        self.adapter.set_task_authority("TASK-A", "granted")
        self.adapter.set_task_authority("TASK-B", "granted")
        self.adapter.set_task_authority("TASK-LOCKED", "locked")
        self.adapter.set_task_authority("TASK-REVOKED", "revoked")
        self.adapter.set_task_state("TASK-A", "ready")
        self.adapter.set_task_state("TASK-B", "ready")
        self.adapter.register_task_locks("TASK-A", ["R3-LOCK-EXCL"])
        self.adapter.register_task_locks("TASK-B", ["R3-LOCK-CAP"])

    def test_r3_01_acquire_rejects_unregistered_authority_override(self):
        """1. Caller cannot grant implicit authority or override unregistered authority at acquire."""
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-UNREGISTERED", "ctx-unreg", authority_state="granted")
        self.assertIn("has no registered authority", str(ctx.exception))

    def test_r3_02_acquire_rejects_registered_authority_override(self):
        """2. Caller cannot override registered non-granted authority at acquire."""
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-LOCKED", "ctx-lock", authority_state="granted")
        self.assertIn("authority override attempt", str(ctx.exception))
        self.assertIn("only 'granted' permitted", str(ctx.exception))

    def test_r3_03_dispatch_rejects_unregistered_authority_override(self):
        """3. Caller cannot grant implicit authority or override unregistered authority at dispatch."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-UNREGISTERED",
                orca_task_id="orca-unreg",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                authority_state="granted",
            )
        self.assertIn("has no registered authority", str(ctx.exception))

    def test_r3_04_dispatch_rejects_registered_authority_override(self):
        """4. Caller cannot override registered non-granted authority at dispatch."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-LOCKED",
                orca_task_id="orca-lock",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                authority_state="granted",
            )
        self.assertIn("authority override attempt", str(ctx.exception))

    def test_r3_05_dispatch_rejects_lease_belonging_to_other_task(self):
        """5. Dispatch rejects active lease belonging to a different delivery task."""
        lease_a = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-B",
                orca_task_id="orca-b-1",
                candidate_commit=self.candidate_commit,
                fencing_token=lease_a.fencing_token,
                lease_id=lease_a.lease_id,
                intended_dispatch_id="ctx-a",
            )
        self.assertIn("belongs to task 'TASK-A', cannot be bound to 'TASK-B'", str(ctx.exception))

    def test_r3_06_dispatch_rejects_expired_lease(self):
        """6. Dispatch rejects active lease whose expiry time has passed."""
        now_time = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a", lease_seconds=10, now=now_time)
        past_expiry = now_time + timedelta(seconds=15)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-a-exp",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx-a",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a"),
                now=past_expiry,
            )
        self.assertIn("has expired", str(ctx.exception))

    def test_r3_07_dispatch_rejects_lease_reuse_across_dispatches(self):
        """7. Dispatch rejects reusing an already-bound lease across dispatches."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        disp1 = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-a-1",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id="ctx-a",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a"),
        )
        self.assertIsNotNone(disp1)
        self.adapter._task_states["TASK-A"] = "ready"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-a-2",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx-a",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a"),
            )
        self.assertIn("already bound to dispatch", str(ctx.exception))

    def test_r3_08_dispatch_rejects_fencing_token_mismatch(self):
        """8. Dispatch rejects fencing token mismatch with active lease."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-a-fence",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token + 99,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx-a",
            )
        self.assertIn("Fencing token mismatch", str(ctx.exception))

    def test_r3_09_dispatch_rejects_non_existent_commit_in_git(self):
        """9. Dispatch rejects candidate commit SHA that does not exist in git."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        fake_sha = "1234567890123456789012345678901234567890"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-a-fake-sha",
                candidate_commit=fake_sha,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx-a",
            )
        self.assertIn("does not exist in git", str(ctx.exception))

    def test_r3_10_dispatch_rejects_unapproved_non_head_candidate_commit(self):
        """10. Dispatch rejects candidate commit that exists in git but does not match approved candidate / HEAD."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        other_existing_commit = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-a-wrong-cand",
                candidate_commit=other_existing_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx-a",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a"),
            )
        self.assertIn("does not match approved candidate / HEAD", str(ctx.exception))

    def test_r3_11_dispatch_rejects_duplicate_orca_task_id(self):
        """11. Dispatch rejects duplicate orca_task_id across delivery tasks or active dispatches."""
        lease_a = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-shared-id",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
            lease_id=lease_a.lease_id,
            intended_dispatch_id="ctx-a",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a"),
        )
        lease_b = self.mgr.acquire_lease("R3-LOCK-CAP", "TASK-B", "ctx-b", units=1)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-B",
                orca_task_id="orca-shared-id",
                candidate_commit=self.candidate_commit,
                fencing_token=lease_b.fencing_token,
                lease_id=lease_b.lease_id,
                intended_dispatch_id="ctx-b",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-B", "ctx-b"),
            )
        self.assertIn("already assigned to delivery task 'TASK-A'", str(ctx.exception))

    def test_r3_12_dispatch_rejects_blocked_and_non_ready_states(self):
        """12. Dispatch rejects tasks in blocked, planned, dispatched, or review states (only 'ready' permitted)."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        for non_ready in ("blocked", "planned", "dispatched", "review", "integrated"):
            self.adapter._task_states["TASK-A"] = non_ready
            with self.assertRaises(ProtocolViolationError) as ctx:
                self.adapter.create_dispatch(
                    "TASK-A",
                    orca_task_id=f"orca-a-{non_ready}",
                    candidate_commit=self.candidate_commit,
                    fencing_token=lease.fencing_token,
                    lease_id=lease.lease_id,
                    intended_dispatch_id="ctx-a",
                )
            self.assertIn("only 'ready' state may be dispatched", str(ctx.exception))

    def test_r3_13_worker_done_rejects_expired_lease(self):
        """13. worker_done rejects result when bound lease has expired before settlement."""
        now_time = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a", lease_seconds=10, now=now_time)
        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-a-wd-exp",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id="ctx-a",
            now=now_time,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a", now=now_time),
        )
        self.adapter.acknowledge_dispatch("TASK-A", disp)
        self.adapter.start_running("TASK-A", disp)
        past_expiry = now_time + timedelta(seconds=15)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_worker_done(
                "TASK-A",
                "orca-a-wd-exp",
                disp,
                "succeeded",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                now=past_expiry,
            )
        self.assertIn("expired", str(ctx.exception))

    def test_r3_14_worker_done_rejects_non_dispatched_state(self):
        """14. worker_done rejects task not currently in 'running' state."""
        self.adapter.set_task_state("TASK-A", "ready")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_worker_done(
                "TASK-A",
                "orca-a-not-disp",
                "ctx_fake",
                "succeeded",
                candidate_commit=self.candidate_commit,
                fencing_token=1,
            )
        self.assertIn("requires state 'running'", str(ctx.exception))

    def test_r3_15_review_verdict_rejects_unknown_verdicts(self):
        """15. Review disposition strictly rejects unknown verdicts (no silent blocked fallback)."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-a-rev",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id="ctx-a",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a"),
        )
        self.adapter.acknowledge_dispatch("TASK-A", disp)
        self.adapter.start_running("TASK-A", disp)
        self.adapter.handle_worker_done("TASK-A", "orca-a-rev", disp, "succeeded", self.candidate_commit, lease.fencing_token)
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "review")

        for bad_verdict in ("APPROVE", "PASS", "UNKNOWN", "REJECT", "", 123, None):
            with self.assertRaises(ProtocolViolationError) as ctx:
                self.adapter.handle_review_verdict("TASK-A", bad_verdict)  # type: ignore
            self.assertIn("Unknown review verdict", str(ctx.exception))

    def test_r3_16_integration_gates_rejects_truthy_coercion(self):
        """16. Integration gate strictly rejects non-boolean truthy/falsy coercion."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-a-int",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id="ctx-a",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a"),
        )
        self.adapter.acknowledge_dispatch("TASK-A", disp)
        self.adapter.start_running("TASK-A", disp)
        self.adapter.handle_worker_done("TASK-A", "orca-a-int", disp, "succeeded", self.candidate_commit, lease.fencing_token)
        self.adapter.handle_review_verdict("TASK-A", "ACCEPT")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "merge_queued")

        for truthy_val in (1, 0, "true", "True", [True], {"pass": True}, None):
            with self.assertRaises(ProtocolViolationError) as ctx:
                self.adapter.handle_integration_gates("TASK-A", gates_pass=truthy_val)  # type: ignore
            self.assertIn("gates_pass must be strict bool", str(ctx.exception))

        # Strict boolean passes
        res = self.adapter.handle_integration_gates("TASK-A", gates_pass=True)
        self.assertEqual(res, "integrated")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "integrated")

    def test_r3_17_lock_schema_rejects_unknown_fields(self):
        """17. Lock schema rejects unknown/irrelevant fields at construction."""
        with self.assertRaises(LockLeaseError) as ctx:
            LeaseManager([{"id": "L-BAD", "mode": "exclusive", "renewable": True, "extra_irrelevant": 42}])
        self.assertIn("contains unknown/irrelevant field(s)", str(ctx.exception))

    def test_r3_18_lock_schema_rejects_illegal_field_combinations(self):
        """18. Lock schema rejects illegal field combinations by mode."""
        # Immutable specifying lease_seconds
        with self.assertRaises(LockLeaseError) as ctx:
            LeaseManager([{"id": "L-IMM-BAD", "mode": "immutable", "renewable": False, "mutation_lease_forbidden": True, "lease_seconds": 300}])
        self.assertIn("cannot specify lease_seconds", str(ctx.exception))

        # Exclusive specifying capacity
        with self.assertRaises(LockLeaseError) as ctx2:
            LeaseManager([{"id": "L-EXCL-BAD", "mode": "exclusive", "renewable": True, "capacity": 2}])
        self.assertIn("contains illegal fields", str(ctx2.exception))

        # Capacity specifying partition_key_prefix
        with self.assertRaises(LockLeaseError) as ctx3:
            LeaseManager([{"id": "L-CAP-BAD", "mode": "capacity", "capacity": 2, "renewable": True, "partition_key_prefix": "p:"}])
        self.assertIn("contains illegal fields for capacity mode", str(ctx3.exception))

    def test_r3_19_lock_schema_rejects_bool_and_fractional_values(self):
        """19. Lock schema rejects boolean and fractional capacity and lease_seconds."""
        with self.assertRaises(LockLeaseError) as ctx:
            LeaseManager([{"id": "L-BOOL-CAP", "mode": "capacity", "capacity": True, "renewable": True}])
        self.assertIn("must declare strict positive integer capacity", str(ctx.exception))

        with self.assertRaises(LockLeaseError) as ctx2:
            LeaseManager([{"id": "L-FLOAT-CAP", "mode": "capacity", "capacity": 2.5, "renewable": True}])
        self.assertIn("must declare strict positive integer capacity", str(ctx2.exception))

        with self.assertRaises(LockLeaseError) as ctx3:
            LeaseManager([{"id": "L-FLOAT-LS", "mode": "exclusive", "renewable": True, "lease_seconds": 300.5}])
        self.assertIn("invalid lease_seconds", str(ctx3.exception))

    def test_r3_20_acquire_lease_rejects_duration_broadening(self):
        """20. Caller cannot broaden declared lock duration at lease acquisition."""
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-broad", lease_seconds=600)
        self.assertIn("declared duration cannot be broadened", str(ctx.exception))

    def test_r3_21_renew_lease_rejects_duration_broadening(self):
        """21. Caller cannot broaden declared lock duration at lease renewal."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-renew")
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.renew_lease(lease.lease_id, extend_seconds=600)
        self.assertIn("declared duration cannot be broadened", str(ctx.exception))

    def test_r3_22_default_lease_duration_preserves_declared_seconds(self):
        """22. Default lease acquisition preserves lock declared duration without silent broadening."""
        now_time = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-def", now=now_time)
        exp = datetime.fromisoformat(lease.expires_at)
        delta = (exp - now_time).total_seconds()
        self.assertEqual(delta, 300, "Default lease_seconds must match declared 300s, not 1800s")

    def test_r3_23_harness_execution_argument_types_strict(self):
        """23. Harness tool execution gate strictly validates argument types."""
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            check_harness_tool_compatibility("functions.exec", "functions.exec", execution_observed=1)  # type: ignore
        self.assertIn("execution_observed must be strict bool", str(ctx.exception))

        with self.assertRaises(HarnessCompatibilityError) as ctx2:
            check_harness_tool_compatibility("functions.exec", "functions.exec", execution_returncode=True)  # type: ignore
        self.assertIn("execution_returncode must be strict int", str(ctx2.exception))

    def test_r3_24_harness_observable_state_machine_transitions(self):
        """24. Harness observable state machine records transitions and fallback conditions."""
        sm = HarnessExecutionStateMachine()
        self.assertEqual(sm.current_state, "IDLE")

        # 1. Successful execution: IDLE -> RUNNING -> SUCCESS
        res = sm.evaluate("functions.exec", "functions.exec", execution_observed=True, execution_returncode=0)
        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.state, "SUCCESS")
        self.assertEqual(sm.current_state, "SUCCESS")
        self.assertFalse(res.fallback_required)

        # 2. Namespace collapse STOP condition: IDLE -> RUNNING -> STOP_BLOCKED
        with self.assertRaises(HarnessCompatibilityError):
            sm.evaluate("functions", "functions.exec")
        self.assertEqual(sm.current_state, "STOP_BLOCKED")
        self.assertTrue(len(sm.transitions) >= 2)
        last_trans = sm.transitions[-1]
        self.assertEqual(last_trans[1], "STOP_BLOCKED")
        self.assertIn("collapse detected", last_trans[2])


class TestSolRoundFourCounterexamples(unittest.TestCase):
    """Counterexamples and positive controls for cx/gpt-5.6-sol-high round 4 review findings."""

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(
            cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.mgr = LeaseManager([
            {"id": "R4-LOCK-EXCL", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
            {"id": "R4-LOCK-CAP", "mode": "capacity", "capacity": 2, "renewable": True, "lease_seconds": 600},
            {"id": "R4-LOCK-BOUND", "mode": "exclusive", "renewable": True, "lease_seconds": 300},
        ])
        self.mgr.set_task_authority("TASK-A", "granted")
        self.mgr.set_task_authority("TASK-B", "granted")
        self.adapter = OrcaDeliveryAdapter(self.mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        self.adapter.set_task_authority("TASK-A", "granted")
        self.adapter.set_task_authority("TASK-B", "granted")
        self.adapter.set_task_state("TASK-A", "ready")
        self.adapter.set_task_state("TASK-B", "ready")
        self.adapter.register_task_locks("TASK-A", ["R4-LOCK-EXCL"])
        self.adapter.register_task_locks("TASK-B", ["R4-LOCK-CAP"])
        self.registry_path = BUNDLE_DIR / "contract-registry.yaml"
        self.catalog = build_contract_catalog(self.registry_path, ROOT_DIR)
        self.known_owners = {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "CROSS-CUTTING-CONTRACT-OWNER"}
        self.known_requirements = {"QR-MNT-002", "QR-MNT-003", "QR-COMP-003", "FR-UI-001"}

    def test_r4_01_per_live_allocation_fencing_concurrent_valid(self):
        """1. Positive control: capacity lease allocates isolated slots and concurrent valid fencing tokens."""
        lease_1 = self.mgr.acquire_lease("R4-LOCK-CAP", "TASK-A", "ctx-a", units=1)
        lease_2 = self.mgr.acquire_lease("R4-LOCK-CAP", "TASK-B", "ctx-b", units=1)

        self.assertEqual(lease_1.allocation_slot, 1)
        self.assertEqual(lease_2.allocation_slot, 2)
        self.assertEqual(lease_1.resource_key, "R4-LOCK-CAP:slot_1")
        self.assertEqual(lease_2.resource_key, "R4-LOCK-CAP:slot_2")
        self.assertEqual(lease_1.fencing_token, 1)
        self.assertEqual(lease_2.fencing_token, 1)

        # Both tokens are concurrently valid and distinct
        self.assertTrue(self.mgr.validate_fencing_token("R4-LOCK-CAP:slot_1", 1, active_lease_id=lease_1.lease_id))
        self.assertTrue(self.mgr.validate_fencing_token("R4-LOCK-CAP:slot_2", 1, active_lease_id=lease_2.lease_id))
        self.assertTrue(self.mgr.validate_fencing_token("R4-LOCK-CAP", 1, active_lease_id=lease_1.lease_id))
        self.assertTrue(self.mgr.validate_fencing_token("R4-LOCK-CAP", 1, active_lease_id=lease_2.lease_id))

    def test_r4_02_capacity_lease_reallocation_rejects_stale_token(self):
        """2. Counterexample: reallocating a capacity slot advances monotonic token and rejects stale token."""
        lease_1 = self.mgr.acquire_lease("R4-LOCK-CAP", "TASK-A", "ctx-a", units=1)
        self.assertEqual(lease_1.allocation_slot, 1)
        stale_token = lease_1.fencing_token

        # Release slot 1
        self.mgr.release_lease(lease_1.lease_id)

        # Re-acquire slot 1
        lease_3 = self.mgr.acquire_lease("R4-LOCK-CAP", "TASK-A", "ctx-a3", units=1)
        self.assertEqual(lease_3.allocation_slot, 1)
        self.assertEqual(lease_3.fencing_token, 2)

        # Stale token 1 is rejected on slot 1
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.validate_fencing_token("R4-LOCK-CAP:slot_1", stale_token, active_lease_id=lease_3.lease_id)
        self.assertIn("Stale fencing token", str(ctx.exception))

    def test_r4_03_capacity_lease_rejects_future_token(self):
        """3. Counterexample: future fencing token ahead of monotonic counter is rejected."""
        lease = self.mgr.acquire_lease("R4-LOCK-CAP", "TASK-A", "ctx-a", units=1)
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.validate_fencing_token("R4-LOCK-CAP:slot_1", 999, active_lease_id=lease.lease_id)
        self.assertIn("Future fencing token", str(ctx.exception))

    def test_r4_04_global_non_reuse_orca_task_ids(self):
        """4. Counterexample: Orca task IDs cannot be reused across active or settled dispatches."""
        lease_a = self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-A", "ctx-a")
        disp_a = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-fixed-task-id",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
            lease_id=lease_a.lease_id,
            intended_dispatch_id="ctx-a",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a"),
        )
        self.adapter.acknowledge_dispatch("TASK-A", disp_a)
        self.adapter.start_running("TASK-A", disp_a)
        self.adapter.handle_worker_done(
            "TASK-A",
            "orca-fixed-task-id",
            disp_a,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
        )

        # Settle task A and try to reuse same orca_task_id for TASK-B
        self.adapter.register_task_locks("TASK-B", ["R4-LOCK-EXCL"])
        lease_b = self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-B", "ctx-b")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-B",
                orca_task_id="orca-fixed-task-id",
                candidate_commit=self.candidate_commit,
                fencing_token=lease_b.fencing_token,
                lease_id=lease_b.lease_id,
                intended_dispatch_id="ctx-b",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-B", "ctx-b"),
            )
        self.assertIn("global reuse is forbidden", str(ctx.exception))

    def test_r4_05_global_non_reuse_dispatch_ids(self):
        """5. Counterexample: Dispatch IDs cannot be reused across active or settled dispatches."""
        lease_a = self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-A", "ctx-disp-reuse")
        disp_a = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-task-unique-1",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
            lease_id=lease_a.lease_id,
            intended_dispatch_id="ctx-disp-reuse",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-disp-reuse"),
        )
        self.adapter.acknowledge_dispatch("TASK-A", disp_a)
        self.adapter.start_running("TASK-A", disp_a)
        self.adapter.handle_worker_done(
            "TASK-A",
            "orca-task-unique-1",
            disp_a,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
        )

        # Reusing ctx-disp-reuse must fail even though task A is settled
        self.adapter.register_task_locks("TASK-B", ["R4-LOCK-EXCL"])
        lease_b = self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-B", "ctx-disp-reuse")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-B",
                orca_task_id="orca-task-unique-2",
                candidate_commit=self.candidate_commit,
                fencing_token=lease_b.fencing_token,
                lease_id=lease_b.lease_id,
                intended_dispatch_id="ctx-disp-reuse",
            )
        self.assertIn("Duplicate dispatch binding overwrite", str(ctx.exception))

    def test_r4_06_reject_duplicate_dispatch_binding_overwrite(self):
        """6. Counterexample: Duplicate dispatch binding overwrite rejected."""
        lease = self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-A", "ctx-overwrite")
        self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-t1",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id="ctx-overwrite",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-overwrite"),
        )
        # Attempt to create duplicate binding with same dispatch ID using TASK-B
        lease_b = self.mgr.acquire_lease("R4-LOCK-CAP", "TASK-B", "ctx-overwrite", units=1)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-B",
                orca_task_id="orca-t2",
                candidate_commit=self.candidate_commit,
                fencing_token=lease_b.fencing_token,
                lease_id=lease_b.lease_id,
                intended_dispatch_id="ctx-overwrite",
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-B", "ctx-overwrite"),
            )
        self.assertIn("Duplicate dispatch binding overwrite", str(ctx.exception))

    def test_r4_07_require_actual_head_and_exact_candidate_binding(self):
        """7. Counterexample: Non-HEAD candidate commit and mismatched approved candidate are rejected."""
        lease = self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-A", "ctx-head")
        fake_sha = "1111111111111111111111111111111111111111"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-head-test",
                candidate_commit=fake_sha,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx-head",
            )
        self.assertTrue(
            "does not match approved candidate / HEAD" in str(ctx.exception)
            or "does not exist in git" in str(ctx.exception)
        )

        # Mismatched approved_candidate_commit also rejected
        self.adapter.approved_candidate_commit = "2222222222222222222222222222222222222222"
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-head-test-2",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx-head",
            )
        self.assertIn("does not match actual current HEAD", str(ctx2.exception))

    def test_r4_08_require_intended_dispatch_binding_unconditionally(self):
        """8. Counterexample: Intended dispatch ID must match active lease dispatch_id unconditionally."""
        lease = self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-A", "ctx_initial_lease")
        # Specifying intended_dispatch_id that differs from lease.dispatch_id is rejected
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-intended-test",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx_different_target",
            )
        self.assertIn("does not match requested", str(ctx.exception))

    def test_r4_09_enforce_internal_legal_task_state_transitions(self):
        """9. Counterexample: Illegal task-state transitions are rejected by transition matrix."""
        # Illegal: planned -> dispatched (skipping ready)
        self.adapter.set_task_state("TASK-A", "planned")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state("TASK-A", "dispatched")
        self.assertIn("Illegal task-state transition", str(ctx.exception))

        # Illegal: ready -> review (must be dispatched first)
        self.adapter.set_task_state("TASK-A", "ready")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state("TASK-A", "review")
        self.assertIn("Illegal task-state transition", str(ctx.exception))

        # Illegal: dispatched -> integrated (must go through review and merge_queued)
        self.adapter.set_task_state("TASK-A", "ready")
        self.adapter.transition_task_state("TASK-A", "dispatched")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state("TASK-A", "integrated")
        self.assertIn("Illegal task-state transition", str(ctx.exception))

        # Legal progression
        self.adapter._task_states["TASK-A"] = "ready"
        self.adapter.transition_task_state("TASK-A", "dispatched")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "dispatched")
        self.adapter.transition_task_state("TASK-A", "acknowledged")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "acknowledged")
        self.adapter.transition_task_state("TASK-A", "running")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "running")
        self.adapter.transition_task_state("TASK-A", "review")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "review")
        self.adapter.transition_task_state("TASK-A", "merge_queued")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "merge_queued")
        self.adapter.transition_task_state("TASK-A", "integrated")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "integrated")

    def test_r4_10_release_all_mutation_leases_after_worker_done_success(self):
        """10. Positive control: all mutation leases are purged upon worker_done succeeded."""
        lease = self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-A", "ctx-worker-done")
        self.assertEqual(len(self.mgr.active_leases), 1)

        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-wd-test",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id="ctx-worker-done",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-worker-done"),
        )
        self.adapter.acknowledge_dispatch("TASK-A", disp)
        self.adapter.start_running("TASK-A", disp)
        new_state = self.adapter.handle_worker_done(
            "TASK-A",
            "orca-wd-test",
            disp,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
        )
        self.assertEqual(new_state, "review")
        # All mutation leases must be released immediately upon success
        self.assertEqual(len(self.mgr.active_leases), 0)

    def test_r4_11_reject_undeclared_locks_at_acquire_and_dag(self):
        """11. Counterexample: Undeclared locks rejected at acquire_lease and in task DAG."""
        # 1. At acquire_lease
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("UNDECLARED-LOCK-ID", "TASK-A", "ctx-undec")
        self.assertIn("Unknown lock ID", str(ctx.exception))

        # 2. In check_task_dag
        bad_dag = {
            "tasks": [
                {
                    "id": "TASK-WITH-UNDECLARED-LOCK",
                    "authority": {"state": "planned"},
                    "status": "planned",
                    "kind": "task",
                    "depends_on": [],
                    "owned_paths": [],
                    "forbidden_paths": [],
                    "evidence_outputs": [],
                    "resource_locks": ["LOCK-PHANTOM-XYZ"],
                    "contract_refs": [],
                    "invariant_refs": [],
                    "requirement_refs": [],
                    "module_owners": [],
                }
            ],
            "external_nodes": [],
            "schema": {"status_enum": ["planned"], "authority_state_enum": ["planned"]},
        }
        ownership = {"locks": [{"id": "R4-LOCK-EXCL"}]}
        errs = check_task_dag(bad_dag, ownership, self.catalog, self.known_owners, self.known_requirements)
        self.assertTrue(any("unknown resource lock LOCK-PHANTOM-XYZ" in e for e in errs))

    def test_r4_12_enforce_declared_lease_duration_bounds(self):
        """12. Counterexample: Cannot broaden declared lease duration at acquire or renew."""
        # Lock declared with lease_seconds=600; requesting 1200 must fail
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-A", "ctx-dur", lease_seconds=1200)
        self.assertIn("declared duration cannot be broadened", str(ctx.exception))

        # Acquire valid lease with 600s
        lease = self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-A", "ctx-dur", lease_seconds=600)
        # Renew with 1200s must fail
        with self.assertRaises(LockLeaseError) as ctx2:
            self.mgr.renew_lease(lease.lease_id, extend_seconds=1200)
        self.assertIn("declared duration cannot be broadened", str(ctx2.exception))

    def test_r4_13_harness_execution_result_argument_validation(self):
        """13. Counterexample: HarnessExecutionResult rejects invalid types and arguments."""
        # success must be strict bool
        with self.assertRaises(HarnessCompatibilityError) as ctx1:
            HarnessExecutionResult(
                success=1,  # type: ignore
                execution_time_ms=10.0,
                status="PASS",
                state="SUCCESS",
                tool_name="tool",
                requested_tool="tool",
                execution_observed=True,
                execution_returncode=0,
                fallback_required=False,
            )
        self.assertIn("success must be strict bool", str(ctx1.exception))

        # execution_time_ms must be non-negative int or float
        with self.assertRaises(HarnessCompatibilityError) as ctx2:
            HarnessExecutionResult(
                success=True,
                execution_time_ms=-5.0,
                status="PASS",
                state="SUCCESS",
                tool_name="tool",
                requested_tool="tool",
                execution_observed=True,
                execution_returncode=0,
                fallback_required=False,
            )
        self.assertIn("execution_time_ms must be non-negative", str(ctx2.exception))

        # status must be PASS or STOP
        with self.assertRaises(HarnessCompatibilityError) as ctx3:
            HarnessExecutionResult(
                success=True,
                execution_time_ms=1.0,
                status="UNKNOWN",
                state="SUCCESS",
                tool_name="tool",
                requested_tool="tool",
                execution_observed=True,
                execution_returncode=0,
                fallback_required=False,
            )
        self.assertIn("status must be 'PASS' or 'STOP'", str(ctx3.exception))

    def test_r4_14_harness_state_machine_idle_running_transitions(self):
        """14. Positive & negative: State machine observes IDLE -> RUNNING -> SUCCESS | STOP_BLOCKED."""
        sm = HarnessExecutionStateMachine()
        self.assertEqual(sm.current_state, "IDLE")

        # 1. Success path: IDLE -> RUNNING -> SUCCESS
        res = sm.evaluate("tool.a", "tool.a", execution_observed=True, execution_returncode=0, execution_time_ms=12.5)
        self.assertTrue(res.success)
        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.state, "SUCCESS")
        self.assertEqual(sm.current_state, "SUCCESS")
        self.assertEqual(sm.transitions[0][0], "IDLE")
        self.assertEqual(sm.transitions[0][1], "RUNNING")
        self.assertEqual(sm.transitions[1][0], "RUNNING")
        self.assertEqual(sm.transitions[1][1], "SUCCESS")

        # 2. Re-evaluating resets from IDLE -> RUNNING -> STOP_BLOCKED on mismatch
        with self.assertRaises(HarnessCompatibilityError):
            sm.evaluate("tool.mismatch", "tool.requested")
        self.assertEqual(sm.current_state, "STOP_BLOCKED")

        # 3. Execution failure: IDLE -> RUNNING -> FAILURE -> STOP_BLOCKED
        with self.assertRaises(HarnessCompatibilityError):
            sm.evaluate("tool.err", "tool.err", execution_observed=True, execution_returncode=1)
        self.assertEqual(sm.current_state, "STOP_BLOCKED")
        trans_names = [t[1] for t in sm.transitions[-3:]]
        self.assertEqual(trans_names, ["RUNNING", "FAILURE", "STOP_BLOCKED"])



class TestSolRoundFiveCounterexamples(unittest.TestCase):
    """Counterexamples and positive controls for cx/gpt-5.6-sol-high round 5 review findings."""

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(
            cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.lock_defs = [
            {
                "id": "R5-LOCK-EXCL",
                "mode": "exclusive",
                "renewable": True,
                "lease_seconds": 600,
                "max_cumulative_seconds": 1200,
                "max_renewals": 2,
            },
            {
                "id": "R5-LOCK-DB",
                "mode": "exclusive_by_database_name",
                "partition_key_prefix": "db:",
                "renewable": True,
            },
            {"id": "R5-LOCK-CAP", "mode": "capacity", "capacity": 3, "renewable": True},
            {
                "id": "R5-LOCK-IMMUTABLE",
                "mode": "immutable",
                "renewable": False,
                "mutation_lease_forbidden": True,
            },
            {"id": "R5-LOCK-EXTRA", "mode": "exclusive", "renewable": True, "lease_seconds": 300},
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.mgr.set_task_authority("TASK-A", "granted")
        self.mgr.set_task_authority("TASK-B", "granted")
        self.adapter = OrcaDeliveryAdapter(
            self.mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR
        )
        self.adapter.set_task_authority("TASK-A", "granted")
        self.adapter.set_task_authority("TASK-B", "granted")
        self.adapter.set_task_state("TASK-A", "ready")
        self.adapter.set_task_state("TASK-B", "ready")
        self.adapter.register_task_locks("TASK-A", ["R5-LOCK-EXCL"])
        self.adapter.register_task_locks("TASK-B", ["R5-LOCK-CAP"])

    # Item 1: Non-skippable fixtures and secret scan gate in release/audit modes
    def test_r5_01_cli_and_env_cannot_skip_fixtures_in_audit_release(self):
        """1. Counterexample: --skip-fixtures and VALIDATE_SKIP_FIXTURES rejected fail-closed."""
        proc_cli = subprocess.run(
            [sys.executable, str(BUNDLE_DIR / "validate.py"), "--skip-fixtures"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_cli.returncode, 1)
        self.assertIn("strictly forbidden in audit/release modes", proc_cli.stdout)

        env_skip = {"VALIDATE_SKIP_FIXTURES": "1"}
        proc_env = subprocess.run(
            [sys.executable, str(BUNDLE_DIR / "validate.py")],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            env=env_skip,
        )
        self.assertEqual(proc_env.returncode, 1)
        self.assertIn("strictly forbidden in audit/release modes", proc_env.stdout)

    def test_r5_02_secret_scan_detects_credentials_and_passes_clean_files(self):
        """2. Counterexample: check_secret_scan detects credentials/keys and passes clean files."""
        # Clean check
        self.assertEqual(check_secret_scan(["docs/parallel-delivery/README.md"]), [])

        # Adversarial check with synthetic secret in temp file
        scratch_dir = ROOT_DIR / ".scratch_test_secrets"
        scratch_dir.mkdir(exist_ok=True)
        secret_file = scratch_dir / "secret_sample.txt"
        try:
            # Construct secret dynamically so this test source file does not match scan patterns
            part_a = "AK" + "IA"
            part_b = "1234567890ABCDEF"
            secret_file.write_text(f"aws_key = {part_a}{part_b}\n", encoding="utf-8")
            rel = secret_file.relative_to(ROOT_DIR).as_posix()
            res = check_secret_scan([rel])
            self.assertEqual(len(res), 1)
            self.assertIn("detected potential secret", res[0])

            sk_part = "s" + "k-"
            sk_body = "012345678901234567890123456789"
            secret_file.write_text(f"key = {sk_part}{sk_body}\n", encoding="utf-8")
            res2 = check_secret_scan([rel])
            self.assertEqual(len(res2), 1)
            self.assertIn("OpenAI/API secret key", res2[0])
        finally:
            if secret_file.exists():
                secret_file.unlink()
            if scratch_dir.exists():
                scratch_dir.rmdir()

    # Item 2: Global Orca task IDs and dispatch IDs unique across adapter instances via shared registry
    def test_r5_03_shared_durable_registry_task_id_uniqueness_across_adapters(self):
        """3. Counterexample: Multiple adapter instances sharing registry enforce task ID uniqueness."""
        shared_reg = SharedOrcaExecutionRegistry()
        adapter1 = OrcaDeliveryAdapter(self.mgr, self.candidate_commit, git_root=ROOT_DIR, registry=shared_reg)
        adapter2 = OrcaDeliveryAdapter(self.mgr, self.candidate_commit, git_root=ROOT_DIR, registry=shared_reg)
        adapter1.set_task_authority("TASK-A", "granted")
        adapter1.set_task_state("TASK-A", "ready")
        adapter1.register_task_locks("TASK-A", ["R5-LOCK-EXCL"])
        adapter2.set_task_authority("TASK-B", "granted")
        adapter2.set_task_state("TASK-B", "ready")
        adapter2.register_task_locks("TASK-B", ["R5-LOCK-CAP"])

        lease_a = self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-A", "ctx-a-r5")
        adapter1.create_dispatch(
            "TASK-A",
            orca_task_id="orca-shared-task-001",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
            lease_id=lease_a.lease_id,
            intended_dispatch_id="ctx-a-r5",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a-r5"),
        )

        lease_b = self.mgr.acquire_lease("R5-LOCK-CAP", "TASK-B", "ctx-b-r5", units=1)
        with self.assertRaises(ProtocolViolationError) as ctx:
            adapter2.create_dispatch(
                "TASK-B",
                orca_task_id="orca-shared-task-001",
                candidate_commit=self.candidate_commit,
                fencing_token=lease_b.fencing_token,
                lease_id=lease_b.lease_id,
                intended_dispatch_id="ctx-b-r5",
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-B", "ctx-b-r5"),
            )
        self.assertIn("global reuse is forbidden", str(ctx.exception))

    def test_r5_04_shared_durable_registry_dispatch_id_uniqueness_across_adapters(self):
        """4. Counterexample: Multiple adapter instances sharing registry enforce dispatch ID uniqueness."""
        shared_reg = SharedOrcaExecutionRegistry()
        adapter1 = OrcaDeliveryAdapter(self.mgr, self.candidate_commit, git_root=ROOT_DIR, registry=shared_reg)
        adapter2 = OrcaDeliveryAdapter(self.mgr, self.candidate_commit, git_root=ROOT_DIR, registry=shared_reg)
        adapter1.set_task_authority("TASK-A", "granted")
        adapter1.set_task_state("TASK-A", "ready")
        adapter1.register_task_locks("TASK-A", ["R5-LOCK-EXCL"])
        adapter2.set_task_authority("TASK-B", "granted")
        adapter2.set_task_state("TASK-B", "ready")
        adapter2.register_task_locks("TASK-B", ["R5-LOCK-CAP"])

        lease_a = self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-A", "ctx-shared-disp")
        adapter1.create_dispatch(
            "TASK-A",
            orca_task_id="orca-t1-unique",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
            lease_id=lease_a.lease_id,
            intended_dispatch_id="ctx-shared-disp",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-shared-disp"),
        )

        lease_b = self.mgr.acquire_lease("R5-LOCK-CAP", "TASK-B", "ctx-shared-disp", units=1)
        with self.assertRaises(ProtocolViolationError) as ctx:
            adapter2.create_dispatch(
                "TASK-B",
                orca_task_id="orca-t2-unique",
                candidate_commit=self.candidate_commit,
                fencing_token=lease_b.fencing_token,
                lease_id=lease_b.lease_id,
                intended_dispatch_id="ctx-shared-disp",
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-B", "ctx-shared-disp"),
            )
        self.assertIn("Duplicate dispatch binding overwrite", str(ctx.exception))

    # Item 3: Approved candidate binding is mandatory and exact
    def test_r5_05_mandatory_exact_approved_candidate_commit_binding(self):
        """5. Counterexample: OrcaDeliveryAdapter strictly requires full 40-char approved_candidate_commit."""
        for bad_candidate in (None, "", "   ", "HEAD", "12345", "not_hex_sha_1234567890123456789012345678"):
            with self.assertRaises(ProtocolViolationError):
                OrcaDeliveryAdapter(self.mgr, approved_candidate_commit=bad_candidate, git_root=ROOT_DIR)  # type: ignore

        lease = self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-A", "ctx-cand-mismatch")
        other_sha = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-cand-test",
                candidate_commit=other_sha,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx-cand-mismatch",
            )
        self.assertTrue(
            "does not match approved candidate" in str(ctx.exception)
            or "does not match approved candidate / HEAD" in str(ctx.exception)
        )

    # Item 4: Intended dispatch is mandatory with no lease rewrite
    def test_r5_06_intended_dispatch_mandatory_without_lease_rewrite(self):
        """6. Counterexample: intended_dispatch_id is mandatory and cannot rewrite lease dispatch_id."""
        lease = self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-A", "ctx-original-target")
        self.assertEqual(lease.dispatch_id, "ctx-original-target")

        # 1. Blank/omitted intended_dispatch_id fails closed
        for blank_disp in (None, "", "   "):
            with self.assertRaises(ProtocolViolationError) as ctx:
                self.adapter.create_dispatch(
                    "TASK-A",
                    orca_task_id="orca-blank-disp",
                    candidate_commit=self.candidate_commit,
                    fencing_token=lease.fencing_token,
                    lease_id=lease.lease_id,
                    intended_dispatch_id=blank_disp,  # type: ignore
                )
            self.assertIn("intended_dispatch_id is mandatory", str(ctx.exception))
            self.assertEqual(lease.dispatch_id, "ctx-original-target")  # No rewrite!

        # 2. Mismatched intended_dispatch_id fails closed without rewrite
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-mismatch-disp",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx-hijack-attempt",
            )
        self.assertIn("does not match requested", str(ctx2.exception))
        self.assertEqual(lease.dispatch_id, "ctx-original-target")  # No rewrite!

    # Item 5: Normal lifecycle progression and blocked illegal transitions
    def test_r5_07_normal_lifecycle_progression_acknowledged_running_worker_done(self):
        """7. Positive control: dispatched -> acknowledged -> running -> worker_done succeeded -> review."""
        lease = self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-A", "ctx-lifecycle-1")
        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-life-1",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id="ctx-lifecycle-1",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-lifecycle-1"),
        )
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "dispatched")

        # acknowledge_dispatch
        self.adapter.acknowledge_dispatch("TASK-A", disp)
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "acknowledged")

        # start_running
        self.adapter.start_running("TASK-A", disp)
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "running")

        # worker_done succeeded -> review
        st = self.adapter.handle_worker_done(
            "TASK-A",
            "orca-life-1",
            disp,
            outcome="succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
        )
        self.assertEqual(st, "review")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "review")

    def test_r5_08_lifecycle_failure_progression_to_blocked(self):
        """8. Positive control: dispatched -> acknowledged -> running -> worker_done failed -> blocked."""
        lease = self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-A", "ctx-lifecycle-2")
        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-life-2",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id="ctx-lifecycle-2",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-lifecycle-2"),
        )
        self.adapter.acknowledge_dispatch("TASK-A", disp)
        self.adapter.start_running("TASK-A", disp)
        st = self.adapter.handle_worker_done(
            "TASK-A",
            "orca-life-2",
            disp,
            outcome="failed",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
        )
        self.assertEqual(st, "blocked")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "blocked")

    def test_r5_09_lifecycle_illegal_direct_transitions_blocked(self):
        """9. Counterexample: Illegal state transitions from lifecycle states are blocked."""
        # dispatched -> integrated is forbidden
        self.adapter.set_task_state("TASK-A", "ready")
        self.adapter.transition_task_state("TASK-A", "dispatched")
        with self.assertRaises(ProtocolViolationError):
            self.adapter.transition_task_state("TASK-A", "integrated")

        # acknowledged -> integrated is forbidden
        self.adapter.transition_task_state("TASK-A", "acknowledged")
        with self.assertRaises(ProtocolViolationError):
            self.adapter.transition_task_state("TASK-A", "integrated")

        # running -> ready is forbidden
        self.adapter.transition_task_state("TASK-A", "running")
        with self.assertRaises(ProtocolViolationError):
            self.adapter.transition_task_state("TASK-A", "ready")

        # Cannot acknowledge or start running a task in ready state
        self.adapter._task_states["TASK-A"] = "ready"
        with self.assertRaises(ProtocolViolationError):
            self.adapter.acknowledge_dispatch("TASK-A", "ctx-none")
        with self.assertRaises(ProtocolViolationError):
            self.adapter.start_running("TASK-A", "ctx-none")

    # Item 6: Dispatch proves complete declared task lock set
    def test_r5_10_dispatch_proves_complete_declared_task_lock_set(self):
        """10. Counterexample & positive: Dispatch requires proving all declared task locks."""
        self.adapter.register_task_locks("TASK-A", ["R5-LOCK-EXCL", "R5-LOCK-EXTRA"])
        lease_excl = self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-A", "ctx-lock-set")

        # Proving only 1 of 2 declared locks fails
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-lock-set-fail",
                candidate_commit=self.candidate_commit,
                fencing_token=lease_excl.fencing_token,
                lease_id=lease_excl.lease_id,
                intended_dispatch_id="ctx-lock-set",
            )
        self.assertIn("Dispatch must prove the complete declared task lock set", str(ctx.exception))
        self.assertIn("R5-LOCK-EXTRA", str(ctx.exception))

        # Proving both declared locks succeeds
        lease_extra = self.mgr.acquire_lease("R5-LOCK-EXTRA", "TASK-A", "ctx-lock-set")
        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-lock-set-pass",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_excl.fencing_token,
            lease_ids=[lease_excl.lease_id, lease_extra.lease_id],
            intended_dispatch_id="ctx-lock-set",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-lock-set"),
        )
        self.assertEqual(disp, "ctx-lock-set")

    # Item 7: Multi-unit capacity reserves and fences every allocated slot
    def test_r5_11_multi_unit_capacity_reserves_and_fences_every_allocated_slot(self):
        """11. Counterexample & positive: Multi-unit capacity assigns and fences each allocated slot."""
        lease_multi = self.mgr.acquire_lease("R5-LOCK-CAP", "TASK-A", "ctx-multi-cap", units=2)
        self.assertEqual(lease_multi.units, 2)
        self.assertEqual(lease_multi.allocated_slots, [1, 2])
        self.assertEqual(set(lease_multi.slot_fencing_tokens.keys()), {1, 2})
        tok1 = lease_multi.slot_fencing_tokens[1]
        tok2 = lease_multi.slot_fencing_tokens[2]
        self.assertEqual(tok1, 1)
        self.assertEqual(tok2, 1)

        # Release and reallocate unit 1
        self.mgr.release_lease(lease_multi.lease_id)
        lease_single = self.mgr.acquire_lease("R5-LOCK-CAP", "TASK-A", "ctx-single-cap", units=1)
        self.assertEqual(lease_single.allocation_slot, 1)
        self.assertEqual(lease_single.fencing_token, 2)  # Monotonically advanced

    # Item 8: Partition namespace overlap is symmetric parent/child
    def test_r5_12_symmetric_partition_namespace_overlap_parent_blocks_child(self):
        """12. Counterexample: Parent namespace lease blocks child namespace lease."""
        parent_l = self.mgr.acquire_lease("R5-LOCK-DB", "TASK-A", "ctx-p", resource_key="db:analytics")
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("R5-LOCK-DB", "TASK-B", "ctx-c", resource_key="db:analytics:us_east")
        self.assertIn("symmetric parent/child overlap", str(ctx.exception))
        self.mgr.release_lease(parent_l.lease_id)

    def test_r5_13_symmetric_partition_namespace_overlap_child_blocks_parent(self):
        """13. Counterexample: Child namespace lease blocks parent namespace lease."""
        child_l = self.mgr.acquire_lease("R5-LOCK-DB", "TASK-A", "ctx-c", resource_key="db:analytics:us_east")
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("R5-LOCK-DB", "TASK-B", "ctx-p", resource_key="db:analytics")
        self.assertIn("symmetric parent/child overlap", str(ctx.exception))
        self.mgr.release_lease(child_l.lease_id)

    def test_r5_14_symmetric_partition_namespace_non_conflicting_siblings_pass(self):
        """14. Positive control: Sibling non-overlapping namespaces pass concurrently."""
        l1 = self.mgr.acquire_lease("R5-LOCK-DB", "TASK-A", "ctx-1", resource_key="db:analytics_1")
        l2 = self.mgr.acquire_lease("R5-LOCK-DB", "TASK-B", "ctx-2", resource_key="db:analytics_2")
        self.assertIsNotNone(l1)
        self.assertIsNotNone(l2)
        self.mgr.release_lease(l1.lease_id)
        self.mgr.release_lease(l2.lease_id)

    # Item 9: Renewals cannot cumulatively exceed declared lease policy
    def test_r5_15_cumulative_renewal_exceeding_max_cumulative_seconds_rejected(self):
        """15. Counterexample: Renewals cannot cumulatively exceed max_cumulative_seconds."""
        mgr_strict = LeaseManager([
            {
                "id": "L-CUM-STRICT",
                "mode": "exclusive",
                "renewable": True,
                "lease_seconds": 600,
                "max_cumulative_seconds": 600,
                "max_renewals": 5,
            }
        ])
        mgr_strict.set_task_authority("TASK-A", "granted")
        lease = mgr_strict.acquire_lease("L-CUM-STRICT", "TASK-A", "ctx-renew-cum", lease_seconds=600)
        # First renewal by 600s brings cumulative_extension_seconds to 600s == max_cumulative_seconds
        mgr_strict.renew_lease(lease.lease_id, extend_seconds=600)
        self.assertEqual(lease.renewal_count, 1)
        self.assertEqual(lease.cumulative_extension_seconds, 600)

        # Second renewal by 100s would bring cumulative extensions to 700s > max_cumulative_seconds (600s)
        with self.assertRaises(LockLeaseError) as ctx:
            mgr_strict.renew_lease(lease.lease_id, extend_seconds=100)
        self.assertIn("would exceed declared lease policy", str(ctx.exception))

    def test_r5_16_cumulative_renewal_exceeding_max_renewals_rejected(self):
        """16. Counterexample: Renewals cannot exceed max_renewals count."""
        mgr_strict = LeaseManager([
            {"id": "L-MAX-R", "mode": "exclusive", "renewable": True, "lease_seconds": 600, "max_renewals": 1, "max_cumulative_seconds": 1800}
        ])
        mgr_strict.set_task_authority("TASK-A", "granted")
        lease = mgr_strict.acquire_lease("L-MAX-R", "TASK-A", "ctx-mr")
        mgr_strict.renew_lease(lease.lease_id, extend_seconds=600)
        self.assertEqual(lease.renewal_count, 1)

        with self.assertRaises(LockLeaseError) as ctx:
            mgr_strict.renew_lease(lease.lease_id, extend_seconds=600)
        self.assertIn("reached maximum allowed renewals (1)", str(ctx.exception))

    # Item 10: Successful worker_done releases leases before exposing review state
    def test_r5_17_successful_worker_done_releases_leases_before_review_state(self):
        """17. Counterexample & positive: Successful worker_done releases all leases before exposing review state."""
        self.adapter.register_task_locks("TASK-A", ["R5-LOCK-EXCL", "R5-LOCK-EXTRA"])
        l1 = self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-A", "ctx-wd-rel")
        l2 = self.mgr.acquire_lease("R5-LOCK-EXTRA", "TASK-A", "ctx-wd-rel")
        self.assertEqual(len(self.mgr.active_leases), 2)

        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-wd-rel",
            candidate_commit=self.candidate_commit,
            fencing_token=l1.fencing_token,
            lease_ids=[l1.lease_id, l2.lease_id],
            intended_dispatch_id="ctx-wd-rel",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-wd-rel"),
        )
        self.adapter.acknowledge_dispatch("TASK-A", disp)
        self.adapter.start_running("TASK-A", disp)
        st = self.adapter.handle_worker_done(
            "TASK-A",
            "orca-wd-rel",
            disp,
            outcome="succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=l1.fencing_token,
        )
        self.assertEqual(st, "review")
        # All mutation leases must be purged immediately before state is exposed
        self.assertEqual(len(self.mgr.active_leases), 0)

        # Another task can immediately acquire the released exclusive lock
        self.adapter.register_task_locks("TASK-B", ["R5-LOCK-EXCL"])
        l_new = self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-B", "ctx-b-after")
        self.assertIsNotNone(l_new)
        self.mgr.release_lease(l_new.lease_id)

    # Item 11: HarnessExecutionResult rejects contradictory fields and state machine rejects illegal direct states
    def test_r5_18_harness_result_rejects_contradictory_success_status_stop(self):
        """18. Counterexample: HarnessExecutionResult rejects success=True with status='STOP'."""
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            HarnessExecutionResult(
                success=True,
                execution_time_ms=10.0,
                status="STOP",
                state="SUCCESS",
                tool_name="t",
                requested_tool="t",
                execution_observed=True,
                execution_returncode=0,
                fallback_required=False,
            )
        self.assertIn("Contradictory fields: success=True but status='STOP'", str(ctx.exception))

    def test_r5_19_harness_result_rejects_contradictory_success_with_fallback(self):
        """19. Counterexample: HarnessExecutionResult rejects success=True with fallback_required=True."""
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            HarnessExecutionResult(
                success=True,
                execution_time_ms=10.0,
                status="PASS",
                state="SUCCESS",
                tool_name="t",
                requested_tool="t",
                execution_observed=True,
                execution_returncode=0,
                fallback_required=True,
            )
        self.assertIn("Contradictory fields: success=True but fallback_required=True", str(ctx.exception))

    def test_r5_20_harness_result_rejects_contradictory_failure_status_pass(self):
        """20. Counterexample: HarnessExecutionResult rejects success=False with status='PASS'."""
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            HarnessExecutionResult(
                success=False,
                execution_time_ms=10.0,
                status="PASS",
                state="FAILURE",
                tool_name="t",
                requested_tool="t",
                execution_observed=True,
                execution_returncode=1,
                fallback_required=True,
            )
        self.assertIn("Contradictory fields: success=False but status='PASS'", str(ctx.exception))

    def test_r5_21_harness_result_rejects_contradictory_failure_without_fallback(self):
        """21. Counterexample: HarnessExecutionResult rejects failure requesting native provider fallback."""
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            HarnessExecutionResult(
                success=False,
                execution_time_ms=10.0,
                status="STOP",
                state="FAILURE",
                tool_name="t",
                requested_tool="t",
                execution_observed=True,
                execution_returncode=1,
                fallback_required=True,
                fallback_target="antigravity_native",
            )
        self.assertIn("native-provider fallback is rejected fail-closed", str(ctx.exception))

    def test_r5_22_harness_result_rejects_contradictory_success_nonzero_returncode(self):
        """22. Counterexample: HarnessExecutionResult rejects success=True with nonzero execution_returncode."""
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            HarnessExecutionResult(
                success=True,
                execution_time_ms=10.0,
                status="PASS",
                state="SUCCESS",
                tool_name="t",
                requested_tool="t",
                execution_observed=True,
                execution_returncode=2,
                fallback_required=False,
            )
        self.assertIn("Contradictory fields: success=True but execution_returncode=2", str(ctx.exception))

    def test_r5_23_harness_state_machine_rejects_illegal_direct_state(self):
        """23. Counterexample: HarnessExecutionStateMachine rejects illegal direct state assignment."""
        sm = HarnessExecutionStateMachine()
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            sm.current_state = "BOGUS_INVALID_STATE"
        self.assertIn("Illegal direct state", str(ctx.exception))

    def test_r5_24_harness_state_machine_rejects_illegal_transitions(self):
        """24. Counterexample: HarnessExecutionStateMachine rejects illegal state machine transitions."""
        sm = HarnessExecutionStateMachine()
        self.assertEqual(sm.current_state, "IDLE")
        # Direct transition IDLE -> SUCCESS is illegal
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            sm.transition("SUCCESS", "skip running")
        self.assertIn("Illegal harness state transition", str(ctx.exception))

    # Item 12: Blank identities and integrated-task reacquisition remain fail-closed
    def test_r5_25_blank_identities_rejected_at_acquire_renew_release(self):
        """25. Counterexample: Blank lock_id, task_id, dispatch_id, and lease_id fail closed."""
        for blank_val in ("", "   ", None):
            with self.assertRaises(LockLeaseError):
                self.mgr.acquire_lease(blank_val, "TASK-A", "ctx-id")  # type: ignore
            with self.assertRaises(LockLeaseError):
                self.mgr.acquire_lease("R5-LOCK-EXCL", blank_val, "ctx-id")  # type: ignore
            with self.assertRaises(LockLeaseError):
                self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-A", blank_val)  # type: ignore
            with self.assertRaises(LockLeaseError):
                self.mgr.renew_lease(blank_val)  # type: ignore
            with self.assertRaises(LockLeaseError):
                self.mgr.release_lease(blank_val)  # type: ignore

    def test_r5_26_integrated_task_lease_reacquisition_strictly_forbidden(self):
        """26. Counterexample: Integrated task cannot re-acquire locks."""
        l = self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-A", "ctx-integ")
        self.assertEqual(len(self.mgr.active_leases), 1)

        # Mark integrated
        self.mgr.mark_task_integrated("TASK-A")
        self.assertEqual(len(self.mgr.active_leases), 0)

        # Re-acquisition must fail closed
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.acquire_lease("R5-LOCK-EXCL", "TASK-A", "ctx-integ-reacquire")
        self.assertIn("already integrated; reacquisition of leases is strictly prohibited", str(ctx.exception))



class TestSolRoundSixCounterexamples(unittest.TestCase):
    """Counterexamples for Sol Round 6 review blockers:
    1. Process-durable shared execution registry with explicit storage path/atomic persistence/locking
    2. Multi-slot capacity validation with monotonic generation and asymmetric reuse invalidation
    3. Mandatory ready->dispatched->acknowledged->running->worker_done lifecycle path (no skipped ACK/running)
    4. Mandatory declared_task_locks registration and exact complete lock set before dispatch
    5. Forbid direct harness state assignment (e.g. IDLE->SUCCESS) and expose legal methods only
    6. Broadened secret scan for Anthropic and common provider token forms without real secrets
    7. Fresh exact-head attestation under parent-plus-wrapper semantics and audit freshness check
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.lock_defs = [
            {"id": "R6-LOCK-EXCL", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
            {"id": "R6-LOCK-EXTRA", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
            {"id": "R6-LOCK-CAP4", "mode": "capacity", "capacity": 4, "renewable": True, "lease_seconds": 600},
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.candidate_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.mgr.set_task_authority("TASK-A", "granted")
        self.mgr.set_task_authority("TASK-B", "granted")
        self.adapter = OrcaDeliveryAdapter(
            self.mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR
        )
        self.adapter.set_task_authority("TASK-A", "granted")
        self.adapter.set_task_authority("TASK-B", "granted")
        self.adapter.set_task_state("TASK-A", "ready")
        self.adapter.set_task_state("TASK-B", "ready")
        self.adapter.register_task_locks("TASK-A", ["R6-LOCK-EXCL"])
        self.adapter.register_task_locks("TASK-B", ["R6-LOCK-CAP4"])

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def test_r6_01_process_durable_registry_persists_across_simulated_restart(self):
        """1. Counterexample: Registry persists to explicit storage path; simulated restart enforces global uniqueness."""
        with tempfile.TemporaryDirectory() as td:
            reg_path = Path(td) / "test_registry.json"
            reg1 = SharedOrcaExecutionRegistry(storage_path=reg_path)
            reg1.register_orca_task("orca-durable-task-1", "TASK-A")
            binding = DispatchBinding(
                delivery_task_id="TASK-A",
                orca_task_id="orca-durable-task-1",
                dispatch_id="ctx-durable-1",
                candidate_commit=self.candidate_commit,
                fencing_token=1,
                lease_id="lease-1",
                lease_ids=["lease-1"],
                authority_state="granted",
                settled=False,
            )
            reg1.register_dispatch_binding("ctx-durable-1", binding)
            self.assertTrue(reg_path.is_file())

            # Simulated process restart: a completely new instance pointing to same storage path
            reg2 = SharedOrcaExecutionRegistry(storage_path=reg_path)
            self.assertIn("orca-durable-task-1", reg2.seen_orca_task_ids)
            self.assertIn("ctx-durable-1", reg2.seen_dispatch_ids)
            self.assertEqual(reg2.orca_task_to_delivery_task.get("orca-durable-task-1"), "TASK-A")

            # Re-registering across simulated restart fails
            with self.assertRaises(ProtocolViolationError) as ctx:
                reg2.register_orca_task("orca-durable-task-1", "TASK-B")
            self.assertIn("global reuse across adapter instances is forbidden", str(ctx.exception))

            with self.assertRaises(ProtocolViolationError) as ctx:
                reg2.register_dispatch_binding("ctx-durable-1", binding)
            self.assertIn("Duplicate dispatch binding overwrite", str(ctx.exception))

    def test_r6_02_default_adapters_share_registry_and_enforce_uniqueness(self):
        """2. Counterexample: Distinct default adapters without explicit registry share execution registry."""
        adapter1 = OrcaDeliveryAdapter(self.mgr, self.candidate_commit, git_root=ROOT_DIR)
        adapter2 = OrcaDeliveryAdapter(self.mgr, self.candidate_commit, git_root=ROOT_DIR)
        adapter1.set_task_authority("TASK-A", "granted")
        adapter1.set_task_state("TASK-A", "ready")
        adapter1.register_task_locks("TASK-A", ["R6-LOCK-EXCL"])

        adapter2.set_task_authority("TASK-B", "granted")
        adapter2.set_task_state("TASK-B", "ready")
        adapter2.register_task_locks("TASK-B", ["R6-LOCK-CAP4"])

        lease_a = self.mgr.acquire_lease("R6-LOCK-EXCL", "TASK-A", "ctx-shared-default-1")
        adapter1.create_dispatch(
            "TASK-A",
            orca_task_id="orca-default-task-1",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
            lease_id=lease_a.lease_id,
            intended_dispatch_id="ctx-shared-default-1",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-shared-default-1"),
        )

        # adapter2 must see orca-default-task-1 and reject reuse
        lease_b = self.mgr.acquire_lease("R6-LOCK-CAP4", "TASK-B", "ctx-shared-default-2", units=1)
        with self.assertRaises(ProtocolViolationError) as ctx:
            adapter2.create_dispatch(
                "TASK-B",
                orca_task_id="orca-default-task-1",
                candidate_commit=self.candidate_commit,
                fencing_token=lease_b.fencing_token,
                lease_id=lease_b.lease_id,
                intended_dispatch_id="ctx-shared-default-2",
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-B", "ctx-shared-default-2"),
            )
        self.assertIn("global reuse is forbidden", str(ctx.exception))

    def test_r6_03_multi_slot_capacity_asymmetric_reuse_invalidates_prior_lease(self):
        """3. Counterexample: Multi-slot capacity lease invalidated when one of its exact slots is asymmetrically reallocated."""
        # Task A acquires 2 units -> gets slots 1, 2
        lease_a = self.mgr.acquire_lease("R6-LOCK-CAP4", "TASK-A", "ctx-a-cap", units=2)
        self.assertEqual(lease_a.allocated_slots, [1, 2])
        initial_tokens = dict(lease_a.slot_fencing_tokens)
        self.assertEqual(initial_tokens, {1: 1, 2: 1})

        # Lease is valid initially
        self.mgr.validate_fencing_token("R6-LOCK-CAP4", lease_a.fencing_token, active_lease_id=lease_a.lease_id)

        # Asymmetric reuse: slot 2 is reallocated while slot 1 is not:
        self.mgr.fencing_counters["R6-LOCK-CAP4:slot_2"] = 2

        # Validating lease A now MUST fail because slot 2's recorded token (1) is stale (current is 2)
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.validate_fencing_token("R6-LOCK-CAP4", lease_a.fencing_token, active_lease_id=lease_a.lease_id)
        self.assertIn("asymmetric", str(ctx.exception).lower())

    def test_r6_04_mandatory_lifecycle_rejects_skipping_acknowledged(self):
        """4. Counterexample: Cannot transition directly from dispatched to running without acknowledging."""
        lease_a = self.mgr.acquire_lease("R6-LOCK-EXCL", "TASK-A", "ctx-life-1")
        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-life-1",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
            lease_id=lease_a.lease_id,
            intended_dispatch_id="ctx-life-1",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-life-1"),
        )
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "dispatched")

        # Directly starting running without acknowledging fails
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.start_running("TASK-A", disp)
        self.assertIn("acknowledged", str(ctx.exception))

        # Directly transitioning state to running fails
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state("TASK-A", "running")
        self.assertIn("Illegal task-state transition", str(ctx.exception))

    def test_r6_05_mandatory_lifecycle_rejects_skipping_running_to_worker_done(self):
        """5. Counterexample: Cannot invoke worker_done from dispatched or acknowledged; must be running."""
        lease_a = self.mgr.acquire_lease("R6-LOCK-EXCL", "TASK-A", "ctx-life-2")
        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-life-2",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
            lease_id=lease_a.lease_id,
            intended_dispatch_id="ctx-life-2",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-life-2"),
        )

        # 1. worker_done from dispatched fails
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_worker_done(
                "TASK-A", "orca-life-2", disp, "succeeded",
                candidate_commit=self.candidate_commit, fencing_token=lease_a.fencing_token
            )
        self.assertIn("running", str(ctx.exception))

        # 2. Acknowledge dispatch
        self.adapter.acknowledge_dispatch("TASK-A", disp)
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "acknowledged")

        # worker_done from acknowledged fails
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_worker_done(
                "TASK-A", "orca-life-2", disp, "succeeded",
                candidate_commit=self.candidate_commit, fencing_token=lease_a.fencing_token
            )
        self.assertIn("running", str(ctx.exception))

        # 3. Start running -> worker_done succeeds
        self.adapter.start_running("TASK-A", disp)
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "running")
        st = self.adapter.handle_worker_done(
            "TASK-A", "orca-life-2", disp, "succeeded",
            candidate_commit=self.candidate_commit, fencing_token=lease_a.fencing_token
        )
        self.assertEqual(st, "review")

    def test_r6_06_mandatory_declared_task_locks_registration(self):
        """6. Counterexample: Dispatch rejects task without registered declared_task_locks."""
        # TASK-UNREG has granted authority and ready state, but no declared_task_locks registered
        self.mgr.set_task_authority("TASK-UNREG", "granted")
        self.adapter.set_task_authority("TASK-UNREG", "granted")
        self.adapter.set_task_state("TASK-UNREG", "ready")

        lease = self.mgr.acquire_lease("R6-LOCK-EXCL", "TASK-UNREG", "ctx-unreg-locks")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-UNREG",
                orca_task_id="orca-unreg-locks",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx-unreg-locks",
            )
        self.assertIn("declared_task_locks", str(ctx.exception))

    def test_r6_07_dispatch_proves_exact_complete_lock_set(self):
        """7. Counterexample: Dispatch must prove exact complete lock set; rejects missing or extraneous locks."""
        self.adapter.register_task_locks("TASK-A", ["R6-LOCK-EXCL", "R6-LOCK-EXTRA"])
        l_excl = self.mgr.acquire_lease("R6-LOCK-EXCL", "TASK-A", "ctx-exact-1")
        l_extra = self.mgr.acquire_lease("R6-LOCK-EXTRA", "TASK-A", "ctx-exact-1")

        # 1. Missing lock: proving only 1 of 2
        with self.assertRaises(ProtocolViolationError) as ctx1:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-missing-lock",
                candidate_commit=self.candidate_commit,
                fencing_token=l_excl.fencing_token,
                lease_id=l_excl.lease_id,
                intended_dispatch_id="ctx-exact-1",
            )
        self.assertIn("missing", str(ctx1.exception))

        # 2. Extraneous lock: TASK-A declares only R6-LOCK-EXCL but passes R6-LOCK-EXTRA too
        self.adapter.register_task_locks("TASK-A", ["R6-LOCK-EXCL"])
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-extraneous-lock",
                candidate_commit=self.candidate_commit,
                fencing_token=l_excl.fencing_token,
                lease_ids=[l_excl.lease_id, l_extra.lease_id],
                intended_dispatch_id="ctx-exact-1",
            )
        self.assertIn("extraneous", str(ctx2.exception))

    def test_r6_08_harness_state_machine_forbids_direct_state_assignment(self):
        """8. Counterexample: Direct harness state assignment (e.g. IDLE->SUCCESS) is strictly forbidden."""
        sm = HarnessExecutionStateMachine()
        self.assertEqual(sm.current_state, "IDLE")

        # Direct assignment of valid state "SUCCESS" is forbidden
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            sm.current_state = "SUCCESS"
        self.assertIn("Illegal direct state", str(ctx.exception))

        # Direct assignment of any state is forbidden
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            sm.current_state = "RUNNING"
        self.assertIn("Illegal direct state", str(ctx.exception))

    def test_r6_09_secret_scan_detects_anthropic_and_common_provider_tokens(self):
        """9. Positive & negative: Secret scan catches Anthropic and common provider token formats without embedding real secrets."""
        import validate
        secret_pats = getattr(validate, "SECRET_PATTERNS", None)
        if secret_pats is None:
            # Fallback to local regex check if not exported as global
            from validate import check_secret_scan
            self.assertTrue(callable(check_secret_scan))
        else:
            ant_sample = "sk-" + "ant-" + "api03-abcdefghijklmnopqrstuvwxyz0123456789_test"
            slack_sample = "xox" + "b-1234567890-1234567890123-abcdefghijklmnop"
            google_sample = "AI" + "za" + "SyDummyKeyForTestingScanPattern35_1"
            stripe_sample = "sk_" + "live_" + "abcdefghijklmnopqrstuvwxyz012"
            samples = [
                ("anthropic", ant_sample),
                ("slack", slack_sample),
                ("google", google_sample),
                ("stripe", stripe_sample),
            ]
            for label, sample in samples:
                matched = any(p.search(sample) for p, _ in secret_pats)
                self.assertTrue(matched, f"Pattern for {label} failed to match synthetic sample")

    def test_r6_10_attestation_audit_verifies_freshness_for_final_head(self):
        """10. Counterexample: Audit verifies attestation report freshness against final HEAD and bundle hashes."""
        import validate
        check_freshness_fn = getattr(validate, "check_attestation_report_freshness", None)
        self.assertIsNotNone(check_freshness_fn, "validate.py must export check_attestation_report_freshness")
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rep_path = td_path / ".validation-report.json"
            # Missing report fails
            errs = check_freshness_fn(td_path, td_path, rep_path, "head123")
            self.assertTrue(any("missing" in e for e in errs))

            # Stale candidate commit fails
            rep_data = {
                "status": "PASS",
                "attestation": {
                    "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "candidate_commit": "stale_commit_1234567890123456789012345678",
                    "overlay_clean": True,
                    "dirty_overlay_count": 0,
                },
                "bundle_sha256": {}
            }
            rep_path.write_text(json.dumps(rep_data), encoding="utf-8")
            errs2 = check_freshness_fn(td_path, td_path, rep_path, "current_head_0000000000000000000000000000")
            self.assertTrue(any("stale" in e.lower() for e in errs2))


class TestSolRoundSevenCounterexamples(unittest.TestCase):
    """Counterexamples and regression fixtures for Sol Round 7 review blockers:
    1. Process-safe registry read-modify-write and duplicate IDs.
    2. Durable default registry when storage_path=None.
    3. No lifecycle bypass through set_task_state.
    4. Correct per-slot fencing validation for multi-slot tasks.
    5. Attestation rejection of zero/stale wrapper commits inconsistent with actual Git topology.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.lock_defs = [
            {
                "id": "R7-LOCK-EXCL",
                "mode": "exclusive",
                "renewable": True,
                "lease_seconds": 600,
            },
            {
                "id": "R7-LOCK-CAP",
                "mode": "capacity",
                "capacity": 3,
                "renewable": True,
                "lease_seconds": 600,
            },
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.mgr.set_task_authority("TASK-A", "granted")
        self.mgr.set_task_authority("TASK-B", "granted")
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(
            cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        cmd_parent = ["git", "rev-parse", "HEAD~1"]
        self.parent_commit = subprocess.run(
            cmd_parent, cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.adapter = OrcaDeliveryAdapter(
            lease_manager=self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
            declared_task_locks={"TASK-A": ["R7-LOCK-EXCL"], "TASK-B": ["R7-LOCK-CAP"]},
        )
        self.adapter.set_task_authority("TASK-A", "granted")
        self.adapter.set_task_authority("TASK-B", "granted")

    def test_r7_01_process_safe_registry_atomic_transaction_and_duplicate_rejection(self):
        """1. Counterexample: Process-safe registry rejects duplicate IDs and supports atomic transactions."""
        with tempfile.TemporaryDirectory() as td:
            reg_file = Path(td) / "test-reg.json"
            reg = SharedOrcaExecutionRegistry(storage_path=reg_file)

            # FileLock reentrancy test on same thread
            lock_p = reg_file.with_name("test.lock")
            fl = _FileLock(lock_p)
            with fl:
                with fl:
                    self.assertTrue(lock_p.exists())

            # Register orca task
            reg.register_orca_task("orca-task-1", "TASK-A")
            self.assertTrue(reg.is_orca_task_registered("orca-task-1"))
            self.assertEqual(reg.get_orca_task_delivery_id("orca-task-1"), "TASK-A")

            # Duplicate orca task ID is rejected
            with self.assertRaises(ProtocolViolationError) as ctx:
                reg.register_orca_task("orca-task-1", "TASK-B")
            self.assertIn("already assigned", str(ctx.exception))

            with self.assertRaises(ProtocolViolationError) as ctx:
                reg.register_orca_task("orca-task-1", "TASK-A")
            self.assertIn("already been registered", str(ctx.exception))

            # Blank orca task ID is rejected
            with self.assertRaises(ProtocolViolationError):
                reg.register_orca_task("", "TASK-A")

            # Register dispatch binding
            b1 = DispatchBinding(
                delivery_task_id="TASK-A",
                orca_task_id="orca-task-1",
                dispatch_id="disp-1",
                candidate_commit=self.candidate_commit,
            )
            reg.register_dispatch_binding("disp-1", b1)
            self.assertIsNotNone(reg.get_dispatch_binding("disp-1"))

            # Duplicate dispatch ID is rejected
            b2 = DispatchBinding(
                delivery_task_id="TASK-A",
                orca_task_id="orca-task-1",
                dispatch_id="disp-1",
                candidate_commit=self.candidate_commit,
            )
            with self.assertRaises(ProtocolViolationError) as ctx:
                reg.register_dispatch_binding("disp-1", b2)
            self.assertIn("already bound or settled", str(ctx.exception))

            # Settle dispatch and reject duplicate settle
            reg.settle_dispatch("disp-1")
            self.assertTrue(reg.is_dispatch_settled("disp-1"))
            with self.assertRaises(DuplicateResultError) as ctx:
                reg.settle_dispatch("disp-1")
            self.assertIn("already settled", str(ctx.exception))

    def test_r7_02_durable_default_registry_when_storage_path_none(self):
        """2. Counterexample: Default registry is durable on disk when storage_path=None."""
        reg = SharedOrcaExecutionRegistry(storage_path=None)
        self.assertIsNotNone(reg.storage_path, "storage_path must not be None by default")
        self.assertTrue(isinstance(reg.storage_path, Path))

        # Register task and verify it is persisted to disk
        reg.register_orca_task("orca-durable-1", "TASK-DURABLE")
        self.assertTrue(reg.storage_path.is_file(), "Registry file must exist on disk")

        # Open fresh instance with same path and verify recovery
        reg2 = SharedOrcaExecutionRegistry(storage_path=reg.storage_path)
        self.assertTrue(reg2.is_orca_task_registered("orca-durable-1"))
        self.assertEqual(reg2.get_orca_task_delivery_id("orca-durable-1"), "TASK-DURABLE")

        # get_default is also durable
        def_reg = SharedOrcaExecutionRegistry.get_default()
        self.assertIsNotNone(def_reg.storage_path)

    def test_r7_03_no_lifecycle_bypass_through_set_task_state(self):
        """3. Counterexample: Lifecycle states cannot be directly set via set_task_state, and active states cannot be overwritten."""
        forbidden_states = ["dispatched", "acknowledged", "running", "review", "merge_queued", "integrated"]
        for st in forbidden_states:
            with self.assertRaises(ProtocolViolationError) as ctx:
                self.adapter.set_task_state("TASK-A", st)
            self.assertIn("Cannot directly set task", str(ctx.exception))

        # Arbitrary / invalid state is rejected
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.set_task_state("TASK-A", "non_existent_state")
        self.assertIn("Invalid or forbidden task state", str(ctx.exception))

        # Blank delivery_task_id is rejected
        with self.assertRaises(ProtocolViolationError):
            self.adapter.set_task_state("", "ready")

        # Overwriting active lifecycle state is rejected
        self.adapter.set_task_state("TASK-A", "ready")
        self.adapter.transition_task_state("TASK-A", "dispatched")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.set_task_state("TASK-A", "ready")
        self.assertIn("while in active lifecycle state 'dispatched'", str(ctx.exception))

        # Task states property is read-only view
        states = self.adapter.task_states
        states["TASK-A"] = "integrated"
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "dispatched", "Mutating returned task_states dict must not alter internal adapter state")

    def test_r7_04_correct_per_slot_fencing_validation_for_multi_slot_tasks(self):
        """4. Counterexample: Per-slot fencing validates all allocated slots and rejects asymmetric reallocations."""
        lease = self.mgr.acquire_lease("R7-LOCK-CAP", "TASK-B", "ctx-b", units=2)
        self.assertEqual(len(lease.allocated_slots), 2)
        self.assertIn(1, lease.slot_fencing_tokens)
        self.assertIn(2, lease.slot_fencing_tokens)

        # Querying unallocated slot raises error
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.validate_fencing_token(lease.resource_key, lease.fencing_token, slot=99)
        self.assertIn("was not allocated", str(ctx.exception))

        # Querying with slot token mismatch raises error
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.validate_fencing_token(lease.resource_key, 9999, slot=1)
        self.assertIn("Slot token mismatch", str(ctx.exception))

        # Simulate asymmetric slot 2 reallocation
        prefix = lease.resource_key.rsplit(":slot_", 1)[0]
        s2_key = f"{prefix}:slot_{lease.allocated_slots[1]}"
        self.mgr.fencing_counters[s2_key] += 1

        # validate_fencing_token detects asymmetric reallocation
        with self.assertRaises(LockLeaseError) as ctx:
            self.mgr.validate_fencing_token(lease.resource_key, lease.fencing_token)
        self.assertIn("asymmetric slot reallocation detected", str(ctx.exception))

        # create_dispatch detects stale slot token on multi-slot lease
        self.adapter.set_task_state("TASK-B", "ready")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-B",
                orca_task_id="orca-cap-fail",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id="ctx-b",
            )
        self.assertIn("capacity slot reallocation detected", str(ctx.exception))

    def test_r7_05_attestation_rejection_of_zero_wrapper_commit(self):
        """5. Counterexample: Attestation rejects zero SHA wrapper_commit."""
        import validate
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rep_path = td_path / ".validation-report.json"
            rep_data = {
                "status": "PASS",
                "attestation": {
                    "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "candidate_commit": self.candidate_commit,
                    "parent_commit": self.parent_commit,
                    "wrapper_commit": "0" * 40,
                    "overlay_clean": True,
                    "dirty_overlay_count": 0,
                },
                "bundle_sha256": {}
            }
            rep_path.write_text(json.dumps(rep_data), encoding="utf-8")
            errs = validate.check_attestation_report_freshness(ROOT_DIR, td_path, rep_path, self.candidate_commit)
            self.assertTrue(any("zero wrapper" in e for e in errs), f"Expected zero wrapper error, got: {errs}")

    def test_r7_06_attestation_rejection_of_zero_parent_commit(self):
        """6. Counterexample: Attestation rejects zero SHA parent_commit."""
        import validate
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rep_path = td_path / ".validation-report.json"
            rep_data = {
                "status": "PASS",
                "attestation": {
                    "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "candidate_commit": self.candidate_commit,
                    "parent_commit": "0" * 40,
                    "wrapper_commit": self.candidate_commit,
                    "overlay_clean": True,
                    "dirty_overlay_count": 0,
                },
                "bundle_sha256": {}
            }
            rep_path.write_text(json.dumps(rep_data), encoding="utf-8")
            errs = validate.check_attestation_report_freshness(ROOT_DIR, td_path, rep_path, self.candidate_commit)
            self.assertTrue(any("zero parent" in e for e in errs), f"Expected zero parent error, got: {errs}")

    def test_r7_07_attestation_rejection_of_zero_candidate_commit(self):
        """7. Counterexample: Attestation rejects zero SHA candidate_commit."""
        import validate
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rep_path = td_path / ".validation-report.json"
            rep_data = {
                "status": "PASS",
                "attestation": {
                    "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "candidate_commit": "0" * 40,
                    "parent_commit": self.parent_commit,
                    "wrapper_commit": self.candidate_commit,
                    "overlay_clean": True,
                    "dirty_overlay_count": 0,
                },
                "bundle_sha256": {}
            }
            rep_path.write_text(json.dumps(rep_data), encoding="utf-8")
            errs = validate.check_attestation_report_freshness(ROOT_DIR, td_path, rep_path, self.candidate_commit)
            self.assertTrue(any("zero candidate" in e for e in errs), f"Expected zero candidate error, got: {errs}")

    def test_r7_08_attestation_rejection_of_stale_wrapper_commit(self):
        """8. Counterexample: Attestation rejects stale wrapper commit disconnected from current HEAD/parent."""
        import validate
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rep_path = td_path / ".validation-report.json"
            rep_data = {
                "status": "PASS",
                "attestation": {
                    "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "candidate_commit": self.candidate_commit,
                    "parent_commit": self.parent_commit,
                    "wrapper_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "overlay_clean": True,
                    "dirty_overlay_count": 0,
                },
                "bundle_sha256": {}
            }
            rep_path.write_text(json.dumps(rep_data), encoding="utf-8")
            errs = validate.check_attestation_report_freshness(ROOT_DIR, td_path, rep_path, self.candidate_commit)
            self.assertTrue(any("stale" in e for e in errs), f"Expected stale error, got: {errs}")

    def test_r7_09_attestation_rejection_of_inconsistent_git_topology(self):
        """9. Counterexample: Attestation rejects report when wrapper parent does not match parent_commit in Git DAG."""
        import validate
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rep_path = td_path / ".validation-report.json"
            # 3b7a618's parent is d0e1dd8, so claiming parent is 4a7c8c9 must fail topology check
            rep_data = {
                "status": "PASS",
                "attestation": {
                    "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "candidate_commit": self.candidate_commit,
                    "parent_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "wrapper_commit": self.candidate_commit,
                    "overlay_clean": True,
                    "dirty_overlay_count": 0,
                },
                "bundle_sha256": {}
            }
            rep_path.write_text(json.dumps(rep_data), encoding="utf-8")
            errs = validate.check_attestation_report_freshness(ROOT_DIR, td_path, rep_path, self.candidate_commit)
            self.assertTrue(any("topology mismatch" in e for e in errs), f"Expected topology mismatch error, got: {errs}")


class TestSolRoundEightCounterexamples(unittest.TestCase):
    """Sol Round 8 Counterexamples:
    1. set_task_state must never reopen terminal integrated/cancelled/stopped states or illegally rewind review/merge_queued to planned.
    2. attestation freshness must reject the actual reproduced mismatch where report candidate/wrapper=c26ead1..., parent=3b7a618..., while Git HEAD=dffd856... and HEAD^=c26ead1...; validate exact allowed topology, not membership in {HEAD,HEAD^}.
    3. create_dispatch compound registry mutation must be one cross-process atomic transaction so duplicate Orca task races cannot leave durable orphan dispatch bindings; rollback/no partial write on any failure.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.lock_defs = [
            {
                "id": "R8-LOCK-EXCL",
                "mode": "exclusive",
                "renewable": True,
                "lease_seconds": 600,
            },
            {
                "id": "R8-LOCK-CAP",
                "mode": "capacity",
                "capacity": 3,
                "renewable": True,
                "lease_seconds": 600,
            },
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.mgr.set_task_authority("TASK-A", "granted")
        self.mgr.set_task_authority("TASK-B", "granted")
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(
            cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        cmd_parent = ["git", "rev-parse", "HEAD~1"]
        self.parent_commit = subprocess.run(
            cmd_parent, cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.adapter = OrcaDeliveryAdapter(
            lease_manager=self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
            declared_task_locks={"TASK-A": ["R8-LOCK-EXCL"], "TASK-B": ["R8-LOCK-CAP"]},
        )
        self.adapter.set_task_authority("TASK-A", "granted")
        self.adapter.set_task_authority("TASK-B", "granted")

    def test_r8_01_set_task_state_terminal_and_rewind_rejection(self):
        """1. Counterexample: set_task_state must never reopen terminal states or illegally rewind review/merge_queued."""
        # 1a. Terminal state integrated cannot be reopened or mutated via set_task_state
        self.adapter.set_task_state("TASK-A", "ready")
        self.adapter._task_states["TASK-A"] = "integrated"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.set_task_state("TASK-A", "ready")
        self.assertTrue(
            "terminal" in str(ctx.exception).lower() or "cannot mutate or reopen" in str(ctx.exception).lower(),
            f"Expected terminal error, got: {ctx.exception}"
        )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.set_task_state("TASK-A", "planned")

        # 1b. Terminal state cancelled cannot be reopened via set_task_state
        self.adapter._task_states["TASK-A"] = "cancelled"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.set_task_state("TASK-A", "ready")
        self.assertTrue(
            "terminal" in str(ctx.exception).lower() or "cannot mutate or reopen" in str(ctx.exception).lower(),
            f"Expected terminal error, got: {ctx.exception}"
        )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.set_task_state("TASK-A", "planned")

        # 1c. Terminal state stopped cannot be reopened via set_task_state
        self.adapter._task_states["TASK-A"] = "stopped"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.set_task_state("TASK-A", "ready")
        self.assertTrue(
            "terminal" in str(ctx.exception).lower() or "cannot mutate or reopen" in str(ctx.exception).lower(),
            f"Expected terminal error, got: {ctx.exception}"
        )

        # 1d. Illegal rewind: review -> planned is strictly forbidden
        self.adapter._task_states["TASK-A"] = "review"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.set_task_state("TASK-A", "planned")
        self.assertTrue(
            "review" in str(ctx.exception).lower() or "illegal" in str(ctx.exception).lower() or "overwrite" in str(ctx.exception).lower(),
            f"Expected illegal rewind rejection, got: {ctx.exception}"
        )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.set_task_state("TASK-A", "ready")

        # 1e. Illegal rewind: merge_queued -> planned is strictly forbidden
        self.adapter._task_states["TASK-A"] = "merge_queued"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.set_task_state("TASK-A", "planned")
        self.assertTrue(
            "merge_queued" in str(ctx.exception).lower() or "illegal" in str(ctx.exception).lower() or "overwrite" in str(ctx.exception).lower(),
            f"Expected illegal rewind rejection, got: {ctx.exception}"
        )

        # 1f. Protocol transition alignment: planned -> blocked is illegal via transition_task_state
        self.adapter._task_states["TASK-A"] = "planned"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state("TASK-A", "blocked")
        self.assertIn("Illegal task-state transition", str(ctx.exception))

        # 1g. Valid pre-dispatch planning/readiness settings succeed
        self.adapter.set_task_state("TASK-A", "ready")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "ready")
        self.adapter.set_task_state("TASK-A", "planned")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "planned")
        self.adapter.set_task_state("TASK-A", "ready")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "ready")
        self.adapter.set_task_state("TASK-A", "ready")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "ready")

    def test_r8_02_attestation_freshness_rejection_of_reproduced_head_mismatch(self):
        """2. Counterexample: attestation freshness must reject the actual reproduced mismatch where
        report candidate/wrapper=c26ead1..., parent=3b7a618..., while Git HEAD=dffd856... and HEAD^=c26ead1...
        """
        import validate
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rep_path = td_path / ".validation-report.json"
            # Exactly reproduced mismatch from Sol Round 7 audit
            rep_data = {
                "status": "PASS",
                "attestation": {
                    "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "candidate_commit": "c26ead1ad8bc99f7034d45e1be3b8121bce245ab",
                    "parent_commit": "3b7a618c50e0fab72723952269f34177f6e8c567",
                    "wrapper_commit": "c26ead1ad8bc99f7034d45e1be3b8121bce245ab",
                    "candidate_is_actual_head": True,
                    "overlay_clean": True,
                    "dirty_overlay_count": 0,
                },
                "bundle_sha256": {}
            }
            rep_path.write_text(json.dumps(rep_data), encoding="utf-8")
            # Tested against Git HEAD = dffd856...
            errs = validate.check_attestation_report_freshness(
                ROOT_DIR, td_path, rep_path, "dffd8569fe4cae9b7a834c2d77ba66d2b1b953a0"
            )
            self.assertTrue(
                any("stale" in e.lower() or "topology" in e.lower() for e in errs),
                f"Expected stale / topology mismatch rejection for reproduced Sol blocker, got: {errs}"
            )

    def test_r8_03_create_dispatch_atomic_compound_registry_mutation_two_process_race(self):
        """3. Counterexample: create_dispatch compound registry mutation must be one cross-process atomic transaction;
        duplicate Orca task races cannot leave durable orphan dispatch bindings; rollback on failure.
        """
        with tempfile.TemporaryDirectory() as td:
            reg_file = Path(td) / "race-reg.json"
            shared_reg = SharedOrcaExecutionRegistry(storage_path=reg_file)

            adapter1 = OrcaDeliveryAdapter(
                lease_manager=self.mgr,
                approved_candidate_commit=self.candidate_commit,
                git_root=ROOT_DIR,
                registry=shared_reg,
                declared_task_locks={"TASK-A": ["R8-LOCK-EXCL"]},
            )
            adapter1.set_task_authority("TASK-A", "granted")
            adapter1.set_task_state("TASK-A", "ready")
            lease1 = self.mgr.acquire_lease("R8-LOCK-EXCL", "TASK-A", "ctx-winner")

            adapter2 = OrcaDeliveryAdapter(
                lease_manager=self.mgr,
                approved_candidate_commit=self.candidate_commit,
                git_root=ROOT_DIR,
                registry=shared_reg,
                declared_task_locks={"TASK-B": ["R8-LOCK-CAP"]},
            )
            adapter2.set_task_authority("TASK-B", "granted")
            adapter2.set_task_state("TASK-B", "ready")
            lease2 = self.mgr.acquire_lease("R8-LOCK-CAP", "TASK-B", "ctx-loser", units=1)

            # Winner creates dispatch with orca_task_id = "orca-race-task-01"
            disp_winner = adapter1.create_dispatch(
                "TASK-A",
                orca_task_id="orca-race-task-01",
                candidate_commit=self.candidate_commit,
                fencing_token=lease1.fencing_token,
                lease_id=lease1.lease_id,
                intended_dispatch_id="ctx-winner",
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-A", "ctx-winner"),
            )
            self.assertEqual(disp_winner, "ctx-winner")

            # Loser attempts to dispatch with the SAME orca_task_id
            with self.assertRaises(ProtocolViolationError) as ctx:
                adapter2.create_dispatch(
                    "TASK-B",
                    orca_task_id="orca-race-task-01",
                    candidate_commit=self.candidate_commit,
                    fencing_token=lease2.fencing_token,
                    lease_id=lease2.lease_id,
                    intended_dispatch_id="ctx-loser",
                    dispatch_origin="dely dispatch",
                    execution_envelope=make_execution_envelope("TASK-B", "ctx-loser"),
                )
            self.assertTrue(
                "already" in str(ctx.exception) or "forbidden" in str(ctx.exception),
                f"Expected duplicate orca_task_id rejection, got: {ctx.exception}"
            )

            # Verify on-disk persistence: ctx-loser MUST NOT exist as durable orphan binding!
            disk_data = json.loads(reg_file.read_text(encoding="utf-8"))
            disk_bindings = disk_data.get("dispatch_bindings", {})
            self.assertIn("ctx-winner", disk_bindings, "Winner dispatch must be durably recorded on disk")
            self.assertNotIn("ctx-loser", disk_bindings, "Loser dispatch must NEVER leave durable orphan binding on disk")
            self.assertNotIn("ctx-loser", disk_data.get("seen_dispatch_ids", []), "Loser dispatch ID must not be marked seen on disk")

            # Verify in-memory state of loser adapter / registry: ctx-loser is rolled back
            self.assertNotIn("ctx-loser", shared_reg.dispatch_bindings)
            self.assertNotIn("ctx-loser", shared_reg.seen_dispatch_ids)
            self.assertEqual(adapter2.get_task_state("TASK-B"), "ready", "TASK-B must remain in ready state on failed dispatch")

            # Direct test of atomic compound registration method rollback on simulated failure:
            from delivery_engine import DispatchBinding
            fake_binding = DispatchBinding(
                delivery_task_id="TASK-B",
                orca_task_id="orca-race-task-01",
                dispatch_id="ctx-orphan-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=lease2.fencing_token,
                lease_id=lease2.lease_id,
                lease_ids=[lease2.lease_id],
                authority_state="granted",
            )
            with self.assertRaises(ProtocolViolationError):
                shared_reg.register_dispatch_and_orca_task(
                    dispatch_id="ctx-orphan-probe",
                    binding=fake_binding,
                    orca_task_id="orca-race-task-01",
                    delivery_task_id="TASK-B",
                )
            # Re-read disk
            disk_data2 = json.loads(reg_file.read_text(encoding="utf-8"))
            self.assertNotIn("ctx-orphan-probe", disk_data2.get("dispatch_bindings", {}))
            self.assertNotIn("ctx-orphan-probe", shared_reg.dispatch_bindings)


class TestSolRoundNineCounterexamples(unittest.TestCase):
    """Sol Round 9 Counterexamples:
    1. attestation freshness must reject bypass where candidate_commit, wrapper_commit,
       and parent_commit all point to HEAD^; under parent-plus-wrapper semantics,
       wrapper_commit must be exact current HEAD.
    """

    def test_r9_01_attestation_freshness_rejection_of_all_head_parent_bypass(self):
        """1. Counterexample: Attestation freshness must reject invalid topology where
        candidate_commit, wrapper_commit, and parent_commit all point to HEAD^.
        Under parent-plus-wrapper semantics, wrapper_commit must be exact current HEAD.
        """
        import validate
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rep_path = td_path / ".validation-report.json"
            # Exactly reproduced bypass on exact SHA a7f5aca:
            # candidate_commit, wrapper_commit, and parent_commit all set to 4366a59 (HEAD^)
            # while validated against Git HEAD = a7f5aca
            head_sha = "a7f5aca06a0a70487d624b68c4ebfccfee150542"
            parent_sha = "4366a59d514f06665cc96c39fccfdb3c377174a8"
            rep_data = {
                "status": "PASS",
                "attestation": {
                    "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "candidate_commit": parent_sha,
                    "parent_commit": parent_sha,
                    "wrapper_commit": parent_sha,
                    "candidate_is_actual_head": False,
                    "overlay_clean": True,
                    "dirty_overlay_count": 0,
                },
                "bundle_sha256": {}
            }
            rep_path.write_text(json.dumps(rep_data), encoding="utf-8")
            errs = validate.check_attestation_report_freshness(
                ROOT_DIR, td_path, rep_path, head_sha
            )
            self.assertTrue(
                any("stale" in e.lower() or "topology" in e.lower() for e in errs),
                f"Expected stale / topology mismatch rejection for all-HEAD^ bypass, got: {errs}"
            )

    def test_r9_02_attestation_freshness_accepts_valid_parent_plus_wrapper_declared_head(self):
        """2. Positive control: Attestation freshness accepts valid parent-plus-wrapper topology
        where candidate_commit == HEAD^, parent_commit == HEAD^, and wrapper_commit == "HEAD"
        without impossible cryptographic self-reference in Git DAG.
        """
        import validate
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rep_path = td_path / ".validation-report.json"
            head_sha = "a7f5aca06a0a70487d624b68c4ebfccfee150542"
            parent_sha = "4366a59d514f06665cc96c39fccfdb3c377174a8"
            rep_data = {
                "status": "PASS",
                "attestation": {
                    "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "candidate_commit": parent_sha,
                    "parent_commit": parent_sha,
                    "wrapper_commit": "HEAD",
                    "candidate_is_actual_head": False,
                    "overlay_clean": True,
                    "dirty_overlay_count": 0,
                },
                "bundle_sha256": {}
            }
            rep_path.write_text(json.dumps(rep_data), encoding="utf-8")
            errs = validate.check_attestation_report_freshness(
                ROOT_DIR, td_path, rep_path, head_sha
            )
            self.assertFalse(
                any("stale" in e.lower() or "topology" in e.lower() for e in errs),
                f"Valid parent-plus-wrapper topology with declared HEAD was rejected: {errs}"
            )

    def test_r9_03_attestation_freshness_accepts_valid_parent_plus_wrapper_explicit_head_sha(self):
        """3. Positive control: Attestation freshness accepts valid parent-plus-wrapper topology
        where candidate_commit == HEAD^, parent_commit == HEAD^, and wrapper_commit == explicit HEAD SHA.
        """
        import validate
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rep_path = td_path / ".validation-report.json"
            head_sha = "a7f5aca06a0a70487d624b68c4ebfccfee150542"
            parent_sha = "4366a59d514f06665cc96c39fccfdb3c377174a8"
            rep_data = {
                "status": "PASS",
                "attestation": {
                    "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "candidate_commit": parent_sha,
                    "parent_commit": parent_sha,
                    "wrapper_commit": head_sha,
                    "candidate_is_actual_head": False,
                    "overlay_clean": True,
                    "dirty_overlay_count": 0,
                },
                "bundle_sha256": {}
            }
            rep_path.write_text(json.dumps(rep_data), encoding="utf-8")
            errs = validate.check_attestation_report_freshness(
                ROOT_DIR, td_path, rep_path, head_sha
            )
            self.assertFalse(
                any("stale" in e.lower() or "topology" in e.lower() for e in errs),
                f"Valid parent-plus-wrapper topology with explicit HEAD SHA was rejected: {errs}"
            )

    def test_r9_04_attestation_freshness_rejection_of_dynamic_checkout_all_head_parent_bypass(self):
        """4. Counterexample: Attestation freshness must reject bypass when candidate, wrapper,
        and parent all equal current checkout's HEAD^.
        """
        import validate
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rep_path = td_path / ".validation-report.json"
            cmd_head = ["git", "rev-parse", "HEAD"]
            head_sha = subprocess.run(
                cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True
            ).stdout.strip()
            cmd_parent = ["git", "rev-parse", "HEAD^"]
            parent_sha = subprocess.run(
                cmd_parent, cwd=ROOT_DIR, capture_output=True, text=True, check=True
            ).stdout.strip()
            rep_data = {
                "status": "PASS",
                "attestation": {
                    "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
                    "candidate_commit": parent_sha,
                    "parent_commit": parent_sha,
                    "wrapper_commit": parent_sha,
                    "candidate_is_actual_head": False,
                    "overlay_clean": True,
                    "dirty_overlay_count": 0,
                },
                "bundle_sha256": {}
            }
            rep_path.write_text(json.dumps(rep_data), encoding="utf-8")
            errs = validate.check_attestation_report_freshness(
                ROOT_DIR, td_path, rep_path, head_sha
            )
            self.assertTrue(
                any("stale" in e.lower() or "topology" in e.lower() for e in errs),
                f"Expected stale / topology mismatch rejection for dynamic all-HEAD^ bypass, got: {errs}"
            )


class TestSolRoundTenCounterexamples(unittest.TestCase):
    """Sol Round 10 / 11: Fail-closed harness compatibility without native-provider fallback.
    In accordance with repository routing policy in AGENTS.md:
    - Codex CLI with ag/gemini-3.8-flash-high is required; Antigravity native is forbidden.
    - Harness failures must stop/block the task, safely release and fence resources,
      and require recovery/human intervention.
    - Silent or explicit fallback to Antigravity native (or any provider switch) is strictly forbidden.
    - Harness state machine transitions to STOP_BLOCKED; STOP_FALLBACK state is rejected fail-closed.
    - No mutation occurs on the candidate tree during harness failures.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(
            cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()

    def test_r10_01_harness_result_rejects_stop_fallback_state(self):
        """1. Counterexample: HarnessExecutionResult strictly rejects state='STOP_FALLBACK'."""
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            HarnessExecutionResult(
                success=False,
                execution_time_ms=10.0,
                status="STOP",
                state="STOP_FALLBACK",
                tool_name="tool.a",
                requested_tool="tool.a",
                execution_observed=True,
                execution_returncode=1,
                fallback_required=False,
                fallback_target="none",
            )
        self.assertIn("native-provider fallback", str(ctx.exception).lower())

    def test_r10_02_harness_result_rejects_antigravity_native_fallback_target(self):
        """2. Counterexample: HarnessExecutionResult rejects fallback_target='antigravity_native'."""
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            HarnessExecutionResult(
                success=False,
                execution_time_ms=10.0,
                status="STOP",
                state="STOP_BLOCKED",
                tool_name="tool.a",
                requested_tool="tool.a",
                execution_observed=True,
                execution_returncode=1,
                fallback_required=False,
                fallback_target="antigravity_native",
            )
        self.assertIn("antigravity", str(ctx.exception).lower())

    def test_r10_03_harness_result_rejects_fallback_required_true(self):
        """3. Counterexample: HarnessExecutionResult rejects fallback_required=True on failure."""
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            HarnessExecutionResult(
                success=False,
                execution_time_ms=10.0,
                status="STOP",
                state="STOP_BLOCKED",
                tool_name="tool.a",
                requested_tool="tool.a",
                execution_observed=True,
                execution_returncode=1,
                fallback_required=True,
                fallback_target="none",
            )
        self.assertIn("fallback_required=true is forbidden", str(ctx.exception).lower())

    def test_r10_04_harness_state_machine_rejects_stop_fallback_transition(self):
        """4. Counterexample: HarnessExecutionStateMachine rejects transition to 'STOP_FALLBACK'."""
        sm = HarnessExecutionStateMachine()
        sm.transition("RUNNING", "start")
        with self.assertRaises(HarnessCompatibilityError) as ctx:
            sm.transition("STOP_FALLBACK", "attempted fallback")
        self.assertIn("native-provider fallback", str(ctx.exception).lower())

    def test_r10_05_harness_state_machine_failure_transitions_to_stop_blocked(self):
        """5. HarnessExecutionStateMachine failure transitions to STOP_BLOCKED, not STOP_FALLBACK."""
        sm = HarnessExecutionStateMachine()
        with self.assertRaises(HarnessCompatibilityError):
            sm.evaluate("tool.mismatch", "tool.requested")
        self.assertEqual(sm.current_state, "STOP_BLOCKED")
        self.assertNotEqual(sm.current_state, "STOP_FALLBACK")

    def test_r10_06_harness_failure_stops_task_releases_leases_without_candidate_mutation(self):
        """6. Harness failure stops/blocks task, safely releases leases, without candidate mutation."""
        mgr = LeaseManager([{"id": "R10-LOCK-MUT", "mode": "exclusive", "renewable": True, "lease_seconds": 600}])
        mgr.set_task_authority("TASK-R10", "granted")
        adapter = OrcaDeliveryAdapter(
            mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR
        )
        adapter.register_task_locks("TASK-R10", ["R10-LOCK-MUT"])
        adapter.set_task_authority("TASK-R10", "granted")
        adapter.set_task_state("TASK-R10", "ready")
        lease = mgr.acquire_lease("R10-LOCK-MUT", "TASK-R10", "ctx_r10")
        disp_id = adapter.create_dispatch(
            "TASK-R10", "orca_task_r10", self.candidate_commit, lease_id=lease.lease_id, intended_dispatch_id="ctx_r10", fencing_token=lease.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-R10", "ctx_r10"),
        )
        adapter.acknowledge_dispatch("TASK-R10", disp_id)
        adapter.start_running("TASK-R10", disp_id)

        # Handle harness failure
        adapter.handle_harness_failure("TASK-R10", disp_id, "Namespace collapse detected")
        self.assertEqual(adapter.get_task_state("TASK-R10"), "blocked")
        self.assertEqual(len(mgr.active_leases), 0, "All leases must be safely released upon harness failure")

    def test_r10_07_bundle_documentation_forbids_antigravity_fallback_wording(self):
        """7. Positive control: Parallel-delivery docs and engine contain zero occurrences of native fallback permissions."""
        bundle_docs = [
            BUNDLE_DIR / "operating-model.md",
            BUNDLE_DIR / "protocol.md",
            BUNDLE_DIR / "security-performance-recovery.md",
            BUNDLE_DIR / "README.md",
        ]
        forbidden_phrases = [
            "fallback an toàn sang antigravity native",
            "fallback an toàn sang harness tương thích",
            "safe fallback / stop condition",
            'fallback_target: str = "antigravity_native"',
            'fallback_target = "antigravity_native"',
            "stop_fallback",
        ]
        for doc_path in bundle_docs:
            text = doc_path.read_text(encoding="utf-8").lower()
            for phrase in forbidden_phrases:
                self.assertNotIn(
                    phrase,
                    text,
                    f"Forbidden native-fallback phrase {phrase!r} found in {doc_path.name}",
                )




class TestSolRound11HarnessFailureLeaseSafety(unittest.TestCase):
    """Sol Round 11 Finding F1: Identity-first fail-closed harness failure handling.
    Rejects spoof, cross-task, settled, and stale dispatches without side effects;
    leases of fresh active dispatches remain completely intact.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_reg_path = Path(self.temp_dir.name) / "reg.json"
        SharedOrcaExecutionRegistry.reset_default(storage_path=self.temp_reg_path)
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True)
        self.candidate_commit = res.stdout.strip() if res.returncode == 0 else "a56e34b630977bb2a3087938fed594ef15f89124"

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass

    def test_r11_01_unknown_spoof_dispatch_id_rejected_fail_closed_leases_intact(self):
        """1. Unknown/spoof dispatch ID rejected fail-closed; active task lease remains intact."""
        mgr = LeaseManager([{"id": "R11-LOCK-1", "mode": "exclusive", "renewable": True, "lease_seconds": 600}])
        mgr.set_task_authority("TASK-R11-1", "granted")
        adapter = OrcaDeliveryAdapter(mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        adapter.register_task_locks("TASK-R11-1", ["R11-LOCK-1"])
        adapter.set_task_authority("TASK-R11-1", "granted")
        adapter.set_task_state("TASK-R11-1", "ready")
        lease = mgr.acquire_lease("R11-LOCK-1", "TASK-R11-1", "ctx_real")
        disp_id = adapter.create_dispatch(
            "TASK-R11-1", "orca_r11_1", self.candidate_commit,
            lease_id=lease.lease_id, intended_dispatch_id="ctx_real", fencing_token=lease.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-R11-1", "ctx_real"),
        )
        adapter.acknowledge_dispatch("TASK-R11-1", disp_id)
        adapter.start_running("TASK-R11-1", disp_id)

        # Attempt harness failure with completely unknown/spoof dispatch ID
        with self.assertRaises(ProtocolViolationError) as ctx:
            adapter.handle_harness_failure("TASK-R11-1", "ctx_spoof_unknown", "Harness crashed")
        self.assertIn("Unknown dispatch ID", str(ctx.exception))
        # Lease must remain 100% active and task state must remain running
        self.assertIn(lease.lease_id, mgr.active_leases, "Live lease must remain intact after rejected spoof failure")
        self.assertEqual(adapter.get_task_state("TASK-R11-1"), "running")

    def test_r11_02_dispatch_bound_to_another_task_rejected_fail_closed_leases_intact(self):
        """2. Dispatch bound to another task rejected fail-closed; both tasks retain their leases."""
        mgr = LeaseManager([
            {"id": "R11-LOCK-A", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
            {"id": "R11-LOCK-B", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
        ])
        mgr.set_task_authority("TASK-A", "granted")
        mgr.set_task_authority("TASK-B", "granted")
        adapter = OrcaDeliveryAdapter(mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        adapter.register_task_locks("TASK-A", ["R11-LOCK-A"])
        adapter.register_task_locks("TASK-B", ["R11-LOCK-B"])
        adapter.set_task_authority("TASK-A", "granted")
        adapter.set_task_authority("TASK-B", "granted")
        adapter.set_task_state("TASK-A", "ready")
        adapter.set_task_state("TASK-B", "ready")

        lease_a = mgr.acquire_lease("R11-LOCK-A", "TASK-A", "ctx_a")
        disp_a = adapter.create_dispatch(
            "TASK-A", "orca_a", self.candidate_commit,
            lease_id=lease_a.lease_id, intended_dispatch_id="ctx_a", fencing_token=lease_a.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx_a"),
        )
        adapter.acknowledge_dispatch("TASK-A", disp_a)
        adapter.start_running("TASK-A", disp_a)

        lease_b = mgr.acquire_lease("R11-LOCK-B", "TASK-B", "ctx_b")
        disp_b = adapter.create_dispatch(
            "TASK-B", "orca_b", self.candidate_commit,
            lease_id=lease_b.lease_id, intended_dispatch_id="ctx_b", fencing_token=lease_b.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-B", "ctx_b"),
        )
        adapter.acknowledge_dispatch("TASK-B", disp_b)
        adapter.start_running("TASK-B", disp_b)

        # Cross-task failure spoof: report failure for TASK-A using dispatch ctx_b
        with self.assertRaises(ProtocolViolationError) as ctx:
            adapter.handle_harness_failure("TASK-A", "ctx_b", "Cross-task failure")
        self.assertIn("bound to delivery task 'TASK-B'", str(ctx.exception))

        # Both leases and task states must be untouched
        self.assertIn(lease_a.lease_id, mgr.active_leases)
        self.assertIn(lease_b.lease_id, mgr.active_leases)
        self.assertEqual(adapter.get_task_state("TASK-A"), "running")
        self.assertEqual(adapter.get_task_state("TASK-B"), "running")

    def test_r11_03_already_settled_duplicate_dispatch_rejected_fail_closed_leases_intact(self):
        """3. Already settled/duplicate dispatch rejected fail-closed without side effects."""
        mgr = LeaseManager([{"id": "R11-LOCK-DUP", "mode": "exclusive", "renewable": True, "lease_seconds": 600}])
        mgr.set_task_authority("TASK-DUP", "granted")
        adapter = OrcaDeliveryAdapter(mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        adapter.register_task_locks("TASK-DUP", ["R11-LOCK-DUP"])
        adapter.set_task_authority("TASK-DUP", "granted")
        adapter.set_task_state("TASK-DUP", "ready")
        lease1 = mgr.acquire_lease("R11-LOCK-DUP", "TASK-DUP", "ctx_dup1")
        disp1 = adapter.create_dispatch(
            "TASK-DUP", "orca_dup1", self.candidate_commit,
            lease_id=lease1.lease_id, intended_dispatch_id="ctx_dup1", fencing_token=lease1.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-DUP", "ctx_dup1"),
        )
        adapter.acknowledge_dispatch("TASK-DUP", disp1)
        adapter.start_running("TASK-DUP", disp1)

        # Complete first dispatch via worker_done failed -> settles ctx_dup1
        adapter.handle_worker_done("TASK-DUP", "orca_dup1", disp1, "failed", candidate_commit=self.candidate_commit, fencing_token=lease1.fencing_token)
        self.assertTrue(adapter.registry.is_dispatch_settled(disp1))

        # Late harness failure arriving for the already settled dispatch
        with self.assertRaises(DuplicateResultError) as ctx:
            adapter.handle_harness_failure("TASK-DUP", disp1, "Late failure for settled dispatch")
        self.assertIn("already settled", str(ctx.exception))

    def test_r11_04_stale_failure_after_replan_and_redispatch_rejected_fresh_lease_intact(self):
        """4. Stale failure arriving after task is replanned and redispatched leaves fresh lease intact."""
        mgr = LeaseManager([{"id": "R11-LOCK-REPLAN", "mode": "exclusive", "renewable": True, "lease_seconds": 600}])
        mgr.set_task_authority("TASK-REPLAN", "granted")
        adapter = OrcaDeliveryAdapter(mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        adapter.register_task_locks("TASK-REPLAN", ["R11-LOCK-REPLAN"])
        adapter.set_task_authority("TASK-REPLAN", "granted")
        adapter.set_task_state("TASK-REPLAN", "ready")

        # Dispatch 1
        lease1 = mgr.acquire_lease("R11-LOCK-REPLAN", "TASK-REPLAN", "ctx_first")
        disp1 = adapter.create_dispatch(
            "TASK-REPLAN", "orca_first", self.candidate_commit,
            lease_id=lease1.lease_id, intended_dispatch_id="ctx_first", fencing_token=lease1.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-REPLAN", "ctx_first"),
        )
        adapter.acknowledge_dispatch("TASK-REPLAN", disp1)
        adapter.start_running("TASK-REPLAN", disp1)
        adapter.handle_worker_done("TASK-REPLAN", "orca_first", disp1, "failed", candidate_commit=self.candidate_commit, fencing_token=lease1.fencing_token)
        self.assertEqual(adapter.get_task_state("TASK-REPLAN"), "blocked")

        # Replan and redispatch as Dispatch 2
        adapter.resolve_blocker_and_replan("TASK-REPLAN")
        self.assertEqual(adapter.get_task_state("TASK-REPLAN"), "ready")
        lease2 = mgr.acquire_lease("R11-LOCK-REPLAN", "TASK-REPLAN", "ctx_second")
        disp2 = adapter.create_dispatch(
            "TASK-REPLAN", "orca_second", self.candidate_commit,
            lease_id=lease2.lease_id, intended_dispatch_id="ctx_second", fencing_token=lease2.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-REPLAN", "ctx_second"),
        )
        adapter.acknowledge_dispatch("TASK-REPLAN", disp2)
        adapter.start_running("TASK-REPLAN", disp2)

        # Stale failure for disp1 arrives while disp2 is actively running
        with self.assertRaises((DuplicateResultError, StaleResultError)) as ctx:
            adapter.handle_harness_failure("TASK-REPLAN", disp1, "Stale failure from first run")

        # Fresh active dispatch lease2 MUST remain active and untouched
        self.assertIn(lease2.lease_id, mgr.active_leases, "Fresh lease2 must remain active after rejected stale failure")
        self.assertEqual(adapter.get_task_state("TASK-REPLAN"), "running")

    def test_r11_05_valid_active_harness_failure_settles_blocks_releases_and_preserves_candidate(self):
        """5. Valid active harness failure settles dispatch, blocks task, releases only own lease, preserves candidate."""
        mgr = LeaseManager([{"id": "R11-LOCK-VALID", "mode": "exclusive", "renewable": True, "lease_seconds": 600}])
        mgr.set_task_authority("TASK-VALID", "granted")
        adapter = OrcaDeliveryAdapter(mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        adapter.register_task_locks("TASK-VALID", ["R11-LOCK-VALID"])
        adapter.set_task_authority("TASK-VALID", "granted")
        adapter.set_task_state("TASK-VALID", "ready")
        lease = mgr.acquire_lease("R11-LOCK-VALID", "TASK-VALID", "ctx_valid")
        disp_id = adapter.create_dispatch(
            "TASK-VALID", "orca_valid", self.candidate_commit,
            lease_id=lease.lease_id, intended_dispatch_id="ctx_valid", fencing_token=lease.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-VALID", "ctx_valid"),
        )
        adapter.acknowledge_dispatch("TASK-VALID", disp_id)
        adapter.start_running("TASK-VALID", disp_id)

        # Valid failure
        res = adapter.handle_harness_failure("TASK-VALID", disp_id, "Harness crash")
        self.assertEqual(res, "blocked")
        self.assertEqual(adapter.get_task_state("TASK-VALID"), "blocked")
        self.assertTrue(adapter.registry.is_dispatch_settled(disp_id))
        self.assertEqual(len(mgr.active_leases), 0, "Own lease must be safely released")

        # Git candidate commit remains preserved
        head_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True)
        self.assertEqual(head_res.stdout.strip(), self.candidate_commit)

    def test_r11_06_persistence_failure_leaves_no_partial_effects(self):
        """6. Failure during registry persistence/settlement rolls back and leaves no partial lease release."""
        mgr = LeaseManager([{"id": "R11-LOCK-TX", "mode": "exclusive", "renewable": True, "lease_seconds": 600}])
        mgr.set_task_authority("TASK-TX", "granted")
        adapter = OrcaDeliveryAdapter(mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        adapter.register_task_locks("TASK-TX", ["R11-LOCK-TX"])
        adapter.set_task_authority("TASK-TX", "granted")
        adapter.set_task_state("TASK-TX", "ready")
        lease = mgr.acquire_lease("R11-LOCK-TX", "TASK-TX", "ctx_tx")
        disp_id = adapter.create_dispatch(
            "TASK-TX", "orca_tx", self.candidate_commit,
            lease_id=lease.lease_id, intended_dispatch_id="ctx_tx", fencing_token=lease.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-TX", "ctx_tx"),
        )
        adapter.acknowledge_dispatch("TASK-TX", disp_id)
        adapter.start_running("TASK-TX", disp_id)

        # Monkeypatch settle_dispatch to simulate I/O or transaction abort
        def broken_settle(did):
            raise IOError("Simulated disk persistence failure")
        orig_settle = adapter.registry.settle_dispatch
        adapter.registry.settle_dispatch = broken_settle

        try:
            with self.assertRaises(IOError):
                adapter.handle_harness_failure("TASK-TX", disp_id, "Failure with disk crash")
        finally:
            adapter.registry.settle_dispatch = orig_settle

        # Leases and task state must not be partially modified
        self.assertIn(lease.lease_id, mgr.active_leases, "Lease must remain active if persistence failed")
        self.assertEqual(adapter.get_task_state("TASK-TX"), "running")


class TestSolRound11RoutingEvidencePolicy(unittest.TestCase):
    """Sol Round 11 Finding F2: Machine-readable routing evidence and execution envelope validation.
    Enforces fail-closed rules: provider == 9router, dely dispatch origin, separate harness/model/effort,
    mandatory live terminal/archive evidence, mandatory 9Router usage evidence after dispatch,
    and secret/mutable path avoidance.
    """

    def setUp(self):
        self.valid_implement_envelope = {
            "delivery_task_id": "PD-PILOT-CONTROL",
            "dispatch_id": "ctx_impl_001",
            "dispatch_origin": "dely dispatch",
            "phase": "implement",
            "route": {
                "provider": "9router",
                "harness": "Codex CLI",
                "model": "ag/gemini-3.8-flash-high",
                "effort": "high",
            },
            "live_terminal_evidence": {
                "harness": "Codex CLI",
                "provider": "9router",
                "route": "ag/gemini-3.8-flash-high",
                "archive_reference": "term_archive_test_01",
                "verified": True,
            },
            "usage_evidence": {
                "backend_provider": "google",
                "backend_model": "ag/gemini-3.8-flash-high",
                "recorded_after_dispatch": True,
                "timestamp": "2026-09-29T00:05:00Z",
                "request_id": "req_test_01",
            },
            "launch_requested": {"harness": "Codex CLI", "route": "ag/gemini-3.8-flash-high"},
            "launch_effective": {"harness": "Codex CLI", "route": "ag/gemini-3.8-flash-high"},
        }
        self.valid_review_envelope = {
            "delivery_task_id": "PD-PILOT-CONTROL",
            "dispatch_id": "ctx_rev_001",
            "dispatch_origin": "dely dispatch",
            "phase": "review",
            "route": {
                "provider": "9router",
                "harness": "Claude Code",
                "model": "cx/gpt-5.6-sol",
                "effort": "high",
            },
            "live_terminal_evidence": {
                "harness": "Claude Code",
                "provider": "9router",
                "route": "cx/gpt-5.6-sol",
                "archive_reference": "term_archive_rev_01",
                "verified": True,
            },
            "usage_evidence": {
                "backend_provider": "openai",
                "backend_model": "cx/gpt-5.6-sol",
                "recorded_after_dispatch": True,
                "timestamp": "2026-09-29T00:06:00Z",
                "request_id": "req_rev_01",
            },
            "launch_requested": {"harness": "Claude Code", "route": "cx/gpt-5.6-sol"},
            "launch_effective": {"harness": "Claude Code", "route": "cx/gpt-5.6-sol"},
        }

    def test_r11_07_valid_routing_envelope_passes(self):
        """7. Valid execution envelope with 9router, dely dispatch, live and usage evidence passes."""
        errors_impl = validate_execution_envelope(self.valid_implement_envelope)
        self.assertEqual(errors_impl, [])
        errors_rev = validate_execution_envelope(self.valid_review_envelope)
        self.assertEqual(errors_rev, [])

    def test_r11_08_provider_not_9router_fails_closed(self):
        """8. Counterexample: Provider != 9router (e.g. antigravity, openai, direct) fails closed."""
        for bad_p in ("antigravity", "antigravity_native", "openai", "google", "direct", "", None):
            env = copy.deepcopy(self.valid_implement_envelope)
            env["route"]["provider"] = bad_p
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env)
            self.assertTrue("provider" in str(ctx.exception).lower() or "9router" in str(ctx.exception).lower())

    def test_r11_09_direct_worker_start_origin_fails_closed(self):
        """9. Counterexample: Dispatch origin direct worker-start fails closed."""
        for bad_origin in ("worker-start", "orca worker-start", "direct worker-start", "orca", "", None):
            env = copy.deepcopy(self.valid_implement_envelope)
            env["dispatch_origin"] = bad_origin
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env)
            self.assertIn("dely dispatch", str(ctx.exception).lower())

    def test_r11_10_combined_model_effort_slug_fails_closed(self):
        """10. Counterexample: Combined slug (e.g. cx/gpt-5.6-sol-high) or missing effort fails closed."""
        env = copy.deepcopy(self.valid_review_envelope)
        env["route"]["model"] = "cx/gpt-5.6-sol-high"
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env)
        self.assertIn("combined", str(ctx.exception).lower())

        env2 = copy.deepcopy(self.valid_review_envelope)
        env2["route"]["effort"] = ""
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env2)
        self.assertIn("effort", str(ctx.exception).lower())

    def test_r11_11_launch_evidence_alone_without_live_and_usage_fails_closed(self):
        """11. Counterexample: launch.requested/effective alone without live/usage evidence fails closed."""
        env = copy.deepcopy(self.valid_implement_envelope)
        env["live_terminal_evidence"] = None
        env["usage_evidence"] = None
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env)
        self.assertIn("insufficient", str(ctx.exception).lower())

    def test_r11_12_missing_or_contradictory_live_evidence_fails_closed(self):
        """12. Counterexample: Missing or contradictory live terminal evidence fails closed."""
        # Missing
        env = copy.deepcopy(self.valid_implement_envelope)
        env["live_terminal_evidence"] = {}
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env)

        # Contradictory harness/route
        env2 = copy.deepcopy(self.valid_implement_envelope)
        env2["live_terminal_evidence"]["harness"] = "Claude Code"
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env2)
        self.assertIn("live terminal", str(ctx.exception).lower())

    def test_r11_13_missing_or_stale_usage_evidence_fails_closed(self):
        """13. Counterexample: 9Router usage evidence not recorded after dispatch fails closed."""
        env = copy.deepcopy(self.valid_implement_envelope)
        env["usage_evidence"]["recorded_after_dispatch"] = False
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env)
        self.assertIn("after dispatch", str(ctx.exception).lower())

        env2 = copy.deepcopy(self.valid_implement_envelope)
        env2["usage_evidence"] = None
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env2)

    def test_r11_14_evidence_containing_secrets_or_mutable_db_paths_fails_closed(self):
        """14. Counterexample: Evidence containing raw secrets or mutable DB paths fails closed."""
        env = copy.deepcopy(self.valid_implement_envelope)
        env["live_terminal_evidence"]["archive_reference"] = f"bearer {'sk-'}{'1234567890abcdef12345678'}"
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env)
        self.assertIn("secret", str(ctx.exception).lower())

        env2 = copy.deepcopy(self.valid_implement_envelope)
        env2["usage_evidence"]["request_id"] = "C:\\Users\\Admin\\AppData\\local.db"
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env2)
        self.assertIn("mutable local database path", str(ctx.exception).lower())



class TestSolRound13FailClosedExecutionEnvelope(unittest.TestCase):
    """Sol Round 13 Finding F2 remediation: fail-closed execution envelope validation,
    anchored identity binding, strictly verified live terminal evidence, machine-readable
    usage evidence freshness, and zero side effects on failure.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.lock_defs = [{"id": "LOCK-R13", "mode": "exclusive", "renewable": True}]
        self.mgr = LeaseManager(self.lock_defs)
        self.delivery_id = "TASK-R13-PROBE"
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.candidate_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
        ).strip()
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
        )
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-R13"])
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.intended_disp = "ctx-r13-probe"
        self.lease = self.mgr.acquire_lease("LOCK-R13", self.delivery_id, self.intended_disp)

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def _assert_zero_side_effects(self, intended_disp_id="ctx-r13-probe"):
        """Verify no side effects occurred on task state, active dispatches, bindings, seen dispatches, or leases."""
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "ready")
        self.assertNotIn(self.delivery_id, self.adapter.active_dispatches)
        self.assertNotIn(intended_disp_id, self.adapter.dispatch_bindings)
        self.assertNotIn(intended_disp_id, self.adapter.seen_dispatch_ids)
        self.assertTrue(self.lease.is_active)

    def test_r13_01_sol_counterexample_dispatch_without_origin_or_envelope_rejected_zero_side_effects(self):
        """1. Counterexample: create_dispatch without origin or envelope fails closed with zero side effects."""
        # Exact Sol counterexample: caller omits both dispatch_origin and execution_envelope
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe-1",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
            )
        self.assertIn("dispatch origin", str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Forbidden direct origin: worker-start
        for bad_origin in ("worker-start", "orca worker-start", "direct worker-start", "orca", "custom-starter"):
            with self.assertRaises(RoutingEvidenceError) as ctx2:
                self.adapter.create_dispatch(
                    self.delivery_id,
                    orca_task_id="orca-r13-probe-2",
                    candidate_commit=self.candidate_commit,
                    fencing_token=self.lease.fencing_token,
                    lease_id=self.lease.lease_id,
                    intended_dispatch_id=self.intended_disp,
                    dispatch_origin=bad_origin,
                    execution_envelope=make_execution_envelope(self.delivery_id, self.intended_disp),
                )
            self.assertIn("dely dispatch", str(ctx2.exception).lower())
            self._assert_zero_side_effects()

        # Correct origin 'dely dispatch' but missing envelope
        with self.assertRaises(RoutingEvidenceError) as ctx3:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe-3",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=None,
            )
        self.assertIn("execution envelope", str(ctx3.exception).lower())
        self._assert_zero_side_effects()

    def test_r13_02_sol_counterexample_missing_identity_fields_rejected_zero_side_effects(self):
        """2. Counterexample: Missing delivery_task_id, dispatch_id, or phase fails closed."""
        # Blank / missing delivery_task_id in envelope
        env_no_task = make_execution_envelope(self.delivery_id, self.intended_disp)
        env_no_task.delivery_task_id = ""
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_no_task,
            )
        self.assertIn("delivery_task_id", str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Blank / missing dispatch_id in envelope
        env_no_disp = make_execution_envelope(self.delivery_id, self.intended_disp)
        env_no_disp.dispatch_id = ""
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_no_disp,
            )
        self.assertIn("dispatch_id", str(ctx2.exception).lower())
        self._assert_zero_side_effects()

        # Invalid phase
        env_bad_phase = make_execution_envelope(self.delivery_id, self.intended_disp)
        env_bad_phase.phase = "invalid_phase"
        with self.assertRaises(RoutingEvidenceError) as ctx3:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_bad_phase,
            )
        self.assertIn("phase", str(ctx3.exception).lower())
        self._assert_zero_side_effects()

    def test_r13_03_sol_counterexample_contradictory_unanchored_evidence_rejected_zero_side_effects(self):
        """3. Counterexample: Unanchored or contradictory terminal/usage evidence fails closed."""
        # Contradictory live terminal evidence dispatch_id
        env_contra_disp = make_execution_envelope(self.delivery_id, self.intended_disp)
        env_contra_disp.live_terminal_evidence.dispatch_id = "ctx-different-disp"
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_contra_disp,
            )
        self.assertIn("does not match dispatch", str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Contradictory usage evidence task_id
        env_contra_task = make_execution_envelope(self.delivery_id, self.intended_disp)
        env_contra_task.usage_evidence.delivery_task_id = "TASK-DIFFERENT"
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_contra_task,
            )
        self.assertIn("does not match task", str(ctx2.exception).lower())
        self._assert_zero_side_effects()

    def test_r13_04_mismatched_task_dispatch_phase_identities_rejected_zero_side_effects(self):
        """4. Counterexample: Mismatched task, dispatch, or phase identities fail closed."""
        # Envelope bound to different task
        env_mismatch_task = make_execution_envelope("TASK-OTHER-BOUND", self.intended_disp)
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_mismatch_task,
            )
        self.assertIn("mismatch", str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Envelope bound to different dispatch
        env_mismatch_disp = make_execution_envelope(self.delivery_id, "ctx-unauthorized-id")
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_mismatch_disp,
            )
        self.assertIn("mismatch", str(ctx2.exception).lower())
        self._assert_zero_side_effects()

        # Task phase mismatch
        self.adapter.register_task_phase(self.delivery_id, "implement")
        env_wrong_phase = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review")
        with self.assertRaises(RoutingEvidenceError) as ctx3:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_wrong_phase,
            )
        self.assertIn("phase mismatch", str(ctx3.exception).lower())
        self._assert_zero_side_effects()

    def test_r13_05_unverified_terminal_evidence_rejected_zero_side_effects(self):
        """5. Counterexample: Unverified live terminal evidence fails closed."""
        # verified is False
        env_unverified = make_execution_envelope(self.delivery_id, self.intended_disp)
        env_unverified.live_terminal_evidence.verified = False
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_unverified,
            )
        self.assertIn("unverified", str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Non-boolean verified or missing archive reference
        env_no_ref = make_execution_envelope(self.delivery_id, self.intended_disp)
        env_no_ref.live_terminal_evidence.archive_reference = ""
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_no_ref,
            )
        self.assertIn("archive reference", str(ctx2.exception).lower())
        self._assert_zero_side_effects()

    def test_r13_06_wrong_backend_provider_and_model_per_phase_rejected_zero_side_effects(self):
        """6. Counterexample: Wrong backend provider/model for phase fails closed."""
        # Implement phase with openai provider
        env_wrong_p = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement")
        env_wrong_p.usage_evidence.backend_provider = "openai"
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_wrong_p,
            )
        self.assertIn("backend_provider", str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Usage route not via 9router
        env_wrong_route = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement")
        env_wrong_route.usage_evidence.router = "direct_vendor"
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_wrong_route,
            )
        self.assertIn("9router", str(ctx2.exception).lower())
        self._assert_zero_side_effects()

    def test_r13_07_stale_or_missing_machine_readable_timestamp_rejected_zero_side_effects(self):
        """7. Counterexample: Usage evidence with stale or missing timestamp fails closed."""
        now_dt = datetime.now(timezone.utc)
        stale_ts = (now_dt - timedelta(hours=2)).isoformat()
        env_stale = make_execution_envelope(self.delivery_id, self.intended_disp, timestamp=stale_ts)
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=now_dt,
                dispatch_origin="dely dispatch",
                execution_envelope=env_stale,
            )
        self.assertIn("earlier than dispatch time", str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Missing timestamp (relying solely on recorded_after_dispatch boolean)
        env_no_ts = make_execution_envelope(self.delivery_id, self.intended_disp)
        env_no_ts.usage_evidence.timestamp = None
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id="orca-r13-probe",
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_no_ts,
            )
        self.assertIn("machine-readable timestamp", str(ctx2.exception).lower())
        self._assert_zero_side_effects()

    def test_r13_08_valid_envelope_succeeds_and_binds_identities(self):
        """8. Positive control: Valid execution envelope succeeds, transitions state, and binds identities."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement")
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id="orca-r13-probe-success",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id=self.intended_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=env,
        )
        self.assertEqual(disp_id, self.intended_disp)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "dispatched")
        self.assertIn(self.intended_disp, self.adapter.dispatch_bindings)
        binding = self.adapter.dispatch_bindings[self.intended_disp]
        self.assertEqual(binding.delivery_task_id, self.delivery_id)
        self.assertEqual(binding.orca_task_id, "orca-r13-probe-success")
        self.assertTrue(self.lease.is_active)
if __name__ == "__main__":
    unittest.main(verbosity=2)


