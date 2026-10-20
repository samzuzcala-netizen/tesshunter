"""Survey yield model: expected detectable and expected NEW transit signals per star.

The model is deliberately simple and every input is a named constant so the
memo (``docs/POPULATION.md``) can quote it.  Occurrence rates come from
published grids (:mod:`tesshunter.occurrence_grids`) or from the legacy
class-based model kept for comparison.

Per star and per occurrence cell (period bin x radius bin):

    expected = rate(cell) x P_transit(P, R*, M*) x P_detect(SNR, N_transits)

with depth = (Rp/R*)^2 / (1 + contamination ratio), a central circular transit
duration, N_transits from the number of sectors with a light curve, and a
logistic detection ramp.  Three mutually exclusive detectability classes:

* **A**: detectable in a single sector alone at SNR >= 9 (QLP's per-sector search).
* **B**: detectable in the stitched light curve at SNR >= 9 but not A.
* **C**: detectable in the stitch at 7.1 <= SNR < 9.

``A + B + C`` equals the stitched SNR >= 7.1 expectation (checked by a test).

Missing TIC contamination ratios are NOT zero.  Every yield call takes an
explicit ``contam_fill``; with NaN ratios present and no fill given the call
raises, so no code path can silently treat "unknown" as "uncontaminated".
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from . import occurrence_grids as og

# ── Noise, detection, priors (unchanged from P1; quoted in the memo) ─────────
NOISE_MODEL = {
    "zero_point_e_per_s_T10": 15000.0,        # Sullivan+2015: a T=10 star gives 1.5e4 e/s
    "sky_e_per_s_per_pixel": 200.0,           # zodiacal + unresolved background per pixel, rough
    "aperture_pixels": {"10": 14, "12": 8, "13.5": 6, "15": 4, "17": 3},   # QLP-like apertures
    "systematic_floor_ppm_per_hour": 60.0,    # Sullivan+2015 / Stassun+2018 adopted floor
    "ffi_pipeline_inefficiency": 1.5,         # realized FFI precision vs photon model, adopted
    "exposure_hours": 1.0,
}
DETECTION = {
    "snr_threshold": 7.1,       # SPOC MES threshold; the ramp is centred here
    "snr_ramp_width": 0.6,      # logistic width in SNR units
    "min_transits": 2,          # the pipeline's floor
    "duty_cycle": 0.85,         # usable fraction of a 27.4-d sector after gaps and quality masks
    "sector_days": 27.4,
    "single_sector_snr_for_prior_search": 9.0,   # QLP TOI release threshold (Huang+2020, Guerrero+2021)
    "class_b_snr": 9.0,
}
PRIOR_COMPLETENESS = {
    "bright": {"A": {"low": 0.70, "mid": 0.85, "high": 0.95},
               "B": {"low": 0.40, "mid": 0.60, "high": 0.80},
               "C": {"low": 0.05, "mid": 0.15, "high": 0.30}},
    "faint_m": {"A": {"low": 0.40, "mid": 0.60, "high": 0.80},
                "B": {"low": 0.20, "mid": 0.40, "high": 0.60},
                "C": {"low": 0.03, "mid": 0.10, "high": 0.25}},
    "toi_host_additional": {"low": 0.60, "mid": 0.75, "high": 0.90},
}
PIPELINE_EFFICIENCY = {"A": 0.80, "B": 0.70, "C": 0.40}

# ── Contamination policy ──────────────────────────────────────────────────────
CONTAMINATION_POLICY = {
    "central": "measured_median",
    "variants": ["zero", "measured_median", "measured_p90"],
    "rationale": (
        "The TIC computes the contamination ratio only for Candidate Target List members, and CTL "
        "membership favours isolated stars; a missing ratio therefore means 'not evaluated', not "
        "'zero', and the measured population is if anything biased low. The central policy imputes "
        "the measured median of the same stratum (CLEAN stars); the p90 variant bounds the yield "
        "from below; zero is kept only to reproduce the P1 result."
    ),
}


def contamination_fills(measured: pd.Series) -> dict[str, float]:
    """Fill values for the three policies from a measured (non-NaN) contamination sample."""
    m = pd.to_numeric(measured, errors="coerce").dropna()
    if len(m) == 0:
        raise ValueError("no measured contamination ratios to impute from")
    return {"zero": 0.0, "measured_median": float(m.median()), "measured_p90": float(m.quantile(0.90))}


# ── Legacy class-based occurrence model (P1), kept for comparison ────────────
LEGACY_OCCURRENCE = {
    "fgk": {
        "1-2":  {"rate": 0.25, "p_lo": 1.0, "p_hi": 50.0, "r_rep": 1.5,
                 "source": "Petigura+2013 PNAS (1-2 Re, 5-100 d, 26%); rescaled to 1-50 d as 25%"},
        "2-4":  {"rate": 0.13, "p_lo": 1.0, "p_hi": 50.0, "r_rep": 2.8,
                 "source": "Howard+2012 ApJS Table 4: 0.130 per star, 2-4 Re, P<50 d"},
        "4-8":  {"rate": 0.023, "p_lo": 1.0, "p_hi": 50.0, "r_rep": 5.5,
                 "source": "Howard+2012: 0.023 per star, 4-8 Re, P<50 d"},
        "8-20": {"rate": 0.013, "p_lo": 1.0, "p_hi": 50.0, "r_rep": 11.0,
                 "source": "Howard+2012: 0.013 per star, 8-32 Re, P<50 d; hot-Jupiter share 0.005 at P<10 d"},
    },
    "m": {
        "1-1.5": {"rate": 0.56, "p_lo": 0.5, "p_hi": 50.0, "r_rep": 1.25,
                  "source": "Dressing & Charbonneau 2015 abstract: 0.56 per M dwarf, 1-1.5 Re, P<50 d"},
        "1.5-2": {"rate": 0.46, "p_lo": 0.5, "p_hi": 50.0, "r_rep": 1.75,
                  "source": "Dressing & Charbonneau 2015 abstract: 0.46 per M dwarf, 1.5-2 Re, P<50 d"},
        "2-4":   {"rate": 0.25, "p_lo": 0.5, "p_hi": 50.0, "r_rep": 2.8,
                  "source": "Dressing & Charbonneau 2015 Table 3 summed over 2-4 Re bins, P<50 d; approximate"},
        "4-20":  {"rate": 0.02, "p_lo": 0.5, "p_hi": 50.0, "r_rep": 8.0,
                  "source": "adopted in P1 without citation: giant planets around M dwarfs ~1-2% at P<50 d (kept verbatim for the legacy comparison)"},
    },
}
LEGACY_PERIOD_EDGES = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 50.0, 100.0]
LEGACY_PERIOD_SHAPE = {"form": "dN/dlnP proportional to min(P/P_break, 1)", "p_break_days": 10.0}


def _period_weight(lo: float, hi: float, p_break: float = LEGACY_PERIOD_SHAPE["p_break_days"]) -> float:
    w = 0.0
    if lo < p_break:
        w += (min(hi, p_break) - lo) / p_break
    if hi > p_break:
        w += float(np.log(hi / max(lo, p_break)))
    return w


def legacy_cells(group: str, p_max: float) -> list[dict]:
    """The P1 class-based model expressed as cells (identical arithmetic to P1)."""
    cells = []
    for rkey, spec in LEGACY_OCCURRENCE[group].items():
        edges = [e for e in LEGACY_PERIOD_EDGES if spec["p_lo"] <= e <= max(spec["p_hi"], p_max) and e <= p_max]
        if len(edges) < 2:
            continue
        w_total = _period_weight(spec["p_lo"], spec["p_hi"])
        for lo, hi in zip(edges[:-1], edges[1:]):
            if hi <= spec["p_hi"]:
                rate = spec["rate"] * _period_weight(lo, hi) / w_total
            else:
                rate = spec["rate"] / w_total * np.log(hi / max(lo, spec["p_hi"]))
            if rkey == "8-20" and hi <= 10.0:
                rate = 0.005 * np.log(hi / lo) / np.log(10.0)
            elif rkey == "8-20":
                rate = (spec["rate"] - 0.005) * np.log(hi / lo) / np.log(spec["p_hi"] / 10.0)
                if lo < 10.0:
                    rate = 0.0
            cells.append({"p_lo": lo, "p_hi": hi, "r_lo": np.nan, "r_hi": np.nan, "r_rep": spec["r_rep"],
                          "rate": float(rate), "label": f"{rkey}Re_{lo:g}-{hi:g}d"})
    return cells


# ── Occurrence model registry ─────────────────────────────────────────────────
FGK_MODELS = {
    "km2020": "Kunimoto & Matthews 2020 baseline FGK grid (occurrence_grids.KM2020_FGK)",
    "legacy_howard_petigura": "P1 class model: Howard+2012 / Petigura+2013 classes with a broken power-law period shape",
}
M_MODELS = {
    "dc15_grid": "Dressing & Charbonneau 2015 Table 3 grid + adopted 4-20 Re giants (occurrence_grids.DC15_M)",
    "legacy_dc15_classes": "P1 class model: DC15 abstract rates in 1-1.5, 1.5-2, 2-4 Re classes + adopted giants",
}
CENTRAL_MODEL = {"fgk": "km2020", "m": "dc15_grid"}


def occurrence_cells(group: str, model: str, p_max: float, p_min: float = 0.0,
                     m_giant_rate: float | None = None) -> list[dict]:
    """Cells for a stellar group under a named model, restricted to [p_min, p_max] days.

    ``m_giant_rate`` overrides the adopted 4-20 Re rate of the DC15 grid (sensitivity runs).
    """
    if group == "fgk":
        if model == "km2020":
            cells = og.km2020_fgk_cells()
        elif model == "legacy_howard_petigura":
            return legacy_cells("fgk", p_max)
        else:
            raise KeyError(model)
    elif group == "m":
        if model == "dc15_grid":
            cells = og.dc15_m_cells(giant_rate=m_giant_rate)
        elif model == "legacy_dc15_classes":
            return legacy_cells("m", p_max)
        else:
            raise KeyError(model)
    else:
        raise KeyError(group)
    out = []
    for c in og.clip_cells_to_period(cells, max(p_min, 1e-9), p_max):
        d = dict(c)
        d["r_rep"] = float(np.sqrt(c["r_lo"] * c["r_hi"]))
        d["label"] = f"{c['r_lo']:g}-{c['r_hi']:g}Re_{d['p_lo']:g}-{d['p_hi']:g}d"
        out.append(d)
    return out


# ── Physics helpers ───────────────────────────────────────────────────────────
def noise_ppm_per_hour(tmag, noise_model: dict = NOISE_MODEL, faint_penalty: float = 1.0,
                       faint_penalty_tmag: float = 13.5) -> np.ndarray:
    nm = noise_model
    t = np.asarray(tmag, dtype=float)
    nstar = nm["zero_point_e_per_s_T10"] * 10 ** (-0.4 * (t - 10.0))
    keys = sorted((float(k), v) for k, v in nm["aperture_pixels"].items())
    npix = np.interp(t, [k for k, _ in keys], [v for _, v in keys])
    nsky = nm["sky_e_per_s_per_pixel"] * npix
    secs = nm["exposure_hours"] * 3600.0
    shot = np.sqrt((nstar + nsky) * secs) / (nstar * secs)
    sig = np.sqrt(shot ** 2 + (nm["systematic_floor_ppm_per_hour"] * 1e-6) ** 2)
    out = sig * 1e6 * nm["ffi_pipeline_inefficiency"]
    if faint_penalty != 1.0:
        out = out * np.where(t > faint_penalty_tmag, faint_penalty, 1.0)
    return out


def transit_duration_hours(period_d, rstar, mstar) -> np.ndarray:
    rho = np.asarray(mstar, float) / np.clip(np.asarray(rstar, float), 0.05, None) ** 3
    return 13.0 * (np.asarray(period_d, float) / 365.25) ** (1.0 / 3.0) * rho ** (-1.0 / 3.0)


def geometric_probability(period_d, rstar, mstar) -> np.ndarray:
    a_au = (np.asarray(mstar, float) * (np.asarray(period_d, float) / 365.25) ** 2) ** (1.0 / 3.0)
    return np.clip(np.asarray(rstar, float) * 0.00465047 / a_au, 0, 1)


def _ramp(snr, thr, width=DETECTION["snr_ramp_width"]):
    return 1.0 / (1.0 + np.exp(-(np.asarray(snr, float) - thr) / width))


# ── Per-star yields ───────────────────────────────────────────────────────────
def _star_arrays(stars: pd.DataFrame, contam_fill: Optional[float]):
    tmag = stars["Tmag"].to_numpy(dtype=float)
    rstar = stars["rad"].to_numpy(dtype=float)
    mass = stars["mass"].to_numpy(dtype=float)
    mstar = np.where(np.isfinite(mass), mass, rstar)          # M ~ R for dwarfs when mass is missing
    contam = stars["contratio"].to_numpy(dtype=float)
    if np.isnan(contam).any():
        if contam_fill is None:
            raise ValueError(
                "stars carry missing TIC contamination ratios; pass contam_fill explicitly "
                "(see CONTAMINATION_POLICY) instead of letting NaN become zero"
            )
        contam = np.where(np.isnan(contam), float(contam_fill), contam)
    nsec = stars["n_sectors_use"].to_numpy(dtype=float)
    return tmag, rstar, mstar, contam, nsec


def per_star_yield(stars: pd.DataFrame, cells: list[dict], mode: str, *,
                   snr_threshold: Optional[float] = None, contam_fill: Optional[float] = None,
                   faint_penalty: float = 1.0, return_per_cell: bool = False):
    """Expected detectable transiting planets per star (array aligned with ``stars``).

    ``mode`` "single": one sector alone, threshold ``single_sector_snr_for_prior_search``;
    ``mode`` "stitch": all sectors with a light curve, threshold ``snr_threshold``
    (default ``DETECTION['snr_threshold']``).
    """
    if len(stars) == 0:
        return (np.zeros(0), {}) if return_per_cell else np.zeros(0)
    tmag, rstar, mstar, contam, nsec = _star_arrays(stars, contam_fill)
    sig = noise_ppm_per_hour(tmag, faint_penalty=faint_penalty) * 1e-6
    d = DETECTION
    total = np.zeros(len(stars))
    per_cell = {}
    for c in cells:
        if c["rate"] <= 0:
            continue
        pmid = float(np.sqrt(c["p_lo"] * c["p_hi"]))
        depth = (c["r_rep"] * 0.009168 / np.clip(rstar, 0.05, None)) ** 2 / (1.0 + contam)
        t14 = transit_duration_hours(pmid, rstar, mstar)
        pgeo = geometric_probability(pmid, rstar, mstar)
        if mode == "single":
            n_tr = np.floor(d["sector_days"] * d["duty_cycle"] / pmid) * np.ones_like(nsec)
            n_tr = np.where(nsec >= 1, n_tr, 0.0)
            snr = depth / sig * np.sqrt(t14 * n_tr)
            pdet = np.where(n_tr >= d["min_transits"], _ramp(snr, d["single_sector_snr_for_prior_search"]), 0.0)
        else:
            n_tr = np.floor(nsec * d["sector_days"] * d["duty_cycle"] / pmid)
            snr = depth / sig * np.sqrt(t14 * n_tr)
            thr = d["snr_threshold"] if snr_threshold is None else snr_threshold
            pdet = np.where(n_tr >= d["min_transits"], _ramp(snr, thr), 0.0)
        val = c["rate"] * pgeo * pdet
        total = total + val
        if return_per_cell:
            per_cell[c["label"]] = float(np.sum(val))
    return (total, per_cell) if return_per_cell else total


def class_yields(stars: pd.DataFrame, cells_le50: list[dict], cells_full: list[dict], *,
                 contam_fill: Optional[float], faint_penalty: float = 1.0) -> dict:
    """Per-star detectable yield in the three exclusive classes.

    ``cells_le50`` are the cells used for the single-sector class (P <= 50 d, the
    prior-search space); ``cells_full`` are the cells for the stitched classes
    (P up to the stratum's maximum).  Returns arrays ``A``, ``B``, ``C`` and the
    stitched totals at SNR 9 and 7.1.
    """
    a = per_star_yield(stars, cells_le50, "single", contam_fill=contam_fill, faint_penalty=faint_penalty)
    s9 = per_star_yield(stars, cells_full, "stitch", snr_threshold=DETECTION["class_b_snr"],
                        contam_fill=contam_fill, faint_penalty=faint_penalty)
    s7 = per_star_yield(stars, cells_full, "stitch", contam_fill=contam_fill, faint_penalty=faint_penalty)
    b = np.maximum(s9 - a, 0.0)
    c = np.maximum(s7 - s9, 0.0)
    return {"A": a, "B": b, "C": c, "stitched_snr9": s9, "stitched_snr7": s7}


def new_signals_per_star(cls: dict, prior_key: str, level: str = "mid") -> np.ndarray:
    """Expected NEW detected signals per star = sum_k class_k x (1 - prior_k) x efficiency_k."""
    return sum(cls[k] * (1.0 - PRIOR_COMPLETENESS[prior_key][k][level]) * PIPELINE_EFFICIENCY[k]
               for k in ("A", "B", "C"))
