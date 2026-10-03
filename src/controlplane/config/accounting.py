"""Bounded P1-C accounting implementation for provider capacity and cost tracking.

Implements CONTRACT-CONFIG-SECURITY (CT-CAP-001, CT-CAP-002, CT-COST-001):
- Immutable capacity snapshots with scope, limits, usage, reset windows, and health.
- Provenance-complete incremental cost records.
- Fail-closed budget guard with typed BudgetExceededError.
- Redacted, immutable revision querying without secret leakage.
"""
from __future__ import annotations

import collections.abc
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
from typing import Any, Optional


class CapacityAccountingError(ValueError):
    """Base typed fail-closed error for capacity and cost accounting."""
    pass


class MissingProvenanceError(CapacityAccountingError):
    """Typed fail-closed error when required provenance or scope fields are missing or empty."""
    pass


class InvalidNumericError(CapacityAccountingError):
    """Typed fail-closed error when a numeric value is invalid, negative, NaN, infinite, or overflows."""
    pass


class BudgetExceededError(CapacityAccountingError):
    """Typed fail-closed reason for an exceeded incremental budget."""
    pass


DISALLOWED_PROVENANCE_PLACEHOLDERS = frozenset({"default", "unknown", "system"})


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


def _safe_deepcopy(val: Any) -> Any:
    failed = False
    is_budget = False
    try:
        return copy.deepcopy(val)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BudgetExceededError:
        failed = True
        is_budget = True
    except (Exception, BaseException):
        failed = True

    if failed:
        err = (
            BudgetExceededError("sanitization failed (fail-closed)")
            if is_budget
            else CapacityAccountingError("sanitization failed (fail-closed)")
        )
        err.__cause__ = None
        err.__context__ = None
        raise err from None


def _is_sensitive_key(key: Any) -> bool:
    clean_k = None
    str_failed = False
    try:
        clean_k = str(key).lower().strip()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        str_failed = True
    if str_failed:
        raise CapacityAccountingError("sanitization failed (fail-closed)") from None
    if clean_k in {"key", "raw_secret", "auth", "authorization", "client_secret"}:
        return True
    return bool(_SENSITIVE_KEY_RE.search(clean_k))


def _sanitize_string_value(val: str) -> str:
    res = None
    sub_failed = False
    try:
        val = _PRIVATE_KEY_RE.sub("[REDACTED PRIVATE KEY]", val)
        val = _BEARER_RE.sub("Bearer [REDACTED]", val)
        val = _ASSIGNMENT_RE.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", val)
        val = _SECRET_TOKEN_RE.sub("[REDACTED]", val)
        val = _JWT_RE.sub("[REDACTED]", val)
        res = val
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        sub_failed = True
    if sub_failed:
        raise CapacityAccountingError("sanitization failed (fail-closed)") from None
    return res


def _sanitize_value(val: Any) -> Any:
    has_secret_attr = False
    attr_failed = False
    try:
        if hasattr(val, "raw_secret"):
            has_secret_attr = True
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        attr_failed = True

    if attr_failed:
        raise CapacityAccountingError("sanitization failed (fail-closed)") from None
    if has_secret_attr:
        return "[REDACTED]"

    if isinstance(val, (str, bytes, bytearray)):
        if isinstance(val, str):
            return _sanitize_string_value(val)
        return _safe_deepcopy(val)

    if isinstance(val, (collections.abc.Mapping, dict)):
        items_failed = False
        items = None
        try:
            items = list(val.items())
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            items_failed = True
        if items_failed:
            raise CapacityAccountingError("sanitization failed (fail-closed)") from None

        res = {}
        for k, v in items:
            is_sens = False
            sens_failed = False
            try:
                is_sens = _is_sensitive_key(k)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                sens_failed = True
            if sens_failed:
                raise CapacityAccountingError("sanitization failed (fail-closed)") from None
            if not is_sens:
                res[k] = _sanitize_value(v)
        return _safe_deepcopy(res)

    if isinstance(val, bool):
        return bool(val)

    if isinstance(val, int):
        int_failed = False
        res_int = 0
        try:
            res_int = int(val)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            int_failed = True
        if int_failed:
            raise CapacityAccountingError("sanitization failed (fail-closed)") from None
        return res_int

    if isinstance(val, float):
        float_failed = False
        res_float = 0.0
        try:
            res_float = float(val)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            float_failed = True
        if float_failed:
            raise CapacityAccountingError("sanitization failed (fail-closed)") from None
        return res_float

    if val is None:
        return None

    if isinstance(val, (list, tuple, set, frozenset, collections.abc.Iterable)):
        iter_failed = False
        items = None
        try:
            items = list(val)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            iter_failed = True
        if iter_failed:
            raise CapacityAccountingError("sanitization failed (fail-closed)") from None

        sanitized = [_sanitize_value(item) for item in items]
        coll_failed = False
        res_coll = None
        try:
            if isinstance(val, (set, frozenset)):
                res_coll = set(sanitized)
            elif isinstance(val, (list, tuple)):
                res_coll = type(val)(sanitized)
            else:
                res_coll = sanitized
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            coll_failed = True
        if coll_failed:
            raise CapacityAccountingError("sanitization failed (fail-closed)") from None
        return _safe_deepcopy(res_coll)

    str_failed = False
    try:
        str(val)
        repr(val)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        str_failed = True
    if str_failed:
        raise CapacityAccountingError("sanitization failed (fail-closed)") from None

    return _safe_deepcopy(val)


