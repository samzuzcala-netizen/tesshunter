"""Prompt 4: the expected number of REAL new signals in ``targets_v1.csv``
under the MEASURED completeness curve of P2, next to the P1 model number.

P1 promised 5.0 expected new signals at mid priors with adopted pipeline
efficiencies of 0.8 / 0.7 / 0.4 for its classes A / B / C. P2 measured the
recovery fraction of injected transits as a function of matched-filter SNR
(``docs/COMPLETENESS.md``): 0% below 7.1, 6% at 7.1-9, 14% at 9-12, 37% at
12-20, 64% at 20-50, 89% at >= 50. This script re-runs the P1 per-star,
per-occurrence-cell yield with that step function in place of the logistic
ramp times the adopted efficiency. Everything else (occurrence grids, noise
model, geometric probability, prior completeness per class) is the P1 model
unchanged, so the difference is the efficiency alone.

Caveat, stated in the output: the P1 SNR is a photon-plus-floor model SNR
scaled to QLP's scatter; the P2 axis is the matched-filter SNR on this
pipeline's own detrended, binned data. They are not the same quantity, and
P2 judged the matched-filter one to be if anything the more optimistic.

Writes ``data/survey/p4/expected_yield_p4.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from tesshunter import survey_yield as sy  # noqa: E402

MDWARF_TEFF_MAX_K = 4000.0     # build_survey_population.DESIGN["mdwarf_teff_max_k"]
P_MAX_DAYS = 100.0             # stratum 3
PRIOR_KEY = "bright"           # stratum 3's prior-completeness key

# measured recovery by expected SNR (COMPLETENESS.md section 2), edges and values
MEASURED_EDGES = [0.0, 5.0, 7.1, 9.0, 12.0, 20.0, 50.0, np.inf]
MEASURED_FRACTION = [0.0, 0.0, 6 / 96, 17 / 120, 77 / 207, 237 / 368, 586 / 658]
MEASURED_N = [519, 131, 96, 120, 207, 368, 658]


def eff_measured(snr: np.ndarray) -> np.ndarray:
    idx = np.clip(np.searchsorted(MEASURED_EDGES, snr, side="right") - 1, 0, len(MEASURED_FRACTION) - 1)
    return np.asarray(MEASURED_FRACTION, float)[idx]


def stars_frame(targets: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "Tmag": pd.to_numeric(targets["tmag"]), "rad": pd.to_numeric(targets["radius_rsun"]),
        "mass": pd.to_numeric(targets["mass_msun"]), "contratio": pd.to_numeric(targets["contamination_ratio_used"]),
        "n_sectors_use": pd.to_numeric(targets["n_sectors_with_lc"]), "Teff": pd.to_numeric(targets["teff_k"]),
    }, index=targets.index)


def per_cell_snr(stars: pd.DataFrame, cells: list[dict], mode: str, contam_fill: float):
    """(snr, n_transits, rate*pgeo) arrays of shape (n_stars, n_cells), the P1 model's own formulae."""
    tmag, rstar, mstar, contam, nsec = sy._star_arrays(stars, contam_fill)
    sig = sy.noise_ppm_per_hour(tmag) * 1e-6
    d = sy.DETECTION
    snr = np.zeros((len(stars), len(cells)))
    ntr = np.zeros_like(snr)
    base = np.zeros_like(snr)
    for j, c in enumerate(cells):
        if c["rate"] <= 0:
            continue
        pmid = float(np.sqrt(c["p_lo"] * c["p_hi"]))
        depth = (c["r_rep"] * 0.009168 / np.clip(rstar, 0.05, None)) ** 2 / (1.0 + contam)
        t14 = sy.transit_duration_hours(pmid, rstar, mstar)
        pgeo = sy.geometric_probability(pmid, rstar, mstar)
        if mode == "single":
            n_tr = np.floor(d["sector_days"] * d["duty_cycle"] / pmid) * np.ones_like(nsec)
            n_tr = np.where(nsec >= 1, n_tr, 0.0)
        else:
            n_tr = np.floor(nsec * d["sector_days"] * d["duty_cycle"] / pmid)
        snr[:, j] = depth / sig * np.sqrt(t14 * n_tr)
        ntr[:, j] = n_tr
        base[:, j] = c["rate"] * pgeo
    return snr, ntr, base


