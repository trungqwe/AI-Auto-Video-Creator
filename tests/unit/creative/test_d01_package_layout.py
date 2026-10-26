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

# Miễn trừ hẹp theo kế hoạch ADAPT đã duyệt: docs/implementation/adapt/plan.md dòng 81 và 107 (ADAPT-D: NineRouterHTTPAdapter, ApprovedEndpointRegistry).
# Miễn trừ hẹp theo kế hoạch PROD-WIRING V4 (PW-D3): PostgresMediaCandidates và PostgresHookCandidates đọc danh mục của C qua src/catalog/application/candidate_query.py nên chỉ hai tệp này được import đúng mô-đun catalog.application.candidate_query.
# Không miễn cả thư mục adapters, không miễn cả gói catalog, không miễn thumbnail_candidates.py; catalog.domain, voice, psycopg vẫn bị báo.
# Khoá là đường dẫn tệp chính xác (posix, tính từ gốc repo), không dùng mẫu, không miễn cả thư mục adapters.
ADAPTER_IMPORT_EXEMPTIONS = {
    'src/creative/adapters/real_route_executor.py': frozenset({'controlplane.config'}),
    'src/creative/adapters/media_candidates.py': frozenset({'catalog.application.candidate_query'}),
    'src/creative/adapters/hook_candidates.py': frozenset({'catalog.application.candidate_query'}),
}


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


def find_unexempted_imports(source: str, rel_path: str, filename: str = '<string>') -> list[str]:
    allowed = ADAPTER_IMPORT_EXEMPTIONS.get(rel_path, frozenset())
    return [
        name
        for name in find_forbidden_imports(source, filename)
        if not any(name == prefix or name.startswith(prefix + '.') for prefix in allowed)
    ]


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


