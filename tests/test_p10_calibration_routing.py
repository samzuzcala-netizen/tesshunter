"""Exercise fresh-process calibration routing without running scientific workers."""
from pathlib import Path
import ast
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_calibration_preserves_original_numerical_function_bodies():
    def functions(path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return {n.name:ast.dump(n, include_attributes=False) for n in tree.body if isinstance(n, ast.FunctionDef)}
    original = functions(ROOT / "scripts/p8_completeness.py")
    adapted = functions(ROOT / "p10/protocol/p10_completeness_calibration.py")
    for name in ("expected_snr", "recovered_jobs", "install_injection", "load_funnel_outcomes", "require_settled_record"):
        assert adapted[name] == original[name], name


def test_calibration_fresh_children_use_p10_roots_and_explicit_preset(tmp_path):
    script = r'''
import json,sys,types
from pathlib import Path
root=Path(sys.argv[1]); temp=Path(sys.argv[2])
sys.path[:0]=[str(root/'p10/protocol'),str(root/'scripts'),str(root/'src')]
import p10_completeness_calibration as C
import p10_funnel_calibration as F
import audit_p5 as A
from tesshunter.survey import get_config
assert C.CONFIG == 'survey_p10'
for p in (C.P8,C.INJ_RUN,C.INJ_ROOT,C.FA_ROOT,F.OUT,F.PACKETS):
    assert p.resolve().is_relative_to((root/'data/survey/p10').resolve()),p
assert C.FA_RUN == root/'data/survey/runs/p10_2b/e_fa'
F.set_root(temp/'fa'); F.set_rules('p10.0')
assert A.INPUT_CONFIG.name=='survey_p10'
A.jdump(F.OUT/'named.json',dict(rules_version='p10.0',value=1))
rec=json.loads((F.OUT/'named.json').read_text())
assert rec['survey_preset']=='survey_p10'
assert rec['input_config']==A.input_config_for(get_config('survey_p10'))
A.jdump(F.OUT/'prior.json',dict(rules_version='p8.0',value=1))
assert 'survey_preset' not in json.loads((F.OUT/'prior.json').read_text())
commands=[]
class Child:
    def __init__(self,command,**kwargs):commands.append(command)
    def wait(self):return 0
F.subprocess.Popen=Child
F.eligible=lambda stage:[]
F.V.write_stage_csv=lambda stage:None
sys.modules['p8_stage_wait']=types.SimpleNamespace(wait_for_existing_workers=lambda *args:None)
F.run_stage('A',2,1,5,False,'p10.0')
assert len(commands)==2
for c in commands:
    assert Path(c[1])==root/'p10/protocol/p10_funnel_calibration.py'
    assert c[c.index('--root')+1]==str(temp/'fa')
    assert c[c.index('--rules')+1]=='p10.0'
commands.clear()
C.P8=temp/'calibration';C.INJ_ROOT=C.P8/'inj_funnel'
C.run_funnel(2,'p10.0',False)
assert len(commands)==2
for c in commands:
    assert Path(c[1])==root/'p10/protocol/p10_completeness_calibration.py'
    assert c[c.index('--rules')+1]=='p10.0'
print('fresh child paths, bound output roots and named record metadata verified')
'''
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    result = subprocess.run([sys.executable,"-c",script,str(ROOT),str(tmp_path)],
                            capture_output=True,text=True,env=env)
    assert result.returncode == 0, result.stdout+result.stderr