def main() -> int:
    targets = pd.read_csv(REPO / "data" / "survey" / "targets_v1.csv")
    stars = stars_frame(targets)
    contam_fill = float(stars["contratio"].dropna().median())
    d = sy.DETECTION
    out = {"n_stars": int(len(stars)), "population": "data/survey/targets_v1.csv", "prior_key": PRIOR_KEY,
           "measured_curve": {"edges": [e if np.isfinite(e) else None for e in MEASURED_EDGES],
                              "fraction": MEASURED_FRACTION, "n_injections": MEASURED_N,
                              "source": "docs/COMPLETENESS.md section 2, recovered fraction by expected SNR"},
           "p1_model": {}, "measured_model": {}, "by_class_measured": {}, "by_cell_measured_mid": {},
           "caveat": ("P1 SNR is a photon-plus-floor model scaled to QLP scatter; the P2 axis is the matched-filter SNR "
                      "on the pipeline's own detrended 30-minute-binned data. Same symbol, different quantity; "
                      "P2 judged the matched-filter one the more optimistic of the two.")}

    # P1 model, reproduced with its own functions (should give the 5.0 of the memo at mid priors)
    tot_p1 = {lvl: 0.0 for lvl in ("low", "mid", "high")}
    tot_meas = {lvl: 0.0 for lvl in ("low", "mid", "high")}
    detectable_meas = 0.0
    detectable_p1_snr7 = 0.0
    by_class = {k: {lvl: 0.0 for lvl in ("low", "mid", "high")} for k in ("A", "B", "C")}
    by_class_detectable = {k: 0.0 for k in ("A", "B", "C")}
    by_cell = {}
    by_snr_band = {}
    for group, model in (("fgk", "km2020"), ("m", "dc15_grid")):
        sub = stars[stars["Teff"] > MDWARF_TEFF_MAX_K] if group == "fgk" else stars[stars["Teff"] <= MDWARF_TEFF_MAX_K]
        if len(sub) == 0:
            continue
        cells_le50 = sy.occurrence_cells(group, model, min(P_MAX_DAYS, 50.0))
        cells_full = sy.occurrence_cells(group, model, P_MAX_DAYS)
        cls = sy.class_yields(sub, cells_le50, cells_full, contam_fill=contam_fill)
        for lvl in tot_p1:
            tot_p1[lvl] += float(sy.new_signals_per_star(cls, PRIOR_KEY, lvl).sum())
        detectable_p1_snr7 += float(cls["stitched_snr7"].sum())

        # measured-curve version, cell by cell
        snr_st, ntr_st, base = per_cell_snr(sub, cells_full, "stitch", contam_fill)
        # single-sector SNR for the class-A test needs the same cells; cells beyond 50 d are never class A
        snr_single = np.zeros_like(snr_st)
        le50 = {c["label"] for c in cells_le50}
        s1, n1, _ = per_cell_snr(sub, cells_le50, "single", contam_fill)
        pos = {c["label"]: j for j, c in enumerate(cells_full)}
        for j, c in enumerate(cells_le50):
            if c["label"] in pos:
                snr_single[:, pos[c["label"]]] = np.where(n1[:, j] >= d["min_transits"], s1[:, j], 0.0)
        ok_ntr = ntr_st >= d["min_transits"]
        eff = np.where(ok_ntr, eff_measured(snr_st), 0.0)
        det = base * eff
        detectable_meas += float(det.sum())
        is_a = snr_single >= d["single_sector_snr_for_prior_search"]
        is_b = (~is_a) & (snr_st >= d["class_b_snr"])
        is_c = (~is_a) & (~is_b)
        for k, m in (("A", is_a), ("B", is_b), ("C", is_c)):
            by_class_detectable[k] += float((det * m).sum())
            for lvl in tot_meas:
                prior = sy.PRIOR_COMPLETENESS[PRIOR_KEY][k][lvl]
                v = float((det * m).sum() * (1.0 - prior))
                by_class[k][lvl] += v
                tot_meas[lvl] += v
        prior_mid = np.where(is_a, sy.PRIOR_COMPLETENESS[PRIOR_KEY]["A"]["mid"],
                             np.where(is_b, sy.PRIOR_COMPLETENESS[PRIOR_KEY]["B"]["mid"],
                                      sy.PRIOR_COMPLETENESS[PRIOR_KEY]["C"]["mid"]))
        new_mid = det * (1.0 - prior_mid)
        for j, c in enumerate(cells_full):
            by_cell[("M:" if group == "m" else "") + c["label"]] = {
                "detectable_measured": round(float(det[:, j].sum()), 4), "new_mid": round(float(new_mid[:, j].sum()), 4)}
        edges = MEASURED_EDGES
        for i in range(len(edges) - 1):
            band = f"{edges[i]:g}-{edges[i + 1]:g}"
            m = (snr_st >= edges[i]) & (snr_st < edges[i + 1]) & ok_ntr
            b = by_snr_band.setdefault(band, {"detectable_measured": 0.0, "new_mid": 0.0, "model_planets_transiting": 0.0})
            b["detectable_measured"] += float((det * m).sum())
            b["new_mid"] += float((new_mid * m).sum())
            b["model_planets_transiting"] += float((base * m).sum())

    out["p1_model"] = {"new_signals": {k: round(v, 3) for k, v in tot_p1.items()},
                       "detectable_stitched_snr7": round(detectable_p1_snr7, 3),
                       "efficiencies": sy.PIPELINE_EFFICIENCY,
                       "note": "P1 model re-evaluated with its own functions on targets_v1.csv (memo value 5.00 at mid)"}
    out["measured_model"] = {"new_signals": {k: round(v, 3) for k, v in tot_meas.items()},
                             "detectable_with_measured_curve": round(detectable_meas, 3),
                             "by_class_detectable": {k: round(v, 3) for k, v in by_class_detectable.items()},
                             "ratio_measured_over_p1_mid": round(tot_meas["mid"] / max(tot_p1["mid"], 1e-9), 3)}
    out["by_class_measured"] = {k: {lvl: round(v, 3) for lvl, v in d_.items()} for k, d_ in by_class.items()}
    out["by_cell_measured_mid"] = by_cell
    out["by_snr_band"] = {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in by_snr_band.items()}
    out["contam_fill_used"] = contam_fill
    out_path = REPO / "data" / "survey" / "p4" / "expected_yield_p4.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("p1_model", "measured_model", "by_class_measured", "by_snr_band")}, indent=1))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
