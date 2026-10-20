"""K1 change 7: merit = expected NEW planets per star (E_new), from the review's yield model.

Seeded from ``population_analysis_2026-10-07/yieldlib.py`` (copied verbatim to
``yieldlib_k1.py``) and the review's ranking scripts ``s6b_topn_clean.py`` / ``s14_data_avail.py``:

    E_new(star) = sum over occurrence cells c of
                  k(type, Rp class of c) x rate_c x P_geo x P_user(SNR(n_user), N_tr(n_user)) x (1 - P_inc)

* occurrence: Kunimoto & Matthews 2020 (``fgk``) for class K (types K_late 3900-4600 K, K_early
  4600-5300 K); Dressing & Charbonneau 2015 (``m``) for class eM (type M_early);
* k: the review's TOI-calibrated radius-class factors (bright stars, Tmag 0-12, column r_toi,
  clipped to [0.1, 1.5]); ``k_variant="published"`` sets k = 1 (the DC15 / KM20 rates as published);
* P_user: the Oct 3-4 real-planet curve (max 0.65, SNR50 12.5, width 2.5, zero below SNR 7.1,
  >= 3 transits), SNR from the repo noise model x the measured Tmag ratio (``yieldlib.sigma_1h``),
  transits from ``n_user`` sectors (K1: n_usable);
* novelty (1 - P_inc): the review's SPOC (2-min sectors) and QLP (all observed sectors, Tmag <= 13.5)
  incumbent models.

``noise_scale`` (Part C refit, rule A4) multiplies sigma_1h per star when supplied.
Nothing here is a detection.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import yieldlib_k1 as Y

DATA = Path(__file__).resolve().parent / "data"
RC_PATH = DATA / "radius_calibration_review_20261007.csv"
RC_BINS = [(0.5, 1.5, "0.5-1.5"), (1.5, 2.5, "1.5-2.5"), (2.5, 4.0, "2.5-4"), (4.0, 20.0, "4-20")]
TYPES_K = ("K_late", "K_early")
TYPE_EM = "M_early"


def star_type(teff) -> np.ndarray:
    """The review's type labels inside the K1 classes (s3_model.classify, dwarfs)."""
    t = np.asarray(teff, float)
    out = np.full(t.shape, "other", dtype=object)
    out[(t >= 3900) & (t < 4600)] = "K_late"
    out[(t >= 4600) & (t < 5300)] = "K_early"
    out[(t >= 5300) & np.isclose(t, 5300)] = "K_early"      # class K includes Teff = 5300 exactly
    out[(t >= 3600) & (t < 3900)] = "M_early"
    return out


def kvec(ty: str, cells: list[dict], variant: str = "toi") -> np.ndarray:
    if variant == "published":
        return np.ones(len(cells))
    rc = pd.read_csv(RC_PATH)
    out = []
    for c in cells:
        lab = next(l for lo, hi, l in RC_BINS if lo <= c["r_rep"] < hi)
        r = rc[(rc.type == ty) & (rc.tmag == "0-12") & (rc.rp == lab)]
        v = float(r.r_toi.iloc[0]) if len(r) and np.isfinite(r.r_toi.iloc[0]) else 1.0
        out.append(np.clip(v, 0.1, 1.5))
    return np.array(out)


def _frame(df: pd.DataFrame, n_user_col: str, n2_col: str, nobs_col: str, noise_scale=None) -> pd.DataFrame:
    rad = pd.to_numeric(df["rad"], errors="coerce").to_numpy(float)
    mass = pd.to_numeric(df["mass"], errors="coerce").to_numpy(float) if "mass" in df else np.full(len(df), np.nan)
    contr = pd.to_numeric(df["contratio"], errors="coerce").to_numpy(float)
    st = pd.DataFrame({"Tmag": pd.to_numeric(df["Tmag"], errors="coerce").to_numpy(float), "rad": rad,
                       "mass_f": np.where(np.isfinite(mass), mass, rad),
                       "contr_f": np.where(np.isfinite(contr), contr, 0.05),
                       "n_user": pd.to_numeric(df[n_user_col], errors="coerce").fillna(0).to_numpy(float),
                       "n_2min": pd.to_numeric(df[n2_col], errors="coerce").fillna(0).to_numpy(float),
                       "n_obs": pd.to_numeric(df[nobs_col], errors="coerce").fillna(0).to_numpy(float)},
                      index=df.index)
    if noise_scale is not None:
        st["noise_scale"] = np.asarray(noise_scale, float)
    return st


