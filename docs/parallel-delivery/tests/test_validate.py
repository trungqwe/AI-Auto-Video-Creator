"""Tests for docs/parallel-delivery/validate.py on the locked stdlib-only runtime."""
from __future__ import annotations

import copy
import importlib.util
import re
import sys
from pathlib import Path

import pytest

BUNDLE = Path(__file__).resolve().parents[1]
ROOT = BUNDLE.parents[1]
if str(BUNDLE) not in sys.path:
    sys.path.insert(0, str(BUNDLE))

import validate  # noqa: E402

REGISTRY_FILES = (
    "task-dag.yaml",
    "contract-registry.yaml",
    "ownership-and-locks.yaml",
    "schedule-policy.yaml",
    "acceptance-matrix.yaml",
)
REVIEW_ROW_RE = re.compile(r"^\| `review` \|.*\|$", re.MULTILINE)


def _dag():
    return validate.load_yaml(BUNDLE / "task-dag.yaml")


def _task(dag, task_id):
    return next(task for task in dag["tasks"] if task["id"] == task_id)


def test_validators_do_not_import_pyyaml():
    for name in ("validate.py", "validate-docs-plan.py"):
        source = (BUNDLE / name).read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import yaml|from yaml\b)", source, re.MULTILINE), name


def test_load_yaml_reads_every_registry_without_pyyaml(monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", None)
    for name in REGISTRY_FILES:
        data = validate.load_yaml(BUNDLE / name)
        assert isinstance(data, dict) and data, name


def test_load_yaml_preserves_registry_values():
    dag = _dag()
    assert dag["schema_version"] == "1.0.0"
    assert dag["as_of"] == "2026-09-28"
    pilot = _task(dag, "PD-PILOT-CONTROL")
    assert pilot["merge_priority"] == 10
    assert pilot["depends_on"] == []
    assert pilot["forbidden_paths"][2] == "**/*.sql"
    assert pilot["acceptance"][0]["requirement"] == (
        "UTF-8 text is valid without BOM and contains no mojibake/control characters."
    )
    assert _task(dag, "M2-P8")["depends_on"] == [{"task": "M2-P7B-ACCEPTED", "condition": "accepted"}]
    green = _task(dag, "TASK-CAP-J-P0-GREEN")
    assert green["acceptance"][0]["red_observation"] == "Ran 3 tests: OK (0 failures, 0 errors, 0 skips)."
    template_route = {"control": "user_checkpoint_required", "implement": "none", "review": "none", "supreme_audit": "none"}
    assert _task(dag, "M4-CI-TEMPLATE")["route"] == template_route
    assert _task(dag, "M5-D-TEMPLATE")["route"] == template_route
    ownership = validate.load_yaml(BUNDLE / "ownership-and-locks.yaml")
    locks = {lock["id"]: lock for lock in ownership["locks"]}
    assert locks["LOCK-ACCEPTED-EVIDENCE"]["lease_seconds"] is None
    assert locks["LOCK-ACCEPTED-EVIDENCE"]["renewable"] is False
    assert locks["LOCK-DESKTOP-GPU"]["capacity"] == 2
    registry = validate.load_yaml(BUNDLE / "contract-registry.yaml")
    page_info = registry["batches_query_contract"]["endpoints"]["list_batches"]["response"]["page_info"]
    assert page_info == {"limit": "integer", "offset": "integer", "has_more": "boolean"}
    schedule = validate.load_yaml(BUNDLE / "schedule-policy.yaml")
    assert schedule["scheduling_rules"]["failure_backoff"]["backoff_multiplier"] == 2.0
    assert schedule["description"].endswith(".\n")
    assert "\n" not in schedule["description"][:-1]


@pytest.mark.parametrize(
    "text",
    ["a:\n\tb: 1\n", "a: [1, 2\n", "a: 1\na: 2\n", "a: *missing\n", "a:\n  b: 1\n c: 2\n", "a: 'open\n"],
)
def test_parse_yaml_text_rejects_malformed_input(text):
    with pytest.raises(validate.YamlLiteError):
        validate.parse_yaml_text(text)


def test_contract_catalog_binds_current_registry():
    catalog = validate.build_contract_catalog_stdlib(BUNDLE / "contract-registry.yaml", ROOT)
    assert catalog["CT-CMN-012"].registry_id == "CONTRACT-COMMON"
    assert catalog["CT-CMN-012"].revision.startswith("sha256:")


def test_contract_catalog_rejects_wrong_source_hash(tmp_path):
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "contracts:\n"
        "  - id: CONTRACT-COMMON\n"
        "    source: docs/09-contracts/00-common-contract.md\n"
        "    source_sha256: " + "f" * 64 + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(validate.ContractBindingError):
        validate.build_contract_catalog_stdlib(registry, ROOT)


def test_check_authority_rejects_granted_template():
    dag = _dag()
    _task(dag, "M3-A-TEMPLATE")["authority"]["state"] = "granted"
    assert any(error.startswith("M3-A-TEMPLATE:") for error in validate.check_authority(dag))


def test_check_authority_rejects_granted_task_without_scope():
    dag = _dag()
    del _task(dag, "M2-P8")["authority"]["scope"]
    assert any(error.startswith("M2-P8:") for error in validate.check_authority(dag))


def test_check_authority_does_not_pin_granted_task_list():
    dag = _dag()
    extra = copy.deepcopy(_task(dag, "M2-P8"))
    extra["id"] = "CP0-EXAMPLE-GRANTED"
    dag["tasks"].append(extra)
    assert validate.check_authority(dag) == []


def _agents_root(tmp_path, text):
    (tmp_path / "AGENTS.md").write_text(text, encoding="utf-8", newline="\n")
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8", newline="\n")
    return tmp_path


def _agents_text():
    return (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def test_check_dely_block_accepts_any_declared_model(tmp_path):
    text = REVIEW_ROW_RE.sub("| `review` | Claude Code | claude-opus-5-5 | high |", _agents_text(), count=1)
    assert text != _agents_text()
    assert validate.check_dely_block(_agents_root(tmp_path, text)) == []


def test_check_dely_block_rejects_missing_review_phase(tmp_path):
    text = REVIEW_ROW_RE.sub("", _agents_text(), count=1)
    errors = validate.check_dely_block(_agents_root(tmp_path, text))
    assert any("'review' exactly once" in error for error in errors), errors


def test_check_dely_block_rejects_blank_effort(tmp_path):
    text = REVIEW_ROW_RE.sub("| `review` | Claude Code | claude-sonnet-5-5 |  |", _agents_text(), count=1)
    errors = validate.check_dely_block(_agents_root(tmp_path, text))
    assert any("empty effort" in error for error in errors), errors


def test_check_dely_block_rejects_missing_fallback_ban(tmp_path):
    text = _agents_text().replace("Do not fall back", "You may fall back")
    assert text != _agents_text()
    errors = validate.check_dely_block(_agents_root(tmp_path, text))
    assert any("Do not fall back" in error for error in errors), errors


TOUCHED_FILES = {
    "AGENTS.md",
    "README.md",
    "HANDOFF.md",
    "CHANGELOG.md",
    "docs/11-roadmap.md",
    "docs/12-pre-code-checklist.md",
    "docs/parallel-delivery/README.md",
    "docs/parallel-delivery/overlay-and-evidence.md",
    "docs/parallel-delivery/merge-and-integration.md",
    "docs/parallel-delivery/ownership-and-locks.yaml",
    "docs/parallel-delivery/task-dag.yaml",
    "docs/parallel-delivery/acceptance-matrix.yaml",
    "docs/parallel-delivery/validate.py",
    "docs/parallel-delivery/validate-docs-plan.py",
    "docs/parallel-delivery/tests/test_validate.py",
}


def _touched(errors):
    return [error for error in errors if error.split(":", 1)[0] in TOUCHED_FILES]


def _docs_plan():
    spec = importlib.util.spec_from_file_location("validate_docs_plan", BUNDLE / "validate-docs-plan.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_docs_plan_yaml_and_cycle_checks_pass_on_current_tree():
    module = _docs_plan()
    assert module.check_yaml_syntax() == []
    assert module.check_dag_cycles() == []


def test_docs_plan_yaml_check_rejects_malformed_registry(tmp_path):
    module = _docs_plan()
    target = tmp_path / "docs" / "parallel-delivery" / "task-dag.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("tasks: [\n", encoding="utf-8", newline="\n")
    module.ROOT = tmp_path
    assert module.check_yaml_syntax()


def test_main_checks_on_current_tree():
    dag = _dag()
    contracts = validate.load_yaml(BUNDLE / "contract-registry.yaml")
    ownership = validate.load_yaml(BUNDLE / "ownership-and-locks.yaml")
    catalog = validate.build_contract_catalog_stdlib(BUNDLE / "contract-registry.yaml", ROOT)
    assert validate.check_authority(dag) == []
    assert validate.check_dely_block() == []
    assert validate.check_lock_leases(ownership, dag) == []
    assert _touched(validate.check_utf8()) == []
    assert _touched(validate.check_canonical_bytes()) == []
    assert _touched(validate.check_links()) == []
    registry_errors = validate.check_registries(contracts, ownership, dag, catalog)
    assert not [e for e in registry_errors if "unknown lock" in e or e.startswith(("lock id", "contract id"))], registry_errors
    owners = set(ownership["modules"]) | {"CROSS-CUTTING-CONTRACT-OWNER"}
    dag_errors = validate.check_task_dag(dag, ownership, catalog, owners, validate.load_known_requirements())
    assert not [e for e in dag_errors if "unknown resource lock" in e or "invalid authority state" in e], dag_errors
