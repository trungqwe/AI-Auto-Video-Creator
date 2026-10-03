"""Projection CapabilityView for Module J under CONTRACT-CONFIG-SECURITY (CT-CAP-003).

Provides:
- Schema-conformant, immutable CapabilityView and CapacityIndicator projections.
- Deterministic, fail-closed status classification:
  * available: valid observation, remaining capacity > 0, healthy state.
  * unavailable: exhausted capacity or health unavailable/revoked/invalid.
  * degraded: degraded health, uncertain quota, or active backoff.
  * unknown: missing identity, invalid timestamp, or non-finite/negative numeric data.
- Exhaustive secret redaction preventing leakage in keys, values, or string representations.
- Multi-observation projection selecting latest observation per capability scope with sequence tie-breaker.
- Input immutability and non-aliasing guarantees.
"""
from __future__ import annotations

import collections.abc
import copy
from datetime import datetime
import math
import re
from typing import Any, Mapping, Optional, Sequence


DISALLOWED_PLACEHOLDERS = frozenset({"default", "unknown", "system", "none", "null"})

_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(token|secret|passwd|password|credential|private[_-]?key|api[_-]?key|client_secret|bearer|authorization|auth)"
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|$)",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"(?i)\bBearer(?:\s+|[:=]\s*|-)([^\s,;]+)")
_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|secret(?:\s*[_-]?key)?|raw(?:\s*[_-]?secret)?|client(?:\s*[_-]?secret)?|private(?:\s*[_-]?key)?|api(?:\s*[_-]?key)?|access(?:\s*[_-]?token)?|refresh(?:\s*[_-]?token)?|auth(?:\s*[_-]?token)?|bearer(?:\s*[_-]?token)?|credentials?|token)(\s*[:=]\s*)([^\s,;]+)"
)
_SECRET_TOKEN_RE = re.compile(r"\b(sk-[a-zA-Z0-9_\-]{8,}|AIza[0-9A-Za-z\-_]{35})\b")


def _is_sensitive_key(key: Any) -> bool:
    try:
        clean_k = str(key).lower().strip()
    except Exception:
        return True
    if clean_k in {"key", "raw_secret", "auth", "authorization", "client_secret", "api_key"}:
        return True
    return bool(_SENSITIVE_KEY_RE.search(clean_k))


def _sanitize_string_value(val: str) -> str:
    try:
        val = _PRIVATE_KEY_RE.sub("[REDACTED PRIVATE KEY]", val)
        val = _BEARER_RE.sub("Bearer [REDACTED]", val)
        val = _ASSIGNMENT_RE.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", val)
        val = _SECRET_TOKEN_RE.sub("[REDACTED]", val)
        return val
    except Exception:
        return "[REDACTED]"


def _sanitize_value(val: Any) -> Any:
    if val is None:
        return None

    try:
        if hasattr(val, "raw_secret"):
            return "[REDACTED]"
    except Exception:
        return "[REDACTED]"

    if isinstance(val, (str, bytes, bytearray)):
        if isinstance(val, str):
            return _sanitize_string_value(val)
        return copy.deepcopy(val)

    if isinstance(val, bool):
        return bool(val)

    if isinstance(val, (int, float)):
        return val

    if isinstance(val, (collections.abc.Mapping, dict)):
        try:
            items = list(val.items())
        except Exception:
            return {}
        res = {}
        for k, v in items:
            if not _is_sensitive_key(k):
                res[k] = _sanitize_value(v)
        return res

    if isinstance(val, (list, tuple, set, frozenset, collections.abc.Iterable)):
        try:
            items = list(val)
        except Exception:
            return []
        sanitized = [_sanitize_value(item) for item in items]
        if isinstance(val, (set, frozenset)):
            return set(sanitized)
        if isinstance(val, tuple):
            return tuple(sanitized)
        return sanitized

    try:
        s = str(val)
        return _sanitize_string_value(s)
    except Exception:
        return "[REDACTED]"


