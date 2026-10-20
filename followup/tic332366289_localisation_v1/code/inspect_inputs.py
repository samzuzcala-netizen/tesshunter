"""Record FITS metadata, time conventions and cadence identity of the inputs.

Writes inputs/fits_metadata.json and inputs/time_crosscheck.json (new files).
Read-only on every historical file.
"""
from __future__ import annotations

import common as C  # noqa: F401  (env first)
import numpy as np
from astropy.io import fits

KEYS_PRIMARY = ["TELESCOP", "INSTRUME", "SECTOR", "CAMERA", "CCD", "OBJECT", "TICID", "RA_OBJ",
                "DEC_OBJ", "TIMEREF", "TASSIGN", "TIMESYS", "BJDREFI", "BJDREFF", "TIMEUNIT",
                "TSTART", "TSTOP", "DATE-OBS", "DATE-END", "PROCVER", "FILEVER", "DATA_REL",
                "CREATOR", "ORIGIN", "TESSMAG", "TEFF", "RADIUS", "FFI_TYPE", "CRMITEN", "CRBLKSZ",
                "CRSPOC"]
KEYS_EXT = ["EXPOSURE", "TIMEDEL", "INT_TIME", "READTIME", "FRAMETIM", "NUM_FRM", "DEADC",
            "TIMEPIXR", "TIERRELA", "BACKAPP", "CDPP0_5", "CROWDSAP", "FLFRCSAP", "PDCVAR",
            "1CRV4P", "2CRV4P", "1CRPX4", "2CRPX4", "TIMESYS", "TIMEREF", "TASSIGN", "TIMEUNIT",
            "BJDREFI", "BJDREFF", "TSTART", "TSTOP", "TELAPSE", "LIVETIME", "BUNIT", "TUNIT2",
            "CDELT1", "CDELT2"]


def hdr_subset(h, keys):
    out = {}
    for k in keys:
        if k in h:
            v = h[k]
            out[k] = v if isinstance(v, (int, float, str, bool)) else str(v)
    return out


