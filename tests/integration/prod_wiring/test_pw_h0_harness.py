"""PW-H0: the prod_wiring harness itself (temporary databases, time-skipping Temporal, recording fakes, import guard).

coveredIds: PW-H0-01, CT-WF-001
"""
from __future__ import annotations

import ast
import asyncio
import importlib.util
import inspect
import re
import sys
import time
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

import pw_support
from controlplane.domain.orchestration.workflow_catalog import WORKFLOW_CATALOG, WORKFLOW_NAMES
from render.ports.lease import GpuLeaseUnavailable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONFTEST_PATH = HERE / 'conftest.py'


def _load_conftest():
    spec = importlib.util.spec_from_file_location('pw_conftest_under_test', CONFTEST_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules['pw_conftest_under_test'] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def seen_databases():
    seen: dict[str, str] = {}
    yield seen
    leaked = [name for name, admin_dsn in seen.items() if pw_support.database_exists(admin_dsn, name)]
    assert not leaked, 'prod_wiring databases leaked after the module: ' + str(leaked)


def _check_private_database(database, seen):
    assert re.fullmatch(r'pw_[0-9a-f]{8}', database.name)
    assert database.name not in seen
    for earlier, admin_dsn in seen.items():
        assert not pw_support.database_exists(admin_dsn, earlier)
    seen[database.name] = database.admin_dsn
    assert pw_support.database_exists(database.admin_dsn, database.name)
    with database.connect() as connection:
        assert connection.execute('SELECT current_database()').fetchone()[0] == database.name
        assert connection.execute('SELECT count(*) FROM controlplane.cp_workspaces').fetchone()[0] == 1
        assert connection.execute('SELECT count(*) FROM controlplane.cp_actors WHERE workspace_id = %s AND actor_id = %s', (database.workspace_id, database.actor_id)).fetchone()[0] == 1


def test_pw_database_first_test_gets_private_migrated_seeded_database(pw_database, seen_databases):
    _check_private_database(pw_database, seen_databases)


def test_pw_database_second_test_gets_other_name_and_first_is_dropped(pw_database, seen_databases):
    _check_private_database(pw_database, seen_databases)


def test_pw_temp_database_is_dropped_even_when_the_body_raises():
    module = _load_conftest()
    captured = {}
    with pytest.raises(RuntimeError, match='boom'):
        with module.pw_temp_database() as database:
            captured['name'] = database.name
            captured['admin_dsn'] = database.admin_dsn
            assert pw_support.database_exists(database.admin_dsn, database.name)
            raise RuntimeError('boom')
    assert not pw_support.database_exists(captured['admin_dsn'], captured['name'])


def test_missing_dsn_fails_with_blocked_external_instead_of_skipping(monkeypatch):
    module = _load_conftest()
    monkeypatch.delenv('M2_TEST_PG_DSN', raising=False)
    with pytest.raises(pytest.fail.Exception, match='BLOCKED_EXTERNAL'):
        module.pw_admin_dsn()
    monkeypatch.setenv('M2_TEST_PG_DSN', '')
    with pytest.raises(pytest.fail.Exception, match='BLOCKED_EXTERNAL'):
        module.pw_admin_dsn()


@pytest.mark.parametrize('host', ['db.example.test', '10.20.30.40', 'postgres.internal'])
def test_non_loopback_dsn_is_refused_without_leaking_the_password(monkeypatch, host):
    module = _load_conftest()
    monkeypatch.setenv('M2_TEST_PG_DSN', 'postgresql://admin:pw-secret-value@' + host + ':5432/postgres')
    with pytest.raises(pytest.fail.Exception, match='BLOCKED_EXTERNAL') as info:
        module.pw_admin_dsn()
    assert 'pw-secret-value' not in str(info.value)
    with pytest.raises(pytest.fail.Exception, match='BLOCKED_EXTERNAL'):
        with module.pw_temp_database():
            pass


def test_loopback_dsn_is_accepted(monkeypatch):
    module = _load_conftest()
    for host in ('127.0.0.1', 'localhost', '[::1]'):
        dsn = 'postgresql://user:pw@' + host + ':5432/postgres'
        monkeypatch.setenv('M2_TEST_PG_DSN', dsn)
        assert module.pw_admin_dsn() == dsn


def test_conftest_blocks_instead_of_skipping():
    text = CONFTEST_PATH.read_text(encoding='utf-8')
    assert 'BLOCKED_EXTERNAL' in text
    assert 'pytest.skip' not in text
    forbidden = {'skip', 'skipif', 'importorskip', 'xfail'}
    found = [node.attr for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Attribute) and node.attr in forbidden]
    assert found == []


@workflow.defn
class PwEchoWorkflow:
    @workflow.run
    async def run(self, text: str) -> str:
        await workflow.sleep(timedelta(hours=1))
        return text


