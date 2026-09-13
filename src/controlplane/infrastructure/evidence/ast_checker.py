"""AST-based Architecture Boundary Validator for Control Plane (ADR-0001, ADR-0002).

Enforces strict one-way dependency rules and pure domain isolation:
1. Domain layer (src/controlplane/domain/**) MUST NOT import any external frameworks:
   fastapi, starlette, uvicorn, psycopg, psycopg_pool, temporalio, google, httpx.
2. Domain layer MUST NOT import M1 proof prototype code (m1proof).
3. Domain layer MUST NOT import outer layers (infrastructure, api, ui).
4. No production code in controlplane may import m1proof.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


FORBIDDEN_DOMAIN_EXTERNAL_MODULES = frozenset({
    "fastapi",
    "starlette",
    "uvicorn",
    "psycopg",
    "psycopg_pool",
    "psycopg2",
    "temporalio",
    "google",
    "googleapiclient",
    "google_auth_oauthlib",
    "httpx",
    "flask",
    "django",
    "sqlalchemy",
})

FORBIDDEN_DOMAIN_INTERNAL_LAYERS = frozenset({
    "controlplane.infrastructure",
    "controlplane.api",
    "controlplane.ui",
    "infrastructure",
    "api",
    "ui",
})

M1_PROTOTYPE_MODULES = frozenset({
    "m1proof",
    "src.m1proof",
})


@dataclass(frozen=True)
class BoundaryViolation:
    file_path: str
    line_number: int
    imported_module: str
    rule_violated: str
    message: str


class ArchitectureBoundaryVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path, is_domain_layer: bool) -> None:
        self.file_path = str(file_path)
        self.is_domain_layer = is_domain_layer
        self.violations: list[BoundaryViolation] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_import(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self._check_import(node.module, node.lineno)
        self.generic_visit(node)

    def _check_import(self, module_name: str, lineno: int) -> None:
        top_level = module_name.split(".")[0]

        # Rule 1: No controlplane code may import M1 prototype
        if top_level in M1_PROTOTYPE_MODULES or module_name in M1_PROTOTYPE_MODULES:
            self.violations.append(
                BoundaryViolation(
                    file_path=self.file_path,
                    line_number=lineno,
                    imported_module=module_name,
                    rule_violated="ARCH-RULE-001:NO_M1_PROTOTYPE_IMPORT",
                    message=f"Import of M1 prototype module '{module_name}' is forbidden in production M2 code.",
                )
            )

        # Domain-specific purity rules
        if self.is_domain_layer:
            # Rule 2: Domain must not import external technical frameworks
            if top_level in FORBIDDEN_DOMAIN_EXTERNAL_MODULES:
                self.violations.append(
                    BoundaryViolation(
                        file_path=self.file_path,
                        line_number=lineno,
                        imported_module=module_name,
                        rule_violated="ARCH-RULE-002:DOMAIN_FRAMEWORK_PURITY",
                        message=f"Domain layer must not import external framework/driver '{module_name}'.",
                    )
                )

            # Rule 3: Domain must not import outer layers (infrastructure, api, ui)
            for forbidden_prefix in FORBIDDEN_DOMAIN_INTERNAL_LAYERS:
                if module_name == forbidden_prefix or module_name.startswith(f"{forbidden_prefix}."):
                    self.violations.append(
                        BoundaryViolation(
                            file_path=self.file_path,
                            line_number=lineno,
                            imported_module=module_name,
                            rule_violated="ARCH-RULE-003:DOMAIN_ONE_WAY_DEPENDENCY",
                            message=f"Domain layer must not import outer layer '{module_name}'.",
                        )
                    )


def check_file_boundary(file_path: Path, is_domain_layer: bool) -> list[BoundaryViolation]:
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
    visitor = ArchitectureBoundaryVisitor(file_path, is_domain_layer=is_domain_layer)
    visitor.visit(tree)
    return visitor.violations


def check_source_tree(root_dir: Path) -> list[BoundaryViolation]:
    """Scan all python files in root_dir and check architecture rules."""
    violations: list[BoundaryViolation] = []
    for py_file in root_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts or ".venv" in py_file.parts:
            continue
        is_domain = "domain" in py_file.parts
        violations.extend(check_file_boundary(py_file, is_domain_layer=is_domain))
    return violations
