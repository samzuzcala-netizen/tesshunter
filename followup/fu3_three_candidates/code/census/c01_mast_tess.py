"""Census task 1 + 2: MAST TESS/HLSP observations and product lists, TESScut sector availability.

Metadata only.  No light curve, TPF or cutout is downloaded.  Sequential requests; astroquery cache disabled
so that every query reaches the network and receives a receipt (census_common hook).
"""
from __future__ import annotations

import json
import re
import sys
import traceback

import census_common as C
from census_common import TARGETS, entry, log, save_json, tag

import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astroquery import cache_conf

cache_conf.cache_active = False
from astroquery.mast import Observations, Tesscut  # noqa: E402
from astroquery.mast import conf as mast_conf  # noqa: E402

mast_conf.timeout = 120
SCRIPT = "c01_mast_tess"
OBS_COLS = ["obs_collection", "provenance_name", "target_name", "sequence_number", "t_exptime",
            "dataproduct_type", "obs_id", "obsid", "t_min", "t_max", "dataRights", "s_ra", "s_dec",
            "instrument_name", "project", "calib_level", "t_obs_release", "proposal_id", "filters",
            "intentType", "obs_title"]
PROD_COLS = ["obsID", "parent_obsid", "obs_collection", "obs_id", "productFilename", "size", "productType",
             "productSubGroupDescription", "description", "dataRights", "prvversion", "calib_level",
             "project", "dataURI", "type", "proposal_id"]


def val(x):
    if x is None or x is np.ma.masked:
        return None
    if isinstance(x, (np.floating, float)):
        x = float(x)
        return None if not np.isfinite(x) else x
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, bytes):
        return x.decode()
    return x if not hasattr(x, "item") else x.item()


def rows(tbl, cols):
    out = []
    if tbl is None:
        return out
    have = [c for c in cols if c in tbl.colnames]
    for r in tbl:
        out.append({c: val(r[c]) for c in have})
    return out


def parse_sector(obs_id: str, seq):
    if seq is not None:
        try:
            s = int(seq)
            if 0 < s < 1000:
                return s
        except Exception:
            pass
    if not obs_id:
        return None
    for pat in (r"-s0*(\d{1,3})-", r"_s0*(\d{1,3})[-_]", r"-s0*(\d{1,3})$", r"s0*(\d{1,3})-", r"sector0*(\d{1,3})"):
        m = re.search(pat, obs_id)
        if m:
            return int(m.group(1))
    return None


