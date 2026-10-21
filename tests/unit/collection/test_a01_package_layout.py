"""A-01: source_ingestion package skeleton and import boundary (D1)."""
import ast
import importlib
import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PACKAGE_DIR = ROOT / 'src' / 'source_ingestion'
SUBPACKAGES = ('domain', 'application', 'ports', 'adapters', 'worker', 'projections')
FORBIDDEN_IMPORT_PREFIXES = (
    'src', 'ingestion', 'catalog', 'creative', 'voice', 'render', 'psycopg', 'temporalio',
    'controlplane.infrastructure', 'controlplane.ui', 'controlplane.api',
)
FORBIDDEN_DIR_NAMES = frozenset({'storage', 'orchestration', 'ui'})
DYNAMIC_IMPORT_CALLS = frozenset({'import_module', '__import__'})

# Miễn trừ hẹp theo kế hoạch ADAPT đã duyệt: docs/implementation/adapt/plan.md dòng 101 (ADAPT-A: real_media_fetch.py dựng DiscoveryObservation của catalog để C gọi register_discovery) và binding A→C CT-MED-001 do GATE-CP-2D-REGISTRY tạo.
# Khoá là đường dẫn tệp chính xác (posix, tính từ gốc repo), không dùng mẫu, không miễn cả thư mục adapters, không miễn cả gói catalog.
# Miễn trừ hẹp theo kế hoạch PERSIST đã duyệt: docs/implementation/persist/plan.md mục 3 (dòng 40-41) đòi adapter dùng TransactionManager và ghi outbox controlplane.cp_outbox_events bằng kết nối của UoW; psycopg là thư viện đã khoá (plan.md dòng 15). Gói PERSIST-A: outbox.py chỉ được import PostgresOutboxRepository của controlplane, repositories.py chỉ được import psycopg.errors.
# Không miễn cả thư mục persistence, không miễn cả gói controlplane.infrastructure, không miễn cả psycopg; mọi module cấm khác vẫn bị báo.
ADAPTER_IMPORT_EXEMPTIONS = {
    'src/source_ingestion/adapters/real_media_fetch.py': frozenset({'catalog.application.discovery', 'catalog.domain.identity'}),
    'src/source_ingestion/persistence/outbox.py': frozenset({'controlplane.infrastructure.db.outbox.postgres'}),
    'src/source_ingestion/persistence/repositories.py': frozenset({'psycopg.errors'}),
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
            'from src.source_ingestion import domain': 'src.source_ingestion',
            'import src.source_ingestion': 'src.source_ingestion',
            'from src import source_ingestion': 'src',
            'import ingestion': 'ingestion',
            'from catalog.domain import entity': 'catalog.domain',
            'import creative': 'creative',
            "__import__('voice')": 'voice',
            "importlib.import_module('render.pipeline')": 'render.pipeline',
            'import psycopg': 'psycopg',
            'from temporalio import workflow': 'temporalio',
            'import controlplane.infrastructure.db': 'controlplane.infrastructure.db',
            'from controlplane.ui import view': 'controlplane.ui',
            'from controlplane import api': 'controlplane.api',
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertIn(expected, find_forbidden_imports(source))

    def test_detector_allows_boundary_safe_imports(self) -> None:
        for source in (
            'import source_ingestion.domain',
            'from . import domain',
            'from controlplane.domain import events',
            'import dataclasses',
            'import ingestion_tools',
        ):
            with self.subTest(source=source):
                self.assertEqual(find_forbidden_imports(source), [])

    def test_dir_detector_flags_duplicate_trees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            for rel in ('storage', 'adapters/orchestration', 'worker/ui', 'domain'):
                (base / rel).mkdir(parents=True)
            self.assertEqual(find_forbidden_dirs(base), ['adapters/orchestration', 'storage', 'worker/ui'])


class AdapterExemptionTests(unittest.TestCase):
    ADAPTER = 'src/source_ingestion/adapters/real_media_fetch.py'
    OUTBOX = 'src/source_ingestion/persistence/outbox.py'
    REPOSITORIES = 'src/source_ingestion/persistence/repositories.py'

    def test_exemption_table_is_exact_path_and_set_only(self) -> None:
        self.assertEqual(set(ADAPTER_IMPORT_EXEMPTIONS), {self.ADAPTER, self.OUTBOX, self.REPOSITORIES})
        self.assertEqual(
            ADAPTER_IMPORT_EXEMPTIONS[self.ADAPTER],
            frozenset({'catalog.application.discovery', 'catalog.domain.identity'}),
        )
        self.assertEqual(
            ADAPTER_IMPORT_EXEMPTIONS[self.OUTBOX],
            frozenset({'controlplane.infrastructure.db.outbox.postgres'}),
        )
        self.assertEqual(
            ADAPTER_IMPORT_EXEMPTIONS[self.REPOSITORIES],
            frozenset({'psycopg.errors'}),
        )
        for rel in ADAPTER_IMPORT_EXEMPTIONS:
            with self.subTest(rel=rel):
                self.assertFalse(set('*?[') & set(rel))
                self.assertTrue((ROOT / rel).is_file())

    def test_exempt_adapter_may_import_only_discovery_and_identity(self) -> None:
        for source in (
            'from catalog.application.discovery import DiscoveryObservation',
            'from catalog.domain.identity import CanonicalFingerprint, MediaKind, ProvenanceEntry, ProvenanceRelation',
        ):
            with self.subTest(source=source):
                self.assertEqual(find_unexempted_imports(source, self.ADAPTER), [])
        for source, expected in (
            ('from creative.domain import x', 'creative.domain'),
            ('import psycopg', 'psycopg'),
            ('from catalog.infrastructure import y', 'catalog.infrastructure'),
            ('from catalog.domain.other import z', 'catalog.domain.other'),
            ('from catalog.application.other import w', 'catalog.application.other'),
            ('import catalog', 'catalog'),
        ):
            with self.subTest(source=source):
                self.assertIn(expected, find_unexempted_imports(source, self.ADAPTER))

    def test_other_modules_still_reject_catalog_imports(self) -> None:
        for rel in (
            'src/source_ingestion/domain/other.py',
            'src/source_ingestion/adapters/other.py',
            'src/source_ingestion/adapters/real_feed_source.py',
            'src/source_ingestion/application/pipeline.py',
            'src/source_ingestion/domain/real_media_fetch.py',
        ):
            with self.subTest(rel=rel):
                self.assertIn(
                    'catalog.application.discovery',
                    find_unexempted_imports('from catalog.application.discovery import DiscoveryObservation', rel),
                )
                self.assertIn(
                    'catalog.domain.identity',
                    find_unexempted_imports('from catalog.domain.identity import MediaKind', rel),
                )

    def test_persistence_exemptions_allow_only_their_own_module(self) -> None:
        for source in (
            'from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository',
        ):
            with self.subTest(source=source):
                self.assertEqual(find_unexempted_imports(source, self.OUTBOX), [])
        for source in (
            'import psycopg.errors',
            'from psycopg.errors import UniqueViolation',
        ):
            with self.subTest(source=source):
                self.assertEqual(find_unexempted_imports(source, self.REPOSITORIES), [])

    def test_persistence_exemptions_still_report_other_forbidden_imports(self) -> None:
        for rel, source, expected in (
            (self.OUTBOX, 'import psycopg', 'psycopg'),
            (self.OUTBOX, 'import psycopg.errors', 'psycopg.errors'),
            (self.OUTBOX, 'from controlplane.infrastructure.db.uow import x', 'controlplane.infrastructure.db.uow'),
            (self.OUTBOX, 'from controlplane.infrastructure.db.outbox.postgres_other import y', 'controlplane.infrastructure.db.outbox.postgres_other'),
            (self.OUTBOX, 'from controlplane.api import z', 'controlplane.api'),
            (self.REPOSITORIES, 'import psycopg', 'psycopg'),
            (self.REPOSITORIES, 'import psycopg.rows', 'psycopg.rows'),
            (self.REPOSITORIES, 'from controlplane.infrastructure.db.uow import x', 'controlplane.infrastructure.db.uow'),
            (self.REPOSITORIES, 'from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository', 'controlplane.infrastructure.db.outbox.postgres'),
        ):
            with self.subTest(rel=rel, source=source):
                self.assertIn(expected, find_unexempted_imports(source, rel))

        for rel in (
            'src/source_ingestion/persistence/unit_of_work.py',
            'src/source_ingestion/persistence/other.py',
            'src/source_ingestion/adapters/other.py',
        ):
            with self.subTest(rel=rel):
                self.assertIn(
                    'psycopg.errors',
                    find_unexempted_imports('import psycopg.errors', rel),
                )
                self.assertIn(
                    'controlplane.infrastructure.db.outbox.postgres',
                    find_unexempted_imports('from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository', rel),
                )


class PackageLayoutTests(unittest.TestCase):
    def test_package_importable_from_src_root(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec('source_ingestion'), 'source_ingestion is not importable from the src/ root')
        module = importlib.import_module('source_ingestion')
        self.assertEqual(pathlib.Path(module.__file__).resolve(), PACKAGE_DIR / '__init__.py')
        for name in SUBPACKAGES:
            qualified = f'source_ingestion.{name}'
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
        self.assertTrue(files, 'src/source_ingestion has no Python modules to scan')
        violations = {
            path.relative_to(ROOT).as_posix(): found
            for path in files
            if (found := find_unexempted_imports(path.read_text(encoding='utf-8'), path.relative_to(ROOT).as_posix(), str(path)))
        }
        self.assertEqual(violations, {})

    def test_package_has_no_duplicate_tree_directories(self) -> None:
        self.assertEqual(find_forbidden_dirs(PACKAGE_DIR), [])

    def test_collection_test_dir_has_no_init(self) -> None:
        self.assertFalse((pathlib.Path(__file__).resolve().parent / '__init__.py').exists())
