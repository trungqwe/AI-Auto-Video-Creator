import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

SUITES = {
    'p5a': (['tests/m2/test_p5a_config_and_secrets.py'], 5),
    'p4': (['tests/m2/test_p4_statemachines.py'], 9),
    'p3': (['tests/m2/test_p3_outbox_and_projections.py'], 11),
    'p2': (['tests/m2/test_p2_envelopes_and_idempotency.py'], 11),
    'p1': (['tests/m2/test_p1_db_and_workspace.py'], 11),
    'p0': (['tests/m2/test_p0_packaging.py', 'tests/m2/test_p0_evidence_validator.py', 'tests/m2/test_p0_architecture_rules.py'], 33),
    'architecture': (['tests/m2/test_p0_architecture_rules.py'], 6),
    'm1': (['tests/m1'], 93),
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    root = Path.cwd()
    source_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    mapping = subprocess.check_output(['docker', 'port', 'ai-auto-video-m2-pg', '5432/tcp'], text=True).splitlines()[0].strip()
    assert mapping.startswith('127.0.0.1:') and mapping.split(':')[1].isdigit()
    env = dict(os.environ)
    env['PYTHONPATH'] = str(root / 'src')
    assert env.get('M2_TEST_PG_DSN'), 'M2_TEST_PG_DSN_REQUIRED'
    historical = root / 'docs/milestones/m1-proof/evidence/m1-p3/drive_e3_evidence.json'
    backup = root / '.local-tools/safety/drive_e3_evidence.accepted-before-fresh-m1.json'
    assert historical.read_bytes() == backup.read_bytes()
    results = {}
    commands = []
    for sequence, (name, (paths, expected)) in enumerate(SUITES.items(), 1):
        command = [sys.executable, '-m', 'pytest', *paths, '-q', '-x', '--junitxml=' + str(output / (name + '.xml'))]
        started = datetime.now(timezone.utc).isoformat()
        log = output / (name + '-stdout.txt')
        try:
            with log.open('w', encoding='utf-8', newline='\n') as stream:
                process = subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT)
            if name == 'm1':
                (output / 'drive-e3-fresh.json').write_bytes(historical.read_bytes())
        finally:
            if name == 'm1':
                historical.write_bytes(backup.read_bytes())
        ended = datetime.now(timezone.utc).isoformat()
        commands.append({'run_id': output.name, 'sequence_idx': sequence, 'timestamp_utc': started, 'finished_utc': ended, 'source_commit_sha': source_sha, 'argv': [str(Path(sys.executable).relative_to(root)), *command[1:]], 'cwd': str(root), 'exit_code': process.returncode, 'created_artifacts': [log.name, name + '.xml'] + (['drive-e3-fresh.json'] if name == 'm1' else [])})
        (output / 'commands.jsonl').write_text(''.join(json.dumps(record) + '\n' for record in commands), encoding='utf-8')
        tree = ET.parse(output / (name + '.xml'))
        cases = list(tree.getroot().iter('testcase'))
        failures = sum(case.find('failure') is not None for case in cases)
        errors = sum(case.find('error') is not None for case in cases)
        skipped = sum(case.find('skipped') is not None for case in cases)
        metrics = {'total': len(cases), 'passed': len(cases)-failures-errors-skipped, 'failed': failures, 'errors': errors, 'skipped': skipped, 'identities': [case.get('classname') + '::' + case.get('name') for case in cases]}
        results[name] = metrics
        print(name.upper() + '=' + json.dumps({key: value for key, value in metrics.items() if key != 'identities'}), flush=True)
        (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
        assert process.returncode == 0 and metrics['passed'] == expected and metrics['total'] == expected and not (failures or errors or skipped), name + '_GATE_FAIL'
    assert historical.read_bytes() == backup.read_bytes()
    print('ALL_FRESH_SUITE_GATES=PASS;HISTORICAL_DRIVE_BYTES_RESTORED=PASS', flush=True)

if __name__ == '__main__':
    main()
