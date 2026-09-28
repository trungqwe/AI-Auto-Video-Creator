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
import sys
import unittest
from datetime import datetime, timezone
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
    validate_contract_ref,
    validate_path_syntax,
    validate_scope_and_deltas,
    validate_task_traceability_and_readiness,
)


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
                "mutation_lease_forbidden": True,
            }
        ])
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
        self.lease_mgr = LeaseManager([
            {"id": "LOCK-PARALLEL-REGISTRY", "mode": "exclusive"},
        ])
        self.adapter = OrcaDeliveryAdapter(self.lease_mgr)
        self.adapter.set_task_state("PD-PILOT-CONTROL", "ready")

    def test_f4_separate_delivery_task_from_orca_execution_pass(self):
        """Positive case: Delivery Task ID is separated from Orca Task ID and Dispatch ID."""
        delivery_id = "PD-PILOT-CONTROL"
        dispatch_id = self.adapter.create_dispatch(delivery_id)
        self.assertTrue(dispatch_id.startswith("ctx_PD-PILOT-CONTROL_"))
        self.assertNotEqual(delivery_id, dispatch_id)
        self.assertEqual(self.adapter.get_task_state(delivery_id), "dispatched")

    def test_f4_worker_done_invalid_outcome_fail(self):
        """Negative counterexample: worker_done with outcome other than 'succeeded' or 'failed' fails."""
        dispatch_id = self.adapter.create_dispatch("PD-PILOT-CONTROL")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_worker_done(
                delivery_task_id="PD-PILOT-CONTROL",
                orca_task_id="task_orca_001",
                dispatch_id=dispatch_id,
                outcome="integrated",  # FORBIDDEN: CLI only accepts succeeded|failed
            )
        self.assertIn("Orca CLI only supports 'succeeded' or 'failed'", str(ctx.exception))

    def test_f4_success_to_review_to_integrated_pass(self):
        """Positive case: worker_done succeeded -> review -> review ACCEPT -> merge_queued -> integrated."""
        delivery_id = "PD-PILOT-CONTROL"
        dispatch_id = self.adapter.create_dispatch(delivery_id)

        # 1. worker_done succeeded settles attempt and moves delivery task to review
        state = self.adapter.handle_worker_done(
            delivery_task_id=delivery_id,
            orca_task_id="task_orca_001",
            dispatch_id=dispatch_id,
            outcome="succeeded",
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
        dispatch_1 = self.adapter.create_dispatch(delivery_id)
        self.lease_mgr.acquire_lease("LOCK-PARALLEL-REGISTRY", delivery_id, dispatch_1)
        self.assertEqual(len(self.lease_mgr.active_leases), 1)

        # Worker reports failure / blocker
        state = self.adapter.handle_worker_done(
            delivery_task_id=delivery_id,
            orca_task_id="task_orca_001",
            dispatch_id=dispatch_1,
            outcome="failed",
        )
        self.assertEqual(state, "blocked")
        # Leases must be released on blocker
        self.assertEqual(len(self.lease_mgr.active_leases), 0)

        # Resolve blocker
        self.adapter.resolve_blocker_and_replan(delivery_id)
        self.assertEqual(self.adapter.get_task_state(delivery_id), "ready")

        # Create fresh dispatch
        dispatch_2 = self.adapter.create_dispatch(delivery_id)
        self.assertNotEqual(dispatch_1, dispatch_2, "Must issue a fresh dispatch ID")
        self.assertEqual(self.adapter.get_task_state(delivery_id), "dispatched")

    def test_f4_duplicate_worker_done_rejected_fail(self):
        """Negative counterexample: Second worker_done for already settled dispatch is rejected."""
        delivery_id = "PD-PILOT-CONTROL"
        dispatch_id = self.adapter.create_dispatch(delivery_id)
        self.adapter.handle_worker_done(delivery_id, "task_orca", dispatch_id, "succeeded")

        with self.assertRaises(DuplicateResultError):
            self.adapter.handle_worker_done(delivery_id, "task_orca", dispatch_id, "succeeded")

    def test_f4_stale_dispatch_result_rejected_fail(self):
        """Negative counterexample: Result from obsolete dispatch attempt is rejected."""
        delivery_id = "PD-PILOT-CONTROL"
        dispatch_1 = self.adapter.create_dispatch(delivery_id)
        self.adapter.handle_worker_done(delivery_id, "task_orca", dispatch_1, "failed")
        self.adapter.resolve_blocker_and_replan(delivery_id)
        dispatch_2 = self.adapter.create_dispatch(delivery_id)

        # Late result from dispatch_1 arrives
        with self.assertRaises(DuplicateResultError):
            self.adapter.handle_worker_done(delivery_id, "task_orca", dispatch_1, "succeeded")


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
            },
            {
                "id": "LOCK-DESKTOP-GPU",
                "class": "runtime_resource",
                "mode": "capacity",
                "capacity": 2,
            },
            {
                "id": "LOCK-DOC-AUTHORITY",
                "class": "path",
                "mode": "exclusive",
            },
        ]
        self.mgr = LeaseManager(self.lock_defs)

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
            {"id": "LOCK-EXCLUSIVE-REG", "mode": "exclusive"},
            {"id": "LOCK-PARTITION-DB", "mode": "exclusive_by_database_name", "partition_key_prefix": "db:"},
            {"id": "LOCK-CAPACITY-RUNNERS", "mode": "capacity", "capacity": 3},
            {"id": "LOCK-EVIDENCE-IMMUTABLE", "mode": "immutable"},
        ]
        self.mgr = LeaseManager(self.lock_defs)

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
        self.lease_mgr = LeaseManager([{"id": "LOCK-REG", "mode": "exclusive"}])
        self.adapter = OrcaDeliveryAdapter(self.lease_mgr)
        self.adapter.set_task_state("TASK-PILOT", "ready")

    def test_sol_adapter_reject_blank_identities(self):
        """Adversarial probe: Blank delivery_task_id, orca_task_id, or dispatch_id rejected."""
        with self.assertRaises(ProtocolViolationError):
            self.adapter.create_dispatch("", orca_task_id="task_1")
        with self.assertRaises(ProtocolViolationError):
            self.adapter.create_dispatch("TASK-PILOT", orca_task_id="   ")

        dispatch_id = self.adapter.create_dispatch("TASK-PILOT", orca_task_id="task_1")
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_worker_done("", "task_1", dispatch_id, "succeeded")
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_worker_done("TASK-PILOT", "", dispatch_id, "succeeded")
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_worker_done("TASK-PILOT", "task_1", "", "succeeded")

    def test_sol_adapter_reject_wrong_orca_task_id(self):
        """Adversarial probe: Mismatch in bound exact orca_task_id rejected."""
        dispatch_id = self.adapter.create_dispatch("TASK-PILOT", orca_task_id="task_orca_bound")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_worker_done(
                "TASK-PILOT",
                orca_task_id="task_orca_impostor",
                dispatch_id=dispatch_id,
                outcome="succeeded",
            )
        self.assertIn("orca_task_id mismatch", str(ctx.exception))

    def test_sol_adapter_reject_candidate_commit_mismatch(self):
        """Adversarial probe: Candidate commit mismatch between bound dispatch and worker_done rejected."""
        bound_commit = "f98eb902696d1c7c27e7cc15efbe1a0b5a8ca571"
        dispatch_id = self.adapter.create_dispatch(
            "TASK-PILOT", orca_task_id="task_orca_001", candidate_commit=bound_commit
        )
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_worker_done(
                "TASK-PILOT",
                orca_task_id="task_orca_001",
                dispatch_id=dispatch_id,
                outcome="succeeded",
                candidate_commit="0000000000000000000000000000000000000000",
            )
        self.assertIn("Candidate commit mismatch", str(ctx.exception))

    def test_sol_adapter_reject_absent_and_stale_fencing_tokens(self):
        """Adversarial probe: Absent or stale fencing tokens rejected on worker_done."""
        dispatch_id = self.adapter.create_dispatch(
            "TASK-PILOT", orca_task_id="task_orca_001", fencing_token=5
        )
        with self.assertRaises(ProtocolViolationError) as ctx1:
            self.adapter.handle_worker_done(
                "TASK-PILOT",
                orca_task_id="task_orca_001",
                dispatch_id=dispatch_id,
                outcome="succeeded",
                fencing_token=None,
            )
        self.assertIn("Absent fencing token", str(ctx1.exception))

        with self.assertRaises(StaleResultError) as ctx2:
            self.adapter.handle_worker_done(
                "TASK-PILOT",
                orca_task_id="task_orca_001",
                dispatch_id=dispatch_id,
                outcome="succeeded",
                fencing_token=4,
            )
        self.assertIn("Stale fencing token", str(ctx2.exception))

    def test_sol_adapter_enforce_authority_on_dispatch(self):
        """Adversarial probe: Non-granted task authority rejected from dispatch."""
        for unauthorized in ("locked", "future_template", "revoked"):
            with self.assertRaises(ProtocolViolationError) as ctx:
                self.adapter.create_dispatch("TASK-PILOT", authority_state=unauthorized)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