@pytest.mark.asyncio
async def test_pw_temporal_runs_echo_workflow_on_time_skipping_server(pw_temporal):
    assert isinstance(pw_temporal, Client)
    task_queue = 'pw-h0-' + uuid.uuid4().hex[:8]
    started = time.monotonic()
    async with Worker(pw_temporal, task_queue=task_queue, workflows=[PwEchoWorkflow], workflow_runner=UnsandboxedWorkflowRunner()):
        result = await asyncio.wait_for(
            pw_temporal.execute_workflow(PwEchoWorkflow.run, 'pw-echo', id='pw-h0-echo-' + uuid.uuid4().hex[:8], task_queue=task_queue),
            timeout=300,
        )
    assert result == 'pw-echo'
    assert time.monotonic() - started < 300


@workflow.defn(name='DailyCollectionWorkflow')
class PwDailyCollectionEchoWorkflow:
    @workflow.run
    async def run(self, text: str) -> str:
        return 'DailyCollectionWorkflow:' + text


@workflow.defn(name='ContentEnrichmentWorkflow')
class PwContentEnrichmentEchoWorkflow:
    @workflow.run
    async def run(self, text: str) -> str:
        return 'ContentEnrichmentWorkflow:' + text


@workflow.defn(name='ProductionBatchWorkflow')
class PwProductionBatchEchoWorkflow:
    @workflow.run
    async def run(self, text: str) -> str:
        return 'ProductionBatchWorkflow:' + text


@workflow.defn(name='VideoProductionWorkflow')
class PwVideoProductionEchoWorkflow:
    @workflow.run
    async def run(self, text: str) -> str:
        return 'VideoProductionWorkflow:' + text


@workflow.defn(name='DebugStageWorkflow')
class PwDebugStageEchoWorkflow:
    @workflow.run
    async def run(self, text: str) -> str:
        return 'DebugStageWorkflow:' + text


@workflow.defn(name='MaintenanceWorkflow')
class PwMaintenanceEchoWorkflow:
    @workflow.run
    async def run(self, text: str) -> str:
        return 'MaintenanceWorkflow:' + text


PW_ECHO_WORKFLOWS = {
    'DailyCollectionWorkflow': PwDailyCollectionEchoWorkflow,
    'ContentEnrichmentWorkflow': PwContentEnrichmentEchoWorkflow,
    'ProductionBatchWorkflow': PwProductionBatchEchoWorkflow,
    'VideoProductionWorkflow': PwVideoProductionEchoWorkflow,
    'DebugStageWorkflow': PwDebugStageEchoWorkflow,
    'MaintenanceWorkflow': PwMaintenanceEchoWorkflow,
}


def test_ct_wf_001_catalog_matches_the_six_logical_workflows_of_the_contract():
    contract = (ROOT / 'docs' / '09-contracts' / '03-workflow-and-execution.md').read_text(encoding='utf-8')
    section = contract.split('### CT-WF-001', 1)[1].split('### CT-WF-002', 1)[0]
    documented = re.findall(r'^\| `(\w+Workflow)` \|', section, flags=re.MULTILINE)
    assert len(documented) == 6
    assert set(documented) == set(WORKFLOW_NAMES)
    assert sorted(spec.name for spec in WORKFLOW_CATALOG) == sorted(documented)


@pytest.mark.asyncio
async def test_pw_temporal_hosts_every_ct_wf_001_workflow_by_catalog_name(pw_temporal):
    assert set(PW_ECHO_WORKFLOWS) == set(WORKFLOW_NAMES)
    classes = [PW_ECHO_WORKFLOWS[spec.name] for spec in WORKFLOW_CATALOG]
    task_queue = 'pw-h0-' + uuid.uuid4().hex[:8]
    async with Worker(pw_temporal, task_queue=task_queue, workflows=classes, workflow_runner=UnsandboxedWorkflowRunner()):
        for spec in WORKFLOW_CATALOG:
            result = await asyncio.wait_for(
                pw_temporal.execute_workflow(spec.name, 'ct-wf-001', id='pw-h0-' + spec.name + '-' + uuid.uuid4().hex[:8], task_queue=task_queue),
                timeout=300,
            )
            assert result == spec.name + ':ct-wf-001'


def test_module_docstring_declares_the_covered_ids():
    assert 'coveredIds: PW-H0-01, CT-WF-001' in (__doc__ or '')


def test_fake_router_counts_every_call_and_keeps_requests():
    router = pw_support.FakeRouter(results={'resolve': {'route': 'r1'}})
    assert router.call_count() == 0
    assert router.resolve({'role': 'script'}) == {'route': 'r1'}
    router.resolve({'role': 'hook'})
    assert router.invoke('decision', 'envelope') is None
    assert router.call_count('resolve') == 2
    assert router.call_count('invoke') == 1
    assert router.call_count() == 3
    assert router.requests == [{'role': 'script'}, {'role': 'hook'}]
    assert router.calls_to('invoke')[0].args == ('decision', 'envelope')


