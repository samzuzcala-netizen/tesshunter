"""Check a fixed P8 fit with the existing small-aperture sky subtraction.

This diagnostic changes no fit, ephemeris, gate or candidate verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from p8_eb_aperture import extract

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "data/survey/p8"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True)
    args = ap.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import lightkurve as lk
    import astropy.units as u
    from tesshunter.secondary import box_depth
    import audit_p5 as A
    from p8_stage_d_packets import setup
    setup(ROOT)

    diff_path = ROOT / "eb_screen" / f"{args.key}_fit_difference.json"
    diff = json.loads(diff_path.read_bytes())
    fit_path = ROOT / "fit" / f"{args.key}.json"
    fit = json.loads(fit_path.read_bytes())
    tic = fit["tic_id"]
    if fit.get("fit_input") != A._p8_fit_input(tic, fit["survey_period"]):
        raise ValueError("The fit no longer matches the accepted Stage C input")
    for name, sha in diff["source_sha256"].items():
        if hashlib.sha256((REPO / name).read_bytes()).hexdigest() != sha:
            raise ValueError(f"Changed difference-image input: {name}")
    nb_path = ROOT / "neighbours" / f"tic{tic}.json"
    nb = json.loads(nb_path.read_bytes())
    source_id = int(nb["gaia"]["target"]["source_id"])
    eph = diff["ephemeris"]
    period, epoch, width = eph["period"], eph["t0"], eph["duration"]
    fig, axes = plt.subplots(3, len(diff["sectors"]), figsize=(12.5, 11.7), squeeze=False, layout="constrained")
    records, arrays = [], {}
    for col, sector in enumerate(diff["sectors"]):
        sec = sector["sector"]
        source = next(o for o in sector["gaia_positions"] if o["source_id"] == source_id)
        paths = [REPO / p for p in diff["source_sha256"] if f"tess-s{sec:04d}-" in p]
        if len(paths) != 1:
            raise ValueError("Expected one verified pixel input per sector")
        tpf = lk.TessTargetPixelFile(str(paths[0]))
        cube = np.asarray(tpf.flux.to_value(u.electron / u.s))
        net, aperture, background = extract(cube, source, sector["gaia_positions"])
        raw = np.sum(cube[:, aperture], axis=1)
        sky = raw - net
        time = np.asarray(tpf.time.value)
        keep = np.isfinite(time) & np.isfinite(net) & np.isfinite(raw)
        time, net, raw, sky = (v[keep] for v in (time, net, raw, sky))
        normalization = float(np.median(net))
        if normalization <= 0:
            raise ValueError("Nonpositive net aperture normalization")
        series = {"net": net / normalization,
                  "raw": 1 + (raw - np.median(raw)) / normalization,
                  "sky": 1 + (sky - np.median(sky)) / normalization}
        measurements = {name: box_depth(time, values, 0, period, epoch, width) for name, values in series.items()}
        phase = ((time - epoch) / period + .5) % 1 - .5
        dt = phase * period

        def folded(ax, x, y, edges, label, color):
            groups = np.searchsorted(edges, x, side="right") - 1
            means = [np.mean(y[groups == i]) if np.any(groups == i) else np.nan for i in range(len(edges) - 1)]
            ax.plot((edges[1:] + edges[:-1]) / 2, means, color=color, lw=1.2, label=label)

        for name, color in (("raw", "#758590"), ("sky", "#b87b30")):
            folded(axes[0, col], dt * 24, (series[name] - 1) * 1000,
                   np.linspace(-3 * width * 24, 3 * width * 24, 61), name, color)
        axes[0, col].set(title=f"Sector {sec}: aperture and sky", xlabel="Time from fixed transit (h)",
                         ylabel="Flux / median net target flux (ppt)")
        axes[0, col].legend(fontsize=8)
        draw = np.linspace(0, len(time) - 1, min(15000, len(time)), dtype=int)
        axes[1, col].scatter(phase[draw], (series["net"][draw] - 1) * 1000, s=1.4, alpha=.12)
        folded(axes[1, col], phase, (series["net"] - 1) * 1000, np.linspace(-.5, .5, 201), "net", "#b94328")
        lo, hi = np.quantile((series["net"] - 1) * 1000, [.005, .995])
        axes[1, col].set(xlim=(-.5, .5), ylim=(lo, hi), xlabel="Phase", ylabel="Net target aperture flux (ppt)", title="Full phase after sky subtraction")
        near = np.abs(dt) < 3 * width
        axes[2, col].scatter(dt[near] * 24, (series["net"][near] - 1) * 1000, s=2, alpha=.15)
        folded(axes[2, col], dt * 24, (series["net"] - 1) * 1000,
               np.linspace(-3 * width * 24, 3 * width * 24, 61), "net", "#b94328")
        axes[2, col].set(xlim=(-3 * width * 24, 3 * width * 24), ylim=(lo, hi), xlabel="Time from fixed transit (h)",
                         ylabel="Net target aperture flux (ppt)", title="Transit window after sky subtraction")
        for ax in axes[:, col]:
            ax.grid(alpha=.15)
        for name, array in {"time": time, **series, "aperture": aperture, "background": background}.items():
            arrays[f"s{sec}_{name}"] = array
        records.append({"sector": sec, "position": source, "n_cadences": len(time),
                        "n_aperture_pixels": int(aperture.sum()), "n_background_pixels": int(background.sum()),
                        "net_normalization_e_per_s": normalization, "measurements": measurements})
    fig.suptitle(f"{args.key}: fixed P = {period:.8f} d\nOne-pixel target aperture; the same 5-9 pixel sky annulus and Gaia masks in every sector", fontsize=12)
    stem = ROOT / "eb_screen" / f"{args.key}_target_aperture"
    fig.savefig(stem.with_name(stem.name + ".png"), dpi=140)
    plt.close(fig)
    np.savez_compressed(stem.with_name(stem.name + ".npz"), **arrays)
    result = {"key": args.key, "source_gaia_id": source_id, "ephemeris": eph, "method": extract.__doc__,
              "limitations": "Fixed apertures remain diluted; no detrending, ephemeris refit or gate change. Box errors use local point scatter and omit some correlated noise. Raw and sky variations use the net target normalization for comparison.",
              "sectors": records, "source_sha256": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                                                       for p in (diff_path, fit_path, nb_path)}}
    stem.with_name(stem.name + ".json").write_text(json.dumps(result, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"key": args.key, "measurements": [{"sector": r["sector"], **r["measurements"]} for r in records]}))
    print(stem.with_name(stem.name + ".png"))


if __name__ == "__main__":
    main()
