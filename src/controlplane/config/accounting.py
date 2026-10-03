"""Bounded P1-C accounting implementation for provider capacity and cost tracking.

Implements CONTRACT-CONFIG-SECURITY (CT-CAP-001, CT-CAP-002, CT-COST-001):
- Immutable capacity snapshots with scope, limits, usage, reset windows, and health.
- Provenance-complete incremental cost records.
- Fail-closed budget guard with typed BudgetExceededError.
- Redacted, immutable revision querying without secret leakage.
"""
from __future__ import annotations

import copy
from decimal import Decimal
import hashlib
import json
import re
from typing import Any, Optional


class BudgetExceededError(Exception):
    """Typed fail-closed reason for an exceeded incremental budget."""
    pass


_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(token|secret|passwd|password|credential|private[_-]?key|api[_-]?key|client_secret|bearer)"
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.DOTALL
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|secret|access[_-]?token|refresh[_-]?token|api[_-]?key|credential)(\s*[:=]\s*)([^\s,;]+)"
)


def _is_sensitive_key(key: str) -> bool:
    clean_k = str(key).lower().strip()
    if clean_k in {"key", "raw_secret", "auth", "authorization", "client_secret"}:
        return True
    return bool(_SENSITIVE_KEY_RE.search(clean_k))


def _sanitize_string_value(val: str) -> str:
    val = _PRIVATE_KEY_RE.sub("[REDACTED PRIVATE KEY]", val)
    val = _BEARER_RE.sub("Bearer [REDACTED]", val)
    val = _ASSIGNMENT_RE.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", val)
    return val


def _sanitize_value(val: Any) -> Any:
    if hasattr(val, "raw_secret"):
        return "[REDACTED]"
    if isinstance(val, str):
        return _sanitize_string_value(val)
    if isinstance(val, dict):
        return {
            k: _sanitize_value(v)
            for k, v in val.items()
            if not _is_sensitive_key(str(k))
        }
    if isinstance(val, (list, tuple, set)):
        sanitized = [_sanitize_value(item) for item in val]
        return type(val)(sanitized) if not isinstance(val, (set, frozenset)) else set(sanitized)
    return val


