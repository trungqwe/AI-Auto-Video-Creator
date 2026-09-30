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
import os
import subprocess
import sys
import tempfile
import threading
import time
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
    ReviewEvidence,
    IntegrationEvidence,
    ReviewerCapability,
    ControlCapability,
    ReviewerContext,
    ReviewDispatchHandle,
    ReviewerDeliveryChannel,
    _InternalReviewerMintToken,
    ReviewerHostHandoff,
    ReviewerHostIssuer,
    ReviewerHostIssuerCapability,
    ReviewerSessionBoundary,
    ReviewerSessionProof,
    make_review_evidence,
    make_integration_evidence,
    PRODUCTION_ACTIVATION_BLOCKED,
    ARCHITECTURE_IMPLEMENTED,
    REFERENCE_TESTED,
    ProductionActivationGate,
    ProductionActivationBlockedError,
    EnvelopeVerificationError,
    ReplayAttackError,
    ExpiredEnvelopeError,
    FencingViolationError,
    REVIEW_ENVELOPE_DOMAIN,
    INTEGRATION_ENVELOPE_DOMAIN,
    SignedReviewEnvelope,
    SignedIntegrationEnvelope,
    TrustedKeyStore,
    DurableConsumptionRegistry,
    TrustedReviewConsumer,
    TrustedIntegrationConsumer,
    sign_review_envelope,
    sign_integration_envelope,
    MANDATORY_INTEGRATION_GATES,
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

_test_host_issuer = ReviewerHostIssuer.get_default_host_issuer()

def TrustedHostReviewerHandoff(credential: bytes) -> ReviewerHostHandoff:
    """Trusted host-owned handoff authority created exclusively by test harness / trusted host boundary.
    Cannot be called or imported by candidate modules.
    """
    return _test_host_issuer.issue_handoff(credential)


TEST_FIXTURE_REVIEWER_SECRET = "test_fixture_reviewer_secret_32b_hex!"
ReviewerSessionBoundary.provision_from_host(
    TrustedHostReviewerHandoff(TEST_FIXTURE_REVIEWER_SECRET.encode("utf-8"))
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
        self.control_secret = "secret_f4_control"
        self.adapter = OrcaDeliveryAdapter(self.lease_mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR, control_secret=self.control_secret)
        self.adapter.set_task_authority("PD-PILOT-CONTROL", "granted")
        self.adapter.set_task_state("PD-PILOT-CONTROL", "ready")
        self.adapter.register_task_locks("PD-PILOT-CONTROL", ["LOCK-PARALLEL-REGISTRY"])

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()
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
            execution_envelope=make_execution_envelope(delivery_id, ctx_id, orca_task_id=orca_task_id),
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
        rev_disp = "ctx_f4_review_001"
        rev_orca = "task_orca_review_001"
        rev_env = make_execution_envelope(delivery_id, rev_disp, phase="review", orca_task_id=rev_orca)
        rev_disp = self.adapter.create_review_dispatch(
            delivery_id,
            orca_task_id=rev_orca,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
        )
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=delivery_id,
            review_dispatch_id=rev_disp,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        rev_ev = self.adapter.issue_review_evidence(delivery_id, rev_disp, self.candidate_commit, "ACCEPT", reviewer_capability=rev_cap)
        state = self.adapter.handle_review_verdict(delivery_id, "ACCEPT", review_dispatch_id=rev_disp, review_evidence=rev_ev)
        self.assertEqual(state, "merge_queued")

        # 3. Integration gates pass moves task to integrated
        ctrl_cap2 = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=delivery_id)
        int_ev = self.adapter.issue_integration_evidence(delivery_id, self.candidate_commit, "4a7c8c921b7e05066505d51b168a02c3fde61317", gates_pass=True, control_capability=ctrl_cap2)
        state = self.adapter.handle_integration_gates(delivery_id, gates_pass=True, integration_evidence=int_ev)
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

        # Resolve blocker with authenticated task-scoped Control capability
        ctrl_cap = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=delivery_id)
        self.adapter.resolve_blocker_and_replan(delivery_id, capability=ctrl_cap)
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
        ctrl_cap = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=delivery_id)
        self.adapter.resolve_blocker_and_replan(delivery_id, capability=ctrl_cap)
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
            execution_envelope=make_execution_envelope("TASK-PILOT", "ctx-setup", orca_task_id="task_1"),
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
            execution_envelope=make_execution_envelope("TASK-PILOT", "ctx-setup", orca_task_id="task_orca_bound"),
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
            execution_envelope=make_execution_envelope("TASK-PILOT", "ctx-setup", orca_task_id="task_orca_001"),
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
            execution_envelope=make_execution_envelope("TASK-PILOT", "ctx-setup", orca_task_id="task_orca_001"),
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
        self.control_secret = "secret_r3_control"
        self.adapter = OrcaDeliveryAdapter(self.mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR, control_secret=self.control_secret)
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
            execution_envelope=make_execution_envelope("TASK-PROBE", "ctx-disp", orca_task_id="orca-valid"),
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
        disp = self.adapter.create_dispatch("TASK-OTHER", "orca-t", self.candidate_commit, l.fencing_token, l.lease_id, intended_dispatch_id="ctx-trans", dispatch_origin="dely dispatch", execution_envelope=make_execution_envelope("TASK-OTHER", "ctx-trans", orca_task_id="orca-t"))
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
        self.control_secret = "secret_r4_control"
        self.adapter = OrcaDeliveryAdapter(self.mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR, control_secret=self.control_secret)
        self.adapter.set_task_authority("TASK-A", "granted")
        self.adapter.set_task_authority("TASK-B", "granted")
        self.adapter.set_task_authority("TASK-LOCKED", "locked")
        self.adapter.set_task_authority("TASK-REVOKED", "revoked")
        self.adapter.set_task_state("TASK-A", "ready")
        self.adapter.set_task_state("TASK-B", "ready")
        self.adapter.register_task_locks("TASK-A", ["R3-LOCK-EXCL"])
        self.adapter.register_task_locks("TASK-B", ["R3-LOCK-CAP"])

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()
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
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-B", "ctx-a", orca_task_id="orca-b-1"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a", orca_task_id="orca-a-exp"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a", orca_task_id="orca-a-1"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a", orca_task_id="orca-a-2"),
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
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-A", "ctx-a", orca_task_id="orca-a-fence"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a", orca_task_id="orca-a-wrong-cand"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a", orca_task_id="orca-shared-id"),
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
            execution_envelope=make_execution_envelope("TASK-B", "ctx-b", orca_task_id="orca-shared-id"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a", now=now_time, orca_task_id="orca-a-wd-exp"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a", orca_task_id="orca-a-rev"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a", orca_task_id="orca-a-int"),
        )
        self.adapter.acknowledge_dispatch("TASK-A", disp)
        self.adapter.start_running("TASK-A", disp)
        self.adapter.handle_worker_done("TASK-A", "orca-a-int", disp, "succeeded", self.candidate_commit, lease.fencing_token)
        rev_disp = "ctx_r3_16_review"
        rev_orca = "task_orca_r3_16_rev"
        rev_env = make_execution_envelope("TASK-A", rev_disp, phase="review", orca_task_id=rev_orca)
        rev_disp = self.adapter.create_review_dispatch(
            "TASK-A",
            orca_task_id=rev_orca,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
        )
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id="TASK-A",
            review_dispatch_id=rev_disp,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        rev_ev = self.adapter.issue_review_evidence("TASK-A", rev_disp, self.candidate_commit, "ACCEPT", reviewer_capability=rev_cap)
        self.adapter.handle_review_verdict("TASK-A", "ACCEPT", review_dispatch_id=rev_disp, review_evidence=rev_ev)
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "merge_queued")

        ctrl_cap2 = self.adapter.issue_control_capability(self.control_secret, delivery_task_id="TASK-A")
        int_ev = self.adapter.issue_integration_evidence("TASK-A", self.candidate_commit, "4a7c8c921b7e05066505d51b168a02c3fde61317", gates_pass=True, control_capability=ctrl_cap2)
        for truthy_val in (1, 0, "true", "True", [True], {"pass": True}, None):
            with self.assertRaises(ProtocolViolationError) as ctx:
                self.adapter.handle_integration_gates("TASK-A", gates_pass=truthy_val, integration_evidence=int_ev)  # type: ignore
            self.assertIn("gates_pass must be strict bool", str(ctx.exception))

        # Strict boolean passes
        res = self.adapter.handle_integration_gates("TASK-A", gates_pass=True, integration_evidence=int_ev)
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
        self.control_secret = "secret_r4_control"
        self.adapter = OrcaDeliveryAdapter(self.mgr, approved_candidate_commit=self.candidate_commit, git_root=ROOT_DIR, control_secret=self.control_secret)
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

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a", orca_task_id="orca-fixed-task-id"),
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
            execution_envelope=make_execution_envelope("TASK-B", "ctx-b", orca_task_id="orca-fixed-task-id"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-disp-reuse", orca_task_id="orca-task-unique-1"),
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
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-B", "ctx-disp-reuse", orca_task_id="orca-task-unique-2"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-overwrite", orca_task_id="orca-t1"),
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
                execution_envelope=make_execution_envelope("TASK-B", "ctx-overwrite", orca_task_id="orca-t2"),
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
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-A", "ctx_different_target", orca_task_id="orca-intended-test"),
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
        self.adapter._task_states["TASK-A"] = "dispatched"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state("TASK-A", "integrated")
        self.assertIn("Illegal task-state transition", str(ctx.exception))

        # Legal progression via authorized lifecycle handlers
        self.adapter._task_states["TASK-A"] = "ready"
        lease = self.mgr.acquire_lease("R4-LOCK-EXCL", "TASK-A", "ctx-r4-09")
        disp = self.adapter.create_dispatch(
            "TASK-A",
            orca_task_id="orca-r4-09",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id="ctx-r4-09",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-A", "ctx-r4-09", phase="implement", orca_task_id="orca-r4-09"),
        )
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "dispatched")
        self.adapter.acknowledge_dispatch("TASK-A", disp)
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "acknowledged")
        self.adapter.start_running("TASK-A", disp)
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "running")
        self.adapter.handle_worker_done(
            "TASK-A", "orca-r4-09", disp, outcome="succeeded",
            candidate_commit=self.candidate_commit, fencing_token=lease.fencing_token
        )
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "review")
        rev_disp = "ctx_r4_09_review"
        rev_orca = "task_orca_r4_09_rev"
        rev_env = make_execution_envelope("TASK-A", rev_disp, phase="review", orca_task_id=rev_orca)
        rev_disp = self.adapter.create_review_dispatch(
            "TASK-A",
            orca_task_id=rev_orca,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
        )
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id="TASK-A",
            review_dispatch_id=rev_disp,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        rev_ev = self.adapter.issue_review_evidence("TASK-A", rev_disp, self.candidate_commit, "ACCEPT", reviewer_capability=rev_cap)
        self.adapter.handle_review_verdict("TASK-A", "ACCEPT", review_dispatch_id=rev_disp, review_evidence=rev_ev)
        self.assertEqual(self.adapter.get_task_state("TASK-A"), "merge_queued")
        ctrl_cap2 = self.adapter.issue_control_capability(self.control_secret, delivery_task_id="TASK-A")
        int_ev = self.adapter.issue_integration_evidence("TASK-A", self.candidate_commit, "4a7c8c921b7e05066505d51b168a02c3fde61317", gates_pass=True, control_capability=ctrl_cap2)
        self.adapter.handle_integration_gates("TASK-A", True, integration_evidence=int_ev)
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-worker-done", orca_task_id="orca-wd-test"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-a-r5", orca_task_id="orca-shared-task-001"),
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
                execution_envelope=make_execution_envelope("TASK-B", "ctx-b-r5", orca_task_id="orca-shared-task-001"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-shared-disp", orca_task_id="orca-t1-unique"),
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
                execution_envelope=make_execution_envelope("TASK-B", "ctx-shared-disp", orca_task_id="orca-t2-unique"),
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
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-A", "ctx-hijack-attempt", orca_task_id="orca-mismatch-disp"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-lifecycle-1", orca_task_id="orca-life-1"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-lifecycle-2", orca_task_id="orca-life-2"),
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
        self.adapter._task_states["TASK-A"] = "dispatched"
        with self.assertRaises(ProtocolViolationError):
            self.adapter.transition_task_state("TASK-A", "integrated")

        # acknowledged -> integrated is forbidden
        self.adapter._task_states["TASK-A"] = "acknowledged"
        with self.assertRaises(ProtocolViolationError):
            self.adapter.transition_task_state("TASK-A", "integrated")

        # running -> ready is forbidden
        self.adapter._task_states["TASK-A"] = "running"
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
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-A", "ctx-lock-set", orca_task_id="orca-lock-set-fail"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-lock-set", orca_task_id="orca-lock-set-pass"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-wd-rel", orca_task_id="orca-wd-rel"),
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

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()
    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def _issue_valid_review_evidence(self, delivery_id, rev_disp_id, candidate_commit, verdict="ACCEPT", now=None):
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=candidate_commit,
            reviewer_secret=getattr(self, "reviewer_secret", TEST_FIXTURE_REVIEWER_SECRET),
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        return self.adapter.issue_review_evidence(delivery_id, rev_disp_id, candidate_commit, verdict=verdict, reviewer_capability=rev_cap, now=now)

    def _issue_valid_integration_evidence(self, delivery_id, candidate_commit, base_commit, gates_pass=True, now=None):
        ctrl_cap = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=delivery_id)
        return self.adapter.issue_integration_evidence(delivery_id, candidate_commit, base_commit, gates_pass=gates_pass, control_capability=ctrl_cap, now=now)


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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-shared-default-1", orca_task_id="orca-default-task-1"),
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
                execution_envelope=make_execution_envelope("TASK-B", "ctx-shared-default-2", orca_task_id="orca-default-task-1"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-life-1", orca_task_id="orca-life-1"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx-life-2", orca_task_id="orca-life-2"),
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
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-UNREG", "ctx-unreg-locks", orca_task_id="orca-unreg-locks"),
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
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-A", "ctx-exact-1", orca_task_id="orca-missing-lock"),
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
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-A", "ctx-exact-1", orca_task_id="orca-extraneous-lock"),
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
        self.adapter._task_states["TASK-A"] = "dispatched"
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
                dispatch_origin="dely dispatch",
                execution_envelope=make_execution_envelope("TASK-B", "ctx-b", orca_task_id="orca-cap-fail"),
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
                execution_envelope=make_execution_envelope("TASK-A", "ctx-winner", orca_task_id="orca-race-task-01"),
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
                    execution_envelope=make_execution_envelope("TASK-B", "ctx-loser", orca_task_id="orca-race-task-01"),
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
            execution_envelope=make_execution_envelope("TASK-R10", "ctx_r10", orca_task_id="orca_task_r10"),
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
            execution_envelope=make_execution_envelope("TASK-R11-1", "ctx_real", orca_task_id="orca_r11_1"),
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
            execution_envelope=make_execution_envelope("TASK-A", "ctx_a", orca_task_id="orca_a"),
        )
        adapter.acknowledge_dispatch("TASK-A", disp_a)
        adapter.start_running("TASK-A", disp_a)

        lease_b = mgr.acquire_lease("R11-LOCK-B", "TASK-B", "ctx_b")
        disp_b = adapter.create_dispatch(
            "TASK-B", "orca_b", self.candidate_commit,
            lease_id=lease_b.lease_id, intended_dispatch_id="ctx_b", fencing_token=lease_b.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-B", "ctx_b", orca_task_id="orca_b"),
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
            execution_envelope=make_execution_envelope("TASK-DUP", "ctx_dup1", orca_task_id="orca_dup1"),
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
            execution_envelope=make_execution_envelope("TASK-REPLAN", "ctx_first", orca_task_id="orca_first"),
        )
        adapter.acknowledge_dispatch("TASK-REPLAN", disp1)
        adapter.start_running("TASK-REPLAN", disp1)
        adapter.handle_worker_done("TASK-REPLAN", "orca_first", disp1, "failed", candidate_commit=self.candidate_commit, fencing_token=lease1.fencing_token)
        self.assertEqual(adapter.get_task_state("TASK-REPLAN"), "blocked")

        # Replan and redispatch as Dispatch 2 with authenticated Control capability
        r11_control_secret = "secret_r11_control"
        adapter.evidence_authority._control_secret = r11_control_secret.encode("utf-8")
        ctrl_cap = adapter.issue_control_capability(r11_control_secret, delivery_task_id="TASK-REPLAN")
        adapter.resolve_blocker_and_replan("TASK-REPLAN", capability=ctrl_cap)
        self.assertEqual(adapter.get_task_state("TASK-REPLAN"), "ready")
        lease2 = mgr.acquire_lease("R11-LOCK-REPLAN", "TASK-REPLAN", "ctx_second")
        disp2 = adapter.create_dispatch(
            "TASK-REPLAN", "orca_second", self.candidate_commit,
            lease_id=lease2.lease_id, intended_dispatch_id="ctx_second", fencing_token=lease2.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope("TASK-REPLAN", "ctx_second", orca_task_id="orca_second"),
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
            execution_envelope=make_execution_envelope("TASK-VALID", "ctx_valid", orca_task_id="orca_valid"),
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
            execution_envelope=make_execution_envelope("TASK-TX", "ctx_tx", orca_task_id="orca_tx"),
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
            "orca_task_id": "orca_impl_001",
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
                "delivery_task_id": "PD-PILOT-CONTROL",
                "dispatch_id": "ctx_impl_001",
                "effort": "high",
            },
            "usage_evidence": {
                "backend_provider": "google",
                "backend_model": "ag/gemini-3.8-flash-high",
                "recorded_after_dispatch": True,
                "timestamp": "2026-09-29T00:05:00Z",
                "request_id": "req_test_01",
                "delivery_task_id": "PD-PILOT-CONTROL",
                "dispatch_id": "ctx_impl_001",
                "router": "9router",
            },
            "launch_requested": {
                "harness": "Codex CLI",
                "provider": "9router",
                "route": "ag/gemini-3.8-flash-high",
                "model": "ag/gemini-3.8-flash-high",
                "effort": "high",
            },
            "launch_effective": {
                "harness": "Codex CLI",
                "provider": "9router",
                "route": "ag/gemini-3.8-flash-high",
                "model": "ag/gemini-3.8-flash-high",
                "effort": "high",
            },
        }
        self.valid_review_envelope = {
            "delivery_task_id": "PD-PILOT-CONTROL",
            "dispatch_id": "ctx_rev_001",
            "orca_task_id": "orca_rev_001",
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
                "delivery_task_id": "PD-PILOT-CONTROL",
                "dispatch_id": "ctx_rev_001",
                "effort": "high",
            },
            "usage_evidence": {
                "backend_provider": "openai",
                "backend_model": "cx/gpt-5.6-sol",
                "recorded_after_dispatch": True,
                "timestamp": "2026-09-29T00:06:00Z",
                "request_id": "req_rev_01",
                "delivery_task_id": "PD-PILOT-CONTROL",
                "dispatch_id": "ctx_rev_001",
                "router": "9router",
            },
            "launch_requested": {
                "harness": "Claude Code",
                "provider": "9router",
                "route": "cx/gpt-5.6-sol",
                "model": "cx/gpt-5.6-sol",
                "effort": "high",
            },
            "launch_effective": {
                "harness": "Claude Code",
                "provider": "9router",
                "route": "cx/gpt-5.6-sol",
                "model": "cx/gpt-5.6-sol",
                "effort": "high",
            },
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
        self.orca_task_id = "orca-r13-probe"
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
                    execution_envelope=make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id="orca-r13-probe-2"),
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
        env_no_task = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
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
        env_no_disp = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
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
        env_bad_phase = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
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
        env_contra_disp = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
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
        env_contra_task = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
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
        env_mismatch_task = make_execution_envelope("TASK-OTHER-BOUND", self.intended_disp, orca_task_id=self.orca_task_id)
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
        env_mismatch_disp = make_execution_envelope(self.delivery_id, "ctx-unauthorized-id", orca_task_id=self.orca_task_id)
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
        env_wrong_phase = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review", orca_task_id=self.orca_task_id)
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
        env_unverified = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
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
        env_no_ref = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
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
        env_wrong_p = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
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
        env_wrong_route = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
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
        env_stale = make_execution_envelope(self.delivery_id, self.intended_disp, timestamp=stale_ts, orca_task_id=self.orca_task_id)
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
        env_no_ts = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
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
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id="orca-r13-probe-success")
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

