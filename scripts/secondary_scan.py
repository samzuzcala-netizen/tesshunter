"""Secondary-eclipse phase scan for the prompt-6 Stage A survivors.

The prompt-6 funnel never looked for a secondary eclipse, and the P4 packets tested only
phase 0.5.  The rank-16 re-analysis found a 52-sigma secondary at phase 0.605, which both
would have missed.  This script closes that gap for every Stage A survivor: it folds the
prepared whole-baseline light curve at the survey ephemeris and scans EVERY phase for a dip.

A dip away from phase 0 is NOT by itself a secondary eclipse.  On a variable star a box scan
finds ppt-level dips at many phases, and the strongest of them means nothing.  A secondary is
claimed only when the scan is otherwise quiet - exactly one dip besides the primary - and that
dip is significant; a scan with four or more dips is reported as variability and no claim is
made.  The scan's own sigma percentiles are recorded so the reader can see which case it is.

Where a secondary IS established, it is decisive against a planet: at these periods the
deepest secondary a planet can make (thermal plus reflected light) is of order 1e-3 ppt, so
anything at the ppt level is a stellar companion.

Writes ``data/survey/p6/secondary_scan.json``.  Nothing here submits anything anywhere.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from rank16_analysis import box_depth  # noqa: E402  (same measurement, one definition)

SIG = 5.0
MIN_SEP = 0.02
OUT = REPO / "data" / "survey" / "p6" / "secondary_scan.json"


def planet_secondary_bound(P: float, rstar: float, mstar: float, teff: float, depth_ppt: float) -> dict:
    G = 6.674e-8
    a_rs = ((G * mstar * 1.989e33 * (P * 86400.0) ** 2) / (4 * math.pi ** 2)) ** (1 / 3) / (rstar * 6.957e10)
    teq = teff * math.sqrt(1.0 / (2.0 * a_rs))

    def planck(T, lam=8.0e-5):
        h, c_, kB = 6.626e-27, 2.998e10, 1.381e-16
        return 1.0 / (lam ** 5 * (math.exp(h * c_ / (lam * kB * T)) - 1.0))

    therm = planck(teq) / planck(teff) * depth_ppt
    refl = 1000.0 * 0.3 * (depth_ppt / 1000.0) / a_rs ** 2
    return {"a_over_rstar": round(a_rs, 2), "T_eq_K": round(teq, 0),
            "max_planetary_secondary_ppt": therm + refl}


def scan_one(A, tic: int, period: float, t0: float, dur: float, row: dict) -> dict:
    z = np.load(REPO / "data" / "survey" / "p6" / "tls" / f"tic{tic}_P{period:.4f}_lc.npz")
    t, f = z["time_unbinned"], z["flux_unbinned"]
    scan = [r for ph in np.arange(0.0, 1.0, 0.002) if (r := box_depth(t, f, ph, period, t0, dur))]
    if not scan:
        return {"tic_id": tic, "period_days": period, "error": "no usable phase scan"}
    sig = np.array([s["sigma"] for s in scan])
    dips, taken = [], []
    for i in np.argsort(-sig):
        if sig[i] < SIG:
            break
        ph = scan[i]["phase"]
        if any(min(abs(ph - q), 1 - abs(ph - q)) < MIN_SEP for q in taken):
            continue
        taken.append(ph)
        best = scan[i]
        for p2 in np.arange(ph - 0.01, ph + 0.01, 0.0004):
            r = box_depth(t, f, p2 % 1.0, period, t0, dur)
            if r and r["sigma"] > best["sigma"]:
                best = r
        dips.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in best.items()})
    dips.sort(key=lambda d: -d["sigma"])
    prim = next((d for d in dips if min(d["phase"], 1 - d["phase"]) < 0.03), None)
    secs = [d for d in dips if d is not prim]
    rstar = float(row["radius_rsun"]); mstar = float(row["mass_msun"] or rstar)
    teff = float(row["teff_k"]) if row.get("teff_k") not in (None, "", "nan") else 5500.0
    bound = planet_secondary_bound(period, rstar, mstar, teff, prim["depth_ppt"] if prim else 1.0)
    out = {"tic_id": tic, "period_days": period, "epoch_btjd": t0, "box_width_days": dur,
           "survey_depth_ppt": round(float(row["depth_ppt"]), 3), "n_points": int(len(t)),
           "n_dips_above_5sigma": len(dips), "primary": prim, "secondaries": secs,
           "planet_secondary_bound": bound}
    # How quiet is the rest of the scan?  A star whose box scan finds ppt-level dips at many
    # phases is variable, and a single off-phase dip there is not evidence of an eclipse.
    all_sig = np.sort(sig)[::-1]
    out["scan_sigma_percentiles"] = {"p50": round(float(np.percentile(sig, 50)), 2),
                                     "p90": round(float(np.percentile(sig, 90)), 2),
                                     "p99": round(float(np.percentile(sig, 99)), 2),
                                     "max": round(float(all_sig[0]), 2)}
    if not prim:
        out["verdict"] = "no dip at phase 0; nothing to interpret"
    elif not secs:
        out["verdict"] = "CLEAN: no dip above 5 sigma at any other phase"
    else:
        d = secs[0]
        out["secondary_over_primary_depth"] = round(d["depth_ppt"] / prim["depth_ppt"], 3)
        out["secondary_over_planet_bound"] = round(
            d["depth_ppt"] / max(bound["max_planetary_secondary_ppt"], 1e-12), 1)
        if len(dips) == 2 and d["sigma"] >= 20.0:
            out["verdict"] = ("SECONDARY ECLIPSE: exactly one other dip in the whole phase scan, "
                              "at high significance -> stellar companion")
        elif len(dips) == 2:
            out["verdict"] = ("POSSIBLE SECONDARY: exactly one other dip in the scan, but only "
                              f"{d['sigma']:.1f} sigma; not decisive on its own")
        elif len(dips) <= 3:
            out["verdict"] = "AMBIGUOUS: two or three dips away from phase 0"
        else:
            out["verdict"] = (f"VARIABILITY: {len(dips)} dips above 5 sigma at scattered phases, so the "
                              "scan is measuring stellar variability or red noise, not an eclipse; "
                              "no secondary claim is made")
    return out


def main() -> None:
    import audit_p5 as A
    A.set_roots(REPO / "data" / "survey" / "p6", REPO / "data" / "survey" / "audit_lc")
    import csv
    rows = {int(r["rank"]): r for r in csv.DictReader(
        open(REPO / "data" / "survey" / "p4" / "survivors.csv", newline="", encoding="utf-8"))}
    stageA = [json.loads(p.read_text(encoding="utf-8"))
              for p in (REPO / "data" / "survey" / "p6" / "stageA").glob("*.json")]
    passes = sorted([r for r in stageA if r["decision"] == "PASS"], key=lambda r: r["rank"])
    res = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "thresholds": {"min_sigma": SIG, "min_phase_separation": MIN_SEP,
                          "box_width": "the survey box duration", "reflected_albedo": 0.3,
                          "band_nm": 800},
           "population": "the seven prompt-6 Stage A survivors", "candidates": []}
    for r in passes:
        row = rows[r["rank"]]
        one = scan_one(A, r["tic_id"], r["survey"]["period"], r["survey"]["epoch_btjd"],
                       r["survey"]["duration_days"], row)
        one["rank"] = r["rank"]
        res["candidates"].append(one)
        p = one.get("primary") or {}
        print(f"rank {r['rank']:>3} TIC {r['tic_id']:>11} P={r['survey']['period']:.4f} d: "
              f"{one['n_dips_above_5sigma']} dip(s); primary {p.get('depth_ppt')} ppt at "
              f"{p.get('sigma')} sigma; {one['verdict']}")
        if one["verdict"].startswith(("SECONDARY", "POSSIBLE")):
            d = one["secondaries"][0]
            print(f"      -> dip at phase {d['phase']:.4f}: {d['depth_ppt']:.3f} +/- {d['err_ppt']:.3f} ppt "
                  f"({d['sigma']:.1f} sigma) = {one.get('secondary_over_primary_depth')} x the primary, "
                  f"{one.get('secondary_over_planet_bound')} x the deepest a planet could make")
        elif one["verdict"].startswith("VARIABILITY"):
            q = one["scan_sigma_percentiles"]
            print(f"      -> scan sigma p50 {q['p50']}, p90 {q['p90']}, p99 {q['p99']}, max {q['max']}: "
                  f"dips everywhere, no eclipse claim")
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
