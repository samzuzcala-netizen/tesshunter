"""Per-event examination of a candidate's predicted transits, and the removal rules.

This is ``docs/AUDIT.md`` section 1 steps 3 and 4, ported out of
``scripts/audit_p5.py`` unchanged.  Every predicted epoch over the whole
baseline is measured twice — in the wotan-detrended corrected flux (the search
input) and in the raw SAP flux against a local quadratic baseline — and removed
when it coincides with a momentum dump, a sector or orbit edge, a PDC gap,
quality- or scattered-light-flagged cadences, a background or baseline ramp, or
when the dip is significant in the corrected flux and absent in SAP.

Pure: arrays and product dicts in, event dicts out.  No MAST, no file paths.

Two prompt-7 options live here:

* ``beta_by_sector`` inflates each event's error by its sector's red-noise beta
  before the depth-consistency chi-square, so the binding rule for real signals
  is not decided by white errors alone;
* ``sector_beta`` measures those betas from the binned out-of-transit residuals
  with the recipe already used by ``audit_p5.fit_step``.
"""
from __future__ import annotations

import math

import numpy as np

from .audit_prep import bin_lc, product_bitmask
from .audit_rules import (
    A_DEPTH_HI,
    A_DEPTH_LO,
    A_MAX_TOP_SHARE,
    A_MIN_KEPT,
    A_MIN_SNR,
    A_MIN_SNR_WO_TOP,
    A_P_CONST,
    BASELINE_HALF_WINDOW_DURATIONS,
    BASELINE_HALF_WINDOW_MIN_DAYS,
    BASELINE_POLY_DEGREE,
    BETA_BIN_DURATION_FRACTION,
    BETA_MAX,
    BETA_MIN,
    BETA_MIN_BINS,
    BETA_MIN_POINTS,
    BKG_CHANGE_OVER_MEDIAN,
    BKG_OVER_SECTOR_MEDIAN,
    EDGE_GAP_DAYS,
    EDGE_MIN_WINDOW_DAYS,
    EVENT_MIN_BASELINE_POINTS,
    EVENT_MIN_COVERAGE,
    EVENTS_FLAG_EXCLUDED_FRACTION,
    EVENTS_FLAG_MIN_SNR,
    NEAR_EVENT_MIN_DAYS,
    OUT_OF_TRANSIT_MARGIN,
    Q_DESAT,
    Q_MANUAL,
    Q_STRAYLIGHT,
    QUALITY_FLAG_FRACTION,
    SAP_ABSENT_MIN_SIGMA,
    SAP_ABSENT_RATIO,
    SAP_RAMP_OVER_DEPTH,
    STRAYLIGHT_FLAG_FRACTION,
)

__all__ = [
    "predicted_epochs", "measure_event", "event_table", "weighted_mean",
    "kept_event_stats", "summarise_events", "sector_beta", "advisory_flags",
    "stagea_criteria", "ARTEFACT_CLASSES", "classes_of",
]

#: the exclusion-reason fragment that identifies each artefact class, so a
#: reason string can be classified without re-running the rule.
ARTEFACT_CLASSES = {
    "dip_absent_in_sap": "dip present in corrected flux",
    "pdc_gap": "corrected flux has a PDC gap",
    "scattered_light_ramp": "scattered-light ramp (background",
    "scattered_light_flag": "carry the scattered-light flag",
    "momentum_dump": "momentum dump within one duration",
    "sector_orbit_edge": "sector/orbit edge",
    "quality_flagged": "of in-transit cadences quality-flagged",
    "sap_baseline_ramp": "SAP baseline changes by more than one depth",
}


#: [K1] change 12: None (prompts 5-12) or a multiple of the event's SAP depth error; when set,
#: the SAP-ramp rule fires only if the baseline change across the event exceeds
#: max(SAP_RAMP_OVER_DEPTH x depth, SAP_RAMP_NOISE_MULTIPLE x SAP depth error).
SAP_RAMP_NOISE_MULTIPLE = None

#: [K1] amendment 2: the per-event depth estimator on the detrended series.  None (prompts 5-12): the
#: mean deficit inside +/- T/2.  "exposure_ld": the least-squares amplitude of a quadratic limb-darkened
#: chord template integrated over the observing product's exposure, fitted to every cadence it overlaps.
#: The template has unit mean over the chord, so at fine cadence the amplitude is the box mean of a
#: limb-darkened transit; with mixed exposures it removes the smearing (1800 s vs 200 s) and the
#: sampling-phase scatter that make the box means of coarse-cadence events disagree.
EVENT_DEPTH_TEMPLATE = None
EVENT_DEPTH_LD = (0.45, 0.20)
EVENT_DEPTH_SUPERSAMPLE = 15

