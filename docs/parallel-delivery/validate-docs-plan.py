#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight static validator for Wave/DAG Architecture (DOC-00 to DOC-10).

Validates:
1. Complete existence of DOC-00..DOC-10 deliverable files.
2. YAML syntax of task-dag.yaml, contract-registry.yaml, ownership-and-locks.yaml, schedule-policy.yaml, acceptance-matrix.yaml.
3. DAG acyclicity (no cycles in dependencies).
4. UTF-8 without BOM and canonical LF line endings (no CRLF).
5. No trailing whitespace on any lines of new/modified deliverables.
"""

from collections import defaultdict
import os
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent

DOCS_MANIFEST = {
    "DOC-00": ["DAG-implement-plan.md"],
    "DOC-01": [
        "docs/adr/0013-wave-dag-development.md",
        "docs/parallel-delivery/operating-model.md",
    ],
    "DOC-02": ["docs/parallel-delivery/contract-registry.yaml"],
    "DOC-03": [
        "docs/modules/capability-b-ingestion.md",
        "docs/modules/capability-c-storage.md",
        "docs/modules/capability-d-scripting.md",
        "docs/modules/capability-e-voice.md",
        "docs/modules/capability-f-rendering.md",
        "docs/modules/capability-g-orchestration.md",
        "docs/modules/capability-j-providers.md",
    ],
    "DOC-04": [
        "docs/parallel-delivery/task-dag.yaml",
        "docs/parallel-delivery/ownership-and-locks.yaml",
        "docs/parallel-delivery/schedule-policy.yaml",
    ],
    "DOC-05": [
        "docs/parallel-delivery/acceptance-matrix.yaml",
        "docs/parallel-delivery/traceability.md",
    ],
    "DOC-06": [
        "docs/11-roadmap.md",
        "docs/12-pre-code-checklist.md",
        "README.md",
        "HANDOFF.md",
    ],
    "DOC-07": ["docs/parallel-delivery/validate-docs-plan.py"],
    "DOC-08": ["docs/parallel-delivery/overlay-and-evidence.md"],
    "DOC-09": ["docs/parallel-delivery/preflight-and-acceptance.md"],
    "DOC-10": ["docs/parallel-delivery/runtime-compatibility.md"],
}

YAML_FILES = [
    "docs/parallel-delivery/task-dag.yaml",
    "docs/parallel-delivery/contract-registry.yaml",
    "docs/parallel-delivery/ownership-and-locks.yaml",
    "docs/parallel-delivery/schedule-policy.yaml",
    "docs/parallel-delivery/acceptance-matrix.yaml",
]

NEW_DELIVERABLE_FILES = [
    "DAG-implement-plan.md",
    "docs/adr/0013-wave-dag-development.md",
    "docs/modules/capability-b-ingestion.md",
    "docs/modules/capability-c-storage.md",
    "docs/modules/capability-d-scripting.md",
    "docs/modules/capability-e-voice.md",
    "docs/modules/capability-f-rendering.md",
    "docs/modules/capability-g-orchestration.md",
    "docs/modules/capability-j-providers.md",
    "docs/parallel-delivery/schedule-policy.yaml",
    "docs/parallel-delivery/acceptance-matrix.yaml",
    "docs/parallel-delivery/overlay-and-evidence.md",
    "docs/parallel-delivery/preflight-and-acceptance.md",
    "docs/parallel-delivery/runtime-compatibility.md",
    "docs/parallel-delivery/validate-docs-plan.py",
    "docs/parallel-delivery/contract-registry.yaml",
    "docs/parallel-delivery/task-dag.yaml",
    "docs/parallel-delivery/ownership-and-locks.yaml",
    "docs/parallel-delivery/operating-model.md",
    "docs/parallel-delivery/traceability.md",
    "HANDOFF.md",
]


def check_file_existence() -> list[str]:
  errors = []
  for doc_id, files in DOCS_MANIFEST.items():
    for rel_path in files:
      p = ROOT / rel_path
      if not p.is_file():
        errors.append(f"{doc_id}: missing file {rel_path}")
      elif p.stat().st_size == 0:
        errors.append(f"{doc_id}: file is empty {rel_path}")
  return errors


def check_yaml_syntax() -> list[str]:
  errors = []
  for rel_path in YAML_FILES:
    p = ROOT / rel_path
    if not p.is_file():
      continue
    try:
      raw = p.read_text(encoding="utf-8")
      data = yaml.safe_load(raw)
      if not isinstance(data, dict):
        errors.append(
            f"{rel_path}: YAML root must be a mapping, got"
            f" {type(data).__name__}"
        )
    except Exception as exc:
      errors.append(f"{rel_path}: YAML parse error: {exc}")
  return errors


def check_dag_cycles() -> list[str]:
  errors = []
  dag_path = ROOT / "docs/parallel-delivery/task-dag.yaml"
  if not dag_path.is_file():
    return [f"Cannot check cycles: {dag_path} missing"]

  try:
    data = yaml.safe_load(dag_path.read_text(encoding="utf-8"))
  except Exception as exc:
    return [f"Cannot load task-dag.yaml for cycle check: {exc}"]

  tasks = data.get("tasks", [])
  external = data.get("external_nodes", [])

  all_ids = set()
  edges = defaultdict(list)

  for node in tasks + external:
    nid = node.get("id")
    if nid:
      all_ids.add(nid)

  for task in tasks:
    tid = task.get("id")
    deps = task.get("depends_on", [])
    for dep in deps:
      dep_id = dep.get("task") if isinstance(dep, dict) else dep
      if dep_id:
        edges[dep_id].append(tid)

  visiting = set()
  visited = set()

  def dfs(node: str) -> None:
    if node in visiting:
      errors.append(f"Cycle detected involving task node {node!r}")
      return
    if node in visited:
      return
    visiting.add(node)
    for child in edges.get(node, []):
      dfs(child)
    visiting.remove(node)
    visited.add(node)

  for node in sorted(all_ids):
    dfs(node)

  return errors


def check_whitespace_and_encoding() -> list[str]:
  errors = []

  for rel_path in sorted(NEW_DELIVERABLE_FILES):
    p = ROOT / rel_path
    if not p.is_file():
      continue

    raw_bytes = p.read_bytes()

    # Check BOM
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
      errors.append(
          f"{rel_path}: UTF-8 BOM detected (\\ufeff); exact UTF-8 without BOM"
          " required"
      )

    # Check CRLF
    if b"\r\n" in raw_bytes:
      errors.append(
          f"{rel_path}: CRLF (\\r\\n) detected; exact LF line endings required"
      )

    # Check trailing whitespace on lines
    try:
      text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
      errors.append(f"{rel_path}: invalid UTF-8 encoding: {exc}")
      continue

    lines = text.split("\n")
    for idx, line in enumerate(lines, 1):
      clean_line = line.rstrip("\r")
      if clean_line.rstrip(" \t") != clean_line:
        errors.append(
            f"{rel_path}:{idx}: trailing whitespace detected on line"
        )
        if len(errors) > 20:
          errors.append("... and more trailing whitespace errors (truncated)")
          return errors

  return errors


def main() -> int:
  sys.stdout.reconfigure(encoding="utf-8")
  print("=" * 70)
  print(
      " WAVE/DAG ARCHITECTURE (BỘ 2) - STATIC DOCUMENTATION PLAN VALIDATOR "
  )
  print("=" * 70)

  results = {
      "1. Tồn tại đầy đủ tệp quy hoạch DOC-00..DOC-10": check_file_existence(),
      "2. Cú pháp YAML hợp lệ (task-dag, contracts, locks, schedule, matrix)": (
          check_yaml_syntax()
      ),
      "3. Đồ thị DAG không chu trình (Acyclicity & Topological Order)": (
          check_dag_cycles()
      ),
      "4. Chuẩn hóa Byte (UTF-8 không BOM, LF line endings, không trailing"
      " whitespace trên tệp mới)": check_whitespace_and_encoding(),
  }

  total_errors = 0
  for check_name, errs in results.items():
    if errs:
      print(f"\n[FAIL] {check_name}:")
      for e in errs:
        print(f"  - {e}")
      total_errors += len(errs)
    else:
      print(f"[PASS] {check_name}")

  print("-" * 70)
  if total_errors == 0:
    print(
        "KẾT LUẬN: TẤT CẢ CÁC BÀI KIỂM TRA TĨNH ĐẠT PASS 100% (EXIT CODE 0)\n"
    )
    return 0
  else:
    print(
        f"KẾT LUẬN: PHÁT HIỆN {total_errors} LỖI KIỂM ĐỊNH (EXIT CODE 1)\n"
    )
    return 1


if __name__ == "__main__":
  sys.exit(main())
