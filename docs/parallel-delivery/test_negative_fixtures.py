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
import subprocess
import sys
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
    DuplicateResultError,
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
    StaleResultError,
    build_contract_catalog,
    check_harness_tool_compatibility,
    check_owned_vs_forbidden,
    check_path_scope,
    patterns_overlap,
    validate_commit_sha,
    validate_contract_ref,
    validate_path_syntax,
    validate_scope_and_deltas,
    validate_task_traceability_and_readiness,
)
from validate import check_task_dag


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
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.lease_mgr = LeaseManager([
            {"id": "LOCK-PARALLEL-REGISTRY", "mode": "exclusive", "renewable": True},
        ])
        self.lease_mgr.set_task_authority("PD-PILOT-CONTROL", "granted")
        self.adapter = OrcaDeliveryAdapter(self.lease_mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        self.adapter.set_task_authority("PD-PILOT-CONTROL", "granted")
        self.adapter.set_task_state("PD-PILOT-CONTROL", "ready")

    def _create_dispatch_helper(self, delivery_id="PD-PILOT-CONTROL", orca_task_id=None):
        if orca_task_id is None:
            self._dispatch_counter = getattr(self, "_dispatch_counter", 0) + 1
            orca_task_id = f"task_orca_{self._dispatch_counter:03d}"
        lease = self.lease_mgr.acquire_lease("LOCK-PARALLEL-REGISTRY", delivery_id, "ctx_init")
        dispatch_id = self.adapter.create_dispatch(
            delivery_id,
            orca_task_id=orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
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
        self.lock_defs = [{"id": "LOCK-REG", "mode": "exclusive", "renewable": True}]
        self.lease_mgr = LeaseManager(self.lock_defs)
        self.lease_mgr.set_task_authority("TASK-PILOT", "granted")
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.adapter = OrcaDeliveryAdapter(self.lease_mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR)
        self.adapter.set_task_authority("TASK-PILOT", "granted")
        self.adapter.set_task_state("TASK-PILOT", "ready")
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
        )
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
        )
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
        )
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
        )
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
        self.adapter = OrcaDeliveryAdapter(self.mgr)
        self.adapter.set_task_authority("TASK-PROBE", "granted")
        self.adapter.set_task_authority("TASK-OTHER", "granted")
        self.adapter.set_task_state("TASK-PROBE", "ready")
        self.adapter.set_task_state("TASK-OTHER", "ready")

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
        report_path = ROOT_DIR / "docs" / "parallel-delivery" / ".validation-report.json"
        content_before = report_path.read_bytes() if report_path.exists() else None
        stat_before = subprocess.run(
            ["git", "status", "--porcelain", "docs/parallel-delivery/.validation-report.json"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        env = os.environ.copy()
        env["VALIDATE_SKIP_FIXTURES"] = "1"
        proc = subprocess.run(
            [sys.executable, str(ROOT_DIR / "docs" / "parallel-delivery" / "validate.py"), "--skip-fixtures"],
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
        )

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
        disp = self.adapter.create_dispatch("TASK-OTHER", "orca-t", self.candidate_commit, l.fencing_token, l.lease_id)
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
        )
        self.assertIsNotNone(disp1)
        self.adapter.set_task_state("TASK-A", "ready")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-A",
                orca_task_id="orca-a-2",
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
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
        )
        lease_b = self.mgr.acquire_lease("R3-LOCK-CAP", "TASK-B", "ctx-b", units=1)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-B",
                orca_task_id="orca-shared-id",
                candidate_commit=self.candidate_commit,
                fencing_token=lease_b.fencing_token,
                lease_id=lease_b.lease_id,
            )
        self.assertIn("already assigned to delivery task 'TASK-A'", str(ctx.exception))

    def test_r3_12_dispatch_rejects_blocked_and_non_ready_states(self):
        """12. Dispatch rejects tasks in blocked, planned, dispatched, or review states (only 'ready' permitted)."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        for non_ready in ("blocked", "planned", "dispatched", "review", "integrated"):
            self.adapter.set_task_state("TASK-A", non_ready)
            with self.assertRaises(ProtocolViolationError) as ctx:
                self.adapter.create_dispatch(
                    "TASK-A",
                    orca_task_id=f"orca-a-{non_ready}",
                    candidate_commit=self.candidate_commit,
                    fencing_token=lease.fencing_token,
                    lease_id=lease.lease_id,
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
            now=now_time,
        )
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
        """14. worker_done rejects task not currently in 'dispatched' state."""
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
        self.assertIn("must be 'dispatched'", str(ctx.exception))

    def test_r3_15_review_verdict_rejects_unknown_verdicts(self):
        """15. Review disposition strictly rejects unknown verdicts (no silent blocked fallback)."""
        lease = self.mgr.acquire_lease("R3-LOCK-EXCL", "TASK-A", "ctx-a")
        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-a-rev",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
        )
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
        )
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

        # 2. Namespace collapse STOP condition: IDLE -> RUNNING -> STOP_FALLBACK
        with self.assertRaises(HarnessCompatibilityError):
            sm.evaluate("functions", "functions.exec")
        self.assertEqual(sm.current_state, "STOP_FALLBACK")
        self.assertTrue(len(sm.transitions) >= 2)
        last_trans = sm.transitions[-1]
        self.assertEqual(last_trans[1], "STOP_FALLBACK")
        self.assertIn("collapse detected", last_trans[2])


class TestSolRoundFourCounterexamples(unittest.TestCase):
    """Counterexamples and positive controls for cx/gpt-5.6-sol-high round 4 review findings."""

    def setUp(self):
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
        )
        self.adapter.handle_worker_done(
            "TASK-A",
            "orca-fixed-task-id",
            disp_a,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
        )

        # Settle task A and try to reuse same orca_task_id for TASK-B
        lease_b = self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-B", "ctx-b")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                "TASK-B",
                orca_task_id="orca-fixed-task-id",
                candidate_commit=self.candidate_commit,
                fencing_token=lease_b.fencing_token,
                lease_id=lease_b.lease_id,
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
        )
        self.adapter.handle_worker_done(
            "TASK-A",
            "orca-task-unique-1",
            disp_a,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=lease_a.fencing_token,
        )

        # Reusing ctx-disp-reuse must fail even though task A is settled
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
        self.adapter.set_task_state("TASK-A", "dispatched")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state("TASK-A", "integrated")
        self.assertIn("Illegal task-state transition", str(ctx.exception))

        # Legal progression
        self.adapter.set_task_state("TASK-A", "ready")
        self.adapter.transition_task_state("TASK-A", "dispatched")
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "dispatched")
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
        )
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
        """14. Positive & negative: State machine observes IDLE -> RUNNING -> SUCCESS | STOP_FALLBACK."""
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

        # 2. Re-evaluating resets from IDLE -> RUNNING -> STOP_FALLBACK on mismatch
        with self.assertRaises(HarnessCompatibilityError):
            sm.evaluate("tool.mismatch", "tool.requested")
        self.assertEqual(sm.current_state, "STOP_FALLBACK")

        # 3. Execution failure: IDLE -> RUNNING -> FAILURE -> STOP_FALLBACK
        with self.assertRaises(HarnessCompatibilityError):
            sm.evaluate("tool.err", "tool.err", execution_observed=True, execution_returncode=1)
        self.assertEqual(sm.current_state, "STOP_FALLBACK")
        trans_names = [t[1] for t in sm.transitions[-3:]]
        self.assertEqual(trans_names, ["RUNNING", "FAILURE", "STOP_FALLBACK"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
