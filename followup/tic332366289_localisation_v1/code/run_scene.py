"""Scene construction + registration check for each event (out-of-event image).

Writes results/scene.json, neighbours.csv, results/scene_arrays/*.npz (D:),
figures/scene_<event>.png.
"""
from __future__ import annotations

import csv
import json

import common as C
import numpy as np

import data as Dm
import diffimg
import prf as P
import scene as Sc
import windows as W

EVENTS = [("E00", 57, 0), ("E32", 79, 32), ("E33", 80, 33), ("E39", 84, 39)]
EA = W.CFG["ephemerides"]["primary"]
SIG_FLOOR = W.CFG["registration"]["sigma_floor_px"]


def main():
    cat = Sc.load_catalogue()
    by_id = {c["source_id"]: c for c in cat}
    out = {"events": {}}
    arrays = C.ARRAYS / "scene"
    arrays.mkdir(parents=True, exist_ok=True)
    nb_rows = {}
    for eid, sec, n in EVENTS:
        S = Dm.load_sector(sec)
        tc = EA["t0_btjd"] + n * EA["period_d"]
        ra, dec, x, y, yr = Sc.scene_positions(S, cat, tc)
        k_t = [c["source_id"] for c in cat].index(C.GAIA_TARGET)
        xt, yt = x[k_t], y[k_t]
        prf = P.prf_for_sector(S, (xt, yt))
        di = diffimg.difference_image(S, tc, EA["duration_d"])
        role = di["role"]
        ref = (role == W.ROLE_REF_L) | (role == W.ROLE_REF_R)
        img = np.median(S.flux[ref], axis=0)
        err = 1.4826 * np.median(np.abs(S.flux[ref] - img), axis=0) / np.sqrt(ref.sum())
        reg = Sc.fit_registration(S, img, err, cat, x, y, prf)
        # PRF-width mismatch scan (diagnostic only)
        wscan = {}
        for ws in (0.9, 0.95, 1.0, 1.05, 1.1, 1.2):
            r2 = Sc.fit_registration(S, img, err, cat, x, y, prf, width_scale=ws)
            wscan[str(ws)] = {"chi2": r2["chi2"], "dx": r2["dx"], "dy": r2["dy"]}
        # Gaussian alternative PRF: scan sigma
        gscan = {}
        best_g = None
        for sg in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1):
            r3 = Sc.fit_registration(S, img, err, cat, x, y, P.GaussPRF(sg))
            gscan[str(sg)] = {"chi2": r3["chi2"], "dx": r3["dx"], "dy": r3["dy"]}
            if best_g is None or r3["chi2"] < best_g[1]:
                best_g = (sg, r3["chi2"], r3)
        zp, zp_mad, nzp = Sc.zero_point(reg, by_id)
        sig_x = float(np.hypot(reg["dx_err_stat"], SIG_FLOOR))
        sig_y = float(np.hypot(reg["dy_err_stat"], SIG_FLOOR))
        # sources that matter: within 3.5 px of the target (after registration), plus the listed four
        xr, yr_ = x + reg["dx"], y + reg["dy"]
        dpx = np.hypot(xr - (xt + reg["dx"]), yr_ - (yt + reg["dy"]))
        sep = Sc.sep_arcsec(ra[k_t], dec[k_t], ra, dec)
        near = [i for i in range(len(cat)) if (dpx[i] <= 3.5 and i != k_t) or cat[i]["source_id"] in C.LISTED_NEIGHBOURS]
        f_target_fit = reg["flux_bright"].get(C.GAIA_TARGET)
        for i in near:
            c = cat[i]
            f_cat = 10 ** (-0.4 * (c["tmag"] - zp)) if np.isfinite(c["tmag"]) else np.nan
            rowd = nb_rows.setdefault(c["source_id"], {"gaia_dr3_source_id": c["source_id"], "tic_id": c["tic_id"],
                                                       "listed_in_prompt": c["source_id"] in C.LISTED_NEIGHBOURS,
                                                       "sep_arcsec": round(float(sep[i]), 2), "G": c["G"], "BP": c["BP"],
                                                       "RP": c["RP"], "tmag": c["tmag"], "tmag_source": c["tmag_src"],
                                                       "e_tmag_adopted": c["e_tmag"],
                                                       "tmag_gaia_relation": c["tmag_gaia_relation"],
                                                       "parallax_mas": c["parallax"], "pmra": c["pmra"], "pmdec": c["pmdec"],
                                                       "ruwe": c["ruwe"]})
            rowd[f"{eid}_x"] = round(float(xr[i]), 3); rowd[f"{eid}_y"] = round(float(yr_[i]), 3)
            rowd[f"{eid}_sep_px"] = round(float(dpx[i]), 3)
            rowd[f"{eid}_flux_e_s"] = float(f_cat)
        np.savez_compressed(arrays / f"scene_{eid}.npz", img=img, err=err, model=reg["model"], resid=reg["residual"],
                            x=x + reg["dx"], y=y + reg["dy"])
        out["events"][eid] = C.clean({
            "sector": sec, "camera": S.camera, "ccd": S.ccd, "epoch_jyear": yr, "tc": tc,
            "target_xy_wcs": [float(xt), float(yt)],
            "target_xy_registered": [float(xt + reg["dx"]), float(yt + reg["dy"])],
            "target_ccd_col_row": [float(S.col0 + xt), float(S.row0 + yt)],
            "prf_interp": prf.weights,
            "registration": {k: v for k, v in reg.items() if k not in ("residual", "model", "flux_bright", "bright_ids")},
            "registration_sigma_adopted_px": [sig_x, sig_y],
            "n_scene_stars_bright": reg["n_bright"], "n_scene_stars_faint": reg["n_faint"],
            "target_flux_fit_e_s": f_target_fit,
            "target_tmag": by_id[C.GAIA_TARGET]["tmag"],
            "zero_point": zp, "zero_point_mad": zp_mad, "zero_point_n": nzp,
            "target_flux_from_zp_e_s": 10 ** (-0.4 * (by_id[C.GAIA_TARGET]["tmag"] - zp)),
            "prf_width_scan": wscan, "gauss_sigma_scan": gscan, "gauss_best_sigma": best_g[0],
            "gauss_best_dx_dy": [best_g[2]["dx"], best_g[2]["dy"]],
            "residual_rms_central_9x9": float(np.std(reg["residual"][int(yt) - 4:int(yt) + 5, int(xt) - 4:int(xt) + 5])),
            "residual_at_target_3x3_sum": float(np.sum(reg["residual"][int(round(yt)) - 1:int(round(yt)) + 2,
                                                                       int(round(xt)) - 1:int(round(xt)) + 2])),
            "spoc_aperture_pixels": int(S.spoc["aperture_mask"].sum()),
        })
        print(eid, sec, "reg dx,dy=%.3f,%.3f +- %.3f,%.3f red=%.1f" % (reg["dx"], reg["dy"], reg["dx_err_stat"],
                                                                         reg["dy_err_stat"], reg["red_chi2"]),
              "ZP %.3f (mad %.3f, n %d)" % (zp, zp_mad, nzp), "fT_fit", f_target_fit,
              "fT_zp %.1f" % (10 ** (-0.4 * (by_id[C.GAIA_TARGET]["tmag"] - zp))), "gauss", best_g[0],
              {k: round(v["chi2"]) for k, v in wscan.items()})
    # bright contributors outside the cutout edges (within 600")
    S57 = Dm.load_sector(57)
    ra, dec, x, y, _ = Sc.scene_positions(S57, cat, 2869.87)
    outside = []
    for i, c in enumerate(cat):
        if not np.isfinite(c["tmag"]) or c["tmag"] > 13.0:
            continue
        ins = (-0.5 <= x[i] <= 20.5) and (-0.5 <= y[i] <= 20.5)
        outside.append({"source_id": c["source_id"], "tmag": c["tmag"], "G": c["G"], "x_s57": float(x[i]), "y_s57": float(y[i]),
                        "inside_cutout_s57": bool(ins),
                        "sep_from_target_arcsec": float(Sc.sep_arcsec(cat[[q["source_id"] for q in cat].index(C.GAIA_TARGET)]["ra"],
                                                                      cat[[q["source_id"] for q in cat].index(C.GAIA_TARGET)]["dec"],
                                                                      c["ra"], c["dec"]))})
    out["bright_T_le_13_within_600arcsec"] = outside
    out["n_gaia_600"] = len(cat)
    C.write_json(C.RESULTS / "scene.json", C.clean(out))
    keys = []
    for r in nb_rows.values():
        for k in r:
            if k not in keys:
                keys.append(k)
    rows = sorted(nb_rows.values(), key=lambda r: r["sep_arcsec"])
    with open(C.WS / "neighbours.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=keys)
        wr.writeheader()
        for r in rows:
            wr.writerow(r)
    for r in rows:
        print(r["gaia_dr3_source_id"], r["sep_arcsec"], "T=%.2f (%s)" % (r["tmag"], r["tmag_source"]), "G=%.2f" % r["G"],
              {k: r.get(k) for k in ("E00_sep_px", "E00_flux_e_s", "E32_flux_e_s", "E33_flux_e_s")})
    print("bright outside/inside", [(o["source_id"], round(o["tmag"], 2), o["inside_cutout_s57"], round(o["sep_from_target_arcsec"]))
                                    for o in outside])


if __name__ == "__main__":
    main()
