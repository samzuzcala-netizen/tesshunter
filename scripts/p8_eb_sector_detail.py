"""Inspect a rejected signal across three sectors without changing its audit."""
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True)
    args = ap.parse_args()
    a_path = ROOT / "stageA" / f"{args.key}.json"
    lc_path = ROOT / "tls" / f"{args.key}_lc.npz"
    rec = json.loads(a_path.read_bytes())
    if rec.get("rules_version") != "p8.0" or rec.get("input_config", {}).get("ingest_key") != "3d160359ad":
        raise RuntimeError("Expected a current native P8 audit")
    eph = rec["per_ephemeris"][rec["chosen_ephemeris"]]["ephemeris"]
    with np.load(lc_path) as z:
        t, flat, sector, trend = (z[name] for name in
            ("time_unbinned", "flux_unbinned", "sector_unbinned", "trend_unbinned"))
    # clean_and_detrend stores flat = normalized corrected flux / trend.
    # Multiplication restores that flux on the retained cadences; clipped or
    # quality-rejected cadences are not reconstructed.
    corrected = flat * trend
    sectors = sorted(s for s in np.unique(sector) if np.count_nonzero(sector == s) >= 500)
    selected = [sectors[i] for i in sorted(set([0, len(sectors) // 2, len(sectors) - 1]))]
    fig, axes = plt.subplots(2, len(selected), figsize=(4.2 * len(selected), 6.8),
                             squeeze=False, layout="constrained")
    for col, s in enumerate(selected):
        mask = sector == s
        x, f, raw = t[mask], (flat[mask] - 1) * 1000, (corrected[mask] - 1) * 1000
        phase = ((x - eph["t0"]) / eph["period"]) % 1
        short = x <= x[0] + 4
        axes[0, col].scatter(x[short] - x[0], raw[short], s=2, alpha=0.4, color="#426681")
        axes[0, col].set(title=f"Sector {s}: before detrending", xlabel=f"Days from BTJD {x[0]:.3f}",
                         ylabel="Normalized corrected flux (ppt)")
        axes[1, col].scatter(phase, f, s=1, alpha=0.12, color="#426681")
        groups = np.minimum((phase * 150).astype(int), 149)
        for values, color, label in [(raw, "#697d69", "Before detrending"), (f, "#b94328", "After detrending")]:
            # Preserve unobserved phase gaps instead of drawing across them.
            bins = [(0.5 / 150 + i / 150, np.mean(values[groups == i]) if np.any(groups == i) else np.nan)
                    for i in range(150)]
            axes[1, col].plot(*np.asarray(bins).T, color=color, lw=1.5, label=label)
        axes[1, col].set(xlabel="Phase at the saved Stage A ephemeris", ylabel="Flux (ppt)", xlim=(0, 1))
        axes[1, col].legend(fontsize=8)
        for ax, values in [(axes[0, col], raw), (axes[1, col], np.r_[raw, f])]:
            lo, hi = np.quantile(values, [0.003, 0.997])
            ax.set_ylim(lo - 0.05 * (hi - lo), hi + 0.05 * (hi - lo))
            ax.grid(alpha=0.15)
    fig.suptitle(f"{args.key}: saved P = {eph['period']:.8f} d | A {rec['decision']}\n"
                 "First, middle and last available sectors; retained native cadences", fontsize=11)
    output = ROOT / "eb_screen" / f"{args.key}_sector_detail"
    output.parent.mkdir(exist_ok=True)
    image_path = output.with_name(output.name + ".png")
    metadata_path = output.with_name(output.name + ".json")
    fig.savefig(image_path, dpi=130)
    plt.close(fig)
    evidence = {"key": args.key, "ephemeris": eph, "sectors": [int(s) for s in selected],
                "method": "First four observed days and sector fold; before-detrend normalized corrected flux is saved flat times saved trend, on retained cadences only.",
                "source_sha256": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (a_path, lc_path)}}
    metadata_path.write_text(json.dumps(evidence, indent=1), encoding="utf-8")
    print(image_path)


if __name__ == "__main__":
    main()
