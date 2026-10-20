"""Targeted re-analysis of prompt-6 rank 16, TIC 233007823, P = 17.4683 d.

Prompt 6 killed this candidate on a 5% margin of the Stage B phase-independent test and
flagged the kill as the one borderline decision in the funnel.  This script decides it on
its own evidence.  It shares no decision code with the funnel: it folds the prepared
whole-baseline light curve, scans every phase for dips, measures each one per event with
the ``AUDIT.md`` removal rules, and tests the blend and eclipsing-binary hypotheses.

Sub-commands, each writing JSON under ``data/survey/p6/rank16/``:

    fold        phase-fold, bin, and scan all phases for dips (the discovery of any secondary)
    events      per-event table at an arbitrary phase offset, with the removal rules
    shape       primary and secondary durations, depths, ingress/egress, V-vs-U
    blend       depth by product/aperture and by sector; Gaia neighbours that could make it
    ephemeris   per-event mid-times, linear fit, TTV residuals
    report      assemble everything into one verdict record

Nothing here submits anything anywhere.  The pipeline finds candidates.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

TIC = 233007823
PERIOD = 17.46828986564532
OUT = REPO / "data" / "survey" / "p6" / "rank16"
OUT.mkdir(parents=True, exist_ok=True)

# thresholds for this re-analysis, stated once [A]
SIG_DIP = 5.0          # a phase-scan dip counts only above this many sigma
MIN_SEP_PHASE = 0.02   # distinct dips must be this far apart in phase


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def jdump(path: Path, obj) -> None:
    def conv(o):
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)
    path.write_text(json.dumps(obj, indent=1, default=conv), encoding="utf-8")


def survey_row() -> dict:
    import audit_p5 as A
    A.set_roots(REPO / "data" / "survey" / "p6", REPO / "data" / "survey" / "audit_lc")
    return A.survivor_row(TIC, PERIOD)


def load_lc():
    """The prepared whole-baseline series: unbinned detrended flux, its sector, and the raw products."""
    import audit_p5 as A
    A.set_roots(REPO / "data" / "survey" / "p6", REPO / "data" / "survey" / "audit_lc")
    z = np.load(REPO / "data" / "survey" / "p6" / "tls" / f"tic{TIC}_P{PERIOD:.4f}_lc.npz")
    return z["time_unbinned"], z["flux_unbinned"], z["sector_unbinned"]


def t0_of() -> float:
    return float(survey_row()["epoch_btjd"])


def dur_of() -> float:
    return float(survey_row()["duration_days"])


def box_depth(t, f, tc_phase, P, T0, width_days):
    """Depth of a box of `width_days` centred at phase `tc_phase`, and its error, from the folded series."""
    ph = ((t - T0) / P) % 1.0
    d = np.abs(((ph - tc_phase + 0.5) % 1.0) - 0.5) * P      # days from the box centre
    inb = d < width_days / 2
    out = (d > width_days) & (d < 4 * width_days)
    if inb.sum() < 5 or out.sum() < 50:
        return None
    base = float(np.nanmedian(f[out]))
    resid = f[out] - base
    sig = float(1.4826 * np.nanmedian(np.abs(resid - np.nanmedian(resid))))
    depth = base - float(np.nanmean(f[inb]))
    err = sig / math.sqrt(int(inb.sum()))
    return {"phase": float(tc_phase), "depth_ppt": 1000 * depth, "err_ppt": 1000 * err,
            "sigma": depth / err if err > 0 else 0.0, "n_in": int(inb.sum()), "n_out": int(out.sum()),
            "point_scatter_ppt": 1000 * sig}


def cmd_fold(args) -> dict:
    t, f, sec = load_lc()
    P, T0, dur = PERIOD, t0_of(), dur_of()
    width = args.width or dur
    # a full phase scan at the survey duration
    scan = []
    for ph in np.arange(0.0, 1.0, 0.002):
        r = box_depth(t, f, ph, P, T0, width)
        if r:
            scan.append(r)
    sig = np.array([s["sigma"] for s in scan])
    # distinct dips: local maxima of sigma above SIG_DIP, separated by MIN_SEP_PHASE
    order = np.argsort(-sig)
    dips, taken = [], []
    for i in order:
        if sig[i] < SIG_DIP:
            break
        ph = scan[i]["phase"]
        if any(min(abs(ph - q), 1 - abs(ph - q)) < MIN_SEP_PHASE for q in taken):
            continue
        taken.append(ph)
        dips.append(scan[i])
    # refine each dip on a fine grid
    refined = []
    for d in dips:
        best = d
        for ph in np.arange(d["phase"] - 0.01, d["phase"] + 0.01, 0.0004):
            r = box_depth(t, f, ph % 1.0, P, T0, width)
            if r and r["sigma"] > best["sigma"]:
                best = r
        best["t_mid_btjd_first"] = T0 + best["phase"] * P
        refined.append(best)
    refined.sort(key=lambda d: d["phase"] if d["phase"] < 0.5 else d["phase"] - 1.0)
    # a binned folded curve for the record
    ph = ((t - T0) / P) % 1.0
    nb = 400
    idx = np.clip((ph * nb).astype(int), 0, nb - 1)
    n = np.bincount(idx, minlength=nb)
    m = np.bincount(idx, weights=f, minlength=nb) / np.maximum(n, 1)
    folded = [{"phase": round((i + 0.5) / nb, 4), "flux_ppt_from_1": round(1000 * (m[i] - 1), 4), "n": int(n[i])}
              for i in range(nb) if n[i] > 0]
    res = {"tic_id": TIC, "period_days": P, "epoch_btjd": T0, "box_width_days": width,
           "generated_utc": utc(), "n_points": int(len(t)),
           "thresholds": {"min_sigma": SIG_DIP, "min_phase_separation": MIN_SEP_PHASE},
           "dips": refined, "folded_400_bins": folded}
    jdump(OUT / "fold.json", res)
    print(f"TIC {TIC} P={P:.5f} d, box {width * 24:.2f} h, {len(t)} points")
    print(f"{len(refined)} distinct dip(s) above {SIG_DIP} sigma:")
    for d in refined:
        print(f"  phase {d['phase']:.4f}  depth {d['depth_ppt']:7.3f} +/- {d['err_ppt']:.3f} ppt  "
              f"{d['sigma']:6.1f} sigma  n_in={d['n_in']}")
    return res


def cmd_events(args) -> dict:
    """Per-event table at an arbitrary phase offset, with the AUDIT.md removal rules applied."""
    import audit_p5 as A
    A.set_roots(REPO / "data" / "survey" / "p6", REPO / "data" / "survey" / "audit_lc")
    P, T0, dur = PERIOD, t0_of() + args.phase * PERIOD, args.width or dur_of()
    row = survey_row()
    ref_depth = float(row["depth_ppt"]) / 1000.0
    products = A.choose_per_sector(A.load_products(TIC))
    z = np.load(REPO / "data" / "survey" / "p6" / "tls" / f"tic{TIC}_P{PERIOD:.4f}_lc.npz")
    tdet, fdet = z["time_unbinned"], z["flux_unbinned"]
    half = dur / 2
    tmin = min(p["t_start"] for p in products); tmax = max(p["t_end"] for p in products)
    n0 = math.ceil((tmin - T0) / P); n1 = math.floor((tmax - T0) / P)
    events = []
    for n in range(n0, n1 + 1):
        tc = T0 + n * P
        prods = [p for p in products if p["t_start"] - 0.25 <= tc <= p["t_end"] + 0.25]
        if not prods:
            continue
        p = prods[0]
        t, q = p["time"], p["quality"]
        sap = p["sap_flux"] if np.isfinite(p["sap_flux"]).sum() > 0.5 * len(t) else p["flux"]
        sap_is_pdc = sap is p["flux"]
        pmask = A.product_bitmask(p)
        fin = np.isfinite(t) & np.isfinite(sap)
        hw = max(3.0 * dur, 0.5)
        m_in = fin & (np.abs(t - tc) < half)
        m_out = fin & (np.abs(t - tc) < hw) & (np.abs(t - tc) > 1.3 * half)
        cad_d = p["cadence_s"] / 86400.0
        cov = m_in.sum() / max(1, int(round(dur / cad_d)))
        ev = {"n": n, "tc_btjd": round(tc, 4), "sector": p["sector"], "author": p["author"],
              "cadence_s": p["cadence_s"], "coverage": round(min(cov, 1.0), 2)}
        if cov < 0.5 or m_out.sum() < 10:
            ev.update({"observed": False, "reason": "coverage or baseline"}); events.append(ev); continue
        ev["observed"] = True
        tt, qq = t[np.isfinite(t)], q[np.isfinite(t)]
        in_all = np.abs(tt - tc) < half
        near = np.abs(tt - tc) < max(dur, 0.25)
        reasons = []
        if np.any(qq[near] & A.Q_DESAT):
            reasons.append("momentum dump within one duration")
        qf = float(np.count_nonzero(qq[in_all] & pmask) / max(1, in_all.sum()))
        if qf > 0.2:
            reasons.append(f"{qf:.0%} of in-transit cadences quality-flagged")
        sf = float(np.count_nonzero(qq[near] & A.Q_STRAYLIGHT) / max(1, near.sum()))
        if sf > 0.2:
            reasons.append(f"{sf:.0%} scattered-light flagged within one duration")
        dt = np.diff(tt)
        edges = np.concatenate([[tt[0], tt[-1]], tt[:-1][dt > 0.5], tt[1:][dt > 0.5]])
        ed = float(np.min(np.abs(edges - tc)))
        if ed < max(dur, 0.2):
            reasons.append(f"sector/orbit edge {ed:.2f} d away")
        fp = p["flux"]; tp = t[np.isfinite(t) & np.isfinite(fp)]
        pd_ = float(np.min(np.abs(np.concatenate([[tp[0], tp[-1]], tp[:-1][np.diff(tp) > 0.5],
                                                  tp[1:][np.diff(tp) > 0.5]]) - tc))) if tp.size > 2 else 0.0
        if pd_ < max(dur, 0.2) and ed >= max(dur, 0.2):
            reasons.append(f"PDC gap {pd_:.2f} d away")
        clean = m_out & ((q & pmask) == 0)
        if clean.sum() < 10:
            clean = m_out
        x = t[clean] - tc; y = sap[clean]; ym = np.nanmedian(y)
        try:
            co = np.polyfit(x, y / ym, 2)
        except Exception:
            co = np.array([0.0, 0.0, 1.0])
        base = np.polyval(co, t - tc) * ym
        r_out = sap[clean] / base[clean] - 1.0
        sg = 1.4826 * np.nanmedian(np.abs(r_out - np.nanmedian(r_out)))
        in_clean = m_in & ((q & pmask) == 0)
        if in_clean.sum() < max(2, 0.3 * m_in.sum()):
            in_clean = m_in
        dsap = float(1.0 - np.nanmean(sap[in_clean] / base[in_clean]))
        esap = float(sg / math.sqrt(max(1, in_clean.sum())))
        ev["sap_depth_ppt"] = round(1000 * dsap, 3); ev["sap_depth_err_ppt"] = round(1000 * esap, 3)
        bch = float(abs(np.polyval(co, half) - np.polyval(co, -half)))
        if bch / max(ref_depth, 1e-5) > 1.0:
            reasons.append("SAP baseline ramp across the event")
        md_in = np.abs(tdet - tc) < half
        md_out = (np.abs(tdet - tc) < hw) & (np.abs(tdet - tc) > 1.3 * half)
        if md_in.sum() >= 2 and md_out.sum() >= 10:
            sd = 1.4826 * np.nanmedian(np.abs(fdet[md_out] - np.nanmedian(fdet[md_out])))
            ev["det_depth_ppt"] = round(1000 * float(1.0 - np.nanmean(fdet[md_in])), 3)
            ev["det_depth_err_ppt"] = round(1000 * float(sd / math.sqrt(md_in.sum())), 3)
        else:
            ev["det_depth_ppt"] = None; ev["det_depth_err_ppt"] = None
        dd, de = ev["det_depth_ppt"], ev["det_depth_err_ppt"]
        if dd is not None and de and dd / de > 5 and not sap_is_pdc and ev["sap_depth_ppt"] < 0.3 * dd:
            reasons.append("dip in corrected flux, absent in SAP")
        ev["excluded"] = bool(reasons); ev["exclusion_reasons"] = reasons
        events.append(ev)
    obs = [e for e in events if e.get("observed")]
    kept = [e for e in obs if not e["excluded"]]

    def stats(evs, kind):
        evs = [e for e in evs if e.get(f"{kind}_depth_ppt") is not None and e.get(f"{kind}_depth_err_ppt")]
        if not evs:
            return {"n": 0}
        d = np.array([e[f"{kind}_depth_ppt"] for e in evs]); s = np.array([e[f"{kind}_depth_err_ppt"] for e in evs])
        w = 1 / s ** 2
        mean = float(np.sum(w * d) / np.sum(w)); err = float(1 / math.sqrt(np.sum(w)))
        chi2 = float(np.sum(((d - mean) / s) ** 2)); dof = max(1, len(d) - 1)
        from scipy import stats as sst
        odd = [i for i, e in enumerate(evs) if e["n"] % 2]; even = [i for i, e in enumerate(evs) if not e["n"] % 2]
        oe = None
        if odd and even:
            mo = float(np.sum(w[odd] * d[odd]) / np.sum(w[odd])); eo = float(1 / math.sqrt(np.sum(w[odd])))
            me = float(np.sum(w[even] * d[even]) / np.sum(w[even])); ee = float(1 / math.sqrt(np.sum(w[even])))
            oe = {"odd_ppt": round(mo, 3), "odd_err": round(eo, 3), "even_ppt": round(me, 3),
                  "even_err": round(ee, 3), "sigma": round(abs(mo - me) / math.sqrt(eo ** 2 + ee ** 2), 2)}
        return {"n": len(d), "weighted_mean_depth_ppt": round(mean, 3), "err_ppt": round(err, 4),
                "snr": round(mean / err, 2), "chi2_const": round(chi2, 1), "dof": dof,
                "p_const": float(sst.chi2.sf(chi2, dof)), "median_per_event_sigma": round(float(np.median(d / s)), 2),
                "n_events_above_3sigma": int(np.sum(d / s > 3)), "odd_even": oe}

    res = {"tic_id": TIC, "period_days": P, "phase_offset": args.phase, "epoch_btjd": T0,
           "box_width_days": dur, "generated_utc": utc(), "label": args.label,
           "n_observed": len(obs), "n_excluded": len(obs) - len(kept), "n_kept": len(kept),
           "det_kept": stats(kept, "det"), "sap_kept": stats(kept, "sap"),
           "det_all": stats(obs, "det"), "sap_all": stats(obs, "sap"), "events": events}
    jdump(OUT / f"events_{args.label}.json", res)
    dk, sk = res["det_kept"], res["sap_kept"]
    print(f"[{args.label}] phase {args.phase:.4f}, {len(obs)} observed, {len(kept)} kept")
    print(f"  detrended kept: depth {dk.get('weighted_mean_depth_ppt')} +/- {dk.get('err_ppt')} ppt, "
          f"SNR {dk.get('snr')}, median per-event {dk.get('median_per_event_sigma')} sigma, "
          f"p_const {dk.get('p_const'):.3g}, odd/even {(dk.get('odd_even') or {}).get('sigma')}")
    print(f"  raw SAP  kept: depth {sk.get('weighted_mean_depth_ppt')} +/- {sk.get('err_ppt')} ppt, "
          f"SNR {sk.get('snr')}")
    return res


def cmd_blend(args) -> dict:
    """Depth by product author (different apertures) and by sector: a blend dilutes differently."""
    import audit_p5 as A
    A.set_roots(REPO / "data" / "survey" / "p6", REPO / "data" / "survey" / "audit_lc")
    out = {"tic_id": TIC, "generated_utc": utc(), "by_label": {}}
    for label in ("primary", "secondary"):
        p = OUT / f"events_{label}.json"
        if not p.exists():
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        kept = [e for e in rec["events"] if e.get("observed") and not e.get("excluded")
                and e.get("det_depth_ppt") is not None and e.get("det_depth_err_ppt")]
        groups: dict = {}
        for e in kept:
            groups.setdefault(e["author"], []).append(e)
        by_author = {}
        for k, evs in groups.items():
            d = np.array([e["det_depth_ppt"] for e in evs]); s = np.array([e["det_depth_err_ppt"] for e in evs])
            w = 1 / s ** 2
            by_author[k] = {"n": len(d), "depth_ppt": round(float(np.sum(w * d) / np.sum(w)), 3),
                            "err_ppt": round(float(1 / math.sqrt(np.sum(w))), 4),
                            "cadences_s": sorted({e["cadence_s"] for e in evs})}
        gs: dict = {}
        for e in kept:
            gs.setdefault(e["sector"], []).append(e)
        by_sector = {}
        for k, evs in sorted(gs.items()):
            d = np.array([e["det_depth_ppt"] for e in evs]); s = np.array([e["det_depth_err_ppt"] for e in evs])
            w = 1 / s ** 2
            by_sector[str(k)] = {"n": len(d), "depth_ppt": round(float(np.sum(w * d) / np.sum(w)), 3),
                                 "err_ppt": round(float(1 / math.sqrt(np.sum(w))), 4)}
        out["by_label"][label] = {"by_author": by_author, "by_sector": by_sector}
        print(f"[{label}] depth by product aperture:")
        for k, v in by_author.items():
            print(f"   {k:<10} n={v['n']:>3}  {v['depth_ppt']:7.3f} +/- {v['err_ppt']:.3f} ppt  cad {v['cadences_s']}")
    nb = REPO / "data" / "survey" / "p6" / "neighbours" / f"tic{TIC}.json"
    if nb.exists():
        n = json.loads(nb.read_text(encoding="utf-8"))
        g = n.get("gaia", {}) or {}
        tg = g.get("target") or {}
        out["gaia_target"] = {k: tg.get(k) for k in ("source_id", "ruwe", "ipd_frac_multi_peak",
                                                     "astrometric_excess_noise_sig", "phot_g_mean_mag",
                                                     "phot_rp_mean_mag", "parallax", "non_single_star")}
        cand = [x for x in g.get("neighbours", []) if (x.get("sep_arcsec") or 999) <= 63
                and (x.get("max_observed_depth_ppt_total_eclipse") or 0) >= 3.4]
        out["neighbours_that_could_make_the_depth"] = cand
        print(f"\nGaia: RUWE {tg.get('ruwe')}, aen_sig {tg.get('astrometric_excess_noise_sig')}, "
              f"{len(cand)} neighbour(s) within 3 px able to make 3.4 ppt if totally eclipsed")
        for c in cand[:6]:
            print(f"   sep {c['sep_arcsec']:6.1f}\" ({c['sep_px']:.2f} px)  dG {c.get('delta_mag')}  "
                  f"max depth {c.get('max_observed_depth_ppt_total_eclipse')} ppt")
    jdump(OUT / "blend.json", out)
    return out


def cmd_shape(args) -> dict:
    """Depth profile and width of each dip, and the eccentricity the pair implies.

    An eccentric eclipsing binary must satisfy two relations at once: the secondary sits at
    phase 0.5 + (2/pi) e cos(w), and the two eclipse durations are in the ratio
    (1 + e sin w) / (1 - e sin w).  Measuring both over-determines (e, w), so agreement is a
    real test rather than a fit.
    """
    t, f, sec = load_lc()
    P, T0 = PERIOD, t0_of()
    ph = ((t - T0) / P) % 1.0
    out = {"tic_id": TIC, "period_days": P, "generated_utc": utc(), "dips": {}}
    fold = json.loads((OUT / "fold.json").read_text(encoding="utf-8"))
    for d, label in zip(sorted(fold["dips"], key=lambda x: 0 if (x["phase"] > 0.9 or x["phase"] < 0.1) else 1),
                        ("primary", "secondary")):
        c = d["phase"]
        dphi = np.abs(((ph - c + 0.5) % 1.0) - 0.5)
        # fine profile in days from mid-eclipse
        prof, step = [], 0.15 / 24.0 / P           # 9-minute steps in phase
        for k in range(-60, 61):
            lo, hi = abs(k) * step, (abs(k) + 1) * step
            m = (dphi >= lo) & (dphi < hi) if k else (dphi < step)
            if k < 0:
                m = m & (((ph - c + 0.5) % 1.0) - 0.5 < 0)
            elif k > 0:
                m = m & (((ph - c + 0.5) % 1.0) - 0.5 > 0)
            if m.sum() > 20:
                prof.append({"dt_hours": round(k * step * P * 24, 3), "flux_ppt": round(1000 * (float(np.mean(f[m])) - 1), 4),
                             "err_ppt": round(1000 * float(np.std(f[m]) / math.sqrt(m.sum())), 4), "n": int(m.sum())})
        base = float(np.median([q["flux_ppt"] for q in prof if abs(q["dt_hours"]) > 4.0])) if prof else 0.0
        deep = min(q["flux_ppt"] for q in prof)
        half = base + 0.5 * (deep - base)
        below = [q["dt_hours"] for q in prof if q["flux_ppt"] <= half]
        w_half = (max(below) - min(below)) if below else None
        out["dips"][label] = {"phase": c, "depth_ppt": d["depth_ppt"], "err_ppt": d["err_ppt"],
                              "sigma": d["sigma"], "baseline_ppt": round(base, 4),
                              "deepest_bin_ppt": round(deep, 4),
                              "width_at_half_depth_hours": None if w_half is None else round(w_half, 3),
                              "profile": prof}
    pr, se = out["dips"].get("primary"), out["dips"].get("secondary")
    if pr and se:
        dphi = (se["phase"] - pr["phase"]) % 1.0
        ecosw = (math.pi / 2.0) * (dphi - 0.5)
        r = (se["width_at_half_depth_hours"] / pr["width_at_half_depth_hours"]
             if pr["width_at_half_depth_hours"] else None)
        esinw = (r - 1) / (r + 1) if r else None
        out["eccentric_binary_test"] = {
            "secondary_phase_offset_from_0.5": round(dphi - 0.5, 5),
            "e_cos_omega_from_phase": round(ecosw, 4),
            "duration_ratio_secondary_over_primary": None if r is None else round(r, 3),
            "e_sin_omega_from_durations": None if esinw is None else round(esinw, 4),
            "e": None if esinw is None else round(math.hypot(ecosw, esinw), 4),
            "omega_deg": None if esinw is None else round(math.degrees(math.atan2(esinw, ecosw)), 1),
            "depth_ratio_secondary_over_primary": round(se["depth_ppt"] / pr["depth_ppt"], 4),
        }
        # what a planet could produce at this period, for comparison
        row = survey_row()
        rstar = float(row["radius_rsun"]); mstar = float(row["mass_msun"])
        G = 6.674e-8
        a_rs = ((G * mstar * 1.989e33 * (P * 86400.0) ** 2) / (4 * math.pi ** 2)) ** (1 / 3) / (rstar * 6.957e10)
        teff = 5733.0
        teq = teff * math.sqrt(1.0 / (2.0 * a_rs))
        # Planck ratio in the TESS band (800 nm) between the companion and the star
        def planck(T, lam_cm=8.0e-5):
            h, c_, kB = 6.626e-27, 2.998e10, 1.381e-16
            return 1.0 / (lam_cm ** 5 * (math.exp(h * c_ / (lam_cm * kB * T)) - 1.0))
        therm = planck(teq) / planck(teff)
        depth_pri = pr["depth_ppt"]
        refl = 0.3 * (depth_pri / 1000.0) / a_rs ** 2
        out["planet_secondary_bound"] = {
            "a_over_rstar": round(a_rs, 2), "T_eq_K": round(teq, 0),
            "thermal_flux_ratio_800nm": therm,
            "max_thermal_secondary_ppt": therm * depth_pri,
            "max_reflected_secondary_ppt": 1000 * refl,
            "max_total_planetary_secondary_ppt": therm * depth_pri + 1000 * refl,
            "measured_secondary_ppt": se["depth_ppt"],
            "ratio_measured_over_max_planetary": (se["depth_ppt"] /
                                                  max(therm * depth_pri + 1000 * refl, 1e-12)),
        }
    jdump(OUT / "shape.json", out)
    for k, v in out["dips"].items():
        print(f"{k:<10} phase {v['phase']:.4f}  depth {v['depth_ppt']:6.3f} +/- {v['err_ppt']:.3f} ppt  "
              f"width at half depth {v['width_at_half_depth_hours']} h")
    if "eccentric_binary_test" in out:
        e = out["eccentric_binary_test"]
        print("\neccentric-binary test:")
        for k, v in e.items():
            print(f"   {k}: {v}")
        b = out["planet_secondary_bound"]
        print("\ndeepest secondary a planet could make here:")
        print(f"   a/R* {b['a_over_rstar']}, T_eq {b['T_eq_K']} K -> thermal {b['max_thermal_secondary_ppt']:.2e} ppt"
              f" + reflected {b['max_reflected_secondary_ppt']:.2e} ppt"
              f" = {b['max_total_planetary_secondary_ppt']:.2e} ppt")
        print(f"   measured secondary {b['measured_secondary_ppt']:.3f} ppt = "
              f"{b['ratio_measured_over_max_planetary']:.3g} x that bound")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fold"); f.add_argument("--width", type=float, default=None)
    e = sub.add_parser("events")
    e.add_argument("--phase", type=float, required=True)
    e.add_argument("--label", required=True)
    e.add_argument("--width", type=float, default=None)
    sub.add_parser("blend")
    sub.add_parser("shape")
    args = ap.parse_args(argv)
    {"fold": cmd_fold, "events": cmd_events, "blend": cmd_blend, "shape": cmd_shape}[args.cmd](args)


if __name__ == "__main__":
    main()