def _parse_timestamp(raw_val: Any) -> Optional[str]:
    if raw_val is None or isinstance(raw_val, bool):
        return None
    try:
        if isinstance(raw_val, (int, float)):
            if not math.isfinite(raw_val) or raw_val <= 0:
                return None
            dt = datetime.utcfromtimestamp(float(raw_val))
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        s = str(raw_val).strip()
        if not s:
            return None
        # Normalize ISO string or validate
        # Check basic ISO 8601 formatting
        # Try datetime parsing
        clean_s = s.replace("Z", "+00:00") if s.endswith("Z") else s
        datetime.fromisoformat(clean_s)
        return _sanitize_string_value(s)
    except Exception:
        return None


def _parse_numeric(val: Any) -> tuple[Optional[float], Optional[str]]:
    """Returns (parsed_value, error_message)."""
    if val is None:
        return (None, "Value is None")
    if isinstance(val, bool):
        return (None, "Boolean value cannot be used as numeric capacity")
    try:
        num = float(val)
    except Exception:
        return (None, f"Cannot convert {val!r} to float")

    if not math.isfinite(num):
        return (None, f"Value must be finite (got {num})")
    if num < 0.0:
        return (None, f"Value cannot be negative (got {num})")
    return (num, None)


class CapacityIndicator:
    """Immutable indicator of capacity metrics recalculating remaining and utilization."""

    __slots__ = ("_limit", "_used", "_remaining", "_utilization", "_confidence")

    def __init__(
        self,
        limit: float = 0.0,
        used: float = 0.0,
        remaining: float = 0.0,
        utilization: float = 0.0,
        confidence: str = "observed",
    ) -> None:
        self._limit = float(limit)
        self._used = float(used)
        self._remaining = float(remaining)
        self._utilization = float(utilization)
        self._confidence = str(confidence)

    @property
    def limit(self) -> float:
        return self._limit

    @property
    def used(self) -> float:
        return self._used

    @property
    def remaining(self) -> float:
        return self._remaining

    @property
    def utilization(self) -> float:
        return self._utilization

    @property
    def confidence(self) -> str:
        return self._confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "limit": self._limit,
            "used": self._used,
            "remaining": self._remaining,
            "utilization": self._utilization,
            "confidence": self._confidence,
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __repr__(self) -> str:
        return (
            f"CapacityIndicator(limit={self._limit}, used={self._used}, "
            f"remaining={self._remaining}, utilization={self._utilization:.4f}, "
            f"confidence={self._confidence!r})"
        )

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, CapacityIndicator):
            return self.to_dict() == other.to_dict()
        if isinstance(other, collections.abc.Mapping):
            return self.to_dict() == dict(other)
        return False


