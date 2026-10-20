import subprocess,sys
from common import ROOT
import pytest


@pytest.mark.parametrize('module',['blind_search_worker','funnel_worker'])
def test_worker_rejects_changed_runtime_before_parsing_or_science(tmp_path,module):
    code='''import importlib,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1]);module=importlib.import_module(sys.argv[3])
root=Path(sys.argv[2]);module.ROOT=root
p=root/'synthetic_runtime.json';p.write_text('not valid JSON')
args=[p,'0'*64] if sys.argv[3]=='blind_search_worker' else ['A',p,'0'*64]
try:module.main(*args)
except RuntimeError as exc:assert 'frozen controller job' in str(exc)
else:raise AssertionError('Changed runtime was accepted')
assert not (root/'results/search_receipts').exists()
assert not (root/'results/funnel').exists()
'''
    subprocess.run([sys.executable,'-c',code,str(ROOT/'protocol'),str(tmp_path),module],capture_output=True,text=True,check=True)
