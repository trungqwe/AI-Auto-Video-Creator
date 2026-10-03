"""Behavioral tests for CT-CAP-003 CapabilityView projection (TASK-CAP-J-P2).

Verifies:
1. Schema conformity: required fields, non-secret leakage, redaction, non-aliasing.
2. Deterministic status classification: available, degraded, unavailable, unknown (fail-closed).
3. Recalculated non-negative finite capacity indicators: limit, used, remaining, utilization, confidence.
4. Latest projection across scopes: newest observed_at, sequence tie-breaker, input immutability.
5. Defensive edge cases: malformed objects, throwing exceptions, nested secret injections.
6. Counterexamples for Finding CT-CAP-003:
   - limit=0 or missing limit cannot be available; capacity limit must be present, finite, and > 0.
   - health missing, malformed, or not in contract must not default to healthy/available; fail-closed.
   - latest observation selection: malformed/missing timestamp cannot beat valid observation; deterministic sequence tie-breaker.
"""
from __future__ import annotations

import copy
import math
import unittest
from typing import Any

from src.controlplane.config.capability_view import (
    CapabilityView,
    CapacityIndicator,
    build_capability_view,
    project_capability_views,
    project_latest_capability_views,
)


class ThrowingStringObject:
    """Object that raises an exception when str() or repr() is called."""

    def __str__(self) -> str:
        raise RuntimeError("secret-crash-string-attempt")

    def __repr__(self) -> str:
        raise RuntimeError("secret-crash-repr-attempt")


class SecretRawCredentialObject:
    """Object that defines raw_secret attribute to test boundary protection."""

    def __init__(self, raw: str = "sk-raw-secret-12345") -> None:
        self.raw_secret = raw


