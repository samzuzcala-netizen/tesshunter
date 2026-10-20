"""Plot named rejected candidates for morphology review; never assign an EB type."""
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
    ap.add_argument("--keys", type=Path, required=True, help="JSON object with a keys list")
    args = ap.parse_args()
    output = ROOT / "eb_screen"
    output.mkdir(exist_ok=True)
    manifest = []
    for key in json.loads(args.keys.read_text(encoding="utf-8"))["keys"]:
        paths = [ROOT / "stageA" / f"{key}.json", ROOT / "secondary" / f"{key}.json",
                 ROOT / "tls" / f"{key}_lc.npz"]
        a, s = [json.loads(p.read_bytes()) for p in paths[:2]]
        if any(r.get("rules_version") != "p8.0" or (r.get("input_config") or {}).get("ingest_key") != "3d160359ad"
               for r in (a, s)) or s.get("gate") != "FAIL":
            raise RuntimeError(f"{key}: expected a current P8 secondary rejection")
        with np.load(paths[2]) as z:
            t, f = z["time_unbinned"], (z["flux_unbinned"] - 1) * 1000
        sec = s["secondary"]
        period, epoch = sec["period_days"], sec["epoch_btjd"]
        phase = ((t - epoch) / period) % 1
        finite = np.isfinite(t) & np.isfinite(f)
        t, f, phase = t[finite], f[finite], phase[finite]
        edges = np.linspace(0, 1, 301)
        groups = np.digitize(phase, edges) - 1
        # Leave unobserved phase bins empty instead of drawing a false bridge.
        bins = [(0.5 * (edges[i] + edges[i + 1]),
                 np.mean(f[groups == i]) if np.any(groups == i) else np.nan)
                for i in range(len(edges) - 1)]
        bins = np.asarray(bins)
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), layout="constrained")
        # Draw a representative observed interval, skipping a tiny first fragment.
        breaks = np.r_[0, np.flatnonzero(np.diff(t) > 0.5) + 1, len(t)]
        start, end = max(zip(breaks[:-1], breaks[1:]), key=lambda pair: pair[1] - pair[0])
        local = (t >= t[start]) & (t <= min(t[end - 1], t[start] + max(3.0, min(8.0, 5 * period))))
        axes[0].scatter(t[local] - t[start], f[local], s=2, alpha=0.35, color="#426681", rasterized=True)
        axes[0].set(xlabel=f"Days from BTJD {t[start]:.3f}", ylabel="Detrended corrected flux (ppt)",
                    title="An observed interval")
        draw = np.linspace(0, len(t) - 1, min(40000, len(t)), dtype=int)
        axes[1].scatter(phase[draw], f[draw], s=1, alpha=0.08, color="#426681", rasterized=True)
        axes[1].plot(bins[:, 0], bins[:, 1], color="#b94328", lw=1.4, label="Mean of all points in each phase bin")
        axes[1].set(xlabel="Phase", ylabel="Detrended corrected flux (ppt)", xlim=(0, 1), title="All observed sectors")
        axes[1].legend(fontsize=8, loc="lower right")
        lo, hi = np.quantile(f, [0.003, 0.997])
        for ax in axes:
            ax.set_ylim(lo - 0.05 * (hi - lo), hi + 0.05 * (hi - lo))
            ax.grid(alpha=0.15)
        fig.suptitle(f"{key}: P = {period:.7f} d | A {a['decision']}, S {s['gate']}\n"
                     f"Scan dips: {sec['n_dips_above_5sigma']}; variability flag: {sec['variability_flag']}", fontsize=11)
        path = output / f"{key}.png"
        fig.savefig(path, dpi=130)
        plt.close(fig)
        manifest.append({"key": key, "plot": str(path.relative_to(REPO)), "n_cadences": len(t),
                         "period_days": period, "epoch_btjd": epoch, "stageA": a["decision"],
                         "secondary": s["gate"], "variability_flag": sec["variability_flag"],
                         "source_sha256": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}})
        print(key, len(t), flush=True)
    (output / f"{args.keys.stem}_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
