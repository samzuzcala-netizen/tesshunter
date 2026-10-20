"""Submission packet for one survivor (prompt 3, part D).

One directory per candidate with

* ``packet.md`` — a one-page data-validation style summary;
* ``summary.png`` — nine panels: full light curve with transits marked,
  folded curve with the fitted model, odd/even overlay, secondary-eclipse
  window, per-unit folds, per-transit depths, centroid offset, nearby stars
  within one arcminute, and the parameter / FPP / completeness text;
* ``ctoi_fields.json`` — the fields the ExoFOP CTOI form asks for, filled
  from the fit, plus supplementary parameters and provenance;
* ``fit.json``, ``fpp.json``, ``vetting.json``, ``neighbours.csv`` — the raw
  inputs, so nothing in the page is unreproducible.

The pipeline finds candidates; nothing here is a detection, and nothing here
submits anything. The human fills the tag and presses the button.

The ExoFOP CTOI form fields were taken from the ExoFOP-TESS candidate
guidelines page (``/tess/candidate_help.php``, read 2026-09-02): TID name,
discovery source, period, transit midpoint (BJD), depth (ppm), duration, tag,
paper URL and an initial note are asked for, candidate name and disposition
(PC / FP) are optional, and for consideration by the TOI working group all
four of period, epoch, depth and duration must be present and positive. The
bulk-upload column list sits behind a login and was not reproduced.
"""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .config import OUTPUTS_DIR, PROJECT_ROOT
from .stellar import StellarParams, fetch_tic_neighbours
from .utils import ensure_dirs, safe_dirname

logger = logging.getLogger(__name__)

PACKETS_DIR = OUTPUTS_DIR / "packets"
COMPLETENESS_JSON = PROJECT_ROOT / "data" / "survey" / "completeness_v1.json"
COMPLETENESS_DOC = "docs/COMPLETENESS.md"
BTJD_OFFSET = 2457000.0
TESS_PIXEL_ARCSEC = 21.0
GAP_SPLIT_DAYS = 1.0

