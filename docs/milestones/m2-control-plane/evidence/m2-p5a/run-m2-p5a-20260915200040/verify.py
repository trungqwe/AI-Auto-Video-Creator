"""Standalone immutable P5A closure profile; production validator stays unchanged."""
from __future__ import annotations
import ast
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(ROOT / 'src'))
from controlplane.infrastructure.evidence.evaluator import PackageSemanticProfile, parse_junit_xml, register_semantic_profile, verify_package_provenance
from controlplane.infrastructure.evidence.validator import validate_package_evidence

EXPECTED = {'p5a': 5, 'p4': 9, 'p3': 11, 'p2': 11, 'p1': 11, 'p0': 33, 'architecture': 6, 'm1': 93, 'correction-green': 3}
P5A_NAMES = {
    'test_tst_m2_p5a_001_config_revision_immutability_and_hash',
    'test_tst_m2_p5a_002_secret_handle_storage_blocks_plaintext',
    'test_tst_m2_p5a_003_secret_redaction_in_domain_events',
    'test_tst_m2_p5a_004_production_0004_forward_rollback_and_constraints',
    'test_tst_m2_p5a_005_workspace_isolation_and_concurrent_publish',
}

class P5AClosureProfile(PackageSemanticProfile):
    @property
    def profile_id(self): return 'm2-p5a-corrected-closure'
    @property
    def target_package(self): return 'M2-P5A'
    def evaluate(self, directory, status):
        manifest = json.loads((directory / 'source-manifest.json').read_text(encoding='utf-8'))
        sha = status['source_commit_sha']
        assert sha == manifest['source_commit_sha']
        subprocess.run(['git', 'cat-file', '-e', sha + '^{commit}'], cwd=ROOT, check=True, capture_output=True)
        for path, digest in manifest['files'].items():
            immutable = subprocess.check_output(['git', 'show', sha + ':' + path], cwd=ROOT)
            assert hashlib.sha256(immutable).hexdigest() == digest
            assert (ROOT / path).read_bytes() == immutable, 'SOURCE_WORKTREE_DRIFT:' + path
        assert status['oracle_sha256'] == manifest['files']['tests/m2/test_p5a_config_and_secrets.py']
        wiring = json.loads((directory / 'test-wiring-audit.json').read_text(encoding='utf-8'))
        assert wiring['normalized_ast_equivalence'] is True and wiring['tracked_paths'] == ['tests/m2/test_p5a_config_and_secrets.py']
        assert wiring['test_wiring_commit_sha'] == status['test_wiring_commit_sha'] and wiring['exact_identities'] == sorted(P5A_NAMES)
        results = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
        commands = [json.loads(line) for line in (directory / 'commands.jsonl').read_text(encoding='utf-8').splitlines()]
        assert len({gate['gate_id'] for gate in status['gates']}) == len(status['gates'])
        assert [record['sequence_idx'] for record in commands] == list(range(1, len(commands) + 1))
        assert all(record['run_id'] == status['run_id'] for record in commands)
        assert all(record['exit_code'] == 0 for record in commands)
        for label, count in EXPECTED.items():
            root = ET.parse(directory / (label + '.xml')).getroot()
            cases = list(root.iter('testcase'))
            metrics = parse_junit_xml(directory / (label + '.xml'))
            assert metrics.total == metrics.passed == count and metrics.failures == metrics.errors == metrics.skipped == 0
            identities = [case.get('classname') + '::' + case.get('name') for case in cases]
            assert len(cases) == count and len(set(identities)) == count
            assert all(case.find('failure') is None and case.find('error') is None and case.find('skipped') is None for case in cases)
            if label != 'correction-green':
                assert results[label] == status['suite_results'][label]
                assert results[label]['identities'] == identities
                assert results[label]['passed'] == results[label]['total'] == count
            producers = [record for record in commands if label + '.xml' in record['created_artifacts']]
            assert len(producers) == 1 and producers[0]['source_commit_sha'] == sha
            assert producers[0]['stage'] == 'immutable_source_execution'
            if label == 'p5a':
                assert {case.get('name') for case in cases} == P5A_NAMES
        collection = (directory / 'collect-p5a-stdout.txt').read_text(encoding='utf-8')
        assert '5 tests collected' in collection
        assert {line.split('::')[-1] for line in collection.splitlines() if '::test_' in line} == P5A_NAMES
        red = list(ET.parse(directory / 'correction-red.xml').getroot().iter('testcase'))
        assert len(red) == 3 and all(case.find('failure') is not None and case.find('error') is None and case.find('skipped') is None for case in red)
        red_metrics = parse_junit_xml(directory / 'correction-red.xml')
        assert red_metrics.total == red_metrics.failures == 3 and red_metrics.errors == red_metrics.skipped == 0
        failure_by_name = {case.get('name'): case.find('failure').get('message', '') for case in red}
        assert 'assert 1 == 2' in failure_by_name['test_correction_stale_cas_reports_persisted_current']
        assert 'TypeError' in failure_by_name['test_correction_explicit_config_revision_id'] and 'config_revision_id' in failure_by_name['test_correction_explicit_config_revision_id']
        assert 'TypeError' in failure_by_name['test_correction_explicit_secret_handle_id'] and 'secret_handle_id' in failure_by_name['test_correction_explicit_secret_handle_id']
        correction = json.loads((directory / 'correction-provenance.json').read_text(encoding='utf-8'))
        assert correction['test_wiring_commit_sha'] == status['test_wiring_commit_sha']
        assert correction['red_application_sha256'] != manifest['files']['src/controlplane/application/config_security/__init__.py']
        assert correction['red_application_sha256'] == hashlib.sha256((directory / 'correction-red-application.py').read_bytes()).hexdigest()
        assert correction['harness_sha256'] == hashlib.sha256((directory / 'correction-harness.py').read_bytes()).hexdigest()
        assert correction['red_before_fix'] and correction['red_exit_code'] == 1
        runtime = json.loads((directory / 'runtime-and-static.json').read_text(encoding='utf-8'))
        observed = runtime['runtime']
        assert observed['python'] == '3.13.15' and observed['psycopg'] == '3.3.5' and observed['psycopg_pool'] == '3.3.1'
        assert observed['m1_postgresql'] == observed['m2_postgresql'] == '18.6'
        assert observed['createdb'] is True and observed['orphan_db_count'] == 0
        assert observed['pool_public_import'] == 'psycopg_pool.ConnectionPool'
        assert observed['pool_runtime_class'] == 'psycopg_pool.pool.ConnectionPool'
        assert observed['borrowed_connection_class'] == 'psycopg.Connection'
        assert observed['m1_endpoint'] == '127.0.0.1:55432/aiavc_m1' and observed['m1_select_one']
        assert observed['temporal_server_version'] == 'temporal version 1.31.2'
        assert observed['temporal_archive_sha256'] == '044a4610695bb31bd5b982c818cd406c2ca88279ddaa776391a7dc909afe7a67'
        assert observed['temporal_executable_sha256'] == '5575b3693f37c9c0f19379a5744210ad9558ada54dadb2d1eabe74001a1f5e6b'
        assert observed['uv_runtime_observed'].startswith('uv 0.12.13 ') and observed['uv_lock_version'] == '0.12.13'
        assert observed['vault_encrypted'] and observed['vault_plaintext_secret_fields_absent']
        gates = runtime['static']
        assert gates['app_infra_forbidden_imports'] == gates['domain_application_imports'] == 0
        assert all(value for key, value in gates.items() if not key.endswith('imports'))
        drive = json.loads((directory / 'drive-e3-fresh.json').read_text(encoding='utf-8'))
        assert drive['status'] == 'PASS_E3_LIVE' and drive['sha256_verified'] and drive['process_isolated']
        assert drive['broker_pid'] != drive['desktop_pid'] and drive['broker_owns_oauth_provisioning']
        assert drive['desktop_vault_access'] is False and drive['desktop_refresh_token_retained'] is False
        assert drive['encryption_method'] == 'WINDOWS_DPAPI' and drive['desktop_disk_token_violations'] == 0
        assert (directory / 'historical-restoration.txt').read_text(encoding='utf-8').strip() == 'HISTORICAL_DRIVE_BYTES_RESTORED=PASS;SHA256=61fad77b8404646f742ef4fe6cef2329379445bd91adfb5456fd5fd82491ad0d'
        verify_package_provenance(directory, status)
        scan = json.loads((directory / 'secret-scan.json').read_text(encoding='utf-8'))
        assert scan['verdict'] == 'CLEAN' and scan['total_findings'] == 0 and scan['total_files_scanned'] > 0
        return {'semantic_verdict': 'PASS', 'source_commit_sha': sha, 'exact_counts': EXPECTED}

def main():
    directory = Path(__file__).resolve().parent
    register_semantic_profile(P5AClosureProfile())
    result = validate_package_evidence(directory, enforce_semantics=True)
    assert result.is_valid and result.semantic_summary['semantic_verdict'] == 'PASS'
    print('VALIDATION: PASS\nVERIFY_ONLY: PASS\nHASH_DAG: PASS')

if __name__ == '__main__':
    main()
