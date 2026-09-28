#!/usr/bin/env python3
"""Validate the proposed parallel-delivery documentation bundle."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "docs" / "parallel-delivery"
REPORT = BUNDLE / ".validation-report.json"
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py", ".toml", ".txt"}
# Specific sequences produced by common UTF-8 double-decoding; ordinary Vietnamese
# text may legitimately contain an isolated U+00C3, so single-character checks are invalid.
MOJIBAKE_PATTERNS = tuple(
    bytes(values).decode("latin-1")
    for values in (
        (0xC3, 0x83, 0xC2),
        (0xC3, 0x82, 0xC2),
        (0xC3, 0x83, 0xC3),
        (0xC3, 0x82, 0xC3),
    )
) + (chr(0x00E2) + chr(0x20AC), chr(0x00C2) + chr(0x00A0))
ALLOWED_CHANGED = {
    "AGENTS.md",
    "CLAUDE.md",
    "HANDOFF.md",
    "README.md",
    "CHANGELOG.md",
    "docs/11-roadmap.md",
    "docs/12-pre-code-checklist.md",
}
REQUIRED_TASK_FIELDS = {
    "id", "milestone", "kind", "status", "authority", "authority_refs",
    "depends_on", "requirement_refs", "contract_refs", "invariant_refs",
    "module_owners", "owned_paths", "forbidden_paths", "resource_locks",
    "runtime_prerequisites", "acceptance", "evidence_outputs", "rollback",
    "route", "merge_priority",
}


def load_yaml(path: Path) -> Any:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to validate YAML") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def check_utf8() -> list[str]:
    errors: list[str] = []
    paths = [ROOT / name for name in ALLOWED_CHANGED if (ROOT / name).exists()]
    paths.extend(p for p in BUNDLE.rglob("*") if p.is_file() and p != REPORT)
    for path in sorted(set(paths)):
        if not path.exists():
            continue
        is_root_text = path.name in {"AGENTS.md", "CLAUDE.md", "HANDOFF.md", "README.md", "CHANGELOG.md"}
        if path.suffix.lower() not in TEXT_SUFFIXES and not is_root_text:
            continue
        raw = path.read_bytes()
        rel = path.relative_to(ROOT).as_posix()
        if raw.startswith(b"\xef\xbb\xbf"):
            errors.append(f"{rel}: UTF-8 BOM is forbidden")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"{rel}: invalid UTF-8: {exc}")
            continue
        for marker in MOJIBAKE_PATTERNS:
            if marker in text:
                errors.append(f"{rel}: mojibake marker {marker!r}")
        for index, char in enumerate(text):
            code = ord(char)
            if code < 32 and char not in "\n\t":
                errors.append(f"{rel}: forbidden control U+{code:04X} at character {index}")
                break
    return errors


def check_task_dag(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tasks = data.get("tasks", [])
    external = data.get("external_nodes", [])
    ids = [entry.get("id") for entry in tasks + external]
    for value, count in Counter(ids).items():
        if not value or count != 1:
            errors.append(f"task id {value!r} occurs {count} times")
    known = set(ids)
    edges: dict[str, list[str]] = defaultdict(list)
    for task in tasks:
        missing = REQUIRED_TASK_FIELDS - set(task)
        if missing:
            errors.append(f"{task.get('id')}: missing fields {sorted(missing)}")
        task_id = task.get("id")
        authority = task.get("authority", {}).get("state")
        if task.get("kind") == "future_template" and authority != "future_template":
            errors.append(f"{task_id}: future template must use future_template authority")
        if task_id in {"M2-P8-LOCKED", "M2-P9-LOCKED"} and authority != "locked":
            errors.append(f"{task_id}: locked sentinel is not locked")
        if authority in {"locked", "future_template", "revoked"} and task.get("owned_paths"):
            errors.append(f"{task_id}: non-granted task owns paths")
        for dep in task.get("depends_on", []):
            dep_id = dep.get("task") if isinstance(dep, dict) else dep
            if dep_id not in known:
                errors.append(f"{task_id}: dangling dependency {dep_id!r}")
            edges[dep_id].append(task_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            errors.append(f"cycle detected at {node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for child in edges.get(node, []):
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in known:
        visit(node)

    allowed_statuses = set(data.get("schema", {}).get("status_enum", []))
    allowed_authority = set(data.get("schema", {}).get("authority_state_enum", []))
    allowed_conditions = set(data.get("schema", {}).get("dependency_condition_enum", []))
    acceptance_fields = set(data.get("schema", {}).get("acceptance_required_fields", []))
    for task in tasks:
        task_id = task.get("id")
        if task.get("status") not in allowed_statuses:
            errors.append(f"{task_id}: invalid status {task.get('status')!r}")
        if task.get("authority", {}).get("state") not in allowed_authority:
            errors.append(f"{task_id}: invalid authority state")
        for dep in task.get("depends_on", []):
            if isinstance(dep, dict) and dep.get("condition") not in allowed_conditions:
                errors.append(f"{task_id}: invalid dependency condition {dep.get('condition')!r}")
        for row in task.get("acceptance", []):
            missing = acceptance_fields - set(row)
            if missing:
                errors.append(f"{task_id}: acceptance row missing {sorted(missing)}")

    task_set = {task.get("id") for task in tasks}
    for wave in data.get("waves", []):
        for task_id in wave.get("task_ids", []):
            if task_id not in task_set:
                errors.append(f"{wave.get('id')}: unknown task {task_id}")
    return errors


def compile_glob(pattern: str) -> re.Pattern[str]:
    translated = re.escape(pattern)
    translated = translated.replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.compile(f"^{translated}$")


def patterns_overlap(left: str, right: str) -> bool:
    if left == right or left == "**" or right == "**":
        return True
    left_wild = any(char in left for char in "*?")
    right_wild = any(char in right for char in "*?")
    if not left_wild and compile_glob(right).fullmatch(left):
        return True
    if not right_wild and compile_glob(left).fullmatch(right):
        return True
    if left_wild and right_wild:
        left_samples = [left.replace("**", "probe/deep").replace("*", "probe").replace("?", "x")]
        right_samples = [right.replace("**", "probe/deep").replace("*", "probe").replace("?", "x")]
        if any(compile_glob(right).fullmatch(sample) for sample in left_samples):
            return True
        if any(compile_glob(left).fullmatch(sample) for sample in right_samples):
            return True
    left_prefix = left.split("*", 1)[0].split("?", 1)[0].rstrip("/")
    right_prefix = right.split("*", 1)[0].split("?", 1)[0].rstrip("/")
    return bool(left_prefix and right_prefix and (left_prefix == right_prefix or left_prefix.startswith(right_prefix + "/") or right_prefix.startswith(left_prefix + "/")))


def source_contract_ids(path: Path) -> set[str]:
    return set(re.findall(r"^### (CT-[A-Z0-9-]+)\b", path.read_text(encoding="utf-8"), re.MULTILINE))


def check_registries(contracts: dict[str, Any], ownership: dict[str, Any], dag: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    contract_records = contracts.get("contracts", [])
    contract_ids = [item.get("id") for item in contract_records]
    lock_ids = [item.get("id") for item in ownership.get("locks", [])]
    for label, values in (("contract", contract_ids), ("lock", lock_ids)):
        for value, count in Counter(values).items():
            if not value or count != 1:
                errors.append(f"{label} id {value!r} occurs {count} times")
    lock_set = set(lock_ids)
    prefix_owners: dict[str, str] = {}
    registry_by_id = {record.get("id"): record for record in contract_records}
    exact_contracts: set[str] = set()
    for contract in contract_records:
        contract_id = contract.get("id")
        if contract.get("lock") not in lock_set:
            errors.append(f"{contract_id}: unknown lock {contract.get('lock')}")
        source = ROOT / str(contract.get("source"))
        if not source.is_file():
            errors.append(f"{contract_id}: missing source {contract.get('source')}")
            continue
        observed_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if contract.get("source_sha256") != observed_hash or contract.get("current_revision") != f"sha256:{observed_hash}":
            errors.append(f"{contract_id}: source revision/hash is not pinned to current bytes")
        observed_ids = source_contract_ids(source)
        exact_contracts.update(observed_ids)
        covered: set[str] = set()
        for prefix in contract.get("id_prefixes", []):
            previous = prefix_owners.setdefault(prefix, contract_id)
            if previous != contract_id:
                errors.append(f"contract prefix {prefix}: owned by {previous} and {contract_id}")
            matches = {value for value in observed_ids if fnmatch.fnmatchcase(value, prefix)}
            if not matches:
                errors.append(f"{contract_id}: prefix {prefix} matches no source contract")
            covered.update(matches)
        missing = observed_ids - covered
        if missing:
            errors.append(f"{contract_id}: source contracts missing from prefixes {sorted(missing)}")
    for module, record in ownership.get("modules", {}).items():
        for lock in record.get("contract_locks", []):
            if lock not in lock_set:
                errors.append(f"module {module}: unknown lock {lock}")

    path_records = ownership.get("path_ownership", [])
    granted = [task for task in dag.get("tasks", []) if task.get("authority", {}).get("state") == "granted"]
    owners: dict[str, str] = {}
    for task in granted:
        task_id = task.get("id")
        requested_locks = set(task.get("resource_locks", []))
        for resource in requested_locks:
            if resource not in lock_set:
                errors.append(f"{task_id}: unknown resource lock {resource}")
            previous = owners.setdefault(resource, task_id)
            if previous != task_id:
                errors.append(f"active lock conflict: {resource} owned by {previous} and {task_id}")
        for owned_path in task.get("owned_paths", []):
            matching_locks = {
                record.get("lock")
                for record in path_records
                if any(patterns_overlap(str(owned_path), str(pattern)) for pattern in record.get("patterns", []))
            }
            if not matching_locks:
                errors.append(f"{task_id}: owned path has no path registry entry: {owned_path}")
            missing_locks = matching_locks - requested_locks
            if missing_locks:
                errors.append(f"{task_id}: owned path {owned_path} missing locks {sorted(missing_locks)}")
        for ref in task.get("contract_refs", []):
            if not isinstance(ref, dict):
                errors.append(f"{task_id}: active contract ref must pin id, registry and revision")
                continue
            registry = registry_by_id.get(ref.get("registry"))
            if registry is None:
                errors.append(f"{task_id}: unknown contract registry {ref.get('registry')}")
                continue
            if ref.get("id") not in exact_contracts:
                errors.append(f"{task_id}: unknown exact contract {ref.get('id')}")
            if not any(fnmatch.fnmatchcase(str(ref.get("id")), prefix) for prefix in registry.get("id_prefixes", [])):
                errors.append(f"{task_id}: contract {ref.get('id')} not owned by {registry.get('id')}")
            if ref.get("revision") != registry.get("current_revision"):
                errors.append(f"{task_id}: contract {ref.get('id')} revision is not frozen")

    for index, left in enumerate(granted):
        for right in granted[index + 1:]:
            for field in ("owned_paths", "evidence_outputs"):
                collisions = [
                    (a, b)
                    for a in left.get(field, [])
                    for b in right.get(field, [])
                    if patterns_overlap(str(a), str(b))
                ]
                if collisions:
                    errors.append(f"active {field} conflict: {left.get('id')} and {right.get('id')} {collisions}")
    return errors


def check_links() -> list[str]:
    errors: list[str] = []
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    paths = [ROOT / "README.md", ROOT / "HANDOFF.md", ROOT / "docs/11-roadmap.md", ROOT / "docs/12-pre-code-checklist.md"]
    paths.extend(BUNDLE.glob("*.md"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for target in pattern.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            clean = target.split("#", 1)[0]
            if clean and not (path.parent / clean).resolve().exists():
                errors.append(f"{path.relative_to(ROOT).as_posix()}: missing link {target}")
    return errors


def changed_paths() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    entries = result.stdout.decode("utf-8", errors="strict").split("\0")
    paths: list[str] = []
    for entry in entries:
        if not entry:
            continue
        path = entry[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.replace("\\", "/"))
    return sorted(paths)


def check_scope(paths: list[str]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        if path == "docs/parallel-delivery/.validation-report.json":
            continue
        if path in ALLOWED_CHANGED or path.startswith("docs/parallel-delivery/"):
            continue
        errors.append(f"changed path outside docs/config scope: {path}")
        if path.startswith(("src/", "tests/")) or path.endswith((".sql", "pyproject.toml", "uv.lock")):
            errors.append(f"prohibited changed path: {path}")
        if "/evidence/" in path:
            errors.append(f"historical evidence changed: {path}")
    return errors


def check_authority(dag: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    granted = [task.get("id") for task in dag.get("tasks", []) if task.get("authority", {}).get("state") == "granted"]
    if granted != ["PD-PILOT-CONTROL"]:
        errors.append(f"unexpected granted tasks: {granted}")
    required = "PROPOSED ARCHITECTURE EXPERIMENT — NO NEW IMPLEMENTATION AUTHORITY"
    for name in ["README.md", "operating-model.md", "protocol.md", "merge-and-integration.md", "traceability.md", "security-performance-recovery.md"]:
        if required not in (BUNDLE / name).read_text(encoding="utf-8"):
            errors.append(f"{name}: missing non-authority banner")
    return errors


def check_dely_block() -> list[str]:
    errors: list[str] = []
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    if text.count("<!-- dely:begin -->") != 1 or text.count("<!-- dely:end -->") != 1:
        errors.append("AGENTS.md must contain exactly one complete Dely block")
    rows = re.findall(r"^\| `(implement|review)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", text, re.MULTILINE)
    expected = [
        ("implement", "Codex CLI", "ag/gemini-3.8-flash-high", "high"),
        ("review", "Claude Code", "cx/gpt-5.6-sol-high", "high"),
    ]
    normalized = [(a, b.strip(), c.strip(), d.strip()) for a, b, c, d in rows]
    if normalized != expected:
        errors.append(f"unexpected Dely rows: {normalized}")
    if (ROOT / "CLAUDE.md").read_text(encoding="utf-8") != "@AGENTS.md\n":
        errors.append("CLAUDE.md must contain only @AGENTS.md")
    return errors


def main() -> int:
    checks: dict[str, list[str]] = {}
    try:
        dag = load_yaml(BUNDLE / "task-dag.yaml")
        contracts = load_yaml(BUNDLE / "contract-registry.yaml")
        ownership = load_yaml(BUNDLE / "ownership-and-locks.yaml")
        checks["yaml_and_task_dag"] = check_task_dag(dag)
        checks["registries_and_locks"] = check_registries(contracts, ownership, dag)
        checks["authority"] = check_authority(dag)
    except Exception as exc:
        checks["yaml_and_task_dag"] = [f"parser failure: {exc}"]
    checks["utf8_and_text"] = check_utf8()
    checks["links"] = check_links()
    paths = changed_paths()
    checks["changed_path_scope"] = check_scope(paths)
    checks["dely_configuration"] = check_dely_block()
    errors = [error for values in checks.values() for error in values]
    report = {
        "schema_version": "1.0.0",
        "status": "PASS" if not errors else "FAIL",
        "checks": {name: {"status": "PASS" if not values else "FAIL", "errors": values} for name, values in checks.items()},
        "changed_paths": paths,
        "bundle_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(BUNDLE.glob("*"))
            if path.is_file() and path != REPORT
        },
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"VALIDATION: FAIL ({len(errors)} errors)")
        return 1
    print(f"VALIDATION: PASS ({len(checks)} checks, {len(paths)} changed paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
