"""D-01: creative package skeleton and import boundary (D1).

coveredIds: không
"""
import ast
import importlib
import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PACKAGE_DIR = ROOT / 'src' / 'creative'
SUBPACKAGES = ('domain', 'application', 'ports', 'adapters', 'worker', 'projections')
FORBIDDEN_IMPORT_PREFIXES = (
    'src', 'source_ingestion', 'ingestion', 'catalog', 'voice', 'render', 'psycopg', 'temporalio', 'pydantic',
    'socket', 'urllib.request', 'http.client', 'controlplane.infrastructure', 'controlplane.ui',
    'controlplane.api', 'controlplane.config',
)
FORBIDDEN_DIR_NAMES = frozenset({'storage', 'orchestration', 'ui', 'config'})
DYNAMIC_IMPORT_CALLS = frozenset({'import_module', '__import__'})


def _is_forbidden(name: str) -> bool:
    return any(name == prefix or name.startswith(prefix + '.') for prefix in FORBIDDEN_IMPORT_PREFIXES)


def find_forbidden_imports(source: str, filename: str = '<string>') -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
            names.extend(f'{node.module}.{alias.name}' for alias in node.names)
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            func_name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', None)
            first = node.args[0]
            if func_name in DYNAMIC_IMPORT_CALLS and isinstance(first, ast.Constant) and isinstance(first.value, str):
                names.append(first.value)
    return sorted({name for name in names if _is_forbidden(name)})


def find_forbidden_dirs(base: pathlib.Path) -> list[str]:
    if not base.is_dir():
        return []
    return sorted(
        p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_dir() and p.name in FORBIDDEN_DIR_NAMES
    )


def package_py_files() -> list[pathlib.Path]:
    if not PACKAGE_DIR.is_dir():
        return []
    return sorted(p for p in PACKAGE_DIR.rglob('*.py') if '__pycache__' not in p.parts)


class DetectorSelfTests(unittest.TestCase):
    def test_detector_flags_counterexamples(self) -> None:
        cases = {
            'from src.creative import domain': 'src.creative',
            'import src.creative': 'src.creative',
            'from src import creative': 'src',
            'import source_ingestion': 'source_ingestion',
            'import ingestion': 'ingestion',
            'from catalog.domain import entity': 'catalog.domain',
            'import voice': 'voice',
            'from render import pipeline': 'render.pipeline',
            'import psycopg': 'psycopg',
            'from temporalio import workflow': 'temporalio',
            'import pydantic': 'pydantic',
            'import socket': 'socket',
            'import urllib.request': 'urllib.request',
            'from urllib import request': 'urllib.request',
            'import http.client': 'http.client',
            'from http import client': 'http.client',
            'import controlplane.infrastructure.db': 'controlplane.infrastructure.db',
            'from controlplane.ui import view': 'controlplane.ui',
            'from controlplane import api': 'controlplane.api',
            'from controlplane import config': 'controlplane.config',
            'import controlplane.config.models': 'controlplane.config.models',
            "__import__('voice')": 'voice',
            "importlib.import_module('render.pipeline')": 'render.pipeline',
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertIn(expected, find_forbidden_imports(source))

    def test_detector_allows_boundary_safe_imports(self) -> None:
        for source in (
            'import creative.domain',
            'from . import domain',
            'from controlplane.domain import events',
            'from controlplane.application import service',
            'import dataclasses',
            'import urllib.parse',
            'from urllib import parse',
            'from http import HTTPStatus',
            'import ingestion_tools',
            'import socketserver',
        ):
            with self.subTest(source=source):
                self.assertEqual(find_forbidden_imports(source), [])

    def test_dir_detector_flags_duplicate_trees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            for rel in ('storage', 'adapters/orchestration', 'worker/ui', 'projections/config', 'domain'):
                (base / rel).mkdir(parents=True)
            self.assertEqual(
                find_forbidden_dirs(base), ['adapters/orchestration', 'projections/config', 'storage', 'worker/ui']
            )


class PackageLayoutTests(unittest.TestCase):
    def test_package_importable_from_src_root(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec('creative'), 'creative is not importable from the src/ root')
        module = importlib.import_module('creative')
        self.assertEqual(pathlib.Path(module.__file__).resolve(), PACKAGE_DIR / '__init__.py')
        for name in SUBPACKAGES:
            qualified = f'creative.{name}'
            with self.subTest(subpackage=qualified):
                self.assertIsNotNone(importlib.util.find_spec(qualified), f'{qualified} is not importable')
                sub = importlib.import_module(qualified)
                self.assertEqual(pathlib.Path(sub.__file__).resolve(), PACKAGE_DIR / name / '__init__.py')

    def test_package_inits_are_docstring_only(self) -> None:
        for init in (PACKAGE_DIR / '__init__.py', *(PACKAGE_DIR / name / '__init__.py' for name in SUBPACKAGES)):
            with self.subTest(path=init.relative_to(ROOT).as_posix()):
                self.assertTrue(init.is_file(), f'missing {init.relative_to(ROOT).as_posix()}')
                tree = ast.parse(init.read_text(encoding='utf-8'), filename=str(init))
                self.assertEqual(len(tree.body), 1, 'package __init__ must contain only its docstring')
                self.assertTrue(ast.get_docstring(tree), 'package __init__ must have a non-empty docstring')

    def test_package_modules_have_no_forbidden_imports(self) -> None:
        files = package_py_files()
        self.assertTrue(files, 'src/creative has no Python modules to scan')
        violations = {
            path.relative_to(ROOT).as_posix(): found
            for path in files
            if (found := find_forbidden_imports(path.read_text(encoding='utf-8'), str(path)))
        }
        self.assertEqual(violations, {})

    def test_package_has_no_duplicate_tree_directories(self) -> None:
        self.assertEqual(find_forbidden_dirs(PACKAGE_DIR), [])

    def test_creative_test_dir_has_no_init(self) -> None:
        self.assertFalse((pathlib.Path(__file__).resolve().parent / '__init__.py').exists())

    def test_test_module_declares_covered_ids(self) -> None:
        doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
        self.assertTrue(any(line.startswith('coveredIds:') for line in (doc or '').splitlines()))
