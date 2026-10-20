"""Inspect cached TESScut pixels for a rejected EB-like signal; never change its gates."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import warnings

import numpy as np

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "data/survey/p8"


def event_differences(time, flux, period, epoch, duration):
    """Local out-minus-in images, with a linear baseline for each complete event.

    In-event samples lie within half a duration. The two flanks span 0.8 to
    1.8 durations from the centre. Their mean images are interpolated to the
    mean in-event time. At least three cadences in each group are required.
    The median over events limits the influence of isolated bad epochs.
    """
    time, flux = np.asarray(time, dtype=float), np.asarray(flux, dtype=float)
    if time.ndim != 1 or not len(time) or flux.ndim != 3 or flux.shape[0] != len(time):
        raise ValueError("Expected one time per two-dimensional pixel image")
    if not (np.isfinite(time).all() and np.all(np.diff(time) > 0)):
        raise ValueError("Pixel times must be finite, unique and increasing")
    if not (np.isfinite([period, epoch, duration]).all() and 0 < duration < period / 4):
        raise ValueError("Expected a positive period and an isolated event duration")
    images, references, counts = [], [], []
    first, last = int(np.ceil((time[0] - epoch) / period)), int(np.floor((time[-1] - epoch) / period))
    for cycle in range(first, last + 1):
        centre = epoch + cycle * period
        dt = time - centre
        masks = [np.abs(dt) < 0.5 * duration,
                 (dt > -1.8 * duration) & (dt < -0.8 * duration),
                 (dt > 0.8 * duration) & (dt < 1.8 * duration)]
        sizes = [int(m.sum()) for m in masks]
        if min(sizes) < 3:
            continue
        inside, left, right = masks
        fraction = (time[inside].mean() - time[left].mean()) / (time[right].mean() - time[left].mean())
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            reference = (1 - fraction) * np.nanmean(flux[left], axis=0) + fraction * np.nanmean(flux[right], axis=0)
            images.append(reference - np.nanmean(flux[inside], axis=0))
        references.append(reference)
        counts.append({"cycle": cycle, "n_in": sizes[0], "n_left": sizes[1], "n_right": sizes[2]})
    if not images:
        raise ValueError("No event has sufficient in-event and two-sided baseline samples")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        stack = np.asarray(images)
        median = np.nanmedian(stack, axis=0)
        scatter = 1.4826 * np.nanmedian(np.abs(stack - median), axis=0)
        reference = np.nanmedian(references, axis=0)
    return {"difference": median, "event_scatter": scatter, "reference": reference,
            "counts": counts, "n_possible_events": max(0, last - first + 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True)
    ap.add_argument("--sectors", nargs="+", type=int, required=True)
    ap.add_argument("--gaia", type=Path, required=True, help="Saved Gaia cone with source coordinates and proper motions")
    ap.add_argument("--ephemeris", choices=("stageA", "fit"), default="stageA")
    ap.add_argument("--pixel-cache", type=Path, default=REPO / "data/cache/lightkurve/tesscut")
    args = ap.parse_args()
    args.gaia = args.gaia.resolve()
    args.pixel_cache = args.pixel_cache.resolve()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import SymLogNorm
    import lightkurve as lk
    from astropy.coordinates import SkyCoord
    from astropy.time import Time
    import astropy.units as u

    a_path = ROOT / "stageA" / f"{args.key}.json"
    a = json.loads(a_path.read_bytes())
    if a.get("rules_version") != "p8.0" or a["input_config"]["ingest_key"] != "3d160359ad":
        raise RuntimeError("Expected a current P8 ephemeris")
    nb_path = ROOT / "neighbours" / f"tic{a['tic_id']}.json"
    nb = json.loads(nb_path.read_bytes())
    eph = a["per_ephemeris"][a["chosen_ephemeris"]]["ephemeris"]
    ephemeris_sources = []
    if args.ephemeris == "fit":
        import audit_p5 as A
        from p8_stage_d_packets import setup
        setup(ROOT)
        fit_path = ROOT / "fit" / f"{args.key}.json"
        fit = json.loads(fit_path.read_bytes())
        if not A.cache_matches(fit) or fit.get("fit_input") != A._p8_fit_input(a["tic_id"], fit["survey_period"]):
            raise RuntimeError("Expected a fit of the current accepted Stage C ephemeris")
        adopted = fit["adopted"]
        eph = {"period": adopted["period"], "t0": adopted["t0_btjd"],
               "duration": adopted["t14_hours"] / 24, "source": "P8 physical fit"}
        ephemeris_sources = [fit_path, ROOT / "stageC" / f"{args.key}.json"]
    gaia = json.loads(args.gaia.read_bytes())
    if gaia.get("status") != "complete":
        raise RuntimeError("The Gaia follow-up query did not complete")
    objects = gaia["objects"]
    centre = SkyCoord(nb["ra"], nb["dec"], unit="deg")
    target_id = int(nb["gaia"]["target"]["source_id"])
    if not any(int(o["source_id"]) == target_id for o in objects):
        raise RuntimeError("The Gaia cone does not include this target")
    for obj in objects:
        obj["sep_arcsec_at_2016"] = float(centre.separation(SkyCoord(obj["ra"], obj["dec"], unit="deg")).arcsec)
    labels = sorted([o for o in objects if o["sep_arcsec_at_2016"] <= 90 and (o.get("phot_g_mean_mag") or 99) < 20],
                    key=lambda o: o["sep_arcsec_at_2016"])[:16]
    label_map = {int(o["source_id"]): str(i + 1) for i, o in enumerate(labels)}
    label_map[target_id] = "T"
    fig, axes = plt.subplots(len(args.sectors), 3, figsize=(12.5, 3.9 * len(args.sectors)),
                             squeeze=False, layout="constrained")
    sources = [a_path, nb_path, args.gaia, *ephemeris_sources]
    records, arrays = [], {}
    for row, sector in enumerate(args.sectors):
        pattern = f"tess-s{sector:04d}-*_{nb['ra']:.6f}_{nb['dec']:.6f}_21x21_astrocut.fits"
        paths = sorted(args.pixel_cache.glob(pattern))
        if len(paths) != 1:
            raise RuntimeError(f"Sector {sector}: expected one already-cached cutout, found {len(paths)}")
        sources.append(paths[0])
        tpf = lk.TessTargetPixelFile(str(paths[0]))
        time, flux = np.asarray(tpf.time.value), np.asarray(tpf.flux.to_value(u.electron / u.s))
        finite = np.isfinite(time)
        time, flux = time[finite], flux[finite]
        p = event_differences(time, flux, eph["period"], eph["t0"], eph["duration"])
        s = event_differences(time, flux, eph["period"], eph["t0"] + eph["period"] / 2, eph["duration"])
        positions = []
        for obj in objects:
            if obj.get("pmra") is not None and obj.get("pmdec") is not None:
                coord = SkyCoord(obj["ra"] * u.deg, obj["dec"] * u.deg, pm_ra_cosdec=obj["pmra"] * u.mas / u.yr,
                                 pm_dec=obj["pmdec"] * u.mas / u.yr, obstime=Time(2016, format="jyear"))
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    coord = coord.apply_space_motion(new_obstime=Time(np.median(time) + 2457000, format="jd"))
            else:
                coord = SkyCoord(obj["ra"], obj["dec"], unit="deg")
            x, y = tpf.wcs.world_to_pixel(coord)
            if -0.5 <= x < flux.shape[2] - 0.5 and -0.5 <= y < flux.shape[1] - 0.5:
                positions.append({"source_id": int(obj["source_id"]), "x": float(x), "y": float(y),
                                  "G": obj.get("phot_g_mean_mag"), "label": label_map.get(int(obj["source_id"]))})
        panels = [(p["reference"], "Local out-of-eclipse reference"),
                  (p["difference"], f"Primary difference: {len(p['counts'])} events"),
                  (s["difference"], f"Phase 0.5 difference: {len(s['counts'])} events")]
        for col, (values, title) in enumerate(panels):
            ax = axes[row, col]
            if col == 0:
                norm = SymLogNorm(linthresh=max(float(np.nanpercentile(np.abs(values), 25)), 1),
                                  vmin=float(np.nanmin(values)), vmax=float(np.nanmax(values)))
                im = ax.imshow(values, origin="lower", cmap="gray_r", norm=norm)
            else:
                scale = max(float(np.nanpercentile(np.abs(values), 99)), 1e-9)
                im = ax.imshow(values, origin="lower", cmap="RdBu_r", vmin=-scale, vmax=scale)
            for pos in positions:
                label = pos["label"]
                if label:
                    if label == "T":
                        ax.scatter(pos["x"], pos["y"], marker="+", s=42, color="cyan", linewidths=0.7)
                    else:
                        ax.scatter(pos["x"], pos["y"], marker="o", s=14, facecolors="none", edgecolors="cyan", linewidths=0.7)
                    ax.text(pos["x"] + 0.2, pos["y"] + 0.25, label, fontsize=7, color="#087f8c")
            ax.set(title=f"Sector {sector}: {title}", xlabel="Cutout column (zero based)", ylabel="Cutout row (zero based)")
            fig.colorbar(im, ax=ax, shrink=0.75, label="electrons / s")
        maxima = {}
        for name, result in [("primary", p), ("secondary", s)]:
            y, x = np.unravel_index(np.nanargmax(result["difference"]), result["difference"].shape)
            maxima[name] = {"row": int(y), "column": int(x), "difference_e_per_s": float(result["difference"][y, x])}
            for field in ("difference", "event_scatter", "reference"):
                arrays[f"s{sector}_{name}_{field}"] = result[field]
        records.append({"sector": sector, "n_cadences": len(time), "time_range_btjd": [float(time.min()), float(time.max())],
                        "median_cadence_s": float(np.median(np.diff(time)) * 86400), "primary_counts": p["counts"],
                        "secondary_counts": s["counts"], "gaia_positions": positions, "maximum_pixels": maxima})
    fig.suptitle(f"{args.key}: local out-minus-in difference images at P = {eph['period']:.8f} d\n"
                 "T = propagated Gaia target position; red = dimming. Pixel maxima are not fitted source positions.", fontsize=12)
    suffix = "fit_difference" if args.ephemeris == "fit" else "difference"
    stem = ROOT / "eb_screen" / f"{args.key}_{suffix}"
    fig.savefig(stem.with_name(stem.name + ".png"), dpi=140)
    plt.close(fig)
    np.savez_compressed(stem.with_name(stem.name + ".npz"), **arrays)
    metadata = {"key": args.key, "ephemeris": eph, "scope": "Pixel diagnostic only; no source identity, significance or funnel verdict is assigned.",
                "method": event_differences.__doc__, "gaia_labels": [{"label": label_map[int(o['source_id'])], **o} for o in labels],
                "sectors": records, "source_sha256": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    stem.with_name(stem.name + ".json").write_text(json.dumps(metadata, indent=1) + "\n", encoding="utf-8")
    print(stem.with_name(stem.name + ".png"))


if __name__ == "__main__":
    main()
