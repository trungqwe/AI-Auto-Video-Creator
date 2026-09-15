import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
from pathlib import Path
import psycopg
import psycopg_pool
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.security.secret_scanner import scan_file

root = Path.cwd()
mapping = subprocess.check_output(['docker', 'port', 'ai-auto-video-m2-pg', '5432/tcp'], text=True).splitlines()[0].strip()
assert mapping.startswith('127.0.0.1:') and mapping.split(':')[1].isdigit()
dsn = os.environ['M2_TEST_PG_DSN']
runtime = {'python': platform.python_version(), 'psycopg': importlib.metadata.version('psycopg'), 'psycopg_pool': importlib.metadata.version('psycopg-pool'), 'uv_runtime_observed': subprocess.check_output([str(root / '.local-tools/uv/uv.exe'), '--version'], text=True).strip(), 'uv_lock_version': '0.12.13'}
with psycopg.connect(dsn, autocommit=True) as connection:
    runtime['m2_postgresql'] = connection.execute('SHOW server_version').fetchone()[0].split()[0]
    runtime['createdb'] = connection.execute('SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user').fetchone()[0]
    runtime['m2_observed_port'] = connection.info.port
    assert connection.info.port == int(mapping.split(':')[1]), 'M2_DSN_OBSERVED_MAPPING_MISMATCH'
    runtime['orphan_db_count'] = connection.execute("SELECT count(*) FROM pg_database WHERE datname ~ '^m2_p[0-9]+[a-z]?_test_[0-9a-f]+$'").fetchone()[0]
manager = TransactionManager(dsn, pool_max_size=2)
try:
    assert isinstance(manager._pool, psycopg_pool.ConnectionPool)
    runtime['pool_public_import'] = 'psycopg_pool.ConnectionPool'
    runtime['pool_runtime_class'] = type(manager._pool).__module__ + '.' + type(manager._pool).__name__
    with manager.unit_of_work() as uow:
        runtime['borrowed_connection_class'] = type(uow.connection).__module__ + '.' + type(uow.connection).__name__
finally:
    manager.close()
with psycopg.connect('host=127.0.0.1 port=55432 dbname=aiavc_m1 user=postgres', autocommit=True) as connection:
    runtime['m1_postgresql'] = connection.execute('SHOW server_version').fetchone()[0].split()[0]
    runtime['m1_database'] = connection.execute('SELECT current_database()').fetchone()[0]
    runtime['m1_select_one'] = connection.execute('SELECT 1').fetchone()[0] == 1
    runtime['m1_endpoint'] = '127.0.0.1:55432/aiavc_m1'
runtime['temporal_server_version'] = subprocess.check_output([str(root / 'scratch/temporal_1.31.2/temporal-server.exe'), '--version'], text=True).strip()
runtime['temporal_archive_sha256'] = hashlib.sha256((root / 'scratch/temporal-download/temporal_1.31.2_windows_amd64.zip').read_bytes()).hexdigest()
runtime['temporal_executable_sha256'] = hashlib.sha256((root / 'scratch/temporal_1.31.2/temporal-server.exe').read_bytes()).hexdigest()
vault = json.loads((Path.home() / '.cloud_token_broker/vault.json').read_text(encoding='utf-8'))
runtime['vault_encrypted'] = vault.get('encrypted') is True and vault.get('encryption') == 'WINDOWS_DPAPI' and bool(vault.get('ciphertext'))
runtime['vault_plaintext_secret_fields_absent'] = 'refresh_token' not in vault and 'client_secret' not in vault

def imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            yield from (item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ''

app_infra = [(str(path.relative_to(root)), name) for path in (root / 'src/controlplane/application').rglob('*.py') for name in imports(path) if name.startswith('controlplane.infrastructure')]
domain_app = [(str(path.relative_to(root)), name) for path in (root / 'src/controlplane/domain').rglob('*.py') for name in imports(path) if name.startswith('controlplane.application')]
texts = [path.read_text(encoding='utf-8') for path in (root / 'src/controlplane').rglob('*.py')]
patch_absent = all('_p5a_original_execute' not in text and 'psycopg.Connection.execute =' not in text for text in texts)
migration = (root / 'src/controlplane/infrastructure/db/migrations/0004_config_and_secrets.sql').read_text(encoding='utf-8')
rollback = (root / 'src/controlplane/infrastructure/db/migrations/0004_config_and_secrets.rollback.sql').read_text(encoding='utf-8')
runner = 'src/controlplane/infrastructure/db/migration_runner.py'
runner_unchanged = (root / runner).read_bytes() == subprocess.check_output(['git', 'show', 'd2e2cd3c7814d938c527d59d5e55414c55ad5703:' + runner])
adapter_tree = ast.parse((root / 'src/controlplane/infrastructure/db/config_security/__init__.py').read_text(encoding='utf-8'))
transaction_ownership = not any(isinstance(node, ast.Call) and ((isinstance(node.func, ast.Attribute) and node.func.attr in {'commit', 'rollback'}) or (isinstance(node.func, ast.Name) and node.func.id == 'ConnectionPool')) for node in ast.walk(adapter_tree))
static = {'app_infra_forbidden_imports': len(app_infra), 'domain_application_imports': len(domain_app), 'global_psycopg_patch_absent': patch_absent, 'migration_ledger_side_effect_absent': 'cp_schema_migrations' not in migration + rollback and 'CREATE TRIGGER' not in migration and 'CREATE FUNCTION' not in migration, 'migration_runner_unchanged': runner_unchanged, 'adapter_caller_transaction_ownership': transaction_ownership, 'migration_0005_absent': not list((root / 'src/controlplane/infrastructure/db/migrations').glob('0005*'))}
targets = [root / 'src/controlplane/application/config_security', root / 'src/controlplane/infrastructure/db/config_security', root / 'src/controlplane/domain/config_security']
files = [file for directory in targets for file in directory.rglob('*') if file.is_file() and file.suffix in {'.py', '.sql'}]
files += [root / 'tests/m2/test_p5a_config_and_secrets.py', root / 'src/controlplane/infrastructure/db/migrations/0004_config_and_secrets.sql', root / 'src/controlplane/infrastructure/db/migrations/0004_config_and_secrets.rollback.sql']
findings = [match for file in files for match in scan_file(file)]
security = {'verdict': 'CLEAN' if not findings else 'VIOLATIONS_DETECTED', 'total_findings': len(findings), 'files_scanned': len(files)}
tools = {name: ('available' if importlib.util.find_spec(name) else 'unavailable') for name in ('ruff', 'mypy', 'build')}
print(json.dumps({'runtime': runtime, 'static': static, 'secret_scan': security, 'optional_quality_tools': tools}, indent=2), flush=True)
assert runtime['python'] == '3.13.15' and runtime['psycopg'] == '3.3.5' and runtime['psycopg_pool'] == '3.3.1'
assert runtime['m1_postgresql'] == runtime['m2_postgresql'] == '18.6' and runtime['createdb'] and runtime['orphan_db_count'] == 0
assert runtime['temporal_archive_sha256'] == '044a4610695bb31bd5b982c818cd406c2ca88279ddaa776391a7dc909afe7a67'
assert runtime['temporal_executable_sha256'] == '5575b3693f37c9c0f19379a5744210ad9558ada54dadb2d1eabe74001a1f5e6b'
assert not app_infra and not domain_app and all(value for key, value in static.items() if not key.endswith('imports')) and not findings