def _sanitize_field_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    if isinstance(val, bool):
        return default

    sanitized = _sanitize_value(val)
    str_failed = False
    s = None
    try:
        s = str(sanitized).strip()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        str_failed = True
    if str_failed:
        raise CapacityAccountingError("sanitization failed (fail-closed)") from None

    return _sanitize_string_value(s)


def _validate_required_provenance_field(val: Any, name: str) -> str:
    if val is None:
        raise MissingProvenanceError(f"Missing required field '{name}' (fail-closed)")
    if isinstance(val, bool):
        raise MissingProvenanceError(f"Field '{name}' cannot be boolean (fail-closed)")

    sanitized = _sanitize_value(val)
    str_failed = False
    s = None
    try:
        s = str(sanitized).strip()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        str_failed = True
    if str_failed:
        raise MissingProvenanceError(f"Field '{name}' cannot be parsed (fail-closed)") from None

    if not s:
        raise MissingProvenanceError(f"Field '{name}' cannot be empty (fail-closed)")
    if s.lower() in DISALLOWED_PROVENANCE_PLACEHOLDERS:
        raise MissingProvenanceError(
            f"Field '{name}' cannot use placeholder '{s}' (fail-closed)"
        )
    return _sanitize_string_value(s)


def _validate_budget_value(val: Any, name: str = "monthly_budget") -> float:
    if val is None or isinstance(val, bool):
        raise InvalidNumericError("invalid numeric value (fail-closed)") from None
    converted = False
    budget_val = 0.0
    try:
        budget_val = float(val)
        converted = True
    except Exception:
        pass
    if not converted or not math.isfinite(budget_val) or budget_val < 0.0:
        raise InvalidNumericError("invalid numeric value (fail-closed)") from None
    return budget_val


