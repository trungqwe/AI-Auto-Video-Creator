"""I-12: chính sách placement theo loại dữ liệu (CT-STO-010, D8-I-09, INV-012)."""
import copy
import dataclasses
import json
import pathlib

import pytest

from controlplane.domain.storage_meta.placement import (
    INVALID_REF,
    NO_CAPACITY,
    NO_RULE,
    UNKNOWN_QUOTA_DOMAIN,
    PlacementDecision,
    PlacementRejected,
    PlacementRule,
    StoragePlacementPolicy,
    decide_placement,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "contracts" / "i-artifact-version" / "payloads.json"
ACCOUNTS = ("acct-a", "acct-b", "acct-c", "acct-d")
CAPACITY = 1000


def _fixture_kind() -> str:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["entities"]["DeclareArtifactVersionRequest"]["valid"][0]["artifact_kind"]


KIND = _fixture_kind()


def _policy(rules=None, quota_domains=None, reserve_ratio=0.25, revision="rev-1") -> StoragePlacementPolicy:
    if rules is None:
        rules = (PlacementRule(KIND, "ns-voice", "acct-a", ("acct-b", "acct-c")),)
    if quota_domains is None:
        quota_domains = {account: f"domain-{account}" for account in ACCOUNTS}
    return StoragePlacementPolicy(revision, rules, quota_domains, reserve_ratio)


def _capacity(policy: StoragePlacementPolicy) -> dict:
    return {domain: CAPACITY for domain in policy.quota_domain_by_account.values()}


def _used(policy: StoragePlacementPolicy, by_account=None) -> dict:
    used = {domain: 0 for domain in policy.quota_domain_by_account.values()}
    for account, value in (by_account or {}).items():
        used[policy.quota_domain_by_account[account]] = value
    return used


def _reject_code(policy, size, used, capacity, kind=KIND) -> str:
    with pytest.raises(PlacementRejected) as exc:
        decide_placement(policy, kind, size, used, capacity)
    return exc.value.code


def test_fixture_kind_voice_has_rule() -> None:
    policy = _policy()
    assert KIND == "voice"
    decision = decide_placement(policy, KIND, 100, _used(policy), _capacity(policy))
    assert decision == PlacementDecision("acct-a", "ns-voice", "rev-1", False)


def test_primary_chosen_up_to_reserve_boundary() -> None:
    policy = _policy()
    used = _used(policy, {"acct-a": 700})
    decision = decide_placement(policy, KIND, 50, used, _capacity(policy))
    assert (decision.account_ref, decision.used_fallback) == ("acct-a", False)


def test_fallback_when_primary_hits_reserve() -> None:
    policy = _policy()
    used = _used(policy, {"acct-a": 701})
    decision = decide_placement(policy, KIND, 50, used, _capacity(policy))
    assert decision == PlacementDecision("acct-b", "ns-voice", "rev-1", True)


def test_fallbacks_are_tried_in_declared_order() -> None:
    policy = _policy()
    used = _used(policy, {"acct-a": 750, "acct-b": 750})
    decision = decide_placement(policy, KIND, 1, used, _capacity(policy))
    assert (decision.account_ref, decision.used_fallback) == ("acct-c", True)


def test_account_outside_rule_is_never_used() -> None:
    policy = _policy()
    used = _used(policy, {"acct-a": 750, "acct-b": 750, "acct-c": 750})
    assert _reject_code(policy, 1, used, _capacity(policy)) == NO_CAPACITY


def test_unknown_kind_is_rejected_without_default_account() -> None:
    policy = _policy()
    for kind in ("unknown-kind", "", "Voice"):
        assert _reject_code(policy, 1, _used(policy), _capacity(policy), kind) == NO_RULE


def test_shared_quota_domain_does_not_add_capacity() -> None:
    policy = _policy(quota_domains={account: "shared" for account in ACCOUNTS})
    capacity = {"shared": CAPACITY}
    decision = decide_placement(policy, KIND, 50, {"shared": 700}, capacity)
    assert (decision.account_ref, decision.used_fallback) == ("acct-a", False)
    assert _reject_code(policy, 51, {"shared": 700}, capacity) == NO_CAPACITY


@pytest.mark.parametrize("case", ["primary", "fallback", "capacity", "used"])
def test_missing_quota_data_is_rejected_even_when_primary_fits(case: str) -> None:
    policy = _policy()
    used = _used(policy)
    capacity = _capacity(policy)
    if case == "primary":
        policy = _policy(quota_domains={"acct-b": "domain-acct-b", "acct-c": "domain-acct-c"})
    elif case == "fallback":
        policy = _policy(quota_domains={"acct-a": "domain-acct-a", "acct-b": "domain-acct-b"})
    elif case == "capacity":
        del capacity["domain-acct-c"]
    else:
        del used["domain-acct-b"]
    assert _reject_code(policy, 1, used, capacity) == UNKNOWN_QUOTA_DOMAIN


BAD_REFS = ["token=abc", "TOKEN=abc", "my-Secret-acct", "drive://folder", "", "   "]


@pytest.mark.parametrize("bad", BAD_REFS)
@pytest.mark.parametrize("position", ["namespace", "primary", "fallback", "domain"])
def test_credential_like_ref_is_rejected(position: str, bad: str) -> None:
    namespace, primary, fallback, domain = "ns-voice", "acct-a", "acct-b", "domain-a"
    if position == "namespace":
        namespace = bad
    elif position == "primary":
        primary = bad
    elif position == "fallback":
        fallback = bad
    else:
        domain = bad
    rules = (PlacementRule(KIND, namespace, primary, (fallback,)),)
    policy = _policy(rules=rules, quota_domains={primary: domain, fallback: "domain-b"})
    used = {domain: 0, "domain-b": 0}
    capacity = {domain: CAPACITY, "domain-b": CAPACITY}
    assert _reject_code(policy, 1, used, capacity) == INVALID_REF


def test_policy_revision_is_copied_into_decision() -> None:
    policy = _policy(revision="rev-42")
    decision = decide_placement(policy, KIND, 1, _used(policy), _capacity(policy))
    assert decision.policy_revision == "rev-42"


def test_rule_is_selected_by_artifact_kind() -> None:
    rules = (
        PlacementRule(KIND, "ns-voice", "acct-a", ("acct-b",)),
        PlacementRule("subtitle", "ns-subtitle", "acct-d", ()),
    )
    policy = _policy(rules=rules)
    used, capacity = _used(policy), _capacity(policy)
    decision = decide_placement(policy, "subtitle", 1, used, capacity)
    assert decision == PlacementDecision("acct-d", "ns-subtitle", "rev-1", False)
    assert decide_placement(policy, KIND, 1, used, capacity).namespace_ref == "ns-voice"


@pytest.mark.parametrize(
    "ratio,size,fits",
    [(0.0, 1000, True), (0.0, 1001, False), (0.5, 500, True), (0.5, 501, False), (1.0, 0, True), (1.0, 1, False)],
)
def test_reserve_ratio_comes_from_policy(ratio: float, size: int, fits: bool) -> None:
    policy = _policy(reserve_ratio=ratio)
    used, capacity = _used(policy), _capacity(policy)
    if fits:
        assert decide_placement(policy, KIND, size, used, capacity).account_ref == "acct-a"
    else:
        assert _reject_code(policy, size, used, capacity) == NO_CAPACITY


@pytest.mark.parametrize("capacity_value", [100, 10**15, 20 * 10**12])
def test_capacity_scale_comes_from_input(capacity_value: int) -> None:
    policy = _policy()
    capacity = {domain: capacity_value for domain in policy.quota_domain_by_account.values()}
    used = _used(policy)
    limit = capacity_value * 3 // 4
    assert decide_placement(policy, KIND, limit, used, capacity).account_ref == "acct-a"
    assert _reject_code(policy, limit + 1, used, capacity) == NO_CAPACITY


def test_account_count_comes_from_rule() -> None:
    names = tuple(f"acct-{index}" for index in range(6))
    rules = (PlacementRule(KIND, "ns-voice", names[0], names[1:]),)
    policy = _policy(rules=rules, quota_domains={name: f"domain-{name}" for name in names})
    used = _used(policy, {name: 750 for name in names[:5]})
    decision = decide_placement(policy, KIND, 1, used, _capacity(policy))
    assert (decision.account_ref, decision.used_fallback) == ("acct-5", True)
    single = _policy(rules=(PlacementRule(KIND, "ns-voice", "acct-a", ()),))
    decision = decide_placement(single, KIND, 1, _used(single), _capacity(single))
    assert (decision.account_ref, decision.used_fallback) == ("acct-a", False)


def test_dataclasses_are_frozen_with_required_fields() -> None:
    expected = {
        PlacementRule: ["artifact_kind", "namespace_ref", "primary_account_ref", "fallback_account_refs"],
        StoragePlacementPolicy: ["policy_revision", "rules", "quota_domain_by_account", "reserve_ratio"],
        PlacementDecision: ["account_ref", "namespace_ref", "policy_revision", "used_fallback"],
    }
    for cls, names in expected.items():
        fields = dataclasses.fields(cls)
        assert [f.name for f in fields] == names
        assert all(f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING for f in fields)
        assert cls.__dataclass_params__.frozen


@pytest.mark.parametrize("size", [-1, True, 1.5, "10"])
def test_invalid_size_raises_value_error(size: object) -> None:
    policy = _policy()
    with pytest.raises(ValueError):
        decide_placement(policy, KIND, size, _used(policy), _capacity(policy))


@pytest.mark.parametrize("ratio", [-0.1, 1.1])
def test_invalid_reserve_ratio_raises_value_error(ratio: float) -> None:
    policy = _policy(reserve_ratio=ratio)
    with pytest.raises(ValueError):
        decide_placement(policy, KIND, 1, _used(policy), _capacity(policy))


def test_duplicate_rule_for_kind_raises_value_error() -> None:
    rules = (PlacementRule(KIND, "ns-1", "acct-a", ()), PlacementRule(KIND, "ns-2", "acct-b", ()))
    policy = _policy(rules=rules)
    with pytest.raises(ValueError):
        decide_placement(policy, KIND, 1, _used(policy), _capacity(policy))


def test_decision_is_pure_and_does_not_mutate_inputs() -> None:
    policy = _policy()
    used = _used(policy, {"acct-a": 701})
    capacity = _capacity(policy)
    before = copy.deepcopy((policy, used, capacity))
    first = decide_placement(policy, KIND, 50, used, capacity)
    second = decide_placement(policy, KIND, 50, used, capacity)
    assert first == second
    assert (policy, used, capacity) == before
