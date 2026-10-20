"""Repair P9 control-reader root routing; preserve the failed v1 attempts."""
from common import *
environment()
import sys,ast,time
sys.path.insert(0,str(ROOT/'protocol'))
from controls import legacy_inventory_functions

def main(tic):
    started=time.perf_counter();raw=REPO/'p9/inputs/raw';idx=read(raw/f'tic{tic}/index.json')
    cache=Path(idx['cache']);reader=legacy_inventory_functions()
    original=REPO/'p11/protocol/input_inventory.py';tree=ast.parse(original.read_text(encoding='utf-8'))
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='inventory_host')
    code=ast.unparse(function)
    old="rawdir = REPO / f'data/survey/audit_lc/tic{tic}'"
    assert code.count(old)==1
    code=code.replace(old,"rawdir = RAW_ROOT / f'tic{tic}'")
    reader['RAW_ROOT']=raw;exec(compile(code,'p11.5-control-audit-root-v2','exec'),reader)
    paths=[]
    for p in cache.rglob('*.fits'):
        if f'{tic:016d}' in p.name and (p.name.endswith('_lc.fits') or p.name.endswith('_llc.fits')):paths.append(p)
    result=reader['inventory_host'](dict(tic_id=tic),paths)
    result.update(p11_5_repair=dict(version='control-audit-v2',original_source_sha256=sha(original),
        repair='Read P9 controls from their recorded raw and download cache roots',raw_root=str(raw),fits_cache=str(cache)),
        p11_5_wall_seconds=time.perf_counter()-started)
    write(ROOT/f'results/control_inputs/tic{tic}.json',result)
    print('P9 control audited',tic,flush=True)

if __name__=='__main__':main(int(sys.argv[1]))