class TestCapabilityView(unittest.TestCase):
    """Behavioral test suite for Module J CapabilityView projection (CT-CAP-003)."""

    def setUp(self) -> None:
        self.valid_obs: dict[str, Any] = {
            "capability_id": "cap-gemini-pro-us-01",
            "capability_type": "llm_generation",
            "location": "cloud",
            "provider": "google",
            "account_scope": "account-proj-123",
            "status": "available",
            "health": "healthy",
            "compatible_versions": ["gemini-1.5-pro", "gemini-1.5-flash"],
            "limit": 1000.0,
            "used": 250.0,
            "confidence": "observed",
            "last_observed_at": "2026-10-04T00:00:00Z",
            "expires_at": "2026-10-04T01:00:00Z",
            "reason": None,
            "next_check_at": "2026-10-04T00:05:00Z",
        }

    def test_build_view_schema_and_redaction(self) -> None:
        """Instrument 1: CapabilityView conforms to CT-CAP-003 without secret leakage.

        Verifies:
        - View contains all required schema attributes and mapping keys:
          capability_id, capability_type, location, provider, account_scope,
          status, compatible_versions, capacity, last_observed_at, expires_at,
          reason, next_check_at.
        - Status is strictly one of {"available", "degraded", "unavailable", "unknown"}.
        - Capacity indicator has limit, used, remaining, utilization, confidence.
        - Secret-like keys and values are completely redacted or excluded.
        - Source observation is not mutated or aliased.
        """
        raw_obs = copy.deepcopy(self.valid_obs)
        raw_obs["api_key"] = "AIzaSySecretApiKey12345"
        raw_obs["client_secret"] = "top-secret-client-token"
        raw_obs["bearer"] = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        raw_obs["password"] = "p@ssword_should_never_leak"
        raw_obs["private_key"] = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
        raw_obs["nested_meta"] = {
            "credential_id": "cred-99",
            "auth_token": "sk-live-secret-token-nested",
            "safe_metric": "ok_value",
            "raw_obj": SecretRawCredentialObject(),
        }

        obs_copy = copy.deepcopy(raw_obs)
        view = build_capability_view(raw_obs)

        # 1. Source observation immutability
        self.assertEqual(raw_obs["capability_id"], obs_copy["capability_id"])
        self.assertEqual(raw_obs["api_key"], obs_copy["api_key"])

        # 2. Schema fields existence and typing
        self.assertEqual(view.capability_id, "cap-gemini-pro-us-01")
        self.assertEqual(view.capability_type, "llm_generation")
        self.assertEqual(view.location, "cloud")
        self.assertEqual(view.provider, "google")
        self.assertEqual(view.account_scope, "account-proj-123")
        self.assertIn(view.status, {"available", "degraded", "unavailable", "unknown"})
        self.assertEqual(view.status, "available")
        self.assertEqual(list(view.compatible_versions), ["gemini-1.5-pro", "gemini-1.5-flash"])
        self.assertEqual(view.last_observed_at, "2026-10-04T00:00:00Z")
        self.assertEqual(view.expires_at, "2026-10-04T01:00:00Z")
        self.assertEqual(view.next_check_at, "2026-10-04T00:05:00Z")

        # 3. Capacity indicator recalculation
        self.assertEqual(view.capacity.limit, 1000.0)
        self.assertEqual(view.capacity.used, 250.0)
        self.assertEqual(view.capacity.remaining, 750.0)
        self.assertAlmostEqual(view.capacity.utilization, 0.25, places=5)
        self.assertEqual(view.capacity.confidence, "observed")

        # 4. Dict representation and Mapping interface
        d = view.to_dict()
        required_keys = {
            "capability_id",
            "capability_type",
            "location",
            "provider",
            "account_scope",
            "status",
            "compatible_versions",
            "capacity",
            "last_observed_at",
            "expires_at",
            "reason",
            "next_check_at",
        }
        self.assertTrue(required_keys.issubset(set(d.keys())))
        for k in required_keys:
            self.assertEqual(view[k], d[k])

        # 5. Secret leakage prevention
        view_str = str(view)
        view_repr = repr(view)
        dict_str = str(d)
        for secret_val in [
            "AIzaSySecretApiKey12345",
            "top-secret-client-token",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "p@ssword_should_never_leak",
            "sk-live-secret-token-nested",
            "BEGIN RSA PRIVATE KEY",
            "sk-raw-secret-12345",
        ]:
            self.assertNotIn(secret_val, view_str)
            self.assertNotIn(secret_val, view_repr)
            self.assertNotIn(secret_val, dict_str)

        for secret_key in ["api_key", "client_secret", "bearer", "password", "private_key", "auth_token"]:
            self.assertNotIn(secret_key, d)

    def test_status_classification_fail_closed(self) -> None:
        """Instrument 2: Status classification is deterministic and fail-closed.

        Transitions:
        - Valid, remaining > 0, health good -> available
        - Capacity exhausted (used >= limit or remaining == 0) -> unavailable
        - Health unavailable/revoked/invalid -> unavailable
        - Health degraded, high latency, quota uncertain, or backoff active -> degraded
        - Missing identity, missing/corrupt timestamp, invalid numeric data -> unknown with fail-closed reason.
        """
        # Case A: available
        v_avail = build_capability_view(self.valid_obs)
        self.assertEqual(v_avail.status, "available")

        # Case B: exhausted capacity -> unavailable
        obs_exhausted = copy.deepcopy(self.valid_obs)
        obs_exhausted["limit"] = 500.0
        obs_exhausted["used"] = 500.0
        v_exh = build_capability_view(obs_exhausted)
        self.assertEqual(v_exh.status, "unavailable")
        self.assertIsNotNone(v_exh.reason)
        self.assertIn("exhausted", str(v_exh.reason).lower())

        obs_over_limit = copy.deepcopy(self.valid_obs)
        obs_over_limit["limit"] = 100.0
        obs_over_limit["used"] = 150.0
        v_over = build_capability_view(obs_over_limit)
        self.assertEqual(v_over.status, "unavailable")

        # Case C: health unavailable / revoked / invalid -> unavailable
        for h in ["unavailable", "revoked", "invalid", "unhealthy", "offline", "down"]:
            obs_down = copy.deepcopy(self.valid_obs)
            obs_down["health"] = h
            v_down = build_capability_view(obs_down)
            self.assertEqual(v_down.status, "unavailable", f"Health {h} should yield unavailable")
            self.assertIsNotNone(v_down.reason)

        # Case D: degraded / uncertain / backoff -> degraded
        obs_deg = copy.deepcopy(self.valid_obs)
        obs_deg["health"] = "degraded"
        v_deg = build_capability_view(obs_deg)
        self.assertEqual(v_deg.status, "degraded")

        obs_uncertain = copy.deepcopy(self.valid_obs)
        obs_uncertain["confidence"] = "uncertain"
        v_unc = build_capability_view(obs_uncertain)
        self.assertEqual(v_unc.status, "degraded")

        obs_backoff = copy.deepcopy(self.valid_obs)
        obs_backoff["backoff_active"] = True
        v_backoff = build_capability_view(obs_backoff)
        self.assertEqual(v_backoff.status, "degraded")

        # Case E: fail-closed unknown on missing identity
        for missing_field in ["provider", "account_scope", "capability_type"]:
            obs_bad = copy.deepcopy(self.valid_obs)
            obs_bad[missing_field] = ""
            v_bad = build_capability_view(obs_bad)
            self.assertEqual(v_bad.status, "unknown")
            self.assertIsNotNone(v_bad.reason)
            self.assertNotEqual(v_bad.reason, "")

        for placeholder in ["unknown", "default", "system"]:
            obs_place = copy.deepcopy(self.valid_obs)
            obs_place["provider"] = placeholder
            v_place = build_capability_view(obs_place)
            self.assertEqual(v_place.status, "unknown")
            self.assertIsNotNone(v_place.reason)

        # Case F: fail-closed unknown on invalid numeric data
        for bad_num in [-1.0, math.nan, math.inf, -math.inf, "invalid_num", True, False]:
            obs_num = copy.deepcopy(self.valid_obs)
            obs_num["limit"] = bad_num
            v_num = build_capability_view(obs_num)
            self.assertEqual(v_num.status, "unknown", f"Bad limit {bad_num} must yield unknown")
            self.assertIsNotNone(v_num.reason)

        # Case G: fail-closed unknown on missing or invalid timestamp
        for bad_time in [None, "", "not-a-timestamp"]:
            obs_time = copy.deepcopy(self.valid_obs)
            obs_time["last_observed_at"] = bad_time
            obs_time.pop("observed_at", None)
            v_time = build_capability_view(obs_time)
            self.assertEqual(v_time.status, "unknown", f"Bad timestamp {bad_time} must yield unknown")
            self.assertIsNotNone(v_time.reason)

    def test_counterexample_capacity_limit_fail_closed(self) -> None:
        """Finding CT-CAP-003 (1): limit=0 or missing limit cannot be available.

        Capacity limit must be present, finite, and positive (> 0) when status is available.
        """
        # 1. limit=0 cannot be available -> must be unavailable
        obs_zero = copy.deepcopy(self.valid_obs)
        obs_zero["limit"] = 0.0
        obs_zero["used"] = 0.0
        v_zero = build_capability_view(obs_zero)
        self.assertNotEqual(v_zero.status, "available")
        self.assertEqual(v_zero.status, "unavailable")
        self.assertIsNotNone(v_zero.reason)
        self.assertTrue(
            "limit is zero" in v_zero.reason.lower() or "exhausted" in v_zero.reason.lower()
        )

        # 2. missing limit cannot be available -> must be unknown
        obs_no_limit = copy.deepcopy(self.valid_obs)
        del obs_no_limit["limit"]
        v_no_limit = build_capability_view(obs_no_limit)
        self.assertNotEqual(v_no_limit.status, "available")
        self.assertEqual(v_no_limit.status, "unknown")
        self.assertIn("limit", v_no_limit.reason)

        obs_none_limit = copy.deepcopy(self.valid_obs)
        obs_none_limit["limit"] = None
        v_none_limit = build_capability_view(obs_none_limit)
        self.assertNotEqual(v_none_limit.status, "available")
        self.assertEqual(v_none_limit.status, "unknown")

        # 3. Available view guarantees present, finite, and positive limit
        v_avail = build_capability_view(self.valid_obs)
        self.assertEqual(v_avail.status, "available")
        self.assertIsNotNone(v_avail.capacity.limit)
        self.assertTrue(math.isfinite(v_avail.capacity.limit))
        self.assertGreater(v_avail.capacity.limit, 0.0)
        self.assertGreater(v_avail.capacity.remaining, 0.0)

    def test_counterexample_health_fail_closed(self) -> None:
        """Finding CT-CAP-003 (2): health missing, malformed, or not in contract must not default to healthy/available.

        Must classify fail-closed (unknown or unavailable per contract) with clear reason.
        """
        # 1. Missing health cannot default to healthy/available -> unknown
        obs_no_health = copy.deepcopy(self.valid_obs)
        del obs_no_health["health"]
        v_no_health = build_capability_view(obs_no_health)
        self.assertNotEqual(v_no_health.status, "available")
        self.assertEqual(v_no_health.status, "unknown")
        self.assertIn("health", v_no_health.reason.lower())

        obs_none_health = copy.deepcopy(self.valid_obs)
        obs_none_health["health"] = None
        v_none_health = build_capability_view(obs_none_health)
        self.assertEqual(v_none_health.status, "unknown")

        obs_empty_health = copy.deepcopy(self.valid_obs)
        obs_empty_health["health"] = "   "
        v_empty_health = build_capability_view(obs_empty_health)
        self.assertEqual(v_empty_health.status, "unknown")

        # 2. Malformed health (boolean, numeric, dict, list) -> unknown
        for bad_health in [True, False, 12345, 0.5, {"status": "ok"}, ["healthy"]]:
            obs_bad = copy.deepcopy(self.valid_obs)
            obs_bad["health"] = bad_health
            v_bad = build_capability_view(obs_bad)
            self.assertNotEqual(v_bad.status, "available")
            self.assertEqual(v_bad.status, "unknown", f"Health {bad_health!r} must fail-closed to unknown")
            self.assertIn("health", v_bad.reason.lower())

        # 3. Unrecognized health value not in contract -> unknown
        for unknown_health in ["super_fine", "unknown_custom_state", "all_good", "perfect"]:
            obs_unrec = copy.deepcopy(self.valid_obs)
            obs_unrec["health"] = unknown_health
            v_unrec = build_capability_view(obs_unrec)
            self.assertNotEqual(v_unrec.status, "available")
            self.assertEqual(v_unrec.status, "unknown")
            self.assertIn("unrecognized health value", v_unrec.reason)

        # 4. Explicit 'unknown' health -> unknown
        obs_explicit_unknown = copy.deepcopy(self.valid_obs)
        obs_explicit_unknown["health"] = "unknown"
        v_explicit_unknown = build_capability_view(obs_explicit_unknown)
        self.assertEqual(v_explicit_unknown.status, "unknown")

        # 5. Contract healthy values -> available (when capacity is positive)
        for h_val in ["healthy", "ok", "up", "available"]:
            obs_h = copy.deepcopy(self.valid_obs)
            obs_h["health"] = h_val
            v_h = build_capability_view(obs_h)
            self.assertEqual(v_h.status, "available", f"Health {h_val} should yield available")

        # 6. Contract degraded values -> degraded
        for d_val in ["degraded", "warning", "slow", "high_latency", "elevated_error"]:
            obs_d = copy.deepcopy(self.valid_obs)
            obs_d["health"] = d_val
            v_d = build_capability_view(obs_d)
            self.assertEqual(v_d.status, "degraded")

        # 7. Contract unavailable values -> unavailable
        for u_val in ["unavailable", "revoked", "invalid", "unhealthy", "offline", "down"]:
            obs_u = copy.deepcopy(self.valid_obs)
            obs_u["health"] = u_val
            v_u = build_capability_view(obs_u)
            self.assertEqual(v_u.status, "unavailable")

    def test_counterexample_latest_projection_timestamp_and_sequence_fail_closed(self) -> None:
        """Finding CT-CAP-003 (3): latest projection timestamp and sequence tie-breaking rules.

        - Timestamp malformed or missing CANNOT win over a valid observation (even with higher sequence).
        - Sequence tie-breaker is deterministic and fail-closed.
        """
        obs_valid = copy.deepcopy(self.valid_obs)
        obs_valid["capability_id"] = "cap-scope-test"
        obs_valid["last_observed_at"] = "2026-10-04T00:00:00Z"
        obs_valid["sequence"] = 1
        obs_valid["used"] = 100.0

        obs_malformed_ts = copy.deepcopy(self.valid_obs)
        obs_malformed_ts["capability_id"] = "cap-scope-test"
        obs_malformed_ts["last_observed_at"] = "corrupt-non-iso-timestamp"
        obs_malformed_ts["sequence"] = 999999
        obs_malformed_ts["used"] = 900.0

        obs_missing_ts = copy.deepcopy(self.valid_obs)
        obs_missing_ts["capability_id"] = "cap-scope-test"
        obs_missing_ts["last_observed_at"] = None
        obs_missing_ts["sequence"] = 888888
        obs_missing_ts["used"] = 800.0

        # Permutation 1: [malformed, valid] -> valid must win
        res1 = project_latest_capability_views([obs_malformed_ts, obs_valid])
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0].last_observed_at, "2026-10-04T00:00:00Z")
        self.assertEqual(res1[0].capacity.used, 100.0)

        # Permutation 2: [valid, malformed] -> valid must stay
        res2 = project_latest_capability_views([obs_valid, obs_malformed_ts])
        self.assertEqual(len(res2), 1)
        self.assertEqual(res2[0].last_observed_at, "2026-10-04T00:00:00Z")
        self.assertEqual(res2[0].capacity.used, 100.0)

        # Permutation 3: [missing, valid] -> valid must win
        res3 = project_latest_capability_views([obs_missing_ts, obs_valid])
        self.assertEqual(res3[0].capacity.used, 100.0)

        # Permutation 4: [valid, missing] -> valid must stay
        res4 = project_latest_capability_views([obs_valid, obs_missing_ts])
        self.assertEqual(res4[0].capacity.used, 100.0)

        # Equal timestamp sequence tie-breaker:
        obs_seq1 = copy.deepcopy(self.valid_obs)
        obs_seq1["capability_id"] = "cap-seq-test"
        obs_seq1["last_observed_at"] = "2026-10-04T00:05:00Z"
        obs_seq1["sequence"] = 5
        obs_seq1["used"] = 50.0

        obs_seq2 = copy.deepcopy(self.valid_obs)
        obs_seq2["capability_id"] = "cap-seq-test"
        obs_seq2["last_observed_at"] = "2026-10-04T00:05:00Z"
        obs_seq2["sequence"] = 10
        obs_seq2["used"] = 70.0

        res_seq_asc = project_latest_capability_views([obs_seq1, obs_seq2])
        self.assertEqual(res_seq_asc[0].capacity.used, 70.0)

        res_seq_desc = project_latest_capability_views([obs_seq2, obs_seq1])
        self.assertEqual(res_seq_desc[0].capacity.used, 70.0)

        # Valid sequence beats malformed sequence on equal timestamp
        obs_seq_bad = copy.deepcopy(self.valid_obs)
        obs_seq_bad["capability_id"] = "cap-seq-bad"
        obs_seq_bad["last_observed_at"] = "2026-10-04T00:05:00Z"
        obs_seq_bad["sequence"] = "not-an-int"
        obs_seq_bad["used"] = 999.0

        obs_seq_ok = copy.deepcopy(self.valid_obs)
        obs_seq_ok["capability_id"] = "cap-seq-bad"
        obs_seq_ok["last_observed_at"] = "2026-10-04T00:05:00Z"
        obs_seq_ok["sequence"] = 1
        obs_seq_ok["used"] = 20.0

        res_bad1 = project_latest_capability_views([obs_seq_bad, obs_seq_ok])
        self.assertEqual(res_bad1[0].capacity.used, 20.0)

        res_bad2 = project_latest_capability_views([obs_seq_ok, obs_seq_bad])
        self.assertEqual(res_bad2[0].capacity.used, 20.0)

        # Equal timestamp AND equal sequence: deterministic tie-break across permutations
        obs_tie_a = copy.deepcopy(self.valid_obs)
        obs_tie_a["capability_id"] = "cap-exact-tie"
        obs_tie_a["last_observed_at"] = "2026-10-04T00:05:00Z"
        obs_tie_a["sequence"] = 1
        obs_tie_a["used"] = 11.0

        obs_tie_b = copy.deepcopy(self.valid_obs)
        obs_tie_b["capability_id"] = "cap-exact-tie"
        obs_tie_b["last_observed_at"] = "2026-10-04T00:05:00Z"
        obs_tie_b["sequence"] = 1
        obs_tie_b["used"] = 22.0

        res_tie_ab = project_latest_capability_views([obs_tie_a, obs_tie_b])
        res_tie_ba = project_latest_capability_views([obs_tie_b, obs_tie_a])
        self.assertEqual(res_tie_ab[0].capacity.used, res_tie_ba[0].capacity.used)

    def test_latest_projection_is_immutable(self) -> None:
        """Instrument 3: Multiple observations select the newest observation per scope without mutation.

        Verifies:
        - Given multiple observations for same capability scope, the one with newest
          observed_at wins.
        - When observed_at ties, the observation with higher sequence wins.
        - Multiple scopes in the observation set produce separate projected views.
        - Input list and observation dictionaries remain completely unmodified.
        - Returned views do not alias caller data or each other.
        """
        obs_older = copy.deepcopy(self.valid_obs)
        obs_older["capability_id"] = "cap-gemini"
        obs_older["last_observed_at"] = "2026-10-04T00:00:00Z"
        obs_older["sequence"] = 10
        obs_older["used"] = 100.0

        obs_newer = copy.deepcopy(self.valid_obs)
        obs_newer["capability_id"] = "cap-gemini"
        obs_newer["last_observed_at"] = "2026-10-04T00:10:00Z"
        obs_newer["sequence"] = 11
        obs_newer["used"] = 300.0

        obs_tie_seq1 = copy.deepcopy(self.valid_obs)
        obs_tie_seq1["capability_id"] = "cap-claude"
        obs_tie_seq1["provider"] = "anthropic"
        obs_tie_seq1["account_scope"] = "acc-anthropic-1"
        obs_tie_seq1["last_observed_at"] = "2026-10-04T00:20:00Z"
        obs_tie_seq1["sequence"] = 1
        obs_tie_seq1["used"] = 50.0

        obs_tie_seq2 = copy.deepcopy(self.valid_obs)
        obs_tie_seq2["capability_id"] = "cap-claude"
        obs_tie_seq2["provider"] = "anthropic"
        obs_tie_seq2["account_scope"] = "acc-anthropic-1"
        obs_tie_seq2["last_observed_at"] = "2026-10-04T00:20:00Z"
        obs_tie_seq2["sequence"] = 2
        obs_tie_seq2["used"] = 90.0

        raw_list = [obs_older, obs_newer, obs_tie_seq1, obs_tie_seq2]
        list_copy = copy.deepcopy(raw_list)

        projected = project_latest_capability_views(raw_list)

        # 1. Input list and items must remain untouched
        self.assertEqual(raw_list, list_copy)

        # 2. Number of views must equal number of distinct scopes (2: cap-gemini and cap-claude)
        self.assertEqual(len(projected), 2)

        view_by_id = {v.capability_id: v for v in projected}
        self.assertIn("cap-gemini", view_by_id)
        self.assertIn("cap-claude", view_by_id)

        # 3. Newest timestamp wins for cap-gemini
        self.assertEqual(view_by_id["cap-gemini"].capacity.used, 300.0)
        self.assertEqual(view_by_id["cap-gemini"].last_observed_at, "2026-10-04T00:10:00Z")

        # 4. Tie in timestamp resolved by higher sequence (seq 2 wins over seq 1)
        self.assertEqual(view_by_id["cap-claude"].capacity.used, 90.0)
        self.assertEqual(view_by_id["cap-claude"].last_observed_at, "2026-10-04T00:20:00Z")

        # 5. Class method alias works identically
        class_projected = CapabilityView.project_latest(raw_list)
        self.assertEqual(len(class_projected), 2)
        class_by_id = {v.capability_id: v for v in class_projected}
        self.assertEqual(class_by_id["cap-gemini"].capacity.used, 300.0)

    def test_capacity_indicator_immutability_and_bounds(self) -> None:
        """Verifies capacity indicator values are recalculable, non-negative, finite and immutable."""
        obs = copy.deepcopy(self.valid_obs)
        obs["limit"] = 1000.0
        obs["used"] = 200.0
        view = build_capability_view(obs)

        self.assertEqual(view.capacity.limit, 1000.0)
        self.assertEqual(view.capacity.used, 200.0)
        self.assertEqual(view.capacity.remaining, 800.0)
        self.assertAlmostEqual(view.capacity.utilization, 0.2, places=5)

        # Remaining should be clamped at 0.0 if used > limit
        obs_exceeded = copy.deepcopy(self.valid_obs)
        obs_exceeded["limit"] = 100.0
        obs_exceeded["used"] = 150.0
        v_exc = build_capability_view(obs_exceeded)
        self.assertEqual(v_exc.capacity.remaining, 0.0)

    def test_derived_capability_id_when_not_explicitly_set(self) -> None:
        """When capability_id is omitted, derive deterministically from provider:type:scope."""
        obs = copy.deepcopy(self.valid_obs)
        obs.pop("capability_id", None)
        obs["provider"] = "openai"
        obs["capability_type"] = "embedding"
        obs["account_scope"] = "team-embed"

        view = build_capability_view(obs)
        self.assertEqual(view.capability_id, "openai:embedding:team-embed")
        self.assertEqual(view.status, "available")

    def test_non_mapping_and_corrupt_inputs_fail_closed(self) -> None:
        """Non-mapping inputs or corrupted inputs safely return unknown view."""
        view_none = build_capability_view(None)  # type: ignore
        self.assertEqual(view_none.status, "unknown")
        self.assertIsNotNone(view_none.reason)

        view_str = build_capability_view("not-a-dict")  # type: ignore
        self.assertEqual(view_str.status, "unknown")

        views_empty = project_latest_capability_views([])
        self.assertEqual(views_empty, [])

    def test_throwing_object_in_observation_fails_closed(self) -> None:
        """Objects raising exceptions during inspection do not crash projection."""
        obs = copy.deepcopy(self.valid_obs)
        obs["throwing_field"] = ThrowingStringObject()
        view = build_capability_view(obs)
        self.assertEqual(view.status, "available")
        self.assertNotIn("secret-crash", repr(view))

    def test_counterexample_utilization_finite_when_limit_tiny_and_used_huge(self) -> None:
        """Finding Sol C2: utilization must be finite even when limit is tiny and used is huge.

        Maintains fail-closed classification and ensures capacity indicators are finite.
        """
        # Case A: limit=1e-300, used=1e300
        obs_huge = copy.deepcopy(self.valid_obs)
        obs_huge["limit"] = 1e-300
        obs_huge["used"] = 1e300
        view_huge = build_capability_view(obs_huge)

        self.assertEqual(view_huge.status, "unavailable")
        self.assertIsNotNone(view_huge.reason)
        self.assertIn("exhausted", view_huge.reason.lower())
        self.assertTrue(math.isfinite(view_huge.capacity.utilization))
        self.assertGreaterEqual(view_huge.capacity.utilization, 1.0)
        self.assertEqual(view_huge.capacity.remaining, 0.0)
        self.assertTrue(math.isfinite(view_huge.capacity.limit))
        self.assertTrue(math.isfinite(view_huge.capacity.used))

        # Case B: subnormal limit=1e-320, used=1e308
        obs_sub = copy.deepcopy(self.valid_obs)
        obs_sub["limit"] = 1e-320
        obs_sub["used"] = 1e308
        view_sub = build_capability_view(obs_sub)
        self.assertEqual(view_sub.status, "unavailable")
        self.assertTrue(math.isfinite(view_sub.capacity.utilization))
        self.assertEqual(view_sub.capacity.remaining, 0.0)

        # Case C: subnormal limit=1e-320, used=1.0
        obs_sub1 = copy.deepcopy(self.valid_obs)
        obs_sub1["limit"] = 1e-320
        obs_sub1["used"] = 1.0
        view_sub1 = build_capability_view(obs_sub1)
        self.assertEqual(view_sub1.status, "unavailable")
        self.assertTrue(math.isfinite(view_sub1.capacity.utilization))
        self.assertEqual(view_sub1.capacity.remaining, 0.0)

        # Case D: JSON serialization succeeds without float 'inf' ValueError
        dict_repr = view_huge.to_dict()
        import json
        serialized = json.dumps(dict_repr, allow_nan=False)
        self.assertIn("utilization", serialized)

    def test_capacity_indicator_enforces_finite_bounds(self) -> None:
        """CapacityIndicator directly rejects non-finite, negative or boolean capacity values."""
        # Non-finite limit, used, remaining, utilization
        for bad_val in [math.inf, -math.inf, math.nan]:
            with self.assertRaises(ValueError):
                CapacityIndicator(limit=bad_val)
            with self.assertRaises(ValueError):
                CapacityIndicator(used=bad_val)
            with self.assertRaises(ValueError):
                CapacityIndicator(remaining=bad_val)
            with self.assertRaises(ValueError):
                CapacityIndicator(utilization=bad_val)

        # Negative values
        for neg_val in [-1.0, -0.0001, -100.0]:
            with self.assertRaises(ValueError):
                CapacityIndicator(limit=neg_val)
            with self.assertRaises(ValueError):
                CapacityIndicator(used=neg_val)
            with self.assertRaises(ValueError):
                CapacityIndicator(remaining=neg_val)
            with self.assertRaises(ValueError):
                CapacityIndicator(utilization=neg_val)

        # Boolean values
        for b_val in [True, False]:
            with self.assertRaises(ValueError):
                CapacityIndicator(limit=b_val)
            with self.assertRaises(ValueError):
                CapacityIndicator(used=b_val)
            with self.assertRaises(ValueError):
                CapacityIndicator(remaining=b_val)
            with self.assertRaises(ValueError):
                CapacityIndicator(utilization=b_val)


    def test_remediation_no_secret_leakage_and_structured_identity_fail_closed(self) -> None:
        """Remediation for Sol CHANGES_REQUESTED findings:

        1. _parse_numeric must not leak raw input or secret markers into reason, to_dict(), or repr().
        2. Structured inputs (e.g. {"api_key": "..."}) in identity or other fields must be rejected
           fail-closed, never become available, and never leak markers into to_dict(), repr(), or reason.
        """
        # Finding 1: numeric input containing probe/secret value
        for numeric_field in ["limit", "used"]:
            for secret_val in [
                "api_key=PROBE_ONLY_VALUE",
                "token=PROBE_ONLY_VALUE",
                "password=PROBE_ONLY_VALUE",
                {"api_key": "PROBE_ONLY_VALUE"},
            ]:
                obs = copy.deepcopy(self.valid_obs)
                obs[numeric_field] = secret_val
                view = build_capability_view(obs)

                self.assertEqual(view.status, "unknown")
                self.assertIsNotNone(view.reason)
                self.assertNotIn("PROBE_ONLY_VALUE", str(view.reason))
                self.assertNotIn("PROBE_ONLY_VALUE", repr(view))
                self.assertNotIn("PROBE_ONLY_VALUE", str(view.to_dict()))
                self.assertNotIn("PROBE_ONLY_VALUE", str(view))
                self.assertIn("Cannot convert", str(view.reason))

        # Finding 2: structured input in identity fields
        identity_fields = ["provider", "account_scope", "capability_type", "capability_id", "location"]
        for field in identity_fields:
            for malformed_id in [
                {"api_key": "PROBE_NESTED_ONLY_VALUE"},
                {"auth": {"api_key": "PROBE_NESTED_ONLY_VALUE"}},
                [{"api_key": "PROBE_NESTED_ONLY_VALUE"}],
                '{"api_key": "PROBE_NESTED_ONLY_VALUE"}',
                "{'api_key': 'PROBE_NESTED_ONLY_VALUE'}",
                "api_key=PROBE_NESTED_ONLY_VALUE",
            ]:
                obs = copy.deepcopy(self.valid_obs)
                obs[field] = malformed_id
                view = build_capability_view(obs)

                # Malformed structured identity MUST NOT become available
                self.assertNotEqual(view.status, "available", f"Field {field} with {malformed_id!r} must not be available")
                self.assertEqual(view.status, "unknown")

                # Secret marker must not appear anywhere in to_dict(), repr() or reason
                d = view.to_dict()
                self.assertNotIn("PROBE_NESTED_ONLY_VALUE", str(d))
                self.assertNotIn("PROBE_NESTED_ONLY_VALUE", repr(view))
                self.assertNotIn("PROBE_NESTED_ONLY_VALUE", str(view))
                self.assertNotIn("PROBE_NESTED_ONLY_VALUE", str(view.reason))
                self.assertNotIn("{'api_key'", str(d))
                self.assertNotIn('{"api_key"', str(d))

        # Structured input in versions, confidence, and reason
        obs_misc = copy.deepcopy(self.valid_obs)
        obs_misc["compatible_versions"] = [
            {"api_key": "PROBE_NESTED_ONLY_VALUE"},
            '{"api_key": "PROBE_NESTED_ONLY_VALUE"}',
            "gemini-2.0",
        ]
        obs_misc["confidence"] = {"api_key": "PROBE_NESTED_ONLY_VALUE"}
        obs_misc["reason"] = {"api_key": "PROBE_NESTED_ONLY_VALUE"}

        view_misc = build_capability_view(obs_misc)
        self.assertNotIn("PROBE_NESTED_ONLY_VALUE", str(view_misc.to_dict()))
        self.assertNotIn("PROBE_NESTED_ONLY_VALUE", repr(view_misc))
        self.assertNotIn("PROBE_NESTED_ONLY_VALUE", str(view_misc.reason))
        self.assertEqual(list(view_misc.compatible_versions), ["gemini-2.0"])
        self.assertEqual(view_misc.capacity.confidence, "uncertain")

        # Latest projection with structured identity input
        obs_proj = copy.deepcopy(self.valid_obs)
        obs_proj["provider"] = {"api_key": "PROBE_NESTED_ONLY_VALUE"}
        obs_proj["sequence"] = 999999
        projected = project_latest_capability_views([obs_proj])
        self.assertEqual(len(projected), 1)
        self.assertNotEqual(projected[0].status, "available")
        self.assertEqual(projected[0].status, "unknown")
        self.assertNotIn("PROBE_NESTED_ONLY_VALUE", str(projected[0].to_dict()))
        self.assertNotIn("PROBE_NESTED_ONLY_VALUE", repr(projected[0]))


if __name__ == "__main__":
    unittest.main()