class CapabilityView:
    """Read-only projection representing a point-in-time view of a capability (CT-CAP-003)."""

    VALID_STATUSES = frozenset({"available", "degraded", "unavailable", "unknown"})

    __slots__ = (
        "_capability_id",
        "_capability_type",
        "_location",
        "_provider",
        "_account_scope",
        "_status",
        "_compatible_versions",
        "_capacity",
        "_last_observed_at",
        "_expires_at",
        "_reason",
        "_next_check_at",
        "_dict_cache",
    )

    def __init__(
        self,
        capability_id: str,
        capability_type: str,
        location: str,
        provider: str,
        account_scope: str,
        status: str,
        compatible_versions: Sequence[str],
        capacity: CapacityIndicator,
        last_observed_at: str,
        expires_at: Optional[str] = None,
        reason: Optional[str] = None,
        next_check_at: Optional[str] = None,
    ) -> None:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'; must be one of {sorted(self.VALID_STATUSES)}")

        self._capability_id = str(capability_id)
        self._capability_type = str(capability_type)
        self._location = str(location)
        self._provider = str(provider)
        self._account_scope = str(account_scope)
        self._status = str(status)
        self._compatible_versions = tuple(str(v) for v in compatible_versions)
        self._capacity = capacity
        self._last_observed_at = str(last_observed_at)
        self._expires_at = str(expires_at) if expires_at is not None else None
        self._reason = str(reason) if reason is not None else None
        self._next_check_at = str(next_check_at) if next_check_at is not None else None
        self._dict_cache: Optional[dict[str, Any]] = None

    @property
    def capability_id(self) -> str:
        return self._capability_id

    @property
    def capability_type(self) -> str:
        return self._capability_type

    @property
    def location(self) -> str:
        return self._location

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def account_scope(self) -> str:
        return self._account_scope

    @property
    def status(self) -> str:
        return self._status

    @property
    def compatible_versions(self) -> tuple[str, ...]:
        return self._compatible_versions

    @property
    def capacity(self) -> CapacityIndicator:
        return self._capacity

    @property
    def last_observed_at(self) -> str:
        return self._last_observed_at

    @property
    def expires_at(self) -> Optional[str]:
        return self._expires_at

    @property
    def reason(self) -> Optional[str]:
        return self._reason

    @property
    def next_check_at(self) -> Optional[str]:
        return self._next_check_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self._capability_id,
            "capability_type": self._capability_type,
            "location": self._location,
            "provider": self._provider,
            "account_scope": self._account_scope,
            "status": self._status,
            "compatible_versions": list(self._compatible_versions),
            "capacity": self._capacity.to_dict(),
            "last_observed_at": self._last_observed_at,
            "expires_at": self._expires_at,
            "reason": self._reason,
            "next_check_at": self._next_check_at,
        }

    def __getitem__(self, item: str) -> Any:
        d = self.to_dict()
        if item in d:
            return d[item]
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return item in self.to_dict()

    def get(self, item: str, default: Any = None) -> Any:
        return self.to_dict().get(item, default)

    def keys(self) -> collections.abc.KeysView[str]:
        return self.to_dict().keys()

    def values(self) -> collections.abc.ValuesView[Any]:
        return self.to_dict().values()

    def items(self) -> collections.abc.ItemsView[str, Any]:
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __repr__(self) -> str:
        return (
            f"CapabilityView(capability_id={self._capability_id!r}, "
            f"capability_type={self._capability_type!r}, "
            f"provider={self._provider!r}, status={self._status!r}, "
            f"capacity={self._capacity!r})"
        )

    def __str__(self) -> str:
        return (
            f"<CapabilityView id={self._capability_id} provider={self._provider} "
            f"status={self._status} remaining={self._capacity.remaining}>"
        )

    @classmethod
    def from_observation(cls, observation: Mapping[str, Any]) -> "CapabilityView":
        return build_capability_view(observation)

    @classmethod
    def project_latest(cls, observations: Sequence[Mapping[str, Any]]) -> list["CapabilityView"]:
        return project_latest_capability_views(observations)


def _validate_identity_str(val: Any) -> tuple[Optional[str], Optional[str]]:
    """Validates required identity string fields; rejects empty, bool or placeholders."""
    if val is None:
        return (None, "Missing required identity value (None)")
    if isinstance(val, bool):
        return (None, "Identity value cannot be boolean")
    try:
        s = str(val).strip()
    except Exception:
        return (None, "Identity value cannot be converted to string")

    if not s:
        return (None, "Identity value cannot be empty")
    if s.lower() in DISALLOWED_PLACEHOLDERS:
        return (None, f"Identity value cannot use disallowed placeholder '{s}'")
    return (_sanitize_string_value(s), None)