def test_fake_drive_counts_calls_and_stores_objects():
    drive = pw_support.FakeDrive()
    first = drive.upload('a.mp4', b'aaa', mime_type='video/mp4')
    second = drive.upload('b.mp4', b'bbb')
    assert first != second
    assert drive.download(first) == b'aaa'
    drive.delete(second)
    with pytest.raises(KeyError):
        drive.download(second)
    assert drive.call_count('upload') == 2
    assert drive.call_count('download') == 2
    assert drive.call_count('delete') == 1
    assert sorted(drive.objects) == [first]
    assert drive.objects[first].mime_type == 'video/mp4'
    assert drive.calls_to('upload')[0].kwargs == {'mime_type': 'video/mp4'}


def test_fake_kokoro_counts_calls_including_failures():
    kokoro = pw_support.FakeKokoro(results={'synthesize': lambda decision, script_text, request: 'voice:' + script_text})
    assert kokoro.synthesize('d', 'xin', {}) == 'voice:xin'
    assert kokoro.synthesize('d', 'chao', {}) == 'voice:chao'
    failing = pw_support.FakeKokoro(errors={'synthesize': RuntimeError('tts down')})
    with pytest.raises(RuntimeError, match='tts down'):
        failing.synthesize('d', 'x', {})
    assert kokoro.call_count('synthesize') == 2
    assert failing.call_count('synthesize') == 1


def test_fake_aligner_counts_calls_and_does_not_share_state():
    aligner = pw_support.FakeAligner(results={'align': 'words'})
    assert aligner.align('r1') == 'words'
    assert aligner.align('r2') == 'words'
    assert aligner.call_count('align') == 2
    assert pw_support.FakeAligner().call_count() == 0


def test_fake_gpu_counts_acquire_and_release_and_enforces_capacity():
    gpu = pw_support.FakeGpu(capacity=1)
    lease = gpu.acquire('render-1')
    assert lease.owner_ref == 'render-1'
    assert lease.lock_id == 'LOCK-DESKTOP-GPU'
    with pytest.raises(GpuLeaseUnavailable):
        gpu.acquire('render-2')
    gpu.release(lease)
    gpu.release(lease)
    assert gpu.held == {}
    assert gpu.call_count('acquire') == 2
    assert gpu.call_count('release') == 2
    assert gpu.acquire('render-3').owner_ref == 'render-3'


@pytest.mark.parametrize('name', ['FakeRouter', 'FakeDrive', 'FakeKokoro', 'FakeAligner', 'FakeGpu'])
def test_fake_lives_in_pw_support_under_tests_and_starts_empty(name):
    cls = getattr(pw_support, name)
    source = Path(inspect.getsourcefile(cls)).resolve()
    assert source == Path(pw_support.__file__).resolve()
    assert ROOT / 'tests' in source.parents
    assert ROOT / 'src' not in source.parents
    assert issubclass(cls, pw_support.RecordingFake)
    instance = cls()
    assert instance.calls == []
    assert instance.call_count() == 0


def test_assert_no_support_import_accepts_clean_tree(tmp_path):
    (tmp_path / 'pkg').mkdir()
    (tmp_path / 'pkg' / 'clean.py').write_text('import json\nfrom pathlib import Path\n', encoding='utf-8')
    (tmp_path / 'top.py').write_text('X = 1\n', encoding='utf-8')
    pw_support.assert_no_support_import(tmp_path)


@pytest.mark.parametrize(
    'source',
    [
        'import pw_support\n',
        'import pw_support as support\n',
        'from pw_support import FakeRouter\n',
        'from tests.integration.prod_wiring.pw_support import FakeRouter\n',
        'from tests.integration.prod_wiring import pw_support\n',
        'from . import pw_support\n',
        "import importlib\nimportlib.import_module('pw_support')\n",
        'def late():\n    import pw_support\n',
    ],
)
def test_assert_no_support_import_goes_red_on_an_importing_file(tmp_path, source):
    package = tmp_path / 'pkg'
    package.mkdir()
    (package / 'offender.py').write_text(source, encoding='utf-8')
    with pytest.raises(AssertionError, match='offender.py'):
        pw_support.assert_no_support_import(tmp_path)


def test_assert_no_support_import_fails_closed_on_unparsable_file_and_missing_root(tmp_path):
    (tmp_path / 'broken.py').write_text('def (:\n', encoding='utf-8')
    with pytest.raises(AssertionError, match='broken.py'):
        pw_support.assert_no_support_import(tmp_path)
    with pytest.raises(AssertionError):
        pw_support.assert_no_support_import(tmp_path / 'missing')


def test_src_never_imports_pw_support():
    src = ROOT / 'src'
    assert any(src.rglob('*.py'))
    pw_support.assert_no_support_import(src)
