"""Build the submission packet for one candidate on one star (prompt 3, part D).

    python scripts/make_packet.py --tic 259377017 --period 5.66 --out docs/packets/toi270c_demo
    python scripts/make_packet.py --tic 259377017 --period 5.66 --no-centroid --no-fpp

Runs ``search_target`` (SPOC 2-min by default, up to 3 sectors) over a period
window bracketing ``--period``, picks the accepted candidate closest to it,
then runs the deferred expensive steps for that candidate only: the centroid
check on target pixel files, the TIC contamination check, TRICERATOPS, and
finally :func:`tesshunter.packet.build_packet`. A ``result.json`` with the
full search result and every stage's output is written next to the packet.
Nothing is submitted anywhere.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
REPO = Path(__file__).resolve().parent.parent
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
sys.path.insert(0, str(REPO / "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tic", type=int, required=True)
    ap.add_argument("--period", type=float, required=True, help="known or expected period (days)")
    ap.add_argument("--author", default="SPOC")
    ap.add_argument("--exptime", default="120")
    ap.add_argument("--max-units", type=int, default=3)
    ap.add_argument("--period-min", type=float, default=None)
    ap.add_argument("--period-max", type=float, default=None)
    ap.add_argument("--duration-max", type=float, default=0.2)
    ap.add_argument("--max-planets", type=int, default=3)
    ap.add_argument("--budget", type=float, default=1200.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--no-centroid", action="store_true")
    ap.add_argument("--no-fpp", action="store_true")
    ap.add_argument("--no-contamination", action="store_true")
    ap.add_argument("--crossmatch", action="store_true", help="run the hard-stop cross-match (network)")
    ap.add_argument("--n-draws", type=int, default=200_000)
    ap.add_argument("--mcmc", action="store_true", help="refit the chosen candidate with emcee for the packet")
    args = ap.parse_args()

    import logging
    logging.basicConfig(level=logging.WARNING)
    import numpy as np
    from tesshunter import fpp as fppmod, packet, stellar as stmod, transit_fit
    from tesshunter.centroid import run_centroid_check
    from tesshunter.contamination import run_contamination_check
    from tesshunter.pipeline import search_target

    p_known = args.period
    p_min = args.period_min if args.period_min is not None else max(0.5, p_known / 3.2)
    p_max = args.period_max if args.period_max is not None else min(40.0, p_known * 3.2)
    exptime = int(args.exptime) if str(args.exptime).isdigit() else args.exptime
    t0 = time.perf_counter()
    res = search_target(
        target=args.tic, mission="TESS", author=args.author, exptime=exptime, max_units=args.max_units,
        period_min=p_min, period_max=p_max, duration_min=0.01, duration_max=args.duration_max,
        max_planets=args.max_planets, bin_minutes=10.0, top_n=20, snr_min=5.0, snr_min_resolved=5.0,
        min_event_completeness=0.5, min_composite_score=3.0, min_transits=2, sigma_clip=4.0,
        mask_width_factor=7.0, artifact_periods=[], max_results=12, generate_report=False,
        time_budget_s=args.budget, do_crossmatch=args.crossmatch, hard_stop=False,
    )
    d = res.to_dict()
    print(f"search: {len(d['planets'])} candidate(s) in {time.perf_counter() - t0:.0f} s")
    if not d["planets"]:
        print("no candidates; nothing to package")
        return 1
    cand = min(d["planets"], key=lambda p: abs(float(p["period_days"]) / p_known - 1.0))
    if abs(float(cand["period_days"]) / p_known - 1.0) > 0.05:
        print(f"WARNING: closest candidate is at {cand['period_days']:.4f} d, not within 5% of {p_known}")
    num = int(cand["planet_num"])
    print(f"candidate {num}: P = {cand['period_days']:.5f} d, depth {cand['depth_ppt']:.3f} ppt "
          f"({cand.get('depth_source')}), SNR {cand['snr']:.1f}, verdict {cand.get('verdict')}")

    sectors = [int(s) for s in (d.get("provenance") or {}).get("units_used", [])]
    st = stmod.StellarParams.from_dict(d["stellar"]) if d.get("stellar") else None
    fit = cand.get("fit") or {}

    if args.mcmc and fit.get("success"):
        t1 = time.perf_counter()
        lc = res.lc_clean
        mf = transit_fit.fit_transit(
            np.asarray(lc.time.value, float), np.asarray(lc.flux.value, float),
            np.asarray(lc.flux_err.value, float) if lc.flux_err is not None else None,
            period=float(fit["period"]), t0=float(fit["t0"]), duration=float(fit["duration_days"]),
            depth_ppt=float(fit["depth_ppt"]), stellar=st, mcmc=True,
        )
        if mf.success:
            cand["fit"] = fit = mf.to_dict()
            print(f"emcee refit in {time.perf_counter() - t1:.0f} s: Rp/R* {mf.rp_rs:.4f}+/-{mf.rp_rs_err:.4f}")

    centroid = None
    if not args.no_centroid:
        t1 = time.perf_counter()
        centroid = run_centroid_check(args.tic, "TESS", sectors[:2], float(cand["period_days"]),
                                      float(cand["epoch_btjd"]), float(fit.get("duration_days") or cand["duration_days"]))
        print(f"centroid: available={centroid.available} shift={centroid.total_shift_px:.3f} px "
              f"sigma={centroid.sigma:.1f} flagged={centroid.flagged} ({time.perf_counter() - t1:.0f} s) {centroid.note[:100]}")

    contamination = None
    if not args.no_contamination and st is not None and st.ra is not None:
        t1 = time.perf_counter()
        contamination = run_contamination_check(st.ra, st.dec, st.tmag or 10.0, float(cand["depth_ppt"]))
        print(f"contamination: available={contamination.available} flagged={contamination.flagged} "
              f"n={contamination.n_neighbours_checked} ({time.perf_counter() - t1:.0f} s)")

    fpp_res = None
    if not args.no_fpp:
        t1 = time.perf_counter()
        lc = res.lc_clean
        fpp_res = fppmod.run_fpp(
            args.tic, sectors, np.asarray(lc.time.value, float), np.asarray(lc.flux.value, float), None,
            period=float(cand["period_days"]), t0=float(cand["epoch_btjd"]),
            duration=float(fit.get("duration_days") or cand["duration_days"]),
            depth_frac=float(cand["depth_ppt"]) / 1000.0, exp_time_days=2.0 / 1440.0,
            tmag=(st.tmag if st else None), aperture="auto", author=args.author, n_draws=args.n_draws,
            red_noise_beta=fit.get("beta_red_noise"),
        )
        print(f"FPP: available={fpp_res.available} FPP={fpp_res.fpp} NFPP={fpp_res.nfpp} "
              f"aperture={fpp_res.aperture_source} ({time.perf_counter() - t1:.0f} s) {fpp_res.error[:120]}")

    # Fold the pixel-level checks and TRICERATOPS into the candidate's verdict
    # (the packet shows both the light-curve-only and the final verdict).
    vet_entry = next((v for v in d["vetting"] if int(v.get("planet_num", 0)) == num), None)
    if vet_entry is not None and vet_entry.get("result") and (
            centroid is not None or contamination is not None or fpp_res is not None):
        from tesshunter.vetting import apply_pixel_checks, vetting_result_from_dict
        vr = vetting_result_from_dict(vet_entry["result"])
        verdict_final = apply_pixel_checks(vr, centroid, contamination, fpp=fpp_res)
        vet_entry["verdict_lc_only"] = vet_entry.get("verdict")
        vet_entry["verdict"] = verdict_final
        vet_entry["flags_high"] = list(vr.high_risk_flags)
        vet_entry["flags_medium"] = list(vr.medium_flags)
        vet_entry["notes"] = list(vr.notes)
        cand["verdict"] = verdict_final
        print(f"verdict after pixel checks: {verdict_final} (light curve only: {vet_entry['verdict_lc_only']})")

    out_dir = Path(args.out) if args.out else None
    summary = packet.build_packet(
        result=d, planet_num=num, lc_clean=res.lc_clean, stellar=st, fpp=fpp_res, centroid=centroid,
        contamination=contamination, out_dir=out_dir, label=args.label, tag=args.tag,
    )
    out_dir = Path(summary["files"]["packet_md"]).parent
    payload = {"search": d, "planet_num": num, "centroid": (centroid.__dict__ if centroid else None),
               "contamination": ({k: v for k, v in contamination.__dict__.items() if not k.endswith("neighbours")}
                                 if contamination else None),
               "fpp": (fpp_res.to_dict() if fpp_res else None), "packet": summary,
               "wall_s": time.perf_counter() - t0}
    (out_dir / "result.json").write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    print(f"packet written to {out_dir} in {time.perf_counter() - t0:.0f} s")
    for k, v in summary["files"].items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
