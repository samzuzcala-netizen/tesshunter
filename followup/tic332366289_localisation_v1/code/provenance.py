"""Dependency/version record, pixel-input provenance table and compact arrays
for the review bundle. Writes inputs/versions.json, inputs/pixel_inputs.csv,
results/arrays_compact/*.npz."""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys

import common as C
import astropy
import matplotlib
import numpy as np
import scipy

import windows as W


def main():
    tdi = C.CACHE / "transit-diffImage_2b13199132ce"
    versions = {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "scipy": scipy.__version__,
                "astropy": astropy.__version__, "matplotlib": matplotlib.__version__,
                "interpreter": sys.executable,
                "environment_note": "existing tesshunter venv used read-only; no package installed or changed; caches redirected to D:",
                "transit_diffImage": {"repo": "https://github.com/stevepur/transit-diffImage", "commit": "2b13199132ce67f437b8cd9bb4eb128bd78e0d81",
                                      "used": "inspected only (not imported); conventions verified, own implementation written",
                                      "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(tdi.iterdir())}},
                "prf": json.load(open(C.INPUTS / "prf_provenance.json")),
                "gaia": json.load(open(C.INPUTS / "gaia_dr3_cone600_provenance.json")),
                "tic": json.load(open(C.INPUTS / "tic_cone400_provenance.json"))}
    C.write_json(C.INPUTS / "versions.json", versions)
    meta = json.load(open(C.INPUTS / "fits_metadata.json"))
    ev = json.load(open(C.RESULTS / "events.json"))
    rows = []
    for s, m in sorted(meta["tesscut"].items(), key=lambda kv: int(kv[0])):
        p, e1, wc = m["primary"], m["ext1"], m.get("aperture_wcs", {})
        k = m["ext1_wcs_keys"]
        sm = ev["sector_meta"][s]
        rows.append({"sector": s, "tesscut_file": m["path"], "sha256": m["sha256"], "camera": p.get("CAMERA"), "ccd": p.get("CCD"),
                     "origin_ccd_col_1CRV4P": e1.get("1CRV4P"), "origin_ccd_row_2CRV4P": e1.get("2CRV4P"),
                     "wcs_crval1": wc.get("CRVAL1"), "wcs_crval2": wc.get("CRVAL2"), "wcs_crpix1": wc.get("CRPIX1"), "wcs_crpix2": wc.get("CRPIX2"),
                     "pc11": k.get("11PC5"), "pc12": k.get("12PC5"), "pc21": k.get("21PC5"), "pc22": k.get("22PC5"),
                     "data_release": p.get("DATA_REL"), "astrocut_version": p.get("PROCVER"), "ffi_type": p.get("FFI_TYPE"),
                     "flux_convention": "calibrated e-/s, NOT background subtracted (FLUX_BKG all zero, BACKAPP 0)",
                     "flux_err_zero_frac": m["flux_err_zero_frac"], "flux_err_nan_frac": m["flux_err_nan_frac"],
                     "flux_err_used": "no (empirical reference-residual noise used instead)",
                     "tesscut_quality_bits_present": m["quality_bits_present"], "n_frames": sm["n_frames"], "n_good_frames": sm["n_good"],
                     "n_momentum_dump_frames": sm["n_dump"], "time_tesscut_minus_spoc_s_median": sm["dt_s_median"],
                     "time_tesscut_minus_spoc_s_range": f"{sm['dt_s_min']:.1f}..{sm['dt_s_max']:.1f}",
                     "spoc_lc_procver": meta["spoc_lc"][s]["primary"].get("PROCVER"), "spoc_lc_sha256": meta["spoc_lc"][s]["sha256"],
                     "spoc_crowdsap": sm["crowdsap"], "spoc_flfrcsap": sm["flfrcsap"], "spoc_aperture_npix": sm["spoc_aperture_npix"]})
    with open(C.INPUTS / "pixel_inputs.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        for r in rows:
            wr.writerow(r)
    out = C.RESULTS / "arrays_compact"
    out.mkdir(parents=True, exist_ok=True)
    for e in ("E00", "E32", "E33", "E39"):
        z = np.load(C.ARRAYS / "real" / f"{e}_primary.npz")
        keep = {k: z[k].astype(np.float32) for k in ("D", "sigma", "out", "inn", "chi2", "chi2p", "A", "sA", "grid_x", "grid_y",
                                                       "model_best", "resid_best", "model_target", "resid_target")}
        keep.update({k: z[k] for k in ("role", "ap", "box", "ser_time", "ser_role", "ser_ap", "ser_box3", "ser_bkg", "ser_cx", "ser_cy",
                                       "ser_sap", "ser_pdc")})
        np.savez_compressed(out / f"{e}_difference_image.npz", **keep)
    z = np.load(C.ARRAYS / "real" / "joint_maps.npz")
    np.savez_compressed(out / "joint_sky_maps.npz", **{k: z[k].astype(np.float32) for k in z.files})
    print("versions + pixel_inputs + compact arrays written:", sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    main()