class AdapterExemptionTests(unittest.TestCase):
    ADAPTER = 'src/creative/adapters/real_route_executor.py'
    MEDIA = 'src/creative/adapters/media_candidates.py'
    HOOKS = 'src/creative/adapters/hook_candidates.py'
    CANDIDATE_QUERY = frozenset({'catalog.application.candidate_query'})

    def test_exemption_table_is_exact_paths_only(self) -> None:
        self.assertEqual(set(ADAPTER_IMPORT_EXEMPTIONS), {self.ADAPTER, self.MEDIA, self.HOOKS})
        self.assertEqual(ADAPTER_IMPORT_EXEMPTIONS[self.ADAPTER], frozenset({'controlplane.config'}))
        self.assertEqual(ADAPTER_IMPORT_EXEMPTIONS[self.MEDIA], self.CANDIDATE_QUERY)
        self.assertEqual(ADAPTER_IMPORT_EXEMPTIONS[self.HOOKS], self.CANDIDATE_QUERY)
        for rel in ADAPTER_IMPORT_EXEMPTIONS:
            with self.subTest(rel=rel):
                self.assertFalse(set('*?[') & set(rel))
                self.assertTrue((ROOT / rel).is_file())

    def test_exempt_adapter_may_import_only_controlplane_config(self) -> None:
        self.assertEqual(
            find_unexempted_imports(
                'from controlplane.config.adapter import ApprovedEndpointRegistry, NineRouterHTTPAdapter',
                self.ADAPTER,
            ),
            [],
        )
        self.assertEqual(
            find_unexempted_imports('from controlplane.config.models import AIRequest', self.ADAPTER),
            [],
        )
        for source, expected in (
            ('import socket', 'socket'),
            ('import urllib.request', 'urllib.request'),
            ('import voice', 'voice'),
            ('import psycopg', 'psycopg'),
            ('from controlplane.infrastructure import db', 'controlplane.infrastructure'),
            ('from controlplane.api import routes', 'controlplane.api'),
        ):
            with self.subTest(source=source):
                self.assertIn(expected, find_unexempted_imports(source, self.ADAPTER))

    def test_other_modules_still_reject_controlplane_config(self) -> None:
        for rel in (
            'src/creative/domain/other.py',
            'src/creative/adapters/other.py',
            'src/creative/adapters/real_ai_invocation.py',
            'src/creative/application/pipeline.py',
            'src/creative/domain/real_route_executor.py',
        ):
            with self.subTest(rel=rel):
                self.assertIn(
                    'controlplane.config.adapter',
                    find_unexempted_imports(
                        'from controlplane.config.adapter import NineRouterHTTPAdapter', rel
                    ),
                )
                self.assertIn(
                    'controlplane.config',
                    find_unexempted_imports('from controlplane import config', rel),
                )

    def test_candidate_adapters_may_import_only_candidate_query(self) -> None:
        for rel in (self.MEDIA, self.HOOKS):
            with self.subTest(rel=rel):
                for source in (
                    'from catalog.application.candidate_query import CandidateIndexEntry, query_media_candidates',
                    'import catalog.application.candidate_query',
                ):
                    self.assertEqual(find_unexempted_imports(source, rel), [])
                for source, expected in (
                    ('import voice', 'voice'),
                    ('import psycopg', 'psycopg'),
                    ('from catalog.domain.identity import MediaKind', 'catalog.domain.identity'),
                    ('from catalog.domain import states', 'catalog.domain'),
                    ('from catalog.application.discovery import register_discovery', 'catalog.application.discovery'),
                    ('from catalog.persistence.assets import PostgresMediaAssetRepository', 'catalog.persistence.assets'),
                    ('from catalog.application import candidate_query', 'catalog.application'),
                    ('import catalog', 'catalog'),
                    ('from controlplane import config', 'controlplane.config'),
                ):
                    self.assertIn(expected, find_unexempted_imports(source, rel))

    def test_candidate_query_stays_forbidden_for_every_other_module(self) -> None:
        source = 'from catalog.application.candidate_query import query_media_candidates'
        for rel in (
            'src/creative/adapters/thumbnail_candidates.py',
            'src/creative/adapters/postgres_selection.py',
            'src/creative/adapters/real_route_executor.py',
            'src/creative/adapters/other.py',
            'src/creative/domain/media_candidates.py',
        ):
            with self.subTest(rel=rel):
                self.assertIn('catalog.application.candidate_query', find_unexempted_imports(source, rel))

    def test_exemptions_do_not_cover_a_directory_or_the_catalog_package(self) -> None:
        for rel, allowed in ADAPTER_IMPORT_EXEMPTIONS.items():
            with self.subTest(rel=rel):
                self.assertTrue(rel.endswith('.py'))
                self.assertNotIn('catalog', allowed)
                self.assertNotIn('catalog.application', allowed)
                self.assertNotIn('catalog.domain', allowed)

    def test_forbidden_import_prefixes_are_unchanged(self) -> None:
        self.assertEqual(
            FORBIDDEN_IMPORT_PREFIXES,
            (
                'src', 'source_ingestion', 'ingestion', 'catalog', 'voice', 'render', 'psycopg', 'temporalio', 'pydantic',
                'socket', 'urllib.request', 'http.client', 'controlplane.infrastructure', 'controlplane.ui',
                'controlplane.api', 'controlplane.config',
            ),
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
            if (found := find_unexempted_imports(path.read_text(encoding='utf-8'), path.relative_to(ROOT).as_posix(), str(path)))
        }
        self.assertEqual(violations, {})

    def test_package_has_no_duplicate_tree_directories(self) -> None:
        self.assertEqual(find_forbidden_dirs(PACKAGE_DIR), [])

    def test_creative_test_dir_has_no_init(self) -> None:
        self.assertFalse((pathlib.Path(__file__).resolve().parent / '__init__.py').exists())

    def test_test_module_declares_covered_ids(self) -> None:
        doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
        self.assertTrue(any(line.startswith('coveredIds:') for line in (doc or '').splitlines()))
