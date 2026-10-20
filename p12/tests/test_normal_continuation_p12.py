from pathlib import Path
from types import SimpleNamespace
import pytest
import continuation_p12 as C
import part0_plan_p12 as P
from p12_common import read,write

def test_native_launch_waits_for_python_caller(tmp_path,monkeypatch):
    root=tmp_path/'p12'
    for folder in ('protocol','manifests','logs','work'):(root/folder).mkdir(parents=True)
    (root/'protocol/launch_detached_p12.ps1').write_text('# native fixture')
    write(root/'manifests/example_jobs.json',[])
    monkeypatch.setattr(C,'ROOT',root);monkeypatch.setattr(C,'REPO',tmp_path)
    monkeypatch.setattr(C,'_preflight',lambda plan:None)
    monkeypatch.setattr(C.shutil,'which',lambda name:r'C:ixture\PowerShell\pwsh.exe')
    calls=[]
    def start(args,**kwargs):calls.append((args,kwargs));return SimpleNamespace(pid=987)
    monkeypatch.setattr(C.subprocess,'Popen',start)
    result=C._launch(dict(name='example',workers=8,deadline_s=600))
    plan=read(root/'manifests/example_native_launch.json')
    assert plan['blockers'] and all(row['pid'] and row['create_time'] and row['command'] for row in plan['blockers'])
    assert result['controller_start_waits_for_caller_exit']
    assert Path(calls[0][0][0]).stem.lower() in ('pwsh','powershell') and '-File' in calls[0][0]
    assert not (root/'manifests/example_launcher.json').exists()
    assert 'if %errorlevel% neq 0' in (root/'work/example_launch.cmd').read_text()

@pytest.mark.parametrize('phase,script',[('sector_probe','sector_probe_p12.py'),('ttt_fetch','fetch_ttt_p12.py')])
def test_online_phase_builder_pins_source_without_running_it(tmp_path,monkeypatch,phase,script):
    root=tmp_path/'p12';(root/'manifests').mkdir(parents=True)
    monkeypatch.setattr(P,'ROOT',root);monkeypatch.setattr(P,'REPO',tmp_path)
    monkeypatch.setattr(P,'source_snapshot',lambda:{'p12/protocol/'+script:'fixture'})
    rows=P.prepare_controller(dict(name=phase,script='p12/protocol/'+script,jobs='p12/manifests/'+phase+'_jobs.json'))
    assert len(rows)==1 and rows[0]['arguments']==['p12/protocol/'+script]
    assert rows[0]['source_hashes'] and rows[0]['attempt']==1


def test_native_shell_falls_back_to_windows_powershell_without_ps7_module_path(monkeypatch):
    monkeypatch.setattr(C.shutil,'which',lambda name:None)
    monkeypatch.setenv('PSModulePath',r'C:\fixture\PowerShell\7\Modules')
    seen={}
    def probe(args,**kwargs):seen.update(args=args,env=kwargs['env']);return SimpleNamespace(returncode=0)
    monkeypatch.setattr(C.subprocess,'run',probe)
    shell,env=C._native_shell()
    assert Path(shell).name.lower()=='powershell.exe' and 'PSModulePath' not in env and 'PSModulePath' not in seen['env']
