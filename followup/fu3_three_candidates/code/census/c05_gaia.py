"""Census task 7: Gaia DR3 (ESA Gaia archive).

The ESA TAP sync endpoint (https://gea.esac.esa.int/tap-server/tap/sync, the service that
astroquery.gaia's Gaia.launch_job uses for synchronous jobs) is called directly with `requests`, so that every
response body passes through the receipt hook (astroquery.gaia's TapPlus uses http.client, which the hook
cannot see).  Read timeout 120 s; a timeout is recorded as ACCESS_FAILED.  Epoch photometry via the Gaia
DataLink data-server (RETRIEVAL_TYPE=EPOCH_PHOTOMETRY), saved but not interpreted.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import census_common as C
from census_common import TARGETS, fetch, log, save_json

SCRIPT = "c05_gaia"
TAP = "https://gea.esac.esa.int/tap-server/tap/sync"
DATALINK = "https://gea.esac.esa.int/data-server/data"
EPOCH_DIR = C.OUT / "gaia_epoch_photometry"


def tap(query, label):
    f = fetch(TAP, label, method="POST", data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv",
                                                "QUERY": query}, timeout=(30, 120), retries=1)
    rows, err = None, None
    if f.ok:
        txt = f.text
        bad = C.looks_like_error_page(txt[:2000]) if txt.lstrip().startswith("<") else None
        if bad:
            err = f"HTTP 200 but non-CSV body ({bad})"
        else:
            rows = list(csv.DictReader(io.StringIO(txt)))
    else:
        err = f"{f.describe()}; body head: {(f.text or '')[:500]!r}" if f.resp is not None else f"exception: {f.exc}"
    return {"query": query, "status": f.status, "error": err, "n_rows": None if rows is None else len(rows),
            "rows": rows, "receipts": f.receipt_files, "raw": f.raw_files}


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "data_release": "Gaia DR3 (ESA archive gaiadr3 schema)",
           "queries": {}, "per_target": {}}
    ids = [TARGETS[t]["gaia"] for t in TARGETS]
    idlist = ",".join(str(i) for i in ids)
    q = tap(f"SELECT * FROM gaiadr3.gaia_source WHERE source_id IN ({idlist})", "gaia_source_targets")
    res["queries"]["gaia_source_targets"] = q
    log(SCRIPT, f"gaia_source targets: n={q['n_rows']} err={q['error']}")
    src = {int(r["source_id"]): r for r in (q["rows"] or [])}
    q = tap(f"SELECT * FROM gaiadr3.astrophysical_parameters WHERE source_id IN ({idlist})", "gaia_ap_targets")
    res["queries"]["astrophysical_parameters_targets"] = q
    log(SCRIPT, f"astrophysical_parameters: n={q['n_rows']} err={q['error']}")
    # ---- cones of 90 arcsec around each target (epoch 2016.0) ----
    cone_ids = set()
    for tic, t in TARGETS.items():
        g = src.get(t["gaia"])
        if g:
            ra0, dec0, cen = float(g["ra"]), float(g["dec"]), "Gaia DR3 position of the target (epoch 2016.0)"
        else:
            ra0, dec0 = C.pos_at_epoch(tic, 2016.0)
            cen = "TIC epoch-2000 position propagated to 2016.0 (target row unavailable)"
        cols = ("source_id, ra, dec, parallax, parallax_error, pmra, pmdec, phot_g_mean_mag, phot_bp_mean_mag, "
                "phot_rp_mean_mag, bp_rp, ruwe, ipd_frac_multi_peak, ipd_frac_odd_win, ipd_gof_harmonic_amplitude, "
                "visibility_periods_used, astrometric_params_solved, phot_variable_flag, has_epoch_photometry, "
                "has_xp_continuous, has_rvs, radial_velocity, non_single_star, duplicated_source, "
                "phot_bp_rp_excess_factor")
        qq = (f"SELECT {cols}, DISTANCE(POINT('ICRS', ra, dec), POINT('ICRS', {ra0:.9f}, {dec0:.9f}))*3600.0 "
              f"AS sep_arcsec FROM gaiadr3.gaia_source WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), "
              f"CIRCLE('ICRS', {ra0:.9f}, {dec0:.9f}, {90.0 / 3600.0:.10f})) ORDER BY sep_arcsec")
        q = tap(qq, f"gaia_cone90_{tic}")
        q["center"] = {"ra": ra0, "dec": dec0, "what": cen}
        res["queries"][f"cone90_{tic}"] = q
        for r in (q["rows"] or []):
            cone_ids.add(int(r["source_id"]))
        # TIC epoch-2000 position propagated to 2016.0 versus the DR3 position
        pra, pdec = C.pos_at_epoch(tic, 2016.0)
        res["per_target"][tic] = {
            "gaia_source": g, "cone_center": q["center"],
            "tic2000_propagated_to_2016_minus_dr3_mas": (None if not g else
                                                         round(C.sep_arcsec(pra, pdec, ra0, dec0) * 1000, 2)),
            "n_cone90": q["n_rows"], "cone_error": q["error"]}
        log(SCRIPT, f"cone90 {tic}: n={q['n_rows']} err={q['error']}")
    allids = ",".join(str(i) for i in sorted(cone_ids | set(ids)))
    for tab in ("vari_summary", "vari_classifier_result", "vari_eclipsing_binary", "vari_planetary_transit",
                "vari_rotation_modulation", "nss_two_body_orbit", "nss_acceleration_astro",
                "nss_non_linear_spectro", "nss_vim_fl"):
        q = tap(f"SELECT * FROM gaiadr3.{tab} WHERE source_id IN ({allids})", f"gaia_{tab}")
        res["queries"][tab] = q
        log(SCRIPT, f"{tab}: n={q['n_rows']} err={q['error']}")
    # ---- epoch photometry for target / neighbours within 60 arcsec flagged has_epoch_photometry ----
    want = []
    for tic in TARGETS:
        for r in (res["queries"][f"cone90_{tic}"]["rows"] or []):
            if float(r["sep_arcsec"]) <= 60.0 and str(r["has_epoch_photometry"]).strip().lower() in ("true", "1", "t"):
                want.append((tic, int(r["source_id"]), float(r["sep_arcsec"])))
    res["epoch_photometry_requested"] = want
    res["epoch_photometry"] = []
    if want:
        EPOCH_DIR.mkdir(parents=True, exist_ok=True)
    for tic, sid, sep in want:
        f = fetch(DATALINK, f"gaia_epochphot_{sid}",
                  params={"RETRIEVAL_TYPE": "EPOCH_PHOTOMETRY", "ID": str(sid), "FORMAT": "csv",
                          "RELEASE": "Gaia DR3", "DATA_STRUCTURE": "INDIVIDUAL", "VALID_DATA": "false",
                          "USE_ZIP_ALWAYS": "true"}, timeout=(30, 120))
        rec = {"tic": tic, "source_id": sid, "sep_arcsec": sep, "status": f.status, "describe": f.describe(),
               "receipts": f.receipt_files, "raw": f.raw_files, "files": []}
        if f.ok:
            try:
                z = zipfile.ZipFile(io.BytesIO(f.resp.content))
                outdir = EPOCH_DIR / f"tic{tic}_gaia{sid}"
                outdir.mkdir(parents=True, exist_ok=True)
                for n in z.namelist():
                    data = z.read(n)
                    p = outdir / Path(n).name
                    C._check_write(p)
                    p.write_bytes(data)
                    nrows = max(0, data.decode("utf-8", "replace").count("\n") - 1)
                    rec["files"].append({"name": n, "saved": str(p), "bytes": len(data),
                                         "sha256": C.sha256_bytes(data), "approx_lines": nrows})
            except zipfile.BadZipFile:
                rec["error"] = f"not a zip; body head {(f.text or '')[:300]!r}"
        res["epoch_photometry"].append(rec)
        log(SCRIPT, f"epoch phot {sid} (TIC {tic}, {sep:.1f}\"): {f.describe()} files={len(rec['files'])}")
    # strip the very large row lists of the vari/nss tables into tables/ for readability
    save_json(C.TABLES / "gaia_dr3_census.json", res)
    save_json(C.PARTS / "c05_gaia.json", {k: v for k, v in res.items() if k != "queries"} |
              {"queries_summary": {k: {"status": v["status"], "n_rows": v["n_rows"], "error": v["error"],
                                       "receipts": v["receipts"]} for k, v in res["queries"].items()}})


if __name__ == "__main__":
    main()