def _parse_non_negative_finite(val: Any, name: str, default: Optional[float] = 0.0) -> Optional[float | int]:
    if val is None:
        return default
    if isinstance(val, bool):
        raise InvalidNumericError("invalid numeric value (fail-closed)") from None
    converted = False
    num = 0.0
    try:
        num = float(val)
        converted = True
    except Exception:
        pass
    if not converted or not math.isfinite(num) or num < 0.0:
        raise InvalidNumericError("invalid numeric value (fail-closed)") from None
    if type(val) is int:
        return val
    if isinstance(val, int) and not isinstance(val, bool):
        try:
            return int(val)
        except Exception:
            return num
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
        converted = False
        val = 0.0
        try:
            val = float(self._cumulative_cost)
            converted = True
        except Exception:
            pass
        if not converted or not math.isfinite(val):
            raise CapacityAccountingError("invalid numeric value (fail-closed)") from None
        return val

    def record_capacity_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        """Records an immutable provider capacity snapshot without secret leakage (CT-CAP-001)."""
        required_scope_fields = ("provider", "project", "account", "scope")
        validated_fields: dict[str, str] = {}
        for req_f in required_scope_fields:
            if req_f not in kwargs or kwargs[req_f] is None:
                raise MissingProvenanceError(
                    f"Missing required snapshot scope field: '{req_f}' (fail-closed)"
                )
            validated_fields[req_f] = _validate_required_provenance_field(
                kwargs[req_f], req_f
            )

        provider = validated_fields["provider"]
        project = validated_fields["project"]
        account = validated_fields["account"]
        scope = validated_fields["scope"]

        if "account_scope" in kwargs and kwargs["account_scope"] is not None:
            account_scope_val = _validate_required_provenance_field(
                kwargs["account_scope"], "account_scope"
            )
        else:
            account_scope_val = account if account == scope else f"{account}:{scope}"

        model = _sanitize_field_str(kwargs.get("model", ""), "")
        quota_domain = _sanitize_field_str(kwargs.get("quota_domain", "default"), "default")
        health = _sanitize_field_str(kwargs.get("health", "healthy"), "healthy")
        confidence = _sanitize_field_str(kwargs.get("confidence", "observed"), "observed")

        raw_limit = kwargs.get("limit", 0)
        raw_used = kwargs.get("used", kwargs.get("usage", 0))
        limit = _parse_non_negative_finite(raw_limit, "Limit", 0.0)
        used = _parse_non_negative_finite(raw_used, "Used", 0.0)

        raw_reset = kwargs.get("reset_at") or kwargs.get("reset_window", "")
        reset_val = _sanitize_field_str(raw_reset, "")

        next_revision_seq = self._revision_seq + 1

        canonical_payload = {
            "account_scope": account_scope_val,
            "confidence": confidence,
            "health": health,
            "limit": limit,
            "model": model,
            "project": project,
            "provider": provider,
            "quota_domain": quota_domain,
            "reset_at": reset_val,
            "seq": next_revision_seq,
            "used": used,
        }
        json_failed = False
        canonical_json = None
        try:
            canonical_json = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            json_failed = True
        if json_failed:
            raise CapacityAccountingError("serialization failed (fail-closed)") from None

        digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        revision_id = f"rev-{next_revision_seq}-{digest[:16]}"

        snapshot_record: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "project": project,
            "account_scope": account_scope_val,
            "account": account,
            "scope": scope,
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

        stored = _safe_deepcopy(snapshot_record)
        return_record = _safe_deepcopy(stored)

        next_snapshots = list(self._snapshots)
        next_snapshots.append(stored)
        next_revisions = dict(self._revisions)
        next_revisions[revision_id] = stored

        self._revision_seq = next_revision_seq
        self._revisions = next_revisions
        self._snapshots = next_snapshots

        return return_record

    def record_cost(self, **kwargs: Any) -> dict[str, Any]:
        """Records an immutable incremental cost record preserving full provenance (CT-COST-001)."""
        required_provenance = (
            "provider",
            "service",
            "operation",
            "project",
            "account",
            "scope",
            "source",
            "timestamp",
        )
        validated_fields: dict[str, str] = {}
        for req_field in required_provenance:
            if req_field not in kwargs or kwargs[req_field] is None:
                raise MissingProvenanceError(
                    f"Missing required cost provenance field: '{req_field}' (fail-closed)"
                )
            validated_fields[req_field] = _validate_required_provenance_field(
                kwargs[req_field], req_field
            )

        unit = _sanitize_field_str(kwargs.get("unit", "request"), "request")
        currency = _sanitize_field_str(kwargs.get("currency", "USD"), "USD")

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
        calc_ok = False
        new_cumulative_cost = self._cumulative_cost
        try:
            new_cumulative_cost = self._cumulative_cost + Decimal(str(incremental_cost))
            calc_ok = True
        except Exception:
            pass
        if not calc_ok:
            raise CapacityAccountingError("invalid numeric value (fail-closed)") from None

        next_cost_seq = self._cost_seq + 1
        record_id = f"cost-{next_cost_seq}"

        cost_record: dict[str, Any] = {
            "provider": validated_fields["provider"],
            "service": validated_fields["service"],
            "operation": validated_fields["operation"],
            "project": validated_fields["project"],
            "account": validated_fields["account"],
            "scope": validated_fields["scope"],
            "quantity": quantity,
            "unit": unit,
            "estimate": estimate,
            "actual": actual,
            "currency": currency,
            "source": validated_fields["source"],
            "timestamp": validated_fields["timestamp"],
            "record_id": record_id,
        }

        for k, v in kwargs.items():
            if k not in cost_record and not _is_sensitive_key(k):
                cost_record[k] = _sanitize_value(v)

        stored = _safe_deepcopy(cost_record)
        return_record = _safe_deepcopy(stored)

        next_cost_records = list(self._cost_records)
        next_cost_records.append(stored)
        next_revisions = dict(self._revisions)
        next_revisions[record_id] = stored

        self._cumulative_cost = new_cumulative_cost
        self._cost_seq = next_cost_seq
        self._cost_records = next_cost_records
        self._revisions = next_revisions

        return return_record

    def guard_budget(self, amount: float = 0.0) -> None:
        """Enforces fail-closed monthly budget check with typed BudgetExceededError."""
        if amount is None or isinstance(amount, bool):
            raise BudgetExceededError("invalid numeric value (fail-closed)") from None
        converted = False
        numeric_amount = 0.0
        try:
            numeric_amount = float(amount)
            converted = True
        except Exception:
            pass

        if not converted or not math.isfinite(numeric_amount) or numeric_amount < 0.0:
            raise BudgetExceededError("invalid numeric value (fail-closed)") from None

        calc_ok = False
        projected = Decimal("0.0")
        budget_limit = Decimal("0.0")
        try:
            projected = self._cumulative_cost + Decimal(str(numeric_amount))
            budget_limit = Decimal(str(self._monthly_budget))
            calc_ok = True
        except Exception:
            pass

        if not calc_ok:
            raise BudgetExceededError("invalid numeric value (fail-closed)") from None

        try:
            if projected > budget_limit:
                raise BudgetExceededError(
                    f"Budget exceeded (fail-closed): projected cost {float(projected):.4f} "
                    f"exceeds monthly budget {float(budget_limit):.4f} "
                    f"(current={float(self._cumulative_cost):.4f}, requested={numeric_amount:.4f})"
                )
        except BudgetExceededError:
            raise
        except Exception:
            raise BudgetExceededError("invalid numeric value (fail-closed)") from None
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
            if not _is_sensitive_key(k):
                redacted[k] = _sanitize_value(v)

        return _safe_deepcopy(redacted)
