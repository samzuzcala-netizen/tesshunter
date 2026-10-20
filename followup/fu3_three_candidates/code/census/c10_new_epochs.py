"""Census task 3: new epochs (sectors / products not used by the discovery search) and a coverage prediction.

Inputs (all produced by this census): tables/mast_tess_<tic>.json (c01), parts/c01c_sector_context.json (WTV and
latest-sector counts) and the raw MAST cone responses (for the FFI footprint polygons, s_region).

For every sector in which any product family or TESScut lists the target and which is not in the discovery
'used' list, and for every product family present in a used sector but not used by discovery, it records the
camera/CCD (TESScut, FFI obs_id, WTV), product families, t_min/t_max (MAST, MJD -> BTJD = MJD - 56999.5;
approximate) and the predicted events:
  primary: tc_n = T0 + n P with tc_n in [t_min - 0.25 d, t_max + 0.25 d]; flagged 'edge' if within 0.25 d of
           t_min/t_max; parity (n mod 2) labels the 2P-alias odd/even split;
  phase-0.5: T0 + (n + 0.5) P in the same window (secondary eclipse at phase 0.5, or the extra events of a P/2
           alias).
COVERAGE METHOD: prediction from sector start/end only; data gaps (orbit gaps, downlinks, flagged cadences)
are unknown here, so an event inside [t_min, t_max] is not guaranteed to have data.
Footprint geometry: signed great-circle distance of the target (position at the sector mid-epoch) to the edges
of each FFI-level footprint polygon returned by the MAST cone (positive = inside), in arcsec and TESS pixels.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

import census_common as C
from census_common import TARGETS, log, save_json

SCRIPT = "c10_new_epochs"
ALLOW = 0.25
PIX = 21.0


def unit(ra, dec):
    r, d = math.radians(ra), math.radians(dec)
    return np.array([math.cos(d) * math.cos(r), math.cos(d) * math.sin(r), math.sin(d)])


def parse_polygon(s):
    if not s or "POLYGON" not in s.upper():
        return None
    nums = [float(x) for x in re.findall(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?", s.split("POLYGON", 1)[1])]
    pts = list(zip(nums[0::2], nums[1::2]))
    if len(pts) >= 2 and abs(pts[0][0] - pts[-1][0]) < 1e-9 and abs(pts[0][1] - pts[-1][1]) < 1e-9:
        pts = pts[:-1]
    return pts if len(pts) >= 3 else None


def signed_edge_distance(poly, ra, dec):
    """min signed angular distance (arcsec) from the point to the polygon's great-circle edges; + inside."""
    V = [unit(a, b) for a, b in poly]
    cen = sum(V)
    cen = cen / np.linalg.norm(cen)
    p = unit(ra, dec)
    dists, inside = [], True
    for i in range(len(V)):
        n = np.cross(V[i], V[(i + 1) % len(V)])
        n = n / np.linalg.norm(n)
        s_c = np.sign(np.dot(n, cen))
        dp = np.dot(n, p) * s_c        # > 0 on the polygon side of this edge
        if dp < 0:
            inside = False
        dists.append(math.degrees(math.asin(max(-1.0, min(1.0, dp)))) * 3600.0)
    return round(min(dists), 1), inside


def btjd_to_year(btjd):
    return 2000.0 + (btjd + 2457000.0 - 2451545.0) / 365.25


def events(t, tmin, tmax):
    P, T0 = t["P"], t["T0"]
    out_p, out_s = [], []
    for kind, off, out in (("primary", 0.0, out_p), ("phase0.5", 0.5, out_s)):
        n0 = math.ceil((tmin - ALLOW - T0) / P - off)
        n1 = math.floor((tmax + ALLOW - T0) / P - off)
        for n in range(n0, n1 + 1):
            tc = T0 + (n + off) * P
            edge = (tc < tmin + ALLOW) or (tc > tmax - ALLOW)
            e = {"n": n, "tc_btjd": round(tc, 5), "within_sector_span": tmin <= tc <= tmax,
                 "edge_flag_within_0.25d": edge}
            if kind == "primary":
                e["parity_n_mod_2"] = "even" if n % 2 == 0 else "odd"
            sig = t.get("_sig")
            if sig:
                e["sigma_tc_d_packet_fit"] = round(math.sqrt(sig[0] ** 2 + ((n + off) * sig[1]) ** 2), 5)
            out.append(e)
    return out_p, out_s


