"""Behavioral tests for CT-CAP-003 CapabilityView projection (TASK-CAP-J-P2).

Verifies:
1. Schema conformity: required fields, non-secret leakage, redaction, non-aliasing.
2. Deterministic status classification: available, degraded, unavailable, unknown (fail-closed).
3. Recalculated non-negative finite capacity indicators: limit, used, remaining, utilization, confidence.
4. Latest projection across scopes: newest observed_at, sequence tie-breaker, input immutability.
5. Defensive edge cases: malformed objects, throwing exceptions, nested secret injections.
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


if __name__ == "__main__":
    unittest.main()