def build_capability_view(observation: Mapping[str, Any]) -> CapabilityView:
    """Builds a projected CapabilityView from a raw observation mapping (CT-CAP-003).

    Performs:
    1. Input sanitization without modifying the input mapping.
    2. Identity extraction and fail-closed validation.
    3. Timestamp parsing and validation.
    4. Capacity recalculation (remaining = max(0.0, limit - used), utilization).
    5. Deterministic status classification (available, degraded, unavailable, unknown).
    6. Complete redaction of any sensitive keys/values.
    """
    if not isinstance(observation, collections.abc.Mapping):
        return CapabilityView(
            capability_id="unknown:unknown:unknown",
            capability_type="unknown",
            location="unknown",
            provider="unknown",
            account_scope="unknown",
            status="unknown",
            compatible_versions=(),
            capacity=CapacityIndicator(0.0, 0.0, 0.0, 0.0, "unreliable"),
            last_observed_at="",
            reason="Observation must be a mapping",
        )

    fail_closed_reasons: list[str] = []

    # 1. Identity validation
    raw_provider = observation.get("provider")
    provider, err = _validate_identity_str(raw_provider)
    if err:
        fail_closed_reasons.append(f"provider: {err}")

    raw_scope = observation.get("account_scope") or observation.get("scope") or observation.get("account")
    account_scope, err = _validate_identity_str(raw_scope)
    if err:
        fail_closed_reasons.append(f"account_scope: {err}")

    raw_type = observation.get("capability_type") or observation.get("type") or observation.get("activity_type")
    capability_type, err = _validate_identity_str(raw_type)
    if err:
        fail_closed_reasons.append(f"capability_type: {err}")

    raw_cap_id = observation.get("capability_id") or observation.get("id")
    capability_id: Optional[str] = None
    if raw_cap_id is not None:
        capability_id, err = _validate_identity_str(raw_cap_id)
        if err:
            fail_closed_reasons.append(f"capability_id: {err}")
    elif provider and capability_type and account_scope:
        capability_id = f"{provider}:{capability_type}:{account_scope}"
    else:
        capability_id = "unknown"

    raw_location = observation.get("location", "cloud")
    location, loc_err = _validate_identity_str(raw_location)
    if loc_err:
        location = "cloud"

    # 2. Timestamp validation
    raw_observed = (
        observation.get("last_observed_at")
        or observation.get("observed_at")
        or observation.get("timestamp")
        or observation.get("heartbeat_at")
    )
    last_observed_at = _parse_timestamp(raw_observed)
    if not last_observed_at:
        fail_closed_reasons.append("last_observed_at: missing or invalid timestamp")

    raw_expires = observation.get("expires_at") or observation.get("expiry")
    expires_at = _parse_timestamp(raw_expires) if raw_expires is not None else None

    raw_next_check = observation.get("next_check_at") or observation.get("next_probe_at") or observation.get("reset_at")
    next_check_at = _parse_timestamp(raw_next_check) if raw_next_check is not None else None

    # 3. Numeric capacity validation and recalculation
    raw_limit = observation.get("limit", 0.0)
    limit, limit_err = _parse_numeric(raw_limit)
    if limit_err:
        fail_closed_reasons.append(f"limit: {limit_err}")

    raw_used = observation.get("used", observation.get("usage", 0.0))
    used, used_err = _parse_numeric(raw_used)
    if used_err:
        fail_closed_reasons.append(f"used: {used_err}")

    raw_confidence = observation.get("confidence", "observed")
    try:
        confidence = _sanitize_string_value(str(raw_confidence).strip())
    except Exception:
        confidence = "uncertain"

    # 4. Status determination
    status: str = "unknown"
    reason: Optional[str] = None

    if fail_closed_reasons:
        status = "unknown"
        reason = "; ".join(fail_closed_reasons)
        capacity = CapacityIndicator(
            limit=limit if limit is not None else 0.0,
            used=used if used is not None else 0.0,
            remaining=0.0,
            utilization=0.0,
            confidence="unreliable",
        )
    else:
        assert limit is not None and used is not None
        remaining = max(0.0, limit - used)
        utilization = (used / limit) if limit > 0.0 else 0.0

        capacity = CapacityIndicator(
            limit=limit,
            used=used,
            remaining=remaining,
            utilization=utilization,
            confidence=confidence,
        )

        health_raw = str(observation.get("health", "healthy")).lower().strip()
        is_backoff = bool(
            observation.get("backoff_active")
            or observation.get("in_backoff")
            or observation.get("rate_limited")
        )
        is_uncertain = (
            confidence.lower() in {"uncertain", "estimated", "unreliable", "low", "stale"}
            or bool(observation.get("is_quota_uncertain"))
        )

        if health_raw in {"unavailable", "revoked", "invalid", "unhealthy", "offline", "down"}:
            status = "unavailable"
            reason = f"Provider health is '{health_raw}'"
        elif limit > 0.0 and remaining <= 0.0:
            status = "unavailable"
            reason = "Capacity exhausted"
        elif health_raw in {"degraded", "warning", "slow", "high_latency", "elevated_error"}:
            status = "degraded"
            reason = f"Provider health is degraded ({health_raw})"
        elif is_uncertain:
            status = "degraded"
            reason = f"Quota confidence is uncertain ({confidence})"
        elif is_backoff:
            status = "degraded"
            reason = "Active backoff or rate limiting in effect"
        else:
            status = "available"
            raw_reason = observation.get("reason")
            reason = _sanitize_string_value(str(raw_reason).strip()) if raw_reason else None

    # Compatible versions
    raw_versions = observation.get("compatible_versions") or observation.get("versions") or []
    compatible_versions: list[str] = []
    if isinstance(raw_versions, (list, tuple, set)):
        for v in raw_versions:
            if not _is_sensitive_key(v):
                clean_v = _sanitize_string_value(str(v).strip())
                if clean_v:
                    compatible_versions.append(clean_v)

    return CapabilityView(
        capability_id=capability_id or "unknown",
        capability_type=capability_type or "unknown",
        location=location or "cloud",
        provider=provider or "unknown",
        account_scope=account_scope or "unknown",
        status=status,
        compatible_versions=compatible_versions,
        capacity=capacity,
        last_observed_at=last_observed_at or "",
        expires_at=expires_at,
        reason=reason,
        next_check_at=next_check_at,
    )


