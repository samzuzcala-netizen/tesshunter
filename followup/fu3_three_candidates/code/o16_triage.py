"""Quick triage of the 16 S1 batch-1 SUBMIT/HOLD candidates that have had no targeted follow-up (user request,
2026-10-19).  Read-only on the survey; no light-curve re-analysis.  Per star:
  * the batch-1 review's ranking and assessment (Codex 'look-at-the-results-of-batch'),
  * the packet's adopted fit, TRICERATOPS FPP/NFPP and Stage D verdict,
  * TOI / CTOI status (ExoFOP tables saved by the deep analysis, 2026-10-18),
  * Gaia DR3 at the TIC position (3-arcsec cone): RUWE, excess-noise significance, NSS flag, and whether the packet's
    neighbours.json 'target' is that source (TIC Gaia IDs read through a float column lose precision),
  * TESS data after sector 98 (MAST observations + TESScut) and the number of predicted transits inside them, with
    the ephemeris uncertainty propagated to that epoch.
Outputs: results/other16_triage.json, tables/other16_triage.csv
"""
import csv
import math

import pandas as pd
import requests

from fu3_common import *

SEVEN = {116046773, 188830138, 193718989, 201247574, 262843927, 270573718, 382098683}
RANK = read(REVIEW / "batch1_rankings.json")
OTHERS = sorted((r for r in RANK if r["tic_id"] not in SEVEN), key=lambda r: r["planet_rank"])
PK = S1 / "packets" / "s1_b1"
TAP = "https://gea.esac.esa.int/tap-server/tap/sync"
CAT = DEEP / "analysis" / "catalogs"


def gaia_cone(ra, dec, r_arcsec=3.0):
    q = (f"SELECT source_id, phot_g_mean_mag, bp_rp, parallax, parallax_error, ruwe, astrometric_excess_noise_sig, "
         f"non_single_star, ipd_frac_multi_peak, DISTANCE(POINT('ICRS', ra, dec), POINT('ICRS', {ra}, {dec})) * 3600 AS sep "
         f"FROM gaiadr3.gaia_source WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra}, {dec}, {r_arcsec / 3600}))")
    r = requests.post(TAP, data=dict(REQUEST="doQuery", LANG="ADQL", FORMAT="json", QUERY=q), timeout=120)
    r.raise_for_status()
    j = r.json()
    cols = [c["name"] for c in j["metadata"]]
    return sorted((dict(zip(cols, row)) for row in j["data"]), key=lambda x: x["sep"])


def new_sectors(ra, dec):
    from astropy.coordinates import SkyCoord
    from astroquery.mast import Observations, Tesscut
    c = SkyCoord(ra, dec, unit="deg")
    out = {}
    try:
        for s in Tesscut.get_sectors(coordinates=c)["sector"]:
            if 98 < int(s) <= 130:
                out.setdefault(int(s), dict(products=set(), tmin=None, tmax=None))["products"].add("TESScut FFI")
    except Exception as exc:   # noqa: BLE001
        out["tesscut_error"] = repr(exc)[:200]
    try:
        obs = Observations.query_region(c, radius="0.0006 deg")
        obs = obs[[str(x) in ("TESS", "HLSP") for x in obs["obs_collection"]]]
        for o in obs:
            try:
                s = int(o["sequence_number"])
            except (TypeError, ValueError):
                continue
            if not 98 < s <= 130 or (o["obs_collection"] == "HLSP" and str(o["project"]).upper() not in ("TESS-SPOC", "QLP", "TICA", "TGLC")
                           and "TESS" not in str(o["provenance_name"]).upper()):
                continue
            e = out.setdefault(s, dict(products=set(), tmin=None, tmax=None))
            e["products"].add(f"{o['obs_collection']}:{o['provenance_name']}")
            tmin, tmax = float(o["t_min"]) - 56999.5, float(o["t_max"]) - 56999.5
            e["tmin"] = tmin if e["tmin"] is None else min(e["tmin"], tmin)
            e["tmax"] = tmax if e["tmax"] is None else max(e["tmax"], tmax)
    except Exception as exc:   # noqa: BLE001
        out["mast_error"] = repr(exc)[:200]
    return out


