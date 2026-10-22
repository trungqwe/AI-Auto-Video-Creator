"""F-01: render package skeleton and import boundary (D1).

coveredIds: không
"""
import ast
import importlib
import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PACKAGE_DIR = ROOT / 'src' / 'render'
SUBPACKAGES = ('domain', 'application', 'ports', 'adapters', 'worker', 'projections')
FORBIDDEN_IMPORT_PREFIXES = (
    'src', 'creative', 'voice', 'catalog', 'ingestion', 'source_ingestion', 'psycopg', 'temporalio', 'pydantic',
    'socket', 'subprocess', 'os', 'shutil', 'tempfile', 'urllib.request', 'http.client',
    'controlplane.infrastructure', 'controlplane.ui', 'controlplane.api', 'controlplane.config',
)
FORBIDDEN_DIR_NAMES = frozenset({'storage', 'orchestration', 'ui', 'config'})
FORBIDDEN_CALL_ATTRS = frozenset({'unlink', 'rmdir', 'rmtree', 'remove', 'rename', 'truncate'})
FORBIDDEN_FUNCTION_PREFIXES = ('delete_', 'cleanup_', 'remove_')
DYNAMIC_IMPORT_CALLS = frozenset({'import_module', '__import__'})

# Miễn trừ hẹp theo kế hoạch ADAPT đã duyệt: docs/implementation/adapt/plan.md dòng 84 và 123-124 (ADAPT-F: subprocess.run, os.replace, xoá tệp tạm).
# Khoá là đường dẫn tệp chính xác tính từ src/render (posix), không dùng mẫu, không miễn cả thư mục adapters; giá trị là đúng chuỗi phát hiện của scan_package.
ADAPTER_EXEMPTIONS = {
    'adapters/real_ffmpeg_renderer.py': frozenset({'import:os', 'import:subprocess', 'call:unlink'}),
    'adapters/real_ffprobe_probe.py': frozenset({'import:subprocess'}),
}

# Miễn trừ theo thư mục theo kế hoạch PERSIST đã duyệt: docs/implementation/persist/plan.md dòng 15 và 40-41.
# Chỉ tệp dưới persistence/ (tính từ src/render) được import hai tiền tố này (adapter PostgreSQL, TransactionManager, outbox controlplane);
# mọi tiền tố cấm khác, mục 'call:' và 'def:' vẫn bị báo cho các tệp đó, và tệp ngoài persistence không đổi.
PERSISTENCE_IMPORT_PREFIXES = ('psycopg', 'controlplane.infrastructure.db')


def _is_forbidden(name: str) -> bool:
    return any(name == prefix or name.startswith(prefix + '.') for prefix in FORBIDDEN_IMPORT_PREFIXES)


def _is_persistence_import(name: str) -> bool:
    return any(name == prefix or name.startswith(prefix + '.') for prefix in PERSISTENCE_IMPORT_PREFIXES)


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


def find_forbidden_calls(source: str, filename: str = '<string>') -> list[str]:
    attrs: set[str] = set()
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_CALL_ATTRS:
            attrs.add(node.func.attr)
    return sorted(attrs)


def find_forbidden_functions(source: str, filename: str = '<string>') -> list[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(FORBIDDEN_FUNCTION_PREFIXES):
            names.add(node.name)
    return sorted(names)


def find_forbidden_dirs(base: pathlib.Path) -> list[str]:
    if not base.is_dir():
        return []
    return sorted(
        p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_dir() and p.name in FORBIDDEN_DIR_NAMES
    )


def package_py_files(base: pathlib.Path = PACKAGE_DIR) -> list[pathlib.Path]:
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob('*.py') if '__pycache__' not in p.parts)


def scan_package(
    base: pathlib.Path = PACKAGE_DIR, exemptions: dict[str, frozenset[str]] = ADAPTER_EXEMPTIONS
) -> dict[str, list[str]]:
    violations: dict[str, list[str]] = {}
    for path in package_py_files(base):
        source = path.read_text(encoding='utf-8')
        rel = path.relative_to(base).as_posix()
        in_persistence = rel.startswith('persistence/')
        found = [
            f'import:{name}'
            for name in find_forbidden_imports(source, str(path))
            if not (in_persistence and _is_persistence_import(name))
        ]
        found += [f'call:{name}' for name in find_forbidden_calls(source, str(path))]
        found += [f'def:{name}' for name in find_forbidden_functions(source, str(path))]
        allowed = exemptions.get(rel, frozenset())
        found = [item for item in found if item not in allowed]
        if found:
            violations[rel] = found
    return violations


