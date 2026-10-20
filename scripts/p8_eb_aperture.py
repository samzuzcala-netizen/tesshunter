"""Fold a small pixel aperture on the source implicated by an EB difference image."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "data/survey/p8"


def extract(flux, source, positions):
    """A radius-one-pixel aperture and a 5-to-9-pixel background annulus.

    Pixels within two pixels of a Gaia source with G < 18 are excluded
    from the background; at least sixteen sky pixels are required.
    Constant neighbouring flux within the aperture
    remains: returned depths are observed, diluted aperture depths.
    """
    yy, xx = np.indices(flux.shape[1:])
    radius2 = (xx - source["x"]) ** 2 + (yy - source["y"]) ** 2
    aperture = radius2 <= 1
    background = (radius2 >= 25) & (radius2 <= 81)
    for star in positions:
        if star.get("G") is not None and star["G"] < 18:
            background &= (xx - star["x"]) ** 2 + (yy - star["y"]) ** 2 > 4
    if aperture.sum() < 2 or background.sum() < 16:
        raise ValueError("Insufficient aperture or background pixels")
    values = np.sum(flux[:, aperture], axis=1) - aperture.sum() * np.nanmedian(flux[:, background], axis=1)
    return values, aperture, background


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True)
    ap.add_argument("--source-gaia", required=True, type=int)
    ap.add_argument("--source-tic", required=True, type=Path)
    args = ap.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import lightkurve as lk
    import astropy.units as u
    from tesshunter.secondary import box_depth, planet_secondary_bound

    difference_path = ROOT / "eb_screen" / f"{args.key}_difference.json"
    difference = json.loads(difference_path.read_bytes())
    args.source_tic = args.source_tic.resolve()
    tic = json.loads(args.source_tic.read_bytes())
    matches = [o for o in tic["objects"] if str(o.get("GAIA")) == str(args.source_gaia)]
    if len(matches) != 1:
        raise RuntimeError("Expected one TIC record matching the implicated Gaia source")
    star = matches[0]
    source_tic = int(star["ID"])
    eph = difference["ephemeris"]
    p, t0, width = eph["period"], eph["t0"], eph["duration"]
    fig, axes = plt.subplots(1, len(difference["sectors"]), figsize=(12.5, 4), squeeze=False, layout="constrained")
    records, arrays, sources = [], {}, [difference_path, args.source_tic]
    for col, sector in enumerate(difference["sectors"]):
        sec = sector["sector"]
        source = next(o for o in sector["gaia_positions"] if o["source_id"] == args.source_gaia)
        relative = [name for name in difference["source_sha256"] if f"tess-s{sec:04d}-" in name]
        if len(relative) != 1:
            raise RuntimeError("Expected one original cutout per sector")
        path = REPO / relative[0]
        if hashlib.sha256(path.read_bytes()).hexdigest() != difference["source_sha256"][relative[0]]:
            raise RuntimeError("The difference-image pixel input has changed")
        sources.append(path)
        tpf = lk.TessTargetPixelFile(str(path))
        values, aperture, background = extract(np.asarray(tpf.flux.to_value(u.electron / u.s)), source, sector["gaia_positions"])
        time = np.asarray(tpf.time.value)
        finite = np.isfinite(time) & np.isfinite(values)
        time, values = time[finite], values[finite]
        normalizer = float(np.median(values))
        if normalizer <= 0:
            raise ValueError("Nonpositive aperture normalization")
        flux = values / normalizer
        phase = ((time - t0) / p + 0.25) % 1 - 0.25
        primary = box_depth(time, flux, 0, p, t0, width)
        secondary = box_depth(time, flux, 0.5, p, t0, width)
        if primary is None or secondary is None:
            raise ValueError("Insufficient eclipse samples")
        bound = planet_secondary_bound(p, float(star["rad"]), float(star["mass"]), float(star["Teff"]), primary["depth_ppt"])
        bins = np.minimum(((phase + 0.25) * 200).astype(int), 199)
        folded = np.array([(i / 200 - 0.25 + 1 / 400, np.mean((flux[bins == i] - 1) * 1000))
                           for i in range(200) if np.any(bins == i)])
        ax = axes[0, col]
        draw = np.linspace(0, len(time) - 1, min(15000, len(time)), dtype=int)
        ax.scatter(phase[draw], (flux[draw] - 1) * 1000, s=1.5, alpha=0.1, color="#426681")
        ax.plot(folded[:, 0], folded[:, 1], color="#b94328", lw=1.5)
        lo, hi = np.quantile((flux - 1) * 1000, [0.005, 0.995])
        ax.set(xlim=(-0.25, 0.75), ylim=(lo, hi), xlabel="Phase at the saved ephemeris", ylabel="Observed aperture flux (ppt)",
               title=f"Sector {sec}: primary {primary['depth_ppt']:.1f}, secondary {secondary['depth_ppt']:.1f} ppt")
        ax.grid(alpha=0.15)
        for name, array in [("time", time), ("flux", flux), ("aperture", aperture), ("background", background)]:
            arrays[f"s{sec}_{name}"] = array
        records.append({"sector": sec, "position": source, "n_cadences": len(time), "n_aperture_pixels": int(aperture.sum()),
                        "n_background_pixels": int(background.sum()), "normalization_e_per_s": normalizer,
                        "primary": primary, "secondary": secondary, "planet_secondary_bound": bound})
    fig.suptitle(f"TIC {source_tic}: Gaia {args.source_gaia}, P = {p:.8f} d\n"
                 "Separate TESScut aperture; local background removed, no detrending or dilution correction", fontsize=11)
    stem = ROOT / "eb_screen" / f"tic{source_tic}_aperture"
    fig.savefig(stem.with_name(stem.name + ".png"), dpi=140)
    plt.close(fig)
    np.savez_compressed(stem.with_name(stem.name + ".npz"), **arrays)
    result = {"source_tic_id": source_tic, "source_gaia_id": args.source_gaia, "originating_candidate": args.key,
              "ephemeris": eph, "method": extract.__doc__, "stellar_parameters_source": "MAST TIC record, not a binary-star fit",
              "limitations": "Observed aperture depths remain diluted. Box-depth errors use local point scatter and do not include all correlated noise. The catalogue stellar parameters may describe a composite source. No ephemeris uncertainty was fitted here.",
              "sectors": records, "source_sha256": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    stem.with_name(stem.name + ".json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(records))
    print(stem.with_name(stem.name + ".png"))


if __name__ == "__main__":
    main()
