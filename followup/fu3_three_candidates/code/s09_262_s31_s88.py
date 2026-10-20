"""PROTOCOL 6: why do TIC 262843927 sectors 31 and 88 fail?  Geometry, pixel validity, expected flux at the WCS
position, background level and quality-flag behaviour, compared with passing sectors of the same star.
Outputs: results/s09_262_s31_s88.json, figures/262_s31_s88_scenes.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fu3_common import *
import pixels as PX

TIC = 262843927
GAIA = "4673750877131752832"
SECTORS = (31, 88, 28, 64, 69, 96)


def diag(s):
    p = CACHE / "cutouts" / f"{TIC}_s{s}.fits"
    if not p.exists():
        p = next((b / f"{TIC}_s{s}.fits" for b in (CONT / "analysis" / "cutouts", DEEP / "analysis" / "cutouts")
                  if (b / f"{TIC}_s{s}.fits").exists()), None)
    import lightkurve as lk
    tpf = lk.TessTargetPixelFile(str(p), quality_bitmask="none")
    cube = np.asarray(tpf.flux.value, float)
    q = np.asarray(tpf.quality, np.int64)
    t = np.asarray(tpf.time.value, float)
    c = PX.load_cube(p)
    pos = PX.positions(c, TIC)
    tgt = PX.target_of(pos, GAIA)
    ny, nx = c["shape"]
    ref = np.nanmedian(c["cube"], axis=0) if len(c["t"]) else np.full((ny, nx), np.nan)
    xi, yi = int(round(tgt["x"])), int(round(tgt["y"]))
    # expected target counts: 15,000 e-/s at T = 10 (TESS instrument handbook scale)
    expect = 15000 * 10 ** (-0.4 * (11.9833 - 10))
    peak_frac_typical = 0.35          # fraction of a star's flux in its brightest pixel (typical TESS PRF)
    loc = ref[max(0, yi - 1):yi + 2, max(0, xi - 1):xi + 2]
    hdr = tpf.hdu[1].header
    rec = dict(sector=s, file=str(p), camera=int(tpf.camera), ccd=int(tpf.ccd), cutout_origin_rowcol=[int(tpf.row), int(tpf.column)],
               target_xy=[tgt["x"], tgt["y"]], target_ccd_row=int(tpf.row) + tgt["y"], target_ccd_col=int(tpf.column) + tgt["x"],
               n_cadences=int(len(t)), n_good_default_mask=int(len(c["t"])), frac_all_nan_frames=float(np.mean(~np.isfinite(cube).any(axis=(1, 2)))),
               frac_frames_any_nan=float(np.mean(~np.isfinite(cube).all(axis=(1, 2)))),
               frac_pixels_nan_in_median=float(np.mean(~np.isfinite(np.nanmedian(cube, axis=0)))),
               quality_bits_present=sorted({b for b in range(20) if np.any(q & (1 << b))}),
               frac_quality_nonzero=float(np.mean(q != 0)),
               ref_peak_3x3=float(np.nanmax(loc)) if loc.size else None, ref_sum_3x3=float(np.nansum(loc)) if loc.size else None,
               expected_target_e_per_s=float(expect), expected_peak_pixel=float(expect * peak_frac_typical),
               ref_median_image=float(np.nanmedian(ref)), ref_min=float(np.nanmin(ref)), ref_max=float(np.nanmax(ref)),
               brightest_pixel_xy=[int(v) for v in np.unravel_index(np.nanargmax(ref), ref.shape)[::-1]] if np.isfinite(ref).any() else None,
               header=dict((k, str(hdr.get(k))) for k in ("1CRV4P", "2CRV4P", "1CRPX4", "2CRPX4", "TELESCOP", "TIMEDEL")),
               bkg_sky_median=float(np.nanmedian(ref[np.hypot(*np.indices(ref.shape)[::-1] - np.array([tgt['x'], tgt['y']])[:, None, None]) > 6])))
    # does the brightest star in the cutout sit where the WCS puts the target?
    if rec["brightest_pixel_xy"]:
        rec["brightest_minus_target_px"] = float(np.hypot(rec["brightest_pixel_xy"][0] - tgt["x"], rec["brightest_pixel_xy"][1] - tgt["y"]))
    return rec, ref, tgt


def main():
    recs = []
    fig, ax = plt.subplots(2, 3, figsize=(12, 7.5))
    for k, s in enumerate(SECTORS):
        try:
            r, ref, tgt = diag(s)
        except Exception as exc:   # noqa: BLE001
            r, ref, tgt = dict(sector=s, error=repr(exc)), None, None
        recs.append(r)
        a = ax.flat[k]
        if ref is not None and np.isfinite(ref).any():
            a.imshow(np.log10(np.clip(ref - np.nanmin(ref) + 1, 1, None)), origin="lower", cmap="gray_r")
            a.plot(tgt["x"], tgt["y"], "r+", ms=14, mew=2)
        a.set_title(f"S{s}: {r.get('camera')}-{r.get('ccd')} row {r.get('target_ccd_row', 0):.0f} col {r.get('target_ccd_col', 0):.0f}", fontsize=9)
        log("s09", f"S{s}: {json.dumps({k: r.get(k) for k in ('camera','ccd','target_ccd_row','target_ccd_col','n_good_default_mask','frac_pixels_nan_in_median','ref_peak_3x3','expected_peak_pixel','ref_median_image','brightest_minus_target_px','frac_quality_nonzero','quality_bits_present')})}")
    fig.suptitle("TIC 262843927 median cutout images (log); red + = Gaia position via cutout WCS")
    fig.tight_layout()
    fig.savefig(FIG / "262_s31_s88_scenes.png", dpi=120)
    save(RES / "s09_262_s31_s88.json", recs)


if __name__ == "__main__":
    main()
