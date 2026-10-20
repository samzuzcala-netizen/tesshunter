"""RULES_K2 section 2: the default path (variant K1, no siblings) of the K2 Stage C worker reproduces a stored K1
Stage C receipt exactly.  Slow (one real Stage C, ~2 min): the fastest R-C job, dev_k1_144401492_p01, re-run
in a copy of its K1 case root through ``funnel_k2.py C``; the test's root and receipt are removed afterwards."""
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

K1_DATA = Path(r"D:\tesshunter_k1")
K2_DATA = Path(r"D:\tesshunter_k2")
CID = "dev_k1_144401492_p01"
PY = r"C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe"
HERE = Path(__file__).resolve().parents[1] / "protocol"
FIELDS = ("decision", "reason", "blind", "peaks", "spectrum_fallback", "inputs", "audit_verdict_tls",
          "decision_strongest_installed", "survey_period", "survey_depth_ppt", "stagec_rule_options")


@pytest.mark.skipif(not (K1_DATA / "runtimes" / "dev_k1_C" / f"{CID}.json").exists(), reason="K1 data not available")
def test_default_path_reproduces_k1_stage_c_receipt():
    k1_rt = json.loads((K1_DATA / "runtimes" / "dev_k1_C" / f"{CID}.json").read_text(encoding="utf-8"))
    k1_rec = json.loads((K1_DATA / "funnel_receipts" / "dev_k1" / "C" / f"{CID}.json").read_text(encoding="utf-8"))
    label = "k2test_" + uuid.uuid4().hex[:8]
    root = K2_DATA / "funnel" / label / CID
    rt = dict(k1_rt, root=str(root), label=label, k2_c_variant="K1", k2_siblings=[], k2_a1_scope=None,
              k2_copy_from=k1_rec["case_root"])
    rt_path = K2_DATA / "runtimes" / label / f"{CID}.json"
    rt_path.parent.mkdir(parents=True, exist_ok=True)
    rt_path.write_text(json.dumps(rt), encoding="utf-8")
    env = dict(os.environ, K1_DATA=str(K2_DATA), K2_DATA=str(K2_DATA))
    try:
        out = subprocess.run([PY, str(HERE / "funnel_k2.py"), "C", str(rt_path)], cwd=str(HERE), env=env,
                             capture_output=True, text=True, timeout=1800)
        assert out.returncode == 0, out.stdout + out.stderr
        rec = json.loads((K2_DATA / "funnel_receipts" / label / "C" / f"{CID}.json").read_text(encoding="utf-8"))
        assert rec["k2"]["c_variant"] == "K1" and rec["k2"]["c_input"]["n_sibling_masked"] == 0
        assert rec["k2"]["c_input"]["n_c_input"] == rec["k2"]["c_input"]["n_k1_input"]
        for f in FIELDS:
            assert rec["measurement"].get(f) == k1_rec["measurement"].get(f), f
    finally:
        shutil.rmtree(K2_DATA / "funnel" / label, ignore_errors=True)
        shutil.rmtree(K2_DATA / "funnel_receipts" / label, ignore_errors=True)
        shutil.rmtree(K2_DATA / "runtimes" / label, ignore_errors=True)