#: Field order of ``ctoi_fields.json["form_fields"]``.
CTOI_FORM_FIELDS = [
    "target", "tic_id", "discovery_source", "period_days", "period_err_days",
    "epoch_bjd", "epoch_err_days", "depth_ppm", "depth_err_ppm",
    "duration_hours", "duration_err_hours", "disposition", "tag",
    "candidate_name", "paper_url", "notes",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_dict(obj) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    try:
        from dataclasses import asdict, is_dataclass
        if is_dataclass(obj):
            return asdict(obj)
    except Exception:                                             # pragma: no cover
        pass
    return dict(getattr(obj, "__dict__", {}))


def _fmt(v, fmt=".4f", unit=""):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    try:
        return f"{float(v):{fmt}}{(' ' + unit) if unit else ''}"
    except (TypeError, ValueError):
        return str(v)


def _pm(v, e, fmt=".4f", unit=""):
    if v is None:
        return "n/a"
    if e is None or not np.isfinite(e) or e <= 0:
        return _fmt(v, fmt, unit)
    return f"{float(v):{fmt}} +/- {float(e):{fmt}}{(' ' + unit) if unit else ''}"


def _bin(x, y, n_bins):
    """Median-bin y on x into n_bins equal bins; returns centres, medians, errors."""
    if x.size == 0:
        return np.array([]), np.array([]), np.array([])
    edges = np.linspace(x.min(), x.max(), n_bins + 1)
    idx = np.clip(np.digitize(x, edges) - 1, 0, n_bins - 1)
    cx, cy, ce = [], [], []
    for b in range(n_bins):
        m = idx == b
        if m.sum() >= 2:
            cx.append(0.5 * (edges[b] + edges[b + 1]))
            cy.append(float(np.median(y[m])))
            ce.append(1.4826 * float(np.median(np.abs(y[m] - np.median(y[m])))) / math.sqrt(m.sum()))
    return np.asarray(cx), np.asarray(cy), np.asarray(ce)


def _fold_days(t, period, t0):
    return ((t - t0 + 0.5 * period) % period) - 0.5 * period


def _model_curve(fit: dict, phase_days: np.ndarray, exp_time_days: Optional[float] = None) -> Optional[np.ndarray]:
    try:
        from .survey import transit_model
        return transit_model(
            phase_days + float(fit["t0"]), period=float(fit["period"]), t0=float(fit["t0"]),
            rp_rs=float(fit["rp_rs"]), b=float(fit["b"]), a_rs=float(fit["a_rs"]),
            u=(float(fit["u1"]), float(fit["u2"])), exp_time_days=exp_time_days,
        ) * float(fit.get("f0", 1.0))
    except Exception as exc:                                      # pragma: no cover
        logger.debug("model curve failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Completeness at this SNR
# ---------------------------------------------------------------------------

def matched_filter_snr(time_days, flux, fit: dict, bin_minutes: float = 30.0) -> dict:
    """Matched-filter SNR of the fitted model on the binned, detrended curve.

    Same definition as the completeness measurement (``docs/COMPLETENESS.md``):
    the model is evaluated on the binned time grid, sigma is 1.4826 x MAD of
    the binned residuals, and SNR = sqrt(sum(delta^2)) / sigma.
    """
    t = np.asarray(time_days, dtype=float)
    f = np.asarray(flux, dtype=float)
    ok = np.isfinite(t) & np.isfinite(f)
    t, f = t[ok], f[ok]
    if t.size < 10:
        return {"available": False}
    w = bin_minutes / 1440.0
    edges = np.arange(t.min(), t.max() + w, w)
    idx = np.digitize(t, edges) - 1
    n = np.bincount(idx, minlength=edges.size)
    s = np.bincount(idx, weights=f, minlength=edges.size)
    st = np.bincount(idx, weights=t, minlength=edges.size)
    keep = n >= 1
    bt, bf = st[keep] / n[keep], s[keep] / n[keep]
    model = _model_curve(fit, bt - float(fit["t0"]), exp_time_days=w)
    if model is None:
        return {"available": False}
    delta = 1.0 - model / float(fit.get("f0", 1.0))
    resid = bf - np.median(bf)
    sigma = 1.4826 * float(np.median(np.abs(resid)))
    in_tr = delta > 0
    n_in = int(in_tr.sum())
    snr = float(np.sqrt(np.sum(delta[in_tr] ** 2)) / sigma) if n_in and sigma > 0 else 0.0
    return {"available": True, "snr": snr, "sigma_bin": sigma, "n_in_bins": n_in, "bin_minutes": bin_minutes}


def completeness_at_snr(snr: Optional[float], path: Path = COMPLETENESS_JSON) -> dict:
    """Recovery fraction the P2 completeness measurement predicts at ``snr``."""
    out = {"available": False, "snr": snr, "source": str(path.relative_to(PROJECT_ROOT)) if path.exists() else str(path)}
    if snr is None or not path.exists():
        return out
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        inj = d["injections"]
        lg = inj["logistic_all"]
        a, b = float(lg["a"]), float(lg["b"])
        p = 1.0 / (1.0 + math.exp(-(a + b * math.log(max(snr, 1e-3)))))
        bin_row = None
        for row in inj.get("by_snr", []):
            if row["lo"] <= snr < row["hi"]:
                bin_row = row
                break
        out.update({
            "available": True, "logistic_recovery": p, "snr50": lg.get("snr50"), "snr90": lg.get("snr90"),
            "bin": bin_row, "config": d.get("config"), "n_injections": inj.get("n_total"),
            "sample_size_stars": d.get("sample_size_stars"), "generated_utc": d.get("generated_utc"),
            "note": (
                "Curve measured in P2 with batman injections into the survey preset "
                f"({d.get('config')}: FFI stitches binned to 30 min, periods 1-40 d, Rp/R* 0.01-0.12); "
                "the matched-filter SNR here is computed on this candidate's own detrended data with the "
                "same definition. Outside that regime the number is an extrapolation."
            ),
        })
    except Exception as exc:                                      # pragma: no cover
        out["error"] = str(exc)
    return out


# ---------------------------------------------------------------------------
# CTOI fields
# ---------------------------------------------------------------------------

def ctoi_fields(
    tic_id: int,
    fit: dict,
    *,
    candidate: dict,
    vet: dict,
    fpp: dict,
    stellar: dict,
    sectors: list,
    crossmatch: dict,
    tag: Optional[str],
    notes: Optional[str],
    packet_dir: Path,
) -> dict:
    period = fit.get("period") or candidate.get("period_days")
    t0 = fit.get("t0") if fit.get("t0") is not None else candidate.get("epoch_btjd")
    depth_ppt = fit.get("depth_ppt") or candidate.get("depth_ppt")
    dur = fit.get("duration_days") or candidate.get("duration_days")
    auto_note = (
        f"tesshunter candidate on TIC {tic_id}: P = {_fmt(period, '.5f')} d, depth = "
        f"{_fmt(depth_ppt * 1000 if depth_ppt else None, '.0f')} ppm, T14 = {_fmt(dur * 24 if dur else None, '.2f')} h, "
        f"SNR {_fmt(candidate.get('snr'), '.1f')}, {fit.get('n_transits', candidate.get('n_transits_observed'))} transits "
        f"in sectors {','.join(str(s) for s in sectors)}. Limb-darkened fit: Rp/R* = "
        f"{_fmt(fit.get('rp_rs'), '.4f')}, a/R* = {_fmt(fit.get('a_rs'), '.2f')} (catalog {_fmt(fit.get('a_rs_star'), '.2f')}), "
        f"b = {_fmt(fit.get('b'), '.2f')}; Rp = {_fmt(fit.get('rp_rearth'), '.2f')} R_Earth. "
        f"TRICERATOPS FPP = {_fmt(fpp.get('fpp'), '.3f')}, NFPP = {_fmt(fpp.get('nfpp'), '.3f')}. "
        f"Automated verdict: {vet.get('verdict')}. Cross-match: {crossmatch.get('summary', 'not attempted')}."
    )
    form = {
        "target": f"TIC {tic_id}",
        "tic_id": int(tic_id),
        "discovery_source": "TESS",
        "period_days": period,
        "period_err_days": fit.get("period_err"),
        "epoch_bjd": (t0 + BTJD_OFFSET) if t0 is not None else None,
        "epoch_err_days": fit.get("t0_err"),
        "depth_ppm": depth_ppt * 1000.0 if depth_ppt else None,
        "depth_err_ppm": (fit.get("depth_err") or 0.0) * 1000.0 if fit.get("depth_err") is not None else None,
        "duration_hours": dur * 24.0 if dur else None,
        "duration_err_hours": (fit.get("duration_err") or 0.0) * 24.0 if fit.get("duration_err") is not None else None,
        "disposition": "PC",
        "tag": tag or "FILL_ME: YYYYMMDD_username_tesshunter_NNN",
        "candidate_name": None,
        "paper_url": None,
        "notes": notes or auto_note,
    }
    form = {k: form[k] for k in CTOI_FORM_FIELDS}
    supplementary = {
        "rp_rs": fit.get("rp_rs"), "rp_rs_err": fit.get("rp_rs_err"),
        "rp_rearth": fit.get("rp_rearth"), "rp_rearth_err": fit.get("rp_rearth_err"),
        "rp_rjup": fit.get("rp_rjup"), "rp_rjup_err": fit.get("rp_rjup_err"),
        "a_rs": fit.get("a_rs"), "a_rs_err": fit.get("a_rs_err"), "a_rs_catalog": fit.get("a_rs_star"),
        "impact_parameter": fit.get("b"), "impact_parameter_err": fit.get("b_err"),
        "inclination_deg": fit.get("inc_deg"),
        "depth_duration_averaged_ppm": (fit.get("depth_mean_ppt") or 0.0) * 1000.0 if fit.get("depth_mean_ppt") else None,
        "stellar_density_fit_cgs": fit.get("rho_star_fit_cgs"), "stellar_density_catalog_cgs": fit.get("rho_star_cat_cgs"),
        "density_prior_adopted": fit.get("density_prior_adopted"), "a_rs_inconsistent": fit.get("a_rs_inconsistent"),
        "snr_bls": candidate.get("snr"), "n_transits": fit.get("n_transits", candidate.get("n_transits_observed")),
        "fpp": fpp.get("fpp"), "nfpp": fpp.get("nfpp"), "fpp_aperture": fpp.get("aperture_source"),
        "verdict": vet.get("verdict"), "flags_hard": vet.get("flags_hard"), "flags_high": vet.get("flags_high"),
        "flags_medium": vet.get("flags_medium"), "sectors": list(sectors),
        "stellar": {k: stellar.get(k) for k in ("teff", "logg", "radius", "radius_err", "mass", "mass_err",
                                                "rho", "tmag", "contamination_ratio", "source")},
    }
    return {
        "form_fields": form,
        "supplementary": supplementary,
        "provenance": {
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "fit_method": fit.get("method"), "limb_darkening": fit.get("ld_source"),
            "catalog_versions": crossmatch.get("catalog_versions"), "crossmatch_status": crossmatch.get("status"),
            "packet_dir": str(packet_dir),
        },
        "field_source": (
            "ExoFOP-TESS candidate guidelines (candidate_help.php, read 2026-09-02): TID name, discovery "
            "source, period, transit midpoint (BJD), depth (ppm), duration, tag, paper URL, initial note; "
            "optional candidate name and disposition (PC/FP). Period, epoch, depth and duration must all be "
            "> 0 for TOI working-group consideration. The human fills the tag and submits."
        ),
    }


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------

def _figure(
    path: Path, *, label: str, t: np.ndarray, f: np.ndarray, fit: dict, candidate: dict, vet: dict,
    stellar: dict, fpp: dict, completeness: dict, centroid: dict, neighbours: Optional[pd.DataFrame],
    contamination: dict, crossmatch: dict, sectors: list,
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    period = float(fit.get("period") or candidate["period_days"])
    t0 = float(fit.get("t0") if fit.get("t0") is not None else candidate["epoch_btjd"])
    dur = float(fit.get("duration_days") or candidate["duration_days"] or 0.1)
    cad = float(np.median(np.diff(np.sort(t)))) if t.size > 1 else 2.0 / 1440.0
    have_fit = bool(fit.get("success"))

    fig, axes = plt.subplots(3, 3, figsize=(17, 14))
    fig.suptitle(f"{label}: candidate at P = {period:.5f} d  |  {vet.get('verdict', '')}", fontsize=13)

    # 1. full light curve with transits marked
    ax = axes[0, 0]
    ax.plot(t, f, ".", ms=1.5, color="0.4", alpha=0.6)
    n0, n1 = int(np.floor((t.min() - t0) / period)), int(np.ceil((t.max() - t0) / period))
    tt = t0 + period * np.arange(n0, n1 + 1)
    tt = tt[(tt >= t.min()) & (tt <= t.max())]
    ylo = np.nanpercentile(f, 0.5)
    ax.plot(tt, np.full(tt.size, ylo), "|", color="tab:red", ms=12, mew=1.5)
    ax.set_title(f"Detrended light curve ({tt.size} predicted transits marked)")
    ax.set_xlabel("BTJD"); ax.set_ylabel("flux")

    # 2. folded with model
    ax = axes[0, 1]
    ph = _fold_days(t, period, t0)
    win = min(3.0 * dur, 0.45 * period)
    m = np.abs(ph) <= win
    ax.plot(ph[m] * 24, f[m], ".", ms=2, color="0.6", alpha=0.5)
    bx, by, be = _bin(ph[m], f[m], 41)
    ax.errorbar(bx * 24, by, be, fmt="o", ms=4, color="k")
    if have_fit:
        grid = np.linspace(-win, win, 400)
        mod = _model_curve(fit, grid, exp_time_days=cad)
        if mod is not None:
            ax.plot(grid * 24, mod, "-", color="tab:red", lw=1.5, label="limb-darkened fit")
            ax.legend(loc="lower right", fontsize=8)
    ax.set_title(f"Folded; depth {_fmt(fit.get('depth_ppt', candidate.get('depth_ppt')), '.3f')} ppt, T14 {dur * 24:.2f} h")
    ax.set_xlabel("hours from mid-transit"); ax.set_ylabel("flux")

    # 3. odd/even overlay
    ax = axes[0, 2]
    idx = np.round((t - t0) / period).astype(int)
    for par, col, name in ((1, "tab:blue", "odd"), (0, "tab:orange", "even")):
        mm = m & (np.abs(idx) % 2 == par)
        bx, by, be = _bin(ph[mm], f[mm], 31)
        ax.errorbar(bx * 24, by, be, fmt="o", ms=4, color=col, label=name, alpha=0.8)
    oe = fit.get("odd_even") or {}
    ax.set_title("Odd / even: " + (f"{_fmt(oe.get('depth_odd_ppt'), '.3f')} vs {_fmt(oe.get('depth_even_ppt'), '.3f')} ppt "
                                   f"({_fmt(oe.get('delta_sigma'), '.1f')} sigma)" if oe.get("available") else "n/a"))
    ax.legend(fontsize=8); ax.set_xlabel("hours from mid-transit")

    # 4. secondary window
    ax = axes[1, 0]
    ph2 = _fold_days(t, period, t0 + 0.5 * period)
    m2 = np.abs(ph2) <= win
    ax.plot(ph2[m2] * 24, f[m2], ".", ms=2, color="0.6", alpha=0.5)
    bx, by, be = _bin(ph2[m2], f[m2], 41)
    ax.errorbar(bx * 24, by, be, fmt="o", ms=4, color="k")
    sec = vet.get("result", vet) or {}
    sec_ppt = sec.get("secondary_depth_ppt")
    bound = sec.get("secondary_planet_bound_ppt")
    ttl = f"Phase 0.5: measured {_fmt(sec_ppt, '.3f')} ppt"
    if bound is not None:
        ttl += f"; planet bound {_fmt(bound, '.4f')} ppt"
        ax.axhline(1.0 - bound / 1000.0, color="tab:green", ls="--", lw=1, label="deepest planetary secondary")
        ax.legend(fontsize=8, loc="lower right")
    ax.set_title(ttl + (" [stellar]" if sec.get("secondary_is_stellar") else ""))
    ax.set_xlabel("hours from phase 0.5")

    # 5. per-unit folds
    ax = axes[1, 1]
    order = np.argsort(t)
    ts, fs = t[order], f[order]
    gaps = np.where(np.diff(ts) > GAP_SPLIT_DAYS)[0]
    starts = np.concatenate([[0], gaps + 1]); ends = np.concatenate([gaps + 1, [ts.size]])
    units = [(s, e) for s, e in zip(starts, ends) if e - s > 50]
    offset = 0.0
    step = max(3.0 * float(fit.get("depth_ppt", candidate.get("depth_ppt", 1.0)) or 1.0) / 1000.0, 5e-4)
    for k, (s, e) in enumerate(units[:8]):
        phu = _fold_days(ts[s:e], period, t0)
        mu = np.abs(phu) <= win
        bx, by, be = _bin(phu[mu], fs[s:e][mu], 25)
        if bx.size:
            ax.errorbar(bx * 24, by - offset, be, fmt="o", ms=3, label=f"unit {k + 1} (BTJD {ts[s]:.0f}-{ts[e - 1]:.0f})")
        offset += step
    ax.set_title(f"Per-unit folds ({len(units)} units, offset for clarity)")
    ax.set_xlabel("hours from mid-transit"); ax.legend(fontsize=7, loc="lower right")

    # 6. per-transit depths
    ax = axes[1, 2]
    pe = oe.get("per_event") or []
    if pe:
        xs = [p["index"] for p in pe]; ys = [p["depth_ppt"] for p in pe]; es = [p["depth_err"] for p in pe]
        ax.errorbar(xs, ys, es, fmt="o", color="k")
        ax.axhline(float(fit.get("depth_ppt", 0.0)), color="tab:red", lw=1)
        ax.set_title(f"Per-transit depth from the template ({len(pe)} events)")
        ax.set_xlabel("transit index"); ax.set_ylabel("depth (ppt)")
    else:
        ax.text(0.5, 0.5, "per-transit depths n/a", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()

    # 7. centroid
    ax = axes[2, 0]
    if centroid.get("available"):
        dc, dr = float(centroid.get("col_shift_px", 0)), float(centroid.get("row_shift_px", 0))
        err = float(centroid.get("shift_err_px", 0) or 0)
        ax.axhline(0, color="0.7", lw=0.8); ax.axvline(0, color="0.7", lw=0.8)
        ax.errorbar([dc], [dr], xerr=[err], yerr=[err], fmt="o", color="tab:red", ms=6)
        circ = plt.Circle((0, 0), 1.0, fill=False, ls="--", color="0.5")
        ax.add_patch(circ)
        lim = max(1.2, 3 * abs(dc), 3 * abs(dr), 3 * err)
        ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_aspect("equal")
        ax.set_title(f"In-transit centroid shift: {float(centroid.get('total_shift_px', 0)):.3f} px "
                     f"({float(centroid.get('shift_arcsec', 0)):.1f} arcsec, {float(centroid.get('sigma', 0)):.1f} sigma)"
                     + (" FLAGGED" if centroid.get("flagged") else ""))
        ax.set_xlabel("column shift (px)"); ax.set_ylabel("row shift (px)")
    else:
        ax.text(0.5, 0.5, "centroid check not run / not available\n" + str(centroid.get("note", ""))[:80],
                ha="center", va="center", transform=ax.transAxes, fontsize=9)
        ax.set_axis_off()

    # 8. nearby stars within 1 arcmin
    ax = axes[2, 1]
    if neighbours is not None and len(neighbours):
        nb = neighbours.copy()
        tgt = nb[nb.get("is_target", False) == True] if "is_target" in nb.columns else nb.iloc[[0]]
        ra0 = float(tgt["ra"].iloc[0]) if len(tgt) else float(nb["ra"].iloc[0])
        dec0 = float(tgt["dec"].iloc[0]) if len(tgt) else float(nb["dec"].iloc[0])
        dx = (nb["ra"].astype(float) - ra0) * 3600.0 * math.cos(math.radians(dec0))
        dy = (nb["dec"].astype(float) - dec0) * 3600.0
        tm = nb["Tmag"].astype(float)
        tm0 = float(tgt["Tmag"].iloc[0]) if len(tgt) else float(tm.min())
        size = 20 + 200 * 10 ** (-0.4 * (tm - tm0)).clip(0, 1)
        ax.scatter(-dx, dy, s=size, color="tab:blue", alpha=0.6, edgecolor="k")
        for x, y, m_, g in zip(-dx, dy, tm, nb.get("GAIAmag", pd.Series([np.nan] * len(nb)))):
            ax.annotate(f"T{m_:.1f}" + (f"/G{g:.1f}" if g == g else ""), (x, y), fontsize=6, xytext=(3, 3),
                        textcoords="offset points")
        r_ap = contamination.get("aperture_radius_px") or 1.5
        ax.add_patch(plt.Circle((0, 0), float(r_ap) * TESS_PIXEL_ARCSEC, fill=False, ls="--", color="tab:red"))
        ax.set_xlim(-65, 65); ax.set_ylim(-65, 65); ax.set_aspect("equal")
        ax.set_title(f"TIC stars within 60 arcsec ({len(nb)}); TIC contamination ratio "
                     f"{_fmt(stellar.get('contamination_ratio'), '.4f')}")
        ax.set_xlabel("east offset (arcsec)"); ax.set_ylabel("north offset (arcsec)")
    else:
        ax.text(0.5, 0.5, "neighbour query not available", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()

    # 9. text
    ax = axes[2, 2]
    ax.set_axis_off()
    lines = [
        f"Rp/R* = {_pm(fit.get('rp_rs'), fit.get('rp_rs_err'), '.4f')}",
        f"a/R*  = {_pm(fit.get('a_rs'), fit.get('a_rs_err'), '.2f')}  (catalog {_fmt(fit.get('a_rs_star'), '.2f')})",
        f"b     = {_pm(fit.get('b'), fit.get('b_err'), '.2f')}   i = {_fmt(fit.get('inc_deg'), '.2f')} deg",
        f"P     = {_pm(fit.get('period'), fit.get('period_err'), '.6f')} d",
        f"T0    = {_pm(fit.get('t0'), fit.get('t0_err'), '.5f')} BTJD",
        f"T14   = {_pm((fit.get('duration_days') or 0) * 24, (fit.get('duration_err') or 0) * 24, '.3f')} h",
        f"depth = {_pm(fit.get('depth_ppt'), fit.get('depth_err'), '.4f')} ppt (max); mean {_fmt(fit.get('depth_mean_ppt'), '.4f')} ppt",
        f"Rp    = {_pm(fit.get('rp_rearth'), fit.get('rp_rearth_err'), '.2f')} R_Earth = {_fmt(fit.get('rp_rjup'), '.3f')} R_Jup",
        f"rho*  = {_fmt(fit.get('rho_star_fit_cgs'), '.3f')} (fit, free) vs {_fmt(fit.get('rho_star_cat_cgs'), '.3f')} g/cc (catalog)",
        f"density profile dchi2 = {_fmt(fit.get('density_dchi2'), '.1f')}; prior adopted: {fit.get('density_prior_adopted')}; "
        f"inconsistent: {fit.get('a_rs_inconsistent')}",
        f"LD: {fit.get('ld_source', '')}",
        f"BLS SNR {_fmt(candidate.get('snr'), '.1f')}; transits {fit.get('n_transits', candidate.get('n_transits_observed'))}; sectors {sectors}",
        f"FPP = {_fmt(fpp.get('fpp'), '.4f')}   NFPP = {_fmt(fpp.get('nfpp'), '.4f')}   ({fpp.get('aperture_source', 'n/a')})",
        f"matched-filter SNR {_fmt(completeness.get('snr'), '.1f')} -> completeness {_fmt(completeness.get('logistic_recovery'), '.2f')}"
        f" (SNR50 {_fmt(completeness.get('snr50'), '.1f')}, SNR90 {_fmt(completeness.get('snr90'), '.1f')})",
        f"verdict: {vet.get('verdict')}",
        "high: " + "; ".join(vet.get("flags_high") or [])[:150],
        "hard: " + "; ".join(vet.get("flags_hard") or [])[:150],
        f"cross-match: {str(crossmatch.get('summary', 'not attempted'))[:90]}",
    ]
    ax.text(0.0, 1.0, "\n".join(lines), va="top", ha="left", fontsize=8, family="monospace", transform=ax.transAxes)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Packet
# ---------------------------------------------------------------------------

def build_packet(
    *,
    result,
    planet_num: int,
    lc_clean=None,
    stellar=None,
    fpp=None,
    centroid=None,
    contamination=None,
    neighbours: Optional[pd.DataFrame] = None,
    fetch_neighbours: bool = True,
    out_dir: Optional[Path] = None,
    label: Optional[str] = None,
    tag: Optional[str] = None,
    notes: Optional[str] = None,
    bin_minutes_for_snr: float = 30.0,
) -> dict:
    """Write the packet for one accepted candidate and return the file paths.

    ``result`` is a :class:`tesshunter.pipeline.SearchTargetResult` (or its
    ``to_dict()``); ``lc_clean`` defaults to ``result.lc_clean``. ``fpp``,
    ``centroid`` and ``contamination`` are the corresponding result objects
    (or dicts, or None when not run).
    """
    d = _as_dict(result) if not isinstance(result, dict) else result
    if lc_clean is None:
        lc_clean = getattr(result, "lc_clean", None)
    planets = d.get("planets") or []
    cand = next((p for p in planets if int(p.get("planet_num", 0)) == int(planet_num)), None)
    if cand is None:
        raise ValueError(f"planet {planet_num} not in the result")
    vet = next((v for v in (d.get("vetting") or []) if int(v.get("planet_num", 0)) == int(planet_num)), {})
    fit = cand.get("fit") or {}
    st = _as_dict(stellar) if stellar is not None else (d.get("stellar") or {})
    fp = _as_dict(fpp)
    cen = _as_dict(centroid)
    con = _as_dict(contamination)
    xm = d.get("crossmatch") or {}
    sectors = list((d.get("provenance") or {}).get("units_used") or [])
    tic_id = None
    try:
        from .pipeline import _numeric_id
        tic_id = _numeric_id(d.get("target"))
    except Exception:                                             # pragma: no cover
        tic_id = None
    if tic_id is None:
        tic_id = int(st.get("tic_id") or 0)
    label = label or (f"TIC {tic_id}" if tic_id else str(d.get("target")))

    p_dir = float(fit.get("period") or cand["period_days"])
    out_dir = Path(out_dir) if out_dir is not None else PACKETS_DIR / safe_dirname(f"{label}_P{p_dir:.4f}")
    ensure_dirs(out_dir)

    # light curve arrays
    if lc_clean is not None:
        t = np.asarray(lc_clean.time.value, dtype=float)
        f = np.asarray(lc_clean.flux.value, dtype=float)
        ok = np.isfinite(t) & np.isfinite(f)
        t, f = t[ok], f[ok]
    else:
        t = f = np.array([])

    # neighbours within 1 arcmin
    if neighbours is None and fetch_neighbours and tic_id:
        neighbours = fetch_tic_neighbours(int(tic_id), st.get("ra"), st.get("dec"), radius_arcsec=60.0)
    if neighbours is not None:
        neighbours.to_csv(out_dir / "neighbours.csv", index=False)

    # completeness at this SNR
    comp = {"available": False}
    if fit.get("success") and t.size:
        mf = matched_filter_snr(t, f, fit, bin_minutes=bin_minutes_for_snr)
        comp = completeness_at_snr(mf.get("snr") if mf.get("available") else None)
        comp["matched_filter"] = mf

    # files
    (out_dir / "fit.json").write_text(json.dumps(fit, indent=1, default=str), encoding="utf-8")
    (out_dir / "fpp.json").write_text(json.dumps(fp, indent=1, default=str), encoding="utf-8")
    (out_dir / "vetting.json").write_text(json.dumps(vet, indent=1, default=str), encoding="utf-8")
    fields = ctoi_fields(int(tic_id or 0), fit, candidate=cand, vet=vet, fpp=fp, stellar=st, sectors=sectors,
                         crossmatch=xm, tag=tag, notes=notes, packet_dir=out_dir)
    (out_dir / "ctoi_fields.json").write_text(json.dumps(fields, indent=1, default=str), encoding="utf-8")

    fig_path = out_dir / "summary.png"
    if t.size:
        try:
            _figure(fig_path, label=label, t=t, f=f, fit=fit, candidate=cand, vet=vet, stellar=st, fpp=fp,
                    completeness=comp, centroid=cen, neighbours=neighbours, contamination=con, crossmatch=xm,
                    sectors=sectors)
        except Exception as exc:
            logger.warning("packet figure failed: %s", exc)
            fig_path = None
    else:
        fig_path = None

    md = _markdown(label=label, tic_id=tic_id, cand=cand, fit=fit, vet=vet, st=st, fp=fp, cen=cen, con=con,
                   xm=xm, comp=comp, neighbours=neighbours, sectors=sectors, fields=fields,
                   fig_name=fig_path.name if fig_path else None, d=d)
    (out_dir / "packet.md").write_text(md, encoding="utf-8")
    summary = {
        "label": label, "tic_id": tic_id, "planet_num": planet_num, "period_days": cand.get("period_days"),
        "verdict": vet.get("verdict"), "fpp": fp.get("fpp"), "nfpp": fp.get("nfpp"),
        "fpp_blocks_packet": bool(fp.get("available") and fp.get("fpp") is not None and fp["fpp"] > 0.5),
        "completeness": comp, "files": {
            "packet_md": str(out_dir / "packet.md"), "summary_png": str(fig_path) if fig_path else None,
            "ctoi_fields_json": str(out_dir / "ctoi_fields.json"), "fit_json": str(out_dir / "fit.json"),
            "fpp_json": str(out_dir / "fpp.json"), "vetting_json": str(out_dir / "vetting.json"),
            "neighbours_csv": str(out_dir / "neighbours.csv") if neighbours is not None else None,
        },
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out_dir / "packet.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    return summary


def _markdown(*, label, tic_id, cand, fit, vet, st, fp, cen, con, xm, comp, neighbours, sectors, fields,
              fig_name, d) -> str:
    vr = vet.get("result") or {}
    p_show = float(fit.get("period") or cand["period_days"])
    L = [f"# Candidate packet: {label}, P = {p_show:.5f} d", "",
         f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} by tesshunter. "
         "This is a CANDIDATE. Nothing in this packet is a detection; the automated checks are "
         "necessary, not sufficient. The human reviews and submits.", "",
         f"**Automated verdict:** {vet.get('verdict')}"
         + (f" (light curve only: {vet['verdict_lc_only']})" if vet.get("verdict_lc_only") else "") + "  ",
         f"**FPP / NFPP (TRICERATOPS):** {_fmt(fp.get('fpp'), '.4f')} / {_fmt(fp.get('nfpp'), '.4f')}"
         + (" — above 0.5, does not proceed to submission" if (fp.get('fpp') or 0) > 0.5 else ""), "",
         "## Fitted parameters (limb-darkened transit fit)", "",
         "| parameter | value |", "|---|---|",
         f"| period | {_pm(fit.get('period'), fit.get('period_err'), '.6f', 'd')} |",
         f"| epoch | {_pm(fit.get('t0'), fit.get('t0_err'), '.5f', 'BTJD')} = {_fmt((fit.get('t0') or 0) + BTJD_OFFSET, '.5f', 'BJD')} |",
         f"| duration T14 | {_pm((fit.get('duration_days') or 0) * 24, (fit.get('duration_err') or 0) * 24, '.3f', 'h')} |",
         f"| depth (model maximum) | {_pm(fit.get('depth_ppt'), fit.get('depth_err'), '.4f', 'ppt')} (shape-degenerate error {_fmt(fit.get('depth_err_shape'), '.4f')} ppt) |",
         f"| depth (duration-averaged) | {_fmt(fit.get('depth_mean_ppt'), '.4f', 'ppt')} |",
         f"| Rp/R* | {_pm(fit.get('rp_rs'), fit.get('rp_rs_err'), '.4f')} |",
         f"| a/R* | {_pm(fit.get('a_rs'), fit.get('a_rs_err'), '.2f')} (catalog density gives {_pm(fit.get('a_rs_star'), fit.get('a_rs_star_err'), '.2f')}) |",
         f"| impact parameter | {_pm(fit.get('b'), fit.get('b_err'), '.2f')} ; inclination {_fmt(fit.get('inc_deg'), '.2f', 'deg')} |",
         f"| Rp | {_pm(fit.get('rp_rearth'), fit.get('rp_rearth_err'), '.2f', 'R_Earth')} = {_pm(fit.get('rp_rjup'), fit.get('rp_rjup_err'), '.3f', 'R_Jup')} (R* = {_pm(st.get('radius'), st.get('radius_err'), '.3f', 'R_Sun')}) |",
         f"| stellar density | fit (free) {_fmt(fit.get('rho_star_fit_cgs'), '.3f')} g/cc vs catalog {_pm(fit.get('rho_star_cat_cgs'), fit.get('rho_star_cat_err'), '.3f')} g/cc; ratio {_fmt(fit.get('density_ratio'), '.2f')}, profile delta chi2 {_fmt(fit.get('density_dchi2'), '.1f')}; prior adopted: {fit.get('density_prior_adopted')}; inconsistent: {fit.get('a_rs_inconsistent')} |",
         f"| limb darkening | u1 = {_fmt(fit.get('u1'), '.3f')}, u2 = {_fmt(fit.get('u2'), '.3f')} ({fit.get('ld_source', '')}) |",
         f"| fit | {fit.get('method')}, {fit.get('n_points')} points, {fit.get('n_transits')} transits, reduced chi2 {_fmt(fit.get('reduced_chi2'), '.2f')}, delta BIC vs flat {_fmt(fit.get('delta_bic'), '.0f')} |",
         f"| BLS | SNR {_fmt(cand.get('snr'), '.1f')}, box depth {_fmt(cand.get('depth_ppt_bls'), '.3f')} ppt, {cand.get('n_transits_observed')} transits observed, alias label {cand.get('harmonic_label')} |",
         "", "## Vetting checks", "",
         "| check | result |", "|---|---|",
         f"| odd/even (median) | {'FLAG' if vr.get('odd_even_mismatch') else 'pass'} ({_fmt(vr.get('odd_even_delta_sigma'), '.1f')} sigma) |",
         f"| odd/even (fit template) | {(fit.get('odd_even') or {}).get('note', 'n/a')} |",
         f"| secondary at phase 0.5 | {_fmt(vr.get('secondary_depth_ppt'), '.4f')} ppt measured; deepest planetary secondary at the fitted a/R* {_fmt(vr.get('secondary_planet_bound_ppt'), '.4f')} ppt; {'STELLAR' if vr.get('secondary_is_stellar') else ('detected, consistent with a planet' if vr.get('secondary_eclipse_detected') else 'not detected')} |",
         f"| a/R* consistency | {'FLAG' if vr.get('a_rs_inconsistent') else 'pass'} — {fit.get('consistency_note', '')[:200]} |",
         f"| V-shape | {vr.get('v_shape_flag')} (t_flat/t_total {_fmt(vr.get('v_shape_ratio'), '.2f')}); fitted geometry grazing: {fit.get('grazing')} |",
         f"| per-unit depths | {'FLAG' if vr.get('sector_depth_mismatch') else 'pass'} |",
         f"| centroid | {('shift ' + _fmt(cen.get('total_shift_px'), '.3f') + ' px, ' + _fmt(cen.get('sigma'), '.1f') + ' sigma' + (' FLAG' if cen.get('flagged') else '')) if cen.get('available') else 'not run'} |",
         f"| contamination | {('flagged' if con.get('flagged') else 'pass') + ', ' + str(con.get('n_neighbours_checked')) + ' neighbours checked' if con.get('available') else 'not run'} |",
         f"| FPP / NFPP | {_fmt(fp.get('fpp'), '.4f')} / {_fmt(fp.get('nfpp'), '.4f')} ({fp.get('note', fp.get('error', 'not run'))}) |",
         "", "Flags: " + ("; ".join((vet.get("flags_hard") or []) + (vet.get("flags_high") or []) + (vet.get("flags_medium") or [])) or "none"), "",
         "## Completeness at this SNR", "",
         (f"Matched-filter SNR {_fmt(comp.get('snr'), '.1f')} on this star's detrended data binned to "
          f"{_fmt(bin_minutes := (comp.get('matched_filter') or {}).get('bin_minutes'), '.0f')} min: the P2 completeness curve "
          f"(`{COMPLETENESS_DOC}`, {comp.get('n_injections')} injections on {comp.get('sample_size_stars')} stars, config "
          f"{comp.get('config')}) recovers {_fmt(comp.get('logistic_recovery'), '.2f')} of injected signals at this SNR "
          f"(SNR50 = {_fmt(comp.get('snr50'), '.1f')}, SNR90 = {_fmt(comp.get('snr90'), '.1f')}"
          + (f"; the {comp['bin']['lo']}-{comp['bin']['hi']} bin recovered {comp['bin']['k']}/{comp['bin']['n']}" if comp.get('bin') else "")
          + f"). {comp.get('note', '')}") if comp.get("available") else "Completeness not available (no fit or no light curve).",
         "", "## Star and neighbours", "",
         f"TIC {tic_id}: Teff {_fmt(st.get('teff'), '.0f')} K, log g {_fmt(st.get('logg'), '.2f')}, R = {_pm(st.get('radius'), st.get('radius_err'), '.3f')} R_Sun, "
         f"M = {_pm(st.get('mass'), st.get('mass_err'), '.3f')} M_Sun, Tmag {_fmt(st.get('tmag'), '.2f')}, TIC contamination ratio "
         f"{_fmt(st.get('contamination_ratio'), '.4f')} (source {st.get('source')}; assumed errors: {st.get('assumed_errors')}).", ""]
    if neighbours is not None and len(neighbours):
        cols = [c for c in ("ID", "dstArcSec", "Tmag", "GAIAmag", "gaiabp", "gaiarp", "Teff", "rad", "contratio", "disposition") if c in neighbours.columns]
        L.append("| " + " | ".join(cols) + " |")
        L.append("|" + "---|" * len(cols))
        for _, r in neighbours.head(25).iterrows():
            L.append("| " + " | ".join(_fmt(r[c], ".2f") if isinstance(r[c], (float, np.floating)) else str(r[c]) for c in cols) + " |")
        L.append("")
    else:
        L += ["_Neighbour table not available._", ""]
    L += ["## Cross-match", "",
          f"{xm.get('summary', 'Catalog cross-match not attempted.')}  ",
          f"Catalog versions: `{xm.get('catalog_versions', 'n/a')}`", "",
          "## Data", "",
          f"Sectors {sectors}; {d.get('n_cadences_raw')} raw and {d.get('n_cadences_clean')} cleaned cadences; "
          f"products: {', '.join(str(p.get('author', '?')) + ' s' + str(p.get('unit', '?')) for p in (d.get('provenance') or {}).get('products', [])[:6])}.", ""]
    if fig_name:
        L += ["## Figure", "", f"![summary]({fig_name})", ""]
    L += ["## ExoFOP CTOI fields", "", "```json", json.dumps(fields["form_fields"], indent=1, default=str), "```", "",
          "_The pipeline finds candidates. It does not submit._", ""]
    return "\n".join(L)
