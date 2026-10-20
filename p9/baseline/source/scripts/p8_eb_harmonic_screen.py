"""Plot explicit shorter-period hypotheses for an already rejected P8 signal.

This diagnostic divides the saved A period without fitting a new period, and
never changes a funnel record. Compare sectors before assigning an EB label.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "data/survey/p8"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", required=True)
    parser.add_argument("--divisors", type=int, nargs="+", required=True)
    parser.add_argument("--sap", action="store_true", help="Prepare SAP using the existing secondary-scan path")
    args = parser.parse_args()
    if any(x < 2 for x in args.divisors) or len(set(args.divisors)) != len(args.divisors):
        parser.error("Use distinct integer divisors >= 2")
    paths = [ROOT / "stageA" / f"{args.key}.json", ROOT / "secondary" / f"{args.key}.json",
             ROOT / "tls" / f"{args.key}_lc.npz"]
    a, s = [json.loads(p.read_bytes()) for p in paths[:2]]
    for record in (a, s):
        if record.get("rules_version") != "p8.0" or record.get("input_config", {}).get("ingest_key") != "3d160359ad":
            raise RuntimeError("Expected a current native P8 audit")
    if s["gate"] != "FAIL":
        raise RuntimeError("This diagnostic is for rejected signals")
    eph = a["per_ephemeris"][a["chosen_ephemeris"]]["ephemeris"]
    sources = list(paths)
    if args.sap:
        import p8_funnel as F
        import audit_p5 as A
        F.set_root(ROOT)
        F.set_rules("p8.0")
        A.set_roots(ROOT, F.LC_ROOT)
        prep_path = ROOT / "prep" / f"{args.key}.json"
        prep = json.loads(prep_path.read_bytes())
        products = A.choose_per_sector(A.load_products(a["tic_id"]))
        sap = F.clean_and_detrend(products, prep["wotan"]["window_days"],
                                  flux_key="sap_flux", err_key="sap_flux_err")
        t, flat, sector, trend = (sap[name] for name in ("time", "flux", "sector", "trend"))
        sources += [prep_path, A.LC_DIR / f"tic{a['tic_id']}" / "index.json"]
        sources += [A.LC_DIR / f"tic{a['tic_id']}" / p["file"] for p in products]
    else:
        with np.load(paths[2]) as z:
            t, flat, sector, trend = (z[name] for name in
                ("time_unbinned", "flux_unbinned", "sector_unbinned", "trend_unbinned"))
    finite = np.isfinite(t) & np.isfinite(flat) & np.isfinite(trend)
    t, flat, sector, trend = (x[finite] for x in (t, flat, sector, trend))
    raw = (flat * trend - 1) * 1000
    flat = (flat - 1) * 1000
    sectors = sorted(x for x in np.unique(sector) if np.count_nonzero(sector == x) >= 500)
    if not sectors:
        raise RuntimeError("No sector has 500 retained native cadences")
    selected = [sectors[i] for i in sorted({0, len(sectors) // 2, len(sectors) - 1})]
    fig, axes = plt.subplots(len(args.divisors), len(selected),
                             figsize=(4.3 * len(selected), 3.6 * len(args.divisors)),
                             squeeze=False, layout="constrained")
    hypotheses, measurements = [], []
    from tesshunter.secondary import box_depth
    for row, divisor in enumerate(args.divisors):
        period = eph["period"] / divisor
        hypotheses.append({"divisor": divisor, "period_days": period, "epoch_btjd": eph["t0"]})
        for col, sn in enumerate(selected):
            take = sector == sn
            phase = ((t[take] - eph["t0"]) / period) % 1
            ax = axes[row, col]
            ax.scatter(phase, raw[take], s=1, alpha=0.10, color="#426681", rasterized=True)
            bins = np.minimum((phase * 100).astype(int), 99)
            for flux, color, label in ((raw[take], "#697d69", "Before detrending"),
                                       (flat[take], "#b94328", "After saved detrending")):
                means = [np.mean(flux[bins == i]) if np.any(bins == i) else np.nan for i in range(100)]
                ax.plot((np.arange(100) + 0.5) / 100, means, color=color, lw=1.5, label=label)
            lo, hi = np.quantile(raw[take], [0.003, 0.997])
            margin = 0.05 * max(hi - lo, 1)
            ax.set(xlim=(0, 1), ylim=(lo - margin, hi + margin), xlabel="Phase at hypothesis period",
                   ylabel="Normalized corrected flux (ppt)",
                   title=f"Sector {sn}: P / {divisor} = {period:.9f} d")
            ax.grid(alpha=0.15)
            ax.legend(fontsize=8)
        width = 0.06 * period
        for sn in sectors:
            take = sector == sn
            primary = box_depth(t[take], 1 + flat[take] / 1000, 0, period, eph["t0"], width)
            secondary = box_depth(t[take], 1 + flat[take] / 1000, 0.5, period, eph["t0"], width)
            measurements.append({"divisor": divisor, "period_days": period, "sector": int(sn),
                                 "box_width_days": width, "primary": primary, "secondary": secondary})
    flux_label = "SAP" if args.sap else "corrected flux"
    fig.suptitle(f"{args.key}: shorter-period hypotheses, no ephemeris fit\n"
                 f"First, middle and last sectors; {flux_label}, retained native cadences", fontsize=11)
    for ax in axes.flat:
        ax.set_ylabel(f"Normalized {flux_label} (ppt)")
    suffix = "_sap" if args.sap else ""
    base = ROOT / "eb_screen" / f"{args.key}{suffix}_harmonic_screen"
    plot_path = base.with_name(base.name + ".png")
    fig.savefig(plot_path, dpi=130)
    plt.close(fig)
    metadata = {"key": args.key, "stageA_ephemeris": eph, "hypotheses": hypotheses,
                "sectors": [int(x) for x in selected], "n_cadences": len(t),
                "flux": flux_label,
                "method": "Divide the saved A period and retain its epoch. SAP uses the existing secondary-scan preparation; corrected flux uses the saved A preparation. No new period or uncertainty is fitted; no missing cadence is reconstructed.",
                "box_measurements": measurements,
                "box_measurement_limit": "Assumed box width of 0.06 of each hypothesis period, fixed centres at phases 0 and 0.5, local baseline and point-scatter errors from secondary.box_depth. Centres and widths are not fitted; errors do not include correlated noise or period uncertainty.",
                "source_sha256": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in [*sources, Path(__file__)]}}
    base.with_name(base.name + ".json").write_text(json.dumps(metadata, indent=1) + "\n", encoding="utf-8")
    print(plot_path)


if __name__ == "__main__":
    main()