#: [K2] rule A1 (k2/protocol/RULES_K2.md section 3): None (K1 and every earlier prompt) or the scope the Stage A
#: gate reads, "author" (TESS-SPOC/SPOC vs QLP) or "author_exposure" (also split by exposure class).  When set,
#: ``kept_event_stats`` records both scopes' within-family depth consistency and family means under ``a1``, and
#: ``stagea_criteria``'s depth-consistency criterion passes when the K1 test passes OR (the within-family p-value
#: >= p_min AND every family's mean agrees with the dominant family's).  None leaves every output unchanged.
DEPTH_CONSISTENCY_FAMILIES = None
A1_SCOPES = ("author", "author_exposure")
A1_RATIO_LO, A1_RATIO_HI = 0.8, 1.25
A1_MEAN_SIGMA = 3.0
A1_EXPOSURE_GRID_S = (120.0, 200.0, 600.0, 1800.0)


def exposure_ld_template(x: np.ndarray, duration: float, exposure_days: float,
                         u: tuple[float, float] | None = None, n: int | None = None) -> np.ndarray:
    """Unit-chord-mean, b = 0 quadratic limb-darkened transit profile at offsets ``x`` (days) from
    mid-transit, averaged over an exposure of ``exposure_days`` with ``n`` sub-samples."""
    u1, u2 = u or EVENT_DEPTH_LD
    n = int(n or EVENT_DEPTH_SUPERSAMPLE)
    off = (np.arange(n) + 0.5) / n - 0.5
    xx = np.asarray(x, dtype=float)[:, None] + off[None, :] * float(exposure_days)
    r = np.clip(2.0 * np.abs(xx) / duration, 0.0, 1.0)
    mu = np.sqrt(1.0 - r * r)
    prof = np.where(np.abs(xx) < duration / 2.0, 1.0 - u1 * (1.0 - mu) - u2 * (1.0 - mu) ** 2, 0.0)
    chord_mean = 1.0 - u1 * (1.0 - math.pi / 4.0) - u2 * (5.0 / 3.0 - math.pi / 2.0)
    return prof.mean(axis=1) / chord_mean


def classes_of(reasons: list[str]) -> list[str]:
    """Which artefact classes a list of removal reasons belongs to."""
    return [k for k, frag in ARTEFACT_CLASSES.items() if any(frag in r for r in reasons)]


def predicted_epochs(t_min: float, t_max: float, period: float, t0: float) -> range:
    """Every epoch number whose mid-time falls inside the observed baseline."""
    n0 = math.ceil((t_min - t0) / period)
    n1 = math.floor((t_max - t0) / period)
    return range(n0, n1 + 1)