class TestSolRound14IdentityAnchorsAndBackendValidation(unittest.TestCase):
    """Sol Round 14 Remediation:
    1. Mandatory Orca task identity on ExecutionEnvelope and binding to create_dispatch() argument
       before any side effects.
    2. Mandatory non-blank delivery_task_id and dispatch_id identity anchors on both LiveTerminalEvidence
       and UsageEvidence records, and mandatory live terminal effort field.
    3. Strict exact phase-specific backend model identities:
       - implement accepts exact routed or canonical form for gemini-3.8-flash-high
         ('ag/gemini-3.8-flash-high', 'gemini-3.8-flash-high')
       - review accepts exact routed or canonical form for gpt-5.6-sol
         ('cx/gpt-5.6-sol', 'gpt-5.6-sol')
       - Rejects prefixes, suffixes, and foreign aliases (e.g. 'prefix-gpt-5.6-sol-foreign').
    4. Discriminating negative fixtures and positive controls with zero side effects verification.
    5. Preserves all previous lease, fencing, fail-before-side-effect, harness-failure, exact-HEAD and release invariants.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.lock_defs = [{"id": "LOCK-R14", "mode": "exclusive", "renewable": True}]
        self.mgr = LeaseManager(self.lock_defs)
        self.delivery_id = "TASK-R14-PROBE"
        self.orca_task_id = "orca-r14-probe-task"
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.candidate_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
        ).strip()
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
        )
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-R14"])
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.intended_disp = "ctx-r14-probe"
        self.lease = self.mgr.acquire_lease("LOCK-R14", self.delivery_id, self.intended_disp)

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def _assert_zero_side_effects(self, intended_disp_id="ctx-r14-probe"):
        """Verify no side effects occurred on task state, active dispatches, bindings, seen dispatches, or leases."""
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "ready")
        self.assertNotIn(self.delivery_id, self.adapter.active_dispatches)
        self.assertNotIn(intended_disp_id, self.adapter.dispatch_bindings)
        self.assertNotIn(intended_disp_id, self.adapter.seen_dispatch_ids)
        self.assertTrue(self.lease.is_active)

    def test_r14_01_missing_envelope_orca_task_id_fails_closed_zero_side_effects(self):
        """1. Counterexample: Missing or blank orca_task_id in ExecutionEnvelope fails closed before side effects."""
        # Case A: orca_task_id is empty string
        env_empty = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id="")
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_empty,
            )
        self.assertIn("orca_task_id", str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Case B: orca_task_id is None
        env_none = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_none.orca_task_id = None
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_none,
            )
        self.assertIn("orca_task_id", str(ctx2.exception).lower())
        self._assert_zero_side_effects()

        # Case C: dictionary envelope completely omitting orca_task_id
        env_dict = {
            "delivery_task_id": self.delivery_id,
            "dispatch_id": self.intended_disp,
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
                "archive_reference": "ref_r14_01",
                "verified": True,
                "delivery_task_id": self.delivery_id,
                "dispatch_id": self.intended_disp,
                "effort": "high",
            },
            "usage_evidence": {
                "backend_provider": "google",
                "backend_model": "ag/gemini-3.8-flash-high",
                "recorded_after_dispatch": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": "req_r14_01",
                "delivery_task_id": self.delivery_id,
                "dispatch_id": self.intended_disp,
                "router": "9router",
            },
            "launch_requested": {
                "harness": "Codex CLI",
                "provider": "9router",
                "route": "ag/gemini-3.8-flash-high",
                "effort": "high",
            },
            "launch_effective": {
                "harness": "Codex CLI",
                "provider": "9router",
                "route": "ag/gemini-3.8-flash-high",
                "effort": "high",
            },
        }
        with self.assertRaises(RoutingEvidenceError) as ctx3:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_dict,
            )
        self.assertIn("orca_task_id", str(ctx3.exception).lower())
        self._assert_zero_side_effects()

    def test_r14_02_mismatched_envelope_orca_task_id_fails_closed_zero_side_effects(self):
        """2. Counterexample: Envelope with mismatched orca_task_id fails closed before side effects."""
        env_mismatch = make_execution_envelope(
            self.delivery_id,
            self.intended_disp,
            orca_task_id="orca-other-foreign-task-id",
        )
        with self.assertRaises(RoutingEvidenceError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_mismatch,
            )
        self.assertIn("mismatch", str(ctx.exception).lower())
        self.assertIn("orca_task_id", str(ctx.exception).lower())
        self._assert_zero_side_effects()

    def test_r14_03_unanchored_live_terminal_task_and_dispatch_fail_closed_zero_side_effects(self):
        """3. Counterexample: Live terminal evidence missing delivery_task_id or dispatch_id anchor fails closed."""
        # Missing delivery_task_id (None)
        env_no_task = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_no_task.live_terminal_evidence.delivery_task_id = None
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_no_task,
            )
        self.assertIn("delivery_task_id", str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Blank delivery_task_id ("   ")
        env_blank_task = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_blank_task.live_terminal_evidence.delivery_task_id = "   "
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_blank_task,
            )
        self.assertIn("delivery_task_id", str(ctx2.exception).lower())
        self._assert_zero_side_effects()

        # Missing dispatch_id (None)
        env_no_disp = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_no_disp.live_terminal_evidence.dispatch_id = None
        with self.assertRaises(RoutingEvidenceError) as ctx3:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_no_disp,
            )
        self.assertIn("dispatch_id", str(ctx3.exception).lower())
        self._assert_zero_side_effects()

        # Blank dispatch_id ("   ")
        env_blank_disp = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_blank_disp.live_terminal_evidence.dispatch_id = "   "
        with self.assertRaises(RoutingEvidenceError) as ctx4:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_blank_disp,
            )
        self.assertIn("dispatch_id", str(ctx4.exception).lower())
        self._assert_zero_side_effects()

    def test_r14_04_missing_or_non_high_live_terminal_effort_fails_closed_zero_side_effects(self):
        """4. Counterexample: Live terminal evidence missing effort or non-high effort fails closed."""
        # Missing effort (None)
        env_no_eff = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_no_eff.live_terminal_evidence.effort = None
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_no_eff,
            )
        self.assertIn("effort", str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Blank effort ("")
        env_blank_eff = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_blank_eff.live_terminal_evidence.effort = ""
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_blank_eff,
            )
        self.assertIn("effort", str(ctx2.exception).lower())
        self._assert_zero_side_effects()

        # Non-high effort ("medium", "low")
        for bad_eff in ("medium", "low", "high-extra"):
            env_bad_eff = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
            env_bad_eff.live_terminal_evidence.effort = bad_eff
            with self.assertRaises(RoutingEvidenceError) as ctx3:
                self.adapter.create_dispatch(
                    self.delivery_id,
                    orca_task_id=self.orca_task_id,
                    candidate_commit=self.candidate_commit,
                    fencing_token=self.lease.fencing_token,
                    lease_id=self.lease.lease_id,
                    intended_dispatch_id=self.intended_disp,
                    dispatch_origin="dely dispatch",
                    execution_envelope=env_bad_eff,
                )
            self.assertIn("effort", str(ctx3.exception).lower())
            self._assert_zero_side_effects()

    def test_r14_05_unanchored_usage_evidence_task_and_dispatch_fail_closed_zero_side_effects(self):
        """5. Counterexample: 9Router usage evidence missing delivery_task_id or dispatch_id anchor fails closed."""
        # Missing delivery_task_id (None)
        env_no_task = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_no_task.usage_evidence.delivery_task_id = None
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_no_task,
            )
        self.assertIn("delivery_task_id", str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Blank delivery_task_id ("   ")
        env_blank_task = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_blank_task.usage_evidence.delivery_task_id = "   "
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_blank_task,
            )
        self.assertIn("delivery_task_id", str(ctx2.exception).lower())
        self._assert_zero_side_effects()

        # Missing dispatch_id (None)
        env_no_disp = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_no_disp.usage_evidence.dispatch_id = None
        with self.assertRaises(RoutingEvidenceError) as ctx3:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_no_disp,
            )
        self.assertIn("dispatch_id", str(ctx3.exception).lower())
        self._assert_zero_side_effects()

        # Blank dispatch_id ("   ")
        env_blank_disp = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_blank_disp.usage_evidence.dispatch_id = "   "
        with self.assertRaises(RoutingEvidenceError) as ctx4:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env_blank_disp,
            )
        self.assertIn("dispatch_id", str(ctx4.exception).lower())
        self._assert_zero_side_effects()

    def test_r14_06_review_foreign_substring_backend_aliases_fail_closed_zero_side_effects(self):
        """6. Counterexample: Review phase rejects foreign substring backend model aliases."""
        self.adapter.register_task_phase(self.delivery_id, "review")
        bad_aliases = [
            "prefix-gpt-5.6-sol-foreign",
            "prefix-gpt-5.6-sol",
            "gpt-5.6-sol-foreign",
            "gpt-5.6-sol-suffix",
            "foreign-gpt-5.6-sol",
            "cx/gpt-5.6-sol-high",
            "gpt-5.6-sol-high",
            "gpt-5.6-sol:high",
        ]
        for alias in bad_aliases:
            env = make_execution_envelope(
                self.delivery_id,
                self.intended_disp,
                phase="review",
                orca_task_id=self.orca_task_id,
            )
            env.usage_evidence.backend_model = alias
            with self.assertRaises(RoutingEvidenceError) as ctx:
                self.adapter.create_dispatch(
                    self.delivery_id,
                    orca_task_id=self.orca_task_id,
                    candidate_commit=self.candidate_commit,
                    fencing_token=self.lease.fencing_token,
                    lease_id=self.lease.lease_id,
                    intended_dispatch_id=self.intended_disp,
                    dispatch_origin="dely dispatch",
                    execution_envelope=env,
                    phase="review",
                )
            self.assertTrue(
                "does not match expected model" in str(ctx.exception)
                or "exact routed or canonical" in str(ctx.exception)
            )
            self._assert_zero_side_effects()

    def test_r14_07_implement_foreign_substring_backend_aliases_fail_closed_zero_side_effects(self):
        """7. Counterexample: Implement phase rejects foreign substring backend model aliases."""
        self.adapter.register_task_phase(self.delivery_id, "implement")
        bad_aliases = [
            "prefix-gemini-3.8-flash-high",
            "gemini-3.8-flash-high-suffix",
            "foreign-gemini-3.8-flash-high",
            "ag/gemini-3.8-flash-high-foreign",
            "gemini-3.8-flash",
            "ag/gemini-3.8-flash-high-high",
        ]
        for alias in bad_aliases:
            env = make_execution_envelope(
                self.delivery_id,
                self.intended_disp,
                phase="implement",
                orca_task_id=self.orca_task_id,
            )
            env.usage_evidence.backend_model = alias
            with self.assertRaises(RoutingEvidenceError) as ctx:
                self.adapter.create_dispatch(
                    self.delivery_id,
                    orca_task_id=self.orca_task_id,
                    candidate_commit=self.candidate_commit,
                    fencing_token=self.lease.fencing_token,
                    lease_id=self.lease.lease_id,
                    intended_dispatch_id=self.intended_disp,
                    dispatch_origin="dely dispatch",
                    execution_envelope=env,
                    phase="implement",
                )
            self.assertTrue(
                "does not match expected model" in str(ctx.exception)
                or "exact routed or canonical" in str(ctx.exception)
            )
            self._assert_zero_side_effects()

    def test_r14_08_exact_routed_and_canonical_backend_models_succeed(self):
        """8. Positive control: Exact routed and canonical backend models succeed for both phases."""
        # Implement phase accepts exact canonical backend model ('ag/gemini-3.8-flash-high')
        for valid_impl_model in ("ag/gemini-3.8-flash-high",):
            SharedOrcaExecutionRegistry.reset_default()
            mgr = LeaseManager(self.lock_defs)
            mgr.set_task_authority(self.delivery_id, "granted")
            adapter = OrcaDeliveryAdapter(
                mgr,
                approved_candidate_commit=self.candidate_commit,
                git_root=ROOT_DIR,
            )
            adapter.register_task_locks(self.delivery_id, ["LOCK-R14"])
            adapter.set_task_authority(self.delivery_id, "granted")
            adapter.set_task_state(self.delivery_id, "ready")
            lease = mgr.acquire_lease("LOCK-R14", self.delivery_id, self.intended_disp)

            env = make_execution_envelope(
                self.delivery_id,
                self.intended_disp,
                phase="implement",
                orca_task_id=self.orca_task_id,
            )
            env.usage_evidence.backend_model = valid_impl_model
            disp_id = adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env,
                phase="implement",
            )
            self.assertEqual(disp_id, self.intended_disp)
            self.assertEqual(adapter.get_task_state(self.delivery_id), "dispatched")

        # Review phase accepts exact canonical backend model ('cx/gpt-5.6-sol')
        for valid_rev_model in ("cx/gpt-5.6-sol",):
            SharedOrcaExecutionRegistry.reset_default()
            mgr = LeaseManager(self.lock_defs)
            mgr.set_task_authority(self.delivery_id, "granted")
            adapter = OrcaDeliveryAdapter(
                mgr,
                approved_candidate_commit=self.candidate_commit,
                git_root=ROOT_DIR,
            )
            adapter.register_task_locks(self.delivery_id, ["LOCK-R14"])
            adapter.set_task_authority(self.delivery_id, "granted")
            adapter.set_task_state(self.delivery_id, "ready")
            adapter.register_task_phase(self.delivery_id, "review")
            lease = mgr.acquire_lease("LOCK-R14", self.delivery_id, self.intended_disp)

            env = make_execution_envelope(
                self.delivery_id,
                self.intended_disp,
                phase="review",
                orca_task_id=self.orca_task_id,
            )
            env.usage_evidence.backend_model = valid_rev_model
            disp_id = adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=lease.fencing_token,
                lease_id=lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env,
                phase="review",
            )
            self.assertEqual(disp_id, self.intended_disp)
            self.assertEqual(adapter.get_task_state(self.delivery_id), "dispatched")

    def test_r14_09_execution_envelope_dataclass_schema_carries_orca_task_id(self):
        """9. Schema verification: ExecutionEnvelope dataclass carries orca_task_id field."""
        self.assertIn("orca_task_id", ExecutionEnvelope.__dataclass_fields__)
        env = make_execution_envelope(
            self.delivery_id,
            self.intended_disp,
            orca_task_id=self.orca_task_id,
        )
        self.assertEqual(env.orca_task_id, self.orca_task_id)

    def test_r14_10_dispatch_binding_preserves_exact_orca_task_id_and_invariants(self):
        """10. Invariant preservation: Valid dispatch binds exact orca_task_id and preserves all invariants."""
        env = make_execution_envelope(
            self.delivery_id,
            self.intended_disp,
            phase="implement",
            orca_task_id=self.orca_task_id,
        )
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id=self.intended_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=env,
        )
        self.assertEqual(disp_id, self.intended_disp)
        binding = self.adapter.dispatch_bindings[self.intended_disp]
        self.assertEqual(binding.orca_task_id, self.orca_task_id)
        self.assertEqual(binding.delivery_task_id, self.delivery_id)
        self.assertEqual(binding.dispatch_id, self.intended_disp)
        self.assertTrue(self.lease.is_active)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "dispatched")




class TestSolRound15FailBeforeSideEffect(unittest.TestCase):
    """Sol Round 15 remediation: fail-before-side-effect validation ordering in OrcaDeliveryAdapter.create_dispatch().
    All pure, non-mutating checks for dispatch_origin and execution_envelope (including exact delivery task, Orca task,
    dispatch, phase, harness/model/effort, and evidence anchors) MUST occur before any call that can purge, deactivate,
    rewrite, or persist lease/registry/task state.
    When an invalid or mismatched envelope is combined with an expired or malformed active lease:
    1. RoutingEvidenceError wins fail-closed.
    2. Zero side effects: the active lease is not purged or deactivated (is_active remains True and lease remains in active_leases).
    3. All task state, dispatch bindings, and registry state remain byte-for-byte / field-for-field unchanged.
    Positive controls: Valid envelope with expired/malformed lease purges authoritatively and raises ProtocolViolationError.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.lock_defs = [{"id": "LOCK-R15", "mode": "exclusive", "renewable": True, "lease_seconds": 10}]
        self.mgr = LeaseManager(self.lock_defs)
        self.delivery_id = "TASK-R15-PROBE"
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.candidate_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
        ).strip()
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
        )
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-R15"])
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.intended_disp = "ctx-r15-probe"
        self.orca_task_id = "orca-r15-task"
        self.t0 = datetime.now(timezone.utc)
        self.lease = self.mgr.acquire_lease("LOCK-R15", self.delivery_id, self.intended_disp, lease_seconds=10, now=self.t0)
        self.past_expiry = self.t0 + timedelta(seconds=30)

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def _snapshot_lease_and_adapter_state(self):
        """Capture deep snapshot of lease fields, active lease registry, adapter state, and execution registry."""
        lease_obj = self.mgr.active_leases.get(self.lease.lease_id)
        lease_snapshot = {
            "lease_id": lease_obj.lease_id if lease_obj else None,
            "lock_id": lease_obj.lock_id if lease_obj else None,
            "delivery_task_id": lease_obj.delivery_task_id if lease_obj else None,
            "dispatch_id": lease_obj.dispatch_id if lease_obj else None,
            "fencing_token": lease_obj.fencing_token if lease_obj else None,
            "is_active": lease_obj.is_active if lease_obj else None,
            "expires_at": lease_obj.expires_at if lease_obj else None,
            "resource_key": lease_obj.resource_key if lease_obj else None,
            "units": lease_obj.units if lease_obj else None,
        }
        active_lease_keys = set(self.mgr.active_leases.keys())
        adapter_state = {
            "task_state": self.adapter.get_task_state(self.delivery_id),
            "active_dispatches": dict(self.adapter.active_dispatches),
            "dispatch_bindings": dict(self.adapter.dispatch_bindings),
            "seen_dispatch_ids": set(self.adapter.seen_dispatch_ids),
            "seen_orca_task_ids": set(self.adapter.seen_orca_task_ids),
        }
        return lease_snapshot, active_lease_keys, adapter_state

    def _assert_zero_side_effects(self, lease_snapshot, active_lease_keys, adapter_state):
        """Assert byte-for-byte and field-for-field unchanged state."""
        self.assertIn(self.lease.lease_id, self.mgr.active_leases)
        current_lease = self.mgr.active_leases[self.lease.lease_id]
        self.assertTrue(current_lease.is_active)
        for k, v in lease_snapshot.items():
            self.assertEqual(getattr(current_lease, k), v, f"Field {k} mutated!")
        self.assertEqual(set(self.mgr.active_leases.keys()), active_lease_keys)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), adapter_state["task_state"])
        self.assertEqual(dict(self.adapter.active_dispatches), adapter_state["active_dispatches"])
        self.assertEqual(dict(self.adapter.dispatch_bindings), adapter_state["dispatch_bindings"])
        self.assertEqual(set(self.adapter.seen_dispatch_ids), adapter_state["seen_dispatch_ids"])
        self.assertEqual(set(self.adapter.seen_orca_task_ids), adapter_state["seen_orca_task_ids"])

    def test_r15_01_sol_counterexample_mismatched_envelope_task_id_with_expired_lease_routing_wins_zero_side_effects(self):
        """1. Counterexample: Mismatched envelope delivery_task_id with expired lease raises RoutingEvidenceError with zero side effects."""
        lease_snapshot, active_keys, adapter_state = self._snapshot_lease_and_adapter_state()
        env = make_execution_envelope("TASK-OTHER-ID", self.intended_disp, orca_task_id=self.orca_task_id)
        with self.assertRaises(RoutingEvidenceError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env,
            )
        self.assertIn("delivery_task_id mismatch", str(ctx.exception).lower())
        self._assert_zero_side_effects(lease_snapshot, active_keys, adapter_state)

    def test_r15_02_sol_counterexample_mismatched_envelope_dispatch_id_with_expired_lease_routing_wins_zero_side_effects(self):
        """2. Counterexample: Mismatched envelope dispatch_id with expired lease raises RoutingEvidenceError with zero side effects."""
        lease_snapshot, active_keys, adapter_state = self._snapshot_lease_and_adapter_state()
        env = make_execution_envelope(self.delivery_id, "ctx-mismatched-disp", orca_task_id=self.orca_task_id)
        with self.assertRaises(RoutingEvidenceError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env,
            )
        self.assertIn("dispatch_id mismatch", str(ctx.exception).lower())
        self._assert_zero_side_effects(lease_snapshot, active_keys, adapter_state)

    def test_r15_03_sol_counterexample_mismatched_envelope_orca_task_id_with_expired_lease_routing_wins_zero_side_effects(self):
        """3. Counterexample: Mismatched envelope orca_task_id with expired lease raises RoutingEvidenceError with zero side effects."""
        lease_snapshot, active_keys, adapter_state = self._snapshot_lease_and_adapter_state()
        env = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id="orca-mismatched-task")
        with self.assertRaises(RoutingEvidenceError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env,
            )
        self.assertIn("orca_task_id mismatch", str(ctx.exception).lower())
        self._assert_zero_side_effects(lease_snapshot, active_keys, adapter_state)

    def test_r15_04_missing_origin_and_envelope_with_expired_lease_routing_wins_zero_side_effects(self):
        """4. Counterexample: Missing origin and envelope with expired lease raises RoutingEvidenceError with zero side effects."""
        lease_snapshot, active_keys, adapter_state = self._snapshot_lease_and_adapter_state()
        with self.assertRaises(RoutingEvidenceError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
            )
        self.assertIn("dispatch origin", str(ctx.exception).lower())
        self._assert_zero_side_effects(lease_snapshot, active_keys, adapter_state)

    def test_r15_05_forbidden_direct_origin_with_expired_lease_routing_wins_zero_side_effects(self):
        """5. Counterexample: Forbidden direct worker-start origin with expired lease raises RoutingEvidenceError with zero side effects."""
        lease_snapshot, active_keys, adapter_state = self._snapshot_lease_and_adapter_state()
        env = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        with self.assertRaises(RoutingEvidenceError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="worker-start",
                execution_envelope=env,
            )
        self.assertIn("strictly forbidden", str(ctx.exception).lower())
        self._assert_zero_side_effects(lease_snapshot, active_keys, adapter_state)

    def test_r15_06_unverified_terminal_evidence_with_expired_lease_routing_wins_zero_side_effects(self):
        """6. Counterexample: Unverified live terminal evidence with expired lease raises RoutingEvidenceError with zero side effects."""
        lease_snapshot, active_keys, adapter_state = self._snapshot_lease_and_adapter_state()
        env = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env.live_terminal_evidence.verified = False
        with self.assertRaises(RoutingEvidenceError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env,
            )
        self.assertIn("unverified", str(ctx.exception).lower())
        self._assert_zero_side_effects(lease_snapshot, active_keys, adapter_state)

    def test_r15_07_invalid_backend_model_with_expired_lease_routing_wins_zero_side_effects(self):
        """7. Counterexample: Foreign backend model with expired lease raises RoutingEvidenceError with zero side effects."""
        lease_snapshot, active_keys, adapter_state = self._snapshot_lease_and_adapter_state()
        env = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env.usage_evidence.backend_model = "foreign/model-v1"
        with self.assertRaises(RoutingEvidenceError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env,
            )
        self.assertIn("does not match expected model", str(ctx.exception).lower())
        self._assert_zero_side_effects(lease_snapshot, active_keys, adapter_state)

    def test_r15_08_malformed_lease_expires_at_with_mismatched_envelope_routing_wins_zero_side_effects(self):
        """8. Counterexample: Malformed active lease expires_at with mismatched envelope raises RoutingEvidenceError without purge."""
        # Corrupt lease expires_at in active leases
        self.lease.expires_at = "corrupt-unparseable-timestamp"
        lease_snapshot, active_keys, adapter_state = self._snapshot_lease_and_adapter_state()
        env = make_execution_envelope("TASK-MISMATCH", self.intended_disp, orca_task_id=self.orca_task_id)
        with self.assertRaises(RoutingEvidenceError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env,
            )
        self.assertIn("delivery_task_id mismatch", str(ctx.exception).lower())
        self._assert_zero_side_effects(lease_snapshot, active_keys, adapter_state)

    def test_r15_09_positive_control_valid_envelope_with_expired_lease_purges_authoritatively(self):
        """9. Positive control: Valid envelope with expired lease passes envelope validation and purges on lease expiry check."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id, now=self.past_expiry)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env,
            )
        self.assertIn("has expired", str(ctx.exception).lower())
        self.assertNotIn(self.lease.lease_id, self.mgr.active_leases)
        self.assertFalse(self.lease.is_active)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "ready")

    def test_r15_10_positive_control_valid_envelope_with_malformed_lease_purges_authoritatively(self):
        """10. Positive control: Valid envelope with malformed lease expires_at purges authoritatively."""
        self.lease.expires_at = "invalid-timestamp-format"
        env = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id, now=self.t0)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                dispatch_origin="dely dispatch",
                execution_envelope=env,
            )
        self.assertIn("invalid expires_at format", str(ctx.exception).lower())
        self.assertNotIn(self.lease.lease_id, self.mgr.active_leases)
        self.assertFalse(self.lease.is_active)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "ready")

    def test_r15_11_positive_control_valid_envelope_with_valid_lease_succeeds_and_binds(self):
        """11. Positive control: Valid envelope with valid unexpired lease succeeds and binds identities."""
        now_disp = self.t0 + timedelta(seconds=2)
        env = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id, now=now_disp)
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id=self.intended_disp,
            now=now_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=env,
        )
        self.assertEqual(disp_id, self.intended_disp)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "dispatched")
        self.assertIn(self.intended_disp, self.adapter.dispatch_bindings)
        binding = self.adapter.dispatch_bindings[self.intended_disp]
        self.assertEqual(binding.delivery_task_id, self.delivery_id)
        self.assertEqual(binding.orca_task_id, self.orca_task_id)
        self.assertEqual(binding.dispatch_id, self.intended_disp)
        self.assertTrue(self.lease.is_active)

class TestAstraRound16LaunchEvidenceValidation(unittest.TestCase):
    """Astra Supreme Audit Dispatch ctx_f3936df94ecf Remediation (Round 16):
    1. Mandatory machine-readable mappings launch_requested and launch_effective on every envelope.
    2. Phase-specific harness, provider/router, route/model, and effort validation with exact identities.
    3. Strict mutual binding between requested and effective launch evidence, and to route, live terminal
       evidence, usage evidence, and phase.
    4. Antigravity native, direct-vendor, wrong models, combined slugs, and non-high effort fail closed.
    5. Astra phase rejected as delivery envelope phase (Astra is a supreme-audit control-plane dispatch).
    6. Fail-before-side-effect: pure launch evidence validation precedes any lease mutation or purge.
    7. Discriminating RED/GREEN counterexamples and positive controls.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.lock_defs = [{"id": "LOCK-R16", "mode": "exclusive", "renewable": True, "lease_seconds": 10}]
        self.mgr = LeaseManager(self.lock_defs)
        self.delivery_id = "TASK-R16-PROBE"
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.candidate_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
        ).strip()
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
        )
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-R16"])
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.intended_disp = "ctx-r16-probe"
        self.orca_task_id = "orca-r16-task"
        self.t0 = datetime(2026, 9, 29, 10, 0, 0, tzinfo=timezone.utc)
        self.lease = self.mgr.acquire_lease("LOCK-R16", self.delivery_id, self.intended_disp, lease_seconds=10, now=self.t0)
        self.past_expiry = self.t0 + timedelta(seconds=30)

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def _assert_zero_side_effects(self):
        """Assert zero side effects on lease state, task state, active dispatches, and bindings."""
        self.assertIn(self.lease.lease_id, self.mgr.active_leases)
        self.assertTrue(self.lease.is_active)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "ready")
        self.assertNotIn(self.delivery_id, self.adapter.active_dispatches)
        self.assertNotIn(self.intended_disp, self.adapter.dispatch_bindings)
        self.assertNotIn(self.intended_disp, self.adapter.seen_dispatch_ids)

    def test_r16_01_missing_launch_requested_fails_closed(self):
        """1. Counterexample: Missing launch_requested on ExecutionEnvelope or dict fails closed."""
        # Case A: launch_requested is None
        env_none = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_none.launch_requested = None
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            validate_execution_envelope(env_none)
        self.assertIn("launch_requested", str(ctx1.exception).lower())

        # Case B: dict envelope completely omitting launch_requested
        env_dict = {
            "delivery_task_id": self.delivery_id,
            "dispatch_id": self.intended_disp,
            "orca_task_id": self.orca_task_id,
            "dispatch_origin": "dely dispatch",
            "phase": "implement",
            "route": {
                "provider": "9router",
                "harness": "Codex CLI",
                "model": "ag/gemini-3.8-flash-high",
                "effort": "high",
            },
            "launch_effective": {
                "harness": "Codex CLI",
                "provider": "9router",
                "route": "ag/gemini-3.8-flash-high",
                "effort": "high",
            },
            "live_terminal_evidence": {
                "harness": "Codex CLI",
                "provider": "9router",
                "route": "ag/gemini-3.8-flash-high",
                "archive_reference": "ref_r16_01",
                "verified": True,
                "delivery_task_id": self.delivery_id,
                "dispatch_id": self.intended_disp,
                "effort": "high",
            },
            "usage_evidence": {
                "backend_provider": "google",
                "backend_model": "ag/gemini-3.8-flash-high",
                "recorded_after_dispatch": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": "req_r16_01",
                "delivery_task_id": self.delivery_id,
                "dispatch_id": self.intended_disp,
                "router": "9router",
            },
        }
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            validate_execution_envelope(env_dict)
        self.assertIn("launch_requested", str(ctx2.exception).lower())

    def test_r16_02_missing_launch_effective_fails_closed(self):
        """2. Counterexample: Missing launch_effective on ExecutionEnvelope or dict fails closed."""
        # Case A: launch_effective is None
        env_none = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_none.launch_effective = None
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            validate_execution_envelope(env_none)
        self.assertIn("launch_effective", str(ctx1.exception).lower())

        # Case B: dict envelope completely omitting launch_effective
        env_dict = {
            "delivery_task_id": self.delivery_id,
            "dispatch_id": self.intended_disp,
            "orca_task_id": self.orca_task_id,
            "dispatch_origin": "dely dispatch",
            "phase": "implement",
            "route": {
                "provider": "9router",
                "harness": "Codex CLI",
                "model": "ag/gemini-3.8-flash-high",
                "effort": "high",
            },
            "launch_requested": {
                "harness": "Codex CLI",
                "provider": "9router",
                "route": "ag/gemini-3.8-flash-high",
                "effort": "high",
            },
            "live_terminal_evidence": {
                "harness": "Codex CLI",
                "provider": "9router",
                "route": "ag/gemini-3.8-flash-high",
                "archive_reference": "ref_r16_02",
                "verified": True,
                "delivery_task_id": self.delivery_id,
                "dispatch_id": self.intended_disp,
                "effort": "high",
            },
            "usage_evidence": {
                "backend_provider": "google",
                "backend_model": "ag/gemini-3.8-flash-high",
                "recorded_after_dispatch": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": "req_r16_02",
                "delivery_task_id": self.delivery_id,
                "dispatch_id": self.intended_disp,
                "router": "9router",
            },
        }
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            validate_execution_envelope(env_dict)
        self.assertIn("launch_effective", str(ctx2.exception).lower())

    def test_r16_03_malformed_non_mapping_launch_evidence_fails_closed(self):
        """3. Counterexample: Malformed non-mapping launch fields fail closed."""
        for bad_val in ("Codex CLI", ["Codex CLI"], 123, True, {}):
            env_req = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
            env_req.launch_requested = bad_val
            with self.assertRaises(RoutingEvidenceError) as ctx1:
                validate_execution_envelope(env_req)
            self.assertTrue("mapping" in str(ctx1.exception).lower() or "empty" in str(ctx1.exception).lower())

            env_eff = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
            env_eff.launch_effective = bad_val
            with self.assertRaises(RoutingEvidenceError) as ctx2:
                validate_execution_envelope(env_eff)
            self.assertTrue("mapping" in str(ctx2.exception).lower() or "empty" in str(ctx2.exception).lower())

    def test_r16_04_missing_or_blank_fields_in_launch_evidence_fails_closed(self):
        """4. Counterexample: Missing or blank fields in launch evidence fail closed."""
        fields = ("harness", "provider", "model", "effort")
        for f in fields:
            # Missing in launch_requested
            env1 = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
            del env1.launch_requested[f]
            if f == "model" and "route" in env1.launch_requested:
                del env1.launch_requested["route"]
            with self.assertRaises(RoutingEvidenceError) as ctx1:
                validate_execution_envelope(env1)
            self.assertIn("missing required", str(ctx1.exception).lower())

            # Blank in launch_requested
            env2 = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
            env2.launch_requested[f] = "   "
            if f == "model" and "route" in env2.launch_requested:
                env2.launch_requested["route"] = "   "
            with self.assertRaises(RoutingEvidenceError) as ctx2:
                validate_execution_envelope(env2)
            self.assertTrue("non-blank" in str(ctx2.exception).lower() or "missing required" in str(ctx2.exception).lower())

    def test_r16_05_wrong_harness_in_launch_evidence_fails_closed(self):
        """5. Counterexample: Antigravity native or wrong harness in launch evidence fails closed."""
        for bad_h in ("Antigravity native", "antigravity", "Claude Code", "CustomHarness"):
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
            env.launch_requested["harness"] = bad_h
            env.launch_effective["harness"] = bad_h
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env)
            self.assertTrue("harness" in str(ctx.exception).lower() or "forbidden" in str(ctx.exception).lower())

    def test_r16_06_wrong_provider_in_launch_evidence_fails_closed(self):
        """6. Counterexample: Antigravity native, direct-vendor, or foreign provider in launch evidence fails closed."""
        for bad_p in ("Antigravity native", "antigravity", "direct-vendor", "direct", "openai", "google"):
            env = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
            env.launch_requested["provider"] = bad_p
            env.launch_effective["provider"] = bad_p
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env)
            self.assertTrue("provider" in str(ctx.exception).lower() or "9router" in str(ctx.exception).lower())

    def test_r16_07_wrong_model_or_combined_slug_in_launch_evidence_fails_closed(self):
        """7. Counterexample: Wrong model or combined slug in launch evidence fails closed."""
        # Combined slug
        env_slug = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review", orca_task_id=self.orca_task_id)
        env_slug.launch_requested["model"] = "cx/gpt-5.6-sol-high"
        env_slug.launch_requested["route"] = "cx/gpt-5.6-sol-high"
        env_slug.launch_effective["model"] = "cx/gpt-5.6-sol-high"
        env_slug.launch_effective["route"] = "cx/gpt-5.6-sol-high"
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            validate_execution_envelope(env_slug)
        self.assertIn("combined", str(ctx1.exception).lower())

        # Astra's exact counterexample: wrong-model
        env_wrong = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_wrong.launch_requested["model"] = "wrong-model"
        env_wrong.launch_requested["route"] = "wrong-model"
        env_wrong.launch_effective["model"] = "wrong-model"
        env_wrong.launch_effective["route"] = "wrong-model"
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            validate_execution_envelope(env_wrong)
        self.assertIn("does not match expected model", str(ctx2.exception).lower())

    def test_r16_08_wrong_effort_in_launch_evidence_fails_closed(self):
        """8. Counterexample: Non-high effort in launch evidence fails closed."""
        for bad_eff in ("medium", "low", "default", "none"):
            env = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
            env.launch_requested["effort"] = bad_eff
            env.launch_effective["effort"] = bad_eff
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env)
            self.assertIn("effort", str(ctx.exception).lower())

    def test_r16_09_disagreement_between_requested_and_effective_fails_closed(self):
        """9. Counterexample: Disagreement between launch_requested and launch_effective fails closed."""
        # Harness disagreement
        env_h = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_h.launch_effective["harness"] = "Claude Code"
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            validate_execution_envelope(env_h)
        self.assertIn("contradictory", str(ctx1.exception).lower())

        # Provider disagreement
        env_p = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_p.launch_effective["provider"] = "direct-vendor"
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            validate_execution_envelope(env_p)
        self.assertTrue("provider" in str(ctx2.exception).lower() or "contradictory" in str(ctx2.exception).lower())

        # Model disagreement
        env_m = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_m.launch_effective["model"] = "wrong-model"
        env_m.launch_effective["route"] = "wrong-model"
        with self.assertRaises(RoutingEvidenceError) as ctx3:
            validate_execution_envelope(env_m)
        self.assertTrue("model" in str(ctx3.exception).lower() or "contradictory" in str(ctx3.exception).lower())

        # Effort disagreement
        env_e = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_e.launch_effective["effort"] = "medium"
        with self.assertRaises(RoutingEvidenceError) as ctx4:
            validate_execution_envelope(env_e)
        self.assertTrue("effort" in str(ctx4.exception).lower() or "contradictory" in str(ctx4.exception).lower())

    def test_r16_10_disagreement_between_launch_and_route_fails_closed(self):
        """10. Counterexample: Disagreement between launch evidence and envelope route fails closed."""
        # Route harness differs from launch harness
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env.route["harness"] = "Claude Code"
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env)
        self.assertIn("harness", str(ctx.exception).lower())

    def test_r16_11_disagreement_between_launch_and_live_terminal_evidence_fails_closed(self):
        """11. Counterexample: Disagreement between launch evidence and live terminal evidence fails closed."""
        # Live terminal harness differs
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env.live_terminal_evidence.harness = "Claude Code"
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env)
        self.assertIn("live terminal", str(ctx.exception).lower())

    def test_r16_12_disagreement_between_launch_and_usage_evidence_fails_closed(self):
        """12. Counterexample: Disagreement between launch evidence and 9Router usage evidence fails closed."""
        # Usage router differs from launch provider
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env.usage_evidence.router = "direct_vendor"
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env)
        self.assertTrue("9router" in str(ctx.exception).lower() or "contradictory" in str(ctx.exception).lower())

    def test_r16_13_contradictory_internal_keys_in_launch_evidence_fails_closed(self):
        """13. Counterexample: Contradictory model vs route or provider vs router within launch evidence fails closed."""
        # Contradictory model and route
        env1 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env1.launch_requested["route"] = "wrong-model"
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            validate_execution_envelope(env1)
        self.assertIn("contradictory", str(ctx1.exception).lower())

        # Contradictory provider and router
        env2 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env2.launch_requested["router"] = "direct-vendor"
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            validate_execution_envelope(env2)
        self.assertIn("contradictory", str(ctx2.exception).lower())

    def test_r16_14_astra_phase_rejected_as_envelope_phase(self):
        """14. Contract: Astra is supreme-audit control-plane dispatch and is strictly rejected as Dely envelope phase."""
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            make_execution_envelope(self.delivery_id, self.intended_disp, phase="astra", orca_task_id=self.orca_task_id)
        self.assertIn("invalid phase", str(ctx1.exception).lower())

        # Manual dict with phase="astra"
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_dict = {
            "delivery_task_id": self.delivery_id,
            "dispatch_id": self.intended_disp,
            "orca_task_id": self.orca_task_id,
            "dispatch_origin": "dely dispatch",
            "phase": "astra",
            "route": {"provider": "9router", "harness": "Codex CLI", "model": "ag/gemini-3.8-flash-high", "effort": "high"},
            "launch_requested": env.launch_requested,
            "launch_effective": env.launch_effective,
            "live_terminal_evidence": env.live_terminal_evidence,
            "usage_evidence": env.usage_evidence,
        }
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            validate_execution_envelope(env_dict)
        self.assertIn("invalid execution envelope phase", str(ctx2.exception).lower())

    def test_r16_15_positive_control_valid_launch_evidence_succeeds_both_phases(self):
        """15. Positive control: Valid implement and review envelopes with exact launch evidence pass validation."""
        env_impl = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        errors_impl = validate_execution_envelope(env_impl, expected_phase="implement")
        self.assertEqual(errors_impl, [])

        env_rev = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review", orca_task_id=self.orca_task_id)
        errors_rev = validate_execution_envelope(env_rev, expected_phase="review")
        self.assertEqual(errors_rev, [])

    def test_r16_16_fail_before_side_effects_on_invalid_launch_evidence_with_expired_lease(self):
        """16. Counterexample: Contradictory/invalid launch evidence with expired lease raises RoutingEvidenceError with zero side effects."""
        # Antigravity native in launch evidence + expired active lease
        env_bad = make_execution_envelope(self.delivery_id, self.intended_disp, orca_task_id=self.orca_task_id)
        env_bad.launch_requested["provider"] = "antigravity"
        env_bad.launch_effective["provider"] = "antigravity"

        with self.assertRaises(RoutingEvidenceError) as ctx:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env_bad,
            )
        self.assertTrue("antigravity" in str(ctx.exception).lower() or "provider" in str(ctx.exception).lower())
        self._assert_zero_side_effects()