class DetectorSelfTests(unittest.TestCase):
    def test_detector_flags_import_counterexamples(self) -> None:
        cases = {
            'from src.render import domain': 'src.render',
            'import src.render': 'src.render',
            'from src import render': 'src',
            'import creative': 'creative',
            'import voice': 'voice',
            'from catalog.domain import entity': 'catalog.domain',
            'import ingestion': 'ingestion',
            'import source_ingestion': 'source_ingestion',
            'import psycopg': 'psycopg',
            'from temporalio import workflow': 'temporalio',
            'import pydantic': 'pydantic',
            'import socket': 'socket',
            'import subprocess': 'subprocess',
            'from subprocess import run': 'subprocess',
            'import os': 'os',
            'import os.path': 'os.path',
            'from os import path': 'os',
            'import shutil': 'shutil',
            'from shutil import rmtree': 'shutil',
            'import tempfile': 'tempfile',
            'from tempfile import mkdtemp': 'tempfile',
            'import urllib.request': 'urllib.request',
            'from urllib import request': 'urllib.request',
            'import http.client': 'http.client',
            'from http import client': 'http.client',
            'import controlplane.infrastructure.db': 'controlplane.infrastructure.db',
            'from controlplane.ui import view': 'controlplane.ui',
            'from controlplane import api': 'controlplane.api',
            'from controlplane import config': 'controlplane.config',
            'import controlplane.config.models': 'controlplane.config.models',
            "importlib.import_module('creative')": 'creative',
            "importlib.import_module('os')": 'os',
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertIn(expected, find_forbidden_imports(source))

    def test_detector_allows_boundary_safe_imports(self) -> None:
        for source in (
            'import render.domain',
            'from . import domain',
            'from controlplane.domain import events',
            'from controlplane.application import service',
            'import dataclasses',
            'from pathlib import PurePath',
            'import urllib.parse',
            'from urllib import parse',
            'from http import HTTPStatus',
            'import ingestion_tools',
            'import socketserver',
            'import subprocess_tools',
            'import osmosis',
            'import shutil_tools',
            'import tempfile_utils',
        ):
            with self.subTest(source=source):
                self.assertEqual(find_forbidden_imports(source), [])

    def test_detector_flags_forbidden_calls(self) -> None:
        for method in ('unlink', 'rmdir', 'rmtree', 'remove', 'rename', 'truncate'):
            with self.subTest(method=method):
                self.assertEqual(find_forbidden_calls(f'target.{method}()'), [method])
        self.assertEqual(find_forbidden_calls('path.unlink(missing_ok=True)'), ['unlink'])
        for source in ('text.removeprefix(prefix)', 'handle.unlinked()', 'value.replace(a, b)'):
            with self.subTest(source=source):
                self.assertEqual(find_forbidden_calls(source), [])

    def test_detector_flags_forbidden_function_names(self) -> None:
        cases = {
            'def delete_item(): pass': 'delete_item',
            'async def cleanup_outputs(): pass': 'cleanup_outputs',
            'class Store:\n    def remove_file(self): pass': 'remove_file',
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(find_forbidden_functions(source), [expected])
        for source in ('def deleted(): pass', 'def render_cleanup(): pass', 'def delete(): pass'):
            with self.subTest(source=source):
                self.assertEqual(find_forbidden_functions(source), [])

    def test_dir_detector_flags_duplicate_trees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            for rel in ('storage', 'adapters/orchestration', 'worker/ui', 'projections/config', 'domain'):
                (base / rel).mkdir(parents=True)
            self.assertEqual(
                find_forbidden_dirs(base), ['adapters/orchestration', 'projections/config', 'storage', 'worker/ui']
            )

    def test_scan_package_reports_violations_in_new_files(self) -> None:
        bad = 'import subprocess\nimport src.render\n\n\ndef cleanup_outputs(path):\n    path.unlink()\n'
        ok = 'import dataclasses\nfrom pathlib import PurePath\n\n\ndef build(path):\n    return PurePath(path)\n'
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            for rel, text in (('domain/bad.py', bad), ('adapters/ok.py', ok), ('worker/deep/nested.py', 'import os\n')):
                target = base / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding='utf-8')
            self.assertEqual(
                scan_package(base),
                {
                    'domain/bad.py': ['import:src.render', 'import:subprocess', 'call:unlink', 'def:cleanup_outputs'],
                    'worker/deep/nested.py': ['import:os'],
                },
            )


class AdapterExemptionTests(unittest.TestCase):
    def _scan(self, files: dict[str, str]) -> dict[str, list[str]]:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            for rel, text in files.items():
                target = base / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding='utf-8')
            return scan_package(base)

    def test_exemption_table_is_exact_paths_only(self) -> None:
        self.assertEqual(
            ADAPTER_EXEMPTIONS,
            {
                'adapters/real_ffmpeg_renderer.py': frozenset({'import:os', 'import:subprocess', 'call:unlink'}),
                'adapters/real_ffprobe_probe.py': frozenset({'import:subprocess'}),
            },
        )
        for rel in ADAPTER_EXEMPTIONS:
            with self.subTest(rel=rel):
                self.assertFalse(set('*?[') & set(rel))
                self.assertTrue((PACKAGE_DIR / rel).is_file())

    def test_exempt_adapters_accept_only_their_items(self) -> None:
        self.assertEqual(
            self._scan({
                'adapters/real_ffmpeg_renderer.py': (
                    'import os\n'
                    'import subprocess\n\n\n'
                    'def run(temp):\n'
                    '    temp.unlink(missing_ok=True)\n'
                )
            }),
            {},
        )
        self.assertEqual(
            self._scan({'adapters/real_ffprobe_probe.py': 'import subprocess\n'}),
            {},
        )

    def test_exempt_adapters_still_flag_other_items(self) -> None:
        self.assertEqual(
            self._scan({
                'adapters/real_ffmpeg_renderer.py': (
                    'import shutil\n'
                    'import socket\n\n\n'
                    'def cleanup_x(p):\n'
                    '    p.rename(p)\n'
                )
            }),
            {
                'adapters/real_ffmpeg_renderer.py': [
                    'import:shutil',
                    'import:socket',
                    'call:rename',
                    'def:cleanup_x',
                ]
            },
        )
        self.assertEqual(
            self._scan({
                'adapters/real_ffprobe_probe.py': (
                    'import os\n'
                    'import subprocess\n\n\n'
                    'def f(p):\n'
                    '    p.unlink()\n'
                )
            }),
            {'adapters/real_ffprobe_probe.py': ['import:os', 'call:unlink']},
        )

    def test_other_modules_still_reject_exempted_items(self) -> None:
        for rel in (
            'domain/other.py',
            'adapters/other.py',
            'adapters/fake_renderer.py',
            'application/x.py',
            'domain/real_ffprobe_probe.py',
            'worker/real_ffmpeg_renderer.py',
        ):
            for source, expected in (
                ('import subprocess\n', 'import:subprocess'),
                ('import os\n', 'import:os'),
                ('p.unlink()\n', 'call:unlink'),
            ):
                with self.subTest(rel=rel, source=source):
                    self.assertEqual(self._scan({rel: source}), {rel: [expected]})