def measure_event(product: dict, tc: float, duration: float, ref_depth: float,
                  t_det: np.ndarray, f_det: np.ndarray, epoch: int) -> dict:
    """Measure one predicted epoch and apply the removal rules.

    ``product`` carries the raw arrays of the product that observed the epoch;
    ``t_det`` / ``f_det`` are the whole-baseline detrended corrected series.
    ``ref_depth`` is the candidate depth as a fraction (not ppt).
    """
    half = duration / 2.0
    ev = {"n": epoch, "tc_btjd": round(tc, 4), "tc_bjd": round(tc + 2457000.0, 4)}
    p = product
    t, q = p["time"], p["quality"]
    sap = p["sap_flux"] if np.isfinite(p["sap_flux"]).sum() > 0.5 * len(t) else p["flux"]
    sap_is_pdc = sap is p["flux"]
    bkg = p["sap_bkg"]
    cad_d = p["cadence_s"] / 86400.0
    hw = max(BASELINE_HALF_WINDOW_DURATIONS * duration, BASELINE_HALF_WINDOW_MIN_DAYS)
    fin = np.isfinite(t) & np.isfinite(sap)
    m_win = fin & (np.abs(t - tc) < hw)
    m_in = fin & (np.abs(t - tc) < half)
    m_out = m_win & (np.abs(t - tc) > OUT_OF_TRANSIT_MARGIN * half)
    expected_in = max(1, int(round(duration / cad_d)))
    coverage = float(m_in.sum() / expected_in)
    ev.update({"sector": p["sector"], "author": p["author"], "cadence_s": p["cadence_s"],
               "flux_used": "sap_flux" if not sap_is_pdc else p["flux_column"],
               "coverage_in_transit": round(min(coverage, 1.0), 2),
               "n_in": int(m_in.sum()), "n_out": int(m_out.sum())})
    if coverage < EVENT_MIN_COVERAGE or m_out.sum() < EVENT_MIN_BASELINE_POINTS:
        ev.update({"observed": False,
                   "reason": f"in-transit coverage {coverage:.0%} (< 50%) or too few baseline points"})
        return ev
    ev["observed"] = True
    # quality: default-mask flags (plus QLP's low-precision flag) inside the transit;
    # momentum dumps within one duration
    pmask = product_bitmask(p)
    tt = t[np.isfinite(t)]
    qq = q[np.isfinite(t)]
    in_all = np.abs(tt - tc) < half
    ev["frac_in_transit_quality_flagged"] = round(
        float(np.count_nonzero(qq[in_all] & pmask) / max(1, in_all.sum())), 2)
    near = np.abs(tt - tc) < max(duration, NEAR_EVENT_MIN_DAYS)
    ev["desat_within_one_duration"] = bool(np.any(qq[near] & Q_DESAT))
    ev["manual_exclude_within_one_duration"] = bool(np.any(qq[near] & Q_MANUAL))
    ev["straylight_flag_in_transit"] = bool(np.any(qq[in_all] & Q_STRAYLIGHT))
    # edges: sector start/end and internal gaps > 0.5 d (in the SAP time series, all cadences)
    dt = np.diff(tt)
    gap_edges = np.concatenate([[tt[0], tt[-1]], tt[:-1][dt > EDGE_GAP_DAYS], tt[1:][dt > EDGE_GAP_DAYS]])
    edge_dist = float(np.min(np.abs(gap_edges - tc)))
    ev["edge_distance_days"] = round(edge_dist, 3)
    ev["edge_within_one_duration"] = bool(edge_dist < max(duration, EDGE_MIN_WINDOW_DAYS))
    # the same for the corrected flux actually searched: PDC gaps (NaN stretches >= 0.5 d) count as edges
    fp = p["flux"]
    tp = t[np.isfinite(t) & np.isfinite(fp)]
    if tp.size > 2:
        dtp = np.diff(tp)
        pdc_edges = np.concatenate([[tp[0], tp[-1]], tp[:-1][dtp > EDGE_GAP_DAYS], tp[1:][dtp > EDGE_GAP_DAYS]])
        pdc_dist = float(np.min(np.abs(pdc_edges - tc)))
    else:
        pdc_dist = 0.0
    ev["pdc_gap_distance_days"] = round(pdc_dist, 3)
    ev["pdc_gap_within_one_duration"] = bool(pdc_dist < max(duration, EDGE_MIN_WINDOW_DAYS))
    ev["frac_straylight_flagged_within_one_duration"] = round(
        float(np.count_nonzero(qq[near] & Q_STRAYLIGHT) / max(1, near.sum())), 2)
    # local SAP baseline (quadratic on out-of-transit, quality-clean points)
    clean = m_out & ((q & pmask) == 0)
    if clean.sum() < EVENT_MIN_BASELINE_POINTS:
        clean = m_out
    x = t[clean] - tc
    y = sap[clean]
    y_med = np.nanmedian(y)
    try:
        co = np.polyfit(x, y / y_med, BASELINE_POLY_DEGREE)
    except Exception:
        co = np.array([0.0, 0.0, 1.0])
    base = np.polyval(co, t - tc) * y_med
    resid_out = sap[clean] / base[clean] - 1.0
    sig_pt = 1.4826 * np.nanmedian(np.abs(resid_out - np.nanmedian(resid_out)))
    in_clean = m_in & ((q & pmask) == 0)
    if in_clean.sum() < max(2, 0.3 * m_in.sum()):
        in_clean = m_in
    depth_sap = float(1.0 - np.nanmean(sap[in_clean] / base[in_clean]))
    err_sap = float(sig_pt / math.sqrt(max(1, in_clean.sum())))
    ev["sap_depth_ppt"] = round(1000 * depth_sap, 3)
    ev["sap_depth_err_ppt"] = round(1000 * err_sap, 3)
    ev["sap_point_scatter_ppt"] = round(1000 * sig_pt, 3)
    # ramp: baseline change across the event relative to the candidate depth; slope over the window
    b_change = float(abs(np.polyval(co, half) - np.polyval(co, -half)))
    ev["baseline_change_across_event_over_depth"] = round(b_change / max(ref_depth, 1e-5), 2)
    if SAP_RAMP_NOISE_MULTIPLE is not None:
        ev["baseline_change_across_event_ppt"] = round(1000 * b_change, 4)
        ev["sap_ramp_noise_threshold_ppt"] = round(1000 * float(SAP_RAMP_NOISE_MULTIPLE) * err_sap, 4)
    ev["baseline_change_across_window_ppt"] = round(
        1000 * float(abs(np.polyval(co, hw) - np.polyval(co, -hw))), 2)
    # background: level relative to the sector, and the background CHANGE within one duration expressed
    # as a fraction of the star's SAP flux (the units a transit depth is measured in)
    if np.isfinite(bkg).sum() > 10:
        bk_sector = float(np.nanmedian(bkg))
        bk_win = bkg[m_win]
        tw = t[m_win]
        bk_in = float(np.nanmedian(bkg[m_in])) if np.isfinite(bkg[m_in]).any() else np.nan
        ok = np.isfinite(bk_win)
        slope = float(np.polyfit(tw[ok] - tc, bk_win[ok], 1)[0]) if ok.sum() > 5 else np.nan
        ev["bkg_in_over_sector_median"] = round(bk_in / bk_sector, 2) if bk_sector > 0 and np.isfinite(bk_in) else None
        ev["bkg_change_across_window_over_median"] = (
            round(abs(slope) * 2 * hw / bk_sector, 2) if bk_sector > 0 and np.isfinite(slope) else None)
        m_near = fin & (np.abs(t - tc) < max(duration, NEAR_EVENT_MIN_DAYS)) & np.isfinite(bkg)
        # QLP ships a normalised SAP flux (median 1), so the background cannot be expressed in flux units there
        if m_near.sum() >= 6 and float(y_med) > 100.0:
            # 1-hour medians of the background within +/- one duration
            tb_, bb_, _ = bin_lc(t[m_near], bkg[m_near], np.ones(m_near.sum()), 60.0)
            bkg_range = float(np.nanmax(bb_) - np.nanmin(bb_))
            ev["bkg_change_within_one_duration_ppt_of_flux"] = round(1000 * bkg_range / max(float(y_med), 1e-9), 2)
        else:
            ev["bkg_change_within_one_duration_ppt_of_flux"] = None
    else:
        ev["bkg_in_over_sector_median"] = None
        ev["bkg_change_across_window_over_median"] = None
        ev["bkg_change_within_one_duration_ppt_of_flux"] = None
    # depth on the detrended PDCSAP (the search input, unbinned)
    if EVENT_DEPTH_TEMPLATE == "exposure_ld":
        reach = half + cad_d / 2.0
        md_in = (np.abs(t_det - tc) < reach) & np.isfinite(f_det)
        md_out = (np.abs(t_det - tc) < hw) & (np.abs(t_det - tc) > max(OUT_OF_TRANSIT_MARGIN * half, reach))
    else:
        md_in = np.abs(t_det - tc) < half
        md_out = (np.abs(t_det - tc) < hw) & (np.abs(t_det - tc) > OUT_OF_TRANSIT_MARGIN * half)
    if md_in.sum() >= 2 and md_out.sum() >= EVENT_MIN_BASELINE_POINTS:
        r_out = f_det[md_out] - np.nanmedian(f_det[md_out])
        s_det = 1.4826 * np.nanmedian(np.abs(r_out))
        if EVENT_DEPTH_TEMPLATE == "exposure_ld":
            m = exposure_ld_template(t_det[md_in] - tc, duration, cad_d)
            m2 = float(np.sum(m * m))
            ev["det_depth_ppt"] = round(1000 * float(np.sum(m * (1.0 - f_det[md_in])) / m2), 3)
            ev["det_depth_err_ppt"] = round(1000 * float(s_det / math.sqrt(m2)), 3)
            ev["det_depth_estimator"] = "exposure_ld"
        else:
            ev["det_depth_ppt"] = round(1000 * float(1.0 - np.nanmean(f_det[md_in])), 3)
            ev["det_depth_err_ppt"] = round(1000 * float(s_det / math.sqrt(md_in.sum())), 3)
        ev["det_n_in"] = int(md_in.sum())
    else:
        ev["det_depth_ppt"] = None
        ev["det_depth_err_ppt"] = None
        ev["det_n_in"] = int(md_in.sum())
    reasons = removal_reasons(ev, edge_dist, pdc_dist, sap_is_pdc)
    ev["excluded"] = bool(reasons)
    ev["exclusion_reasons"] = reasons
    return ev