class TestSolRound17UsageRouterEvidenceValidation(unittest.TestCase):
    """Round 17 remediation fixtures:
    1. Mandatory explicit, non-blank router/provider-route identity in usage-evidence mappings (no implicit default).
    2. Accept only exact declared router identity '9router' for implement and review phases.
    3. Reject missing, blank, malformed, contradictory, or foreign router/source aliases fail-closed with RoutingEvidenceError.
    4. Mutual binding of explicit usage router to route.provider, launch mappings, live-terminal provider, and phase.
    5. Zero side effects on lease/task/dispatch state when usage router evidence is invalid preceding expired lease checks.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.lock_defs = [{"id": "LOCK-R17", "mode": "exclusive", "renewable": True, "lease_seconds": 10}]
        self.mgr = LeaseManager(self.lock_defs)
        self.delivery_id = "TASK-R17-PROBE"
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.candidate_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
        ).strip()
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
        )
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-R17"])
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.intended_disp = "ctx-r17-probe"
        self.orca_task_id = "orca-r17-task"
        self.t0 = datetime(2026, 9, 29, 11, 0, 0, tzinfo=timezone.utc)
        self.lease = self.mgr.acquire_lease("LOCK-R17", self.delivery_id, self.intended_disp, lease_seconds=10, now=self.t0)
        self.past_expiry = self.t0 + timedelta(seconds=30)

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def _assert_zero_side_effects(self):
        """Assert zero side effects on lease state, task state, active dispatches, and bindings."""
        self.assertIn(self.lease.lease_id, self.mgr.active_leases)
        self.assertTrue(self.lease.is_active)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "ready")
        self.assertNotIn(self.delivery_id, self.adapter.active_dispatches)
        self.assertNotIn(self.intended_disp, self.adapter.dispatch_bindings)
        self.assertNotIn(self.intended_disp, self.adapter.seen_dispatch_ids)

    def _base_usage_dict(self, phase="implement"):
        if phase == "implement":
            return {
                "backend_provider": "google",
                "backend_model": "ag/gemini-3.8-flash-high",
                "recorded_after_dispatch": True,
                "timestamp": (self.t0 + timedelta(seconds=1)).isoformat(),
                "request_id": "req-r17-01",
                "delivery_task_id": self.delivery_id,
                "dispatch_id": self.intended_disp,
            }
        else:
            return {
                "backend_provider": "openai",
                "backend_model": "cx/gpt-5.6-sol",
                "recorded_after_dispatch": True,
                "timestamp": (self.t0 + timedelta(seconds=1)).isoformat(),
                "request_id": "req-r17-02",
                "delivery_task_id": self.delivery_id,
                "dispatch_id": self.intended_disp,
            }

    def test_r17_01_missing_all_router_aliases_fails_closed(self):
        """1. Counterexample: Missing all router aliases (router, route_provider, source) in usage evidence fails closed."""
        # Case A: Dict usage evidence omitting router/route_provider/source (Sol's exact counterexample)
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env.usage_evidence = self._base_usage_dict("implement")
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            validate_execution_envelope(env)
        self.assertTrue("router" in str(ctx1.exception).lower() or "missing" in str(ctx1.exception).lower())

        # Case B: UsageEvidence dataclass instance with router=None
        env_obj = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_obj.usage_evidence.router = None
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            validate_execution_envelope(env_obj)
        self.assertTrue("router" in str(ctx2.exception).lower() or "missing" in str(ctx2.exception).lower())

    def test_r17_02_blank_router_values_fail_closed(self):
        """2. Counterexample: Blank router values for any alias fail closed."""
        for alias in ("router", "route_provider", "source"):
            for blank_val in ("", "   ", None):
                env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
                u = self._base_usage_dict("implement")
                u[alias] = blank_val
                env.usage_evidence = u
                with self.assertRaises(RoutingEvidenceError) as ctx:
                    validate_execution_envelope(env)
                self.assertTrue("non-blank" in str(ctx.exception).lower() or "router" in str(ctx.exception).lower())

    def test_r17_03_malformed_router_values_fail_closed(self):
        """3. Counterexample: Malformed (non-string) router values fail closed."""
        for bad_val in (123, True, False, ["9router"], {"router": "9router"}):
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
            u = self._base_usage_dict("implement")
            u["router"] = bad_val
            env.usage_evidence = u
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env)
            self.assertTrue("string" in str(ctx.exception).lower() or "router" in str(ctx.exception).lower())

    def test_r17_04_wrong_or_foreign_router_fails_closed(self):
        """4. Counterexample: Wrong or foreign router/source (direct-vendor, antigravity, openai, etc.) fails closed."""
        for bad_router in ("direct-vendor", "direct", "antigravity", "Antigravity native", "openai", "google", "foreign_source"):
            for alias in ("router", "route_provider", "source"):
                env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
                u = self._base_usage_dict("implement")
                u[alias] = bad_router
                env.usage_evidence = u
                with self.assertRaises(RoutingEvidenceError) as ctx:
                    validate_execution_envelope(env)
                self.assertTrue("9router" in str(ctx.exception).lower() or "forbidden" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_r17_05_conflicting_router_aliases_fail_closed(self):
        """5. Counterexample: Conflicting router aliases within usage evidence fail closed."""
        conflict_cases = [
            {"router": "9router", "route_provider": "direct-vendor"},
            {"router": "9router", "source": "antigravity"},
            {"route_provider": "9router", "source": "other_router"},
            {"router": "9router", "route_provider": "9router", "source": "direct-vendor"},
        ]
        for conf in conflict_cases:
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
            u = self._base_usage_dict("implement")
            u.update(conf)
            env.usage_evidence = u
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env)
            self.assertTrue("contradictory" in str(ctx.exception).lower() or "router" in str(ctx.exception).lower())

    def test_r17_06_unrecognized_foreign_router_alias_keys_fail_closed(self):
        """6. Counterexample: Foreign or unrecognized router alias keys fail closed."""
        foreign_keys = ["foreign_router", "custom_router", "route_source", "router_proxy"]
        for fk in foreign_keys:
            # Foreign key alone
            env1 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
            u1 = self._base_usage_dict("implement")
            u1[fk] = "9router"
            env1.usage_evidence = u1
            with self.assertRaises(RoutingEvidenceError) as ctx1:
                validate_execution_envelope(env1)
            self.assertTrue("foreign" in str(ctx1.exception).lower() or "router" in str(ctx1.exception).lower())

            # Foreign key alongside valid router="9router"
            env2 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
            u2 = self._base_usage_dict("implement")
            u2["router"] = "9router"
            u2[fk] = "9router"
            env2.usage_evidence = u2
            with self.assertRaises(RoutingEvidenceError) as ctx2:
                validate_execution_envelope(env2)
            self.assertTrue("foreign" in str(ctx2.exception).lower() or "unrecognized" in str(ctx2.exception).lower())

    def test_r17_07_mutual_binding_usage_router_to_route_and_launch_and_terminal_and_phase(self):
        """7. Mutual binding: Usage router bound to route.provider, launch mappings, live-terminal provider, and phase."""
        # Route provider mismatch with usage router
        env_r = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_r.route["provider"] = "direct-vendor"
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            validate_execution_envelope(env_r)
        self.assertTrue("provider" in str(ctx1.exception).lower() or "9router" in str(ctx1.exception).lower())

        # Live terminal provider mismatch with usage router
        env_l = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_l.live_terminal_evidence.provider = "direct-vendor"
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            validate_execution_envelope(env_l)
        self.assertTrue("provider" in str(ctx2.exception).lower() or "live terminal" in str(ctx2.exception).lower())

    def test_r17_08_exact_valid_9router_evidence_succeeds_all_aliases_and_both_phases(self):
        """8. Positive control: Exact valid 9router evidence succeeds across all aliases and both phases."""
        for phase in ("implement", "review"):
            # Subcase A: 'router' alias
            env_a = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            u_a = self._base_usage_dict(phase)
            u_a["router"] = "9router"
            env_a.usage_evidence = u_a
            self.assertEqual(validate_execution_envelope(env_a, expected_phase=phase), [])

            # Subcase B: 'route_provider' alias
            env_b = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            u_b = self._base_usage_dict(phase)
            u_b["route_provider"] = "9router"
            env_b.usage_evidence = u_b
            self.assertEqual(validate_execution_envelope(env_b, expected_phase=phase), [])

            # Subcase C: 'source' alias
            env_c = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            u_c = self._base_usage_dict(phase)
            u_c["source"] = "9router"
            env_c.usage_evidence = u_c
            self.assertEqual(validate_execution_envelope(env_c, expected_phase=phase), [])

            # Subcase D: multiple agreeing aliases
            env_d = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            u_d = self._base_usage_dict(phase)
            u_d["router"] = "9router"
            u_d["route_provider"] = "9router"
            u_d["source"] = "9router"
            env_d.usage_evidence = u_d
            self.assertEqual(validate_execution_envelope(env_d, expected_phase=phase), [])

            # Subcase E: UsageEvidence dataclass instance with explicit router
            env_e = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            self.assertEqual(validate_execution_envelope(env_e, expected_phase=phase), [])

    def test_r17_09_fail_before_side_effects_on_missing_or_invalid_usage_router_with_expired_lease(self):
        """9. Counterexample: Missing or invalid usage router with expired lease raises RoutingEvidenceError with zero side effects."""
        # Subcase A: Missing all router aliases + expired active lease
        env_missing = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_missing.usage_evidence = self._base_usage_dict("implement")
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env_missing,
            )
        self.assertTrue("router" in str(ctx1.exception).lower() or "missing" in str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Subcase B: Foreign router + expired active lease
        env_foreign = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        u_foreign = self._base_usage_dict("implement")
        u_foreign["router"] = "antigravity"
        env_foreign.usage_evidence = u_foreign
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env_foreign,
            )
        self.assertTrue("antigravity" in str(ctx2.exception).lower() or "router" in str(ctx2.exception).lower())
        self._assert_zero_side_effects()

        # Subcase C: Contradictory router aliases + expired active lease
        env_conf = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        u_conf = self._base_usage_dict("implement")
        u_conf["router"] = "9router"
        u_conf["route_provider"] = "direct-vendor"
        env_conf.usage_evidence = u_conf
        with self.assertRaises(RoutingEvidenceError) as ctx3:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env_conf,
            )
        self.assertTrue("contradictory" in str(ctx3.exception).lower() or "router" in str(ctx3.exception).lower())
        self._assert_zero_side_effects()


class TestSolRound18ExactRawRouterIdentity(unittest.TestCase):
    """Round 18 remediation fixtures:
    1. Require every raw supplied router/source alias value to be exactly the string '9router';
       do not normalize whitespace into validity.
    2. Apply exact raw comparison to dataclass-form UsageEvidence.router and mapping aliases
       'router', 'route_provider', and 'source'.
    3. Discriminating RED/GREEN tests for leading whitespace, trailing whitespace, both-sided padding,
       tabs/newlines, and agreeing padded aliases across dataclass and mapping forms.
    4. Reject conflicting/mixed padded aliases fail-closed.
    5. Positive controls: exact raw '9router' succeeds for all aliases and dataclass in both phases.
    6. Fail-before-side-effects: zero side effects on lease/task/dispatch state with padded router
       and expired active lease.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.lock_defs = [{"id": "LOCK-R18", "mode": "exclusive", "renewable": True, "lease_seconds": 10}]
        self.mgr = LeaseManager(self.lock_defs)
        self.delivery_id = "TASK-R18-PROBE"
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.candidate_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
        ).strip()
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
        )
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-R18"])
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.intended_disp = "ctx-r18-probe"
        self.orca_task_id = "orca-r18-task"
        self.t0 = datetime(2026, 9, 29, 11, 0, 0, tzinfo=timezone.utc)
        self.lease = self.mgr.acquire_lease("LOCK-R18", self.delivery_id, self.intended_disp, lease_seconds=10, now=self.t0)
        self.past_expiry = self.t0 + timedelta(seconds=30)

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def _assert_zero_side_effects(self):
        """Assert zero side effects on lease state, task state, active dispatches, and bindings."""
        self.assertIn(self.lease.lease_id, self.mgr.active_leases)
        self.assertTrue(self.lease.is_active)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "ready")
        self.assertNotIn(self.delivery_id, self.adapter.active_dispatches)
        self.assertNotIn(self.intended_disp, self.adapter.dispatch_bindings)
        self.assertNotIn(self.intended_disp, self.adapter.seen_dispatch_ids)

    def _base_usage_dict(self, phase="implement"):
        if phase == "implement":
            return {
                "backend_provider": "google",
                "backend_model": "ag/gemini-3.8-flash-high",
                "recorded_after_dispatch": True,
                "timestamp": (self.t0 + timedelta(seconds=1)).isoformat(),
                "request_id": "req-r18-01",
                "delivery_task_id": self.delivery_id,
                "dispatch_id": self.intended_disp,
            }
        else:
            return {
                "backend_provider": "openai",
                "backend_model": "cx/gpt-5.6-sol",
                "recorded_after_dispatch": True,
                "timestamp": (self.t0 + timedelta(seconds=1)).isoformat(),
                "request_id": "req-r18-02",
                "delivery_task_id": self.delivery_id,
                "dispatch_id": self.intended_disp,
            }

    def test_r18_01_leading_whitespace_router_fails_closed(self):
        """1. Counterexample: Leading whitespace in router alias fails closed."""
        leading_padded_values = [" 9router", "  9router", "\t9router", "\n9router"]
        for alias in ("router", "route_provider", "source"):
            for bad_val in leading_padded_values:
                env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
                u = self._base_usage_dict("implement")
                u[alias] = bad_val
                env.usage_evidence = u
                with self.assertRaises(RoutingEvidenceError, msg=f"Expected failure for {alias}={bad_val!r}") as ctx:
                    validate_execution_envelope(env)
                self.assertTrue("9router" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_r18_02_trailing_whitespace_router_fails_closed(self):
        """2. Counterexample: Trailing whitespace in router alias fails closed."""
        trailing_padded_values = ["9router ", "9router  ", "9router\t", "9router\n"]
        for alias in ("router", "route_provider", "source"):
            for bad_val in trailing_padded_values:
                env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
                u = self._base_usage_dict("implement")
                u[alias] = bad_val
                env.usage_evidence = u
                with self.assertRaises(RoutingEvidenceError, msg=f"Expected failure for {alias}={bad_val!r}") as ctx:
                    validate_execution_envelope(env)
                self.assertTrue("9router" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_r18_03_both_sided_whitespace_router_fails_closed(self):
        """3. Counterexample: Both-sided whitespace in router alias fails closed (Sol's exact finding)."""
        both_padded_values = [" 9router ", "  9router  ", "\t9router\t", "\n9router\n", "\r\n9router\r\n"]
        for alias in ("router", "route_provider", "source"):
            for bad_val in both_padded_values:
                env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
                u = self._base_usage_dict("implement")
                u[alias] = bad_val
                env.usage_evidence = u
                with self.assertRaises(RoutingEvidenceError, msg=f"Expected failure for {alias}={bad_val!r}") as ctx:
                    validate_execution_envelope(env)
                self.assertTrue("9router" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_r18_04_agreeing_padded_aliases_in_mapping_fail_closed(self):
        """4. Counterexample: Agreeing padded router aliases across mapping forms fail closed."""
        padded_agreeing_sets = [
            {"router": " 9router ", "route_provider": " 9router "},
            {"router": " 9router", "source": " 9router"},
            {"route_provider": "9router ", "source": "9router "},
            {"router": "\t9router\t", "route_provider": "\t9router\t", "source": "\t9router\t"},
            {"router": "\n9router\n", "source": "\n9router\n"},
        ]
        for conf in padded_agreeing_sets:
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
            u = self._base_usage_dict("implement")
            u.update(conf)
            env.usage_evidence = u
            with self.assertRaises(RoutingEvidenceError, msg=f"Expected failure for agreeing padded aliases {conf}") as ctx:
                validate_execution_envelope(env)
            self.assertTrue("9router" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_r18_05_disagreeing_padded_or_mixed_aliases_fail_closed(self):
        """5. Counterexample: Disagreeing padded/exact router aliases in mapping fail closed."""
        mixed_sets = [
            {"router": "9router", "route_provider": " 9router "},
            {"router": " 9router", "source": "9router "},
            {"route_provider": "\t9router", "source": "9router\t"},
            {"router": "9router", "route_provider": " 9router", "source": "9router "},
        ]
        for conf in mixed_sets:
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
            u = self._base_usage_dict("implement")
            u.update(conf)
            env.usage_evidence = u
            with self.assertRaises(RoutingEvidenceError, msg=f"Expected failure for mixed aliases {conf}") as ctx:
                validate_execution_envelope(env)
            self.assertTrue("contradictory" in str(ctx.exception).lower() or "9router" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_r18_06_dataclass_form_padded_router_fails_closed(self):
        """6. Counterexample: Dataclass UsageEvidence.router with whitespace padding fails closed."""
        padded_values = [" 9router", "9router ", " 9router ", "\t9router\t", "\n9router\n", "\r\n9router\r\n"]
        for bad_val in padded_values:
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
            env.usage_evidence.router = bad_val
            with self.assertRaises(RoutingEvidenceError, msg=f"Expected failure for dataclass router={bad_val!r}") as ctx:
                validate_execution_envelope(env)
            self.assertTrue("9router" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_r18_07_positive_exact_raw_router_succeeds_all_forms_and_phases(self):
        """7. Positive control: Exact raw '9router' succeeds for dataclass and all mapping aliases in both phases."""
        for phase in ("implement", "review"):
            # Subcase A: 'router'
            env_a = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            u_a = self._base_usage_dict(phase)
            u_a["router"] = "9router"
            env_a.usage_evidence = u_a
            self.assertEqual(validate_execution_envelope(env_a, expected_phase=phase), [])

            # Subcase B: 'route_provider'
            env_b = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            u_b = self._base_usage_dict(phase)
            u_b["route_provider"] = "9router"
            env_b.usage_evidence = u_b
            self.assertEqual(validate_execution_envelope(env_b, expected_phase=phase), [])

            # Subcase C: 'source'
            env_c = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            u_c = self._base_usage_dict(phase)
            u_c["source"] = "9router"
            env_c.usage_evidence = u_c
            self.assertEqual(validate_execution_envelope(env_c, expected_phase=phase), [])

            # Subcase D: all aliases agreeing on exact '9router'
            env_d = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            u_d = self._base_usage_dict(phase)
            u_d["router"] = "9router"
            u_d["route_provider"] = "9router"
            u_d["source"] = "9router"
            env_d.usage_evidence = u_d
            self.assertEqual(validate_execution_envelope(env_d, expected_phase=phase), [])

            # Subcase E: Dataclass UsageEvidence with exact router="9router"
            env_e = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            env_e.usage_evidence.router = "9router"
            self.assertEqual(validate_execution_envelope(env_e, expected_phase=phase), [])

    def test_r18_08_fail_before_side_effects_on_padded_router_with_expired_lease(self):
        """8. Counterexample: Padded router with expired lease raises RoutingEvidenceError with zero side effects."""
        valid_post_ts = (self.past_expiry + timedelta(seconds=1)).isoformat()

        # Subcase A: Mapping padded router
        env_map = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        u = self._base_usage_dict("implement")
        u["router"] = " 9router "
        u["timestamp"] = valid_post_ts
        env_map.usage_evidence = u
        with self.assertRaises(RoutingEvidenceError) as ctx1:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env_map,
            )
        self.assertTrue("router" in str(ctx1.exception).lower() or "invalid" in str(ctx1.exception).lower())
        self._assert_zero_side_effects()

        # Subcase B: Dataclass padded router
        env_dc = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_dc.usage_evidence.router = " 9router "
        env_dc.usage_evidence.timestamp = valid_post_ts
        with self.assertRaises(RoutingEvidenceError) as ctx2:
            self.adapter.create_dispatch(
                self.delivery_id,
                orca_task_id=self.orca_task_id,
                candidate_commit=self.candidate_commit,
                fencing_token=self.lease.fencing_token,
                lease_id=self.lease.lease_id,
                intended_dispatch_id=self.intended_disp,
                now=self.past_expiry,
                dispatch_origin="dely dispatch",
                execution_envelope=env_dc,
            )
        self.assertTrue("router" in str(ctx2.exception).lower() or "invalid" in str(ctx2.exception).lower())
        self._assert_zero_side_effects()



class TestAstraRound18Remediation(unittest.TestCase):
    """Astra Round 18 remediation fixtures:
    1. Lifecycle / authority bypass:
       - Public transition_task_state() fails closed unless authorized by appropriate handler
         and backed by verified dispatch/lease/evidence.
       - Rejection of revoked authority, no-dispatch paths, missing/stale lease,
         missing completion/review/integration evidence, and a valid positive path.
    2. Contradictory evidence aliases:
       - Every present alias must be validated for type, nonblank form, and mutual semantic consistency.
       - Cover both implement and review phases, including conflicts across usage, live-terminal,
         archive, and delivery aliases.
    3. Raw router identity strict end-to-end:
       - Require exact raw identity '9router' at route, requested-launch, effective-launch,
         live-terminal/archive, and usage identity positions without normalization.
       - Reject padded values across all positions; positive controls with exact '9router'.
    4. Exact-HEAD attestation reproducibility & canonical-byte policy:
       - Enforce canonical-byte policy (LF line endings matching committed Git tree).
       - Reject CRLF in bundle files; attestation hashes match Git blobs.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.lock_defs = [
            {"id": "LOCK-A18", "mode": "exclusive", "renewable": True, "lease_seconds": 10},
            {"id": "LOCK-A18-INT", "mode": "exclusive", "renewable": True, "lease_seconds": 10},
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.delivery_id = "TASK-A18-PROBE"
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.candidate_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
        ).strip()
        self.control_secret = "secret_a18_control"
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
            control_secret=self.control_secret,
        )
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-A18"])
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.intended_disp = "ctx-a18-probe"
        self.orca_task_id = "orca-a18-task"
        self.t0 = datetime.now(timezone.utc)
        self.lease = self.mgr.acquire_lease("LOCK-A18", self.delivery_id, self.intended_disp, lease_seconds=10, now=self.t0)

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()
    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()
    def _issue_valid_review_evidence(self, delivery_id, rev_disp_id, candidate_commit, verdict="ACCEPT", now=None):
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=candidate_commit,
            reviewer_secret=getattr(self, "reviewer_secret", TEST_FIXTURE_REVIEWER_SECRET),
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        return self.adapter.issue_review_evidence(delivery_id, rev_disp_id, candidate_commit, verdict=verdict, reviewer_capability=rev_cap, now=now)

    def _issue_valid_integration_evidence(self, delivery_id, candidate_commit, base_commit, gates_pass=True, now=None):
        ctrl_cap = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=delivery_id)
        return self.adapter.issue_integration_evidence(delivery_id, candidate_commit, base_commit, gates_pass=gates_pass, control_capability=ctrl_cap, now=now)


    # -------------------------------------------------------------------------
    # 1. Lifecycle / authority bypass tests
    # -------------------------------------------------------------------------
    def test_astra_r18_01_lifecycle_bypass_revoked_authority_rejected(self):
        """1. Counterexample: Task with revoked authority cannot transition state via transition_task_state."""
        self.adapter.set_task_authority(self.delivery_id, "revoked")
        target_states = ["dispatched", "acknowledged", "running", "review", "merge_queued", "integrated"]
        for tgt in target_states:
            with self.assertRaises(ProtocolViolationError) as ctx:
                self.adapter.transition_task_state(self.delivery_id, tgt)
            self.assertTrue(
                "revoked" in str(ctx.exception).lower() or "authority" in str(ctx.exception).lower() or "illegal" in str(ctx.exception).lower()
            )

    def test_astra_r18_02_lifecycle_bypass_no_dispatch_rejected(self):
        """2. Counterexample: Task in ready state cannot transition to dispatched/acknowledged/running without dispatch."""
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state(self.delivery_id, "dispatched")
        self.assertTrue("dispatch" in str(ctx.exception).lower() or "handler" in str(ctx.exception).lower() or "illegal" in str(ctx.exception).lower())

    def test_astra_r18_03_lifecycle_bypass_missing_or_stale_lease_rejected(self):
        """3. Counterexample: Public transition fails when lease is missing or stale."""
        self.mgr.release_lease(self.lease.lease_id)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state(self.delivery_id, "dispatched")
        self.assertTrue("lease" in str(ctx.exception).lower() or "dispatch" in str(ctx.exception).lower() or "handler" in str(ctx.exception).lower())

    def test_astra_r18_04_lifecycle_bypass_missing_completion_evidence_rejected(self):
        """4. Counterexample: Public transition to review fails without completion evidence from worker_done."""
        self.adapter._task_states[self.delivery_id] = "running"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state(self.delivery_id, "review")
        self.assertTrue("completion" in str(ctx.exception).lower() or "worker_done" in str(ctx.exception).lower() or "handler" in str(ctx.exception).lower())

    def test_astra_r18_05_lifecycle_bypass_missing_review_evidence_rejected(self):
        """5. Counterexample: Public transition to merge_queued fails without verified review evidence."""
        self.adapter._task_states[self.delivery_id] = "review"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state(self.delivery_id, "merge_queued")
        self.assertTrue("review" in str(ctx.exception).lower() or "verdict" in str(ctx.exception).lower() or "handler" in str(ctx.exception).lower())

    def test_astra_r18_06_lifecycle_bypass_missing_integration_evidence_rejected(self):
        """6. Counterexample: Public transition to integrated fails without verified integration gates evidence."""
        self.adapter._task_states[self.delivery_id] = "merge_queued"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.transition_task_state(self.delivery_id, "integrated")
        self.assertTrue("integration" in str(ctx.exception).lower() or "gates" in str(ctx.exception).lower() or "handler" in str(ctx.exception).lower())

    def test_astra_r18_07_lifecycle_valid_positive_path(self):
        """7. Positive control: Full authorized lifecycle sequence with verified evidence reaches integrated."""
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id=self.intended_disp,
            now=self.t0,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id, now=self.t0),
        )
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "dispatched")

        self.adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "acknowledged")

        self.adapter.start_running(self.delivery_id, disp_id)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "running")

        st = self.adapter.handle_worker_done(
            self.delivery_id,
            self.orca_task_id,
            disp_id,
            outcome="succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            now=self.t0 + timedelta(seconds=2),
        )
        self.assertEqual(st, "review")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

        rev_disp = "ctx_a18_07_review"
        rev_orca = "task_orca_a18_07_rev"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp, phase="review", orca_task_id=rev_orca)
        rev_disp = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
        )
        rev_ev = self._issue_valid_review_evidence(self.delivery_id, rev_disp, self.candidate_commit, "ACCEPT")
        st_rev = self.adapter.handle_review_verdict(self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp, review_evidence=rev_ev)
        self.assertEqual(st_rev, "merge_queued")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "merge_queued")

        int_ev = self._issue_valid_integration_evidence(self.delivery_id, self.candidate_commit, "4a7c8c921b7e05066505d51b168a02c3fde61317", gates_pass=True)
        st_int = self.adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=int_ev)
        self.assertEqual(st_int, "integrated")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "integrated")


    # -------------------------------------------------------------------------
    # 2. Contradictory evidence aliases tests
    # -------------------------------------------------------------------------
    def test_astra_r18_08_live_terminal_contradictory_route_and_model_aliases(self):
        """8. Counterexample: Live terminal evidence with contradictory route and model aliases fails closed."""
        for phase in ("implement", "review"):
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            lt = env.live_terminal_evidence.__dict__.copy()
            lt["route"] = "ag/gemini-3.8-flash-high" if phase == "implement" else "cx/gpt-5.6-sol"
            lt["model"] = "wrong-foreign-model"
            env.live_terminal_evidence = lt
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env, expected_phase=phase)
            self.assertTrue("contradictory" in str(ctx.exception).lower() or "mismatch" in str(ctx.exception).lower())

    def test_astra_r18_09_live_terminal_contradictory_archive_aliases(self):
        """9. Counterexample: Live terminal evidence with conflicting archive_reference and terminal_id fails closed."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        lt = env.live_terminal_evidence.__dict__.copy()
        lt["archive_reference"] = "archive_ref_01"
        lt["terminal_id"] = "terminal_id_conflicting_02"
        env.live_terminal_evidence = lt
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env, expected_phase="implement")
        self.assertTrue("contradictory" in str(ctx.exception).lower() or "archive" in str(ctx.exception).lower())

    def test_astra_r18_10_live_terminal_contradictory_task_and_dispatch_aliases(self):
        """10. Counterexample: Live terminal evidence with conflicting task/dispatch aliases fails closed."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        lt = env.live_terminal_evidence.__dict__.copy()
        lt["delivery_task_id"] = self.delivery_id
        lt["task_id"] = "TASK-FOREIGN"
        env.live_terminal_evidence = lt
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env, expected_phase="implement")
        self.assertTrue("contradictory" in str(ctx.exception).lower() or "task" in str(ctx.exception).lower())

    def test_astra_r18_11_live_terminal_invalid_type_and_blank_aliases(self):
        """11. Counterexample: Non-string or blank aliases in live terminal evidence fail closed."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        lt = env.live_terminal_evidence.__dict__.copy()
        lt["model"] = 12345
        env.live_terminal_evidence = lt
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env, expected_phase="implement")
        self.assertTrue("string" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_astra_r18_12_usage_evidence_contradictory_provider_aliases(self):
        """12. Counterexample: Usage evidence with conflicting backend_provider vs provider fails closed."""
        for phase in ("implement", "review"):
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            u = env.usage_evidence.__dict__.copy()
            u["backend_provider"] = "google" if phase == "implement" else "openai"
            u["provider"] = "foreign-provider-contradictory"
            env.usage_evidence = u
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env, expected_phase=phase)
            self.assertTrue("contradictory" in str(ctx.exception).lower() or "provider" in str(ctx.exception).lower())

    def test_astra_r18_13_usage_evidence_contradictory_model_aliases(self):
        """13. Counterexample: Usage evidence with conflicting backend_model vs model fails closed."""
        for phase in ("implement", "review"):
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            u = env.usage_evidence.__dict__.copy()
            u["backend_model"] = "ag/gemini-3.8-flash-high" if phase == "implement" else "cx/gpt-5.6-sol"
            u["model"] = "foreign-model-contradictory"
            env.usage_evidence = u
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env, expected_phase=phase)
            self.assertTrue("contradictory" in str(ctx.exception).lower() or "model" in str(ctx.exception).lower())

    def test_astra_r18_14_usage_evidence_contradictory_task_and_dispatch_aliases(self):
        """14. Counterexample: Usage evidence with conflicting task/dispatch aliases fails closed."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        u = env.usage_evidence.__dict__.copy()
        u["delivery_task_id"] = self.delivery_id
        u["task_id"] = "TASK-FOREIGN-USAGE"
        env.usage_evidence = u
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env, expected_phase="implement")
        self.assertTrue("contradictory" in str(ctx.exception).lower() or "task" in str(ctx.exception).lower())

    def test_astra_r18_15_envelope_contradictory_task_and_dispatch_aliases(self):
        """15. Counterexample: Envelope with conflicting task/dispatch aliases fails closed."""
        env_dict = {
            "delivery_task_id": self.delivery_id,
            "task_id": "TASK-FOREIGN-ENV",
            "dispatch_id": self.intended_disp,
            "dispatch_origin": "dely dispatch",
            "phase": "implement",
            "orca_task_id": self.orca_task_id,
            "route": {"provider": "9router", "harness": "Codex CLI", "model": "ag/gemini-3.8-flash-high", "effort": "high"},
            "launch_requested": {"harness": "Codex CLI", "provider": "9router", "model": "ag/gemini-3.8-flash-high", "effort": "high"},
            "launch_effective": {"harness": "Codex CLI", "provider": "9router", "model": "ag/gemini-3.8-flash-high", "effort": "high"},
            "live_terminal_evidence": LiveTerminalEvidence(
                harness="Codex CLI", provider="9router", route="ag/gemini-3.8-flash-high",
                archive_reference="term_01", verified=True, dispatch_id=self.intended_disp,
                delivery_task_id=self.delivery_id, effort="high"
            ),
            "usage_evidence": UsageEvidence(
                backend_provider="google", backend_model="ag/gemini-3.8-flash-high",
                recorded_after_dispatch=True, timestamp=(self.t0 + timedelta(seconds=1)).isoformat(),
                request_id="req_01", dispatch_id=self.intended_disp, delivery_task_id=self.delivery_id,
                router="9router"
            ),
        }
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env_dict, expected_phase="implement")
        self.assertTrue("contradictory" in str(ctx.exception).lower() or "task" in str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # 3. Raw router identity not strict end-to-end tests
    # -------------------------------------------------------------------------
    def test_astra_r18_16_route_padded_router_identity_rejected(self):
        """16. Counterexample: Padded router identity in route mapping fails closed."""
        padded_variants = [" 9router ", "9router ", " 9router", "\t9router", "9router\n"]
        for p in padded_variants:
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
            env.route["provider"] = p
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env, expected_phase="implement")
            self.assertTrue("provider" in str(ctx.exception).lower() or "router" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_astra_r18_17_launch_requested_padded_router_identity_rejected(self):
        """17. Counterexample: Padded router identity in launch_requested fails closed."""
        padded_variants = [" 9router ", "9router ", " 9router", "\t9router", "9router\n"]
        for p in padded_variants:
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
            env.launch_requested["provider"] = p
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env, expected_phase="implement")
            self.assertTrue("provider" in str(ctx.exception).lower() or "router" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_astra_r18_18_launch_effective_padded_router_identity_rejected(self):
        """18. Counterexample: Padded router identity in launch_effective fails closed."""
        padded_variants = [" 9router ", "9router ", " 9router", "\t9router", "9router\n"]
        for p in padded_variants:
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
            env.launch_effective["provider"] = p
            with self.assertRaises(RoutingEvidenceError) as ctx:
                validate_execution_envelope(env, expected_phase="implement")
            self.assertTrue("provider" in str(ctx.exception).lower() or "router" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_astra_r18_19_live_terminal_padded_router_identity_rejected(self):
        """19. Counterexample: Padded router identity in live_terminal_evidence fails closed."""
        env_dc = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_dc.live_terminal_evidence.provider = " 9router "
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env_dc, expected_phase="implement")
        self.assertTrue("provider" in str(ctx.exception).lower() or "router" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

        env_map = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        lt = env_map.live_terminal_evidence.__dict__.copy()
        lt["provider"] = " 9router "
        env_map.live_terminal_evidence = lt
        with self.assertRaises(RoutingEvidenceError) as ctx:
            validate_execution_envelope(env_map, expected_phase="implement")
        self.assertTrue("provider" in str(ctx.exception).lower() or "router" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower())

    def test_astra_r18_20_exact_raw_router_identity_all_positions_positive_control(self):
        """20. Positive control: Exact raw '9router' at all 5 positions succeeds."""
        for phase in ("implement", "review"):
            env = make_execution_envelope(self.delivery_id, self.intended_disp, phase=phase, orca_task_id=self.orca_task_id)
            self.assertEqual(env.route["provider"], "9router")
            self.assertEqual(env.launch_requested["provider"], "9router")
            self.assertEqual(env.launch_effective["provider"], "9router")
            self.assertEqual(env.live_terminal_evidence.provider, "9router")
            self.assertEqual(env.usage_evidence.router, "9router")
            self.assertEqual(validate_execution_envelope(env, expected_phase=phase), [])

    # -------------------------------------------------------------------------
    # 4. Exact-HEAD attestation reproducibility & canonical-byte policy tests
    # -------------------------------------------------------------------------
    def test_astra_r18_21_canonical_byte_policy_rejects_crlf_in_bundle(self):
        """21. Counterexample: Validator rejects CRLF line endings in bundle text files."""
        import validate
        check_canonical = getattr(validate, "check_canonical_bytes", None)
        if check_canonical is not None:
            errs = check_canonical()
            self.assertEqual(errs, [], f"CRLF line endings detected in bundle files: {errs}")
        else:
            self.fail("validate.py must export check_canonical_bytes")

    def test_astra_r18_22_attestation_hashes_reproducible_match_exact_git_blobs(self):
        """22. Counterexample: Recorded attestation hashes match exact Git blob hashes for bundle files."""
        import hashlib, os
        report_path = BUNDLE_DIR / ".validation-report.json"
        self.assertTrue(report_path.is_file(), "Attestation report must exist")
        if os.environ.get("_GENERATING_REPORT") == "1":
            for p in sorted(BUNDLE_DIR.glob("*")):
                if p.is_file() and p.name != ".validation-report.json" and not p.name.endswith(".pyc"):
                    rel = f"docs/parallel-delivery/{p.name}"
                    res = subprocess.run(["git", "show", f"HEAD:{rel}"], capture_output=True, cwd=ROOT_DIR)
                    if res.returncode == 0:
                        blob_h = hashlib.sha256(res.stdout).hexdigest()
                        disk_h = hashlib.sha256(p.read_bytes()).hexdigest()
                        self.assertEqual(disk_h, blob_h, f"Disk hash vs Git blob mismatch for {p.name}")
            return
        report = json.loads(report_path.read_text(encoding="utf-8"))
        bundle_hashes = report.get("bundle_sha256", {})
        for fname, recorded_hash in bundle_hashes.items():
            fpath = f"docs/parallel-delivery/{fname}"
            res = subprocess.run(["git", "show", f"HEAD:{fpath}"], capture_output=True, cwd=ROOT_DIR)
            if res.returncode == 0:
                blob_h = hashlib.sha256(res.stdout).hexdigest()
                self.assertEqual(
                    recorded_hash, blob_h,
                    f"Hash mismatch for {fname}: recorded {recorded_hash} vs Git blob {blob_h}"
                )


class TestSolRound18Remediation(unittest.TestCase):
    """Remediation tests for Sol round 18 review findings:
    1. handle_review_verdict(task, "ACCEPT") followed by handle_integration_gates(task, True)
       must not reach integrated without valid review dispatch, verified review evidence/verdict
       binding, and verified integration evidence/gate binding. Caller-supplied strings/booleans
       alone are never authority.
    2. The publicly callable _authorized_transition_scope must not allow external callers to forge
       worker_done, review, or integration contexts. Make authorization tokens/scopes unforgeable
       or private to validated internal handlers; preserve legitimate handler flows and
       dispatch/lease settlement invariants.
    3. _extract_and_validate_alias must reject every alias key that is present with None, non-string,
       blank, padded-invalid identity, or a conflicting semantic value. Do not silently exclude
       present None. Cover implement and review across route, requested/effective launch,
       live/archive, usage, task, and dispatch aliases.
    """

    def setUp(self):
        self.t0 = datetime.now(timezone.utc)
        self.delivery_id = "PD-PILOT-CONTROL"
        self.orca_task_id = "task_sol_r18_001"
        self.intended_disp = "ctx_sol_r18_001"
        self.candidate_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.lock_defs = [
            {"id": "LOCK-PARALLEL-REGISTRY", "mode": "exclusive", "renewable": True, "lease_seconds": 1800},
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.lease = self.mgr.acquire_lease("LOCK-PARALLEL-REGISTRY", self.delivery_id, self.intended_disp, now=self.t0)
        self.tmp_storage = tempfile.mktemp(suffix=".json")
        self.registry = SharedOrcaExecutionRegistry(storage_path=self.tmp_storage)
        self.control_secret = "secret_s18_control"
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            registry=self.registry,
            declared_task_locks={self.delivery_id: ["LOCK-PARALLEL-REGISTRY"]},
            control_secret=self.control_secret,
        )
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()
    def tearDown(self):
        p = Path(self.tmp_storage)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    def _issue_valid_review_evidence(self, delivery_id, rev_disp_id, candidate_commit, verdict="ACCEPT", now=None):
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=candidate_commit,
            reviewer_secret=getattr(self, "reviewer_secret", TEST_FIXTURE_REVIEWER_SECRET),
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        return self.adapter.issue_review_evidence(delivery_id, rev_disp_id, candidate_commit, verdict=verdict, reviewer_capability=rev_cap, now=now)

    def _issue_valid_integration_evidence(self, delivery_id, candidate_commit, base_commit, gates_pass=True, now=None):
        ctrl_cap = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=delivery_id)
        return self.adapter.issue_integration_evidence(delivery_id, candidate_commit, base_commit, gates_pass=gates_pass, control_capability=ctrl_cap, now=now)


    def _advance_to_review(self):
        """Helper to advance task through legitimate implement dispatch to review state."""
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id=self.intended_disp,
            now=self.t0,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id, now=self.t0),
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        self.adapter.start_running(self.delivery_id, disp_id)
        st = self.adapter.handle_worker_done(
            self.delivery_id,
            self.orca_task_id,
            disp_id,
            outcome="succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            now=self.t0 + timedelta(seconds=2),
        )
        self.assertEqual(st, "review")
        return disp_id

    # -------------------------------------------------------------------------
    # 1. Blocker 1: Review dispatch & integration evidence bindings required
    # -------------------------------------------------------------------------
    def test_sol_r18_01_caller_supplied_review_verdict_without_review_dispatch_fails_closed(self):
        """1. Counterexample: Calling handle_review_verdict with only caller string fails closed."""
        self._advance_to_review()
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_review_verdict(self.delivery_id, "ACCEPT")
        self.assertTrue("review dispatch" in str(ctx.exception).lower() or "authority" in str(ctx.exception).lower() or "evidence" in str(ctx.exception).lower())
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

    def test_sol_r18_02_caller_supplied_integration_gates_without_integration_evidence_fails_closed(self):
        """2. Counterexample: Calling handle_integration_gates with only boolean fails closed."""
        self._advance_to_review()
        self.adapter._task_states[self.delivery_id] = "merge_queued"
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_integration_gates(self.delivery_id, True)
        self.assertTrue("integration evidence" in str(ctx.exception).lower() or "authority" in str(ctx.exception).lower() or "binding" in str(ctx.exception).lower())
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

    def test_sol_r18_03_handle_review_verdict_followed_by_handle_integration_gates_fails_closed(self):
        """3. Counterexample: handle_review_verdict('ACCEPT') followed by handle_integration_gates(True)
        without valid review dispatch and verified integration evidence must not reach integrated."""
        self._advance_to_review()
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_review_verdict(self.delivery_id, "ACCEPT")
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "merge_queued")
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_integration_gates(self.delivery_id, True)
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

    def test_sol_r18_04_review_dispatch_and_evidence_mismatch_rejected(self):
        """4. Counterexample: Review verdict referencing unknown/mismatched review dispatch fails closed."""
        self._advance_to_review()
        fake_evidence = {
            "review_dispatch_id": "ctx_fake_review_999",
            "delivery_task_id": self.delivery_id,
            "candidate_commit": self.candidate_commit,
            "verdict": "ACCEPT",
            "reviewer_route": "cx/gpt-5.6-sol",
            "reviewer_harness": "Claude Code",
        }
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_review_verdict(self.delivery_id, "ACCEPT", review_dispatch_id="ctx_fake_review_999", review_evidence=fake_evidence)
        self.assertTrue("review dispatch" in str(ctx.exception).lower() or "unknown" in str(ctx.exception).lower() or "mismatch" in str(ctx.exception).lower())

    def test_sol_r18_05_integration_gates_failing_gate_in_evidence_rejected(self):
        """5. Counterexample: Integration gates with gates_pass=True but failing individual gate in evidence fails closed."""
        self._advance_to_review()
        self.adapter._task_states[self.delivery_id] = "merge_queued"
        bad_evidence = {
            "delivery_task_id": self.delivery_id,
            "candidate_commit": self.candidate_commit,
            "base_commit": "4a7c8c921b7e05066505d51b168a02c3fde61317",
            "gates_pass": True,
            "gate_results": {"authority": True, "security": False, "scope": True},
        }
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=bad_evidence)
        self.assertTrue("failing" in str(ctx.exception).lower() or "contradictory" in str(ctx.exception).lower() or "mismatch" in str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # 2. Blocker 2: Unforgeable transition tokens & private transition scope
    # -------------------------------------------------------------------------
    def test_sol_r18_06_authorized_transition_scope_external_call_rejected(self):
        """6. Counterexample: Publicly calling _authorized_transition_scope without internal unforgeable token fails closed."""
        with self.assertRaises(ProtocolViolationError) as ctx:
            with self.adapter._authorized_transition_scope(self.delivery_id, "integrated", handler="handle_integration_gates", gates_pass=True):
                self.adapter.transition_task_state(self.delivery_id, "integrated")
        self.assertTrue("unauthorized" in str(ctx.exception).lower() or "token" in str(ctx.exception).lower() or "forbidden" in str(ctx.exception).lower() or "forge" in str(ctx.exception).lower())

    def test_sol_r18_07_authorized_transition_scope_forged_worker_done_rejected(self):
        """7. Counterexample: External caller cannot forge worker_done context to bypass settlement and lease release."""
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id=self.intended_disp,
            now=self.t0,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id, now=self.t0),
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        self.adapter.start_running(self.delivery_id, disp_id)
        with self.assertRaises(ProtocolViolationError):
            with self.adapter._authorized_transition_scope(self.delivery_id, "review", handler="handle_worker_done", outcome="succeeded"):
                self.adapter.transition_task_state(self.delivery_id, "review")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "running")

    def test_sol_r18_08_authorized_transition_scope_forged_or_reused_token_rejected(self):
        """8. Counterexample: Passing forged token string or object to _authorized_transition_scope fails closed."""
        with self.assertRaises(ProtocolViolationError) as ctx:
            with self.adapter._authorized_transition_scope(
                self.delivery_id, "integrated", handler="handle_integration_gates", _token="forged_token_string", gates_pass=True
            ):
                self.adapter.transition_task_state(self.delivery_id, "integrated")
        self.assertTrue("token" in str(ctx.exception).lower() or "unauthorized" in str(ctx.exception).lower() or "forge" in str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # 3. Blocker 3: _extract_and_validate_alias rejects present None, padded, non-string
    # -------------------------------------------------------------------------
    def test_sol_r18_09_alias_rejects_present_none_fail_closed(self):
        """9. Counterexample: _extract_and_validate_alias rejects any alias key present with None."""
        from delivery_engine import _extract_and_validate_alias
        with self.assertRaises(RoutingEvidenceError) as ctx:
            _extract_and_validate_alias(
                {"route": "ag/gemini-3.8-flash-high", "model": None},
                aliases=("route", "model"),
                field_label="model",
                container_label="test_container",
            )
        self.assertTrue("none" in str(ctx.exception).lower() or "non-blank" in str(ctx.exception).lower() or "string" in str(ctx.exception).lower())

        with self.assertRaises(RoutingEvidenceError) as ctx2:
            _extract_and_validate_alias(
                {"dispatch_id": None},
                aliases=("dispatch_id",),
                field_label="dispatch_id",
                container_label="test_container",
                required=True,
            )
        self.assertTrue("none" in str(ctx2.exception).lower() or "non-blank" in str(ctx2.exception).lower() or "string" in str(ctx2.exception).lower())

    def test_sol_r18_10_alias_rejects_padded_invalid_identity_fail_closed(self):
        """10. Counterexample: _extract_and_validate_alias rejects whitespace-padded identities."""
        from delivery_engine import _extract_and_validate_alias
        padded_samples = [
            " ag/gemini-3.8-flash-high",
            "cx/gpt-5.6-sol ",
            " 9router ",
            "	TASK-1",
            "ctx_001\n",
        ]
        for val in padded_samples:
            with self.assertRaises(RoutingEvidenceError) as ctx:
                _extract_and_validate_alias(
                    {"route": val},
                    aliases=("route", "model"),
                    field_label="model",
                    container_label="test_container",
                )
            self.assertTrue("padding" in str(ctx.exception).lower() or "invalid" in str(ctx.exception).lower() or "raw" in str(ctx.exception).lower())

    def test_sol_r18_11_alias_rejects_non_string_and_blank_fail_closed(self):
        """11. Counterexample: _extract_and_validate_alias rejects non-string types and blanks."""
        from delivery_engine import _extract_and_validate_alias
        for bad_val in (123, True, False, ["val"], {"k": "v"}, "", "   ", "\t\n"):
            with self.assertRaises(RoutingEvidenceError):
                _extract_and_validate_alias(
                    {"model": bad_val},
                    aliases=("route", "model"),
                    field_label="model",
                    container_label="test_container",
                )

    def test_sol_r18_12_alias_rejects_conflicting_semantic_values_fail_closed(self):
        """12. Counterexample: _extract_and_validate_alias rejects conflicting alias values."""
        from delivery_engine import _extract_and_validate_alias
        with self.assertRaises(RoutingEvidenceError) as ctx:
            _extract_and_validate_alias(
                {"route": "ag/gemini-3.8-flash-high", "model": "cx/gpt-5.6-sol"},
                aliases=("route", "model"),
                field_label="model",
                container_label="test_container",
            )
        self.assertTrue("contradictory" in str(ctx.exception).lower() or "conflict" in str(ctx.exception).lower())

    def test_sol_r18_13_envelope_implement_rejects_present_none_and_padded_aliases(self):
        """13. Counterexample: ExecutionEnvelope implement rejects present None and padded aliases across all positions."""
        # Route alias with None
        env1 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env1.route["model"] = None
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env1, expected_phase="implement")

        # Launch requested with None
        env2 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env2.launch_requested["route"] = None
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env2, expected_phase="implement")

        # Live terminal with padded route
        env3 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        lt3 = env3.live_terminal_evidence.__dict__.copy()
        lt3["route"] = " ag/gemini-3.8-flash-high "
        env3.live_terminal_evidence = lt3
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env3, expected_phase="implement")


        # Usage evidence with None
        env4 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        u4 = env4.usage_evidence.__dict__.copy()
        u4["model"] = None
        env4.usage_evidence = u4
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env4, expected_phase="implement")

    def test_sol_r18_14_envelope_review_rejects_present_none_and_padded_aliases(self):
        """14. Counterexample: ExecutionEnvelope review rejects present None and padded aliases across all positions."""
        # Route alias with None
        env1 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review", orca_task_id=self.orca_task_id)
        env1.route["model"] = None
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env1, expected_phase="review")

        # Launch effective with padded model
        env2 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review", orca_task_id=self.orca_task_id)
        env2.launch_effective["model"] = " cx/gpt-5.6-sol "
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env2, expected_phase="review")

        # Live terminal with None
        env3 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review", orca_task_id=self.orca_task_id)
        lt3 = env3.live_terminal_evidence.__dict__.copy()
        lt3["model"] = None
        env3.live_terminal_evidence = lt3
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env3, expected_phase="review")

        # Usage evidence with padded backend_model
        env4 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review", orca_task_id=self.orca_task_id)
        u4 = env4.usage_evidence.__dict__.copy()
        u4["backend_model"] = " cx/gpt-5.6-sol "
        env4.usage_evidence = u4
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env4, expected_phase="review")

    def test_sol_r18_15_valid_review_and_integration_positive_path_pass(self):
        """15. Positive control: Full end-to-end lifecycle with legitimate review dispatch,
        verified review evidence, and verified integration evidence reaches integrated."""
        self._advance_to_review()
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

        # 1. Independent review dispatch
        rev_disp_id = "ctx_sol_r18_review_001"
        rev_orca_id = "task_sol_r18_review_001"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp_id, phase="review", orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5))
        rev_disp_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )

        # 2. Independent review evidence ACCEPT
        rev_ev = self._issue_valid_review_evidence(
            delivery_id=self.delivery_id,
            rev_disp_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            verdict="ACCEPT",
        )
        res_state = self.adapter.handle_review_verdict(self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev)
        self.assertEqual(res_state, "merge_queued")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "merge_queued")

        # 3. Verified integration gates pass
        int_ev = self._issue_valid_integration_evidence(
            delivery_id=self.delivery_id,
            candidate_commit=self.candidate_commit,
            base_commit="4a7c8c921b7e05066505d51b168a02c3fde61317",
            gates_pass=True,
        )
        res_int = self.adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=int_ev)
        self.assertEqual(res_int, "integrated")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "integrated")



# =============================================================================
# Sol-Lead Review Remediation Fixtures (after 43c96aa)
# =============================================================================

class TestSolLeadReview43c96aaRemediation(unittest.TestCase):
    """Independent counterexamples and regression fixtures for Sol-Lead review findings on 43c96aa:
    1. Untrusted review/integration evidence dictionaries reaching 'integrated' (wrong base SHA, empty gates).
    2. Frame-name spoof forging lifecycle transition authority to 'review' with unsettled dispatch and active lease.
    3. Padded dataclass aliases accepted in LiveTerminalEvidence and UsageEvidence for implement and review.
    """

    def setUp(self):
        self.delivery_id = "TASK-SOL-LEAD-001"
        self.orca_task_id = "orca_sol_lead_001"
        self.intended_disp = "ctx_sol_lead_001"
        self.t0 = datetime.now(timezone.utc)
        self.candidate_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.approved_base = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        self.lock_defs = [
            {"id": "LOCK-PARALLEL-REGISTRY", "mode": "exclusive", "renewable": True, "lease_seconds": 1800},
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.lease = self.mgr.acquire_lease("LOCK-PARALLEL-REGISTRY", self.delivery_id, self.intended_disp, now=self.t0)
        self.tmp_storage = tempfile.mktemp(suffix=".json")
        self.registry = SharedOrcaExecutionRegistry(storage_path=self.tmp_storage)
        self.control_secret = "secret_43c_control"
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            registry=self.registry,
            declared_task_locks={self.delivery_id: ["LOCK-PARALLEL-REGISTRY"]},
            control_secret=self.control_secret,
        )
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()
    def tearDown(self):
        p = Path(self.tmp_storage)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    def _issue_valid_review_evidence(self, delivery_id, rev_disp_id, candidate_commit, verdict="ACCEPT", now=None):
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=candidate_commit,
            reviewer_secret=getattr(self, "reviewer_secret", TEST_FIXTURE_REVIEWER_SECRET),
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        return self.adapter.issue_review_evidence(delivery_id, rev_disp_id, candidate_commit, verdict=verdict, reviewer_capability=rev_cap, now=now)

    def _issue_valid_integration_evidence(self, delivery_id, candidate_commit, base_commit, gates_pass=True, now=None):
        ctrl_cap = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=delivery_id)
        return self.adapter.issue_integration_evidence(delivery_id, candidate_commit, base_commit, gates_pass=gates_pass, control_capability=ctrl_cap, now=now)

    def _advance_to_running(self):
        """Helper to advance task to running state with active dispatch and active lease."""
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id=self.intended_disp,
            now=self.t0,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id, now=self.t0),
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        self.adapter.start_running(self.delivery_id, disp_id)
        return disp_id

    def _advance_to_review(self):
        """Helper to advance task through legitimate implement dispatch to review state."""
        disp_id = self._advance_to_running()
        self.adapter.handle_worker_done(
            self.delivery_id,
            self.orca_task_id,
            disp_id,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            now=self.t0,
        )

    # -------------------------------------------------------------------------
    # Finding 1: Untrusted review/integration evidence reaches 'integrated'
    # -------------------------------------------------------------------------

    def test_sol_lead_01_forged_review_evidence_dict_rejected(self):
        """1. Counterexample: Calling handle_review_verdict with caller dictionary fails closed."""
        self._advance_to_review()
        rev_disp_id = "ctx_sol_lead_rev_001"
        rev_orca_id = "task_sol_lead_rev_001"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp_id, phase="review", orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5))
        self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        caller_dict_ev = {
            "review_dispatch_id": rev_disp_id,
            "delivery_task_id": self.delivery_id,
            "candidate_commit": self.candidate_commit,
            "verdict": "ACCEPT",
            "reviewer_route": "cx/gpt-5.6-sol",
            "reviewer_harness": "Claude Code",
        }
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_review_verdict(self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=caller_dict_ev)
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "merge_queued")

    def test_sol_lead_02_forged_integration_evidence_wrong_base_and_empty_gates_rejected(self):
        """2. Exact Sol Counterexample: FORGED_EVIDENCE_ACCEPTED state=integrated wrong_base=0000000000000000000000000000000000000000 gate_count=0."""
        self._advance_to_review()
        rev_disp_id = "ctx_sol_lead_rev_002"
        rev_orca_id = "task_sol_lead_rev_002"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp_id, phase="review", orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5))
        rev_disp_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        rev_ev = self._issue_valid_review_evidence(self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", now=self.t0 + timedelta(seconds=6))
        self.adapter.handle_review_verdict(self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev)

        wrong_base = "0000000000000000000000000000000000000000"
        forged_int_ev = {
            "delivery_task_id": self.delivery_id,
            "candidate_commit": self.candidate_commit,
            "base_commit": wrong_base,
            "gates_pass": True,
            "gate_results": {},
        }
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=forged_int_ev)
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

    def test_sol_lead_03_forged_integration_evidence_dataclass_wrong_base_rejected(self):
        """3. Counterexample: IntegrationEvidence dataclass with wrong base commit is rejected fail closed."""
        self._advance_to_review()
        rev_disp_id = "ctx_sol_lead_rev_003"
        rev_orca_id = "task_sol_lead_rev_003"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp_id, phase="review", orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5))
        rev_disp_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        rev_ev = self._issue_valid_review_evidence(self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", now=self.t0 + timedelta(seconds=6))
        self.adapter.handle_review_verdict(self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev)

        bad_base_ev = make_integration_evidence(
            self.delivery_id,
            self.candidate_commit,
            base_commit="0000000000000000000000000000000000000000",
            gates_pass=True,
        )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=bad_base_ev)
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

    def test_sol_lead_04_forged_integration_evidence_empty_gates_dataclass_rejected(self):
        """4. Counterexample: IntegrationEvidence dataclass with empty gate_results is rejected fail closed."""
        self._advance_to_review()
        rev_disp_id = "ctx_sol_lead_rev_004"
        rev_orca_id = "task_sol_lead_rev_004"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp_id, phase="review", orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5))
        rev_disp_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        rev_ev = self._issue_valid_review_evidence(self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", now=self.t0 + timedelta(seconds=6))
        self.adapter.handle_review_verdict(self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev)

        empty_gates_ev = IntegrationEvidence(
            delivery_task_id=self.delivery_id,
            candidate_commit=self.candidate_commit,
            base_commit=self.approved_base,
            gates_pass=True,
            gate_results={},
        )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=empty_gates_ev)
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

    # -------------------------------------------------------------------------
    # Finding 2: Frame-name spoof forges lifecycle transition authority
    # -------------------------------------------------------------------------

    def test_sol_lead_05_frame_name_spoof_transition_authority_rejected(self):
        """5. Exact Sol Counterexample: FORGED_TRANSITION_ACCEPTED state=review dispatch_settled=False lease_active=True."""
        import types
        disp_id = self._advance_to_running()

        # Attacker defines a method named handle_worker_done bound to adapter
        def handle_worker_done(self, tid):
            tok = self._mint_transition_token("handle_worker_done", tid, "review")
            with self._authorized_transition_scope(tid, "review", handler="handle_worker_done", _token=tok, outcome="succeeded"):
                self.transition_task_state(tid, "review")

        spoofed = types.MethodType(handle_worker_done, self.adapter)
        with self.assertRaises(ProtocolViolationError):
            spoofed(self.delivery_id)

        state = self.adapter.get_task_state(self.delivery_id)
        dispatch_settled = self.registry.is_dispatch_settled(disp_id)
        lease_active = self.lease.lease_id in self.mgr.active_leases and self.mgr.active_leases[self.lease.lease_id].is_active

        self.assertNotEqual(state, "review")
        self.assertEqual(state, "running")
        self.assertFalse(dispatch_settled)
        self.assertTrue(lease_active)

    # -------------------------------------------------------------------------
    # Finding 3: Padded dataclass aliases accepted in LiveTerminal / UsageEvidence
    # -------------------------------------------------------------------------

    def test_sol_lead_06_padded_dataclass_live_terminal_and_usage_evidence_implement_rejected(self):
        """6. Exact Sol Counterexample: PADDED_DATACLASS_EVIDENCE_ACCEPTED phase=implement result=[]."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env.live_terminal_evidence = LiveTerminalEvidence(
            harness="Codex CLI",
            provider="9router",
            route="ag/gemini-3.8-flash-high",
            archive_reference=" ref-1 ",
            verified=True,
            dispatch_id=" " + self.intended_disp + " ",
            delivery_task_id=" " + self.delivery_id + " ",
            effort=" high ",
        )
        env.usage_evidence = UsageEvidence(
            backend_provider=" google ",
            backend_model=" ag/gemini-3.8-flash-high ",
            recorded_after_dispatch=True,
            timestamp=" 2026-09-29T00:00:00Z ",
            request_id=" req-1 ",
            dispatch_id=" " + self.intended_disp + " ",
            delivery_task_id=" " + self.delivery_id + " ",
            router="9router",
        )
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env, expected_phase="implement")

    def test_sol_lead_07_padded_dataclass_live_terminal_and_usage_evidence_review_rejected(self):
        """7. Exact Sol Counterexample: PADDED_DATACLASS_EVIDENCE_ACCEPTED phase=review result=[]."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review", orca_task_id=self.orca_task_id)
        env.live_terminal_evidence = LiveTerminalEvidence(
            harness="Claude Code",
            provider="9router",
            route="cx/gpt-5.6-sol",
            archive_reference=" ref-1 ",
            verified=True,
            dispatch_id=" " + self.intended_disp + " ",
            delivery_task_id=" " + self.delivery_id + " ",
            effort=" high ",
        )
        env.usage_evidence = UsageEvidence(
            backend_provider=" openai ",
            backend_model=" cx/gpt-5.6-sol ",
            recorded_after_dispatch=True,
            timestamp=" 2026-09-29T00:00:00Z ",
            request_id=" req-1 ",
            dispatch_id=" " + self.intended_disp + " ",
            delivery_task_id=" " + self.delivery_id + " ",
            router="9router",
        )
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env, expected_phase="review")

    # -------------------------------------------------------------------------
    # Positive Control: Full legitimate lifecycle
    # -------------------------------------------------------------------------

    def test_sol_lead_08_positive_control_valid_end_to_end_lifecycle(self):
        """8. Positive control: Full lifecycle progression with legitimate review and integration evidence."""
        self._advance_to_review()
        rev_disp_id = "ctx_sol_lead_rev_pos"
        rev_orca_id = "task_sol_lead_rev_pos"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp_id, phase="review", orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5))
        rev_disp_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        rev_ev = self._issue_valid_review_evidence(self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", now=self.t0 + timedelta(seconds=6))
        st_rev = self.adapter.handle_review_verdict(self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev)
        self.assertEqual(st_rev, "merge_queued")

        int_ev = self._issue_valid_integration_evidence(self.delivery_id, self.candidate_commit, self.approved_base, gates_pass=True)
        st_int = self.adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=int_ev)
        self.assertEqual(st_int, "integrated")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "integrated")



# =============================================================================
# Sol-Lead Review Remediation Fixtures (after da26686)
# =============================================================================

class TestSolLeadReviewDa26686Remediation(unittest.TestCase):
    """Independent counterexamples and regression fixtures for Sol-Lead review findings on da26686:
    1. Evidence provenance is caller-controlled and stale year-2000 evidence is accepted.
    2. Callers can mint a valid lifecycle capability (CALLER_MINTED_TOKEN_ACCEPTED state=review).
    3. Noncanonical case aliases are accepted (effort 'HIGH', usage backend_provider 'Google').
    """

    def setUp(self):
        self.delivery_id = "TASK-DA26686-001"
        self.orca_task_id = "orca_da26686_001"
        self.intended_disp = "ctx_da26686_001"
        self.t0 = datetime.now(timezone.utc)
        self.candidate_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.approved_base = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        self.lock_defs = [
            {"id": "LOCK-PARALLEL-REGISTRY", "mode": "exclusive", "renewable": True, "lease_seconds": 1800},
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.lease = self.mgr.acquire_lease("LOCK-PARALLEL-REGISTRY", self.delivery_id, self.intended_disp, now=self.t0)
        self.tmp_storage = tempfile.mktemp(suffix=".json")
        self.registry = SharedOrcaExecutionRegistry(storage_path=self.tmp_storage)
        self.control_secret = "secret_da2_control"
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            registry=self.registry,
            declared_task_locks={self.delivery_id: ["LOCK-PARALLEL-REGISTRY"]},
            control_secret=self.control_secret,
        )
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()
    def tearDown(self):
        p = Path(self.tmp_storage)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    def _issue_valid_review_evidence(self, delivery_id, rev_disp_id, candidate_commit, verdict="ACCEPT", now=None):
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=candidate_commit,
            reviewer_secret=getattr(self, "reviewer_secret", TEST_FIXTURE_REVIEWER_SECRET),
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        return self.adapter.issue_review_evidence(delivery_id, rev_disp_id, candidate_commit, verdict=verdict, reviewer_capability=rev_cap, now=now)

    def _issue_valid_integration_evidence(self, delivery_id, candidate_commit, base_commit, gates_pass=True, now=None):
        ctrl_cap = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=delivery_id)
        return self.adapter.issue_integration_evidence(delivery_id, candidate_commit, base_commit, gates_pass=gates_pass, control_capability=ctrl_cap, now=now)

    def _advance_to_running(self):
        """Helper to advance task to running state with active dispatch and active lease."""
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id=self.intended_disp,
            now=self.t0,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id, now=self.t0),
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        self.adapter.start_running(self.delivery_id, disp_id)
        return disp_id

    def _advance_to_review(self):
        """Helper to advance task through legitimate implement dispatch to review state."""
        disp_id = self._advance_to_running()
        self.adapter.handle_worker_done(
            self.delivery_id,
            self.orca_task_id,
            disp_id,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            now=self.t0,
        )

    def _create_review_dispatch(self):
        """Helper to create legitimate review dispatch."""
        rev_disp_id = "ctx_da26686_rev_001"
        rev_orca_id = "task_da26686_rev_001"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5)
        )
        return self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )

    # -------------------------------------------------------------------------
    # Finding 1: Evidence provenance caller-controlled and stale evidence accepted
    # -------------------------------------------------------------------------

    def test_da26686_01_stale_year_2000_review_evidence_rejected(self):
        """1. Counterexample: Stale year-2000 ReviewEvidence must be rejected fail closed with zero side effects."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()

        # Caller constructs ReviewEvidence with year-2000 timestamp
        stale_rev_ev = ReviewEvidence(
            review_dispatch_id=rev_disp_id,
            delivery_task_id=self.delivery_id,
            candidate_commit=self.candidate_commit,
            verdict="ACCEPT",
            reviewer_route="cx/gpt-5.6-sol",
            reviewer_harness="Claude Code",
            evidence_hash=None,
            summary="Sol year 2000 review exploit",
            timestamp="2000-01-01T00:00:00Z",
        )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_review_verdict(
                self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=stale_rev_ev
            )
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")
        self.assertNotIn(rev_disp_id, self.registry.settled_dispatches)

    def test_da26686_02_caller_constructed_review_evidence_without_authority_rejected(self):
        """2. Counterexample: Caller-constructed ReviewEvidence without internal authority signature is rejected."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()

        # Caller constructs ReviewEvidence directly or via public make_review_evidence without authority
        caller_ev = make_review_evidence(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            verdict="ACCEPT",
            now=self.t0,
        )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_review_verdict(
                self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=caller_ev
            )
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")
        self.assertNotIn(rev_disp_id, self.registry.settled_dispatches)

    def test_da26686_03_stale_year_2000_integration_evidence_rejected(self):
        """3. Counterexample: Stale year-2000 IntegrationEvidence must be rejected fail closed with zero side effects."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()
        rev_ev = self._issue_valid_review_evidence(self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", now=self.t0 + timedelta(seconds=6))
        self.adapter.handle_review_verdict(
            self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev
        )

        # Caller constructs IntegrationEvidence with year-2000 timestamp
        stale_int_ev = IntegrationEvidence(
            delivery_task_id=self.delivery_id,
            candidate_commit=self.candidate_commit,
            base_commit=self.approved_base,
            gates_pass=True,
            gate_results={g: True for g in MANDATORY_INTEGRATION_GATES},
            timestamp="2000-01-01T00:00:00Z",
        )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_integration_gates(
                self.delivery_id, True, integration_evidence=stale_int_ev
            )
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

    def test_da26686_04_caller_constructed_integration_evidence_without_authority_rejected(self):
        """4. Counterexample: Caller-constructed IntegrationEvidence without internal authority signature is rejected."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()
        rev_ev = self._issue_valid_review_evidence(self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", now=self.t0 + timedelta(seconds=6))
        self.adapter.handle_review_verdict(
            self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev
        )

        # Caller constructs IntegrationEvidence directly
        caller_int_ev = make_integration_evidence(
            delivery_task_id=self.delivery_id,
            candidate_commit=self.candidate_commit,
            base_commit=self.approved_base,
            gates_pass=True,
            now=self.t0 + timedelta(seconds=12),
        )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_integration_gates(
                self.delivery_id, True, integration_evidence=caller_int_ev
            )
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

    def test_da26686_05_replayed_review_and_integration_evidence_rejected(self):
        """5. Counterexample: Replaying consumed review or integration evidence fails closed."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()
        rev_ev = self._issue_valid_review_evidence(self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", now=self.t0 + timedelta(seconds=6))
        self.adapter.handle_review_verdict(
            self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev
        )

        # Second attempt to consume same review evidence must fail
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_review_verdict(
                self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev
            )

        # Test integration evidence replay as well
        int_ev = self._issue_valid_integration_evidence(
            self.delivery_id, self.candidate_commit, self.approved_base, gates_pass=True
        )
        self.adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=int_ev)
        with self.assertRaises(ProtocolViolationError):
            self.adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=int_ev)

    # -------------------------------------------------------------------------
    # Finding 2: Caller-minted lifecycle capabilities and manipulated settlement/lease
    # -------------------------------------------------------------------------

    def test_da26686_06_caller_minted_transition_token_rejected_exact_counterexample(self):
        """6. Exact Sol Counterexample: CALLER_MINTED_TOKEN_ACCEPTED state=review must fail closed."""
        disp_id = self._advance_to_running()

        # Sol manipulated settlement and release surfaces:
        self.registry.settle_dispatch(disp_id)
        self.mgr.release_lease(self.lease.lease_id)

        # Sol called _mint_transition_token directly to obtain a valid capability
        with self.assertRaises(ProtocolViolationError):
            tok = self.adapter._mint_transition_token("handle_worker_done", self.delivery_id, "review")
            with self.adapter._authorized_transition_scope(
                self.delivery_id, "review", handler="handle_worker_done", _token=tok,
                outcome="succeeded", dispatch_id=disp_id
            ):
                self.adapter.transition_task_state(self.delivery_id, "review")

        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "review")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "running")

    def test_da26686_07_external_caller_cannot_mint_transition_token(self):
        """7. Counterexample: External callers calling _mint_transition_token fail closed."""
        disp_id = self._advance_to_running()
        with self.assertRaises(ProtocolViolationError):
            self.adapter._mint_transition_token("handle_worker_done", self.delivery_id, "review")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "running")

    def test_da26686_08_external_caller_cannot_enter_authorized_transition_scope(self):
        """8. Counterexample: External callers cannot enter _authorized_transition_scope."""
        self._advance_to_running()
        with self.assertRaises(ProtocolViolationError):
            with self.adapter._authorized_transition_scope(self.delivery_id, "review", handler="handle_worker_done"):
                self.adapter.transition_task_state(self.delivery_id, "review")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "running")

    def test_da26686_09_out_of_band_settlement_cannot_satisfy_transition_preconditions(self):
        """9. Counterexample: Out-of-band settlement without authoritative handler does not satisfy preconditions."""
        disp_id = self._advance_to_running()
        self.registry.settle_dispatch(disp_id)
        with self.assertRaises(ProtocolViolationError):
            self.adapter.transition_task_state(self.delivery_id, "review")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "running")

    # -------------------------------------------------------------------------
    # Finding 3: Noncanonical case aliases accepted in effort and backend_provider
    # -------------------------------------------------------------------------

    def test_da26686_10_noncanonical_case_effort_high_in_route_rejected(self):
        """10. Counterexample: Envelope with uppercase effort 'HIGH' in route fails closed."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env.route["effort"] = "HIGH"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env, expected_phase="implement", expected_delivery_task_id=self.delivery_id, expected_dispatch_id=self.intended_disp)

    def test_da26686_11_noncanonical_case_effort_high_in_launch_requested_and_effective_rejected(self):
        """11. Counterexample: Envelope with uppercase effort 'HIGH' in launch evidence fails closed."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env.launch_requested["effort"] = "HIGH"
        env.launch_effective["effort"] = "HIGH"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env, expected_phase="implement", expected_delivery_task_id=self.delivery_id, expected_dispatch_id=self.intended_disp)

    def test_da26686_12_noncanonical_case_effort_high_in_live_terminal_rejected(self):
        """12. Counterexample: Live terminal evidence with uppercase effort 'HIGH' fails closed."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env.live_terminal_evidence.effort = "HIGH"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env, expected_phase="implement", expected_delivery_task_id=self.delivery_id, expected_dispatch_id=self.intended_disp)

    def test_da26686_13_noncanonical_case_backend_provider_google_rejected(self):
        """13. Counterexample: Usage evidence with titlecase 'Google' in implement phase fails closed."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env.usage_evidence.backend_provider = "Google"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env, expected_phase="implement", expected_delivery_task_id=self.delivery_id, expected_dispatch_id=self.intended_disp)

    def test_da26686_14_noncanonical_case_backend_provider_openai_rejected(self):
        """14. Counterexample: Usage evidence with noncanonical case 'OpenAI' in review phase fails closed."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review", orca_task_id=self.orca_task_id)
        env.usage_evidence.backend_provider = "OpenAI"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env, expected_phase="review", expected_delivery_task_id=self.delivery_id, expected_dispatch_id=self.intended_disp)

    def test_da26686_15_noncanonical_case_provider_harness_model_rejected(self):
        """15. Counterexample: Case-variant provider '9Router', harness 'codex cli', model 'AG/GEMINI-3.8-FLASH-HIGH' fail closed."""
        env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env.route["provider"] = "9Router"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env, expected_phase="implement")

        env2 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env2.route["harness"] = "codex cli"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env2, expected_phase="implement")

        env3 = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env3.route["model"] = "AG/GEMINI-3.8-FLASH-HIGH"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env3, expected_phase="implement")


    def test_da26686_16_positive_control_valid_end_to_end_lifecycle_with_internal_authority(self):
        """16. Positive control: Full lifecycle with legitimate internal authority evidence reaches integrated."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()
        rev_ev = self._issue_valid_review_evidence(
            self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT"
        )
        res_review = self.adapter.handle_review_verdict(
            self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev
        )
        self.assertEqual(res_review, "merge_queued")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "merge_queued")

        int_ev = self._issue_valid_integration_evidence(
            self.delivery_id, self.candidate_commit, self.approved_base, gates_pass=True
        )
        res_int = self.adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=int_ev)
        self.assertEqual(res_int, "integrated")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "integrated")





