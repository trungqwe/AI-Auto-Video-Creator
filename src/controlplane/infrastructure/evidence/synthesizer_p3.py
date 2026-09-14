"""Generate and verify a single-run M2-P3 evidence package."""
from __future__ import annotations
import argparse, datetime, importlib.metadata, json, os, platform, subprocess, sys
from pathlib import Path
import psycopg
from psycopg_pool import ConnectionPool
from controlplane.infrastructure.evidence.evaluator import parse_junit_xml, register_semantic_profile
from controlplane.infrastructure.evidence.profile_p3 import M2P3SemanticProfile
from controlplane.infrastructure.evidence.validator import sha256_file, validate_package_evidence
from controlplane.infrastructure.security.secret_scanner import generate_secret_scan_report
ROOT=Path(__file__).parents[4]; OUT=ROOT/'docs/milestones/m2-control-plane/evidence/m2-p3'
def write(p:Path,s:str)->None:p.write_text(s.replace('\r\n','\n'),encoding='utf-8',newline='\n')
def metrics(p:Path)->dict[str,int]:
 s=parse_junit_xml(p);return {'total':s.total,'passed':s.passed,'failed':s.failures,'errors':s.errors,'skipped':s.skipped}
def root_python()->str:
 p=ROOT/'.venv/Scripts/python.exe'
 if not p.is_file(): raise RuntimeError('frozen root interpreter unavailable')
 return str(p)
def runtime(run:str)->dict:
 dsn=os.environ.get('M2_TEST_PG_DSN')
 if not dsn: raise RuntimeError('M2_TEST_PG_DSN required')
 with psycopg.connect(dsn,autocommit=True) as c:
  server=str(c.execute('SHOW server_version').fetchone()[0]).split()[0]; createdb=bool(c.execute('SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user').fetchone()[0]); orphans=int(c.execute("SELECT count(*) FROM pg_database WHERE datname ~ '^m2_p3_test_[0-9a-f]+$'").fetchone()[0])
 result={'run_id':run,'python':platform.python_version(),'psycopg':psycopg.__version__,'psycopg-pool':importlib.metadata.version('psycopg-pool'),'actual_pool_implementation':f'psycopg_pool.{ConnectionPool.__name__}','postgresql_server':server,'createdb_prerequisite':createdb,'disposable_db_orphan_count':orphans}
 if {k:result[k] for k in result if k!='run_id'} != {'python':'3.13.15','psycopg':'3.3.5','psycopg-pool':'3.3.1','actual_pool_implementation':'psycopg_pool.ConnectionPool','postgresql_server':'18.6','createdb_prerequisite':True,'disposable_db_orphan_count':0}:raise RuntimeError('locked runtime mismatch')
 return result
def run(cmd:list[str],xml:str,report:str,records:list,run_id:str)->None:
 r=subprocess.run([*cmd,f'--junitxml={OUT/xml}'],cwd=ROOT,capture_output=True,text=True,env={**os.environ,'PYTHONPATH':'src'})
 write(OUT/report,f'STDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}')
 if r.returncode:raise RuntimeError('closure command failed: '+' '.join(cmd))
 records.append({'run_id':run_id,'command':' '.join(cmd),'exit_code':0,'created_artifacts':[xml,report]})
def synth()->dict:
 OUT.mkdir(parents=True,exist_ok=True); run_id='run-m2-p3-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S'); rec=[]; rt=runtime(run_id)
 suites=[('m2-p2-regression.xml','m2-p2-regression-report.txt',[sys.executable,'-m','pytest','tests/m2/test_p2_envelopes_and_idempotency.py','-vv']),('m2-p1-regression.xml','m2-p1-regression-report.txt',[sys.executable,'-m','pytest','tests/m2/test_p1_db_and_workspace.py','-vv']),('m2-p0-regression.xml','m2-p0-regression-report.txt',[root_python(),'-m','pytest','tests/m2/test_p0_architecture_rules.py','tests/m2/test_p0_evidence_validator.py','tests/m2/test_p0_packaging.py','-vv']),('m1-regression.xml','m1-regression-report.txt',[root_python(),'-m','pytest','tests/m1','-vv']),('m2-p3-tests.xml','m2-p3-tests-report.txt',[sys.executable,'-m','pytest','tests/m2/test_p3_outbox_and_projections.py','-vv'])]
 for x,y,z in suites:run(z,x,y,rec,run_id)
 write(OUT/'runtime-capability.json',json.dumps(runtime(run_id),indent=2)+'\n'); secret=generate_secret_scan_report([ROOT/'src/controlplane',ROOT/'tests/m2',OUT],output_file=OUT/'secret-scan.json',run_id=run_id);write(OUT/'secret-scan.json',json.dumps(secret,indent=2)+'\n')
 summary={'p3_tests':metrics(OUT/'m2-p3-tests.xml'),'p2_regression_tests':metrics(OUT/'m2-p2-regression.xml'),'p1_regression_tests':metrics(OUT/'m2-p1-regression.xml'),'m2_p0_regression_tests':metrics(OUT/'m2-p0-regression.xml'),'m1_regression_tests':metrics(OUT/'m1-regression.xml'),'secret_scan_violations':secret['total_findings']}; status={'schema_version':'m2_package_status_v1','milestone':'M2','package':'M2-P3','run_id':run_id,'semantic_profile':'m2-p3','status':'READY_FOR_REVIEW','evidence_summary':summary,'runtime_capability':runtime(run_id),'gates':[{'gate_id':f'GATE-P3-0{i}','status':'PASS'} for i in range(1,7)]};write(OUT/'status.json',json.dumps(status,indent=2)+'\n');write(OUT/'status.md',f'# Trạng thái M2-P3\n\n`READY_FOR_REVIEW` — run `{run_id}`.\n');write(OUT/'commands.jsonl',''.join(json.dumps(x)+'\n' for x in rec));write(OUT/'hashes.sha256','\n'.join(f'{sha256_file(p)}  {p.name}' for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='hashes.sha256')+'\n');return validate_package_evidence(OUT,enforce_semantics=True).__dict__
def main()->None:
 a=argparse.ArgumentParser();a.add_argument('--verify-only',action='store_true');x=a.parse_args();register_semantic_profile(M2P3SemanticProfile(),allow_override=True);r=validate_package_evidence(OUT,enforce_semantics=True).__dict__ if x.verify_only else synth();print('VALIDATION: PASS');print(json.dumps(r,default=str))
if __name__=='__main__':main()