def _get_scope_key(obs: Mapping[str, Any]) -> str:
    """Extracts a unique capability scope key for projection grouping."""
    cap_id = obs.get("capability_id") or obs.get("id")
    if cap_id:
        return str(cap_id).strip()
    provider = str(obs.get("provider", "")).strip()
    cap_type = str(obs.get("capability_type") or obs.get("type", "")).strip()
    scope = str(obs.get("account_scope") or obs.get("scope") or obs.get("account", "")).strip()
    return f"{provider}:{cap_type}:{scope}"


def _get_sequence_number(obs: Mapping[str, Any]) -> int:
    """Extracts sequence number tie-breaker, defaulting to 0."""
    raw_seq = obs.get("sequence", obs.get("seq", obs.get("revision_seq", 0)))
    try:
        return int(raw_seq)
    except Exception:
        return 0


def _get_observation_time_key(obs: Mapping[str, Any]) -> str:
    """Extracts comparable observation timestamp string."""
    raw_time = (
        obs.get("last_observed_at")
        or obs.get("observed_at")
        or obs.get("timestamp")
        or obs.get("heartbeat_at")
    )
    parsed = _parse_timestamp(raw_time)
    return parsed or ""


def project_latest_capability_views(
    observations: Sequence[Mapping[str, Any]],
) -> list[CapabilityView]:
    """Projects latest capability views per scope without mutating source records.

    Selection rules:
    1. Group observations by capability scope.
    2. Select observation with newest observed_at timestamp.
    3. In case of equal timestamp, choose observation with higher sequence.
    4. Deterministically sort projected views by capability_id.
    """
    if not observations:
        return []

    latest_by_scope: dict[str, Mapping[str, Any]] = {}

    for obs in observations:
        if not isinstance(obs, collections.abc.Mapping):
            continue
        scope = _get_scope_key(obs)
        if scope not in latest_by_scope:
            latest_by_scope[scope] = obs
            continue

        existing = latest_by_scope[scope]
        existing_time = _get_observation_time_key(existing)
        new_time = _get_observation_time_key(obs)

        if new_time > existing_time:
            latest_by_scope[scope] = obs
        elif new_time == existing_time:
            existing_seq = _get_sequence_number(existing)
            new_seq = _get_sequence_number(obs)
            if new_seq > existing_seq:
                latest_by_scope[scope] = obs

    projected = [build_capability_view(obs) for obs in latest_by_scope.values()]
    projected.sort(key=lambda v: v.capability_id)
    return projected


def project_capability_views(
    observations: Sequence[Mapping[str, Any]],
) -> list[CapabilityView]:
    """Alias for project_latest_capability_views."""
    return project_latest_capability_views(observations)