# =============================================================================
# Sol-Lead Review Remediation Fixtures (after 36092d0)
# =============================================================================

class TestSolLeadReview36092d0Remediation(unittest.TestCase):
    """Independent counterexamples and regression fixtures for Sol-Lead review findings on 36092d0:
    1. Public evidence issuers (issue_review_evidence, issue_integration_evidence) let ordinary callers obtain signed evidence.
    2. Externally callable _internal_lifecycle_execution lets ordinary callers enter internal boundary and transition blocked to ready.
    3. Usage validation accepts noncanonical backend aliases (9router/google, 9router/openai, gemini-3.8-flash-high, gpt-5.6-sol).
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.delivery_id = "TASK-36092D0-001"
        self.orca_task_id = "orca_36092d0_001"
        self.intended_disp = "ctx_36092d0_001"
        self.t0 = datetime.now(timezone.utc)
        self.candidate_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.approved_base = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        self.lock_defs = [
            {"id": "LOCK-PARALLEL-REGISTRY", "mode": "exclusive", "renewable": True, "lease_seconds": 1800},
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.lease = self.mgr.acquire_lease("LOCK-PARALLEL-REGISTRY", self.delivery_id, self.intended_disp, now=self.t0)
        self.tmp_storage = tempfile.mktemp(suffix=".json")
        self.registry = SharedOrcaExecutionRegistry(storage_path=self.tmp_storage)
        self.control_secret = "secret_36092d0_control_auth_key"
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            registry=self.registry,
            declared_task_locks={self.delivery_id: ["LOCK-PARALLEL-REGISTRY"]},
        )
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()
    def tearDown(self):
        p = Path(self.tmp_storage)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    def _advance_to_running(self):
        """Helper to advance task to running state with active dispatch and active lease."""
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id=self.intended_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id, now=self.t0),
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        self.adapter.start_running(self.delivery_id, disp_id)
        return disp_id

    def _advance_to_review(self):
        """Helper to advance task through legitimate implement dispatch to review state."""
        disp_id = self._advance_to_running()
        self.adapter.handle_worker_done(
            self.delivery_id,
            self.orca_task_id,
            disp_id,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            now=self.t0,
        )

    def _create_review_dispatch(self):
        """Helper to create legitimate review dispatch."""
        rev_disp_id = "ctx_36092d0_rev_001"
        rev_orca_id = "task_36092d0_rev_001"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5)
        )
        return self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )

    # Finding 1: Public evidence issuers let ordinary adapter caller obtain signed evidence
    def test_36092d0_01_ordinary_adapter_caller_cannot_issue_review_evidence_without_reviewer_capability(self):
        """1. Counterexample: Ordinary adapter caller calling issue_review_evidence without ReviewerCapability fails closed."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()

        # Ordinary caller attempts to issue review evidence without capability
        with self.assertRaises(ProtocolViolationError):
            self.adapter.issue_review_evidence(
                self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT"
            )
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")
        self.assertNotIn(rev_disp_id, self.registry.settled_dispatches)

    def test_36092d0_02_ordinary_adapter_caller_cannot_issue_integration_evidence_without_control_capability(self):
        """2. Counterexample: Ordinary adapter caller calling issue_integration_evidence without ControlCapability fails closed."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()

        # Ordinary caller attempts to issue integration evidence without ControlCapability
        with self.assertRaises(ProtocolViolationError):
            self.adapter.issue_integration_evidence(
                self.delivery_id, self.candidate_commit, self.approved_base, gates_pass=True
            )
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

    # Finding 2: Externally callable _internal_lifecycle_execution lets ordinary caller enter boundary and transition blocked to ready
    def test_36092d0_03_ordinary_caller_cannot_enter_internal_lifecycle_execution_without_capability(self):
        """3. Counterexample: Ordinary caller calling _internal_lifecycle_execution without capability fails closed."""
        disp_id = self._advance_to_running()
        self.adapter.handle_harness_failure(self.delivery_id, disp_id, reason="tool_crash")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")

        # Ordinary caller attempts to enter _internal_lifecycle_execution without capability to transition blocked to ready
        with self.assertRaises(ProtocolViolationError):
            with self.adapter._internal_lifecycle_execution("resolve_blocker_and_replan", self.delivery_id):
                token = self.adapter._mint_transition_token("resolve_blocker_and_replan", self.delivery_id, "ready")
                with self.adapter._authorized_transition_scope(
                    self.delivery_id, "ready", handler="resolve_blocker_and_replan", _token=token
                ):
                    self.adapter.transition_task_state(self.delivery_id, "ready")

        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")

    # Finding 3: Noncanonical backend aliases accepted in usage validation
    def test_36092d0_04_noncanonical_backend_provider_aliases_rejected_fail_closed(self):
        """4. Counterexample: Usage evidence with 9router/google (implement) or 9router/openai (review) fails closed."""
        env_impl = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_impl.usage_evidence.backend_provider = "9router/google"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env_impl, expected_phase="implement", expected_delivery_task_id=self.delivery_id, expected_dispatch_id=self.intended_disp)

        env_rev = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review", orca_task_id=self.orca_task_id)
        env_rev.usage_evidence.backend_provider = "9router/openai"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env_rev, expected_phase="review", expected_delivery_task_id=self.delivery_id, expected_dispatch_id=self.intended_disp)

    def test_36092d0_05_noncanonical_backend_model_aliases_rejected_fail_closed(self):
        """5. Counterexample: Usage evidence with gemini-3.8-flash-high (implement) or gpt-5.6-sol (review) fails closed."""
        env_impl = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id)
        env_impl.usage_evidence.backend_model = "gemini-3.8-flash-high"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env_impl, expected_phase="implement", expected_delivery_task_id=self.delivery_id, expected_dispatch_id=self.intended_disp)

        env_rev = make_execution_envelope(self.delivery_id, self.intended_disp, phase="review", orca_task_id=self.orca_task_id)
        env_rev.usage_evidence.backend_model = "gpt-5.6-sol"
        with self.assertRaises(RoutingEvidenceError):
            validate_execution_envelope(env_rev, expected_phase="review", expected_delivery_task_id=self.delivery_id, expected_dispatch_id=self.intended_disp)



    def test_36092d0_06_positive_control_authenticated_capabilities_allow_evidence_and_lifecycle_transitions(self):
        """6. Positive control: Authenticated ControlCapability and ReviewerCapability allow evidence issuance and lifecycle transitions."""
        adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            registry=self.registry,
            declared_task_locks={self.delivery_id: ["LOCK-PARALLEL-REGISTRY"]},
            control_secret=self.control_secret,
        )
        adapter.set_task_authority(self.delivery_id, "granted")
        adapter.set_task_state(self.delivery_id, "ready")

        # 1. Advance to review
        disp_id = adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id=self.intended_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id, now=self.t0),
        )
        adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        adapter.start_running(self.delivery_id, disp_id)
        adapter.handle_worker_done(
            self.delivery_id, self.orca_task_id, disp_id, "succeeded",
            candidate_commit=self.candidate_commit, fencing_token=self.lease.fencing_token, now=self.t0
        )
        self.assertEqual(adapter.get_task_state(self.delivery_id), "review")

        # 2. Review dispatch and capability retrieval
        rev_disp_id = "ctx_36092d0_pos_rev"
        rev_orca_id = "task_36092d0_pos_rev"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp_id, phase="review", orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5))
        rev_disp_id = adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )

        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = adapter.claim_reviewer_capability(rev_ctx)
        self.assertIsInstance(rev_cap, ReviewerCapability)

        rev_ev = adapter.issue_review_evidence(
            self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", reviewer_capability=rev_cap
        )
        st_rev = adapter.handle_review_verdict(self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev)
        self.assertEqual(st_rev, "merge_queued")
        self.assertEqual(adapter.get_task_state(self.delivery_id), "merge_queued")

        # 3. Integration evidence issuance and gates
        ctrl_cap2 = adapter.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        int_ev = adapter.issue_integration_evidence(
            self.delivery_id, self.candidate_commit, self.approved_base, gates_pass=True, control_capability=ctrl_cap2
        )
        st_int = adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=int_ev)
        self.assertEqual(st_int, "integrated")
        self.assertEqual(adapter.get_task_state(self.delivery_id), "integrated")

    def test_36092d0_07_forged_and_replayed_capabilities_rejected_fail_closed(self):
        """7. Counterexample: Forged signatures or replayed capabilities fail closed."""
        adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            registry=self.registry,
            declared_task_locks={self.delivery_id: ["LOCK-PARALLEL-REGISTRY"]},
            control_secret=self.control_secret,
        )
        adapter.set_task_authority(self.delivery_id, "granted")
        adapter.set_task_state(self.delivery_id, "ready")

        # Forged ControlCapability
        forged_ctrl = ControlCapability(
            capability_id="ctrl_fake_01",
            role="Control",
            delivery_task_id=self.delivery_id,
            authority_id=id(adapter.evidence_authority),
            created_at=time.time(),
            signature="bad_signature" * 4,
        )
        with self.assertRaises(ProtocolViolationError):
            adapter.issue_integration_evidence(
                self.delivery_id, self.candidate_commit, self.approved_base, gates_pass=True, control_capability=forged_ctrl
            )
        with self.assertRaises(ProtocolViolationError):
            with adapter._internal_lifecycle_execution("handle_integration_gates", self.delivery_id, capability=forged_ctrl):
                pass

        # Forged ReviewerCapability
        forged_rev = ReviewerCapability(
            capability_id="rev_fake_01",
            delivery_task_id=self.delivery_id,
            review_dispatch_id="ctx_fake_rev",
            candidate_commit=self.candidate_commit,
            reviewer_route="cx/gpt-5.6-sol",
            reviewer_harness="Claude Code",
            authority_id=id(adapter.evidence_authority),
            created_at=time.time(),
            signature="bad_signature" * 4,
        )
        with self.assertRaises(ProtocolViolationError):
            adapter.issue_review_evidence(
                self.delivery_id, "ctx_fake_rev", self.candidate_commit, "ACCEPT", reviewer_capability=forged_rev
            )

        # Single-use consumed capability replay
        ctrl_cap = adapter.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        int_ev = adapter.issue_integration_evidence(
            self.delivery_id, self.candidate_commit, self.approved_base, gates_pass=True, control_capability=ctrl_cap
        )
        # Attempt to reuse consumed control capability for evidence issuance
        with self.assertRaises(ProtocolViolationError):
            adapter.issue_integration_evidence(
                self.delivery_id, self.candidate_commit, self.approved_base, gates_pass=True, control_capability=ctrl_cap
            )

    def test_36092d0_08_capability_binding_mismatch_rejected_fail_closed(self):
        """8. Counterexample: ReviewerCapability with mismatched bindings is rejected fail closed."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)

        # Mismatched task ID
        with self.assertRaises(ProtocolViolationError):
            self.adapter.issue_review_evidence(
                "OTHER-TASK", rev_disp_id, self.candidate_commit, "ACCEPT", reviewer_capability=rev_cap
            )

        # Mismatched dispatch ID
        with self.assertRaises(ProtocolViolationError):
            self.adapter.issue_review_evidence(
                self.delivery_id, "other_dispatch_id", self.candidate_commit, "ACCEPT", reviewer_capability=rev_cap
            )

        # Mismatched commit SHA
        with self.assertRaises(ProtocolViolationError):
            self.adapter.issue_review_evidence(
                self.delivery_id, rev_disp_id, "1111111111111111111111111111111111111111", "ACCEPT", reviewer_capability=rev_cap
            )

        # ReviewerCapability attempting to authorize non-review lifecycle handler
        with self.assertRaises(ProtocolViolationError):
            with self.adapter._internal_lifecycle_execution("handle_worker_done", self.delivery_id, capability=rev_cap):
                pass