def load_polygons(tic):
    d = json.loads((C.TABLES / f"mast_tess_{tic}.json").read_text(encoding="utf-8"))
    polys = {}
    for rp in d["queries"]["cone15"]["receipts"]:
        rec = json.loads(Path(rp).read_text(encoding="utf-8"))
        raw = rec.get("raw_file")
        if not raw:
            continue
        try:
            j = json.loads(Path(raw).read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in j.get("data") or []:
            if row.get("obs_id") and row.get("s_region"):
                polys[row["obs_id"]] = row["s_region"]
    return d, polys


def main():
    ctx = json.loads((C.PARTS / "c01c_sector_context.json").read_text(encoding="utf-8"))
    prov = {270573718: json.loads((C.ROOT / "results" / "s00_provenance_270573718.json").read_text(encoding="utf-8")),
            262843927: json.loads((C.ROOT / "results" / "s00_provenance_262843927.json").read_text(encoding="utf-8")),
            193718989: json.loads((C.ROOT / "results" / "s00_provenance_193718989.json").read_text(encoding="utf-8"))}
    out = {"script": SCRIPT, "utc": C.utc(),
           "method": ("Coverage prediction from MAST sector start/end only (t_min/t_max, approximate); orbit gaps, "
                      "downlinks and flagged cadences unknown; +/-0.25 d timing allowance; phase-0.5 events and "
                      "n-parity (2P-alias odd/even) listed. Ephemerides: user-supplied P, T0 (BTJD). 1-sigma tc "
                      "from the discovery packet fit_adopted t0_err/period_err where available (no covariance; "
                      "informational only)."),
           "latest_sectors_at_MAST": {k: v["counts_per_sector"] for k, v in ctx["mast_counts"].items()},
           "targets": {}}
    for tic, t in TARGETS.items():
        fa = prov[tic]["ephemerides"]["fit_adopted"]
        t = dict(t)
        t["_sig"] = (fa["t0_err"], fa["period_err"]) if fa.get("t0_err") and fa.get("period_err") else None
        d, polys = load_polygons(tic)
        used = set(C.used_sectors(tic))
        used_by_family = {k: set(v) for k, v in TARGETS[tic]["used"].items()}
        tess_cut = {int(r["sector"]): (int(r["camera"]), int(r["ccd"])) for r in d["tesscut"]["SPOC"]["rows"] or []}
        wtv_rows = (ctx["wtv"][str(tic)]["tables"] or [[]])[0][1:]
        wtv = {int(r[4]): {"camera": int(r[5]), "ccd": int(r[6]), "col": float(r[7]), "row": float(r[8]),
                           "midpoint": r[9]} for r in wtv_rows}
        by_sector = {}
        for r in d["observations"]:
            s = r.get("sector")
            if s is None:
                continue
            b = by_sector.setdefault(s, {"families": {}, "ffi": []})
            if r["ffi_level"] or r["provenance_name"] == "ELEANOR":
                if r["ffi_level"]:
                    ra_, dec_ = C.pos_at_epoch(tic, btjd_to_year(0.5 * (r["t_min_btjd"] + r["t_max_btjd"])))
                    poly = parse_polygon(polys.get(r["obs_id"]))
                    geo = signed_edge_distance(poly, ra_, dec_) if poly else (None, None)
                    b["ffi"].append({"provenance": r["provenance_name"], "obs_id": r["obs_id"],
                                     "camera_ccd_from_obs_id": [r["camera_from_obs_id"], r["ccd_from_obs_id"]],
                                     "t_min_btjd": r["t_min_btjd"], "t_max_btjd": r["t_max_btjd"],
                                     "footprint_signed_edge_distance_arcsec": geo[0],
                                     "footprint_signed_edge_distance_px": None if geo[0] is None else round(geo[0] / PIX, 1),
                                     "inside_footprint": geo[1]})
                continue
            fam = f"{r['obs_collection']}/{r['provenance_name']}"
            b["families"].setdefault(fam, []).append({"obs_id": r["obs_id"], "t_exptime": r["t_exptime"],
                                                      "dataproduct_type": r["dataproduct_type"],
                                                      "t_min_btjd": r["t_min_btjd"], "t_max_btjd": r["t_max_btjd"]})
        # SPOC footprints fetched by obs_id (c01d) for sectors where the cone returned only a TICA footprint
        p01d = C.PARTS / "c01d_s97_footprint.json"
        if tic == 270573718 and p01d.exists():
            for r in json.loads(p01d.read_text(encoding="utf-8"))["rows"]:
                s = int(r["sequence_number"])
                t0b, t1b = r["t_min"] + C.MJD_TO_BTJD, r["t_max"] + C.MJD_TO_BTJD
                ra_, dec_ = C.pos_at_epoch(tic, btjd_to_year(0.5 * (t0b + t1b)))
                poly = parse_polygon(r["s_region"])
                geo = signed_edge_distance(poly, ra_, dec_) if poly else (None, None)
                by_sector.setdefault(s, {"families": {}, "ffi": []})["ffi"].append(
                    {"provenance": "SPOC (fetched by obs_id; not returned by the 15\" cone)", "obs_id": r["obs_id"],
                     "camera_ccd_from_obs_id": [4, 1], "t_min_btjd": round(t0b, 5), "t_max_btjd": round(t1b, 5),
                     "footprint_signed_edge_distance_arcsec": geo[0],
                     "footprint_signed_edge_distance_px": None if geo[0] is None else round(geo[0] / PIX, 1),
                     "inside_footprint": geo[1]})
        all_sectors = sorted(set(by_sector) | set(tess_cut))
        new_entries, unused_products = [], []
        for s in all_sectors:
            b = by_sector.get(s, {"families": {}, "ffi": []})
            spans = [(x["t_min_btjd"], x["t_max_btjd"]) for v in b["families"].values() for x in v] + \
                    [(x["t_min_btjd"], x["t_max_btjd"]) for x in b["ffi"] if x["provenance"] == "SPOC"]
            if not spans:
                spans = [(x["t_min_btjd"], x["t_max_btjd"]) for x in b["ffi"]]
            tmin = min(a for a, _ in spans) if spans else None
            tmax = max(z for _, z in spans) if spans else None
            entry = {"sector": s, "in_discovery_used_list": s in used,
                     "tesscut_spoc": {"listed": s in tess_cut, "camera_ccd": tess_cut.get(s)},
                     "wtv_tess_point": wtv.get(s), "target_level_families": sorted(b["families"].keys()),
                     "ffi_level_footprints": b["ffi"], "t_min_btjd": tmin, "t_max_btjd": tmax,
                     "t_span_source": "MAST observation t_min/t_max (union over listed products), approximate"}
            if tmin is not None:
                pe, se = events(t, tmin, tmax)
                entry["predicted_primary_events"] = pe
                entry["predicted_phase0.5_events"] = se
            else:
                entry["predicted_primary_events"] = None
                entry["predicted_phase0.5_events"] = None
                entry["note"] = "no MAST time range available"
            if s not in used:
                entry["status"] = "NEW_SECTOR_NOT_USED_BY_DISCOVERY"
                spoc_in = [f["inside_footprint"] for f in b["ffi"] if str(f["provenance"]).startswith("SPOC")]
                entry["on_silicon_assessment"] = {
                    "tesscut_lists_sector": s in tess_cut,
                    "wtv_tess_point_lists_sector": s in wtv,
                    "spoc_ffi_4corner_footprint_contains_target": spoc_in or None,
                    "target_level_pipeline_products": sorted(b["families"].keys()),
                    "note": ("4-corner footprint polygons ignore the camera distortion, so containment by tens of "
                             "pixels is not decisive; tess-point (WTV) states ~1 px accuracy. Status is reported, "
                             "not resolved, by this metadata-only census."),
                }
                new_entries.append(entry)
            else:
                used_fams = {f"HLSP/{k}" for k, v in used_by_family.items() if s in v}
                extra = [f for f in b["families"] if f not in used_fams]
                if extra:
                    e2 = {k: entry[k] for k in ("sector", "tesscut_spoc", "wtv_tess_point", "t_min_btjd",
                                                "t_max_btjd", "predicted_primary_events", "predicted_phase0.5_events")}
                    e2["discovery_used_family"] = sorted(used_fams)
                    e2["unused_families_same_sector"] = {f: b["families"][f] for f in extra}
                    e2["status"] = "USED_SECTOR_OTHER_PRODUCTS (same photons; D-alt, not new epochs)"
                    unused_products.append(e2)
        future = [{"sector": s, **v} for s, v in sorted(wtv.items()) if s not in by_sector and s not in tess_cut]
        out["targets"][tic] = {
            "ephemeris": {"P": t["P"], "T0_btjd": t["T0"], "T14_h": t["T14_h"],
                          "packet_fit_sigma_T0_P": t["_sig"]},
            "used_sectors": sorted(used),
            "sectors_gt_98_with_any_data": [e["sector"] for e in new_entries + unused_products if e["sector"] > 98],
            "new_sectors": new_entries,
            "unused_products_in_used_sectors": unused_products,
            "predicted_future_sectors_no_data_yet (WTV/tess-point)": future,
        }
        log(SCRIPT, f"TIC {tic}: new sectors {[e['sector'] for e in new_entries]}; used-sector extra products in "
                    f"{[e['sector'] for e in unused_products]}; future {[f['sector'] for f in future]}")
    save_json(C.OUT / "new_epochs.json", out)


if __name__ == "__main__":
    main()
