"""Per-sector noise calibration factor kappa from the CALIBRATION half of the
independent null control windows (never the evaluation half, never events).

kappa_s = sqrt(median over windows of chi2(M0) / (npix - 3)), computed with the
formal per-pixel errors (kappa = 1). Writes results/kappa.json.
"""
from __future__ import annotations

import csv

import common as C
import numpy as np

import core


def main():
    ctrl = list(csv.DictReader(open(C.RESULTS / "controls.csv")))
    out = {}
    cat = None
    for eid in ("E00", "E32", "E33", "E39"):
        ctx = core.EventContext(eid, cat=cat)
        cat = ctx.cat
        sec = ctx.sector
        rows = [r for r in ctrl if int(r["sector"]) == sec and r["half"] == "calibration"]
        red = []
        for r in rows:
            res = core.analyse(ctx, float(r["tc_btjd"]), core.EA["duration_d"], kappa=1.0, keep_maps=False)
            if res is None:
                continue
            red.append(res["chi2_0"] / (res["npix"] - 3))
        red = np.array(red)
        k = float(np.sqrt(np.median(red)))
        out[str(sec)] = {"kappa": k, "n_windows": int(red.size), "red_chi2_null_median": float(np.median(red)),
                         "red_chi2_null_p16_p84": [float(np.percentile(red, 16)), float(np.percentile(red, 84))],
                         "windows": "independent, calibration half (even independent index)"}
        print(sec, out[str(sec)])
    C.write_json(C.RESULTS / "kappa.json", out)


if __name__ == "__main__":
    main()