def _terms(st: pd.DataFrame, cells: list[dict], model: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """yieldlib.star_cell_terms with an optional per-star noise scale (A4)."""
    if "noise_scale" not in st:
        t = Y.star_cell_terms(st, cells, "n_user", model)
        return (np.array([x[1] for x in t]), np.array([x[2] for x in t]), np.array([x[3] for x in t]))
    tm = st.Tmag.to_numpy(float); rs = st.rad.to_numpy(float)
    ms = st.mass_f.to_numpy(float); cr = st.contr_f.to_numpy(float)
    sig = Y.sigma_1h(tm) * st.noise_scale.to_numpy(float)
    nu = st.n_user.to_numpy(float); n2 = st.n_2min.to_numpy(float); nall = st.n_obs.to_numpy(float)
    q_ok = tm <= Y.QLP["tmag_max"]
    rg, pu, pi = [], [], []
    for c in cells:
        P = c["p_rep"]
        depth = (c["r_rep"] * 0.009168 / np.clip(rs, 0.05, None)) ** 2 / (1 + cr)
        t14 = Y.t14_hours(P, rs, ms)
        g = Y.p_geo(P, rs, ms)
        snr = lambda n: depth / sig * np.sqrt(t14 * Y.ntr(n, P))  # noqa: E731
        ps = np.where(n2 > 0, Y.pdet(snr(n2), Y.ntr(n2, P), Y.SPOC), 0.0)
        pq = np.where(q_ok, Y.pdet(snr(nall), Y.ntr(nall, P), Y.QLP), 0.0)
        rg.append(c["rate"] * g); pu.append(Y.pdet(snr(nu), Y.ntr(nu, P), model)); pi.append(1 - (1 - ps) * (1 - pq))
    return np.array(rg), np.array(pu), np.array(pi)


def e_new(df: pd.DataFrame, types, *, n_user_col: str = "n_usable", n2_col: str = "n_2min_all",
          nobs_col: str = "n_obs_le105", p_max: float = 50.0, k_variant: str = "toi",
          model: dict | None = None, noise_scale=None, by_radius: bool = False):
    """E_new per row of ``df`` (columns Tmag, rad, mass, contratio and the three sector counts);
    ``types`` is a per-row array of K_late / K_early / M_early.  Returns a Series (and, with
    ``by_radius``, a DataFrame of the per-radius-class contributions)."""
    model = model or Y.USER
    types = np.asarray(types, dtype=object)
    st = _frame(df, n_user_col, n2_col, nobs_col, noise_scale)
    out = pd.Series(0.0, index=df.index)
    parts = pd.DataFrame(0.0, index=df.index, columns=[l for _, _, l in RC_BINS])
    for ty in sorted(set(types)):
        if ty not in TYPES_K + (TYPE_EM,):
            continue
        m = types == ty
        cells = Y.cells_for("m" if ty.startswith("M") else "fgk", p_max=p_max)
        kv = kvec(ty, cells, k_variant)
        rg, pu, pi = _terms(st[m], cells, model)
        contrib = kv[:, None] * rg * pu * (1 - pi)
        out[m] = contrib.sum(axis=0)
        if by_radius:
            for lo, hi, lab in RC_BINS:
                sel = np.array([lo <= c["r_rep"] < hi for c in cells])
                parts.loc[m, lab] = contrib[sel].sum(axis=0)
    return (out, parts) if by_radius else out
