import unittest

from src.controlplane.config.accounting import BudgetExceededError, CapacityAccounting


class TestProviderCapacityAccounting(unittest.TestCase):
    def setUp(self):
        self.accounting = CapacityAccounting(monthly_budget=10.0)

    def test_snapshot_schema_and_secret_boundary(self):
        snapshot = self.accounting.record_capacity_snapshot(
            provider="9router", model="ag/gemini-3.8-flash-high",
            project="AI-Auto-Video-Creator", account_scope="worker",
            quota_domain="monthly", limit=100, used=25,
            reset_at="2026-10-31T00:00:00Z", health="healthy",
            confidence="observed", token="must-not-be-stored",
        )
        self.assertEqual(snapshot["quota_domain"], "monthly")
        self.assertEqual(snapshot["confidence"], "observed")
        self.assertNotIn("token", snapshot)
        self.assertNotIn("must-not-be-stored", repr(snapshot))

    def test_incremental_cost_provenance(self):
        record = self.accounting.record_cost(
            provider="9router", service="codex", operation="completion",
            quantity=2, unit="request", estimate=1.25, actual=1.20,
            currency="USD", source="usage_receipt",
            timestamp="2026-10-03T08:00:00Z",
        )
        for key in ("provider", "service", "operation", "quantity", "unit", "estimate", "actual", "currency", "source", "timestamp"):
            self.assertIn(key, record)

    def test_budget_guard_fail_closed(self):
        self.accounting.record_cost(provider="9router", service="codex", operation="completion", quantity=1, unit="request", estimate=11.0, actual=11.0, currency="USD", source="usage_receipt", timestamp="2026-10-03T08:00:00Z")
        with self.assertRaises(BudgetExceededError):
            self.accounting.guard_budget(0.01)

    def test_revision_immutability_and_redacted_view(self):
        first = self.accounting.record_capacity_snapshot(provider="9router", model="ag/gemini-3.8-flash-high", project="AI-Auto-Video-Creator", account_scope="worker", quota_domain="5h", limit=100, used=10, reset_at="2026-10-03T12:00:00Z", health="healthy", confidence="observed")
        revision = first["revision"]
        second = self.accounting.record_capacity_snapshot(provider="9router", model="ag/gemini-3.8-flash-high", project="AI-Auto-Video-Creator", account_scope="worker", quota_domain="5h", limit=100, used=20, reset_at="2026-10-03T12:00:00Z", health="healthy", confidence="observed")
        self.assertNotEqual(revision, second["revision"])
        self.assertEqual(self.accounting.revision_view(revision)["used"], 10)
        self.assertNotIn("token", self.accounting.revision_view(revision))

    def test_snapshot_scope_and_aliasing(self):
        snapshot = self.accounting.record_capacity_snapshot(
            provider="9router", model="ag/gemini-3.8-flash-high",
            project="AI-Auto-Video-Creator", account="worker",
            quota_domain="5h", limit=50, usage=15,
            reset_window="2026-10-03T18:00:00Z", health="healthy",
            confidence="observed",
        )
        self.assertEqual(snapshot["account_scope"], "worker")
        self.assertEqual(snapshot["account"], "worker")
        self.assertEqual(snapshot["used"], 15)
        self.assertEqual(snapshot["usage"], 15)
        self.assertEqual(snapshot["reset_at"], "2026-10-03T18:00:00Z")
        self.assertEqual(snapshot["reset_window"], "2026-10-03T18:00:00Z")

    def test_snapshot_validation_fail_closed(self):
        with self.assertRaises(ValueError):
            self.accounting.record_capacity_snapshot(limit=-1, used=10)
        with self.assertRaises(ValueError):
            self.accounting.record_capacity_snapshot(limit=10, used=-5)
        with self.assertRaises(ValueError):
            self.accounting.record_capacity_snapshot(limit="not-a-number", used=10)

    def test_secret_leak_prevention_exhaustive(self):
        sensitive_kwargs = {
            "api" + "_key": "sk-" + "test-token-value",
            "access_" + "token": "bearer-" + "access-val",
            "pass" + "word": "super-" + "secret-val",
            "client_" + "secret": "cs-" + "client-val",
            "private_" + "key": "rsa-" + "private-material",
            "credentials": {"nested_" + "token": "secret"},
        }
        snapshot = self.accounting.record_capacity_snapshot(
            provider="9router", model="ag/gemini-3.8-flash-high",
            project="AI-Auto-Video-Creator", account_scope="worker",
            quota_domain="monthly", limit=100, used=10,
            reset_at="2026-10-31T00:00:00Z", health="healthy",
            confidence="observed",
            **sensitive_kwargs,
        )
        for key in sensitive_kwargs:
            self.assertNotIn(key, snapshot)
            self.assertNotIn(key, self.accounting.revision_view(snapshot["revision"]))
        self.assertNotIn("sk-test-token-value", repr(snapshot))

    def test_secret_redaction_in_text_fields(self):
        token_segment = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        bearer_val = f"Bearer {token_segment}.dummy.signature"
        record = self.accounting.record_cost(
            provider="9router", service="codex", operation="completion",
            quantity=1, unit="request", estimate=0.5, actual=0.5,
            currency="USD",
            source=bearer_val,
            timestamp="2026-10-03T08:00:00Z",
        )
        self.assertIn("Bearer [REDACTED]", record["source"])
        self.assertNotIn(token_segment, record["source"])

    def test_budget_guard_within_limit_and_sequential_accumulation(self):
        acct = CapacityAccounting(monthly_budget=20.0)
        acct.record_cost(
            provider="9router", service="codex", operation="completion",
            quantity=1, unit="request", estimate=5.0, actual=5.0,
            currency="USD", source="usage_receipt", timestamp="2026-10-03T08:00:00Z",
        )
        self.assertIsNone(acct.guard_budget(10.0))

        acct.record_cost(
            provider="9router", service="codex", operation="completion",
            quantity=1, unit="request", estimate=10.0, actual=10.0,
            currency="USD", source="usage_receipt", timestamp="2026-10-03T09:00:00Z",
        )
        self.assertIsNone(acct.guard_budget(5.0))

        with self.assertRaises(BudgetExceededError):
            acct.guard_budget(5.01)

    def test_budget_guard_negative_amount_fail_closed(self):
        with self.assertRaises(BudgetExceededError):
            self.accounting.guard_budget(-1.0)
        with self.assertRaises(BudgetExceededError):
            self.accounting.guard_budget("invalid-amount")

    def test_budget_guard_zero_budget_fail_closed(self):
        zero_acct = CapacityAccounting(monthly_budget=0.0)
        self.assertIsNone(zero_acct.guard_budget(0.0))
        with self.assertRaises(BudgetExceededError):
            zero_acct.guard_budget(0.01)

    def test_budget_negative_initialization_fail_closed(self):
        with self.assertRaises(ValueError):
            CapacityAccounting(monthly_budget=-1.0)

    def test_revision_immutability_deep_defense(self):
        snapshot = self.accounting.record_capacity_snapshot(
            provider="9router", model="ag/gemini-3.8-flash-high",
            project="AI-Auto-Video-Creator", account_scope="worker",
            quota_domain="monthly", limit=100, used=10,
            reset_at="2026-10-31T00:00:00Z", health="healthy",
            confidence="observed",
        )
        rev = snapshot["revision"]
        snapshot["used"] = 999
        snapshot["injected_leak"] = "evil"
        self.assertEqual(self.accounting.revision_view(rev)["used"], 10)
        self.assertNotIn("injected_leak", self.accounting.revision_view(rev))

        view = self.accounting.revision_view(rev)
        view["used"] = 888
        self.assertEqual(self.accounting.revision_view(rev)["used"], 10)

    def test_revision_view_latest_and_missing(self):
        fresh = CapacityAccounting(monthly_budget=10.0)
        self.assertEqual(fresh.revision_view(None), {})
        self.assertEqual(fresh.revision_view("non-existent"), {})

        first = fresh.record_capacity_snapshot(
            provider="9router", model="ag/gemini-3.8-flash-high",
            project="AI-Auto-Video-Creator", account_scope="worker",
            quota_domain="monthly", limit=100, used=10,
            reset_at="2026-10-31T00:00:00Z", health="healthy",
            confidence="observed",
        )
        second = fresh.record_capacity_snapshot(
            provider="9router", model="ag/gemini-3.8-flash-high",
            project="AI-Auto-Video-Creator", account_scope="worker",
            quota_domain="monthly", limit=100, used=30,
            reset_at="2026-10-31T00:00:00Z", health="healthy",
            confidence="observed",
        )
        self.assertEqual(fresh.revision_view(None)["used"], 30)
        self.assertEqual(fresh.revision_view(first["revision"])["used"], 10)
        self.assertEqual(fresh.revision_view(second["revision"])["used"], 30)

    def test_cost_record_immutability_and_validation(self):
        with self.assertRaises(ValueError):
            self.accounting.record_cost(quantity=-1)
        with self.assertRaises(ValueError):
            self.accounting.record_cost(estimate=-0.5)
        with self.assertRaises(ValueError):
            self.accounting.record_cost(actual=-10.0)

        record = self.accounting.record_cost(
            provider="9router", service="codex", operation="completion",
            quantity=1, unit="request", estimate=2.0, actual=2.0,
            currency="USD", source="usage_receipt",
            timestamp="2026-10-03T08:00:00Z",
        )
        record["actual"] = 999.0
        self.assertEqual(self.accounting.cumulative_cost, 2.0)


    def test_capacity_snapshot_identity_and_scope_secret_sanitization(self):
        """Finding 1: Every identity and scope field in capacity snapshot must be sanitized."""
        raw_private_key = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0r123secretmaterialhere==\n"
            "-----END RSA PRIVATE KEY-----"
        )
        snapshot = self.accounting.record_capacity_snapshot(
            provider="9router; secret_key=sk-live-secret-val",
            model="ag/gemini-3.8-flash-high; client_secret: cs-model-secret",
            project="AI-Auto-Video-Creator; private_key=pk-proj-secret",
            account_scope="Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.sig",
            quota_domain="credential: user:superpasswd",
            health="healthy; bearer-access-token-999",
            confidence="observed; api_key=sk-conf-secret",
            reset_window="Bearer reset-window-token",
            limit=100,
            used=10,
        )

        self.assertIn("secret_key=[REDACTED]", snapshot["provider"])
        self.assertNotIn("sk-live-secret-val", repr(snapshot))

        self.assertIn("client_secret: [REDACTED]", snapshot["model"])
        self.assertNotIn("cs-model-secret", repr(snapshot))

        self.assertIn("private_key=[REDACTED]", snapshot["project"])
        self.assertNotIn("pk-proj-secret", repr(snapshot))

        self.assertEqual(snapshot["account_scope"], "Bearer [REDACTED]")
        self.assertEqual(snapshot["account"], "Bearer [REDACTED]")
        self.assertNotIn("dummy.sig", repr(snapshot))

        self.assertIn("credential: [REDACTED]", snapshot["quota_domain"])
        self.assertNotIn("superpasswd", repr(snapshot))

        self.assertIn("Bearer [REDACTED]", snapshot["health"])
        self.assertNotIn("bearer-access-token-999", repr(snapshot))

        self.assertIn("api_key=[REDACTED]", snapshot["confidence"])
        self.assertNotIn("sk-conf-secret", repr(snapshot))

        self.assertEqual(snapshot["reset_window"], "Bearer [REDACTED]")
        self.assertEqual(snapshot["reset_at"], "Bearer [REDACTED]")

        # Check revision_view
        rev_view = self.accounting.revision_view(snapshot["revision"])
        self.assertEqual(rev_view["account_scope"], "Bearer [REDACTED]")
        self.assertNotIn("sk-live-secret-val", repr(rev_view))
        self.assertNotIn("pk-proj-secret", repr(rev_view))

        # Check storage
        self.assertNotIn("sk-live-secret-val", repr(self.accounting._snapshots))
        self.assertNotIn("sk-live-secret-val", repr(self.accounting._revisions))

        # Check raw private key in account_scope
        pk_snapshot = self.accounting.record_capacity_snapshot(
            provider="9router",
            account_scope=raw_private_key,
            limit=50,
            used=5,
        )
        self.assertEqual(pk_snapshot["account_scope"], "[REDACTED PRIVATE KEY]")
        self.assertNotIn("secretmaterialhere", repr(pk_snapshot))
        self.assertNotIn("secretmaterialhere", repr(self.accounting._snapshots))
        self.assertNotIn("secretmaterialhere", repr(self.accounting._revisions))

    def test_cost_record_identity_and_scope_secret_sanitization(self):
        """Finding 1: Every identity, scope, and provenance field in cost record must be sanitized."""
        record = self.accounting.record_cost(
            provider="Bearer 9router-token-123",
            service="codex; secret_key=sec-svc-val",
            operation="completion; private_key: pk-op-val",
            quantity=1,
            unit="request; api_key=ak-val",
            estimate=1.0,
            actual=1.0,
            currency="USD; client_secret=cs-curr-val",
            source="https://router.internal?credential=cred-src-val",
            timestamp="2026-10-03T08:00:00Z; Bearer time-token",
        )
        self.assertEqual(record["provider"], "Bearer [REDACTED]")
        self.assertNotIn("9router-token-123", repr(record))

        self.assertIn("secret_key=[REDACTED]", record["service"])
        self.assertNotIn("sec-svc-val", repr(record))

        self.assertIn("private_key: [REDACTED]", record["operation"])
        self.assertNotIn("pk-op-val", repr(record))

        self.assertIn("api_key=[REDACTED]", record["unit"])
        self.assertNotIn("ak-val", repr(record))

        self.assertIn("client_secret=[REDACTED]", record["currency"])
        self.assertNotIn("cs-curr-val", repr(record))

        self.assertIn("credential=[REDACTED]", record["source"])
        self.assertNotIn("cred-src-val", repr(record))

        self.assertIn("Bearer [REDACTED]", record["timestamp"])
        self.assertNotIn("time-token", repr(record))

        # Check revision_view
        rev_view = self.accounting.revision_view(record["record_id"])
        self.assertEqual(rev_view["provider"], "Bearer [REDACTED]")
        self.assertNotIn("sec-svc-val", repr(rev_view))

        # Check storage
        self.assertNotIn("sec-svc-val", repr(self.accounting._cost_records))
        self.assertNotIn("sec-svc-val", repr(self.accounting._revisions))

    def test_budget_guard_nan_and_infinity_fail_closed(self):
        """Finding 2: NaN, Infinity, negative, non-numeric must raise BudgetExceededError."""
        bad_amounts = [
            float("nan"),
            "nan",
            float("inf"),
            "inf",
            float("-inf"),
            "-inf",
            -1.0,
            "-5.0",
            "not-a-number",
            None,
            True,
            False,
            [1.0],
            {"amount": 1.0},
        ]
        for val in bad_amounts:
            with self.subTest(val=val):
                with self.assertRaises(BudgetExceededError):
                    self.accounting.guard_budget(val)

    def test_cost_record_numeric_validation_fail_closed(self):
        """Finding 2: Cost quantity, estimate, and actual must reject NaN, Infinity, negatives, booleans."""
        for bad_val in [float("nan"), float("inf"), float("-inf"), -1.0, True, False]:
            with self.subTest(bad_val=bad_val):
                with self.assertRaises(ValueError):
                    self.accounting.record_cost(quantity=bad_val)
                with self.assertRaises(ValueError):
                    self.accounting.record_cost(estimate=bad_val)
                with self.assertRaises(ValueError):
                    self.accounting.record_cost(actual=bad_val)

    def test_capacity_snapshot_numeric_validation_fail_closed(self):
        """Finding 2: Limit and used must reject NaN, Infinity, negatives, booleans."""
        for bad_val in [float("nan"), float("inf"), float("-inf"), -5, True, False]:
            with self.subTest(bad_val=bad_val):
                with self.assertRaises(ValueError):
                    self.accounting.record_capacity_snapshot(limit=bad_val, used=10)
                with self.assertRaises(ValueError):
                    self.accounting.record_capacity_snapshot(limit=10, used=bad_val)

    def test_monthly_budget_nan_and_infinity_fail_closed(self):
        """Finding 2: monthly_budget must reject NaN, Infinity, negatives, booleans."""
        for bad_val in [float("nan"), float("inf"), float("-inf"), -1.0, True, False]:
            with self.subTest(bad_val=bad_val):
                with self.assertRaises(ValueError):
                    CapacityAccounting(monthly_budget=bad_val)

        acct = CapacityAccounting(monthly_budget=10.0)
        for bad_val in [float("nan"), float("inf"), float("-inf"), -1.0, True, False]:
            with self.subTest(bad_val=bad_val):
                with self.assertRaises(ValueError):
                    acct.monthly_budget = bad_val


if __name__ == "__main__":
    unittest.main()
