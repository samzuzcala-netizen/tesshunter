from pathlib import Path
import json,subprocess,sys,random
from common import ROOT,host_hash
from nested_order import order,timing_pilot,stratum


def sample():
    return [dict(tic_id=i+100,tmag=12.5+(i%3)*.5,n_usable_sectors=[3,6,12][(i//3)%3],n_cad=1000+i//2) for i in range(93)]


def test_nested_order_is_permutation_and_input_order_independent():
    rows=sample();expected=order(rows)
    random.Random(2026091402).shuffle(rows)
    assert order(rows)==expected
    assert len({r['tic_id'] for r in expected})==len(rows)
    for key in {stratum(r) for r in rows}:
        observed=[r['tic_id'] for r in expected if r['stratum']==key]
        assert observed==[r['tic_id'] for r in sorted((r for r in rows if stratum(r)==key),key=lambda r:host_hash(r['tic_id']))]


def test_timing_hash_selects_two_per_point_count_tercile():
    rows=sample();pilot=timing_pilot(rows);ordered=sorted(rows,key=lambda r:(r['n_cad'],r['tic_id']))
    for i in range(3):
        group=ordered[i*31:(i+1)*31]
        expected=sorted(group,key=lambda r:host_hash(r['tic_id'],'timing'))[:2]
        assert [r['tic_id'] for r in pilot if r['tercile']==i]==[r['tic_id'] for r in expected]


def test_guard_records_numpy_reads_and_blocks_sidecar_before_content_access(tmp_path):
    program='''import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,sys.argv[1])
from blind_io import install,summary,SidecarAccessError
root=Path(sys.argv[2]);ordinary=root/'prepared.npz';sidecar=root/'spoc_tce.ephemerides.csv'
np.savez(ordinary,time=np.arange(3));sidecar.write_text('must never be read')
state=install(root/'io.jsonl',sidecar)
with np.load(ordinary) as z:assert len(z['time'])==3
try:sidecar.read_text()
except SidecarAccessError:pass
else:raise AssertionError('Sidecar guard did not block')
print(json.dumps(summary(state)))
'''
    r=subprocess.run([sys.executable,'-c',program,str(ROOT/'protocol'),str(tmp_path)],capture_output=True,text=True,check=True)
    result=json.loads(r.stdout)
    assert len(result['sidecar_open_attempts'])==1
    events=[json.loads(s) for s in (tmp_path/'io.jsonl').read_text().splitlines()]
    assert any(Path(e['path']).name=='prepared.npz' and not e['denied'] for e in events)
    assert any(e['denied'] for e in events)