class PersistenceImportTests(unittest.TestCase):
    def _scan(self, files: dict[str, str]) -> dict[str, list[str]]:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            for rel, text in files.items():
                target = base / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding='utf-8')
            return scan_package(base)

    def test_persistence_constant_is_exact(self) -> None:
        self.assertEqual(PERSISTENCE_IMPORT_PREFIXES, ('psycopg', 'controlplane.infrastructure.db'))

    def test_persistence_may_import_psycopg_and_controlplane_db(self) -> None:
        source = (
            'import psycopg\n'
            'import psycopg.errors\n'
            'import psycopg.types.json\n'
            'from psycopg.types.json import Json\n'
            'import controlplane.infrastructure.db.outbox.postgres\n'
            'from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository\n'
        )
        self.assertEqual(self._scan({'persistence/repository.py': source, 'persistence/deep/tables.py': source}), {})

    def test_persistence_still_rejects_other_forbidden_items(self) -> None:
        for source, expected in (
            ('import subprocess\n', 'import:subprocess'),
            ('import os\n', 'import:os'),
            ('import controlplane.api.routes\n', 'import:controlplane.api.routes'),
            ('import controlplane.infrastructure.storage\n', 'import:controlplane.infrastructure.storage'),
            ('import controlplane.infrastructure.dbx\n', 'import:controlplane.infrastructure.dbx'),
            ('p.unlink()\n', 'call:unlink'),
            ('def cleanup_x(p):\n    pass\n', 'def:cleanup_x'),
        ):
            with self.subTest(source=source):
                self.assertEqual(
                    self._scan({'persistence/x.py': 'import psycopg.errors\n' + source}),
                    {'persistence/x.py': [expected]},
                )

    def test_files_outside_persistence_still_reject_psycopg_and_controlplane_db(self) -> None:
        for rel in (
            'adapters/x.py',
            'domain/x.py',
            'application/x.py',
            'domain/persistence/x.py',
            'persistence_extra/x.py',
            'persistence.py',
        ):
            for source, expected in (
                ('import psycopg\n', 'import:psycopg'),
                ('import psycopg.errors\n', 'import:psycopg.errors'),
                ('import controlplane.infrastructure.db.outbox.postgres\n', 'import:controlplane.infrastructure.db.outbox.postgres'),
            ):
                with self.subTest(rel=rel, source=source):
                    self.assertEqual(self._scan({rel: source}), {rel: [expected]})


class PackageLayoutTests(unittest.TestCase):
    def test_package_importable_from_src_root(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec('render'), 'render is not importable from the src/ root')
        module = importlib.import_module('render')
        self.assertEqual(pathlib.Path(module.__file__).resolve(), PACKAGE_DIR / '__init__.py')
        for name in SUBPACKAGES:
            qualified = f'render.{name}'
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

    def test_package_modules_have_no_forbidden_constructs(self) -> None:
        self.assertTrue(package_py_files(PACKAGE_DIR), 'src/render has no Python modules to scan')
        self.assertEqual(scan_package(PACKAGE_DIR), {})

    def test_package_has_no_duplicate_tree_directories(self) -> None:
        self.assertEqual(find_forbidden_dirs(PACKAGE_DIR), [])

    def test_render_test_dir_has_no_init(self) -> None:
        self.assertFalse((pathlib.Path(__file__).resolve().parent / '__init__.py').exists())

    def test_test_module_declares_covered_ids(self) -> None:
        doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
        self.assertTrue(any(line.startswith('coveredIds:') for line in (doc or '').splitlines()))