class CapacityAccounting:
    """Manages provider capacity snapshots, incremental cost tracking, and budget enforcement."""

    def __init__(self, monthly_budget: float = 0.0) -> None:
        budget_val = float(monthly_budget)
        if budget_val < 0.0:
            raise ValueError("monthly_budget cannot be negative (fail-closed)")
        self._monthly_budget = budget_val
        self._cumulative_cost = Decimal("0.0")
        self._snapshots: list[dict[str, Any]] = []
        self._cost_records: list[dict[str, Any]] = []
        self._revisions: dict[str, dict[str, Any]] = {}
        self._revision_seq: int = 0
        self._cost_seq: int = 0

    @property
    def monthly_budget(self) -> float:
        return self._monthly_budget

    @monthly_budget.setter
    def monthly_budget(self, value: float) -> None:
        budget_val = float(value)
        if budget_val < 0.0:
            raise ValueError("monthly_budget cannot be negative (fail-closed)")
        self._monthly_budget = budget_val

    @property
    def cumulative_cost(self) -> float:
        return float(self._cumulative_cost)

    def record_capacity_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        """Records an immutable provider capacity snapshot without secret leakage (CT-CAP-001)."""
        provider = str(kwargs.get("provider", "default")).strip()
        model = str(kwargs.get("model", "default")).strip()
        project = str(kwargs.get("project", "default")).strip()
        account_scope = str(kwargs.get("account_scope") or kwargs.get("account", "default")).strip()
        quota_domain = str(kwargs.get("quota_domain", "default")).strip()
        health = str(kwargs.get("health", "healthy")).strip()
        confidence = str(kwargs.get("confidence", "observed")).strip()

        raw_limit = kwargs.get("limit", 0)
        raw_used = kwargs.get("used", kwargs.get("usage", 0))
        try:
            limit = float(raw_limit) if raw_limit is not None else 0.0
            used = float(raw_used) if raw_used is not None else 0.0
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Limit and used must be numeric: {exc}") from exc

        if limit < 0.0 or used < 0.0:
            raise ValueError("Limit and used must be non-negative (fail-closed)")

        if isinstance(raw_limit, int) and not isinstance(raw_limit, bool):
            limit = raw_limit
        if isinstance(raw_used, int) and not isinstance(raw_used, bool):
            used = raw_used

        reset_val = str(kwargs.get("reset_at") or kwargs.get("reset_window", "")).strip()

        self._revision_seq += 1

        canonical_payload = {
            "account_scope": account_scope,
            "confidence": confidence,
            "health": health,
            "limit": limit,
            "model": model,
            "project": project,
            "provider": provider,
            "quota_domain": quota_domain,
            "reset_at": reset_val,
            "seq": self._revision_seq,
            "used": used,
        }
        canonical_json = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        revision_id = f"rev-{self._revision_seq}-{digest[:16]}"

        snapshot_record: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "project": project,
            "account_scope": account_scope,
            "account": account_scope,
            "quota_domain": quota_domain,
            "limit": limit,
            "used": used,
            "usage": used,
            "reset_at": reset_val,
            "reset_window": reset_val,
            "health": health,
            "confidence": confidence,
            "revision": revision_id,
        }

        for k, v in kwargs.items():
            if k not in snapshot_record and not _is_sensitive_key(k):
                snapshot_record[k] = _sanitize_value(v)

        stored = copy.deepcopy(snapshot_record)
        self._revisions[revision_id] = stored
        self._snapshots.append(stored)

        return copy.deepcopy(stored)

    def record_cost(self, **kwargs: Any) -> dict[str, Any]:
        """Records an immutable incremental cost record preserving full provenance (CT-COST-001)."""
        provider = str(kwargs.get("provider", "unknown")).strip()
        service = str(kwargs.get("service", "unknown")).strip()
        operation = str(kwargs.get("operation", "unknown")).strip()
        unit = str(kwargs.get("unit", "request")).strip()
        currency = str(kwargs.get("currency", "USD")).strip()
        source = str(kwargs.get("source", "system")).strip()
        timestamp = str(kwargs.get("timestamp", "")).strip()

        raw_quantity = kwargs.get("quantity", 1)
        raw_estimate = kwargs.get("estimate", 0.0)
        raw_actual = kwargs.get("actual")

        try:
            quantity = float(raw_quantity) if raw_quantity is not None else 1.0
            estimate = float(raw_estimate) if raw_estimate is not None else 0.0
            actual = float(raw_actual) if raw_actual is not None else None
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Cost quantity, estimate, and actual must be numeric: {exc}") from exc

        if quantity < 0.0 or estimate < 0.0 or (actual is not None and actual < 0.0):
            raise ValueError("Cost quantity, estimate, and actual must be non-negative (fail-closed)")

        if isinstance(raw_quantity, int) and not isinstance(raw_quantity, bool):
            quantity = raw_quantity
        if isinstance(raw_estimate, int) and not isinstance(raw_estimate, bool):
            estimate = raw_estimate
        if isinstance(raw_actual, int) and not isinstance(raw_actual, bool):
            actual = raw_actual

        incremental_cost = actual if actual is not None else estimate
        self._cumulative_cost += Decimal(str(incremental_cost))

        self._cost_seq += 1
        record_id = f"cost-{self._cost_seq}"

        cost_record: dict[str, Any] = {
            "provider": provider,
            "service": service,
            "operation": operation,
            "quantity": quantity,
            "unit": unit,
            "estimate": estimate,
            "actual": actual,
            "currency": currency,
            "source": _sanitize_string_value(source),
            "timestamp": timestamp,
            "record_id": record_id,
        }

        for k, v in kwargs.items():
            if k not in cost_record and not _is_sensitive_key(k):
                cost_record[k] = _sanitize_value(v)

        stored = copy.deepcopy(cost_record)
        self._cost_records.append(stored)
        self._revisions[record_id] = stored

        return copy.deepcopy(stored)

    def guard_budget(self, amount: float = 0.0) -> None:
        """Enforces fail-closed monthly budget check with typed BudgetExceededError."""
        try:
            numeric_amount = float(amount) if amount is not None else 0.0
        except (TypeError, ValueError) as exc:
            raise BudgetExceededError(f"Invalid budget amount {amount!r} (fail-closed)") from exc

        if numeric_amount < 0.0:
            raise BudgetExceededError(
                f"Negative budget amount {numeric_amount} is rejected (fail-closed)"
            )

        projected = self._cumulative_cost + Decimal(str(numeric_amount))
        budget_limit = Decimal(str(self._monthly_budget))

        if projected > budget_limit:
            raise BudgetExceededError(
                f"Budget exceeded (fail-closed): projected cost {float(projected):.4f} "
                f"exceeds monthly budget {float(budget_limit):.4f} "
                f"(current={float(self._cumulative_cost):.4f}, requested={numeric_amount:.4f})"
            )
        return None

    def revision_view(self, revision: Optional[str] = None) -> dict[str, Any]:
        """Returns a sanitized, redacted, immutable view of the specified revision."""
        if revision is None:
            if not self._snapshots:
                return {}
            target = self._snapshots[-1]
        else:
            if revision not in self._revisions:
                return {}
            target = self._revisions[revision]

        redacted: dict[str, Any] = {}
        for k, v in target.items():
            if not _is_sensitive_key(str(k)):
                redacted[k] = _sanitize_value(v)

        return copy.deepcopy(redacted)