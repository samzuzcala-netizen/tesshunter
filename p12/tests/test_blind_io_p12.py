import json
from pathlib import Path
import subprocess
import sys
import pytest
import blind_io_p12 as guard


@pytest.mark.parametrize('relative',[
    'p9/truth/final_truth.csv',
    'data/cache/catalogs/spoc_tce/spoc_tce.ephemerides.csv',
    'data/survey/p12/catalogs/spoc_tce/spoc_tce.ephemerides.csv',
    'data/survey/p12/calibration/archival/truth/case.json',
    'data/survey/injections_p8.csv',
    'data/survey/p10/injections_2b.csv',
    'data/survey/p12/negatives/ttt_downloads/2506.05631.eprint.tar',
    'data/survey/p12/negatives/ttt_table.json',
])
def test_protected_registered_paths(relative):
    assert guard.is_protected(guard.REPO/relative)


def test_guard_caught_open_still_fails_job(tmp_path):
    guarded=tmp_path/'private/fixture.csv'
    guarded.parent.mkdir();guarded.write_text('fixture only')
    log=tmp_path/'opened.jsonl';probe=tmp_path/'A_guard_probe.py'
    module_path=str(Path(guard.__file__).parent)
    probe.write_text(
        'import sys\nsys.path.insert(0,'+repr(module_path)+')\n'
        'from blind_io_p12 import install,SidecarAccessError\n'
        'state=install('+repr(str(log))+',protected_paths=['+repr(str(guarded))+'])\n'
        'try:\n open('+repr(str(guarded))+').read()\n'
        'except SidecarAccessError:\n pass\n',encoding='utf-8')
    result=subprocess.run([sys.executable,str(probe)],capture_output=True,text=True,timeout=20)
    assert result.returncode==86
    rows=[json.loads(line) for line in log.read_text().splitlines()]
    assert any(row['denied'] for row in rows)


def test_normal_python_import_is_allowed():
    assert not guard.is_protected(guard.REPO/'p12/protocol/fetch_ttt_p12.py')