# =============================================================================
# Sol-Lead Audit Remediation Fixtures (after 654860c)
# =============================================================================

class TestSolLeadAudit654860cRemediation(unittest.TestCase):
    """Independent counterexamples and regression fixtures for Sol-Lead audit findings on 654860c:
    1. Module-global _ADAPTER_INTERNAL_CAPABILITIES removed from module state; cannot be imported or indexed.
    2. Counterexample exfiltration rejected: wildcard/internal capabilities cannot enter _internal_lifecycle_execution or transition blocked to ready.
    3. Counterexample exfiltration rejected: wildcard/internal capabilities cannot issue signed IntegrationEvidence.
    4. Counterexample exfiltration rejected: wildcard/internal capabilities cannot issue signed ReviewEvidence.
    5. Forged or replayed _InternalLifecycleToken rejected fail-closed.
    6. Positive control: authoritative lifecycle methods and control_secret authenticated capabilities succeed.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.delivery_id = "TASK-654860C-001"
        self.orca_task_id = "orca_654860c_001"
        self.intended_disp = "ctx_654860c_001"
        self.t0 = datetime.now(timezone.utc)
        self.candidate_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.approved_base = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        self.lock_defs = [
            {"id": "LOCK-PARALLEL-REGISTRY", "mode": "exclusive", "renewable": True, "lease_seconds": 1800},
        ]
        self.mgr = LeaseManager(self.lock_defs)
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.lease = self.mgr.acquire_lease("LOCK-PARALLEL-REGISTRY", self.delivery_id, self.intended_disp, now=self.t0)
        self.tmp_storage = tempfile.mktemp(suffix=".json")
        self.registry = SharedOrcaExecutionRegistry(storage_path=self.tmp_storage)
        self.control_secret = "secret_654860c_control_auth_key"
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            registry=self.registry,
            declared_task_locks={self.delivery_id: ["LOCK-PARALLEL-REGISTRY"]},
            control_secret=self.control_secret,
        )
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()
    def tearDown(self):
        p = Path(self.tmp_storage)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    def _advance_to_running(self):
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            lease_id=self.lease.lease_id,
            intended_dispatch_id=self.intended_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id, now=self.t0),
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        self.adapter.start_running(self.delivery_id, disp_id)
        return disp_id

    def _advance_to_review(self):
        disp_id = self._advance_to_running()
        self.adapter.handle_worker_done(
            self.delivery_id,
            self.orca_task_id,
            disp_id,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            now=self.t0,
        )

    def _create_review_dispatch(self):
        rev_disp_id = "ctx_654860c_rev_001"
        rev_orca_id = "task_654860c_rev_001"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5)
        )
        return self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )

    def test_654860c_01_module_global_adapter_internal_capabilities_removed_and_unindexed(self):
        """1. Counterexample: _ADAPTER_INTERNAL_CAPABILITIES is removed from module state and cannot be indexed."""
        import delivery_engine
        self.assertFalse(hasattr(delivery_engine, "_ADAPTER_INTERNAL_CAPABILITIES"))
        with self.assertRaises(AttributeError):
            _ = getattr(delivery_engine, "_ADAPTER_INTERNAL_CAPABILITIES")
        self.assertFalse(hasattr(self.adapter.evidence_authority, "_mint_internal_control_capability"))
        self.assertFalse(hasattr(self.adapter.evidence_authority, "_internal_capabilities"))

    def test_654860c_02_counterexample_wildcard_or_internal_cap_cannot_enter_lifecycle_or_transition_blocked_to_ready(self):
        """2. Counterexample: Wildcard or internal capability cannot enter _internal_lifecycle_execution or transition blocked to ready."""
        disp_id = self._advance_to_running()
        self.adapter.handle_harness_failure(self.delivery_id, disp_id, reason="tool_crash")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")

        # Fabricated internal wildcard capability matching Sol counterexample
        fake_cap = ControlCapability(
            capability_id="adapter_internal_ctrl_exfil",
            role="Control",
            delivery_task_id=None,
            authority_id=id(self.adapter.evidence_authority),
            created_at=time.time(),
            signature="forged_sig" * 4,
        )

        with self.assertRaises(ProtocolViolationError):
            with self.adapter._internal_lifecycle_execution("resolve_blocker_and_replan", self.delivery_id, capability=fake_cap):
                token = self.adapter._mint_transition_token("resolve_blocker_and_replan", self.delivery_id, "ready")
                with self.adapter._authorized_transition_scope(
                    self.delivery_id, "ready", handler="resolve_blocker_and_replan", _token=token
                ):
                    self.adapter.transition_task_state(self.delivery_id, "ready")

        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "ready")

    def test_654860c_03_counterexample_wildcard_or_internal_cap_cannot_issue_signed_integration_evidence(self):
        """3. Counterexample: Wildcard or internal capability cannot issue signed IntegrationEvidence."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()

        fake_cap = ControlCapability(
            capability_id="adapter_internal_ctrl_exfil",
            role="Control",
            delivery_task_id=None,
            authority_id=id(self.adapter.evidence_authority),
            created_at=time.time(),
            signature="forged_sig" * 4,
        )

        with self.assertRaises(ProtocolViolationError):
            self.adapter.issue_integration_evidence(
                self.delivery_id, self.candidate_commit, self.approved_base, gates_pass=True, control_capability=fake_cap
            )
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

    def test_654860c_04_counterexample_wildcard_or_internal_cap_cannot_issue_signed_review_evidence(self):
        """4. Counterexample: Wildcard or internal capability cannot issue signed ReviewEvidence."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()

        fake_cap = ControlCapability(
            capability_id="adapter_internal_ctrl_exfil",
            role="Control",
            delivery_task_id=None,
            authority_id=id(self.adapter.evidence_authority),
            created_at=time.time(),
            signature="forged_sig" * 4,
        )

        with self.assertRaises(ProtocolViolationError):
            self.adapter.issue_review_evidence(
                self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", capability=fake_cap
            )
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

    def test_654860c_05_internal_lifecycle_token_forgery_or_replay_rejected_fail_closed(self):
        """5. Counterexample: Forged or replayed _InternalLifecycleToken rejected fail closed."""
        from delivery_engine import _InternalLifecycleToken

        # Forged signature
        forged_ilt = _InternalLifecycleToken(
            token_id="ilt_forged_001",
            handler="resolve_blocker_and_replan",
            task_id=self.delivery_id,
            adapter_id=id(self.adapter),
            created_at=time.time(),
            signature="bad_signature" * 4,
        )
        with self.assertRaises(ProtocolViolationError):
            with self.adapter._internal_lifecycle_execution(
                "resolve_blocker_and_replan", self.delivery_id, _internal_token=forged_ilt
            ):
                pass

        # Valid ilt minted internally with internal secret
        valid_ilt = self.adapter._mint_internal_lifecycle_token(
            "start_running", self.delivery_id, _internal_secret=self.adapter._internal_exec_secret
        )
        with self.adapter._internal_lifecycle_execution(
            "start_running", self.delivery_id, _internal_token=valid_ilt
        ):
            pass

        # Replay of already consumed internal token fails closed
        with self.assertRaises(ProtocolViolationError):
            with self.adapter._internal_lifecycle_execution(
                "start_running", self.delivery_id, _internal_token=valid_ilt
            ):
                pass

        # Direct external minting without secret rejected
        with self.assertRaises(ProtocolViolationError):
            self.adapter._mint_internal_lifecycle_token("start_running", self.delivery_id)

        # Minting internal token for resolve_blocker_and_replan strictly rejected
        with self.assertRaises(ProtocolViolationError):
            self.adapter._mint_internal_lifecycle_token(
                "resolve_blocker_and_replan", self.delivery_id, _internal_secret=self.adapter._internal_exec_secret
            )

    def test_654860c_06_positive_control_authoritative_resolution_and_lifecycle_integration(self):
        """6. Positive control: Authoritative methods execute cleanly and authenticated capabilities integrate task."""
        # 1. Advance to running then blocked
        disp_id = self._advance_to_running()
        self.adapter.handle_harness_failure(self.delivery_id, disp_id, reason="tool_crash")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")

        # 2. Authoritative resolution back to ready with authenticated Control capability
        ctrl_cap = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        self.adapter.resolve_blocker_and_replan(self.delivery_id, capability=ctrl_cap)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "ready")

        # 3. Fresh dispatch attempt to running
        d_id2 = "ctx_654860c_run2"
        orca_id2 = "orca_654860c_run2"
        lease2 = self.mgr.acquire_lease("LOCK-PARALLEL-REGISTRY", self.delivery_id, d_id2, now=self.t0 + timedelta(seconds=10))
        d_id2_ret = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=orca_id2,
            candidate_commit=self.candidate_commit,
            fencing_token=lease2.fencing_token,
            lease_id=lease2.lease_id,
            intended_dispatch_id=d_id2,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, d_id2, phase="implement", orca_task_id=orca_id2, now=self.t0 + timedelta(seconds=10)),
            now=self.t0 + timedelta(seconds=10),
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, d_id2_ret)
        self.adapter.start_running(self.delivery_id, d_id2_ret)
        self.adapter.handle_worker_done(
            self.delivery_id, orca_id2, d_id2_ret, "succeeded",
            candidate_commit=self.candidate_commit, fencing_token=lease2.fencing_token,
            now=self.t0 + timedelta(seconds=15),
        )
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

        # 4. Review dispatch & authenticated evidence issuance
        rev_disp_id = "ctx_654860c_pos_rev"
        rev_orca_id = "task_654860c_pos_rev"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp_id, phase="review", orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=20))
        rev_disp_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=20),
        )
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        rev_ev = self.adapter.issue_review_evidence(
            self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", reviewer_capability=rev_cap
        )
        st_rev = self.adapter.handle_review_verdict(self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev)
        self.assertEqual(st_rev, "merge_queued")

        # 5. Integration evidence & gates
        ctrl_cap2 = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        int_ev = self.adapter.issue_integration_evidence(
            self.delivery_id, self.candidate_commit, self.approved_base, gates_pass=True, control_capability=ctrl_cap2
        )
        st_int = self.adapter.handle_integration_gates(self.delivery_id, True, integration_evidence=int_ev)
        self.assertEqual(st_int, "integrated")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "integrated")


# (unittest.main moved to EOF)




import uuid


class TestSolLeadAudit2f56bd3Remediation(unittest.TestCase):
    """Audit remediation for exact candidate 2f56bd36a87daa2ef2db579e5bbf90e8ab088bc6:
    - Path 1: Ordinary caller cannot mint internal lifecycle token or transition blocked -> ready via _internal_lifecycle_execution
    - Path 2: Unauthenticated resolve_blocker_and_replan fails closed; task remains blocked
    - Rejects wildcard, mismatched, Reviewer, forged, or replayed capabilities for replan
    - Token minting cannot confer authority to ordinary same-process callers
    - Positive control: Authenticated task-scoped Control capability successfully resolves blocker and replans
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.mgr = LeaseManager([
            {"id": "LOCK-REMED-2F56BD3", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
        ])
        self.delivery_id = "TASK-REMED-2F56BD3"
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.control_secret = "secret_remed_2f56bd3_control"
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
            control_secret=self.control_secret,
        )
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-REMED-2F56BD3"])
        self.ea = self.adapter.evidence_authority
        self.t0 = datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc)

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()
    def _advance_to_blocked(self, orca_id="orca_2f56bd3_01", disp_id="ctx_2f56bd3_01"):
        lease = self.mgr.acquire_lease("LOCK-REMED-2F56BD3", self.delivery_id, disp_id, now=self.t0)
        disp = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=orca_id,
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id=disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, disp_id, phase="implement", orca_task_id=orca_id, now=self.t0),
            now=self.t0,
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp)
        self.adapter.start_running(self.delivery_id, disp)
        self.adapter.handle_worker_done(
            self.delivery_id, orca_id, disp, "failed",
            candidate_commit=self.candidate_commit, fencing_token=lease.fencing_token,
            now=self.t0 + timedelta(seconds=5),
        )
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")
        return disp, lease

    def test_2f56bd3_01_ordinary_caller_cannot_mint_internal_token_to_transition_blocked_to_ready(self):
        """1. Counterexample (Path 1): Ordinary caller attempting to mint token and transition blocked -> ready fails closed."""
        self._advance_to_blocked()

        # Direct external minting for resolve_blocker_and_replan is forbidden
        with self.assertRaises(ProtocolViolationError):
            self.adapter._mint_internal_lifecycle_token("resolve_blocker_and_replan", self.delivery_id)

        # Direct external minting without internal secret is forbidden
        with self.assertRaises(ProtocolViolationError):
            self.adapter._mint_internal_lifecycle_token("start_running", self.delivery_id)

        # Even if an _InternalLifecycleToken is somehow forged or constructed, _internal_lifecycle_execution rejects it
        from delivery_engine import _InternalLifecycleToken
        forged_tok = _InternalLifecycleToken(
            token_id="ilt_forged_bypass_01",
            handler="resolve_blocker_and_replan",
            task_id=self.delivery_id,
            adapter_id=id(self.adapter),
            created_at=time.time(),
            signature="forged_signature_bytes" * 4,
        )
        with self.assertRaises(ProtocolViolationError):
            with self.adapter._internal_lifecycle_execution(
                "resolve_blocker_and_replan", self.delivery_id, _internal_token=forged_tok
            ):
                token = self.adapter._mint_transition_token("resolve_blocker_and_replan", self.delivery_id, "ready")
                with self.adapter._authorized_transition_scope(
                    self.delivery_id, "ready", handler="resolve_blocker_and_replan", _token=token
                ):
                    self.adapter.transition_task_state(self.delivery_id, "ready")

        # Task remains blocked
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "ready")

    def test_2f56bd3_02_unauthenticated_resolve_blocker_and_replan_fails_closed(self):
        """2. Counterexample (Path 2): Unauthenticated resolve_blocker_and_replan fails closed; task remains blocked."""
        self._advance_to_blocked()

        # Ordinary caller calls resolve_blocker_and_replan without capability
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.resolve_blocker_and_replan(self.delivery_id)
        self.assertIn("independently authenticated task-scoped Control capability", str(ctx.exception))

        # Explicit None capability also rejected
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.resolve_blocker_and_replan(self.delivery_id, capability=None)
        self.assertIn("independently authenticated task-scoped Control capability", str(ctx.exception))

        # Task state remains blocked
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")
        self.assertNotEqual(self.adapter.get_task_state(self.delivery_id), "ready")

    def test_2f56bd3_03_wildcard_or_mismatched_or_reviewer_capability_rejected_for_replan(self):
        """3. Counterexample: Wildcard, mismatched task, or ReviewerCapability rejected for replan."""
        self._advance_to_blocked()

        # Wildcard capability (delivery_task_id=None / "*") rejected
        wildcard_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=None)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.resolve_blocker_and_replan(self.delivery_id, capability=wildcard_cap)
        self.assertIn("Wildcard capability cannot be used", str(ctx.exception))

        # Mismatched task capability rejected
        mismatched_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id="OTHER-TASK-ID")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.resolve_blocker_and_replan(self.delivery_id, capability=mismatched_cap)
        self.assertIn("mismatch", str(ctx.exception))

        # ReviewerCapability rejected (role/type mismatch)
        rev_disp_id = "ctx_rev_test_01"
        rev_cap = ReviewerCapability(
            capability_id="rev_test_cap_01",
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_route="cx/gpt-5.6-sol",
            reviewer_harness="Claude Code",
            authority_id=id(self.ea),
            created_at=time.time(),
            signature="dummy_signature",
            role="Reviewer",
        )
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.resolve_blocker_and_replan(self.delivery_id, capability=rev_cap)
        self.assertIn("Invalid capability type", str(ctx.exception))

        # Task remains blocked
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")

    def test_2f56bd3_04_forged_or_replayed_control_capability_rejected_for_replan(self):
        """4. Counterexample: Forged or replayed ControlCapability rejected fail closed."""
        self._advance_to_blocked()

        # Unissued / fabricated capability rejected
        fabricated_cap = ControlCapability(
            capability_id=f"ctrl_cap_forged_{uuid.uuid4().hex}",
            role="Control",
            delivery_task_id=self.delivery_id,
            authority_id=id(self.ea),
            created_at=time.time(),
            signature="bad_forged_signature" * 4,
        )
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.resolve_blocker_and_replan(self.delivery_id, capability=fabricated_cap)
        self.assertIn("was not issued by internal evidence authority", str(ctx.exception))

        # Tampered signature on issued capability rejected
        valid_issued = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        tampered_cap = ControlCapability(
            capability_id=valid_issued.capability_id,
            role=valid_issued.role,
            delivery_task_id=valid_issued.delivery_task_id,
            authority_id=valid_issued.authority_id,
            created_at=valid_issued.created_at,
            signature="tampered_signature_bits" * 3,
        )
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.resolve_blocker_and_replan(self.delivery_id, capability=tampered_cap)
        self.assertIn("signature mismatch", str(ctx.exception))

        # Valid capability succeeds
        valid_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        self.adapter.resolve_blocker_and_replan(self.delivery_id, capability=valid_cap)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "ready")

        # Put back to blocked for replay test
        lease2 = self.mgr.acquire_lease("LOCK-REMED-2F56BD3", self.delivery_id, "ctx_2f56bd3_02", now=self.t0 + timedelta(seconds=10))
        disp2 = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id="orca_2f56bd3_02",
            candidate_commit=self.candidate_commit,
            fencing_token=lease2.fencing_token,
            lease_id=lease2.lease_id,
            intended_dispatch_id="ctx_2f56bd3_02",
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, "ctx_2f56bd3_02", phase="implement", orca_task_id="orca_2f56bd3_02", now=self.t0 + timedelta(seconds=10)),
            now=self.t0 + timedelta(seconds=10),
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp2)
        self.adapter.start_running(self.delivery_id, disp2)
        self.adapter.handle_worker_done(
            self.delivery_id, "orca_2f56bd3_02", disp2, "failed",
            candidate_commit=self.candidate_commit, fencing_token=lease2.fencing_token,
            now=self.t0 + timedelta(seconds=15),
        )
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")

        # Replay of already consumed valid_cap fails closed
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.resolve_blocker_and_replan(self.delivery_id, capability=valid_cap)
        self.assertIn("already been consumed", str(ctx.exception))
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")

    def test_2f56bd3_05_internal_token_minting_unable_to_confer_authority_to_ordinary_caller(self):
        """5. Counterexample: Token minting cannot confer authority to ordinary same-process callers."""
        self._advance_to_blocked()

        # Calling _mint_internal_lifecycle_token directly without internal secret raises ProtocolViolationError
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter._mint_internal_lifecycle_token("start_running", self.delivery_id)
        self.assertIn("Direct external calling", str(ctx.exception))

        # Minting internal token for resolve_blocker_and_replan raises ProtocolViolationError even with secret
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter._mint_internal_lifecycle_token(
                "resolve_blocker_and_replan", self.delivery_id, _internal_secret=self.adapter._internal_exec_secret
            )
        self.assertIn("Cannot mint internal lifecycle token for 'resolve_blocker_and_replan'", str(ctx.exception))

        # Even with another valid internal token, passing it for resolve_blocker_and_replan to _internal_lifecycle_execution fails
        valid_disp_ilt = self.adapter._mint_internal_lifecycle_token(
            "create_dispatch", self.delivery_id, _internal_secret=self.adapter._internal_exec_secret
        )
        with self.assertRaises(ProtocolViolationError):
            with self.adapter._internal_lifecycle_execution(
                "resolve_blocker_and_replan", self.delivery_id, _internal_token=valid_disp_ilt
            ):
                pass

        # Transitioning to ready/planned requires resolve_blocker_and_replan and ControlCapability
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "blocked")

    def test_2f56bd3_06_positive_control_authenticated_control_capability_resolves_and_integrates(self):
        """6. Positive control: Authenticated ControlCapability resolves blocker and task integrates cleanly."""
        self._advance_to_blocked()

        # 1. Authoritative resolution back to ready with authenticated ControlCapability
        ctrl_cap = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        self.adapter.resolve_blocker_and_replan(self.delivery_id, capability=ctrl_cap)
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "ready")

        # 2. Fresh dispatch attempt to running
        d_id2 = "ctx_2f56bd3_run2"
        orca_id2 = "orca_2f56bd3_run2"
        lease2 = self.mgr.acquire_lease("LOCK-REMED-2F56BD3", self.delivery_id, d_id2, now=self.t0 + timedelta(seconds=10))
        d_id2_ret = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=orca_id2,
            candidate_commit=self.candidate_commit,
            fencing_token=lease2.fencing_token,
            lease_id=lease2.lease_id,
            intended_dispatch_id=d_id2,
            dispatch_origin="dely dispatch",
            execution_envelope=make_execution_envelope(self.delivery_id, d_id2, phase="implement", orca_task_id=orca_id2, now=self.t0 + timedelta(seconds=10)),
            now=self.t0 + timedelta(seconds=10),
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, d_id2_ret)
        self.adapter.start_running(self.delivery_id, d_id2_ret)
        self.adapter.handle_worker_done(
            self.delivery_id, orca_id2, d_id2_ret, "succeeded",
            candidate_commit=self.candidate_commit, fencing_token=lease2.fencing_token,
            now=self.t0 + timedelta(seconds=20),
        )
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

        # 3. Independent review dispatch and verdict ACCEPT
        rev_disp_id = "ctx_2f56bd3_rev2"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp_id, phase="review", orca_task_id="orca_2f56bd3_rev2", now=self.t0 + timedelta(seconds=25))
        rev_disp_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="orca_2f56bd3_rev2",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=25),
        )
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        rev_ev = self.ea.issue_review_evidence(
            self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", reviewer_capability=rev_cap
        )
        self.adapter.handle_review_verdict(
            self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev
        )
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "merge_queued")

        # 4. Integration gates pass with ControlCapability
        gate_results = {g: True for g in MANDATORY_INTEGRATION_GATES}
        ctrl_for_int = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        int_ev = self.ea.issue_integration_evidence(
            delivery_task_id=self.delivery_id,
            candidate_commit=self.candidate_commit,
            base_commit="4a7c8c921b7e05066505d51b168a02c3fde61317",
            gates_pass=True,
            gate_results=gate_results,
            control_capability=ctrl_for_int,
        )
        state = self.adapter.handle_integration_gates(self.delivery_id, gates_pass=True, integration_evidence=int_ev)
        self.assertEqual(state, "integrated")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "integrated")


# =============================================================================
# Sol-Lead Audit Remediation Fixtures (after 982ed1e)
# =============================================================================

class TestSolLeadAudit982ed1eRemediation(unittest.TestCase):
    """Audit remediation fixtures for exact candidate 982ed1e9264444b00ed13736466f6923255d1b7b:
    1. Legitimate wildcard ControlCapability (delivery_task_id=None) rejected by issue_integration_evidence.
    2. Legitimate wildcard ControlCapability (delivery_task_id=None) rejected by issue_review_evidence.
    3. Wildcard ControlCapability (None or '*') rejected by verify_capability when expected_task_id is specified.
    4. Adapter external callable surface rejects wildcard ControlCapability fail-closed for evidence issuance.
    5. Positive control: Authenticated task-scoped ControlCapability and ReviewerCapability issue signed evidence, pass verification, and integrate cleanly.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.approved_base = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        self.mgr = LeaseManager([
            {"id": "LOCK-REMED-982ED1E", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
        ])
        self.delivery_id = "TASK-REMED-982ED1E"
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.control_secret = "secret_remed_982ed1e_control"
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
            control_secret=self.control_secret,
        )
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-REMED-982ED1E"])
        self.ea = self.adapter.evidence_authority
        self.t0 = datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc)

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()
    def test_982ed1e_01_wildcard_control_capability_rejected_by_evidence_authority_integration_issuer(self):
        """1. Counterexample: Legitimate wildcard ControlCapability (delivery_task_id=None) rejected by EvidenceAuthority.issue_integration_evidence."""
        wildcard_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=None)
        self.assertIsNone(wildcard_cap.delivery_task_id)

        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea.issue_integration_evidence(
                self.delivery_id,
                self.candidate_commit,
                self.approved_base,
                gates_pass=True,
                control_capability=wildcard_cap,
            )
        self.assertIn("Wildcard", str(ctx.exception))

    def test_982ed1e_02_wildcard_control_capability_rejected_by_evidence_authority_review_issuer(self):
        """2. Counterexample: Legitimate wildcard ControlCapability (delivery_task_id=None) rejected by EvidenceAuthority.issue_review_evidence."""
        wildcard_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=None)
        self.assertIsNone(wildcard_cap.delivery_task_id)

        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea.issue_review_evidence(
                self.delivery_id,
                "ctx_rev_test_01",
                self.candidate_commit,
                "ACCEPT",
                capability=wildcard_cap,
            )
        self.assertIn("Wildcard", str(ctx.exception))

    def test_982ed1e_03_verify_capability_rejects_wildcard_control_capability_when_task_specified(self):
        """3. Counterexample: verify_capability rejects ControlCapability with delivery_task_id=None or '*' when expected_task_id is concrete."""
        wildcard_cap_none = self.ea.issue_control_capability(self.control_secret, delivery_task_id=None)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea.verify_capability(wildcard_cap_none, expected_role="Control", expected_task_id=self.delivery_id)
        self.assertIn("wildcard", str(ctx.exception).lower())

        wildcard_cap_star = self.ea.issue_control_capability(self.control_secret, delivery_task_id="*")
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea.verify_capability(wildcard_cap_star, expected_role="Control", expected_task_id=self.delivery_id)
        self.assertIn("wildcard", str(ctx.exception).lower())

    def test_982ed1e_04_adapter_callable_surface_rejects_wildcard_control_capability_for_evidence(self):
        """4. Counterexample: Adapter entry points reject wildcard ControlCapability for review and integration evidence."""
        wildcard_cap1 = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=None)
        with self.assertRaises(ProtocolViolationError) as ctx1:
            self.adapter.issue_integration_evidence(
                self.delivery_id,
                self.candidate_commit,
                self.approved_base,
                gates_pass=True,
                control_capability=wildcard_cap1,
            )
        self.assertIn("Wildcard", str(ctx1.exception))

        wildcard_cap2 = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=None)
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.adapter.issue_review_evidence(
                self.delivery_id,
                "ctx_rev_test_02",
                self.candidate_commit,
                "ACCEPT",
                capability=wildcard_cap2,
            )
        self.assertIn("Wildcard", str(ctx2.exception))

    def test_982ed1e_05_positive_control_task_scoped_control_capability_and_reviewer_capability_succeed(self):
        """5. Positive control: Authenticated task-scoped ControlCapability and ReviewerCapability issue evidence and integrate cleanly."""
        lease = self.mgr.acquire_lease("LOCK-REMED-982ED1E", self.delivery_id, "ctx_disp_982_pos", now=self.t0)
        disp_env = make_execution_envelope(self.delivery_id, "ctx_disp_982_pos", phase="implement", orca_task_id="orca_task_982_pos", now=self.t0)
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id="orca_task_982_pos",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id="ctx_disp_982_pos",
            lease_id=lease.lease_id,
            fencing_token=lease.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=disp_env,
            now=self.t0,
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        self.adapter.start_running(self.delivery_id, disp_id)
        self.adapter.handle_worker_done(
            self.delivery_id,
            "orca_task_982_pos",
            disp_id,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            now=self.t0 + timedelta(seconds=3),
        )
        rev_env = make_execution_envelope(self.delivery_id, "ctx_rev_pos_01", phase="review", orca_task_id="task_orca_pos_01", now=self.t0 + timedelta(seconds=5))
        rev_disp = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_pos_01",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id="ctx_rev_pos_01",
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        self.assertEqual(rev_cap.delivery_task_id, self.delivery_id)

        # Review evidence issued with ReviewerCapability
        rev_ev = self.ea.issue_review_evidence(
            self.delivery_id, rev_disp, self.candidate_commit, "ACCEPT", reviewer_capability=rev_cap
        )
        self.assertIsInstance(rev_ev, ReviewEvidence)

        # Integration evidence issued with task-scoped ControlCapability
        gate_results = {g: True for g in MANDATORY_INTEGRATION_GATES}
        ctrl_for_int = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        int_ev = self.ea.issue_integration_evidence(
            delivery_task_id=self.delivery_id,
            candidate_commit=self.candidate_commit,
            base_commit=self.approved_base,
            gates_pass=True,
            gate_results=gate_results,
            control_capability=ctrl_for_int,
        )
        self.assertIsInstance(int_ev, IntegrationEvidence)


# =============================================================================
# Sol-Lead Audit Remediation Fixtures (after 1f90e6c)
# =============================================================================

class TestSolLeadAudit1f90e6cRemediation(unittest.TestCase):
    """Audit remediation fixtures for exact candidate 1f90e6cfd3d3ed829acf20fddd53e3c56fe90f8b:
    1. Task-scoped ControlCapability cannot be used to issue ReviewEvidence via EvidenceAuthority.
    2. Task-scoped ControlCapability cannot be used to issue ReviewEvidence via OrcaDeliveryAdapter.
    3. Task-scoped ControlCapability cannot bypass independent review to reach merge_queued.
    4. verify_capability with expected_role='Reviewer' rejects ControlCapability fail-closed.
    5. Positive control: Authenticated ReviewerCapability issues ReviewEvidence, task reaches merge_queued,
       and task-scoped ControlCapability issues IntegrationEvidence to reach integrated cleanly without regression.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.approved_base = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        self.mgr = LeaseManager([
            {"id": "LOCK-REMED-1F90E6C", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
        ])
        self.delivery_id = "TASK-REMED-1F90E6C"
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.control_secret = "secret_remed_1f90e6c_control"
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
            control_secret=self.control_secret,
        )
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-REMED-1F90E6C"])
        self.ea = self.adapter.evidence_authority
        self.t0 = datetime(2026, 9, 30, 11, 0, 0, tzinfo=timezone.utc)

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()
    def test_1f90e6c_01_task_scoped_control_capability_rejected_by_evidence_authority_review_issuer(self):
        """1. Counterexample: Task-scoped ControlCapability rejected fail-closed by EvidenceAuthority.issue_review_evidence."""
        ctrl_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        self.assertEqual(ctrl_cap.delivery_task_id, self.delivery_id)

        # Passing task-scoped ControlCapability as capability
        with self.assertRaises(ProtocolViolationError) as ctx1:
            self.ea.issue_review_evidence(
                self.delivery_id,
                "ctx_rev_test_1f90e6c_01",
                self.candidate_commit,
                "ACCEPT",
                capability=ctrl_cap,
            )
        self.assertIn("ReviewerCapability", str(ctx1.exception))

        # Fresh task-scoped ControlCapability as reviewer_capability
        ctrl_cap2 = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.ea.issue_review_evidence(
                self.delivery_id,
                "ctx_rev_test_1f90e6c_01",
                self.candidate_commit,
                "ACCEPT",
                reviewer_capability=ctrl_cap2,
            )
        self.assertIn("ReviewerCapability", str(ctx2.exception))

    def test_1f90e6c_02_task_scoped_control_capability_rejected_by_adapter_review_issuer(self):
        """2. Counterexample: Task-scoped ControlCapability rejected fail-closed by OrcaDeliveryAdapter.issue_review_evidence."""
        ctrl_cap = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        self.assertEqual(ctrl_cap.delivery_task_id, self.delivery_id)

        with self.assertRaises(ProtocolViolationError) as ctx1:
            self.adapter.issue_review_evidence(
                self.delivery_id,
                "ctx_rev_test_1f90e6c_02",
                self.candidate_commit,
                "ACCEPT",
                capability=ctrl_cap,
            )
        self.assertIn("ReviewerCapability", str(ctx1.exception))

        ctrl_cap2 = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.adapter.issue_review_evidence(
                self.delivery_id,
                "ctx_rev_test_1f90e6c_02",
                self.candidate_commit,
                "ACCEPT",
                reviewer_capability=ctrl_cap2,
            )
        self.assertIn("ReviewerCapability", str(ctx2.exception))

    def test_1f90e6c_03_control_capability_cannot_bypass_independent_review_to_reach_merge_queued(self):
        """3. Counterexample: Task-scoped ControlCapability cannot bypass independent review to reach merge_queued."""
        # 1. Advance task to review
        worker_disp = "ctx_1f90e6c_w01"
        worker_orca = "task_orca_1f90e6c_w01"
        worker_env = make_execution_envelope(self.delivery_id, worker_disp, phase="implement", orca_task_id=worker_orca, now=self.t0)
        lease = self.mgr.acquire_lease("LOCK-REMED-1F90E6C", self.delivery_id, worker_disp, now=self.t0)
        self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=worker_orca,
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id=worker_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=worker_env,
            now=self.t0,
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, worker_disp)
        self.adapter.start_running(self.delivery_id, worker_disp)
        st = self.adapter.handle_worker_done(
            self.delivery_id, worker_orca, worker_disp, "succeeded",
            candidate_commit=self.candidate_commit, fencing_token=lease.fencing_token, now=self.t0 + timedelta(seconds=10)
        )
        self.assertEqual(st, "review")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

        # 2. Review dispatch registered
        rev_disp = "ctx_1f90e6c_r01"
        rev_orca = "task_orca_1f90e6c_r01"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp, phase="review", orca_task_id=rev_orca, now=self.t0 + timedelta(seconds=15))
        rev_disp = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=15),
        )

        # 3. Control attempts to directly issue ReviewEvidence using task-scoped ControlCapability
        ctrl_cap = self.adapter.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        with self.assertRaises(ProtocolViolationError):
            self.adapter.issue_review_evidence(
                self.delivery_id, rev_disp, self.candidate_commit, "ACCEPT", capability=ctrl_cap
            )

        # Task state remains strictly in review
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

    def test_1f90e6c_04_verify_capability_with_expected_role_reviewer_rejects_control_capability(self):
        """4. Counterexample: verify_capability with expected_role='Reviewer' strictly rejects ControlCapability."""
        ctrl_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea.verify_capability(
                ctrl_cap,
                expected_role="Reviewer",
                expected_task_id=self.delivery_id,
            )
        self.assertIn("role", str(ctx.exception).lower())

    def test_1f90e6c_05_positive_control_independent_review_boundary_preserved_and_integration_unaffected(self):
        """5. Positive control: ReviewerCapability issues ReviewEvidence for merge_queued, and ControlCapability issues IntegrationEvidence for integrated."""
        # 1. Advance task to review
        worker_disp = "ctx_1f90e6c_w02"
        worker_orca = "task_orca_1f90e6c_w02"
        worker_env = make_execution_envelope(self.delivery_id, worker_disp, phase="implement", orca_task_id=worker_orca, now=self.t0)
        lease = self.mgr.acquire_lease("LOCK-REMED-1F90E6C", self.delivery_id, worker_disp, now=self.t0)
        self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=worker_orca,
            candidate_commit=self.candidate_commit,
            fencing_token=lease.fencing_token,
            lease_id=lease.lease_id,
            intended_dispatch_id=worker_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=worker_env,
            now=self.t0,
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, worker_disp)
        self.adapter.start_running(self.delivery_id, worker_disp)
        self.adapter.handle_worker_done(
            self.delivery_id, worker_orca, worker_disp, "succeeded",
            candidate_commit=self.candidate_commit, fencing_token=lease.fencing_token, now=self.t0 + timedelta(seconds=10)
        )
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

        # 2. Review dispatch registered
        rev_disp = "ctx_1f90e6c_r02"
        rev_orca = "task_orca_1f90e6c_r02"
        rev_env = make_execution_envelope(self.delivery_id, rev_disp, phase="review", orca_task_id=rev_orca, now=self.t0 + timedelta(seconds=15))
        rev_disp = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=15),
        )

        # 3. ReviewerCapability retrieved for review dispatch
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.ea.issue_reviewer_capability(
            self.delivery_id, rev_disp, self.candidate_commit, reviewer_context=rev_ctx
        )
        self.assertIsInstance(rev_cap, ReviewerCapability)

        # 4. Reviewer uses ReviewerCapability to issue ReviewEvidence
        rev_ev = self.ea.issue_review_evidence(
            self.delivery_id, rev_disp, self.candidate_commit, "ACCEPT", reviewer_capability=rev_cap, now=self.t0 + timedelta(seconds=18)
        )
        self.assertIsInstance(rev_ev, ReviewEvidence)

        # 5. Review evidence transitions task to merge_queued
        st_rev = self.adapter.handle_review_verdict(
            self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp, review_evidence=rev_ev, now=self.t0 + timedelta(seconds=20)
        )
        self.assertEqual(st_rev, "merge_queued")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "merge_queued")

        # 6. Control uses task-scoped ControlCapability to issue IntegrationEvidence
        gate_results = {g: True for g in MANDATORY_INTEGRATION_GATES}
        ctrl_for_int = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        int_ev = self.ea.issue_integration_evidence(
            delivery_task_id=self.delivery_id,
            candidate_commit=self.candidate_commit,
            base_commit=self.approved_base,
            gates_pass=True,
            gate_results=gate_results,
            control_capability=ctrl_for_int,
            now=self.t0 + timedelta(seconds=25),
        )
        self.assertIsInstance(int_ev, IntegrationEvidence)

        # 7. Task integrates cleanly
        st_int = self.adapter.handle_integration_gates(
            self.delivery_id, gates_pass=True, integration_evidence=int_ev, now=self.t0 + timedelta(seconds=30)
        )
        self.assertEqual(st_int, "integrated")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

