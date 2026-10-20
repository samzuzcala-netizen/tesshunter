"""Read-only contract probes for the inherited P10 Stage C implementation.

These probes record unfinished implementation work without modifying live source,
historical measurements or frozen rules. No TLS computation is launched.
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
import json
import os
import sys
import tempfile
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO/"src"),str(REPO/"scripts")]
os.environ.setdefault("LIGHTKURVE_CACHE",str(REPO/"data/cache/lightkurve"))
os.environ.setdefault("TESSHUNTER_OFFLINE","1")
from tesshunter import stage_c as SC
import revet_p6 as V

def main():
    issues = []
    key = "tic237222864_P10.2888"
    ws = REPO/"data/survey/p10/stage_c/p9/repro_hip"/key
    tls = json.loads((ws/"tls"/(key+".json")).read_text())
    fallback = V.spectrum_fallback(SimpleNamespace(OUT=ws),237222864,10.2888)
    sp = V.significant_peak_check(SimpleNamespace(OUT=ws),237222864,10.2888,tls,1,3,False,robust=True)
    issues.append({"id":"robust_result_overwritten_by_significant_peak",
        "rule":"0.4(i): triggered raw robust SDE >=9 at the same matching strongest peak may pass",
        "fallback_passes":fallback["passes_on_robust"],"raw_robust_sde":fallback["sde_robust_at_peak"],
        "inherited_significant_peak":sp["decision"],"reproduced":fallback["passes_on_robust"] and sp["decision"]=="FAIL",
        "cause":"significant_peak_check accepts robust as a metadata flag, but evaluates local/strongest installed SDE unchanged; stagec_one then overwrites its fallback decision."})
    tmp_parent = REPO/"p10/work"
    tmp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp_parent,prefix="contract_") as tmp:
        temp = Path(tmp); (temp/"tls").mkdir()
        rng=np.random.default_rng(20260908)
        installed=rng.normal(size=20000)
        installed[100]=12; installed[5000]=-400
        raw=rng.normal(size=20000); raw[100]=12
        p=np.linspace(.5,110,20000)
        np.savez(temp/"tls/tic1_P10.0000_spectrum.npz",periods=p,power=installed,power_raw=raw)
        result=V.spectrum_fallback(SimpleNamespace(OUT=temp),1,10)
        installed_trigger=SC.concentration(installed)["fraction"] > .5
        issues.append({"id":"fallback_trigger_uses_raw_instead_of_installed_concentration",
            "rule":"0.4(i): concentration is measured on installed power; raw power supplies SDE_robust",
            "installed_trigger":installed_trigger,"inherited_trigger":result["triggered"],
            "raw_robust_at_same_peak":result["sde_robust_at_peak"],
            "reproduced":installed_trigger and not result["triggered"],
            "cause":"spectrum_fallback overwrites triggered and passes_on_robust with values computed from raw-power concentration."})
    alias=SC.significant_peak(9.0,{"period":18.0,"SDE":30.0},[{"period":18.0,"SDE":30.0}],
        {"sde":12.0,"period":9.0,"is_local_maximum":True},alias_depths_consistent=None)
    issues.append({"id":"unmeasured_alias_depths_can_pass",
        "rule":"0.4(ii): 2:1 and 1:2 aliases keep the existing depth-consistency requirement",
        "inherited_decision":alias["decision"],"reproduced":alias["decision"]=="PASS",
        "cause":"significant_peak only rejects explicit False; a missing depth-consistency measurement is treated as nonblocking."})
    report={"utc":datetime.now(timezone.utc).isoformat(),"inherited_head":"dd9457b00cba1e8290aa53ae9467be8f9cc137c7",
        "scientific_source_modified":False,"tls_runs_launched":0,"issues":issues,
        "required_next_action":"After all existing and queued workers that load these files have ended, implement corrections to enforce the unchanged registered rules; preserve and reuse underlying spectra. Do not adopt current p10c output as final validation."}
    path=REPO/"p10/results/stage_c_inherited_contract_audit.json"
    path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()

