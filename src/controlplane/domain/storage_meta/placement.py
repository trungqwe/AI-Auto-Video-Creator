"""I-12: chính sách placement lưu trữ theo loại dữ liệu (CT-STO-010, D8-I-09, INV-012)."""
from __future__ import annotations

from dataclasses import dataclass

NO_RULE = "NO_RULE"
UNKNOWN_QUOTA_DOMAIN = "UNKNOWN_QUOTA_DOMAIN"
NO_CAPACITY = "NO_CAPACITY"
INVALID_REF = "INVALID_REF"


class PlacementRejected(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class PlacementRule:
    artifact_kind: str
    namespace_ref: str
    primary_account_ref: str
    fallback_account_refs: tuple[str, ...]


@dataclass(frozen=True)
class StoragePlacementPolicy:
    policy_revision: str
    rules: tuple[PlacementRule, ...]
    quota_domain_by_account: dict[str, str]
    reserve_ratio: float


@dataclass(frozen=True)
class PlacementDecision:
    account_ref: str
    namespace_ref: str
    policy_revision: str
    used_fallback: bool


_FORBIDDEN_REF_MARKERS = ("token=", "secret", "://")


def _check_ref(ref: object) -> None:
    if not isinstance(ref, str) or not ref.strip():
        raise PlacementRejected(INVALID_REF)
    lowered = ref.lower()
    if any(marker in lowered for marker in _FORBIDDEN_REF_MARKERS):
        raise PlacementRejected(INVALID_REF)


def _find_rule(policy: StoragePlacementPolicy, artifact_kind: str) -> PlacementRule:
    matches = [rule for rule in policy.rules if rule.artifact_kind == artifact_kind]
    if not matches:
        raise PlacementRejected(NO_RULE)
    if len(matches) > 1:
        raise ValueError(f"Duplicate placement rule for kind: {artifact_kind}")
    return matches[0]


def decide_placement(
    policy: StoragePlacementPolicy,
    artifact_kind: str,
    size_bytes: int,
    used_bytes_by_quota_domain: dict[str, int],
    capacity_bytes_by_quota_domain: dict[str, int],
) -> PlacementDecision:
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        raise ValueError("size_bytes must be a non-negative integer")
    if not 0.0 <= policy.reserve_ratio <= 1.0:
        raise ValueError("reserve_ratio must be within [0, 1]")
    rule = _find_rule(policy, artifact_kind)
    _check_ref(rule.namespace_ref)
    accounts = (rule.primary_account_ref, *rule.fallback_account_refs)
    domains = []
    for account in accounts:
        _check_ref(account)
        domain = policy.quota_domain_by_account.get(account)
        if domain is None:
            raise PlacementRejected(UNKNOWN_QUOTA_DOMAIN)
        _check_ref(domain)
        if domain not in capacity_bytes_by_quota_domain or domain not in used_bytes_by_quota_domain:
            raise PlacementRejected(UNKNOWN_QUOTA_DOMAIN)
        domains.append(domain)
    for account, domain in zip(accounts, domains):
        limit = capacity_bytes_by_quota_domain[domain] * (1 - policy.reserve_ratio)
        if used_bytes_by_quota_domain[domain] + size_bytes <= limit:
            used_fallback = account != rule.primary_account_ref
            return PlacementDecision(account, rule.namespace_ref, policy.policy_revision, used_fallback)
    raise PlacementRejected(NO_CAPACITY)


__all__ = [
    "INVALID_REF",
    "NO_CAPACITY",
    "NO_RULE",
    "PlacementDecision",
    "PlacementRejected",
    "PlacementRule",
    "StoragePlacementPolicy",
    "UNKNOWN_QUOTA_DOMAIN",
    "decide_placement",
]