def main():
    tg = pd.read_csv(REPO / "s1" / "survey" / "targets_s1.csv", low_memory=False, dtype={"GAIA": str})
    toi = pd.read_csv(CAT / "toi.csv", comment="#", low_memory=False)
    ctoi = pd.read_csv(CAT / "ctoi.csv", comment="#", low_memory=False)
    res = []
    for r in OTHERS:
        tic = r["tic_id"]
        row = tg[tg.tic_id == tic].iloc[0]
        pdir = next(PK.glob(f"tic{tic}_P*"))
        fit = read(pdir / "fit.json")["adopted"]
        ex = read(pdir / "expensive.json")
        sd = read(pdir / "stageD.json")
        nb = read(pdir / "neighbours.json")
        fpp = ex.get("fpp") or {}
        dt = 16.0                      # TIC J2000 coordinates -> Gaia DR3 epoch 2016.0
        pmra = float(row.pmRA) if pd.notna(row.pmRA) else 0.0
        pmde = float(row.pmDEC) if pd.notna(row.pmDEC) else 0.0
        ra16 = float(row.ra) + pmra * dt / 3.6e6 / math.cos(math.radians(float(row.dec)))
        de16 = float(row.dec) + pmde * dt / 3.6e6
        g = gaia_cone(ra16, de16)
        g0 = g[0] if g else {}
        nb_t = (nb.get("gaia") or {}).get("target") or {}
        P, T0 = fit["period"], fit["t0_btjd"]
        sP = fit.get("period_err")
        sT = fit.get("t0_err")
        ns = new_sectors(float(row.ra), float(row.dec))
        new = []
        for s, e in sorted((k, v) for k, v in ns.items() if isinstance(k, int)):
            n_ev, sig_h = None, None
            if e["tmin"] is not None:
                n0, n1 = math.ceil((e["tmin"] - T0) / P), math.floor((e["tmax"] - T0) / P)
                n_ev = max(0, n1 - n0 + 1)
                n_mid = round(((e["tmin"] + e["tmax"]) / 2 - T0) / P)
                if sP is not None and sT is not None and sP < 1 and sT < 1:
                    sig_h = 24 * math.sqrt(sT ** 2 + (n_mid * sP) ** 2)
            new.append(dict(sector=s, products=sorted(e["products"]), tmin=e["tmin"], tmax=e["tmax"], n_pred_transits=n_ev,
                            ephem_sigma_h=sig_h))
        rec = dict(tic=tic, review_rank=r["planet_rank"], signal_rank=r["signal_rank"], planet_band=r["planet_band"],
                   signal_band=r["signal_band"], verdict=r["pipeline_verdict"], period=P, period_err=sP, t0=T0, t0_err=sT,
                   depth_ppt=fit.get("depth_avg_ppt"), t14_h=fit.get("t14_hours"), rp=fit.get("rp_rearth"), rp_err=fit.get("rp_rearth_err"),
                   b=fit.get("b"), density_ratio=fit.get("density_ratio_fit_over_cat"),
                   fpp=fpp.get("fpp") if isinstance(fpp, dict) else fpp, nfpp=fpp.get("nfpp") if isinstance(fpp, dict) else None,
                   stageD_verdict=sd.get("verdict"), stageD_reason=sd.get("reason"),
                   tmag=float(row.Tmag), teff=float(row.Teff), rad=float(row.rad), dist_pc=float(row.d) if pd.notna(row.d) else None,
                   slice=row.slice, survey_ms_delta_mag=float(row.gaia_ms_delta_mag) if pd.notna(row.gaia_ms_delta_mag) else None,
                   survey_ms_status=row.gaia_ms_status, spoc_tce=row.spoc_tce if pd.notna(row.spoc_tce) else None,
                   in_toi=bool((toi["TIC ID"] == tic).any()), toi=", ".join(map(str, toi.loc[toi["TIC ID"] == tic, "TOI"])) or None,
                   in_ctoi=bool((ctoi["TIC ID"] == tic).any()), ctoi=", ".join(map(str, ctoi.loc[ctoi["TIC ID"] == tic, "CTOI"])) or None,
                   gaia_nearest=g0, gaia_n_within_3as=len(g), tic_gaia_str=row.GAIA,
                   packet_gaia_target_id=nb_t.get("source_id"), packet_gaia_target_G=nb_t.get("phot_g_mean_mag"),
                   packet_target_is_true_source=(str(nb_t.get("source_id")) == str(g0.get("source_id"))) if g0 else None,
                   new_sectors=new, n_new_transits=sum(x["n_pred_transits"] or 0 for x in new),
                   review_assessment=r["assessment"], review_next=r["next_step"])
        res.append(rec)
        log("o16", f"{tic} rank {rec['review_rank']} P {P:.4f} Rp {rec['rp']} FPP {rec['fpp']} TOI {rec['toi']} CTOI {rec['ctoi']} "
                   f"RUWE {g0.get('ruwe')} AEN {g0.get('astrometric_excess_noise_sig')} pkt-target-ok {rec['packet_target_is_true_source']} "
                   f"new {[(x['sector'], x['n_pred_transits'], round(x['ephem_sigma_h'], 1) if x['ephem_sigma_h'] else None) for x in new]}")
    save(RES / "other16_triage.json", res)
    keys = [k for k in res[0] if k not in ("gaia_nearest", "new_sectors", "review_assessment", "review_next")]
    with open(ROOT / "tables" / "other16_triage.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys + ["gaia_ruwe", "gaia_aen_sig", "gaia_nss", "new_sectors"])
        w.writeheader()
        for x in res:
            w.writerow({**{k: x[k] for k in keys}, "gaia_ruwe": x["gaia_nearest"].get("ruwe"),
                        "gaia_aen_sig": x["gaia_nearest"].get("astrometric_excess_noise_sig"),
                        "gaia_nss": x["gaia_nearest"].get("non_single_star"),
                        "new_sectors": "; ".join(f"S{s['sector']}:{s['n_pred_transits']}" for s in x["new_sectors"])})


if __name__ == "__main__":
    main()
