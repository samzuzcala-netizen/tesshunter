"""Publication-style plots from the completed P8 injection outcomes; no new measurements."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
import numpy as np

REPO = Path(__file__).resolve().parents[1]
P8 = REPO / "data" / "survey" / "p8"


def interval(k, n):
    """95% Wilson interval for a binomial proportion."""
    p, z = k / n, 1.959963984540054
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return p, centre - half, centre + half


def main():
    result = json.loads((P8 / "completeness_p8.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader(open(P8 / "injection_outcomes_p8.csv", newline="", encoding="utf-8")))
    if len(rows) != result["n_injections"] or any(r["job_status"] != "ok" for r in rows):
        raise ValueError("complete injection outcomes required")
    snr = np.array([float(r["snr_expected"]) for r in rows])
    outcomes = [("Search", "search_only", np.array([r["recovered"] == "True" for r in rows]), "#2166ac", "s"),
                ("Search + pre-gate + A + secondary", "full_funnel_with_pregate",
                 np.array([r["through_funnel_pregated"] == "True" for r in rows]), "#c34a24", "o")]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.fonttype": "none"})
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    axis = axes[0, 0]
    edges = [0, 5, 7.1, 9, 12, 20, 50, np.inf]
    domain = np.geomspace(max(0.5, float(np.nanmin(snr[snr > 0]))), float(np.nanmax(snr)), 400)
    for label, level, outcome, colour, marker in outcomes:
        xs, ys, lower, upper = [], [], [], []
        for lo, hi in zip(edges[:-1], edges[1:]):
            selected = (snr >= lo) & (snr < hi) & (snr > 0)
            n = int(selected.sum())
            if not n:
                continue
            p, low, high = interval(int(outcome[selected].sum()), n)
            xs.append(np.exp(np.mean(np.log(snr[selected]))))
            ys.append(p); lower.append(p - low); upper.append(high - p)
        axis.errorbar(xs, ys, yerr=[lower, upper], fmt=marker, color=colour, capsize=3, label=label)
        fit = result["levels"][level].get("logistic")
        if fit:
            curve = 1 / (1 + np.exp(-(fit["a"] + fit["b"] * np.log(domain))))
            axis.plot(domain, curve, color=colour, lw=1.6, alpha=0.8)
    axis.set_xscale("log")
    axis.set_xlabel("Expected matched-filter SNR")
    axis.set_title("Recovery and fitted completeness curves", loc="left", fontweight="bold")

    for axis, field, bounds, title, xlabel, logarithmic in (
        (axes[0, 1], "period", np.geomspace(0.5, 30, 5), "Period", "Injected period (days)", True),
        (axes[1, 0], "rp_earth", [1, 1.41, 2, 2.83, 4], "Radius", "Injected radius (Earth radii)", True),
        (axes[1, 1], "tmag", [12.5, 13, 13.5, 14], "Brightness", "TESS magnitude", False),
    ):
        values = np.array([float(r[field]) for r in rows])
        centres = [np.sqrt(lo * hi) if logarithmic else (lo + hi) / 2 for lo, hi in zip(bounds[:-1], bounds[1:])]
        for index, (label, level, outcome, colour, marker) in enumerate(outcomes):
            for position, lo, hi in zip(centres, bounds[:-1], bounds[1:]):
                selected = (values >= lo) & (values < hi)
                n = int(selected.sum())
                if not n:
                    continue
                p, low, high = interval(int(outcome[selected].sum()), n)
                x = position * (1.035 if index else 0.965) if logarithmic else position + (0.04 if index else -0.04)
                axis.errorbar(x, p, yerr=[[p - low], [high - p]], fmt=marker, color=colour, capsize=3)
        for position, lo, hi in zip(centres, bounds[:-1], bounds[1:]):
            axis.text(position, 1.04, f"n={int(((values >= lo) & (values < hi)).sum())}", ha="center", fontsize=9, color="#666666")
        if logarithmic:
            axis.set_xscale("log")
            axis.xaxis.set_minor_locator(NullLocator())
        axis.set_xticks(centres, [f"{lo:.3g}–{hi:.3g}" for lo, hi in zip(bounds[:-1], bounds[1:])])
        axis.set_title(title, loc="left", fontweight="bold")
        axis.set_xlabel(xlabel)
    for axis in axes.flat:
        axis.set_ylim(-0.035, 1.13)
        axis.set_yticks(np.linspace(0, 1, 6), ["0%", "20%", "40%", "60%", "80%", "100%"])
        axis.set_ylabel("Injection recovery")
        axis.grid(axis="y", color="#dddddd", lw=0.6)
        axis.set_axisbelow(True)
    fig.suptitle(f"P8: native 200-second completeness\n{len(rows):,} injections on {result['n_stars']} stars; rules {result['rules_version']}",
                 fontsize=16, fontweight="bold")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncols=2, frameon=False)
    target = REPO / "docs" / "figures"
    target.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg"):
        fig.savefig(target / f"completeness_p8.{suffix}", dpi=180)
    plt.close(fig)
    print("wrote docs/figures/completeness_p8.png and .svg; intervals: 95% Wilson, within-bin binomial model")


if __name__ == "__main__":
    main()
