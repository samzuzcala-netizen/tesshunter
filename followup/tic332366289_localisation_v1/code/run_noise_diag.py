"""Method-revision diagnostic (R1), CALIBRATION-half null windows only.

Pre-stated selection rule (before looking at any event): choose the baseline /
noise variant with the smallest mean (over sectors 57, 79, 80) interquartile
range of log10(chi2(M0)/(npix-3)) on the calibration windows; ties (< 0.02 dex)
go to the simpler variant (order below). Writes results/noise_model_revision.json.
"""
from __future__ import annotations

import csv

import common as C
import numpy as np

import core
import diffimg

VARIANTS = [("V0_deg1_mad", 1, "mad", False), ("V1_deg1_p2p", 1, "p2p", False), ("V2_deg1_bkg_p2p", 1, "p2p", True),
            ("V3_deg2_p2p", 2, "p2p", False), ("V4_deg1_bkg_mad", 1, "mad", True)]


def main():
    ctrl = list(csv.DictReader(open(C.RESULTS / "controls.csv")))
    out = {"rule": __doc__, "variants": {}}
    cat = None
    stats = {v[0]: {} for v in VARIANTS}
    for eid in ("E00", "E32", "E33", "E39"):
        ctx = core.EventContext(eid, cat=cat); cat = ctx.cat
        rows = [r for r in ctrl if int(r["sector"]) == ctx.sector and r["half"] == "calibration"]
        for name, deg, noise, bkg in VARIANTS:
            red = []
            for r in rows:
                di = diffimg.difference_image(ctx.S, float(r["tc_btjd"]), core.EA["duration_d"], deg=deg,
                                              noise=noise, bkg_regressor=bkg)
                m = ctx.fitter.fit_map(di["D"], di["sigma"], 1.0)
                red.append(m["chi2_0"] / (m["npix"] - 3))
            red = np.array(red)
            lr = np.log10(red)
            stats[name][str(ctx.sector)] = {"median_red": float(np.median(red)),
                                            "iqr_log10": float(np.percentile(lr, 75) - np.percentile(lr, 25)),
                                            "p10": float(np.percentile(red, 10)), "p90": float(np.percentile(red, 90)),
                                            "n": int(red.size)}
    score = {}
    for name, *_ in VARIANTS:
        score[name] = float(np.mean([stats[name][s]["iqr_log10"] for s in ("57", "79", "80")]))
    order = [v[0] for v in VARIANTS]
    smin = min(score.values())
    tied = [n for n in order if score[n] - smin < 0.02]   # stated rule: ties (< 0.02 dex) -> simpler (earlier) variant
    best = tied[0]
    out["variants"] = stats
    out["score_mean_iqr_log10_primary_sectors"] = score
    out["tie_group"] = tied
    out["selected"] = best
    out["implementation_note"] = ("first implementation bucketed scores by round(score/0.02), which does not implement the "
                                  "stated tie rule and printed V3; corrected to the stated rule before any event fit")
    C.write_json(C.RESULTS / "noise_model_revision.json", out)
    for n in order:
        print(n, "score %.3f" % score[n], {s: (round(v["median_red"], 2), round(v["iqr_log10"], 2), round(v["p10"], 2), round(v["p90"], 2))
                                           for s, v in stats[n].items()})
    print("selected", best)


if __name__ == "__main__":
    main()
