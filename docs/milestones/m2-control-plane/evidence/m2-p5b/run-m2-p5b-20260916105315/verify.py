import hashlib, json, xml.etree.ElementTree as ET
from pathlib import Path
r=Path(__file__).parent
s=json.loads((r/'status.json').read_text(encoding='utf-8'))
assert s['status']=='BEHAVIORAL_RED_READY_FOR_REVIEW' and s['implementation_authorized'] is False
assert s['source_commit_sha']=='bd225c8cf1b3416f06dd96aea483db9cba757a62'
assert s['oracle_sha256']=='7660938d15e4c04e0ee0b400f3f280c736aa11925bf42607922ff8c34b291716'
red=s['suite_results']['p5b']; assert (red['total'],red['passed'],red['failed'],red['errors'],red['skipped'])==(5,0,5,0,0)
for name,n in {'p5a-regression':5,'p4-regression':9,'p3-regression':11,'p2-regression':11,'p1-regression':11,'p0-regression':33,'architecture':6,'m1-regression':93}.items():
 v=s['suite_results'][name]; assert (v['total'],v['passed'],v['failed'],v['errors'],v['skipped'])==(n,n,0,0,0)
rt=json.loads((r/'runtime-and-static.json').read_text(encoding='utf-8')); assert rt['postgresql']=='18.6' and rt['createdb'] and rt['m2_orphan_count']==0 and rt['production_0005_absent']
sec=json.loads((r/'secret-scan.json').read_text(encoding='utf-8')); assert sec=={'verdict':'CLEAN','total_findings':0,'files_scanned':sec['files_scanned']}
print('VALIDATION: PASS'); print('VERIFY_ONLY: PASS'); print('INTENTIONAL_BEHAVIORAL_RED: PASS')