def removal_reasons(ev: dict, edge_dist: float, pdc_dist: float, sap_is_pdc: bool) -> list[str]:
    """The removal rules of ``docs/AUDIT.md`` section 1 step 3, in order."""
    reasons: list[str] = []
    if ev["desat_within_one_duration"]:
        reasons.append("momentum dump within one duration")
    if ev["edge_within_one_duration"]:
        reasons.append(f"sector/orbit edge {edge_dist:.2f} d away")
    if ev["frac_in_transit_quality_flagged"] > QUALITY_FLAG_FRACTION:
        reasons.append(f"{ev['frac_in_transit_quality_flagged']:.0%} of in-transit cadences quality-flagged")
    ramp = ev["baseline_change_across_event_over_depth"] > SAP_RAMP_OVER_DEPTH
    if (ramp and SAP_RAMP_NOISE_MULTIPLE is not None
            and ev.get("baseline_change_across_event_ppt") is not None
            and ev.get("sap_ramp_noise_threshold_ppt") is not None):
        ramp = ev["baseline_change_across_event_ppt"] > ev["sap_ramp_noise_threshold_ppt"]
    if ramp:
        reasons.append("SAP baseline changes by more than one depth across the event (ramp)")
    if (ev["bkg_change_across_window_over_median"] is not None
            and ev["bkg_change_across_window_over_median"] > BKG_CHANGE_OVER_MEDIAN
            and (ev["bkg_in_over_sector_median"] or 0) > BKG_OVER_SECTOR_MEDIAN):
        reasons.append("scattered-light ramp (background > 2 x sector median and doubling across the window)")
    if ev["frac_straylight_flagged_within_one_duration"] > STRAYLIGHT_FLAG_FRACTION:
        reasons.append(f"{ev['frac_straylight_flagged_within_one_duration']:.0%} of cadences within one "
                       f"duration carry the scattered-light flag")
    if ev["pdc_gap_within_one_duration"] and not ev["edge_within_one_duration"]:
        reasons.append(f"corrected flux has a PDC gap {pdc_dist:.2f} d away "
                       f"(event abuts a stretch PDC removed)")
    # the raw-SAP test itself: a dip that is significant in the corrected flux but absent in the SAP flux
    dd, de = ev.get("det_depth_ppt"), ev.get("det_depth_err_ppt")
    if (dd is not None and de and dd / de > SAP_ABSENT_MIN_SIGMA and not sap_is_pdc
            and ev["sap_depth_ppt"] < SAP_ABSENT_RATIO * dd):
        reasons.append(f"dip present in corrected flux ({dd:.2f} ppt) but not in SAP "
                       f"({ev['sap_depth_ppt']:.2f} +/- {ev['sap_depth_err_ppt']:.2f} ppt)")
    return reasons


