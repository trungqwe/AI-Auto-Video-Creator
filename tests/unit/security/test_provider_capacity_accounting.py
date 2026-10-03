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


if __name__ == "__main__":
    unittest.main()