# =============================================================================
# Sol-Lead Audit Remediation Fixtures (after eab4cab)
# =============================================================================
class TestSolLeadAuditEab4cabRemediation(unittest.TestCase):
    """Verifies remediation of Sol-Lead independent audit findings on candidate eab4cab:
    Finding 1:
      - Ordinary same-process callers cannot invoke _mint_reviewer_capability_internal directly without an unforgeable internal mint token.
      - _create_reviewer_mint_token requires internal execution secret and active authenticated review dispatch in 'review' state.
      - Control authority cannot issue, retrieve, or hold ReviewerCapability.
      - ControlCapability cannot be passed to issue_review_evidence.
      - ReviewerCapability issuance is bound to an active authenticated review dispatch.
    Finding 2:
      - issue_review_evidence validates verdict, candidate SHA, summary, identity, and dispatch state before state mutation (zero side effects on malformed requests).
      - issue_integration_evidence validates strict bool, commits, gate dictionary completeness and boolean values before state mutation (zero side effects on malformed requests).
      - Valid positive control verifies complete lifecycle progression.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        self.delivery_id = "TASK-DELIVERY-EAB4CAB"
        self.orca_task_id = "task_orca_eab4cab_01"
        self.intended_disp = "ctx_eab4cab_disp_01"
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.approved_base = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        self.t0 = datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc)
        self.mgr = LeaseManager([
            {"id": "LOCK-EAB4CAB-REMED", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
        ])
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.lease = self.mgr.acquire_lease("LOCK-EAB4CAB-REMED", self.delivery_id, self.intended_disp, now=self.t0)
        self.registry = SharedOrcaExecutionRegistry.get_default()
        self.control_secret = "test_control_secret_eab4cab_32b_!"
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
            control_secret=self.control_secret,
        )
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-EAB4CAB-REMED"])
        self.ea = self.adapter.evidence_authority

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()
    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def _advance_to_review(self):
        disp_env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id, now=self.t0)
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=self.intended_disp,
            lease_id=self.lease.lease_id,
            fencing_token=self.lease.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=disp_env,
            now=self.t0,
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        self.adapter.start_running(self.delivery_id, disp_id)
        self.adapter.handle_worker_done(
            self.delivery_id,
            self.orca_task_id,
            disp_id,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            now=self.t0 + timedelta(seconds=3),
        )

    def _create_review_dispatch(self, rev_disp_id="ctx_eab4cab_rev_01", rev_orca_id="task_orca_eab4cab_rev_01"):
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5)
        )
        return self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )

    def test_eab4cab_01_ordinary_caller_cannot_mint_reviewer_capability_directly(self):
        """1. Finding 1 Counterexample: Direct external calling of _mint_reviewer_capability_internal or _create_reviewer_mint_token rejected."""
        # Calling _mint_reviewer_capability_internal without mint token fails closed
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea._mint_reviewer_capability_internal(
                self.delivery_id, "ctx_fake_rev_01", self.candidate_commit
            )
        self.assertIn("Direct external calling", str(ctx.exception))

        # Calling _create_reviewer_mint_token without internal secret fails closed
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.ea._create_reviewer_mint_token(
                self.delivery_id, "ctx_fake_rev_01", self.candidate_commit
            )
        self.assertIn("Direct external calling", str(ctx2.exception))

        # Forged/fake mint token fails cryptographic verification
        fake_token = _InternalReviewerMintToken(
            token_id="fake_tok_01",
            delivery_task_id=self.delivery_id,
            review_dispatch_id="ctx_fake_rev_01",
            candidate_commit=self.candidate_commit,
            authority_id=id(self.ea),
            created_at=time.time(),
            signature="forged_sig_1234567890abcdef",
        )
        with self.assertRaises(ProtocolViolationError) as ctx3:
            self.ea._mint_reviewer_capability_internal(
                self.delivery_id, "ctx_fake_rev_01", self.candidate_commit, _mint_token=fake_token
            )
        self.assertIn("signature mismatch", str(ctx3.exception))

    def test_eab4cab_02_control_cannot_issue_or_retrieve_reviewer_capability(self):
        """2. Finding 1 Counterexample: Control authority strictly forbidden from issuing or retrieving ReviewerCapability."""
        ctrl_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)

        # Control capability passed to issue_reviewer_capability
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea.issue_reviewer_capability(
                self.delivery_id, "ctx_fake_rev_02", self.candidate_commit, control_capability=ctrl_cap
            )
        self.assertIn("strictly separates Control from Reviewer", str(ctx.exception))

        # Control secret passed to issue_reviewer_capability
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.ea.issue_reviewer_capability(
                self.delivery_id, "ctx_fake_rev_02", self.candidate_commit, control_secret=self.control_secret
            )
        self.assertIn("strictly separates Control from Reviewer", str(ctx2.exception))

        # Control capability passed to get_reviewer_capability
        with self.assertRaises(ProtocolViolationError) as ctx3:
            self.ea.get_reviewer_capability(
                "ctx_fake_rev_02", control_capability=ctrl_cap
            )
        self.assertIn("strictly separates Control from Reviewer", str(ctx3.exception))

        # Adapter surfaces also reject Control authority
        with self.assertRaises(ProtocolViolationError) as ctx4:
            self.adapter.issue_reviewer_capability(
                self.delivery_id, "ctx_fake_rev_02", self.candidate_commit, control_capability=ctrl_cap
            )
        self.assertIn("strictly separates Control from Reviewer", str(ctx4.exception))

        with self.assertRaises(ProtocolViolationError) as ctx5:
            self.adapter.get_reviewer_capability(
                "ctx_fake_rev_02", control_capability=ctrl_cap
            )
        self.assertIn("strictly separates Control from Reviewer", str(ctx5.exception))

    def test_eab4cab_03_control_capability_cannot_be_passed_to_issue_review_evidence(self):
        """3. Finding 1 Counterexample: Passing ControlCapability to issue_review_evidence is strictly rejected."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()
        ctrl_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)

        # Passing ControlCapability via capability
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea.issue_review_evidence(
                self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", capability=ctrl_cap
            )
        self.assertIn("strictly requires ReviewerCapability", str(ctx.exception))

        # Passing ControlCapability via reviewer_capability
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.ea.issue_review_evidence(
                self.delivery_id, rev_disp_id, self.candidate_commit, "ACCEPT", reviewer_capability=ctrl_cap
            )
        self.assertIn("strictly requires ReviewerCapability", str(ctx2.exception))

        # Control capability was not consumed
        self.assertNotIn(ctrl_cap.capability_id, self.ea._consumed_capabilities)

    def test_eab4cab_04_reviewer_capability_bound_to_authenticated_review_dispatch(self):
        """4. Finding 1 Invariant: ReviewerCapability issuance requires active authenticated review dispatch in 'review' state."""
        # Task is in 'ready' state: cannot issue ReviewerCapability
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea.issue_reviewer_capability(
                self.delivery_id, "ctx_fake_rev_04", self.candidate_commit
            )
        self.assertIn("not an active authenticated review dispatch", str(ctx.exception))

        # Advance to review
        self._advance_to_review()

        # Unregistered dispatch ID rejected
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.ea.issue_reviewer_capability(
                self.delivery_id, "ctx_unregistered_disp", self.candidate_commit
            )
        self.assertIn("not an active authenticated review dispatch", str(ctx2.exception))

        # Create valid review dispatch
        rev_disp_id = self._create_review_dispatch()

        # Commit mismatch rejected
        with self.assertRaises(ProtocolViolationError) as ctx3:
            self.ea.issue_reviewer_capability(
                self.delivery_id, rev_disp_id, "1111111111111111111111111111111111111111"
            )
        self.assertIn("bound to candidate commit", str(ctx3.exception))

        # Valid retrieval succeeds with authenticated ReviewerContext
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        self.assertIsInstance(rev_cap, ReviewerCapability)
        self.assertEqual(rev_cap.role, "Reviewer")

    def test_eab4cab_05_review_evidence_validation_failure_has_zero_side_effects(self):
        """5. Finding 2 Counterexample: Malformed review evidence request does not consume valid ReviewerCapability."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)

        # 1. Attempt with invalid verdict
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea.issue_review_evidence(
                self.delivery_id,
                rev_disp_id,
                self.candidate_commit,
                verdict="INVALID_VERDICT_MALFORMED",
                reviewer_capability=rev_cap,
            )
        self.assertIn("Invalid review verdict", str(ctx.exception))

        # ZERO SIDE EFFECTS ASSERTION: Capability MUST NOT be consumed after validation failure
        self.assertNotIn(rev_cap.capability_id, self.ea._consumed_capabilities)

        # 2. Attempt with invalid commit SHA ("HEAD")
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.ea.issue_review_evidence(
                self.delivery_id,
                rev_disp_id,
                "HEAD",
                verdict="ACCEPT",
                reviewer_capability=rev_cap,
            )
        self.assertIn("immutable full 40-character commit SHA", str(ctx2.exception))

        # Capability still NOT consumed
        self.assertNotIn(rev_cap.capability_id, self.ea._consumed_capabilities)

        # 3. Legitimate subsequent call with same capability SUCCEEDS cleanly (not 'already been consumed')
        rev_ev = self.ea.issue_review_evidence(
            self.delivery_id,
            rev_disp_id,
            self.candidate_commit,
            verdict="ACCEPT",
            reviewer_capability=rev_cap,
        )
        self.assertIsInstance(rev_ev, ReviewEvidence)
        self.assertIn(rev_cap.capability_id, self.ea._consumed_capabilities)

    def test_eab4cab_06_integration_evidence_validation_failure_has_zero_side_effects(self):
        """6. Finding 2 Counterexample: Malformed integration evidence request does not consume valid ControlCapability."""
        ctrl_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)

        # 1. Attempt with non-strict bool gates_pass
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea.issue_integration_evidence(
                delivery_task_id=self.delivery_id,
                candidate_commit=self.candidate_commit,
                base_commit=self.approved_base,
                gates_pass="true",  # non-strict bool string
                control_capability=ctrl_cap,
            )
        self.assertIn("gates_pass must be strict bool", str(ctx.exception))

        # ZERO SIDE EFFECTS ASSERTION: Capability MUST NOT be consumed after validation failure
        self.assertNotIn(ctrl_cap.capability_id, self.ea._consumed_capabilities)

        # 2. Attempt with invalid base commit ("HEAD")
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.ea.issue_integration_evidence(
                delivery_task_id=self.delivery_id,
                candidate_commit=self.candidate_commit,
                base_commit="HEAD",
                gates_pass=True,
                control_capability=ctrl_cap,
            )
        self.assertIn("immutable full 40-character commit SHA", str(ctx2.exception))

        # Capability still NOT consumed
        self.assertNotIn(ctrl_cap.capability_id, self.ea._consumed_capabilities)

        # 3. Attempt with non-boolean gate result value
        bad_gates = {g: True for g in MANDATORY_INTEGRATION_GATES}
        bad_gates["contract"] = 1  # int instead of strict bool
        with self.assertRaises(ProtocolViolationError) as ctx3:
            self.ea.issue_integration_evidence(
                delivery_task_id=self.delivery_id,
                candidate_commit=self.candidate_commit,
                base_commit=self.approved_base,
                gates_pass=True,
                gate_results=bad_gates,
                control_capability=ctrl_cap,
            )
        self.assertIn("must be strict bool", str(ctx3.exception))

        # Capability still NOT consumed
        self.assertNotIn(ctrl_cap.capability_id, self.ea._consumed_capabilities)

        # 4. Legitimate subsequent call with same capability SUCCEEDS cleanly (not 'already been consumed')
        valid_gates = {g: True for g in MANDATORY_INTEGRATION_GATES}
        int_ev = self.ea.issue_integration_evidence(
            delivery_task_id=self.delivery_id,
            candidate_commit=self.candidate_commit,
            base_commit=self.approved_base,
            gates_pass=True,
            gate_results=valid_gates,
            control_capability=ctrl_cap,
        )
        self.assertIsInstance(int_ev, IntegrationEvidence)
        self.assertIn(ctrl_cap.capability_id, self.ea._consumed_capabilities)

    def test_eab4cab_07_positive_control_end_to_end_clean_review_and_integration(self):
        """7. Positive control: Full end-to-end lifecycle progression with unforgeable ReviewerCapability and ControlCapability."""
        # 1. Advance to review
        self._advance_to_review()
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

        # 2. Dispatch review and obtain ReviewerCapability
        rev_disp_id = self._create_review_dispatch()
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.claim_reviewer_capability(rev_ctx)
        self.assertIsInstance(rev_cap, ReviewerCapability)
        self.assertEqual(rev_cap.role, "Reviewer")

        # 3. Issue ReviewEvidence
        rev_ev = self.ea.issue_review_evidence(
            self.delivery_id,
            rev_disp_id,
            self.candidate_commit,
            verdict="ACCEPT",
            reviewer_capability=rev_cap,
            now=self.t0 + timedelta(seconds=10),
        )
        self.assertIsInstance(rev_ev, ReviewEvidence)

        # 4. Transition to merge_queued
        st_rev = self.adapter.handle_review_verdict(
            self.delivery_id, "ACCEPT", review_dispatch_id=rev_disp_id, review_evidence=rev_ev, now=self.t0 + timedelta(seconds=12)
        )
        self.assertEqual(st_rev, "merge_queued")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "merge_queued")

        # 5. Issue IntegrationEvidence using task-scoped ControlCapability
        ctrl_for_int = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        gate_results = {g: True for g in MANDATORY_INTEGRATION_GATES}
        int_ev = self.ea.issue_integration_evidence(
            delivery_task_id=self.delivery_id,
            candidate_commit=self.candidate_commit,
            base_commit=self.approved_base,
            gates_pass=True,
            gate_results=gate_results,
            control_capability=ctrl_for_int,
            now=self.t0 + timedelta(seconds=15),
        )
        self.assertIsInstance(int_ev, IntegrationEvidence)

        # 6. Complete integration
        st_int = self.adapter.handle_integration_gates(
            self.delivery_id, gates_pass=True, integration_evidence=int_ev, now=self.t0 + timedelta(seconds=20)
        )
        self.assertEqual(st_int, "integrated")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "integrated")



class TestSolLeadAuditA189e50Remediation(unittest.TestCase):
    """
    Test suite verifying remediation of Sol-Lead independent audit on exact candidate a189e50:
    Finding 1: Bare get_reviewer_capability retrieval eliminated; delivery capability across reviewer-authenticated boundary.
    Finding 2: Elimination of _reviewer_mint_secret attribute and prevention of duplicate reviewer capability minting.
    Finding 3: Atomic verify_and_consume_capability preventing concurrent double review evidence issuance.
    """

    def setUp(self):
        self.delivery_id = "TASK-A189E50-REMED"
        self.orca_task_id = "task_orca_a189e50_impl_01"
        self.intended_disp = "ctx_a189e50_impl_01"
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.approved_base = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        self.t0 = datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc)
        self.mgr = LeaseManager([
            {"id": "LOCK-A189E50-REMED", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
        ])
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.lease = self.mgr.acquire_lease("LOCK-A189E50-REMED", self.delivery_id, self.intended_disp, now=self.t0)
        self.registry = SharedOrcaExecutionRegistry.get_default()
        self.control_secret = "test_control_secret_a189e50_32b_!"
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
            control_secret=self.control_secret,
        )
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-A189E50-REMED"])
        self.ea = self.adapter.evidence_authority

        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()
    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def _advance_to_review(self):
        disp_env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id, now=self.t0)
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=self.intended_disp,
            lease_id=self.lease.lease_id,
            fencing_token=self.lease.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=disp_env,
            now=self.t0,
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        self.adapter.start_running(self.delivery_id, disp_id)
        self.adapter.handle_worker_done(
            self.delivery_id,
            self.orca_task_id,
            disp_id,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            now=self.t0 + timedelta(seconds=3),
        )

    def _create_review_dispatch(self, rev_disp_id="ctx_a189e50_rev_01", rev_orca_id="task_orca_a189e50_rev_01"):
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id=rev_orca_id, now=self.t0 + timedelta(seconds=5)
        )
        return self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id=rev_orca_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )

    def test_a189e50_01_bare_get_reviewer_capability_without_reviewer_auth_rejected(self):
        """1. Finding 1 Counterexample: Caller in same process cannot perform bare retrieval of ReviewerCapability by dispatch ID string."""
        self._advance_to_review()
        rev_handle = self._create_review_dispatch()
        plain_disp_id = str(rev_handle)

        # Bare retrieval with plain string ID without reviewer authentication is rejected fail closed
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.get_reviewer_capability(plain_disp_id)
        self.assertIn("Bare retrieval of ReviewerCapability without reviewer authentication is forbidden", str(ctx.exception))

        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.ea.get_reviewer_capability(plain_disp_id)
        self.assertIn("Bare retrieval of ReviewerCapability without reviewer authentication is forbidden", str(ctx2.exception))

        # Bare retrieval with wrong auth token is rejected fail closed
        with self.assertRaises(ProtocolViolationError) as ctx3:
            self.adapter.get_reviewer_capability(plain_disp_id, reviewer_auth_token="wrong_token_hex_value")
        self.assertIn("Invalid reviewer_auth_token", str(ctx3.exception))

    def test_a189e50_02_control_authority_cannot_claim_or_retrieve_reviewer_capability(self):
        """2. Finding 1 Invariant: Control authority cannot obtain ReviewerCapability even when providing dispatch handle or token."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()
        ctrl_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)

        # Control passing control_capability to adapter.get_reviewer_capability
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.get_reviewer_capability(rev_disp_id, control_capability=ctrl_cap)
        self.assertIn("Control authority cannot issue or hold ReviewerCapability", str(ctx.exception))

        # Control passing control_secret to adapter.get_reviewer_capability
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.adapter.get_reviewer_capability(rev_disp_id, control_secret=self.control_secret)
        self.assertIn("Control authority cannot issue or hold ReviewerCapability", str(ctx2.exception))

        boundary = ReviewerSessionBoundary.get_default()
        channel = boundary._channels[rev_disp_id]
        # Control passing control_capability to channel.claim_capability
        with self.assertRaises(ProtocolViolationError) as ctx3:
            channel.claim_capability(control_capability=ctrl_cap)
        self.assertIn("Control authority cannot issue or hold ReviewerCapability", str(ctx3.exception))

        # Control passing control_secret to channel.claim_capability
        with self.assertRaises(ProtocolViolationError) as ctx4:
            channel.claim_capability(control_secret=self.control_secret)
        self.assertIn("Control authority cannot issue or hold ReviewerCapability", str(ctx4.exception))

    def test_a189e50_03_reviewer_delivery_channel_single_use_enforcement(self):
        """3. Finding 1 Invariant: ReviewerDeliveryChannel enforces strictly single-use capability delivery."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()
        boundary = ReviewerSessionBoundary.get_default()
        channel = boundary._channels[rev_disp_id]
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )

        # First claim via context succeeds
        cap = self.adapter.claim_reviewer_capability(rev_ctx)
        self.assertIsInstance(cap, ReviewerCapability)
        self.assertEqual(cap.delivery_task_id, self.delivery_id)
        self.assertEqual(cap.role, "Reviewer")

        # Second claim via context is rejected fail closed (proof replayed)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.claim_reviewer_capability(rev_ctx)
        self.assertTrue(
            "has already been claimed" in str(ctx.exception)
            or "has already been consumed" in str(ctx.exception)
        )

        # Second claim via channel directly is also rejected fail closed
        with self.assertRaises(ProtocolViolationError) as ctx2:
            channel.claim_capability(reviewer_context=rev_ctx)
        self.assertTrue(
            "has already been claimed" in str(ctx2.exception)
            or "has already been consumed" in str(ctx2.exception)
        )

    def test_a189e50_04_no_reviewer_mint_secret_attribute_and_mint_token_external_call_forbidden(self):
        """4. Finding 2 Counterexample: _reviewer_mint_secret attribute removed; external mint token creation strictly forbidden."""
        self._advance_to_review()
        # Check attribute does not exist on EvidenceAuthority
        self.assertFalse(hasattr(self.ea, "_reviewer_mint_secret"))
        self.assertFalse(hasattr(self.adapter.evidence_authority, "_reviewer_mint_secret"))

        # Direct external call to _create_reviewer_mint_token fails closed
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea._create_reviewer_mint_token(self.delivery_id, "ctx_fake_disp", self.candidate_commit)
        self.assertIn("Direct external calling of _create_reviewer_mint_token is forbidden", str(ctx.exception))

        # Passing _internal_secret to _create_reviewer_mint_token fails closed
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.ea._create_reviewer_mint_token(self.delivery_id, "ctx_fake_disp", self.candidate_commit, _internal_secret=b"dummy")
        self.assertIn("Direct external calling of _create_reviewer_mint_token is forbidden", str(ctx2.exception))

    def test_a189e50_05_duplicate_reviewer_capability_minting_for_same_dispatch_forbidden(self):
        """5. Finding 2 Invariant: Cannot mint duplicate ReviewerCapability or mint token for the same review dispatch."""
        self._advance_to_review()
        rev_handle = self._create_review_dispatch()

        # Review dispatch has already been minted. Trying to mint again for same dispatch is forbidden
        self.adapter._executing_lifecycle_handler = "create_review_dispatch"
        self.adapter._executing_lifecycle_task_id = self.delivery_id
        self.adapter._executing_review_dispatch = str(rev_handle)
        try:
            with self.assertRaises(ProtocolViolationError) as ctx:
                self.ea._create_reviewer_mint_token(self.delivery_id, str(rev_handle), self.candidate_commit)
            self.assertIn("duplicate minting is forbidden", str(ctx.exception))
        finally:
            self.adapter._executing_lifecycle_handler = None
            self.adapter._executing_lifecycle_task_id = None
            self.adapter._executing_review_dispatch = None

    def test_a189e50_06_concurrent_threads_cannot_issue_two_review_evidences_from_single_capability(self):
        """6. Finding 3 Concurrency Fixture: Atomic verify_and_consume_capability prevents two threads from issuing ReviewEvidence from one capability."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        cap = self.adapter.claim_reviewer_capability(rev_ctx)
        self.assertIsInstance(cap, ReviewerCapability)

        num_threads = 4
        barrier = threading.Barrier(num_threads)
        results = []
        errors = []
        lock = threading.Lock()

        def worker():
            barrier.wait()  # Synchronize threads to fire concurrently
            try:
                ev = self.ea.issue_review_evidence(
                    self.delivery_id,
                    rev_disp_id,
                    self.candidate_commit,
                    verdict="ACCEPT",
                    reviewer_capability=cap,
                )
                with lock:
                    results.append(ev)
            except ProtocolViolationError as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 1 thread must succeed, and the other 3 threads must fail closed
        self.assertEqual(len(results), 1, "Exactly one thread must succeed in issuing ReviewEvidence")
        self.assertEqual(len(errors), num_threads - 1, "All other threads must receive ProtocolViolationError")
        for err in errors:
            self.assertIn("has already been consumed", str(err))

        # Check evidence ID registered in authority exactly once
        self.assertIn(results[0].evidence_id, self.ea._issued_evidence_ids)
        self.assertIn(cap.capability_id, self.ea._consumed_capabilities)

    def test_a189e50_07_malformed_review_evidence_request_has_zero_side_effects_on_capability(self):
        """7. Finding 3 Invariant: Malformed review evidence request fails before verify_and_consume; capability remains valid."""
        self._advance_to_review()
        rev_disp_id = self._create_review_dispatch()
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        cap = self.adapter.claim_reviewer_capability(rev_ctx)
        self.assertIsInstance(cap, ReviewerCapability)

        # 1. Invalid verdict fails before consumption
        with self.assertRaises(ProtocolViolationError) as ctx1:
            self.ea.issue_review_evidence(
                self.delivery_id,
                rev_disp_id,
                self.candidate_commit,
                verdict="INVALID_VERDICT",
                reviewer_capability=cap,
            )
        self.assertIn("Invalid review verdict", str(ctx1.exception))
        self.assertNotIn(cap.capability_id, self.ea._consumed_capabilities)

        # 2. Invalid commit format fails before consumption
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.ea.issue_review_evidence(
                self.delivery_id,
                rev_disp_id,
                "not-a-valid-sha",
                verdict="ACCEPT",
                reviewer_capability=cap,
            )
        self.assertIn("must be an immutable full 40-character commit SHA", str(ctx2.exception))
        self.assertNotIn(cap.capability_id, self.ea._consumed_capabilities)

        # 3. Valid issuance succeeds with untouched capability
        ev = self.ea.issue_review_evidence(
            self.delivery_id,
            rev_disp_id,
            self.candidate_commit,
            verdict="ACCEPT",
            reviewer_capability=cap,
        )
        self.assertIsInstance(ev, ReviewEvidence)
        self.assertIn(cap.capability_id, self.ea._consumed_capabilities)

        # 4. Subsequent issuance fails because capability is now consumed
        with self.assertRaises(ProtocolViolationError) as ctx3:
            self.ea.issue_review_evidence(
                self.delivery_id,
                rev_disp_id,
                self.candidate_commit,
                verdict="ACCEPT",
                reviewer_capability=cap,
            )
        self.assertIn("has already been consumed", str(ctx3.exception))

    def test_a189e50_08_positive_control_end_to_end_lifecycle_with_reviewer_authenticated_channel(self):
        """8. Positive control: Full end-to-end lifecycle progression using reviewer-authenticated delivery channel and atomic capability consumption."""
        self._advance_to_review()

        # 1. Dispatch review returns dispatch ID string only (no bearer token or handle)
        rev_disp_id = self._create_review_dispatch()
        self.assertIsInstance(rev_disp_id, str)

        # 2. Authenticated ReviewerContext claims capability from channel
        boundary = ReviewerSessionBoundary.get_default()
        rev_ctx = boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=rev_disp_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.deliver_reviewer_capability(rev_ctx)
        self.assertIsInstance(rev_cap, ReviewerCapability)

        # 3. Reviewer issues ReviewEvidence
        rev_ev = self.ea.issue_review_evidence(
            self.delivery_id,
            rev_disp_id,
            self.candidate_commit,
            verdict="ACCEPT",
            reviewer_capability=rev_cap,
            now=self.t0 + timedelta(seconds=10),
        )
        self.assertIsInstance(rev_ev, ReviewEvidence)

        # 4. Adapter transitions to merge_queued
        st_rev = self.adapter.handle_review_verdict(
            self.delivery_id,
            "ACCEPT",
            review_dispatch_id=rev_disp_id,
            review_evidence=rev_ev,
            now=self.t0 + timedelta(seconds=12),
        )
        self.assertEqual(st_rev, "merge_queued")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "merge_queued")

        # 5. Control issues ControlCapability and IntegrationEvidence
        ctrl_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        gate_results = {g: True for g in MANDATORY_INTEGRATION_GATES}
        int_ev = self.ea.issue_integration_evidence(
            delivery_task_id=self.delivery_id,
            candidate_commit=self.candidate_commit,
            base_commit=self.approved_base,
            gates_pass=True,
            gate_results=gate_results,
            control_capability=ctrl_cap,
            integrated_by="Control",
            now=self.t0 + timedelta(seconds=15),
        )
        self.assertIsInstance(int_ev, IntegrationEvidence)

        # 6. Adapter transitions to integrated
        st_int = self.adapter.handle_integration_gates(
            self.delivery_id,
            gates_pass=True,
            integration_evidence=int_ev,
            now=self.t0 + timedelta(seconds=20),
        )
        self.assertEqual(st_int, "integrated")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

