"""P12 copy of ``scripts/make_injection_spec.py`` for the extension calibration (5a).

Edits: the sample is given (``--sample``: the 300 eligible extension stars ordered by SHA-256 of
``20260920:ext_cal:<integer TIC>``, written by ``plan_part5_p12.py ext_sample``) instead of drawn with
``rng.choice``; the generator, the per-star loop, the limb darkening, ``a/R*`` and the column set are
unchanged; job ids carry the prefix ``ext`` (so no identity can meet a Part 2 ``inj`` job id in the shared
preparation folders); ``REPO`` and the ``src`` path are the repository's (this file lives in ``p12/protocol``).
Registered call: ``--per-star 2 --seed 20260920 --rp-earth-min 1 --rp-earth-max 4 --period-bins 0.5,30,4``.
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from tesshunter import survey  # noqa: E402

PERIOD_BINS = [(1.0, 2.5), (2.5, 6.3), (6.3, 16.0), (16.0, 40.0)]

R_EARTH_OVER_R_SUN = 0.009168


def log_bins(lo: float, hi: float, n: int) -> list[tuple[float, float]]:
    """``n`` equal log-width period bins over [lo, hi] (prompt 8: 4 bins over 0.5-30 d)."""
    edges = np.exp(np.linspace(np.log(lo), np.log(hi), n + 1))
    return [(float(a), float(b)) for a, b in zip(edges[:-1], edges[1:])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True)
    ap.add_argument("--n-stars", type=int, default=300)
    ap.add_argument("--per-star", type=int, default=7)
    ap.add_argument("--seed", type=int, default=20260902)
    ap.add_argument("--rp-min", type=float, default=0.01)
    ap.add_argument("--rp-max", type=float, default=0.12)
    ap.add_argument("--rp-earth-min", type=float, default=None,
                    help="draw the planet radius log-uniformly in EARTH radii between --rp-earth-min and "
                         "--rp-earth-max and convert to Rp/R* per star (prompt 8); overrides --rp-min/--rp-max")
    ap.add_argument("--rp-earth-max", type=float, default=None)
    ap.add_argument("--period-bins", default=None,
                    help="'lo,hi,n': n equal-log period bins over [lo, hi] d (default: the prompt-2 bins 1-40 d)")
    ap.add_argument("--b-max", type=float, default=0.9)
    ap.add_argument("--sample-out", default=str(REPO / "data" / "survey" / "completeness_sample_v1.csv"))
    ap.add_argument("--spec-out", default=str(REPO / "data" / "survey" / "injections_v1.csv"))
    args = ap.parse_args()
    period_bins = PERIOD_BINS
    if args.period_bins:
        lo, hi, n = args.period_bins.split(",")
        period_bins = log_bins(float(lo), float(hi), int(n))
    use_earth = args.rp_earth_min is not None and args.rp_earth_max is not None

    with open(args.sample, newline="", encoding="utf-8") as fh:
        sample = list(csv.DictReader(fh))
    if len(sample) != args.n_stars:
        raise SystemExit(f"sample holds {len(sample)} stars, not {args.n_stars}")
    rng = np.random.default_rng(args.seed)

    keep_cols = ["tic_id", "ra_deg", "dec_deg", "tmag", "teff_k", "radius_rsun", "mass_msun",
                 "contamination_ratio_used", "n_sectors_with_lc", "sectors_qlp", "sectors_tess_spoc",
                 "lc_products_available"]
    with open(args.sample_out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keep_cols + ["sample_seed"])
        w.writeheader()
        for r in sample:
            w.writerow({**{k: r.get(k, "") for k in keep_cols}, "sample_seed": args.seed})

    spec_cols = ["job_id", "tic_id", "period", "rp_rs", "b", "t0_frac", "a_rs", "u1", "u2",
                 "period_bin", "radius_rsun", "mass_msun", "teff_k", "tmag", "contamination_ratio_used",
                 "rp_earth"]
    n_spec = 0
    with open(args.spec_out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=spec_cols)
        w.writeheader()
        for si, r in enumerate(sample):
            tic = int(r["tic_id"])
            radius = float(r["radius_rsun"]) if r.get("radius_rsun") not in ("", None) else 1.0
            mass = float(r["mass_msun"]) if r.get("mass_msun") not in ("", None) and r["mass_msun"] == r["mass_msun"] else radius
            if not np.isfinite(mass) or mass <= 0:
                mass = radius
            teff = float(r["teff_k"]) if r.get("teff_k") not in ("", None) else 5500.0
            u1, u2 = survey.limb_darkening_for_teff(teff)
            for k in range(args.per_star):
                pb = (si * args.per_star + k) % len(period_bins)
                lo, hi = period_bins[pb]
                period = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
                rp_earth = ""
                if use_earth:
                    rp_earth = float(np.exp(rng.uniform(np.log(args.rp_earth_min), np.log(args.rp_earth_max))))
                    rp_rs = float(rp_earth * R_EARTH_OVER_R_SUN / radius)
                else:
                    rp_rs = float(np.exp(rng.uniform(np.log(args.rp_min), np.log(args.rp_max))))
                b = float(rng.uniform(0.0, args.b_max))
                t0_frac = float(rng.uniform(0.0, 1.0))
                a_rs = survey.a_over_rs(period, mass, radius)
                w.writerow({
                    "job_id": f"ext{n_spec:05d}_tic{tic}", "tic_id": tic,
                    "period": f"{period:.6f}", "rp_rs": f"{rp_rs:.5f}", "b": f"{b:.4f}",
                    "t0_frac": f"{t0_frac:.5f}", "a_rs": f"{a_rs:.4f}",
                    "u1": f"{u1:.4f}", "u2": f"{u2:.4f}", "period_bin": pb,
                    "radius_rsun": radius, "mass_msun": mass, "teff_k": teff,
                    "tmag": r.get("tmag", ""), "contamination_ratio_used": r.get("contamination_ratio_used", ""),
                    "rp_earth": (f"{rp_earth:.4f}" if use_earth else ""),
                })
                n_spec += 1
    print(f"period bins: {[(round(a, 3), round(b, 3)) for a, b in period_bins]}; "
          f"radius: {'%g-%g R_earth' % (args.rp_earth_min, args.rp_earth_max) if use_earth else '%g-%g Rp/R*' % (args.rp_min, args.rp_max)}")
    print(f"sample: {len(sample)} stars -> {args.sample_out}")
    print(f"spec:   {n_spec} injections -> {args.spec_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
