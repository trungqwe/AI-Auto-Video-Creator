import unittest

from controlplane.config.accounting import BudgetExceededError, CapacityAccounting, CapacityAccountingError, InvalidNumericError, MissingProvenanceError, _parse_non_negative_finite, _validate_budget_value, _sanitize_value



class SecretCrashFloatAndStr:
    """Object where both __float__ and __str__ raise RuntimeError containing secrets."""

    def __init__(self, secret: str = "sk-custom-crash-secret-12345"):
        self.secret = secret

    def __float__(self):
        raise RuntimeError(f"crash_float_with_secret: {self.secret}")

    def __str__(self):
        raise RuntimeError(f"crash_str_with_secret: {self.secret}")

    def __repr__(self):
        return f"SecretCrashFloatAndStr({self.secret})"


class SecretCrashStrOnly:
    """Object where __float__ delegates to string and __str__ raises RuntimeError with secret."""

    def __init__(self, secret: str = "sk-custom-str-secret-67890"):
        self.secret = secret

    def __float__(self):
        return float(str(self))

    def __str__(self):
        raise RuntimeError(f"crash_str_with_secret: {self.secret}")

    def __repr__(self):
        return f"SecretCrashStrOnly({self.secret})"


class SecretCrashNoFloat:
    """Object without __float__ whose __str__ raises RuntimeError with secret."""

    def __init__(self, secret: str = "sk-custom-nofloat-secret-abcde"):
        self.secret = secret

    def __str__(self):
        raise RuntimeError(f"crash_str_with_secret: {self.secret}")

    def __repr__(self):
        return f"SecretCrashNoFloat({self.secret})"


class SecretCrashIntSubclass(int):
    """Integer subclass whose __str__ and __repr__ raise RuntimeError with secret."""

    def __str__(self):
        raise RuntimeError("crash_int_subclass_secret_xyz")

    def __repr__(self):
        return "crash_int_subclass_secret_xyz"


class SecretCrashDeepcopy:
    """Object whose __deepcopy__ raises RuntimeError containing a secret."""

    def __init__(self, secret: str = "sk-custom-deepcopy-secret-99999"):
        self.secret = secret

    def __deepcopy__(self, memo):
        raise RuntimeError(f"crash_deepcopy_with_secret: {self.secret}")

    def __str__(self):
        return f"SecretCrashDeepcopy({self.secret})"

    def __repr__(self):
        return f"SecretCrashDeepcopy({self.secret})"


class SecretCrashIterator:
    """Iterator whose __next__ raises RuntimeError containing a secret."""

    def __init__(self, secret: str = "sk-custom-iter-secret-88888"):
        self.secret = secret

    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError(f"crash_iter_with_secret: {self.secret}")

    def __str__(self):
        return f"SecretCrashIterator({self.secret})"

    def __repr__(self):
        return f"SecretCrashIterator({self.secret})"


class SecretCrashIterable:
    """Iterable whose __iter__ raises RuntimeError containing a secret."""

    def __init__(self, secret: str = "sk-custom-iterable-secret-77777"):
        self.secret = secret

    def __iter__(self):
        raise RuntimeError(f"crash_iterable_with_secret: {self.secret}")

    def __str__(self):
        return f"SecretCrashIterable({self.secret})"

    def __repr__(self):
        return f"SecretCrashIterable({self.secret})"

class SecretCrashOnNthDeepcopy:
    """Object that succeeds during the first N-1 deepcopies and raises on the Nth deepcopy."""

    def __init__(
        self,
        fail_at: int = 3,
        secret: str = "sk-third-deepcopy-secret-99999",
        exc_cls: type[Exception] = RuntimeError,
    ):
        self.state = {"count": 0}
        self.fail_at = fail_at
        self.secret = secret
        self.exc_cls = exc_cls

    def __deepcopy__(self, memo):
        self.state["count"] += 1
        if self.state["count"] >= self.fail_at:
            raise self.exc_cls(f"secret={self.secret}")
        new_obj = SecretCrashOnNthDeepcopy(self.fail_at, self.secret, self.exc_cls)
        new_obj.state = self.state
        memo[id(self)] = new_obj
        return new_obj

    def __str__(self):
        return f"SecretCrashOnNthDeepcopy(count={self.state['count']})"

    def __repr__(self):
        return f"SecretCrashOnNthDeepcopy(count={self.state['count']})"


