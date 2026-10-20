# K1 change 7: copied verbatim from population_analysis_2026-10-07/yieldlib.py (review of 2026-10-07).
# Source sha256 ec53c2e2ef44b2d336b3674ccfe52e9a1876fc7ecac069920e1a3147aa189cae. Do not edit; K1 ranking changes go in rank_k1.py.
"""Shared yield-model pieces for the population comparison (scratch analysis, not repo code).

Per star and occurrence cell:
    expected = k_type * rate * P_geo * P_detect
SNR = depth / sigma_1h * sqrt(T14_h * N_tr); sigma_1h from the repo noise model (survey_yield.noise_ppm_per_hour)
corrected by the measured/model ratio on 120 real hosts (Oct 3 validation, 200-s data).
"""
import sys
import numpy as np
import pandas as pd

REPO = r"C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter"
sys.path.insert(0, REPO + r"\src")
from tesshunter import occurrence_grids as og           # noqa: E402
from tesshunter.survey_yield import noise_ppm_per_hour  # noqa: E402

# measured/model noise ratio by Tmag (120 hosts, planets_with_signal_strength.csv, 200-s cadence)
_NT = [8.0, 9.5, 10.5, 11.5, 12.25, 12.75, 13.25, 13.75, 14.25, 14.75]
_NR = [0.74, 0.82, 0.87, 0.91, 0.91, 0.97, 1.03, 1.01, 1.18, 1.59]

SECTOR_DAYS, DUTY = 27.4, 0.85


def sigma_1h(tmag):
    t = np.asarray(tmag, float)
    return noise_ppm_per_hour(t) * np.interp(t, _NT, _NR) * 1e-6


def t14_hours(p, rstar, mstar):
    rho = np.asarray(mstar, float) / np.clip(np.asarray(rstar, float), 0.05, None) ** 3
    return 13.0 * (np.asarray(p, float) / 365.25) ** (1 / 3) * rho ** (-1 / 3)


def p_geo(p, rstar, mstar):
    a_au = (np.asarray(mstar, float) * (np.asarray(p, float) / 365.25) ** 2) ** (1 / 3)
    return np.clip(np.asarray(rstar, float) * 0.00465047 / a_au, 0, 1)


def logistic(x, x50, w, cmax=1.0):
    return cmax / (1.0 + np.exp(-(np.asarray(x, float) - x50) / w))


def cells_for(group, p_max=30.0, p_min=0.5, m_giant_rate=0.01):
    if group == "fgk":
        cells = og.km2020_fgk_cells()
    else:
        cells = og.dc15_m_cells(giant_rate=m_giant_rate)
    out = []
    for c in og.clip_cells_to_period(cells, p_min, p_max):
        if c["rate"] <= 0:
            continue
        d = dict(c)
        d["r_rep"] = float(np.sqrt(c["r_lo"] * c["r_hi"])) if np.isfinite(c["r_lo"]) else 8.0
        d["p_rep"] = float(np.sqrt(d["p_lo"] * d["p_hi"]))
        out.append(d)
    return out


def ntr(nsec, p):
    """Expected number of observed transits (not floored), given n sectors and period."""
    return np.asarray(nsec, float) * SECTOR_DAYS * DUTY / p


# detection models ---------------------------------------------------------------
# user's pipeline end-to-end on real planets (Oct 3-4 validation, through C, n=162):
#   SNR<7.1 0/87, 7.1-12 2/6, 12-20 12/27, 20-40 21/30, >=40 6/12  -> cmax 0.65, SNR50 12.5, w 2.5
USER = {"x50": 12.5, "w": 2.5, "cmax": 0.65, "min_tr": 3, "floor": 7.1}
USER_OPT = {"x50": 11.0, "w": 2.0, "cmax": 0.80, "min_tr": 3, "floor": 7.1}     # injection-like optimistic variant
SPOC = {"x50": 8.0, "w": 0.8, "cmax": 0.90, "min_tr": 2, "floor": 7.1}          # 2-min TPS MES 7.1 + DV/vetting
QLP = {"x50": 10.0, "w": 1.2, "cmax": 0.80, "min_tr": 2, "tmag_max": 13.5, "floor": 9.0}  # multi-sector BLS + vetting


def pdet(snr, ntr_, m):
    ok = (ntr_ >= m["min_tr"]) & (np.asarray(snr) >= m["floor"])
    return np.where(ok, logistic(snr, m["x50"], m["w"], m["cmax"]), 0.0)


def star_cell_terms(st, cells, nsec_user_col, user_model=USER):
    """Return per-cell arrays (n_cells x n_stars) of rate*pgeo, P_user, P_inc."""
    tm = st.Tmag.to_numpy(float); rs = st.rad.to_numpy(float)
    ms = st["mass_f"].to_numpy(float); cr = st["contr_f"].to_numpy(float)
    sig = sigma_1h(tm)
    nu = st[nsec_user_col].to_numpy(float)
    n2 = st.n_2min.to_numpy(float); nall = st.n_obs.to_numpy(float)
    q_ok = tm <= QLP["tmag_max"]
    out = []
    for c in cells:
        P = c["p_rep"]
        depth = (c["r_rep"] * 0.009168 / np.clip(rs, 0.05, None)) ** 2 / (1 + cr)
        t14 = t14_hours(P, rs, ms)
        g = p_geo(P, rs, ms)
        def snr(n):
            return depth / sig * np.sqrt(t14 * ntr(n, P))
        pu = pdet(snr(nu), ntr(nu, P), user_model)
        ps = np.where(n2 > 0, pdet(snr(n2), ntr(n2, P), SPOC), 0.0)
        pq = np.where(q_ok, pdet(snr(nall), ntr(nall, P), QLP), 0.0)
        pinc = 1 - (1 - ps) * (1 - pq)
        out.append((c, c["rate"] * g, pu, pinc, ps, pq))
    return out
