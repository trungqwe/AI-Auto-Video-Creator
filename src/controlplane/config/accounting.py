"""Bounded P1-C accounting implementation for provider capacity and cost tracking.

Implements CONTRACT-CONFIG-SECURITY (CT-CAP-001, CT-CAP-002, CT-COST-001):
- Immutable capacity snapshots with scope, limits, usage, reset windows, and health.
- Provenance-complete incremental cost records.
- Fail-closed budget guard with typed BudgetExceededError.
- Redacted, immutable revision querying without secret leakage.
"""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
from typing import Any, Optional


class BudgetExceededError(Exception):
    """Typed fail-closed reason for an exceeded incremental budget."""
    pass


_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(token|secret|passwd|password|credential|private[_-]?key|api[_-]?key|client_secret|bearer)"
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|$)",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"(?i)\bBearer(?:\s+|[:=]\s*|-)([^\s,;]+)")
_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|secret(?:\s*[_-]?key)?|raw(?:\s*[_-]?secret)?|client(?:\s*[_-]?secret)?|private(?:\s*[_-]?key)?|api(?:\s*[_-]?key)?|access(?:\s*[_-]?token)?|refresh(?:\s*[_-]?token)?|auth(?:\s*[_-]?token)?|bearer(?:\s*[_-]?token)?|credentials?|token)(\s*[:=]\s*)([^\s,;]+)"
)
_SECRET_TOKEN_RE = re.compile(
    r"\b(sk-[a-zA-Z0-9_\-]{8,}|ghp_[a-zA-Z0-9]{20,}|xox[baprs]-[a-zA-Z0-9\-]{10,}|AKIA[0-9A-Z]{16})\b"
)
_JWT_RE = re.compile(
    r"\beyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}(?:\.[a-zA-Z0-9_\-]*)?\b"
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
    val = _SECRET_TOKEN_RE.sub("[REDACTED]", val)
    val = _JWT_RE.sub("[REDACTED]", val)
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


def _sanitize_field_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    sanitized = _sanitize_value(val)
    s = str(sanitized).strip()
    return _sanitize_string_value(s)


def _validate_budget_value(val: Any, name: str = "monthly_budget") -> float:
    if isinstance(val, bool):
        raise ValueError(f"{name} cannot be boolean (fail-closed)")
    try:
        budget_val = float(val)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric (fail-closed): {exc}") from exc
    if not math.isfinite(budget_val) or budget_val < 0.0:
        raise ValueError(f"{name} must be a finite non-negative number (fail-closed)")
    return budget_val


def _parse_non_negative_finite(val: Any, name: str, default: Optional[float] = 0.0) -> Optional[float | int]:
    if val is None:
        return default
    if isinstance(val, bool):
        raise ValueError(f"{name} cannot be boolean (fail-closed)")
    try:
        num = float(val)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric: {exc}") from exc
    if not math.isfinite(num) or num < 0.0:
        raise ValueError(f"{name} must be a finite non-negative number, got {val!r} (fail-closed)")
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    return num


class CapacityAccounting:
    """Manages provider capacity snapshots, incremental cost tracking, and budget enforcement."""

    def __init__(self, monthly_budget: float = 0.0) -> None:
        self._monthly_budget = _validate_budget_value(monthly_budget, "monthly_budget")
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
        self._monthly_budget = _validate_budget_value(value, "monthly_budget")

    @property
    def cumulative_cost(self) -> float:
        return float(self._cumulative_cost)

    def record_capacity_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        """Records an immutable provider capacity snapshot without secret leakage (CT-CAP-001)."""
        provider = _sanitize_field_str(kwargs.get("provider", "default"), "default")
        model = _sanitize_field_str(kwargs.get("model", "default"), "default")
        project = _sanitize_field_str(kwargs.get("project", "default"), "default")
        account_scope = _sanitize_field_str(
            kwargs.get("account_scope") or kwargs.get("account", "default"), "default"
        )
        quota_domain = _sanitize_field_str(kwargs.get("quota_domain", "default"), "default")
        health = _sanitize_field_str(kwargs.get("health", "healthy"), "healthy")
        confidence = _sanitize_field_str(kwargs.get("confidence", "observed"), "observed")

        raw_limit = kwargs.get("limit", 0)
        raw_used = kwargs.get("used", kwargs.get("usage", 0))
        limit = _parse_non_negative_finite(raw_limit, "Limit", 0.0)
        used = _parse_non_negative_finite(raw_used, "Used", 0.0)

        raw_reset = kwargs.get("reset_at") or kwargs.get("reset_window", "")
        reset_val = _sanitize_field_str(raw_reset, "")

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
        provider = _sanitize_field_str(kwargs.get("provider", "unknown"), "unknown")
        service = _sanitize_field_str(kwargs.get("service", "unknown"), "unknown")
        operation = _sanitize_field_str(kwargs.get("operation", "unknown"), "unknown")
        unit = _sanitize_field_str(kwargs.get("unit", "request"), "request")
        currency = _sanitize_field_str(kwargs.get("currency", "USD"), "USD")
        source = _sanitize_field_str(kwargs.get("source", "system"), "system")
        timestamp = _sanitize_field_str(kwargs.get("timestamp", ""), "")

        raw_quantity = kwargs.get("quantity", 1)
        raw_estimate = kwargs.get("estimate", 0.0)
        raw_actual = kwargs.get("actual")

        quantity = _parse_non_negative_finite(raw_quantity, "Cost quantity", 1.0)
        estimate = _parse_non_negative_finite(raw_estimate, "Cost estimate", 0.0)
        actual = (
            _parse_non_negative_finite(raw_actual, "Cost actual", None)
            if raw_actual is not None
            else None
        )

        incremental_cost = actual if actual is not None else estimate
        try:
            self._cumulative_cost += Decimal(str(incremental_cost))
        except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Cost calculation failed (fail-closed): {exc}") from exc

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
            "source": source,
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
        if amount is None or isinstance(amount, bool):
            raise BudgetExceededError(
                f"Invalid budget amount {amount!r}: must be numeric (fail-closed)"
            )
        try:
            numeric_amount = float(amount)
        except (TypeError, ValueError) as exc:
            raise BudgetExceededError(f"Invalid budget amount {amount!r} (fail-closed)") from exc

        if not math.isfinite(numeric_amount):
            raise BudgetExceededError(
                f"Budget amount must be a finite number, got {numeric_amount} (fail-closed)"
            )

        if numeric_amount < 0.0:
            raise BudgetExceededError(
                f"Negative budget amount {numeric_amount} is rejected (fail-closed)"
            )

        try:
            projected = self._cumulative_cost + Decimal(str(numeric_amount))
            budget_limit = Decimal(str(self._monthly_budget))

            if projected > budget_limit:
                raise BudgetExceededError(
                    f"Budget exceeded (fail-closed): projected cost {float(projected):.4f} "
                    f"exceeds monthly budget {float(budget_limit):.4f} "
                    f"(current={float(self._cumulative_cost):.4f}, requested={numeric_amount:.4f})"
                )
        except BudgetExceededError:
            raise
        except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
            raise BudgetExceededError(f"Budget calculation failed (fail-closed): {exc}") from exc
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