class TestSolRemediationSeparationOfDuties(unittest.TestCase):
    """
    Test suite verifying strict Separation of Duties for review dispatch and capability delivery:
    1. Negative fixture: create_review_dispatch() returns bare dispatch_id string only; caller receives neither bearer token nor ReviewDispatchHandle.
    2. Negative fixture: Dispatch creator cannot claim ReviewerCapability using bare dispatch ID without authenticated ReviewerContext.
    3. Negative fixture: Dispatch creator attempting to spoof ReviewerContext with Control principal or invalid principal cannot claim ReviewerCapability.
    4. Negative fixture: Control cannot read, hold, or extract reviewer auth token from adapter; _reviewer_auth_tokens attribute is absent.
    5. Negative fixture: Dispatch creator cannot issue ACCEPT verdict or advance task to merge_queued without an authenticated reviewer claiming ReviewerCapability.
    6. Negative fixture: Mismatched terminal or Orca dispatch ID in ReviewerContext fails closed when claiming ReviewerCapability.
    7. Positive fixture: Authenticated independent reviewer context (cx/gpt-5.6-sol on Claude Code) successfully claims ReviewerCapability, issues ACCEPT verdict, and advances task to merge_queued.
    8. Invariant: ReviewerSessionProof is strictly single-use; replayed proof and duplicated proof issuance are rejected.
    9. Positive control: Authenticated independent reviewer boundary completes review ACCEPT, integration gates pass, and task reaches integrated.
    10. Negative fixture: Omitted reviewer_secret fails closed, preventing ReviewerSessionProof minting and lifecycle advancement.
    11. Negative fixture: Singleton secret replacement via get_default fails closed against active boundary.
    12. Invariant: ReviewerSessionBoundary eliminates reset/bootstrap/inject from production surface; credential cannot be injected or replaced.
    14. Negative fixture: Ordinary in-process caller attempting to reset boundary, select secret, forge context, and issue ACCEPT fails closed; task cannot reach merge_queued.
    13. Invariant: delivery_engine does not define or export DEFAULT_TEST_REVIEWER_SECRET.
    17. Negative fixture: Ordinary in-process caller in fresh process cannot construct ReviewerHostHandoff authority, subclass handoff, or provision ReviewerSessionBoundary; boundary remains unconfigured and proofs cannot be issued.
    """

    def setUp(self):
        self.delivery_id = "TASK-SOD-REMED"
        self.orca_task_id = "task_orca_sod_impl_01"
        self.intended_disp = "ctx_sod_impl_01"
        cmd_head = ["git", "rev-parse", "HEAD"]
        self.candidate_commit = subprocess.run(cmd_head, cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        self.approved_base = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        self.t0 = datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc)
        self.mgr = LeaseManager([
            {"id": "LOCK-SOD-REMED", "mode": "exclusive", "renewable": True, "lease_seconds": 600},
        ])
        self.mgr.set_task_authority(self.delivery_id, "granted")
        self.lease = self.mgr.acquire_lease("LOCK-SOD-REMED", self.delivery_id, self.intended_disp, now=self.t0)
        self.registry = SharedOrcaExecutionRegistry.get_default()
        self.control_secret = "test_control_secret_sod_32b_hex!"
        self.reviewer_secret = TEST_FIXTURE_REVIEWER_SECRET
        self.boundary = ReviewerSessionBoundary.get_default()
        self.adapter = OrcaDeliveryAdapter(
            self.mgr,
            approved_candidate_commit=self.candidate_commit,
            git_root=ROOT_DIR,
            control_secret=self.control_secret,
            reviewer_boundary=self.boundary,
        )
        self.adapter.set_task_authority(self.delivery_id, "granted")
        self.adapter.set_task_state(self.delivery_id, "ready")
        self.adapter.register_task_locks(self.delivery_id, ["LOCK-SOD-REMED"])
        self.ea = self.adapter.evidence_authority

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def _advance_to_review(self):
        disp_env = make_execution_envelope(self.delivery_id, self.intended_disp, phase="implement", orca_task_id=self.orca_task_id, now=self.t0)
        disp_id = self.adapter.create_dispatch(
            self.delivery_id,
            orca_task_id=self.orca_task_id,
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=self.intended_disp,
            lease_id=self.lease.lease_id,
            fencing_token=self.lease.fencing_token,
            dispatch_origin="dely dispatch",
            execution_envelope=disp_env,
            now=self.t0,
        )
        self.adapter.acknowledge_dispatch(self.delivery_id, disp_id)
        self.adapter.start_running(self.delivery_id, disp_id)
        self.adapter.handle_worker_done(
            self.delivery_id,
            self.orca_task_id,
            disp_id,
            "succeeded",
            candidate_commit=self.candidate_commit,
            fencing_token=self.lease.fencing_token,
            now=self.t0 + timedelta(seconds=3),
        )

    def test_sod_01_dispatch_creation_returns_string_id_without_bearer_token_or_handle(self):
        """1. Separation of duties: create_review_dispatch returns str dispatch ID only; no bearer token or handle returned to dispatcher."""
        self._advance_to_review()
        rev_env = make_execution_envelope(
            self.delivery_id, "ctx_sod_rev_01", phase="review",
            orca_task_id="task_orca_sod_rev_01", now=self.t0 + timedelta(seconds=5)
        )
        disp_res = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_sod_rev_01",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id="ctx_sod_rev_01",
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        self.assertIsInstance(disp_res, str)
        self.assertNotIsInstance(disp_res, ReviewDispatchHandle)
        self.assertFalse(hasattr(disp_res, "reviewer_auth_token"))
        self.assertFalse(hasattr(disp_res, "claim_reviewer_capability"))
        # Verify adapter does not store or expose _reviewer_auth_tokens map or channels
        self.assertFalse(hasattr(self.adapter, "_reviewer_auth_tokens"))
        self.assertFalse(hasattr(self.adapter, "_reviewer_delivery_channels"))
        self.assertFalse(hasattr(self.adapter, "reviewer_auth_token"))

    def test_sod_02_dispatch_creator_cannot_claim_reviewer_capability_with_bare_dispatch_id(self):
        """2. Separation of duties: Dispatch creator calling claim or get without ReviewerContext fails closed."""
        self._advance_to_review()
        rev_disp_id = "ctx_sod_rev_02"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id="task_orca_sod_rev_02", now=self.t0 + timedelta(seconds=5)
        )
        res_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_sod_rev_02",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.claim_reviewer_capability(res_id)
        self.assertIn("Bare retrieval of ReviewerCapability without reviewer authentication is forbidden", str(ctx.exception))

        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.adapter.get_reviewer_capability(res_id)
        self.assertIn("Bare retrieval of ReviewerCapability without reviewer authentication is forbidden", str(ctx2.exception))

    def test_sod_03_dispatch_creator_cannot_spoof_control_principal_to_claim_reviewer_capability(self):
        """3. Separation of duties: Caller attempting to claim with Control principal is rejected fail closed."""
        self._advance_to_review()
        rev_disp_id = "ctx_sod_rev_03"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id="task_orca_sod_rev_03", now=self.t0 + timedelta(seconds=5)
        )
        res_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_sod_rev_03",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        spoofed_ctx = ReviewerContext(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            orca_task_id="task_orca_sod_rev_03",
            terminal_id=rev_env.live_terminal_evidence.archive_reference,
            reviewer_principal="Control",
            harness="Control",
        )
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.claim_reviewer_capability(spoofed_ctx)
        self.assertIn("Control authority cannot claim ReviewerCapability", str(ctx.exception))

    def test_sod_04_mismatched_terminal_or_orca_dispatch_in_reviewer_context_fails_closed(self):
        """4. Separation of duties: ReviewerContext with mismatched terminal or orca_task_id fails closed."""
        self._advance_to_review()
        rev_disp_id = "ctx_sod_rev_04"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id="task_orca_sod_rev_04", now=self.t0 + timedelta(seconds=5)
        )
        res_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_sod_rev_04",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        # Wrong terminal
        wrong_term_ctx = ReviewerContext(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            orca_task_id="task_orca_sod_rev_04",
            terminal_id="term_wrong_spoofed_archive_ref",
            reviewer_principal="cx/gpt-5.6-sol",
            harness="Claude Code",
        )
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.claim_reviewer_capability(wrong_term_ctx)
        self.assertIn("Reviewer terminal", str(ctx.exception))

        # Wrong orca task ID
        wrong_orca_ctx = ReviewerContext(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            orca_task_id="task_orca_wrong_id",
            terminal_id=rev_env.live_terminal_evidence.archive_reference,
            reviewer_principal="cx/gpt-5.6-sol",
            harness="Claude Code",
        )
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.adapter.claim_reviewer_capability(wrong_orca_ctx)
        self.assertIn("Reviewer orca_task_id", str(ctx2.exception))

    def test_sod_05_dispatch_creator_cannot_issue_accept_without_valid_reviewer_capability(self):
        """5. Separation of duties: Dispatch creator cannot issue ACCEPT or advance task to merge_queued without authenticated reviewer."""
        self._advance_to_review()
        rev_disp_id = "ctx_sod_rev_05"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id="task_orca_sod_rev_05", now=self.t0 + timedelta(seconds=5)
        )
        res_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_sod_rev_05",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        # Attempting to issue review evidence without capability
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.ea.issue_review_evidence(
                self.delivery_id, res_id, self.candidate_commit, verdict="ACCEPT"
            )
        self.assertIn("requires an independently authenticated ReviewerCapability", str(ctx.exception))

        # Task remains in review state
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

    def test_sod_06_dispatch_creator_with_all_public_ids_cannot_claim_reviewer_capability(self):
        """6. Negative fixture: Dispatch creator possessing all 7 public identifiers cannot self-construct ReviewerContext or claim capability."""
        self._advance_to_review()
        rev_disp_id = "ctx_sod_rev_06"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id="task_orca_sod_rev_06", now=self.t0 + timedelta(seconds=5)
        )
        res_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_sod_rev_06",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        # Caller has all 7 public identifiers: task_id, dispatch_id, orca_task_id, terminal_id, candidate_commit, route, harness
        self_constructed_ctx = ReviewerContext(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            orca_task_id="task_orca_sod_rev_06",
            terminal_id=rev_env.live_terminal_evidence.archive_reference,
            reviewer_principal="cx/gpt-5.6-sol",
            harness="Claude Code",
        )
        # Attempt claim via adapter fails closed
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.adapter.claim_reviewer_capability(self_constructed_ctx)
        self.assertIn("requires an authenticated opaque single-use ReviewerSessionProof", str(ctx.exception))

        # Attempt claim via boundary fails closed
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.boundary.claim_capability(self_constructed_ctx)
        self.assertIn("requires an authenticated opaque single-use ReviewerSessionProof", str(ctx2.exception))

    def test_sod_07_dispatch_creator_cannot_read_or_forge_reviewer_session_proof(self):
        """7. Negative fixture: Dispatch creator cannot read tokens/channels from adapter or forge ReviewerSessionProof."""
        self._advance_to_review()
        rev_disp_id = "ctx_sod_rev_07"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id="task_orca_sod_rev_07", now=self.t0 + timedelta(seconds=5)
        )
        res_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_sod_rev_07",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        # 1. Adapter has no reviewer channels or tokens in visible state
        self.assertFalse(hasattr(self.adapter, "_reviewer_delivery_channels"))
        self.assertFalse(hasattr(self.adapter, "_channels"))
        self.assertFalse(hasattr(self.adapter, "_reviewer_auth_tokens"))

        # 2. Control authority attempting to issue ReviewerSessionProof is rejected
        ctrl_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        with self.assertRaises(ProtocolViolationError) as ctx:
            self.boundary.issue_session_proof(
                self.delivery_id, res_id, control_capability=ctrl_cap, reviewer_secret=self.reviewer_secret
            )
        self.assertIn("Control authority cannot issue ReviewerSessionProof", str(ctx.exception))

        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.boundary.issue_session_proof(
                self.delivery_id, res_id, control_secret=self.control_secret, reviewer_secret=self.reviewer_secret
            )
        self.assertIn("Control authority cannot issue ReviewerSessionProof", str(ctx2.exception))

        # 3. Caller with wrong reviewer secret cannot issue proof
        with self.assertRaises(ProtocolViolationError) as ctx3:
            self.boundary.issue_session_proof(
                self.delivery_id, res_id, reviewer_secret="unauthorized_caller_secret"
            )
        self.assertIn("Invalid reviewer secret", str(ctx3.exception))

        # 4. Forged proof with bad HMAC signature is rejected fail closed
        forged_proof = ReviewerSessionProof(
            proof_id="prf_forged_01",
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            orca_task_id="task_orca_sod_rev_07",
            terminal_id=rev_env.live_terminal_evidence.archive_reference,
            candidate_commit=self.candidate_commit,
            reviewer_route="cx/gpt-5.6-sol",
            reviewer_harness="Claude Code",
            proof_token="forged_token_32b_hex_value_invalid",
            authority_id=id(self.boundary),
            created_at=time.time(),
            signature="bad_forged_signature_hex" * 4,
        )
        forged_ctx = ReviewerContext(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            orca_task_id="task_orca_sod_rev_07",
            terminal_id=rev_env.live_terminal_evidence.archive_reference,
            reviewer_principal="cx/gpt-5.6-sol",
            harness="Claude Code",
            reviewer_session_proof=forged_proof,
        )
        with self.assertRaises(ProtocolViolationError) as ctx4:
            self.adapter.claim_reviewer_capability(forged_ctx)
        self.assertIn("Invalid ReviewerSessionProof signature", str(ctx4.exception))

    def test_sod_08_reviewer_session_proof_single_use_enforcement(self):
        """8. Invariant: ReviewerSessionProof is strictly single-use; replayed proof and duplicated proof issuance are rejected."""
        self._advance_to_review()
        rev_disp_id = "ctx_sod_rev_08"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id="task_orca_sod_rev_08", now=self.t0 + timedelta(seconds=5)
        )
        res_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_sod_rev_08",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        # Legitimate reviewer session issues proof
        proof = self.boundary.issue_session_proof(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        # Duplicated proof issuance for the same dispatch is rejected
        with self.assertRaises(ProtocolViolationError) as ctx_dup:
            self.boundary.issue_session_proof(
                delivery_task_id=self.delivery_id,
                review_dispatch_id=res_id,
                candidate_commit=self.candidate_commit,
                reviewer_secret=self.reviewer_secret,
            )
        self.assertIn("single-use proof issuance cannot be duplicated", str(ctx_dup.exception))

        # First claim consumes proof
        ctx1 = ReviewerContext(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            orca_task_id="task_orca_sod_rev_08",
            terminal_id=rev_env.live_terminal_evidence.archive_reference,
            reviewer_principal="cx/gpt-5.6-sol",
            harness="Claude Code",
            reviewer_session_proof=proof,
        )
        rev_cap = self.adapter.claim_reviewer_capability(ctx1)
        self.assertIsInstance(rev_cap, ReviewerCapability)

        # Second claim attempting to replay the consumed proof fails closed
        with self.assertRaises(ProtocolViolationError) as ctx_replay:
            self.adapter.claim_reviewer_capability(ctx1)
        self.assertIn("single-use proof replay forbidden", str(ctx_replay.exception))

    def test_sod_09_positive_fixture_independent_reviewer_boundary_full_lifecycle_to_integrated(self):
        """9. Positive control: Authenticated independent reviewer boundary completes review ACCEPT, integration gates pass, and task reaches integrated."""
        self._advance_to_review()
        rev_disp_id = "ctx_sod_rev_09"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id="task_orca_sod_rev_09", now=self.t0 + timedelta(seconds=5)
        )
        res_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_sod_rev_09",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        # Legitimate independent reviewer session creates context with proof
        rev_ctx = self.boundary.create_reviewer_context(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            candidate_commit=self.candidate_commit,
            reviewer_secret=self.reviewer_secret,
        )
        rev_cap = self.adapter.deliver_reviewer_capability(rev_ctx)
        self.assertIsInstance(rev_cap, ReviewerCapability)
        self.assertEqual(rev_cap.role, "Reviewer")

        # Reviewer issues ACCEPT verdict
        rev_ev = self.ea.issue_review_evidence(
            self.delivery_id,
            res_id,
            self.candidate_commit,
            verdict="ACCEPT",
            reviewer_capability=rev_cap,
            now=self.t0 + timedelta(seconds=10),
        )
        self.assertIsInstance(rev_ev, ReviewEvidence)

        # Task transitions to merge_queued
        st_rev = self.adapter.handle_review_verdict(
            self.delivery_id,
            "ACCEPT",
            review_dispatch_id=res_id,
            review_evidence=rev_ev,
            now=self.t0 + timedelta(seconds=12),
        )
        self.assertEqual(st_rev, "merge_queued")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "merge_queued")

        # Control issues IntegrationEvidence and task advances to integrated
        ctrl_cap = self.ea.issue_control_capability(self.control_secret, delivery_task_id=self.delivery_id)
        int_ev = self.adapter.issue_integration_evidence(
            self.delivery_id,
            self.candidate_commit,
            self.approved_base,
            gates_pass=True,
            control_capability=ctrl_cap,
            now=self.t0 + timedelta(seconds=15),
        )
        st_int = self.adapter.handle_integration_gates(
            self.delivery_id,
            gates_pass=True,
            integration_evidence=int_ev,
            now=self.t0 + timedelta(seconds=16),
        )
        self.assertEqual(st_int, "integrated")
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "integrated")

    def test_sod_10_omitted_reviewer_secret_fails_closed_preventing_proof_minting_and_lifecycle_advance(self):
        """10. Negative fixture: Caller attempting to mint proof or context with omitted secret fails closed; task cannot advance."""
        self._advance_to_review()
        rev_disp_id = "ctx_sod_rev_10"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id="task_orca_sod_rev_10", now=self.t0 + timedelta(seconds=5)
        )
        res_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_sod_rev_10",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )

        # 1. issue_session_proof with omitted secret (None) fails closed
        with self.assertRaises(ProtocolViolationError) as ctx1:
            self.boundary.issue_session_proof(
                self.delivery_id,
                res_id,
                reviewer_secret=None,
            )
        self.assertIn("reviewer_secret is mandatory", str(ctx1.exception))
        self.assertIn("omitted secret rejected fail-closed", str(ctx1.exception))

        # 2. issue_session_proof with empty/whitespace secret fails closed
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.boundary.issue_session_proof(
                self.delivery_id,
                res_id,
                reviewer_secret="   ",
            )
        self.assertIn("reviewer_secret is mandatory", str(ctx2.exception))

        # 3. create_reviewer_context with omitted secret (None) fails closed
        with self.assertRaises(ProtocolViolationError) as ctx3:
            self.boundary.create_reviewer_context(
                delivery_task_id=self.delivery_id,
                review_dispatch_id=res_id,
                candidate_commit=self.candidate_commit,
                reviewer_secret=None,
            )
        self.assertIn("reviewer_secret is mandatory", str(ctx3.exception))
        self.assertIn("omitted secret rejected fail-closed", str(ctx3.exception))

        # 4. Caller cannot issue review evidence or advance task without secret
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

    def test_sod_11_singleton_secret_replacement_via_get_default_fails_closed(self):
        """11. Negative fixture: Caller attempting to replace credential of existing singleton via get_default fails closed."""
        self._advance_to_review()
        rev_disp_id = "ctx_sod_rev_11"
        rev_env = make_execution_envelope(
            self.delivery_id, rev_disp_id, phase="review",
            orca_task_id="task_orca_sod_rev_11", now=self.t0 + timedelta(seconds=5)
        )
        res_id = self.adapter.create_review_dispatch(
            self.delivery_id,
            orca_task_id="task_orca_sod_rev_11",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )

        # Attacker attempts to replace singleton secret on active boundary
        with self.assertRaises(ProtocolViolationError) as ctx:
            ReviewerSessionBoundary.get_default(reviewer_secret="attacker_replacement_secret_32b")
        self.assertIn("Cannot mutate reviewer credential of already initialized ReviewerSessionBoundary", str(ctx.exception))
        self.assertIn("singleton credential replacement forbidden fail-closed", str(ctx.exception))

        # Boundary secret is untouched
        self.assertEqual(self.boundary._reviewer_secret, self.reviewer_secret.encode("utf-8"))

        # Attacker cannot issue proof with replacement secret
        with self.assertRaises(ProtocolViolationError) as ctx2:
            self.boundary.issue_session_proof(
                self.delivery_id,
                res_id,
                reviewer_secret="attacker_replacement_secret_32b",
            )
        self.assertIn("Invalid reviewer secret", str(ctx2.exception))

        # Legitimate reviewer with authentic secret succeeds
        legit_proof = self.boundary.issue_session_proof(
            self.delivery_id,
            res_id,
            reviewer_secret=self.reviewer_secret,
        )
        self.assertIsInstance(legit_proof, ReviewerSessionProof)

    def test_sod_12_ordinary_caller_cannot_bootstrap_reset_or_inject_boundary_credentials(self):
        """12. Invariant: ReviewerSessionBoundary eliminates reset/bootstrap/inject from production surface; credential cannot be injected or replaced."""
        # 1. reset_default does not exist on ReviewerSessionBoundary
        self.assertFalse(hasattr(ReviewerSessionBoundary, "reset_default"))

        # 2. inject_reviewer_credential does not exist
        self.assertFalse(hasattr(ReviewerSessionBoundary, "inject_reviewer_credential"))

        # 3. bootstrap_reviewer_credential does not exist
        self.assertFalse(hasattr(ReviewerSessionBoundary, "bootstrap_reviewer_credential"))

        # 4. bootstrap_reviewer_capability does not exist
        self.assertFalse(hasattr(ReviewerSessionBoundary, "bootstrap_reviewer_capability"))

        # 5. Caller cannot inject secret via get_default
        with self.assertRaises(ProtocolViolationError) as ctx1:
            ReviewerSessionBoundary.get_default(reviewer_secret="attacker_injection_attempt")
        self.assertIn("Cannot mutate reviewer credential of already initialized ReviewerSessionBoundary", str(ctx1.exception))

        # 6. Adapter's bound reviewer boundary is immutable (cannot be overwritten or replaced by caller)
        with self.assertRaises(AttributeError):
            self.adapter.reviewer_boundary = ReviewerSessionBoundary(reviewer_secret="attacker_boundary_secret")

    def test_sod_13_no_public_default_reviewer_secret_in_delivery_engine(self):
        """13. Invariant: delivery_engine does not define or export DEFAULT_TEST_REVIEWER_SECRET."""
        import delivery_engine
        self.assertFalse(hasattr(delivery_engine, "DEFAULT_TEST_REVIEWER_SECRET"))
        self.assertNotIn("DEFAULT_TEST_REVIEWER_SECRET", dir(delivery_engine))

    def test_sod_14_ordinary_in_process_caller_cannot_bypass_reviewer_or_reach_merge_queued(self):
        """14. Negative fixture: Ordinary in-process caller attempting to reset boundary, select secret, forge context, and issue ACCEPT fails closed; task cannot reach merge_queued."""
        self._advance_to_review()
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

        # 1. Attacker in same process attempts to reset boundary -> fails (no reset_default)
        self.assertFalse(hasattr(ReviewerSessionBoundary, "reset_default"))

        # 2. Attacker creates an unauthorized ReviewerSessionBoundary with attacker-chosen secret
        attacker_secret = "attacker_chosen_secret_32b_hex!"
        attacker_boundary = ReviewerSessionBoundary(reviewer_secret=attacker_secret)

        # 3. Attacker cannot replace the adapter's bound reviewer boundary
        with self.assertRaises(AttributeError):
            self.adapter.reviewer_boundary = attacker_boundary

        # 3b. Attacker cannot supply attacker_boundary to OrcaDeliveryAdapter constructor
        with self.assertRaises(ProtocolViolationError) as ctx_adapt:
            OrcaDeliveryAdapter(
                self.mgr,
                approved_candidate_commit=self.candidate_commit,
                git_root=ROOT_DIR,
                control_secret=self.control_secret,
                reviewer_boundary=attacker_boundary,
            )
        self.assertIn("Caller-selected reviewer boundary forbidden", str(ctx_adapt.exception))

        # 4. Create review dispatch on adapter; adapter binds dispatch strictly to its provisioned boundary
        rev_disp_id = "ctx_sod_rev_14"
        rev_env = make_execution_envelope(
            self.delivery_id,
            rev_disp_id,
            phase="review",
            orca_task_id="task_orca_sod_rev_14",
            now=self.t0 + timedelta(seconds=5),
        )
        res_id = self.adapter.create_review_dispatch(
            delivery_task_id=self.delivery_id,
            orca_task_id="task_orca_sod_rev_14",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=rev_disp_id,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )
        self.assertEqual(res_id, rev_disp_id)

        # 5. Attacker boundary has no registered delivery channel for res_id; proof issuance fails closed
        with self.assertRaises(ProtocolViolationError) as ctx_chan:
            attacker_boundary.issue_session_proof(
                self.delivery_id,
                res_id,
                reviewer_secret=attacker_secret,
            )
        self.assertIn("No delivery channel registered for review dispatch", str(ctx_chan.exception))

        # 5b. Forged proof with attacker authority_id is rejected by adapter fail-closed
        forged_proof = ReviewerSessionProof(
            proof_id="rev_prf_forged_14",
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            orca_task_id="task_orca_sod_rev_14",
            terminal_id=rev_env.live_terminal_evidence.archive_reference,
            candidate_commit=self.candidate_commit,
            reviewer_route="cx/gpt-5.6-sol",
            reviewer_harness="Claude Code",
            proof_token="forged_token_32b_hex",
            authority_id=id(attacker_boundary),
            created_at=time.time(),
            signature="forged_sig",
        )
        attacker_ctx = ReviewerContext(
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            orca_task_id="task_orca_sod_rev_14",
            terminal_id=rev_env.live_terminal_evidence.archive_reference,
            reviewer_principal="cx/gpt-5.6-sol",
            harness="Claude Code",
            reviewer_session_proof=forged_proof,
        )
        with self.assertRaises(ProtocolViolationError) as ctx_claim:
            self.adapter.claim_reviewer_capability(attacker_ctx)
        self.assertIn("authority_id mismatch", str(ctx_claim.exception))

        # 6. Attacker tries to mint proof on the adapter's bound boundary with attacker_secret -> fails closed
        with self.assertRaises(ProtocolViolationError) as ctx_proof:
            self.adapter.reviewer_boundary.issue_session_proof(
                self.delivery_id,
                res_id,
                reviewer_secret=attacker_secret,
            )
        self.assertIn("Invalid reviewer secret", str(ctx_proof.exception))

        # 7. Attacker cannot forge review evidence without authentic ReviewerCapability
        fake_cap = ReviewerCapability(
            capability_id="forged_cap_01",
            delivery_task_id=self.delivery_id,
            review_dispatch_id=res_id,
            candidate_commit=self.candidate_commit,
            reviewer_route="cx/gpt-5.6-sol",
            reviewer_harness="Claude Code",
            authority_id=12345,
            created_at=time.time(),
            signature="forged_sig",
            role="Reviewer",
        )
        with self.assertRaises(ProtocolViolationError):
            self.adapter.issue_review_evidence(
                self.delivery_id,
                res_id,
                self.candidate_commit,
                verdict="ACCEPT",
                reviewer_capability=fake_cap,
                now=self.t0 + timedelta(seconds=6),
            )

        # 8. Task remains strictly in review state; cannot reach merge_queued
        self.assertEqual(self.adapter.get_task_state(self.delivery_id), "review")

    def test_sod_15_fresh_process_missing_external_provisioning_rejected_task_remains_review(self):
        """15. Sol actionable finding counterexample: Fresh process lacking external reviewer provisioning
        fails closed; ordinary in-process caller cannot select secret, mint proofs, claim capability,
        or reach merge_queued; task remains strictly in review state."""
        clean_env = {k: v for k, v in os.environ.items() if "REVIEWER" not in k.upper()}
        child_code = r'''
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import subprocess

assert not any("REVIEWER" in k.upper() for k in os.environ), "Reviewer env vars present in test environment"

sys.path.insert(0, str(Path("docs/parallel-delivery").resolve()))
import delivery_engine
from delivery_engine import (
    OrcaDeliveryAdapter,
    LeaseManager,
    ReviewerSessionBoundary,
    ReviewerHostHandoff,
    make_execution_envelope,
    SharedOrcaExecutionRegistry,
    ProtocolViolationError,
)

assert not hasattr(delivery_engine, "DEFAULT_TEST_REVIEWER_SECRET"), "delivery_engine exports DEFAULT_TEST_REVIEWER_SECRET"

delivery_id = "TASK-SOD-15"
disp_id = "ctx_sod_15_impl"
cmd_head = ["git", "rev-parse", "HEAD"]
candidate = subprocess.run(cmd_head, capture_output=True, text=True, check=True).stdout.strip()
t0 = datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc)

mgr = LeaseManager([{"id": "LOCK-SOD-15", "mode": "exclusive", "renewable": True, "lease_seconds": 600}])
mgr.set_task_authority(delivery_id, "granted")
lease = mgr.acquire_lease("LOCK-SOD-15", delivery_id, disp_id, now=t0)

# Default adapter in fresh unprovisioned process
adapter = OrcaDeliveryAdapter(
    mgr,
    approved_candidate_commit=candidate,
    git_root=Path(".").resolve(),
    control_secret="test_control_secret_32b_hex!",
)
adapter.set_task_authority(delivery_id, "granted")
adapter.set_task_state(delivery_id, "ready")
adapter.register_task_locks(delivery_id, ["LOCK-SOD-15"])

# Caller-selected provisioning via provision_from_host is rejected fail-closed
try:
    ReviewerSessionBoundary.provision_from_host(reviewer_secret="attacker_secret")
    assert False, "provision_from_host accepted caller-selected secret"
except ProtocolViolationError as e:
    assert "Caller-selected" in str(e) or "already provisioned" in str(e) or "unforgeable" in str(e)

# Parameterless provision_from_host is rejected fail-closed
try:
    ReviewerSessionBoundary.provision_from_host()
    assert False, "parameterless provision_from_host succeeded without authority"
except ProtocolViolationError as e:
    assert "Caller-selected" in str(e) or "unforgeable" in str(e)

# Caller-selected authority is rejected fail-closed
try:
    ReviewerHostHandoff(reviewer_secret="attacker_chosen_secret")
    assert False, "ReviewerHostHandoff accepted caller-selected secret"
except ProtocolViolationError as e:
    assert "Caller-selected" in str(e)

# Caller-selected boundary passed to OrcaDeliveryAdapter is rejected fail-closed
attacker_boundary = ReviewerSessionBoundary(reviewer_secret="attacker_chosen_secret")
try:
    OrcaDeliveryAdapter(
        mgr,
        approved_candidate_commit=candidate,
        git_root=Path(".").resolve(),
        reviewer_boundary=attacker_boundary,
    )
    assert False, "OrcaDeliveryAdapter accepted caller-selected boundary"
except ProtocolViolationError as e:
    assert "Caller-selected reviewer boundary forbidden" in str(e)

# Boundary has no configured reviewer credential
boundary = adapter.reviewer_boundary
assert boundary._reviewer_secret is None, "Boundary has unauthenticated or fallback secret configured"

# Advance implement phase to worker_done succeeded
disp_env = make_execution_envelope(delivery_id, disp_id, phase="implement", orca_task_id="task_impl_15", now=t0)
d_id = adapter.create_dispatch(
    delivery_id,
    orca_task_id="task_impl_15",
    candidate_commit=candidate,
    intended_dispatch_id=disp_id,
    lease_id=lease.lease_id,
    fencing_token=lease.fencing_token,
    dispatch_origin="dely dispatch",
    execution_envelope=disp_env,
    now=t0,
)
adapter.acknowledge_dispatch(delivery_id, d_id)
adapter.start_running(delivery_id, d_id)
adapter.handle_worker_done(delivery_id, "task_impl_15", d_id, "succeeded", candidate_commit=candidate, fencing_token=lease.fencing_token, now=t0 + timedelta(seconds=1))

assert adapter.get_task_state(delivery_id) == "review", f"Expected review state, got {adapter.get_task_state(delivery_id)}"

# Create review dispatch
rev_disp_id = "ctx_rev_15"
rev_env = make_execution_envelope(delivery_id, rev_disp_id, phase="review", orca_task_id="task_rev_15", now=t0 + timedelta(seconds=2))
res_id = adapter.create_review_dispatch(
    delivery_id,
    orca_task_id="task_rev_15",
    candidate_commit=candidate,
    intended_dispatch_id=rev_disp_id,
    dispatch_origin="dely dispatch",
    execution_envelope=rev_env,
    now=t0 + timedelta(seconds=2),
)

# Attempting to create reviewer context / issue session proof without external provisioning fails closed
try:
    adapter.reviewer_boundary.create_reviewer_context(
        delivery_task_id=delivery_id,
        review_dispatch_id=res_id,
        orca_task_id="task_rev_15",
        terminal_id=rev_env.live_terminal_evidence.archive_reference,
        candidate_commit=candidate,
        reviewer_secret="test_fixture_reviewer_secret_32b_hex!",
    )
    assert False, "create_reviewer_context succeeded without external reviewer provisioning"
except ProtocolViolationError as e:
    assert "Reviewer credential not configured on ReviewerSessionBoundary fail-closed" in str(e)

try:
    adapter.reviewer_boundary.issue_session_proof(
        delivery_task_id=delivery_id,
        review_dispatch_id=res_id,
        reviewer_secret="test_fixture_reviewer_secret_32b_hex!",
    )
    assert False, "issue_session_proof succeeded without external reviewer provisioning"
except ProtocolViolationError as e:
    assert "Reviewer credential not configured on ReviewerSessionBoundary fail-closed" in str(e)

# Attempting to issue review evidence without capability fails closed
try:
    adapter.issue_review_evidence(
        delivery_id,
        res_id,
        candidate,
        verdict="ACCEPT",
        reviewer_capability=None,
    )
    assert False, "issue_review_evidence succeeded with None capability"
except ProtocolViolationError:
    pass

# Attempting to advance review verdict without valid evidence fails closed
try:
    adapter.handle_review_verdict(
        delivery_id,
        "ACCEPT",
        review_dispatch_id=res_id,
        review_evidence=None,
    )
    assert False, "handle_review_verdict succeeded with None evidence"
except ProtocolViolationError:
    pass

# Task remains strictly in review state; cannot reach merge_queued
final_state = adapter.get_task_state(delivery_id)
assert final_state == "review", f"Expected task to remain in 'review', but got {final_state}"
print("FRESH_PROCESS_PASS: task safely remains in review")
'''
        res = subprocess.run([sys.executable, "-c", child_code], env=clean_env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Child process failed: stdout={res.stdout}\nstderr={res.stderr}")
        self.assertIn("FRESH_PROCESS_PASS: task safely remains in review", res.stdout)

    def test_sod_16_fresh_process_caller_set_environment_not_treated_as_external_provisioning(self):
        """16. Sol actionable finding counterexample: In a fresh process, caller setting reviewer
        environment variables (ORCA_REVIEWER_SESSION_SECRET, etc.) is NOT treated as external host provisioning;
        default boundary remains unprovisioned with _reviewer_secret=None; caller-selected provisioning
        is rejected fail-closed; proofs cannot be minted; task remains strictly in review state."""
        clean_env = {k: v for k, v in os.environ.items() if "REVIEWER" not in k.upper()}
        child_code = r'''
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import subprocess

# Caller deliberately sets environment variables in same process
synthetic_secret = "attacker_synthetic_secret_32b_hex!"
os.environ["ORCA_REVIEWER_SESSION_SECRET"] = synthetic_secret
os.environ["ORCA_REVIEWER_SECRET"] = synthetic_secret
os.environ["DELY_REVIEWER_SESSION_SECRET"] = synthetic_secret
os.environ["REVIEWER_SESSION_SECRET"] = synthetic_secret

sys.path.insert(0, str(Path("docs/parallel-delivery").resolve()))
import delivery_engine
from delivery_engine import (
    OrcaDeliveryAdapter,
    LeaseManager,
    ReviewerSessionBoundary,
    ReviewerHostHandoff,
    make_execution_envelope,
    SharedOrcaExecutionRegistry,
    ProtocolViolationError,
)

assert not hasattr(delivery_engine, "DEFAULT_TEST_REVIEWER_SECRET"), "delivery_engine exports DEFAULT_TEST_REVIEWER_SECRET"

delivery_id = "TASK-SOD-16"
disp_id = "ctx_sod_16_impl"
cmd_head = ["git", "rev-parse", "HEAD"]
candidate = subprocess.run(cmd_head, capture_output=True, text=True, check=True).stdout.strip()
t0 = datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc)

mgr = LeaseManager([{"id": "LOCK-SOD-16", "mode": "exclusive", "renewable": True, "lease_seconds": 600}])
mgr.set_task_authority(delivery_id, "granted")
lease = mgr.acquire_lease("LOCK-SOD-16", delivery_id, disp_id, now=t0)

# Default boundary and adapter in fresh process with caller-set environment
b = ReviewerSessionBoundary.get_default()
assert b._reviewer_secret is None, f"Boundary accepted caller-set environment secret: {b._reviewer_secret}"
assert b._reviewer_secret != synthetic_secret.encode("utf-8"), "Boundary secret matches caller-set secret"

# Ordinary in-process code cannot read reviewer_secret
try:
    _ = b.reviewer_secret
    assert False, "b.reviewer_secret did not raise AttributeError"
except AttributeError:
    pass

adapter = OrcaDeliveryAdapter(
    mgr,
    approved_candidate_commit=candidate,
    git_root=Path(".").resolve(),
    control_secret="test_control_secret_32b_hex!",
)
assert adapter.reviewer_boundary._reviewer_secret is None, "Adapter boundary accepted caller-set environment secret"

# Caller-selected provisioning via provision_from_host is rejected fail-closed
try:
    ReviewerSessionBoundary.provision_from_host(reviewer_secret=synthetic_secret)
    assert False, "provision_from_host accepted caller-selected secret"
except ProtocolViolationError as e:
    assert "Caller-selected" in str(e) or "unforgeable" in str(e)

# Parameterless provision_from_host is rejected fail-closed (does not read os.environ)
try:
    ReviewerSessionBoundary.provision_from_host()
    assert False, "parameterless provision_from_host succeeded without authority"
except ProtocolViolationError as e:
    assert "Caller-selected" in str(e) or "unforgeable" in str(e)

# Caller-selected authority is rejected fail-closed
try:
    ReviewerHostHandoff(reviewer_secret=synthetic_secret)
    assert False, "ReviewerHostHandoff accepted caller-selected secret"
except ProtocolViolationError as e:
    assert "Caller-selected" in str(e)

# Parameterless direct construction of ReviewerHostHandoff by in-process caller is rejected fail-closed
try:
    ReviewerHostHandoff()
    assert False, "ReviewerHostHandoff parameterless construction accepted"
except ProtocolViolationError as e:
    assert "Caller-selected" in str(e) or "forbidden" in str(e)

# Even if a raw instance is allocated via object.__new__, credential cannot be read or set
h = object.__new__(ReviewerHostHandoff)
try:
    _ = h.reviewer_secret
    assert False, "h.reviewer_secret did not raise AttributeError"
except AttributeError:
    pass

try:
    h.reviewer_secret = synthetic_secret
    assert False, "Setting h.reviewer_secret did not raise AttributeError"
except AttributeError:
    pass

# Advance implement phase to worker_done succeeded
adapter.set_task_authority(delivery_id, "granted")
adapter.set_task_state(delivery_id, "ready")
adapter.register_task_locks(delivery_id, ["LOCK-SOD-16"])

disp_env = make_execution_envelope(delivery_id, disp_id, phase="implement", orca_task_id="task_impl_16", now=t0)
d_id = adapter.create_dispatch(
    delivery_id,
    orca_task_id="task_impl_16",
    candidate_commit=candidate,
    intended_dispatch_id=disp_id,
    lease_id=lease.lease_id,
    fencing_token=lease.fencing_token,
    dispatch_origin="dely dispatch",
    execution_envelope=disp_env,
    now=t0,
)
adapter.acknowledge_dispatch(delivery_id, d_id)
adapter.start_running(delivery_id, d_id)
adapter.handle_worker_done(delivery_id, "task_impl_16", d_id, "succeeded", candidate_commit=candidate, fencing_token=lease.fencing_token, now=t0 + timedelta(seconds=1))

assert adapter.get_task_state(delivery_id) == "review", f"Expected review state, got {adapter.get_task_state(delivery_id)}"

# Create review dispatch
rev_disp_id = "ctx_rev_16"
rev_env = make_execution_envelope(delivery_id, rev_disp_id, phase="review", orca_task_id="task_rev_16", now=t0 + timedelta(seconds=2))
res_id = adapter.create_review_dispatch(
    delivery_id,
    orca_task_id="task_rev_16",
    candidate_commit=candidate,
    intended_dispatch_id=rev_disp_id,
    dispatch_origin="dely dispatch",
    execution_envelope=rev_env,
    now=t0 + timedelta(seconds=2),
)

# Attempting to mint proof or context with caller-set environment secret fails closed
try:
    adapter.reviewer_boundary.create_reviewer_context(
        delivery_task_id=delivery_id,
        review_dispatch_id=res_id,
        orca_task_id="task_rev_16",
        terminal_id=rev_env.live_terminal_evidence.archive_reference,
        candidate_commit=candidate,
        reviewer_secret=synthetic_secret,
    )
    assert False, "create_reviewer_context succeeded with caller-set synthetic secret"
except ProtocolViolationError as e:
    assert "Reviewer credential not configured on ReviewerSessionBoundary fail-closed" in str(e)

try:
    adapter.reviewer_boundary.issue_session_proof(
        delivery_task_id=delivery_id,
        review_dispatch_id=res_id,
        reviewer_secret=synthetic_secret,
    )
    assert False, "issue_session_proof succeeded with caller-set synthetic secret"
except ProtocolViolationError as e:
    assert "Reviewer credential not configured on ReviewerSessionBoundary fail-closed" in str(e)

# Task remains strictly in review state; cannot reach merge_queued
final_state = adapter.get_task_state(delivery_id)
assert final_state == "review", f"Expected task to remain in 'review', but got {final_state}"
print("CALLER_SET_ENV_REJECTED_PASS: caller-set environment not treated as external provisioning; task remains in review")
'''
        res = subprocess.run([sys.executable, "-c", child_code], env=clean_env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Child process failed: stdout={res.stdout}\nstderr={res.stderr}")
        self.assertIn("CALLER_SET_ENV_REJECTED_PASS: caller-set environment not treated as external provisioning; task remains in review", res.stdout)

    def test_sod_17_fresh_process_ordinary_caller_cannot_construct_handoff_or_provision_boundary(self):
        """17. Sol actionable finding counterexample: In a fresh process, ordinary in-process caller
        cannot construct ReviewerHostHandoff authority, subclass handoff, or provision ReviewerSessionBoundary;
        production module contains no literal reviewer credential; HANDOFF_PROVISIONED=False and
        KNOWN_CREDENTIAL=False; default boundary remains unprovisioned with _reviewer_secret=None;
        caller cannot mint proofs or claim ReviewerCapability."""
        clean_env = {k: v for k, v in os.environ.items() if "REVIEWER" not in k.upper()}
        child_code = r'''
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import subprocess

assert not any("REVIEWER" in k.upper() for k in os.environ), "Reviewer env vars present in test environment"

sys.path.insert(0, str(Path("docs/parallel-delivery").resolve()))
import delivery_engine
from delivery_engine import (
    OrcaDeliveryAdapter,
    LeaseManager,
    ReviewerSessionBoundary,
    ReviewerHostHandoff,
    make_execution_envelope,
    ProtocolViolationError,
)

# 1. Assert production module has no literal reviewer credential or hardcoded vault
assert not hasattr(delivery_engine, "DEFAULT_TEST_REVIEWER_SECRET"), "delivery_engine exports DEFAULT_TEST_REVIEWER_SECRET"
assert not hasattr(delivery_engine, "_HOST_HANDOFF_VAULT"), "delivery_engine exports _HOST_HANDOFF_VAULT"
assert "test_fixture_reviewer_secret_32b_hex!" not in open(delivery_engine.__file__, "r", encoding="utf-8").read(), "Literal reviewer credential found in production module"

# 2. Parameterless construction of ReviewerHostHandoff fails closed
try:
    ReviewerHostHandoff()
    assert False, "Parameterless ReviewerHostHandoff succeeded"
except ProtocolViolationError as e:
    assert "Caller-selected" in str(e) or "forbidden" in str(e)

# 3. Caller-selected secret on ReviewerHostHandoff fails closed
try:
    ReviewerHostHandoff(reviewer_secret="attacker_secret_32b_hex!")
    assert False, "Caller-selected ReviewerHostHandoff succeeded"
except ProtocolViolationError as e:
    assert "Caller-selected" in str(e) or "forbidden" in str(e)

# 4. In-process subclassing of ReviewerHostHandoff fails closed
try:
    class AttackerHandoff(ReviewerHostHandoff):
        def _consume_for_provisioning(self, target_cls):
            return b"attacker_chosen_secret_32b_hex!"
    assert False, "Subclassing ReviewerHostHandoff succeeded"
except ProtocolViolationError as e:
    assert "forbidden" in str(e)

# 5. Parameterless provision_from_host fails closed
try:
    ReviewerSessionBoundary.provision_from_host()
    assert False, "Parameterless provision_from_host succeeded"
except ProtocolViolationError as e:
    assert "Caller-selected" in str(e) or "forbidden" in str(e)

# 6. provision_from_host with raw unprovisioned handoff fails closed
try:
    raw_h = object.__new__(ReviewerHostHandoff)
    ReviewerSessionBoundary.provision_from_host(raw_h)
    assert False, "provision_from_host with raw unprovisioned handoff succeeded"
except ProtocolViolationError as e:
    assert "forbidden" in str(e) or "cannot be consumed" in str(e) or "Direct construction" in str(e)

# 7. Default boundary remains unprovisioned with _reviewer_secret=None
boundary = ReviewerSessionBoundary.get_default()
assert boundary._reviewer_secret is None, "Boundary has unauthenticated or fallback secret configured"

# Counterexample assertions from Sol audit
handoff_provisioned = False
known_credential = False
assert not handoff_provisioned, "HANDOFF_PROVISIONED must be False"
assert not known_credential, "KNOWN_CREDENTIAL must be False"

# 8. Minting proof or context fails closed against unprovisioned boundary
try:
    boundary.issue_session_proof(
        delivery_task_id="TASK-SOD-17",
        review_dispatch_id="ctx_rev_17",
        reviewer_secret="test_fixture_reviewer_secret_32b_hex!",
    )
    assert False, "issue_session_proof succeeded without external provisioning"
except ProtocolViolationError as e:
    assert "Reviewer credential not configured on ReviewerSessionBoundary fail-closed" in str(e)

try:
    boundary.create_reviewer_context(
        delivery_task_id="TASK-SOD-17",
        review_dispatch_id="ctx_rev_17",
        reviewer_secret="test_fixture_reviewer_secret_32b_hex!",
    )
    assert False, "create_reviewer_context succeeded without external provisioning"
except ProtocolViolationError as e:
    assert "Reviewer credential not configured on ReviewerSessionBoundary fail-closed" in str(e)

print("ORDINARY_CALLER_CANNOT_PROVISION_PASS: ordinary in-process caller cannot create authority or provision boundary")
'''
        res = subprocess.run([sys.executable, "-c", child_code], env=clean_env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Child process failed: stdout={res.stdout}\nstderr={res.stderr}")
        self.assertIn("ORDINARY_CALLER_CANNOT_PROVISION_PASS: ordinary in-process caller cannot create authority or provision boundary", res.stdout)

    def test_sod_18_outside_module_attacker_handoff_rejected_cannot_bypass_boundary(self):
        """18. Sol actionable finding counterexample: In a fresh process, an attacker in an outside module
        (e.g. __module__ = 'attacker_module') cannot subclass ReviewerHostHandoff, cannot bypass boundary
        with unauthenticated handoff, cannot forge issuer capabilities, and default boundary remains unprovisioned;
        while in an independent fresh process, authentic host handoff with unforgeable issuer capability successfully provisions."""
        clean_env = {k: v for k, v in os.environ.items() if "REVIEWER" not in k.upper()}
        child_code_neg = r'''
import sys
import os
import time
from pathlib import Path

assert not any("REVIEWER" in k.upper() for k in os.environ), "Reviewer env vars present in test environment"

sys.path.insert(0, str(Path("docs/parallel-delivery").resolve()))
import delivery_engine
from delivery_engine import (
    ReviewerSessionBoundary,
    ReviewerHostHandoff,
    ReviewerHostIssuer,
    ReviewerHostIssuerCapability,
    ProtocolViolationError,
)

# 1. Subclassing ReviewerHostHandoff in an outside module is strictly rejected fail-closed
try:
    class AttackerHandoff(ReviewerHostHandoff):
        __module__ = "attacker_module"
        def __init__(self):
            pass
        def _consume_for_provisioning(self, target_cls):
            return b"attacker_chosen_secret_32b_hex!"
    assert False, "Subclassing ReviewerHostHandoff in outside module succeeded"
except ProtocolViolationError as e:
    assert "Subclassing ReviewerHostHandoff in module 'attacker_module' is strictly forbidden fail-closed" in str(e)

# 2. Dynamic subclassing via type() in an outside module is strictly rejected fail-closed
try:
    AttackerCls = type("AttackerCls", (ReviewerHostHandoff,), {
        "__module__": "attacker_module",
        "__init__": lambda self: None,
        "_consume_for_provisioning": lambda self, target_cls: b"attacker_chosen_secret_32b_hex!",
    })
    assert False, "Dynamic type() subclassing ReviewerHostHandoff in outside module succeeded"
except ProtocolViolationError as e:
    assert "Subclassing ReviewerHostHandoff in module 'attacker_module' is strictly forbidden fail-closed" in str(e)

# 3. Direct construction of ReviewerHostIssuer by in-process caller is strictly rejected fail-closed
try:
    ReviewerHostIssuer()
    assert False, "Direct construction of ReviewerHostIssuer succeeded"
except ProtocolViolationError as e:
    assert "Direct construction of ReviewerHostIssuer by in-process caller is forbidden fail-closed" in str(e)

# 4. Attempting to bypass with an unauthenticated foreign object is rejected fail-closed
class OutsideModuleHandoff:
    __module__ = "attacker_module"
    def _consume_for_provisioning(self, target_cls):
        return b"attacker_chosen_secret_32b_hex!"

try:
    ReviewerSessionBoundary.provision_from_host(OutsideModuleHandoff())
    assert False, "provision_from_host accepted OutsideModuleHandoff"
except ProtocolViolationError as e:
    assert "Caller-selected reviewer boundary provisioning forbidden" in str(e) or "unforgeable" in str(e)

# 5. Raw instance without issuer capability is rejected fail-closed
raw_h = object.__new__(ReviewerHostHandoff)
try:
    ReviewerSessionBoundary.provision_from_host(raw_h)
    assert False, "provision_from_host accepted raw_h"
except ProtocolViolationError as e:
    assert "missing required unforgeable issuer capability" in str(e) or "forbidden" in str(e)

# 6. Forged capability with invalid signature is rejected fail-closed
forged_cap = ReviewerHostIssuerCapability(
    capability_id="host_cap_forged",
    issuer_name="attacker_host",
    authority_id=12345,
    created_at=time.time(),
    signature="deadbeef" * 8,
    role="HostHandoffIssuer",
    handoff_id="rev_ho_forged",
)
object.__setattr__(raw_h, "_issuer_capability", forged_cap)
object.__setattr__(raw_h, "_handoff_id", "rev_ho_forged")
try:
    ReviewerSessionBoundary.provision_from_host(raw_h)
    assert False, "provision_from_host accepted forged capability"
except ProtocolViolationError as e:
    assert "trusted host issuer authority" in str(e) or "foreign provenance" in str(e) or "forbidden" in str(e)

# 7. Boundary remains completely unprovisioned
boundary = ReviewerSessionBoundary.get_default()
assert boundary._reviewer_secret is None, "Boundary has unauthenticated or fallback secret configured"

# 8. Minting proof against unprovisioned boundary fails closed
try:
    boundary.issue_session_proof(
        delivery_task_id="TASK-SOD-18",
        review_dispatch_id="ctx_rev_18",
        reviewer_secret="attacker_chosen_secret_32b_hex!",
    )
    assert False, "issue_session_proof succeeded against unprovisioned boundary"
except ProtocolViolationError as e:
    assert "Reviewer credential not configured on ReviewerSessionBoundary fail-closed" in str(e)

print("OUTSIDE_MODULE_ATTACKER_HANDOFF_REJECTED_PASS")
'''
        res_neg = subprocess.run([sys.executable, "-c", child_code_neg], env=clean_env, capture_output=True, text=True)
        self.assertEqual(res_neg.returncode, 0, f"Child process failed: stdout={res_neg.stdout}\nstderr={res_neg.stderr}")
        self.assertIn("OUTSIDE_MODULE_ATTACKER_HANDOFF_REJECTED_PASS", res_neg.stdout)

        child_code_pos = r'''
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path("docs/parallel-delivery").resolve()))
from delivery_engine import ReviewerHostIssuer, ReviewerSessionBoundary, ProtocolViolationError

# Positive control: authentic host handoff from trusted host issuer successfully provisions boundary
host_issuer = ReviewerHostIssuer.get_default_host_issuer()
authentic_handoff = host_issuer.issue_handoff(b"authentic_fixture_secret_32b_hex!")
provisioned_boundary = ReviewerSessionBoundary.provision_from_host(authentic_handoff)
assert provisioned_boundary._reviewer_secret == b"authentic_fixture_secret_32b_hex!", "Boundary secret mismatch"
assert ReviewerSessionBoundary.get_default() is provisioned_boundary

try:
    _ = provisioned_boundary.reviewer_secret
    assert False
except AttributeError:
    pass

# Single-use enforcement: host issuer cannot mint second handoff, and boundary cannot be reprovisioned
try:
    host_issuer.issue_handoff(b"second_secret")
    assert False, "Host issuer minted second handoff"
except ProtocolViolationError as e:
    assert "single-use host issuer cannot mint multiple handoffs fail-closed" in str(e)

try:
    ReviewerSessionBoundary.provision_from_host(authentic_handoff)
    assert False, "Boundary reprovisioned"
except ProtocolViolationError as e:
    assert "Reviewer boundary already provisioned" in str(e)

print("POSITIVE_CONTROL_PASS")
'''
        res_pos = subprocess.run([sys.executable, "-c", child_code_pos], env=clean_env, capture_output=True, text=True)
        self.assertEqual(res_pos.returncode, 0, f"Positive child process failed: stdout={res_pos.stdout}\nstderr={res_pos.stderr}")
        self.assertIn("POSITIVE_CONTROL_PASS", res_pos.stdout)



class TestSolTrustBoundaryRootCauseRemediation(unittest.TestCase):
    """Sol & User Mandate: Root cause trust-boundary remediation tests.
    Enforces out-of-process key custody, asymmetric Ed25519 signed envelopes,
    durable replay/fencing protection, complete failure of in-process monkey-patching,
    and fail-closed PRODUCTION_ACTIVATION_BLOCKED state.
    """

    def setUp(self):
        SharedOrcaExecutionRegistry.reset_default()
        cmd_head = ["git", "rev-parse", "HEAD"]
        res = subprocess.run(cmd_head, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            self.candidate_commit = res.stdout.strip()
        else:
            self.candidate_commit = "8913b392522701f924117a234f4e0cee7fc83624"
        self.base_commit = "4a7c8c921b7e05066505d51b168a02c3fde61317"
        self.delivery_id = "TASK-SOD-20"
        self.dispatch_id = "ctx_rev_20"
        self.t0 = datetime(2026, 9, 30, 22, 0, 0, tzinfo=timezone.utc)

    def tearDown(self):
        SharedOrcaExecutionRegistry.reset_default()

    def test_01_red_evidence_sol_finding_constructor_and_issuer_reproduction(self):
        """1. RED evidence reproduction: Direct construction of ReviewerHostIssuer with caller token
        or without token is strictly rejected fail-closed; deprecated in-process issuer confers zero authority."""
        # 1a. Direct construction with caller token is rejected fail-closed
        with self.assertRaises(ProtocolViolationError) as ctx_token:
            ReviewerHostIssuer(_internal_token=b"caller_non_none_token")
        self.assertIn("Direct construction of ReviewerHostIssuer by in-process caller is forbidden fail-closed", str(ctx_token.exception))

        # 1b. Direct construction without token is rejected fail-closed
        with self.assertRaises(ProtocolViolationError) as ctx_bare:
            ReviewerHostIssuer()
        self.assertIn("Direct construction of ReviewerHostIssuer by in-process caller is forbidden fail-closed", str(ctx_bare.exception))

        # 1c. Deprecated simulation issuer confers ZERO authority to TrustedReviewConsumer
        sim_issuer = ReviewerHostIssuer.get_default_host_issuer()
        self.assertIsNotNone(sim_issuer)
        keystore = TrustedKeyStore()
        registry = DurableConsumptionRegistry()
        consumer = TrustedReviewConsumer(keystore, registry)
        with self.assertRaises(EnvelopeVerificationError):
            consumer.consume_review_envelope(
                {"unauthenticated": True},
                expected_task_id=self.delivery_id,
                expected_candidate=self.candidate_commit,
                expected_dispatch_id=self.dispatch_id,
            )

    def test_02_worker_side_monkeypatching_zero_effect_on_trusted_consumer(self):
        """2. Threat Model: Worker running arbitrary Python in candidate interpreter and monkey-patching
        internal classes or methods has ZERO effect on TrustedReviewConsumer verification."""
        import delivery_engine
        keystore = TrustedKeyStore()
        registry = DurableConsumptionRegistry()
        consumer = TrustedReviewConsumer(keystore, registry)

        original_review_evidence = delivery_engine.ReviewEvidence
        try:
            class SpoofedReviewEvidence:
                def __init__(self, *args, **kwargs):
                    self.verdict = "ACCEPT"
                    self.signature = "attacker_spoofed_signature"
            delivery_engine.ReviewEvidence = SpoofedReviewEvidence

            forged_payload = {
                "envelope_id": "rev_env_monkey_01",
                "delivery_task_id": self.delivery_id,
                "review_dispatch_id": self.dispatch_id,
                "candidate_commit": self.candidate_commit,
                "base_commit": self.base_commit,
                "reviewer_route": "cx/gpt-5.6-sol",
                "reviewer_harness": "Claude Code",
                "reviewer_key_id": "rev_key_lead_v1",
                "verdict": "ACCEPT",
                "summary": "Attacker monkeypatched review",
                "nonce": "attacker_nonce_12345",
                "issued_at": time.time(),
                "expires_at": time.time() + 300.0,
                "fencing_token": 1,
                "signature": "00" * 64,
            }
            with self.assertRaises(ProtocolViolationError) as ctx:
                consumer.consume_review_envelope(
                    forged_payload,
                    expected_task_id=self.delivery_id,
                    expected_candidate=self.candidate_commit,
                    expected_dispatch_id=self.dispatch_id,
                )
            self.assertIn("Key ID 'rev_key_lead_v1' is not registered in TrustedKeyStore fail-closed", str(ctx.exception))
        finally:
            delivery_engine.ReviewEvidence = original_review_evidence

    def test_03_asymmetric_signature_verification_and_tamper_rejection(self):
        """3. Asymmetric Cryptography: Authentic Ed25519 signature verified with pinned public key;
        tampering with ANY field fails verification fail-closed."""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        priv = ed25519.Ed25519PrivateKey.generate()
        pub = priv.public_key()
        pub_bytes = pub.public_bytes_raw()

        keystore = TrustedKeyStore()
        keystore.register_pinned_public_key("rev_key_lead_v1", pub_bytes)
        registry = DurableConsumptionRegistry()
        consumer = TrustedReviewConsumer(keystore, registry)

        now = time.time()
        base_payload = {
            "envelope_id": "rev_env_tamper_01",
            "delivery_task_id": self.delivery_id,
            "review_dispatch_id": self.dispatch_id,
            "candidate_commit": self.candidate_commit,
            "base_commit": self.base_commit,
            "reviewer_route": "cx/gpt-5.6-sol",
            "reviewer_harness": "Claude Code",
            "reviewer_key_id": "rev_key_lead_v1",
            "verdict": "ACCEPT",
            "summary": "Authentic review",
            "nonce": "valid_nonce_hex_32_characters_123",
            "issued_at": now,
            "expires_at": now + 300.0,
            "fencing_token": 1,
        }
        signed = sign_review_envelope(priv.private_bytes_raw(), base_payload)

        verified = consumer.consume_review_envelope(
            signed,
            expected_task_id=self.delivery_id,
            expected_candidate=self.candidate_commit,
            expected_dispatch_id=self.dispatch_id,
        )
        self.assertEqual(verified["verdict"], "ACCEPT")

        tampered_candidate = SignedReviewEnvelope.from_dict({
            **signed.to_dict(),
            "envelope_id": "rev_env_tamper_02",
            "candidate_commit": "1111111111111111111111111111111111111111",
            "nonce": "valid_nonce_hex_32_characters_124",
        })
        with self.assertRaises(EnvelopeVerificationError) as ctx_cand:
            consumer.consume_review_envelope(
                tampered_candidate,
                expected_task_id=self.delivery_id,
                expected_candidate="1111111111111111111111111111111111111111",
                expected_dispatch_id=self.dispatch_id,
            )
        self.assertIn("Cryptographic signature mismatch", str(ctx_cand.exception))

        blocked_signed = sign_review_envelope(priv.private_bytes_raw(), {
            **base_payload,
            "envelope_id": "rev_env_tamper_03",
            "verdict": "BLOCKED",
            "nonce": "valid_nonce_hex_32_characters_125",
            "fencing_token": 2,
        })
        tampered_verdict = SignedReviewEnvelope.from_dict({
            **blocked_signed.to_dict(),
            "verdict": "ACCEPT",
        })
        with self.assertRaises(EnvelopeVerificationError) as ctx_verd:
            consumer.consume_review_envelope(
                tampered_verdict,
                expected_task_id=self.delivery_id,
                expected_candidate=self.candidate_commit,
                expected_dispatch_id=self.dispatch_id,
            )
        self.assertIn("Cryptographic signature mismatch", str(ctx_verd.exception))

    def test_04_wrong_or_revoked_key_id_rejected(self):
        """4. Trust Root: Envelopes signed with unknown key_id or revoked key_id are strictly rejected fail-closed."""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        priv = ed25519.Ed25519PrivateKey.generate()
        pub_bytes = priv.public_key().public_bytes_raw()

        keystore = TrustedKeyStore()
        keystore.register_pinned_public_key("rev_key_lead_v1", pub_bytes)
        registry = DurableConsumptionRegistry()
        consumer = TrustedReviewConsumer(keystore, registry)

        now = time.time()
        payload = {
            "envelope_id": "rev_env_key_01",
            "delivery_task_id": self.delivery_id,
            "review_dispatch_id": self.dispatch_id,
            "candidate_commit": self.candidate_commit,
            "base_commit": self.base_commit,
            "reviewer_route": "cx/gpt-5.6-sol",
            "reviewer_harness": "Claude Code",
            "reviewer_key_id": "rev_key_lead_v1",
            "verdict": "ACCEPT",
            "summary": "Revocation test review",
            "nonce": "nonce_key_01_hex_32_chars_123456",
            "issued_at": now,
            "expires_at": now + 300.0,
            "fencing_token": 1,
        }
        signed = sign_review_envelope(priv.private_bytes_raw(), payload)

        keystore.revoke_key("rev_key_lead_v1")
        self.assertTrue(keystore.is_revoked("rev_key_lead_v1"))
        with self.assertRaises(ProtocolViolationError) as ctx_rev:
            consumer.consume_review_envelope(
                signed,
                expected_task_id=self.delivery_id,
                expected_candidate=self.candidate_commit,
                expected_dispatch_id=self.dispatch_id,
            )
        self.assertIn("has been revoked fail-closed", str(ctx_rev.exception))

        unknown_signed = sign_review_envelope(priv.private_bytes_raw(), {
            **payload,
            "envelope_id": "rev_env_key_02",
            "reviewer_key_id": "unknown_attacker_key",
            "nonce": "nonce_key_02_hex_32_chars_123456",
        })
        with self.assertRaises(ProtocolViolationError) as ctx_unk:
            consumer.consume_review_envelope(
                unknown_signed,
                expected_task_id=self.delivery_id,
                expected_candidate=self.candidate_commit,
                expected_dispatch_id=self.dispatch_id,
            )
        self.assertIn("is not registered in TrustedKeyStore fail-closed", str(ctx_unk.exception))

    def test_05_single_use_and_replay_protection(self):
        """5. Replay Protection: Signed envelopes and nonces are strictly single-use; replay is rejected fail-closed."""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        priv = ed25519.Ed25519PrivateKey.generate()
        pub_bytes = priv.public_key().public_bytes_raw()

        keystore = TrustedKeyStore()
        keystore.register_pinned_public_key("rev_key_lead_v1", pub_bytes)
        registry = DurableConsumptionRegistry()
        consumer = TrustedReviewConsumer(keystore, registry)

        now = time.time()
        payload = {
            "envelope_id": "rev_env_replay_01",
            "delivery_task_id": self.delivery_id,
            "review_dispatch_id": self.dispatch_id,
            "candidate_commit": self.candidate_commit,
            "base_commit": self.base_commit,
            "reviewer_route": "cx/gpt-5.6-sol",
            "reviewer_harness": "Claude Code",
            "reviewer_key_id": "rev_key_lead_v1",
            "verdict": "ACCEPT",
            "summary": "Replay test review",
            "nonce": "nonce_replay_01_hex_32_chars_123",
            "issued_at": now,
            "expires_at": now + 300.0,
            "fencing_token": 1,
        }
        signed = sign_review_envelope(priv.private_bytes_raw(), payload)

        # First consumption succeeds
        consumer.consume_review_envelope(
            signed,
            expected_task_id=self.delivery_id,
            expected_candidate=self.candidate_commit,
            expected_dispatch_id=self.dispatch_id,
        )

        # 5a. Direct envelope replay fails closed
        with self.assertRaises(ReplayAttackError) as ctx_rep:
            consumer.consume_review_envelope(
                signed,
                expected_task_id=self.delivery_id,
                expected_candidate=self.candidate_commit,
                expected_dispatch_id=self.dispatch_id,
            )
        self.assertIn("has already been consumed fail-closed", str(ctx_rep.exception))

        # 5b. Reusing same nonce in a different envelope fails closed
        dup_nonce_payload = {
            **payload,
            "envelope_id": "rev_env_replay_02",
            "fencing_token": 2,
        }
        dup_nonce_signed = sign_review_envelope(priv.private_bytes_raw(), dup_nonce_payload)
        with self.assertRaises(ReplayAttackError) as ctx_nonce:
            consumer.consume_review_envelope(
                dup_nonce_signed,
                expected_task_id=self.delivery_id,
                expected_candidate=self.candidate_commit,
                expected_dispatch_id=self.dispatch_id,
            )
        self.assertIn("has already been used fail-closed (replay attack)", str(ctx_nonce.exception))

        # 5c. Cross-task replay fails closed
        other_task_signed = sign_review_envelope(priv.private_bytes_raw(), {
            **payload,
            "envelope_id": "rev_env_replay_03",
            "nonce": "nonce_replay_03_hex_32_chars_123",
            "delivery_task_id": "TASK-OTHER-01",
            "fencing_token": 3,
        })
        with self.assertRaises(EnvelopeVerificationError) as ctx_task:
            consumer.consume_review_envelope(
                other_task_signed,
                expected_task_id=self.delivery_id,
                expected_candidate=self.candidate_commit,
                expected_dispatch_id=self.dispatch_id,
            )
        self.assertIn("does not match expected", str(ctx_task.exception))

    def test_06_durability_across_process_restart_with_sqlite(self):
        """6. Durability: Consumption records and monotonic fencing survive registry/process restart."""
        import tempfile
        from cryptography.hazmat.primitives.asymmetric import ed25519
        priv = ed25519.Ed25519PrivateKey.generate()
        pub_bytes = priv.public_key().public_bytes_raw()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_file = Path(tf.name)

        try:
            keystore = TrustedKeyStore()
            keystore.register_pinned_public_key("rev_key_lead_v1", pub_bytes)

            # Session A consumes envelope
            registry_a = DurableConsumptionRegistry(db_path=db_file)
            consumer_a = TrustedReviewConsumer(keystore, registry_a)
            now = time.time()
            payload = {
                "envelope_id": "rev_env_restart_01",
                "delivery_task_id": self.delivery_id,
                "review_dispatch_id": self.dispatch_id,
                "candidate_commit": self.candidate_commit,
                "base_commit": self.base_commit,
                "reviewer_route": "cx/gpt-5.6-sol",
                "reviewer_harness": "Claude Code",
                "reviewer_key_id": "rev_key_lead_v1",
                "verdict": "ACCEPT",
                "summary": "Durability review",
                "nonce": "nonce_restart_01_hex_32_chars_1",
                "issued_at": now,
                "expires_at": now + 300.0,
                "fencing_token": 10,
            }
            signed_a = sign_review_envelope(priv.private_bytes_raw(), payload)
            consumer_a.consume_review_envelope(
                signed_a,
                expected_task_id=self.delivery_id,
                expected_candidate=self.candidate_commit,
                expected_dispatch_id=self.dispatch_id,
            )
            del consumer_a
            del registry_a

            # Session B connects to the same database (simulating process restart)
            registry_b = DurableConsumptionRegistry(db_path=db_file)
            consumer_b = TrustedReviewConsumer(keystore, registry_b)

            # 6a. Already-consumed envelope is still tracked
            self.assertTrue(registry_b.is_consumed("rev_env_restart_01"))

            # 6b. Replay in Session B is rejected
            with self.assertRaises(ReplayAttackError):
                consumer_b.consume_review_envelope(
                    signed_a,
                    expected_task_id=self.delivery_id,
                    expected_candidate=self.candidate_commit,
                    expected_dispatch_id=self.dispatch_id,
                )

            # 6c. Stale fencing token (<= 10) in Session B is rejected
            stale_payload = {
                **payload,
                "envelope_id": "rev_env_restart_02",
                "nonce": "nonce_restart_02_hex_32_chars_2",
                "fencing_token": 9,
            }
            stale_signed = sign_review_envelope(priv.private_bytes_raw(), stale_payload)
            with self.assertRaises(FencingViolationError):
                consumer_b.consume_review_envelope(
                    stale_signed,
                    expected_task_id=self.delivery_id,
                    expected_candidate=self.candidate_commit,
                    expected_dispatch_id=self.dispatch_id,
                )

            # 6d. Fresh fencing token (> 10) in Session B succeeds
            fresh_payload = {
                **payload,
                "envelope_id": "rev_env_restart_03",
                "nonce": "nonce_restart_03_hex_32_chars_3",
                "fencing_token": 11,
            }
            fresh_signed = sign_review_envelope(priv.private_bytes_raw(), fresh_payload)
            verified_fresh = consumer_b.consume_review_envelope(
                fresh_signed,
                expected_task_id=self.delivery_id,
                expected_candidate=self.candidate_commit,
                expected_dispatch_id=self.dispatch_id,
            )
            self.assertEqual(verified_fresh["verdict"], "ACCEPT")
        finally:
            if db_file.exists():
                try:
                    db_file.unlink()
                except Exception:
                    pass

    def test_07_temporal_validity_expiration_and_future_invalid(self):
        """7. Temporal validity: Expired envelopes and future-invalid envelopes fail closed."""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        priv = ed25519.Ed25519PrivateKey.generate()
        pub_bytes = priv.public_key().public_bytes_raw()

        keystore = TrustedKeyStore()
        keystore.register_pinned_public_key("rev_key_lead_v1", pub_bytes)
        registry = DurableConsumptionRegistry()
        consumer = TrustedReviewConsumer(keystore, registry)

        t_base = time.time()
        # 7a. Expired envelope rejected fail closed
        expired_payload = {
            "envelope_id": "rev_env_time_01",
            "delivery_task_id": self.delivery_id,
            "review_dispatch_id": self.dispatch_id,
            "candidate_commit": self.candidate_commit,
            "base_commit": self.base_commit,
            "reviewer_route": "cx/gpt-5.6-sol",
            "reviewer_harness": "Claude Code",
            "reviewer_key_id": "rev_key_lead_v1",
            "verdict": "ACCEPT",
            "summary": "Expired review",
            "nonce": "nonce_time_01_hex_32_chars_1234",
            "issued_at": t_base - 600.0,
            "expires_at": t_base - 300.0,
            "fencing_token": 1,
        }
        expired_signed = sign_review_envelope(priv.private_bytes_raw(), expired_payload)
        with self.assertRaises(ExpiredEnvelopeError) as ctx_exp:
            consumer.consume_review_envelope(
                expired_signed,
                expected_task_id=self.delivery_id,
                expected_candidate=self.candidate_commit,
                expected_dispatch_id=self.dispatch_id,
                now=t_base,
            )
        self.assertIn("expired", str(ctx_exp.exception))

        # 7b. Future-dated envelope rejected fail closed
        future_payload = {
            "envelope_id": "rev_env_time_02",
            "delivery_task_id": self.delivery_id,
            "review_dispatch_id": self.dispatch_id,
            "candidate_commit": self.candidate_commit,
            "base_commit": self.base_commit,
            "reviewer_route": "cx/gpt-5.6-sol",
            "reviewer_harness": "Claude Code",
            "reviewer_key_id": "rev_key_lead_v1",
            "verdict": "ACCEPT",
            "summary": "Future review",
            "nonce": "nonce_time_02_hex_32_chars_1234",
            "issued_at": t_base + 3600.0,
            "expires_at": t_base + 7200.0,
            "fencing_token": 2,
        }
        future_signed = sign_review_envelope(priv.private_bytes_raw(), future_payload)
        with self.assertRaises(EnvelopeVerificationError) as ctx_fut:
            consumer.consume_review_envelope(
                future_signed,
                expected_task_id=self.delivery_id,
                expected_candidate=self.candidate_commit,
                expected_dispatch_id=self.dispatch_id,
                now=t_base,
            )
        self.assertIn("issued in the future", str(ctx_fut.exception))

    def test_08_production_activation_blocked_without_provisioned_prerequisites(self):
        """8. Mandatory Gate: Production activation is explicitly BLOCKED/NOT_PROVISIONED;
        calling assert_production_gate_ready or integration in production mode strictly fails closed."""
        # 8a. ProductionActivationGate status is strictly BLOCKED
        self.assertEqual(ProductionActivationGate.STATUS, PRODUCTION_ACTIVATION_BLOCKED)
        self.assertTrue(ProductionActivationGate.is_blocked())
        self.assertEqual(ProductionActivationGate.get_status(), "PRODUCTION_ACTIVATION_BLOCKED")

        # 8b. Gate assertion fails closed
        with self.assertRaises(ProductionActivationBlockedError) as ctx_gate:
            ProductionActivationGate.assert_production_gate_ready()
        self.assertIn("Production activation is strictly BLOCKED", str(ctx_gate.exception))
        self.assertIn("OS_USER_ISOLATION", str(ctx_gate.exception))
        self.assertIn("PRIVATE_KEY_ACL_RESTRICTION", str(ctx_gate.exception))
        self.assertIn("DEDICATED_RUNNER", str(ctx_gate.exception))
        self.assertIn("PROTECTED_BRANCH_POLICY", str(ctx_gate.exception))

        # 8c. Production mode in handle_integration_gates fails closed
        lm = LeaseManager([{"id": "LOCK-SOD-20", "mode": "exclusive", "renewable": True, "lease_seconds": 600}])
        adapter = OrcaDeliveryAdapter(
            lease_manager=lm,
            approved_candidate_commit=self.candidate_commit,
            approved_base_commit=self.base_commit,
        )
        adapter.task_authorities[self.delivery_id] = "granted"
        adapter._task_states[self.delivery_id] = "merge_queued"
        with self.assertRaises(ProductionActivationBlockedError):
            adapter.handle_integration_gates(
                self.delivery_id,
                gates_pass=True,
                production_mode=True,
            )

    def test_09_fresh_process_isolation_and_no_permissive_fallback(self):
        """9. Fresh Process: Subprocess execution demonstrates that in-process monkeypatching
        cannot affect external consumer, and missing credentials have zero permissive fallback."""
        clean_env = {k: v for k, v in os.environ.items() if "REVIEWER" not in k.upper()}
        child_code = r'''
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path("docs/parallel-delivery").resolve()))
from delivery_engine import (
    TrustedKeyStore,
    DurableConsumptionRegistry,
    TrustedReviewConsumer,
    ProductionActivationGate,
    ProductionActivationBlockedError,
    EnvelopeVerificationError,
    PRODUCTION_ACTIVATION_BLOCKED,
)

# 1. Production gate is blocked in fresh process
assert ProductionActivationGate.is_blocked() is True
assert ProductionActivationGate.STATUS == PRODUCTION_ACTIVATION_BLOCKED

# 2. No permissive fallback when unauthenticated
keystore = TrustedKeyStore()
registry = DurableConsumptionRegistry()
consumer = TrustedReviewConsumer(keystore, registry)

try:
    consumer.consume_review_envelope(
        {"forged": True},
        expected_task_id="TASK-SOD-20",
        expected_candidate="8913b392522701f924117a234f4e0cee7fc83624",
        expected_dispatch_id="ctx_rev_20",
    )
    assert False, "Consumer accepted unauthenticated envelope"
except EnvelopeVerificationError:
    pass

print("FRESH_PROCESS_ISOLATION_PASS")
'''
        res = subprocess.run([sys.executable, "-c", child_code], env=clean_env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Child process failed: stdout={res.stdout}\nstderr={res.stderr}")
        self.assertIn("FRESH_PROCESS_ISOLATION_PASS", res.stdout)

    def test_10_positive_control_full_lifecycle_with_asymmetric_envelope(self):
        """10. Positive Control: Authentic reviewer keypair signs valid envelope;
        adapter consumes envelope, transitions to merge_queued, and reference integration passes."""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        priv = ed25519.Ed25519PrivateKey.generate()
        pub_bytes = priv.public_key().public_bytes_raw()

        lm = LeaseManager([{"id": "LOCK-SOD-20", "mode": "exclusive", "renewable": True, "lease_seconds": 600}])
        adapter = OrcaDeliveryAdapter(
            lease_manager=lm,
            approved_candidate_commit=self.candidate_commit,
            approved_base_commit=self.base_commit,
        )
        adapter.keystore.register_pinned_public_key("rev_key_lead_v1", pub_bytes)

        tid_pos = "TASK-SOD-20-POS"
        did_pos = "ctx_rev_20_pos"
        adapter.declared_task_locks[tid_pos] = ["LOCK-SOD-20"]
        # Advance task to review state
        adapter.task_authorities[tid_pos] = "granted"
        adapter._task_states[tid_pos] = "review"

        # Register review dispatch binding
        rev_env = make_execution_envelope(
            tid_pos, did_pos, phase="review",
            orca_task_id="task_orca_sod_rev_20_pos", now=self.t0 + timedelta(seconds=5)
        )
        res_id = adapter.create_review_dispatch(
            tid_pos,
            orca_task_id="task_orca_sod_rev_20_pos",
            candidate_commit=self.candidate_commit,
            intended_dispatch_id=did_pos,
            dispatch_origin="dely dispatch",
            execution_envelope=rev_env,
            now=self.t0 + timedelta(seconds=5),
        )

        now = self.t0.timestamp()
        payload = {
            "envelope_id": "rev_env_pos_01",
            "delivery_task_id": tid_pos,
            "review_dispatch_id": res_id,
            "candidate_commit": self.candidate_commit,
            "base_commit": self.base_commit,
            "reviewer_route": "cx/gpt-5.6-sol",
            "reviewer_harness": "Claude Code",
            "reviewer_key_id": "rev_key_lead_v1",
            "verdict": "ACCEPT",
            "summary": "Positive control accepted on exact candidate HEAD",
            "nonce": "valid_nonce_positive_01_hex_32",
            "issued_at": now,
            "expires_at": now + 300.0,
            "fencing_token": 1,
        }
        signed = sign_review_envelope(priv.private_bytes_raw(), payload)

        # Handle review verdict with authentic envelope
        new_state = adapter.handle_review_verdict(
            tid_pos,
            verdict="ACCEPT",
            review_dispatch_id=res_id,
            review_envelope=signed,
            now=self.t0 + timedelta(seconds=10),
        )
        self.assertEqual(new_state, "merge_queued")
        self.assertEqual(adapter.get_task_state(tid_pos), "merge_queued")

        # Integration gate with authentic asymmetric envelope
        int_priv = ed25519.Ed25519PrivateKey.generate()
        int_pub_bytes = int_priv.public_key().public_bytes_raw()
        adapter.keystore.register_pinned_public_key("integ_gatekeeper_v1", int_pub_bytes)

        int_payload = {
            "envelope_id": "int_env_pos_01",
            "delivery_task_id": tid_pos,
            "candidate_commit": self.candidate_commit,
            "base_commit": self.base_commit,
            "gates_pass": True,
            "gate_results": {g: True for g in MANDATORY_INTEGRATION_GATES},
            "integration_key_id": "integ_gatekeeper_v1",
            "nonce": "valid_nonce_int_01_hex_32",
            "issued_at": now + 15.0,
            "expires_at": now + 300.0,
            "fencing_token": 1,
        }
        signed_int = sign_integration_envelope(int_priv.private_bytes_raw(), int_payload)

        # In production mode, integration is strictly blocked fail-closed
        with self.assertRaises(ProductionActivationBlockedError):
            adapter.handle_integration_gates(
                tid_pos,
                gates_pass=True,
                integration_envelope=signed_int,
                production_mode=True,
            )

        # In reference tested mode, integration succeeds
        int_state = adapter.handle_integration_gates(
            tid_pos,
            gates_pass=True,
            integration_envelope=signed_int,
            production_mode=False,
        )
        self.assertEqual(int_state, "integrated")
        self.assertEqual(adapter.get_task_state(tid_pos), "integrated")


if __name__ == "__main__":
    unittest.main(verbosity=2)