def event_table(products: list[dict], t_det: np.ndarray, f_det: np.ndarray,
                period: float, t0: float, duration: float, ref_depth: float) -> list[dict]:
    """Every predicted epoch over the baseline the products span, measured."""
    t_min = min(p["t_start"] for p in products)
    t_max = max(p["t_end"] for p in products)
    events = []
    for n in predicted_epochs(t_min, t_max, period, t0):
        tc = t0 + n * period
        prods = [p for p in products if p["t_start"] - 0.25 <= tc <= p["t_end"] + 0.25]
        if not prods:
            events.append({"n": n, "tc_btjd": round(tc, 4), "tc_bjd": round(tc + 2457000.0, 4),
                           "observed": False, "reason": "no product covers the epoch"})
            continue
        events.append(measure_event(prods[0], tc, duration, ref_depth, t_det, f_det, n))
    return events


def weighted_mean(d: np.ndarray, e: np.ndarray) -> tuple[float, float]:
    """Inverse-variance weighted mean and its error."""
    w = 1.0 / np.maximum(e, 1e-12) ** 2
    return float(np.sum(w * d) / np.sum(w)), float(1.0 / math.sqrt(np.sum(w)))


def sector_beta(t: np.ndarray, f: np.ndarray, sector: np.ndarray, in_transit: np.ndarray,
                duration: float, cadence_by_sector: dict, beta_max: float = BETA_MAX) -> dict:
    """Per-sector red-noise beta from binned out-of-transit residuals.

    Prompt-7 option 2.  The recipe is the one already used by
    ``audit_p5.fit_step``: bin the out-of-transit residuals of a sector into
    bins of ``duration / 3``, compare their scatter with the white expectation
    ``sigma / sqrt(n_per_bin)``, and clip the ratio to [1, 5].  A sector with
    too little data gets beta 1.
    """
    out: dict[int, float] = {}
    for s in np.unique(sector):
        ms = sector == s
        r = f[ms & ~in_transit] - 1.0
        if r.size < 20:
            r = f[ms] - 1.0
        if r.size == 0:
            out[int(s)] = 1.0
            continue
        w = float(1.4826 * np.nanmedian(np.abs(r - np.nanmedian(r))))
        w = max(w, 1e-6)
        tt = t[ms & ~in_transit]
        beta = 1.0
        if tt.size > BETA_MIN_POINTS:
            cad_d = cadence_by_sector.get(int(s), 1800.0) / 86400.0
            nb = max(3, int(round(duration * BETA_BIN_DURATION_FRACTION / cad_d)))
            k = (tt.size // nb) * nb
            if k >= BETA_MIN_BINS * nb:
                rb = r[:k].reshape(-1, nb).mean(axis=1)
                exp = w / math.sqrt(nb)
                beta = float(np.std(rb) / exp) if exp > 0 else 1.0
        out[int(s)] = float(np.clip(beta, BETA_MIN, beta_max))
    return out


def kept_event_stats(events: list[dict], kind: str, beta_by_sector: dict | None = None,
                     gate_errors: str = "inflated") -> dict:
    """Weighted depth, SNR, top-event share, leave-one-out SNR, chi-square
    consistency and odd/even over a list of events.

    ``kind`` is ``"det"`` (the detrended corrected flux) or ``"sap"``.
    ``beta_by_sector`` (prompt-7 option 2) multiplies each event's error by its
    sector's red-noise beta before the chi-square; the white statistics are
    returned alongside under ``*_white`` keys so both are on the record.
    """
    evs = [e for e in events if e.get(f"{kind}_depth_ppt") is not None]
    if not evs:
        return {"n": 0}
    d = np.array([e[f"{kind}_depth_ppt"] for e in evs])
    s = np.array([e[f"{kind}_depth_err_ppt"] for e in evs])
    mean, err = weighted_mean(d, s)
    chi2 = float(np.sum(((d - mean) / s) ** 2))
    dof = max(1, len(d) - 1)
    contrib = (d / s) ** 2 * np.sign(d)
    pos = np.clip(contrib, 0, None)
    top = int(np.argmax(pos)) if len(pos) else None
    loo = None
    if len(d) > 1:
        m = np.ones(len(d), bool)
        m[top] = False
        mean2, err2 = weighted_mean(d[m], s[m])
        loo = mean2 / err2
    odd = [i for i, e in enumerate(evs) if e["n"] % 2]
    even = [i for i, e in enumerate(evs) if not e["n"] % 2]
    oe = None
    if odd and even:
        mo, eo = weighted_mean(d[odd], s[odd])
        me, ee = weighted_mean(d[even], s[even])
        oe = {"odd_ppt": round(mo, 3), "odd_err": round(eo, 3), "even_ppt": round(me, 3),
              "even_err": round(ee, 3), "sigma": round(abs(mo - me) / math.sqrt(eo ** 2 + ee ** 2), 2)}
    from scipy import stats as sst
    out = {"n": len(d), "weighted_mean_depth_ppt": round(mean, 3), "err_ppt": round(err, 3),
           "snr": round(mean / err, 2), "chi2_const": round(chi2, 1), "dof": dof,
           "p_const": float(sst.chi2.sf(chi2, dof)),
           "top_event_n": int(evs[top]["n"]) if top is not None else None,
           "top_event_share_of_snr2": round(float(pos[top] / pos.sum()), 2) if pos.sum() > 0 else None,
           "snr_without_top_event": round(float(loo), 2) if loo is not None else None,
           "n_events_depth_above_2sigma": int(np.sum(d / s > 2)),
           "n_events_negative": int(np.sum(d < 0)), "odd_even": oe}
    if beta_by_sector:
        beta = np.array([float(beta_by_sector.get(int(e.get("sector", -1)), 1.0)) for e in evs])
        s_inf = s * beta
        mean_i, err_i = weighted_mean(d, s_inf)
        chi2_i = float(np.sum(((d - mean_i) / s_inf) ** 2))
        out.update({
            "p_const_white": out["p_const"], "chi2_const_white": out["chi2_const"],
            "snr_white": out["snr"],
            "beta_median": round(float(np.median(beta)), 3),
            "beta_min": round(float(beta.min()), 3), "beta_max": round(float(beta.max()), 3),
            "weighted_mean_depth_ppt_inflated": round(mean_i, 3),
            "err_ppt_inflated": round(err_i, 3), "snr_inflated": round(mean_i / err_i, 2),
            "chi2_const_inflated": round(chi2_i, 1),
            "p_const_inflated": float(sst.chi2.sf(chi2_i, dof)),
        })
        # which p-value the gate reads (prompt-8 decision 2): p7.0 reads the inflated one
        out["p_const"] = out["p_const_inflated"] if gate_errors == "inflated" else out["p_const_white"]
        if gate_errors != "inflated":
            out["p_const_gate_errors"] = gate_errors
    if DEPTH_CONSISTENCY_FAMILIES is not None:
        # [K2] A1: the same errors the gate reads (inflated when the K1 gate reads the inflated p-value)
        s_gate = s * beta if (beta_by_sector and gate_errors == "inflated") else s
        out["a1"] = {sc: depth_families(evs, d, s_gate, sc) for sc in A1_SCOPES}
    return out


def depth_family(event: dict, scope: str) -> str:
    """[K2] A1: the product family of one event (``author``) or family x exposure class (``author_exposure``)."""
    fam = "QLP" if str(event.get("author")) == "QLP" else "SPOC"
    if scope == "author":
        return fam
    cad = float(event.get("cadence_s") or 0.0)
    return f"{fam}_{int(min(A1_EXPOSURE_GRID_S, key=lambda g: abs(g - cad)))}"


def depth_families(evs: list[dict], d: np.ndarray, s: np.ndarray, scope: str) -> dict:
    """[K2] A1: the within-family chi-square of the per-event depths and every family's mean against the
    dominant family (largest total weight).  ``d`` / ``s`` are the depths and the errors the gate reads."""
    from scipy import stats as sst
    keys = [depth_family(e, scope) for e in evs]
    fam = {}
    for k in sorted(set(keys)):
        m = np.array([kk == k for kk in keys])
        mean, err = weighted_mean(d[m], s[m])
        fam[k] = {"n": int(m.sum()), "mean_ppt": mean, "err_ppt": err,
                  "chi2": float(np.sum(((d[m] - mean) / s[m]) ** 2)),
                  "weight": float(np.sum(1.0 / np.maximum(s[m], 1e-12) ** 2))}
    chi2w = float(sum(f["chi2"] for f in fam.values()))
    dofw = int(sum(f["n"] - 1 for f in fam.values()))
    pw = float(sst.chi2.sf(chi2w, dofw)) if dofw > 0 else 1.0
    dom = max(fam, key=lambda k: fam[k]["weight"])
    md, ed = fam[dom]["mean_ppt"], fam[dom]["err_ppt"]
    agree = bool(md > 0)
    for k, f in fam.items():
        ratio = f["mean_ppt"] / md if md > 0 else None
        ok = bool(k == dom or (ratio is not None and A1_RATIO_LO <= ratio <= A1_RATIO_HI)
                  or abs(f["mean_ppt"] - md) <= A1_MEAN_SIGMA * math.sqrt(f["err_ppt"] ** 2 + ed ** 2))
        f.update(ratio_to_dominant=None if ratio is None else round(ratio, 4), agrees=ok,
                 mean_ppt=round(f["mean_ppt"], 4), err_ppt=round(f["err_ppt"], 4), chi2=round(f["chi2"], 2))
        f.pop("weight")
        agree = agree and ok
    return {"scope": scope, "families": fam, "dominant": dom, "chi2_within": round(chi2w, 2),
            "dof_within": dofw, "p_within": pw, "means_agree": bool(agree)}


def advisory_flags(det_kept: dict, n_observed: int, n_excluded: int) -> list[str]:
    """The ``events`` step's own advisory flags (never a Stage A criterion)."""
    flags = []
    if det_kept.get("n", 0) and det_kept.get("snr", 0) < EVENTS_FLAG_MIN_SNR:
        flags.append("SNR of kept events (detrended) < 7")
    if det_kept.get("top_event_share_of_snr2") is not None and det_kept["top_event_share_of_snr2"] > 0.5:
        flags.append("one event carries > 50% of the signal")
    if det_kept.get("snr_without_top_event") is not None and det_kept["snr_without_top_event"] < 7:
        flags.append("SNR < 7 without the strongest event")
    if det_kept.get("p_const") is not None and det_kept["p_const"] < 0.001 and det_kept.get("n", 0) >= 3:
        flags.append("per-event depths inconsistent with a constant (p < 0.001)")
    if n_observed and n_excluded / n_observed > EVENTS_FLAG_EXCLUDED_FRACTION:
        flags.append("more than half of the observed events coincide with dumps/edges/ramps")
    return flags


def summarise_events(events: list[dict], ephemeris: dict,
                     beta_by_sector: dict | None = None, gate_errors: str = "inflated") -> dict:
    """The ``summary`` block of an ``events`` record."""
    obs = [e for e in events if e.get("observed")]
    kept = [e for e in obs if not e["excluded"]]
    summary = {
        "ephemeris": ephemeris, "n_predicted_in_span": len(events), "n_observed": len(obs),
        "n_excluded": len(obs) - len(kept), "n_kept": len(kept),
        "exclusion_reasons": {r: sum(r.split(" ")[0] in " ".join(e["exclusion_reasons"]) for e in obs)
                              for r in ["momentum", "sector/orbit", "quality-flagged", "SAP",
                                        "scattered-light", "manual-exclude"]},
        "sap_all": kept_event_stats(obs, "sap", beta_by_sector, gate_errors),
        "sap_kept": kept_event_stats(kept, "sap", beta_by_sector, gate_errors),
        "det_all": kept_event_stats(obs, "det", beta_by_sector, gate_errors),
        "det_kept": kept_event_stats(kept, "det", beta_by_sector, gate_errors),
    }
    summary["flags"] = advisory_flags(summary["det_kept"], summary["n_observed"], summary["n_excluded"])
    return summary


def stagea_criteria(det_kept: dict, survey_depth_ppt: float, p_min: float = A_P_CONST) -> dict:
    """The six Stage A criteria, evaluated on one ephemeris' kept-event statistics.

    All six must hold for a candidate to pass.  ``det_kept`` is the ``det_kept``
    block of an events summary; ``survey_depth_ppt`` the depth the survey
    reported, which the kept depth is measured against.  When the
    ``inflated_depth_consistency`` option produced the statistics, ``p_const``
    is already the red-noise-inflated p-value, so the gate uses it.
    """
    n = det_kept.get("n", 0) or 0
    snr = det_kept.get("snr")
    share = det_kept.get("top_event_share_of_snr2")
    wo = det_kept.get("snr_without_top_event")
    depth = det_kept.get("weighted_mean_depth_ppt")
    pc = det_kept.get("p_const")
    ratio = (depth / survey_depth_ppt) if (depth is not None and survey_depth_ppt) else None
    crit = {
        "kept_events_ge_3": bool(n >= A_MIN_KEPT),
        "kept_snr_ge_7": bool(snr is not None and snr >= A_MIN_SNR),
        "top_share_le_50pct": bool(share is not None and share <= A_MAX_TOP_SHARE),
        "snr_without_top_ge_5": bool(wo is not None and wo >= A_MIN_SNR_WO_TOP),
        "depth_within_0.5_2x_survey": bool(ratio is not None and A_DEPTH_LO <= ratio <= A_DEPTH_HI),
        "depths_consistent_p_ge_1e-3": bool(pc is not None and pc >= p_min),
    }
    a1 = None
    if DEPTH_CONSISTENCY_FAMILIES is not None:
        # [K2] A1: a monotone relaxation; the K1 test still passes on its own
        blk = (det_kept.get("a1") or {}).get(DEPTH_CONSISTENCY_FAMILIES) or {}
        pw = blk.get("p_within")
        k1_ok = crit["depths_consistent_p_ge_1e-3"]
        rescued = bool(not k1_ok and pw is not None and pw >= p_min and blk.get("means_agree"))
        a1 = {"scope": DEPTH_CONSISTENCY_FAMILIES, "k1_consistent": k1_ok, "p_within": pw,
              "means_agree": blk.get("means_agree"), "rescued": rescued}
        crit["depths_consistent_p_ge_1e-3"] = bool(k1_ok or rescued)
    out = {"criteria": crit, "n_criteria_passed": int(sum(crit.values())),
           "all_passed": bool(all(crit.values())), "n_kept": n, "kept_snr": snr,
           "top_event_share": share, "snr_without_top": wo, "kept_depth_ppt": depth,
           "kept_depth_err_ppt": det_kept.get("err_ppt"),
           "depth_over_survey_depth": None if ratio is None else round(ratio, 3), "p_const": pc,
           "top_event_n": det_kept.get("top_event_n")}
    if a1 is not None:
        out["depth_consistency_a1"] = a1
    return out
