import unittest

from src.controlplane.config.accounting import BudgetExceededError, CapacityAccounting, CapacityAccountingError, InvalidNumericError, MissingProvenanceError


class TestProviderCapacityAccounting(unittest.TestCase):
    def setUp(self):
        self.accounting = CapacityAccounting(monthly_budget=10.0)

    def test_snapshot_schema_and_secret_boundary(self):
        snapshot = self.accounting.record_capacity_snapshot(
            provider="9router", model="ag/gemini-3.8-flash-high",
            project="AI-Auto-Video-Creator", account="worker", scope="worker", account_scope="worker",
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
            project="AI-Auto-Video-Creator", account="worker", scope="worker",
            quantity=2, unit="request", estimate=1.25, actual=1.20,
            currency="USD", source="usage_receipt",
            timestamp="2026-10-03T08:00:00Z",
        )
        for key in ("provider", "service", "operation", "project", "account", "scope", "quantity", "unit", "estimate", "actual", "currency", "source", "timestamp"):
            self.assertIn(key, record)

    def test_budget_guard_fail_closed(self):
        self.accounting.record_cost(provider="9router", service="codex", operation="completion", project="AI-Auto-Video-Creator", account="worker", scope="worker", quantity=1, unit="request", estimate=11.0, actual=11.0, currency="USD", source="usage_receipt", timestamp="2026-10-03T08:00:00Z")
        with self.assertRaises(BudgetExceededError):
            self.accounting.guard_budget(0.01)

    def test_revision_immutability_and_redacted_view(self):
        first = self.accounting.record_capacity_snapshot(provider="9router", model="ag/gemini-3.8-flash-high", project="AI-Auto-Video-Creator", account="worker", scope="worker", account_scope="worker", quota_domain="5h", limit=100, used=10, reset_at="2026-10-03T12:00:00Z", health="healthy", confidence="observed")
        revision = first["revision"]
        second = self.accounting.record_capacity_snapshot(provider="9router", model="ag/gemini-3.8-flash-high", project="AI-Auto-Video-Creator", account="worker", scope="worker", account_scope="worker", quota_domain="5h", limit=100, used=20, reset_at="2026-10-03T12:00:00Z", health="healthy", confidence="observed")
        self.assertNotEqual(revision, second["revision"])
        self.assertEqual(self.accounting.revision_view(revision)["used"], 10)
        self.assertNotIn("token", self.accounting.revision_view(revision))

    def test_snapshot_scope_and_aliasing(self):
        # Passing only account without scope fails-closed (no alias fallback)
        with self.assertRaises(MissingProvenanceError):
            self.accounting.record_capacity_snapshot(
                provider="9router", model="ag/gemini-3.8-flash-high",
                project="AI-Auto-Video-Creator", account="worker",
                quota_domain="5h", limit=50, usage=15,
                reset_window="2026-10-03T18:00:00Z", health="healthy",
                confidence="observed",
            )
        # Passing only scope without account fails-closed (no alias fallback)
        with self.assertRaises(MissingProvenanceError):
            self.accounting.record_capacity_snapshot(
                provider="9router", model="ag/gemini-3.8-flash-high",
                project="AI-Auto-Video-Creator", scope="worker",
                quota_domain="5h", limit=50, usage=15,
                reset_window="2026-10-03T18:00:00Z", health="healthy",
                confidence="observed",
            )
        snapshot = self.accounting.record_capacity_snapshot(
            provider="9router", model="ag/gemini-3.8-flash-high",
            project="AI-Auto-Video-Creator", account="worker-acc", scope="worker-scope",
            quota_domain="5h", limit=50, usage=15,
            reset_window="2026-10-03T18:00:00Z", health="healthy",
            confidence="observed",
        )
        self.assertEqual(snapshot["account_scope"], "worker-acc:worker-scope")
        self.assertEqual(snapshot["account"], "worker-acc")
        self.assertEqual(snapshot["scope"], "worker-scope")
        self.assertEqual(snapshot["used"], 15)
        self.assertEqual(snapshot["usage"], 15)
        self.assertEqual(snapshot["reset_at"], "2026-10-03T18:00:00Z")
        self.assertEqual(snapshot["reset_window"], "2026-10-03T18:00:00Z")

    def test_snapshot_validation_fail_closed(self):
        valid_snap = {"provider": "9router", "project": "AI-Auto-Video-Creator", "account": "worker", "scope": "worker"}
        with self.assertRaises(ValueError):
            self.accounting.record_capacity_snapshot(**valid_snap, limit=-1, used=10)
        with self.assertRaises(ValueError):
            self.accounting.record_capacity_snapshot(**valid_snap, limit=10, used=-5)
        with self.assertRaises(ValueError):
            self.accounting.record_capacity_snapshot(**valid_snap, limit="not-a-number", used=10)

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
            project="AI-Auto-Video-Creator", account="worker", scope="worker", account_scope="worker",
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
            project="AI-Auto-Video-Creator", account="worker", scope="worker",
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
            project="AI-Auto-Video-Creator", account="worker", scope="worker",
            quantity=1, unit="request", estimate=5.0, actual=5.0,
            currency="USD", source="usage_receipt", timestamp="2026-10-03T08:00:00Z",
        )
        self.assertIsNone(acct.guard_budget(10.0))

        acct.record_cost(
            provider="9router", service="codex", operation="completion",
            project="AI-Auto-Video-Creator", account="worker", scope="worker",
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
            project="AI-Auto-Video-Creator", account="worker", scope="worker", account_scope="worker",
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
            project="AI-Auto-Video-Creator", account="worker", scope="worker", account_scope="worker",
            quota_domain="monthly", limit=100, used=10,
            reset_at="2026-10-31T00:00:00Z", health="healthy",
            confidence="observed",
        )
        second = fresh.record_capacity_snapshot(
            provider="9router", model="ag/gemini-3.8-flash-high",
            project="AI-Auto-Video-Creator", account="worker", scope="worker", account_scope="worker",
            quota_domain="monthly", limit=100, used=30,
            reset_at="2026-10-31T00:00:00Z", health="healthy",
            confidence="observed",
        )
        self.assertEqual(fresh.revision_view(None)["used"], 30)
        self.assertEqual(fresh.revision_view(first["revision"])["used"], 10)
        self.assertEqual(fresh.revision_view(second["revision"])["used"], 30)

    def test_cost_record_immutability_and_validation(self):
        valid_cost = {
            "provider": "9router",
            "service": "codex",
            "operation": "completion",
            "project": "AI-Auto-Video-Creator",
            "account": "worker",
            "scope": "worker",
            "source": "usage_receipt",
            "timestamp": "2026-10-03T08:00:00Z",
        }
        with self.assertRaises(ValueError):
            self.accounting.record_cost(**valid_cost, quantity=-1)
        with self.assertRaises(ValueError):
            self.accounting.record_cost(**valid_cost, estimate=-0.5)
        with self.assertRaises(ValueError):
            self.accounting.record_cost(**valid_cost, actual=-10.0)

        record = self.accounting.record_cost(
            provider="9router", service="codex", operation="completion",
            project="AI-Auto-Video-Creator", account="worker", scope="worker",
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
            account="worker; token=raw-token",
            scope="worker; password=superpwd",
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
        self.assertIn("token=[REDACTED]", snapshot["account"])
        self.assertIn("password=[REDACTED]", snapshot["scope"])
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
            project="AI-Auto-Video-Creator",
            account=raw_private_key,
            scope=raw_private_key,
            account_scope=raw_private_key,
            limit=50,
            used=5,
        )
        self.assertEqual(pk_snapshot["account"], "[REDACTED PRIVATE KEY]")
        self.assertEqual(pk_snapshot["scope"], "[REDACTED PRIVATE KEY]")
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
            project="AI-Auto-Video-Creator; api_key=sk-proj-val",
            account="worker; password=pw-val",
            scope="worker; token=tok-val",
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
        valid_cost = {
            "provider": "9router",
            "service": "codex",
            "operation": "completion",
            "project": "AI-Auto-Video-Creator",
            "account": "worker",
            "scope": "worker",
            "source": "usage_receipt",
            "timestamp": "2026-10-03T08:00:00Z",
        }
        for bad_val in [float("nan"), float("inf"), float("-inf"), -1.0, True, False]:
            with self.subTest(bad_val=bad_val):
                with self.assertRaises(ValueError):
                    self.accounting.record_cost(**valid_cost, quantity=bad_val)
                with self.assertRaises(ValueError):
                    self.accounting.record_cost(**valid_cost, estimate=bad_val)
                with self.assertRaises(ValueError):
                    self.accounting.record_cost(**valid_cost, actual=bad_val)

    def test_capacity_snapshot_numeric_validation_fail_closed(self):
        """Finding 2: Limit and used must reject NaN, Infinity, negatives, booleans."""
        valid_snap = {
            "provider": "9router",
            "project": "AI-Auto-Video-Creator",
            "account": "worker",
            "scope": "worker",
        }
        for bad_val in [float("nan"), float("inf"), float("-inf"), -5, True, False]:
            with self.subTest(bad_val=bad_val):
                with self.assertRaises(ValueError):
                    self.accounting.record_capacity_snapshot(**valid_snap, limit=bad_val, used=10)
                with self.assertRaises(ValueError):
                    self.accounting.record_capacity_snapshot(**valid_snap, limit=10, used=bad_val)

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


    def test_numeric_overflow_fail_closed(self):
        """Finding 1 (C2): OverflowError (10**400) must be converted to BudgetExceededError or typed fail-closed ValueError."""
        huge_int = 10**400
        neg_huge_int = -10**400
        huge_str = "1" + "0" * 400

        # guard_budget must raise BudgetExceededError
        with self.assertRaises(BudgetExceededError):
            self.accounting.guard_budget(huge_int)
        with self.assertRaises(BudgetExceededError):
            self.accounting.guard_budget(neg_huge_int)
        with self.assertRaises(BudgetExceededError):
            self.accounting.guard_budget(huge_str)

        # CapacityAccounting init and setter must raise ValueError
        with self.assertRaises(ValueError):
            CapacityAccounting(monthly_budget=huge_int)
        with self.assertRaises(ValueError):
            CapacityAccounting(monthly_budget=huge_str)

        acct = CapacityAccounting(monthly_budget=10.0)
        with self.assertRaises(ValueError):
            acct.monthly_budget = huge_int
        with self.assertRaises(ValueError):
            acct.monthly_budget = huge_str

        # record_capacity_snapshot must reject huge integer for limit and used
        valid_snap = {
            "provider": "9router",
            "project": "AI-Auto-Video-Creator",
            "account": "worker",
            "scope": "worker",
        }
        with self.assertRaises(ValueError):
            self.accounting.record_capacity_snapshot(**valid_snap, limit=huge_int, used=10)
        with self.assertRaises(ValueError):
            self.accounting.record_capacity_snapshot(**valid_snap, limit=10, used=huge_int)

        # record_cost must reject huge integer for quantity, estimate, and actual
        valid_cost = {
            "provider": "9router",
            "service": "codex",
            "operation": "completion",
            "project": "AI-Auto-Video-Creator",
            "account": "worker",
            "scope": "worker",
            "source": "usage_receipt",
            "timestamp": "2026-10-03T08:00:00Z",
        }
        with self.assertRaises(ValueError):
            self.accounting.record_cost(**valid_cost, quantity=huge_int)
        with self.assertRaises(ValueError):
            self.accounting.record_cost(**valid_cost, estimate=huge_int)
        with self.assertRaises(ValueError):
            self.accounting.record_cost(**valid_cost, actual=huge_int)

    def test_capacity_snapshot_missing_or_empty_scope_fail_closed(self):
        """Finding 2 (C2/C3): Snapshot scope fields (provider, project, account, scope) must be provided; missing, empty, or placeholder rejected fail-closed."""
        base_valid = {
            "provider": "9router",
            "model": "ag/gemini-3.8-flash-high",
            "project": "AI-Auto-Video-Creator",
            "account": "worker",
            "scope": "worker",
            "account_scope": "worker",
            "limit": 100,
            "used": 10,
        }

        # 1. provider missing, empty, whitespace, boolean, or placeholder
        for bad_p in ["", "   ", None, True, False, "default", "unknown", "system"]:
            kwargs = dict(base_valid)
            kwargs["provider"] = bad_p
            with self.subTest(bad_provider=bad_p):
                with self.assertRaises(MissingProvenanceError):
                    self.accounting.record_capacity_snapshot(**kwargs)

        kwargs_no_prov = dict(base_valid)
        del kwargs_no_prov["provider"]
        with self.assertRaises(MissingProvenanceError):
            self.accounting.record_capacity_snapshot(**kwargs_no_prov)

        # 2. project missing, empty, whitespace, boolean, or placeholder
        for bad_prj in ["", "   ", None, True, False, "default", "unknown", "system"]:
            kwargs = dict(base_valid)
            kwargs["project"] = bad_prj
            with self.subTest(bad_project=bad_prj):
                with self.assertRaises(MissingProvenanceError):
                    self.accounting.record_capacity_snapshot(**kwargs)

        kwargs_no_prj = dict(base_valid)
        del kwargs_no_prj["project"]
        with self.assertRaises(MissingProvenanceError):
            self.accounting.record_capacity_snapshot(**kwargs_no_prj)

        # 3. account missing, empty, whitespace, boolean, or placeholder
        for bad_acc in ["", "   ", None, True, False, "default", "unknown", "system"]:
            kwargs = dict(base_valid)
            kwargs["account"] = bad_acc
            with self.subTest(bad_account=bad_acc):
                with self.assertRaises(MissingProvenanceError):
                    self.accounting.record_capacity_snapshot(**kwargs)

        kwargs_no_acc = dict(base_valid)
        del kwargs_no_acc["account"]
        with self.assertRaises(MissingProvenanceError):
            self.accounting.record_capacity_snapshot(**kwargs_no_acc)

        # 4. scope missing, empty, whitespace, boolean, or placeholder
        for bad_scp in ["", "   ", None, True, False, "default", "unknown", "system"]:
            kwargs = dict(base_valid)
            kwargs["scope"] = bad_scp
            with self.subTest(bad_scope=bad_scp):
                with self.assertRaises(MissingProvenanceError):
                    self.accounting.record_capacity_snapshot(**kwargs)

        kwargs_no_scp = dict(base_valid)
        del kwargs_no_scp["scope"]
        with self.assertRaises(MissingProvenanceError):
            self.accounting.record_capacity_snapshot(**kwargs_no_scp)

        # 5. account alone cannot deduce scope
        with self.assertRaises(MissingProvenanceError):
            self.accounting.record_capacity_snapshot(
                provider="9router", project="AI-Auto-Video-Creator", account="acc-only"
            )

        # 6. scope alone cannot deduce account
        with self.assertRaises(MissingProvenanceError):
            self.accounting.record_capacity_snapshot(
                provider="9router", project="AI-Auto-Video-Creator", scope="scope-only"
            )

        # 7. account_scope alone cannot substitute for missing account or scope
        with self.assertRaises(MissingProvenanceError):
            self.accounting.record_capacity_snapshot(
                provider="9router", project="AI-Auto-Video-Creator", account_scope="acc-scope"
            )

        # 8. Both account and scope provided cleanly without deduction
        snap = self.accounting.record_capacity_snapshot(
            provider="9router", project="AI-Auto-Video-Creator", account="acc-val", scope="scope-val"
        )
        self.assertEqual(snap["account"], "acc-val")
        self.assertEqual(snap["scope"], "scope-val")
        self.assertEqual(snap["account_scope"], "acc-val:scope-val")

    def test_cost_record_missing_or_empty_provenance_fail_closed(self):
        """Finding 2 (C2/C3): Cost provenance fields must be provided; missing, empty, or placeholder rejected."""
        base_valid = {
            "provider": "9router",
            "service": "codex",
            "operation": "completion",
            "project": "AI-Auto-Video-Creator",
            "account": "worker",
            "scope": "worker",
            "quantity": 1,
            "unit": "request",
            "estimate": 1.0,
            "actual": 1.0,
            "currency": "USD",
            "source": "usage_receipt",
            "timestamp": "2026-10-03T08:00:00Z",
        }

        required_keys = (
            "provider",
            "service",
            "operation",
            "project",
            "account",
            "scope",
            "source",
            "timestamp",
        )
        for req_k in required_keys:
            # Missing key from kwargs
            kwargs_missing = dict(base_valid)
            del kwargs_missing[req_k]
            with self.subTest(missing_key=req_k):
                with self.assertRaises(MissingProvenanceError):
                    self.accounting.record_cost(**kwargs_missing)

            # Empty, whitespace, None, boolean, or placeholder
            for bad_val in ["", "   ", None, True, False, "default", "unknown", "system"]:
                kwargs_bad = dict(base_valid)
                kwargs_bad[req_k] = bad_val
                with self.subTest(key=req_k, bad_val=bad_val):
                    with self.assertRaises(MissingProvenanceError):
                        self.accounting.record_cost(**kwargs_bad)

    def test_cost_record_optional_scope_fields_validation(self):
        """All scope fields (project, account, scope) are strictly required and preserved."""
        base_valid = {
            "provider": "9router",
            "service": "codex",
            "operation": "completion",
            "project": "my-project",
            "account": "my-account",
            "scope": "my-scope",
            "source": "usage_receipt",
            "timestamp": "2026-10-03T08:00:00Z",
        }
        record = self.accounting.record_cost(**base_valid)
        self.assertEqual(record["project"], "my-project")
        self.assertEqual(record["account"], "my-account")
        self.assertEqual(record["scope"], "my-scope")

    def test_numeric_overflow_or_numeric_validation_or_missing_or_empty(self):
        """Directive targeted suite covering numeric overflow, validation, and missing/empty checks."""
        self.test_numeric_overflow_fail_closed()
        self.test_capacity_snapshot_numeric_validation_fail_closed()
        self.test_cost_record_numeric_validation_fail_closed()
        self.test_monthly_budget_nan_and_infinity_fail_closed()
        self.test_capacity_snapshot_missing_or_empty_scope_fail_closed()
        self.test_cost_record_missing_or_empty_provenance_fail_closed()


# Attach alias so unittest -k "numeric_overflow or numeric_validation or missing_or_empty" executes cleanly
setattr(
    TestProviderCapacityAccounting,
    "test numeric_overflow or numeric_validation or missing_or_empty",
    TestProviderCapacityAccounting.test_numeric_overflow_or_numeric_validation_or_missing_or_empty,
)


if __name__ == "__main__":
    unittest.main()
