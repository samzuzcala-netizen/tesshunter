"""Calibrated data-quality diagnostics for each event (real vs null windows).

(a) stripe statistic: sum over rows (cols) of (median of D/sigma along the row
    (col) across the full 21-px cutout / 0.2735)^2 -> extended row/column
    structure that a point source cannot make;
(b) baseline adequacy: median over fit-box pixels of MAD-scatter / p2p-scatter
    of the reference residuals (~1 if the baseline captures the trends);
(c) per-event pixel deficit at the target in ppt of the target flux vs the
    Stage A per-event PDCSAP and SAP depths.
Writes results/diagnostics.json.
"""
from __future__ import annotations

import csv
import json

import common as C
import numpy as np

import core
import diffimg
import scene as Sc

KAPPA = {int(k): v["kappa"] for k, v in json.load(open(C.RESULTS / "kappa.json")).items()}
REAL = json.load(open(C.RESULTS / "real_events.json"))
STAGEA = json.load(open(C.PACKET / "stageA.json"))
NORM = 1.2533 / np.sqrt(21.0)


def stats(ctx, tc):
    rec = core.PRIMARY_RECIPE
    a = diffimg.difference_image(ctx.S, tc, core.EA["duration_d"], deg=rec["deg"], noise="p2p", bkg_regressor=rec["bkg_regressor"])
    b = diffimg.difference_image(ctx.S, tc, core.EA["duration_d"], deg=rec["deg"], noise="mad", bkg_regressor=rec["bkg_regressor"])
    z = a["D"] / (a["sigma"] * KAPPA[ctx.sector])
    rows = np.median(z, axis=1) / NORM
    cols = np.median(z, axis=0) / NORM
    f = ctx.fitter
    ratio = float(np.median(b["ref_scatter"][f.rows, f.cols] / a["ref_scatter"][f.rows, f.cols]))
    return {"stripe_rows": float(np.sum(rows ** 2)), "stripe_cols": float(np.sum(cols ** 2)),
            "max_abs_row_median_z": float(np.max(np.abs(rows))), "argmax_row": int(np.argmax(np.abs(rows))),
            "mad_over_p2p": ratio}


def main():
    cat = Sc.load_catalogue()
    ctrl = list(csv.DictReader(open(C.RESULTS / "controls.csv")))
    out = {"definition": __doc__, "events": {}}
    ev = {e["n"]: e for e in STAGEA["per_ephemeris"]["survey"]["events"]}
    for eid in ("E00", "E32", "E33", "E39"):
        ctx = core.EventContext(eid, cat=cat)
        real = stats(ctx, ctx.tc)
        nulls = [stats(ctx, float(r["tc_btjd"])) for r in ctrl if int(r["sector"]) == ctx.sector]
        d = {"real": real, "n_null": len(nulls)}
        for k in ("stripe_rows", "stripe_cols", "mad_over_p2p"):
            v = np.array([n[k] for n in nulls])
            d[f"{k}_null_frac_ge_real"] = float(np.mean(v >= real[k]))
            d[f"{k}_null_median"] = float(np.median(v)); d[f"{k}_null_p95"] = float(np.percentile(v, 95))
        t = REAL[eid]["target"]
        ft = REAL[eid]["hosts"][C.GAIA_TARGET]["flux_e_s"]
        n = ctx.n
        d["pixel_deficit_at_target_ppt"] = [1000 * t["A"] / ft, 1000 * t["sA"] / ft]
        d["stageA_pdcsap_depth_ppt"] = [ev[n]["det_depth_ppt"], ev[n]["det_depth_err_ppt"]]
        d["stageA_sap_depth_ppt"] = [ev[n]["sap_depth_ppt"], ev[n]["sap_depth_err_ppt"]]
        crowd = ctx.S.meta["crowdsap"]
        # aperture-equivalent: what the target-position deficit implies for a PDCSAP-like (crowding-corrected) depth
        d["note"] = ("pixel deficit = A_target / f_target (total-flux normalisation); SPOC SAP depths are diluted by "
                     f"(1 - CROWDSAP) = {1 - crowd:.3f}, PDCSAP depths are crowding-corrected")
        out["events"][eid] = d
        print(eid, "stripe_rows real %.1f null med %.1f p95 %.1f frac>=real %.3f | cols %.1f frac %.3f | mad/p2p real %.2f null med %.2f p95 %.2f frac %.3f"
              % (real["stripe_rows"], d["stripe_rows_null_median"], d["stripe_rows_null_p95"], d["stripe_rows_null_frac_ge_real"],
                 real["stripe_cols"], d["stripe_cols_null_frac_ge_real"], real["mad_over_p2p"], d["mad_over_p2p_null_median"],
                 d["mad_over_p2p_null_p95"], d["mad_over_p2p_null_frac_ge_real"]),
              "| pixel %.1f+-%.1f ppt vs PDC %.1f+-%.1f, SAP %.1f+-%.1f" % (*d["pixel_deficit_at_target_ppt"], *d["stageA_pdcsap_depth_ppt"],
                                                                       *d["stageA_sap_depth_ppt"]))
    C.write_json(C.RESULTS / "diagnostics.json", C.clean(out))


if __name__ == "__main__":
    main()