def parse_multisector(obs_id: str):
    m = re.search(r"-s0*(\d{1,3})-s0*(\d{1,3})-", obs_id or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_cam_ccd(obs_id: str):
    for pat in (r"tess-s\d{4}-(\d)-(\d)", r"cam(\d)-ccd(\d)", r"-(\d)-(\d)(?:_|$)"):
        m = re.search(pat, obs_id or "")
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def is_ffi_level(row) -> bool:
    tn = str(row.get("target_name") or "").upper()
    return "FFI" in tn


def main():
    summary = {"script": SCRIPT, "utc": C.utc(), "astroquery_mast_timeout": mast_conf.timeout, "targets": {}}
    entries = []
    for tic, t in TARGETS.items():
        log(SCRIPT, f"TIC {tic}: MAST queries")
        coord = SkyCoord(t["ra"], t["dec"], unit="deg")
        res = {"tic": tic, "queries": {}}
        # ---- 1a: target_name query ----
        q1 = None
        with tag(f"mast_obs_target_{tic}") as rc1:
            try:
                q1 = Observations.query_criteria(target_name=str(tic), obs_collection=["TESS", "HLSP"])
                err1 = None
            except Exception as e:  # noqa: BLE001
                err1 = f"{type(e).__name__}: {e}"
        res["queries"]["target_name"] = {"n": None if q1 is None else len(q1), "error": err1,
                                         "receipts": [r["receipt"] for r in rc1]}
        # ---- 1b: 15 arcsec cone restricted to TESS/HLSP ----
        q2 = None
        with tag(f"mast_obs_cone15_{tic}") as rc2:
            try:
                q2 = Observations.query_criteria(coordinates=coord, radius=15 * u.arcsec,
                                                 obs_collection=["TESS", "HLSP"])
                err2 = None
            except Exception as e:  # noqa: BLE001
                err2 = f"{type(e).__name__}: {e}"
        res["queries"]["cone15"] = {"n": None if q2 is None else len(q2), "error": err2,
                                    "receipts": [r["receipt"] for r in rc2]}
        # ---- merge ----
        merged = {}
        for src, tbl in (("target_name", q1), ("cone15", q2)):
            for r in rows(tbl, OBS_COLS):
                key = str(r.get("obsid"))
                if key in merged:
                    merged[key]["found_by"].append(src)
                else:
                    r["found_by"] = [src]
                    merged[key] = r
        obs = list(merged.values())
        for r in obs:
            r["sector"] = parse_sector(r.get("obs_id"), r.get("sequence_number"))
            ms = parse_multisector(r.get("obs_id"))
            r["multisector_range"] = list(ms) if ms else None
            cam, ccd = parse_cam_ccd(r.get("obs_id"))
            r["camera_from_obs_id"], r["ccd_from_obs_id"] = cam, ccd
            r["ffi_level"] = is_ffi_level(r)
            if r.get("s_ra") is not None and r.get("s_dec") is not None:
                r["sep_arcsec_from_TIC2000"] = round(C.sep_arcsec(t["ra"], t["dec"], r["s_ra"], r["s_dec"]), 3)
            for k in ("t_min", "t_max"):
                r[k + "_btjd"] = None if r.get(k) is None else round(r[k] + C.MJD_TO_BTJD, 5)
        obs.sort(key=lambda r: (r.get("sector") or 0, str(r.get("provenance_name")), str(r.get("obs_id"))))
        # ---- 1c: product lists for target-level observations (never for FFI-level observations) ----
        prod_rows, prod_err, prod_receipts = [], [], []
        tl = [r for r in obs if not r["ffi_level"]]
        ids = [str(r["obsid"]) for r in tl]
        for i in range(0, len(ids), 25):
            chunk = ids[i:i + 25]
            with tag(f"mast_products_{tic}_{i // 25:02d}") as rc3:
                try:
                    pl = Observations.get_product_list(chunk)
                    prod_rows.extend(rows(pl, PROD_COLS))
                except Exception as e:  # noqa: BLE001
                    prod_err.append(f"chunk {i // 25}: {type(e).__name__}: {e}")
            prod_receipts += [r["receipt"] for r in rc3]
        res["queries"]["product_lists"] = {"n_obs_listed": len(ids), "n_products": len(prod_rows),
                                           "errors": prod_err, "receipts": prod_receipts}
        # ---- 2: TESScut sectors (SPOC FFIs default; TICA as a secondary product family) ----
        tc = {}
        for product in ("SPOC", "TICA"):
            with tag(f"tesscut_sectors_{product}_{tic}") as rc4:
                try:
                    st = Tesscut.get_sectors(coordinates=coord, product=product)
                    tc[product] = {"rows": rows(st, list(st.colnames)), "error": None}
                except Exception as e:  # noqa: BLE001
                    tc[product] = {"rows": None, "error": f"{type(e).__name__}: {e}"}
            tc[product]["receipts"] = [r["receipt"] for r in rc4]
            tc[product]["raw"] = [r["raw"] for r in rc4 if r.get("raw")]
        res["tesscut"] = tc
        res["observations"] = obs
        res["products"] = prod_rows
        save_json(C.TABLES / f"mast_tess_{tic}.json", res)
        # flat CSVs for convenience
        try:
            import pandas as pd
            pd.DataFrame(obs).to_csv(C.TABLES / f"mast_obs_{tic}.csv", index=False)
            pd.DataFrame(prod_rows).to_csv(C.TABLES / f"mast_products_{tic}.csv", index=False)
            for product in tc:
                if tc[product]["rows"]:
                    pd.DataFrame(tc[product]["rows"]).to_csv(C.TABLES / f"tesscut_{product}_{tic}.csv", index=False)
        except Exception:
            traceback.print_exc()
        summary["targets"][tic] = {"n_obs": len(obs), "n_products": len(prod_rows),
                                   "q_errors": [err1, err2] + prod_err,
                                   "tesscut": {p: (None if v["rows"] is None else len(v["rows"])) for p, v in tc.items()}}
        log(SCRIPT, f"TIC {tic}: {len(obs)} observations, {len(prod_rows)} products, "
                    f"tesscut SPOC={summary['targets'][tic]['tesscut'].get('SPOC')} "
                    f"TICA={summary['targets'][tic]['tesscut'].get('TICA')} errors={[e for e in [err1, err2] + prod_err if e]}")
    save_json(C.PARTS / "c01_summary.json", summary)


if __name__ == "__main__":
    main()