def main():
    meta = {"tesscut": {}, "spoc_lc": {}}
    for s, path in sorted(C.TESSCUT.items()):
        with fits.open(path, memmap=True) as hd:
            p, t = hd[0].header, hd[1].header
            cols = [c.name for c in hd[1].columns]
            d = hd[1].data
            time = np.array(d["TIME"], float)
            q = np.array(d["QUALITY"], int)
            flux = d["FLUX"]
            bkg = d["FLUX_BKG"] if "FLUX_BKG" in cols else None
            ferr = d["FLUX_ERR"]
            ap = hd[2].header if len(hd) > 2 else None
            finite = np.isfinite(time)
            rec = {
                "path": str(path), "sha256": C.sha256(path),
                "primary": hdr_subset(p, KEYS_PRIMARY),
                "ext1": hdr_subset(t, KEYS_EXT),
                "columns": cols,
                "n_cadences": int(len(time)), "n_finite_time": int(finite.sum()),
                "time_min": float(np.nanmin(time)), "time_max": float(np.nanmax(time)),
                "median_dt_s": float(np.nanmedian(np.diff(time[finite])) * 86400.0),
                "shape": list(flux.shape),
                "flux_bkg_all_zero": (None if bkg is None else bool(np.nanmax(np.abs(bkg)) == 0)),
                "flux_bkg_median": (None if bkg is None else float(np.nanmedian(bkg))),
                "flux_median": float(np.nanmedian(flux)),
                "flux_min_pixel_median": float(np.nanmin(np.nanmedian(flux, axis=0))),
                "flux_err_zero_frac": float(np.mean(np.asarray(ferr) == 0)),
                "flux_err_nan_frac": float(np.mean(~np.isfinite(np.asarray(ferr)))),
                "quality_nonzero_frac": float(np.mean(q != 0)),
                "quality_bits_present": sorted(int(b) for b in range(32) if np.any(q & (1 << b))),
                "timecorr_present": "TIMECORR" in cols,
            }
            if "TIMECORR" in cols:
                tc = np.array(d["TIMECORR"], float)
                rec["timecorr_min_s"] = float(np.nanmin(tc) * 86400)
                rec["timecorr_max_s"] = float(np.nanmax(tc) * 86400)
            if "CADENCENO" in cols:
                cn = np.array(d["CADENCENO"])
                rec["cadenceno_min"] = int(np.nanmin(cn)); rec["cadenceno_max"] = int(np.nanmax(cn))
            if "FFI_FILE" in cols:
                ff = d["FFI_FILE"]
                rec["ffi_file_first"] = str(ff[0]); rec["ffi_file_last"] = str(ff[-1])
            if ap is not None:
                rec["aperture_wcs"] = hdr_subset(ap, ["CTYPE1", "CTYPE2", "CRVAL1", "CRVAL2", "CRPIX1",
                                                      "CRPIX2", "CD1_1", "CD1_2", "CD2_1", "CD2_2",
                                                      "A_ORDER", "B_ORDER", "1CRV4P", "2CRV4P",
                                                      "CRVAL1P", "CRVAL2P", "WCSAXES", "NAXIS1", "NAXIS2"])
                rec["ext2_name"] = ap.get("EXTNAME")
            rec["ext1_wcs_keys"] = hdr_subset(t, ["1CTYP5", "2CTYP5", "1CRVL5", "2CRVL5", "1CRPX5", "2CRPX5",
                                                  "1CRV5P", "2CRV5P", "1CRV4P", "2CRV4P", "11PC5", "12PC5",
                                                  "21PC5", "22PC5", "1CDLT5", "2CDLT5", "WCSAXES"])
            meta["tesscut"][str(s)] = rec

    for s in (57, 77, 78, 79, 80, 84):
        path = C.spoc_lc(s)
        with fits.open(path, memmap=True) as hd:
            p, t = hd[0].header, hd[1].header
            cols = [c.name for c in hd[1].columns]
            d = hd[1].data
            time = np.array(d["TIME"], float)
            rec = {"path": str(path), "sha256": C.sha256(path),
                   "primary": hdr_subset(p, KEYS_PRIMARY), "ext1": hdr_subset(t, KEYS_EXT),
                   "columns": cols, "n_cadences": int(len(time)),
                   "time_min": float(np.nanmin(time)), "time_max": float(np.nanmax(time)),
                   "median_dt_s": float(np.nanmedian(np.diff(time[np.isfinite(time)])) * 86400.0),
                   "cadenceno_min": int(np.min(d["CADENCENO"])), "cadenceno_max": int(np.max(d["CADENCENO"]))}
            if len(hd) > 2:
                ap = hd[2].header
                rec["aperture_hdr"] = hdr_subset(ap, ["NPIXSAP", "NPIXMISS", "CROWDSAP", "FLFRCSAP", "1CRV4P",
                                                      "2CRV4P", "CRVAL1P", "CRVAL2P", "NAXIS1", "NAXIS2"])
            meta["spoc_lc"][str(s)] = rec
    C.write_json(C.INPUTS / "fits_metadata.json", C.clean(meta))

    # ---- time cross-check: TESScut vs TESS-SPOC, matched by nearest time
    xc = {}
    for s in (57, 77, 78, 79, 80, 84):
        with fits.open(C.TESSCUT[s], memmap=True) as a, fits.open(C.spoc_lc(s), memmap=True) as b:
            ta = np.array(a[1].data["TIME"], float)
            tb = np.array(b[1].data["TIME"], float)
            cb = np.array(b[1].data["CADENCENO"])
            ok_a = np.isfinite(ta); ok_b = np.isfinite(tb)
            ta_f, tb_f = ta[ok_a], tb[ok_b]
            idx = np.searchsorted(tb_f, ta_f)
            idx = np.clip(idx, 1, len(tb_f) - 1)
            left, right = tb_f[idx - 1], tb_f[idx]
            near = np.where(np.abs(ta_f - left) < np.abs(ta_f - right), left, right)
            dt = (ta_f - near) * 86400.0
            matched = np.abs(dt) < 60.0
            xc[str(s)] = {
                "n_tesscut_finite": int(ok_a.sum()), "n_spoc_finite": int(ok_b.sum()),
                "n_matched_within_60s": int(matched.sum()),
                "dt_s_median": float(np.median(dt[matched])) if matched.any() else None,
                "dt_s_min": float(np.min(dt[matched])) if matched.any() else None,
                "dt_s_max": float(np.max(dt[matched])) if matched.any() else None,
                "dt_s_p01": float(np.percentile(dt[matched], 1)) if matched.any() else None,
                "dt_s_p99": float(np.percentile(dt[matched], 99)) if matched.any() else None,
                "n_tesscut_nan_time": int((~ok_a).sum()), "n_spoc_nan_time": int((~ok_b).sum()),
                "spoc_cadenceno_range": [int(cb.min()), int(cb.max())],
            }
    C.write_json(C.INPUTS / "time_crosscheck.json", C.clean(xc))
    for k, v in xc.items():
        print(k, v)
    for k, v in meta["tesscut"].items():
        print("TESSCUT", k, v["primary"].get("CAMERA"), v["primary"].get("CCD"), v["shape"], v["median_dt_s"],
              "bkg0", v["flux_bkg_all_zero"], "bkgmed", v["flux_bkg_median"], "fluxmed", v["flux_median"],
              "minpixmed", v["flux_min_pixel_median"], "errzero", v["flux_err_zero_frac"],
              "q", v["quality_nonzero_frac"], v["quality_bits_present"], v.get("timecorr_min_s"), v.get("timecorr_max_s"))
        print("   ext1", v["ext1"])
        print("   ap", v.get("aperture_wcs"))
        print("   ext1wcs", v.get("ext1_wcs_keys"))
        print("   prim", v["primary"])
    for k, v in meta["spoc_lc"].items():
        print("SPOC", k, v["ext1"], v.get("aperture_hdr"), v["primary"].get("TIMEREF"), v["primary"].get("PROCVER"),
              v["primary"].get("DATA_REL"), v["primary"].get("CAMERA"), v["primary"].get("CCD"))


if __name__ == "__main__":
    main()