class SecretCrashCapacityAccountingError:
    """Object whose __deepcopy__ raises CapacityAccountingError containing a secret."""

    def __init__(self, secret: str = "sk-custom-cap-error-secret-77777"):
        self.secret = secret

    def __deepcopy__(self, memo):
        raise CapacityAccountingError(f"secret={self.secret}")

    def __str__(self):
        return f"SecretCrashCapacityAccountingError({self.secret})"

    def __repr__(self):
        return f"SecretCrashCapacityAccountingError({self.secret})"


class SecretCrashBudgetExceededError:
    """Object whose __deepcopy__ raises BudgetExceededError containing a secret."""

    def __init__(self, secret: str = "sk-custom-budget-error-secret-88888"):
        self.secret = secret

    def __deepcopy__(self, memo):
        raise BudgetExceededError(f"secret={self.secret}")

    def __str__(self):
        return f"SecretCrashBudgetExceededError({self.secret})"

    def __repr__(self):
        return f"SecretCrashBudgetExceededError({self.secret})"

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

    def test_numeric_and_budget_exceptions_never_leak_secrets(self):
        """Regression test: numeric validation and budget guard exceptions must never leak secrets."""
        import traceback

        raw_private_key = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0r123secretmaterialhere==\n"
            "-----END RSA PRIVATE KEY-----"
        )
        sensitive_cases = [
            ("sk-test-token-value", ["sk-test-token-value"]),
            ("Bearer super-secret-bearer-token-12345", ["super-secret-bearer-token-12345", "Bearer"]),
            (raw_private_key, ["secretmaterialhere", "BEGIN RSA PRIVATE KEY"]),
        ]
        valid_snap = {
            "provider": "9router",
            "project": "AI-Auto-Video-Creator",
            "account": "worker",
            "scope": "worker",
        }
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

        for secret_input, markers in sensitive_cases:
            # 1. CapacityAccounting init
            with self.assertRaises(InvalidNumericError) as cm:
                CapacityAccounting(monthly_budget=secret_input)
            for marker in markers:
                self.assertNotIn(marker, str(cm.exception))
                self.assertNotIn(marker, repr(cm.exception))
                self.assertNotIn(marker, "".join(traceback.format_exception(cm.exception)))
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)

            # 2. CapacityAccounting setter
            acct = CapacityAccounting(monthly_budget=10.0)
            with self.assertRaises(InvalidNumericError) as cm:
                acct.monthly_budget = secret_input
            for marker in markers:
                self.assertNotIn(marker, str(cm.exception))
                self.assertNotIn(marker, repr(cm.exception))
                self.assertNotIn(marker, "".join(traceback.format_exception(cm.exception)))
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)

            # 3. guard_budget
            with self.assertRaises(BudgetExceededError) as cm:
                acct.guard_budget(secret_input)
            for marker in markers:
                self.assertNotIn(marker, str(cm.exception))
                self.assertNotIn(marker, repr(cm.exception))
                self.assertNotIn(marker, "".join(traceback.format_exception(cm.exception)))
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)

            # 4. record_capacity_snapshot limit
            with self.assertRaises(InvalidNumericError) as cm:
                acct.record_capacity_snapshot(**valid_snap, limit=secret_input, used=10)
            for marker in markers:
                self.assertNotIn(marker, str(cm.exception))
                self.assertNotIn(marker, repr(cm.exception))
                self.assertNotIn(marker, "".join(traceback.format_exception(cm.exception)))
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)

            # 5. record_capacity_snapshot used
            with self.assertRaises(InvalidNumericError) as cm:
                acct.record_capacity_snapshot(**valid_snap, limit=10, used=secret_input)
            for marker in markers:
                self.assertNotIn(marker, str(cm.exception))
                self.assertNotIn(marker, repr(cm.exception))
                self.assertNotIn(marker, "".join(traceback.format_exception(cm.exception)))
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)

            # 6. record_cost quantity
            with self.assertRaises(InvalidNumericError) as cm:
                acct.record_cost(**valid_cost, quantity=secret_input)
            for marker in markers:
                self.assertNotIn(marker, str(cm.exception))
                self.assertNotIn(marker, repr(cm.exception))
                self.assertNotIn(marker, "".join(traceback.format_exception(cm.exception)))
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)

            # 7. record_cost estimate
            with self.assertRaises(InvalidNumericError) as cm:
                acct.record_cost(**valid_cost, estimate=secret_input)
            for marker in markers:
                self.assertNotIn(marker, str(cm.exception))
                self.assertNotIn(marker, repr(cm.exception))
                self.assertNotIn(marker, "".join(traceback.format_exception(cm.exception)))
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)

            # 8. record_cost actual
            with self.assertRaises(InvalidNumericError) as cm:
                acct.record_cost(**valid_cost, actual=secret_input)
            for marker in markers:
                self.assertNotIn(marker, str(cm.exception))
                self.assertNotIn(marker, repr(cm.exception))
                self.assertNotIn(marker, "".join(traceback.format_exception(cm.exception)))
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)

    def test_custom_objects_raising_runtime_error_boundary_fail_closed(self):
        """Regression test (C5): objects whose __float__ or __str__ raise RuntimeError must convert to typed error without secret leakage."""
        import traceback

        bad_objects = [
            SecretCrashFloatAndStr("sk-float-and-str-secret-11111"),
            SecretCrashStrOnly("sk-str-only-secret-22222"),
            SecretCrashNoFloat("sk-no-float-secret-33333"),
        ]

        valid_snap = {
            "provider": "9router",
            "project": "AI-Auto-Video-Creator",
            "account": "worker",
            "scope": "worker",
        }
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

        for bad_obj in bad_objects:
            secret_marker = bad_obj.secret

            # 1. _validate_budget_value
            with self.assertRaises(InvalidNumericError) as cm:
                _validate_budget_value(bad_obj)
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            tb_str = "".join(traceback.format_exception(cm.exception))
            self.assertNotIn(secret_marker, tb_str)
            self.assertNotIn("RuntimeError", tb_str)

            # 2. CapacityAccounting constructor budget
            with self.assertRaises(InvalidNumericError) as cm:
                CapacityAccounting(monthly_budget=bad_obj)
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            tb_str = "".join(traceback.format_exception(cm.exception))
            self.assertNotIn(secret_marker, tb_str)
            self.assertNotIn("RuntimeError", tb_str)

            # 3. CapacityAccounting monthly_budget setter
            acct = CapacityAccounting(monthly_budget=10.0)
            with self.assertRaises(InvalidNumericError) as cm:
                acct.monthly_budget = bad_obj
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            tb_str = "".join(traceback.format_exception(cm.exception))
            self.assertNotIn(secret_marker, tb_str)
            self.assertNotIn("RuntimeError", tb_str)

            # 4. _parse_non_negative_finite
            with self.assertRaises(InvalidNumericError) as cm:
                _parse_non_negative_finite(bad_obj, "test_field")
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            tb_str = "".join(traceback.format_exception(cm.exception))
            self.assertNotIn(secret_marker, tb_str)
            self.assertNotIn("RuntimeError", tb_str)

            # 5. guard_budget
            with self.assertRaises(BudgetExceededError) as cm:
                acct.guard_budget(bad_obj)
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            tb_str = "".join(traceback.format_exception(cm.exception))
            self.assertNotIn(secret_marker, tb_str)
            self.assertNotIn("RuntimeError", tb_str)

            # 6. record_capacity_snapshot limit
            with self.assertRaises(InvalidNumericError) as cm:
                acct.record_capacity_snapshot(**valid_snap, limit=bad_obj, used=10)
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            tb_str = "".join(traceback.format_exception(cm.exception))
            self.assertNotIn(secret_marker, tb_str)
            self.assertNotIn("RuntimeError", tb_str)

            # 7. record_capacity_snapshot used
            with self.assertRaises(InvalidNumericError) as cm:
                acct.record_capacity_snapshot(**valid_snap, limit=10, used=bad_obj)
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            tb_str = "".join(traceback.format_exception(cm.exception))
            self.assertNotIn(secret_marker, tb_str)
            self.assertNotIn("RuntimeError", tb_str)

            # 8. record_cost quantity
            with self.assertRaises(InvalidNumericError) as cm:
                acct.record_cost(**valid_cost, quantity=bad_obj)
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            tb_str = "".join(traceback.format_exception(cm.exception))
            self.assertNotIn(secret_marker, tb_str)
            self.assertNotIn("RuntimeError", tb_str)

            # 9. record_cost estimate
            with self.assertRaises(InvalidNumericError) as cm:
                acct.record_cost(**valid_cost, estimate=bad_obj)
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            tb_str = "".join(traceback.format_exception(cm.exception))
            self.assertNotIn(secret_marker, tb_str)
            self.assertNotIn("RuntimeError", tb_str)

            # 10. record_cost actual
            with self.assertRaises(InvalidNumericError) as cm:
                acct.record_cost(**valid_cost, actual=bad_obj)
            self.assertEqual(str(cm.exception), "invalid numeric value (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            tb_str = "".join(traceback.format_exception(cm.exception))
            self.assertNotIn(secret_marker, tb_str)
            self.assertNotIn("RuntimeError", tb_str)

    def test_custom_int_subclass_with_throwing_str_and_repr(self):
        """Regression test (C5): custom int subclass overriding __str__ and __repr__ to throw does not leak or crash."""
        acct = CapacityAccounting(monthly_budget=10.0)
        # Passing SecretCrashIntSubclass should safely convert to primitive int without invoking throwing __str__/__repr__
        safe_quantity = SecretCrashIntSubclass(2)
        safe_estimate = SecretCrashIntSubclass(1)
        safe_actual = SecretCrashIntSubclass(1)

        record = acct.record_cost(
            provider="9router",
            service="codex",
            operation="completion",
            project="AI-Auto-Video-Creator",
            account="worker",
            scope="worker",
            quantity=safe_quantity,
            unit="request",
            estimate=safe_estimate,
            actual=safe_actual,
            currency="USD",
            source="usage_receipt",
            timestamp="2026-10-03T08:00:00Z",
        )
        self.assertEqual(record["quantity"], 2)
        self.assertEqual(record["estimate"], 1)
        self.assertEqual(record["actual"], 1)
        self.assertEqual(acct.cumulative_cost, 1.0)

    def test_numeric_overflow_or_numeric_validation_or_missing_or_empty(self):
        """Directive targeted suite covering numeric overflow, validation, and missing/empty checks."""
        self.test_numeric_overflow_fail_closed()
        self.test_capacity_snapshot_numeric_validation_fail_closed()
        self.test_cost_record_numeric_validation_fail_closed()
        self.test_monthly_budget_nan_and_infinity_fail_closed()
        self.test_capacity_snapshot_missing_or_empty_scope_fail_closed()
        self.test_cost_record_missing_or_empty_provenance_fail_closed()
        self.test_numeric_and_budget_exceptions_never_leak_secrets()
        self.test_custom_objects_raising_runtime_error_boundary_fail_closed()
        self.test_custom_int_subclass_with_throwing_str_and_repr()
        self.test_custom_objects_raising_deepcopy_or_iterator_fail_closed_and_state_unchanged()
        self.test_safe_deepcopy_never_reraises_verbatim_exceptions_and_redacts()
        self.test_record_capacity_snapshot_and_cost_fail_on_third_deepcopy_and_state_unchanged()

    def test_custom_objects_raising_deepcopy_or_iterator_fail_closed_and_state_unchanged(self):
        """Regression test (C6): object with __deepcopy__ or iterator raising RuntimeError containing secret
        must raise typed CapacityAccountingError without secret leakage or context, and leave state/cost/seq unchanged.
        """
        import traceback

        # 1. Test _sanitize_value directly with crashing objects
        deepcopy_secret = "sk-direct-deepcopy-secret-11111"
        iter_secret = "sk-direct-iter-secret-22222"
        iterable_secret = "sk-direct-iterable-secret-33333"

        for bad_obj, secret in [
            (SecretCrashDeepcopy(deepcopy_secret), deepcopy_secret),
            (SecretCrashIterator(iter_secret), iter_secret),
            (SecretCrashIterable(iterable_secret), iterable_secret),
        ]:
            with self.assertRaises(CapacityAccountingError) as cm:
                _sanitize_value(bad_obj)
            self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            tb_str = "".join(traceback.format_exception(cm.exception))
            self.assertNotIn(secret, tb_str)
            self.assertNotIn("RuntimeError", tb_str)

        # 2. Test record_capacity_snapshot with __deepcopy__ throwing object
        acct = CapacityAccounting(monthly_budget=50.0)
        initial_seq = acct._revision_seq
        initial_snapshots_len = len(acct._snapshots)
        initial_revisions_len = len(acct._revisions)

        snap_secret = "sk-snap-deepcopy-secret-44444"
        with self.assertRaises(CapacityAccountingError) as cm:
            acct.record_capacity_snapshot(
                provider="9router",
                project="AI-Auto-Video-Creator",
                account="worker",
                scope="worker",
                custom_bad_field=SecretCrashDeepcopy(snap_secret),
            )
        self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        tb_str = "".join(traceback.format_exception(cm.exception))
        self.assertNotIn(snap_secret, tb_str)
        self.assertNotIn("RuntimeError", tb_str)
        # Verify state/sequence/snapshots unchanged
        self.assertEqual(acct._revision_seq, initial_seq)
        self.assertEqual(len(acct._snapshots), initial_snapshots_len)
        self.assertEqual(len(acct._revisions), initial_revisions_len)

        # 3. Test record_capacity_snapshot with nested __deepcopy__ throwing object
        nested_snap_secret = "sk-nested-snap-secret-55555"
        with self.assertRaises(CapacityAccountingError) as cm:
            acct.record_capacity_snapshot(
                provider="9router",
                project="AI-Auto-Video-Creator",
                account="worker",
                scope="worker",
                metadata={"nested": SecretCrashDeepcopy(nested_snap_secret)},
            )
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        self.assertNotIn(nested_snap_secret, "".join(traceback.format_exception(cm.exception)))
        self.assertEqual(acct._revision_seq, initial_seq)
        self.assertEqual(len(acct._snapshots), initial_snapshots_len)

        # 4. Test record_cost with __deepcopy__ throwing object
        initial_cost = acct.cumulative_cost
        initial_cost_seq = acct._cost_seq
        initial_cost_records_len = len(acct._cost_records)

        cost_secret = "sk-cost-deepcopy-secret-66666"
        with self.assertRaises(CapacityAccountingError) as cm:
            acct.record_cost(
                provider="9router",
                service="codex",
                operation="completion",
                project="AI-Auto-Video-Creator",
                account="worker",
                scope="worker",
                source="usage_receipt",
                timestamp="2026-10-03T08:00:00Z",
                estimate=12.50,
                actual=12.50,
                custom_bad_field=SecretCrashDeepcopy(cost_secret),
            )
        self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        tb_str = "".join(traceback.format_exception(cm.exception))
        self.assertNotIn(cost_secret, tb_str)
        self.assertNotIn("RuntimeError", tb_str)
        # Verify cumulative_cost, cost_seq, and cost_records completely unchanged
        self.assertEqual(acct.cumulative_cost, initial_cost)
        self.assertEqual(acct._cost_seq, initial_cost_seq)
        self.assertEqual(len(acct._cost_records), initial_cost_records_len)

        # 5. Test record_cost with nested __deepcopy__ throwing object
        nested_cost_secret = "sk-nested-cost-secret-77777"
        with self.assertRaises(CapacityAccountingError) as cm:
            acct.record_cost(
                provider="9router",
                service="codex",
                operation="completion",
                project="AI-Auto-Video-Creator",
                account="worker",
                scope="worker",
                source="usage_receipt",
                timestamp="2026-10-03T08:00:00Z",
                estimate=5.0,
                extra={"bad_list": [SecretCrashDeepcopy(nested_cost_secret)]},
            )
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        self.assertNotIn(nested_cost_secret, "".join(traceback.format_exception(cm.exception)))
        self.assertEqual(acct.cumulative_cost, initial_cost)
        self.assertEqual(acct._cost_seq, initial_cost_seq)
        self.assertEqual(len(acct._cost_records), initial_cost_records_len)

        # 6. Test iterator and iterable throwing objects in snapshot and cost
        for bad_iter, sec in [
            (SecretCrashIterator("sk-iter-sec-88888"), "sk-iter-sec-88888"),
            (SecretCrashIterable("sk-iterable-sec-99999"), "sk-iterable-sec-99999"),
        ]:
            with self.assertRaises(CapacityAccountingError) as cm:
                acct.record_capacity_snapshot(
                    provider="9router",
                    project="AI-Auto-Video-Creator",
                    account="worker",
                    scope="worker",
                    custom_iter=bad_iter,
                )
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            self.assertNotIn(sec, "".join(traceback.format_exception(cm.exception)))
            self.assertEqual(acct._revision_seq, initial_seq)

            with self.assertRaises(CapacityAccountingError) as cm:
                acct.record_cost(
                    provider="9router",
                    service="codex",
                    operation="completion",
                    project="AI-Auto-Video-Creator",
                    account="worker",
                    scope="worker",
                    source="usage_receipt",
                    timestamp="2026-10-03T08:00:00Z",
                    estimate=7.0,
                    custom_iter=bad_iter,
                )
            self.assertIsNone(cm.exception.__cause__)
            self.assertIsNone(cm.exception.__context__)
            self.assertNotIn(sec, "".join(traceback.format_exception(cm.exception)))
            self.assertEqual(acct.cumulative_cost, initial_cost)
            self.assertEqual(acct._cost_seq, initial_cost_seq)

        # 7. Verify subsequent valid operations succeed cleanly from preserved state
        valid_snap = acct.record_capacity_snapshot(
            provider="9router",
            model="ag/gemini-3.8-flash-high",
            project="AI-Auto-Video-Creator",
            account="worker",
            scope="worker",
            quota_domain="monthly",
            limit=100,
            used=10,
        )
        self.assertEqual(acct._revision_seq, 1)
        self.assertTrue(valid_snap["revision"].startswith("rev-1-"))
        self.assertEqual(len(acct._snapshots), 1)

        valid_cost = acct.record_cost(
            provider="9router",
            service="codex",
            operation="completion",
            project="AI-Auto-Video-Creator",
            account="worker",
            scope="worker",
            source="usage_receipt",
            timestamp="2026-10-03T08:00:00Z",
            estimate=2.50,
            actual=2.50,
        )
        self.assertEqual(acct._cost_seq, 1)
        self.assertEqual(valid_cost["record_id"], "cost-1")
        self.assertEqual(acct.cumulative_cost, 2.50)
        self.assertEqual(len(acct._cost_records), 1)


    def test_safe_deepcopy_never_reraises_verbatim_exceptions_and_redacts(self):
        """Test that _safe_deepcopy never re-raises CapacityAccountingError, BudgetExceededError,
        or custom exceptions verbatim, and always converts to typed redacted error with from None.
        """
        import traceback
        from controlplane.config.accounting import _safe_deepcopy

        # 1. CapacityAccountingError with secret
        cap_secret = "sk-direct-cap-secret-11111"
        cap_obj = SecretCrashCapacityAccountingError(cap_secret)
        with self.assertRaises(CapacityAccountingError) as cm:
            _safe_deepcopy(cap_obj)
        self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
        self.assertNotIn(cap_secret, repr(cm.exception))
        self.assertNotIn("secret=", repr(cm.exception))
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        tb_str = "".join(traceback.format_exception(cm.exception))
        self.assertNotIn(cap_secret, tb_str)

        # 2. BudgetExceededError with secret
        budget_secret = "sk-direct-budget-secret-22222"
        budget_obj = SecretCrashBudgetExceededError(budget_secret)
        with self.assertRaises(BudgetExceededError) as cm:
            _safe_deepcopy(budget_obj)
        self.assertIsInstance(cm.exception, BudgetExceededError)
        self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
        self.assertNotIn(budget_secret, repr(cm.exception))
        self.assertNotIn("secret=", repr(cm.exception))
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        tb_str = "".join(traceback.format_exception(cm.exception))
        self.assertNotIn(budget_secret, tb_str)

        # 3. RuntimeError with secret
        runtime_secret = "sk-direct-runtime-secret-33333"
        runtime_obj = SecretCrashDeepcopy(runtime_secret)
        with self.assertRaises(CapacityAccountingError) as cm:
            _safe_deepcopy(runtime_obj)
        self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
        self.assertNotIn(runtime_secret, repr(cm.exception))
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        tb_str = "".join(traceback.format_exception(cm.exception))
        self.assertNotIn(runtime_secret, tb_str)

    def test_record_capacity_snapshot_and_cost_fail_on_third_deepcopy_and_state_unchanged(self):
        """Regression test (C7): fail on 3rd deepcopy with RuntimeError or CapacityAccountingError('secret=...').
        Verifies atomicity (state, seq, cost unchanged) and typed redacted error with no secret/context leak.
        """
        import traceback

        acct = CapacityAccounting(monthly_budget=50.0)
        initial_seq = acct._revision_seq
        initial_snapshots_len = len(acct._snapshots)
        initial_revisions_len = len(acct._revisions)
        initial_cost = acct.cumulative_cost
        initial_cost_seq = acct._cost_seq
        initial_cost_records_len = len(acct._cost_records)

        # 1. Snapshot: fail on third deepcopy with RuntimeError containing secret
        snap_secret_rt = "sk-snap-fail3-rt-12345"
        snap_obj_rt = SecretCrashOnNthDeepcopy(fail_at=3, secret=snap_secret_rt, exc_cls=RuntimeError)
        with self.assertRaises(CapacityAccountingError) as cm:
            acct.record_capacity_snapshot(
                provider="9router",
                project="AI-Auto-Video-Creator",
                account="worker",
                scope="worker",
                bad_data=snap_obj_rt,
            )
        self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
        self.assertNotIn(snap_secret_rt, repr(cm.exception))
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        tb_str = "".join(traceback.format_exception(cm.exception))
        self.assertNotIn(snap_secret_rt, tb_str)
        self.assertEqual(acct._revision_seq, initial_seq)
        self.assertEqual(len(acct._snapshots), initial_snapshots_len)
        self.assertEqual(len(acct._revisions), initial_revisions_len)

        # 2. Snapshot: fail on third deepcopy with CapacityAccountingError('secret=...')
        snap_secret_cap = "sk-snap-fail3-cap-67890"
        snap_obj_cap = SecretCrashOnNthDeepcopy(fail_at=3, secret=snap_secret_cap, exc_cls=CapacityAccountingError)
        with self.assertRaises(CapacityAccountingError) as cm:
            acct.record_capacity_snapshot(
                provider="9router",
                project="AI-Auto-Video-Creator",
                account="worker",
                scope="worker",
                bad_data=snap_obj_cap,
            )
        self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
        self.assertNotIn(snap_secret_cap, repr(cm.exception))
        self.assertNotIn("secret=", repr(cm.exception))
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        tb_str = "".join(traceback.format_exception(cm.exception))
        self.assertNotIn(snap_secret_cap, tb_str)
        self.assertEqual(acct._revision_seq, initial_seq)
        self.assertEqual(len(acct._snapshots), initial_snapshots_len)
        self.assertEqual(len(acct._revisions), initial_revisions_len)

        # 3. Snapshot: object directly raising CapacityAccountingError('secret=...') on deepcopy
        snap_secret_direct = "sk-snap-direct-cap-11223"
        snap_obj_direct = SecretCrashCapacityAccountingError(snap_secret_direct)
        with self.assertRaises(CapacityAccountingError) as cm:
            acct.record_capacity_snapshot(
                provider="9router",
                project="AI-Auto-Video-Creator",
                account="worker",
                scope="worker",
                bad_data=snap_obj_direct,
            )
        self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
        self.assertNotIn(snap_secret_direct, repr(cm.exception))
        self.assertNotIn("secret=", repr(cm.exception))
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        tb_str = "".join(traceback.format_exception(cm.exception))
        self.assertNotIn(snap_secret_direct, tb_str)
        self.assertEqual(acct._revision_seq, initial_seq)
        self.assertEqual(len(acct._snapshots), initial_snapshots_len)
        self.assertEqual(len(acct._revisions), initial_revisions_len)

        # 4. Cost: fail on third deepcopy with RuntimeError containing secret
        cost_secret_rt = "sk-cost-fail3-rt-33445"
        cost_obj_rt = SecretCrashOnNthDeepcopy(fail_at=3, secret=cost_secret_rt, exc_cls=RuntimeError)
        with self.assertRaises(CapacityAccountingError) as cm:
            acct.record_cost(
                provider="9router",
                service="codex",
                operation="completion",
                project="AI-Auto-Video-Creator",
                account="worker",
                scope="worker",
                source="usage_receipt",
                timestamp="2026-10-03T08:00:00Z",
                estimate=15.0,
                actual=15.0,
                bad_data=cost_obj_rt,
            )
        self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
        self.assertNotIn(cost_secret_rt, repr(cm.exception))
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        tb_str = "".join(traceback.format_exception(cm.exception))
        self.assertNotIn(cost_secret_rt, tb_str)
        self.assertEqual(acct.cumulative_cost, initial_cost)
        self.assertEqual(acct._cost_seq, initial_cost_seq)
        self.assertEqual(len(acct._cost_records), initial_cost_records_len)
        self.assertEqual(len(acct._revisions), initial_revisions_len)

        # 5. Cost: fail on third deepcopy with CapacityAccountingError('secret=...')
        cost_secret_cap = "sk-cost-fail3-cap-55667"
        cost_obj_cap = SecretCrashOnNthDeepcopy(fail_at=3, secret=cost_secret_cap, exc_cls=CapacityAccountingError)
        with self.assertRaises(CapacityAccountingError) as cm:
            acct.record_cost(
                provider="9router",
                service="codex",
                operation="completion",
                project="AI-Auto-Video-Creator",
                account="worker",
                scope="worker",
                source="usage_receipt",
                timestamp="2026-10-03T08:00:00Z",
                estimate=20.0,
                actual=20.0,
                bad_data=cost_obj_cap,
            )
        self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
        self.assertNotIn(cost_secret_cap, repr(cm.exception))
        self.assertNotIn("secret=", repr(cm.exception))
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        tb_str = "".join(traceback.format_exception(cm.exception))
        self.assertNotIn(cost_secret_cap, tb_str)
        self.assertEqual(acct.cumulative_cost, initial_cost)
        self.assertEqual(acct._cost_seq, initial_cost_seq)
        self.assertEqual(len(acct._cost_records), initial_cost_records_len)
        self.assertEqual(len(acct._revisions), initial_revisions_len)

        # 6. Cost: object directly raising CapacityAccountingError('secret=...') on deepcopy
        cost_secret_direct = "sk-cost-direct-cap-77889"
        cost_obj_direct = SecretCrashCapacityAccountingError(cost_secret_direct)
        with self.assertRaises(CapacityAccountingError) as cm:
            acct.record_cost(
                provider="9router",
                service="codex",
                operation="completion",
                project="AI-Auto-Video-Creator",
                account="worker",
                scope="worker",
                source="usage_receipt",
                timestamp="2026-10-03T08:00:00Z",
                estimate=10.0,
                actual=10.0,
                bad_data=cost_obj_direct,
            )
        self.assertEqual(str(cm.exception), "sanitization failed (fail-closed)")
        self.assertNotIn(cost_secret_direct, repr(cm.exception))
        self.assertNotIn("secret=", repr(cm.exception))
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)
        tb_str = "".join(traceback.format_exception(cm.exception))
        self.assertNotIn(cost_secret_direct, tb_str)
        self.assertEqual(acct.cumulative_cost, initial_cost)
        self.assertEqual(acct._cost_seq, initial_cost_seq)
        self.assertEqual(len(acct._cost_records), initial_cost_records_len)
        self.assertEqual(len(acct._revisions), initial_revisions_len)

        # 7. Verify subsequent valid operations succeed cleanly from preserved state
        valid_snap = acct.record_capacity_snapshot(
            provider="9router",
            model="ag/gemini-3.8-flash-high",
            project="AI-Auto-Video-Creator",
            account="worker",
            scope="worker",
            quota_domain="monthly",
            limit=100,
            used=10,
        )
        self.assertEqual(acct._revision_seq, 1)
        self.assertTrue(valid_snap["revision"].startswith("rev-1-"))
        self.assertEqual(len(acct._snapshots), 1)

        valid_cost = acct.record_cost(
            provider="9router",
            service="codex",
            operation="completion",
            project="AI-Auto-Video-Creator",
            account="worker",
            scope="worker",
            source="usage_receipt",
            timestamp="2026-10-03T08:00:00Z",
            estimate=3.50,
            actual=3.50,
        )
        self.assertEqual(acct._cost_seq, 1)
        self.assertEqual(valid_cost["record_id"], "cost-1")
        self.assertEqual(acct.cumulative_cost, 3.50)
        self.assertEqual(len(acct._cost_records), 1)

# Attach alias so unittest -k "numeric_overflow or numeric_validation or missing_or_empty" executes cleanly
setattr(
    TestProviderCapacityAccounting,
    "test numeric_overflow or numeric_validation or missing_or_empty",
    TestProviderCapacityAccounting.test_numeric_overflow_or_numeric_validation_or_missing_or_empty,
)


if __name__ == "__main__":
    unittest.main()
