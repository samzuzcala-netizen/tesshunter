"""Physical transit fit for accepted candidates (prompt 3, part A).

A quadratic-limb-darkened batman model (coefficients from the Claret 2017
TESS tables, see :mod:`tesshunter.limb_darkening`) is fitted to the detrended
light curve in a window around every transit by bounded least squares; the
covariance of the solution gives uncertainties on period, epoch, Rp/R*,
a/R*, impact parameter and baseline, and Monte-Carlo propagation gives them
on the derived duration, depth, planet radius and stellar density. An
optional emcee run (``mcmc=True``) replaces the covariance with posterior
percentiles for the packet stage.

Two things the fit provides that the box search cannot:

* a **depth definition** that matches catalogues (the maximum of the
  limb-darkened model, ``depth_ppt``, alongside the duration-averaged
  ``depth_mean_ppt``) instead of a median over the flat bottom;
* the **stellar density implied by the transit shape** (Seager &
  Mallen-Ornelas 2003), which is compared with the catalog density: a
  transit that needs a much less dense star than the TIC reports is the
  signature of a diluted (blended) eclipse or a grazing stellar companion,
  and :attr:`TransitFit.a_rs_inconsistent` becomes a vetting flag.

The b to a/R* degeneracy is handled explicitly. Every star with a catalog
density gets TWO fits: a free one and one whose a/R* is confined to the
catalog value's 3-sigma range. The profile difference in chi-square between
them is the consistency statistic (a covariance-based sigma is also reported
but is known to be optimistic when b sits at a bound). When the data cannot
reject the catalog range (delta chi2 below DENSITY_DCHI2_MIN) the
constrained solution is ADOPTED for the reported parameters, which is the
usual stellar-density prior; when they can, the free solution is reported.
``density_prior_adopted`` records which.

The fit also yields an odd/even depth comparison with uncertainties from
the model template (:func:`odd_even_from_fit`), used by the alias resolver
to test P against 2P before choosing.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Optional

import numpy as np

from . import limb_darkening
from .stellar import (
    REARTH_PER_RSUN,
    RJUP_PER_RSUN,
    StellarParams,
    a_rs_from_density,
    density_from_a_rs,
)

logger = logging.getLogger(__name__)

#: Rp/R* above which a candidate is not planet-shaped (a 0.2 ratio is 4% deep
#: and, on a Sun, 2 R_Jup). Used by gates 6 and 7 (prompt 3, part C).
MAX_PLANET_RP_RS = 0.2

#: A fitted depth below this many times its statistical error means the
#: limb-darkened model does not see a transit at the BLS ephemeris: the box
#: depth is kept and vetting raises a flag. Measured on the dev benchmark:
#: every recovered planet sits above it (the weakest, TOI-700 b at BLS SNR
#: 5.2, at 3.7 sigma) and the two HD 63433 rotation artifacts at BLS SNR
#: 89 and 104 come out at 1.1 and 0.3 sigma.
FIT_MIN_DEPTH_SIGMA = 3.0

#: a/R* consistency (profile-likelihood test). The free fit is compared with a
#: second fit whose a/R* is confined to the catalog value's +/- 3 sigma range;
#: the candidate is flagged when that constrained fit is worse by more than
#: DENSITY_DCHI2_MIN (9 = 3 sigma for one parameter of interest) AND the free
#: fit's density differs from the catalog density by more than a factor of
#: DENSITY_RATIO_MAX. The second condition keeps a merely imprecise catalog
#: density (TIC masses come from log g and are often 20-50% off) from
#: flagging a high-SNR planet whose a/R* is pinned to a few percent.
DENSITY_RATIO_MAX = 3.0
DENSITY_DCHI2_MIN = 9.0

#: Floor on the fractional (log) error of the fitted density: the b to a/R*
#: degeneracy makes the covariance optimistic when b sits at a bound.
DENSITY_FIT_LOG_ERR_FLOOR = 0.15

#: Red-noise factor (Winn et al. 2008 "beta"): the ratio of the scatter of
#: time-binned residuals to the white-noise expectation, over bin widths from
#: a sixth to a half of T14. Correlated residuals (rotation, scattered light)
#: inflate every chi-square difference by about beta^2, so the profile
#: delta chi2 of the density test is divided by beta^2 before it is compared
#: with DENSITY_DCHI2_MIN, and the reported depth error is multiplied by
#: beta. Measured need: HD 63433 c (young, spotted host) came out at
#: delta chi2 = 70 on white-noise errors and would have been flagged.
BETA_MAX = 5.0

#: Floor on the half-width (in ln a/R*) of the constrained fit's a/R* range,
#: so a catalog density quoted with a tiny error is not pinned exactly.
DENSITY_LOG_HALFWIDTH_FLOOR = 0.05

#: Among least-squares starts whose chi-square agrees to within this, the
#: least grazing solution (lowest b) is preferred: the b to a/R* degeneracy
#: otherwise lets noise pick a V-shaped solution for a real small planet.
START_TIE_DCHI2 = 1.0

#: Odd/even from the fit: flagged when the parity depths differ by more than
#: ODD_EVEN_SIGMA sigma AND ODD_EVEN_MIN_FRACTION of the mean, with at least
#: ODD_EVEN_MIN_EVENTS events of each parity. The error of each parity mean
#: is the LARGER of the white-noise error and the empirical event-to-event
#: scatter divided by sqrt(n): on bright stars the per-transit depth varies
#: with residual systematics far more than photon noise says (Pi Men c came
#: out 7.5 "sigma" odd/even-different on white noise alone), and the
#: empirical scatter is what the significance must be measured against.
ODD_EVEN_SIGMA = 4.0
ODD_EVEN_MIN_FRACTION = 0.25
ODD_EVEN_MIN_EVENTS = 3


def _supersample_for(exp_time_days: float) -> int:
    """Sub-samples per cadence for the exposure-time integration."""
    minutes = exp_time_days * 1440.0
    if minutes < 4.0:
        return 1
    if minutes < 12.0:
        return 3
    if minutes < 22.0:
        return 5
    return 7


@dataclass
class TransitFit:
    success: bool = False
    method: str = "least_squares"
    message: str = ""
    # fitted parameters (adopted solution)
    period: float = 0.0
    period_err: float = 0.0
    t0: float = 0.0
    t0_err: float = 0.0
    rp_rs: float = 0.0
    rp_rs_err: float = 0.0
    a_rs: float = 0.0
    a_rs_err: float = 0.0
    b: float = 0.0
    b_err: float = 0.0
    inc_deg: float = 90.0
    f0: float = 1.0
    f0_err: float = 0.0
    u1: float = 0.0
    u2: float = 0.0
    ld_source: str = ""
    period_fitted: bool = True
    density_prior_adopted: bool = False
    # the free fit, kept whatever was adopted
    free_rp_rs: float = 0.0
    free_a_rs: float = 0.0
    free_b: float = 0.0
    free_chi2: float = 0.0
    # derived
    duration_days: float = 0.0          # T14
    duration_err: float = 0.0
    t23_days: float = 0.0               # full-depth duration (0 when grazing)
    depth_ppt: float = 0.0              # maximum depth of the model
    depth_err: float = 0.0              # statistical, at the fitted shape
    depth_err_shape: float = 0.0        # including the shape degeneracy
    depth_mean_ppt: float = 0.0         # duration-averaged depth
    rp_rearth: Optional[float] = None
    rp_rearth_err: Optional[float] = None
    rp_rjup: Optional[float] = None
    rp_rjup_err: Optional[float] = None
    rho_star_fit_cgs: float = 0.0       # from the FREE fit
    rho_star_fit_err: float = 0.0
    rho_star_cat_cgs: Optional[float] = None
    rho_star_cat_err: Optional[float] = None
    rho_source: str = ""
    a_rs_star: Optional[float] = None     # a/R* implied by the catalog density
    a_rs_star_err: Optional[float] = None
    a_rs_ratio: Optional[float] = None    # free fit / star
    density_ratio: Optional[float] = None # free fit / catalog
    density_sigma: Optional[float] = None # covariance-based (informational)
    density_dchi2: Optional[float] = None # chi2(constrained) - chi2(free), white-noise errors
    density_dchi2_eff: Optional[float] = None  # the same divided by beta^2
    beta_red_noise: float = 1.0
    depth_err_white: float = 0.0          # statistical depth error before the beta scaling
    a_rs_inconsistent: bool = False
    a_rs_direction: str = ""              # "low" (fit less dense) | "high" | ""
    consistency_note: str = ""
    grazing: bool = False                 # b + Rp/R* > 1 in the adopted fit
    rp_rs_constrained: bool = True        # Rp/R* error below half its value
    # fit statistics (adopted solution)
    n_points: int = 0
    n_in_transit: int = 0
    n_transits: int = 0
    chi2: float = 0.0
    chi2_flat: float = 0.0
    reduced_chi2: float = 0.0
    delta_bic: float = 0.0                # BIC(flat) - BIC(transit); > 0 favours the transit
    sigma_used: float = 0.0
    exp_time_days: float = 0.0
    supersample: int = 1
    window_durations: float = 0.0
    # odd/even from the fitted template
    odd_even: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def planet_shaped(self) -> bool:
        return bool(self.success and self.rp_rs <= MAX_PLANET_RP_RS and not self.a_rs_inconsistent)

    @property
    def depth_significant(self) -> bool:
        """The model sees a dip at FIT_MIN_DEPTH_SIGMA or better (white noise)."""
        err = self.depth_err_white or self.depth_err
        return bool(self.success and self.depth_ppt > 0.0 and err > 0.0
                    and self.depth_ppt >= FIT_MIN_DEPTH_SIGMA * err)


def red_noise_beta(time: np.ndarray, resid: np.ndarray, sigma: np.ndarray, t14: float,
                   cadence: float) -> float:
    """Winn et al. (2008) beta from time-binned normalised residuals.

    For bin widths from T14/6 to T14/2 (at least two cadences) the residuals
    ``resid / sigma`` are averaged in contiguous time bins; beta is the ratio
    of the observed scatter of the bin means to the 1/sqrt(N) expectation,
    corrected for the number of bins, median over the widths, floored at 1.
    """
    r = np.asarray(resid, dtype=float) / np.asarray(sigma, dtype=float)
    t = np.asarray(time, dtype=float)
    if r.size < 50 or t14 <= 0 or cadence <= 0:
        return 1.0
    lo = max(t14 / 6.0, 2.0 * cadence)
    hi = max(t14 / 2.0, 3.0 * cadence)
    betas = []
    for w in np.linspace(lo, hi, 5):
        idx = np.floor((t - t.min()) / w).astype(int)
        n = np.bincount(idx)
        s = np.bincount(idx, weights=r)
        keep = n >= 2
        if keep.sum() < 8:
            continue
        means = s[keep] / n[keep]
        n_mean = float(n[keep].mean())
        m = int(keep.sum())
        sigma_n = float(np.std(means, ddof=1))
        expected = 1.0 / math.sqrt(n_mean)
        if expected <= 0:
            continue
        betas.append(sigma_n / expected * math.sqrt(m / (m - 1.0)))
    if not betas:
        return 1.0
    return float(np.clip(np.median(betas), 1.0, BETA_MAX))


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class _Model:
    """Thin batman wrapper holding the time array and the fixed settings."""

    def __init__(self, time: np.ndarray, u: tuple[float, float],
                 exp_time_days: Optional[float], supersample: int):
        import batman
        self.params = batman.TransitParams()
        self.params.ecc = 0.0
        self.params.w = 90.0
        self.params.u = [float(u[0]), float(u[1])]
        self.params.limb_dark = "quadratic"
        self.params.t0 = 0.0
        self.params.per = 1.0
        self.params.rp = 0.01
        self.params.a = 10.0
        self.params.inc = 90.0
        kw = {}
        if exp_time_days and exp_time_days > 0 and supersample > 1:
            kw = {"supersample_factor": int(supersample), "exp_time": float(exp_time_days)}
        self.model = batman.TransitModel(self.params, np.asarray(time, dtype=float), **kw)

    def __call__(self, t0: float, period: float, rp: float, a_rs: float, b: float) -> np.ndarray:
        p = self.params
        p.t0 = float(t0)
        p.per = float(period)
        p.rp = float(rp)
        p.a = float(a_rs)
        cosi = np.clip(b / a_rs, -1.0, 1.0)
        p.inc = float(np.degrees(np.arccos(cosi)))
        return self.model.light_curve(p)


def transit_duration_t14(period: float, a_rs: float, b: float, rp_rs: float) -> float:
    """T14 for a circular orbit (Winn 2010 eq. 14); 0 when there is no transit."""
    if a_rs <= 1.0:
        return 0.0
    sin_i = math.sqrt(max(1.0 - (b / a_rs) ** 2, 0.0))
    arg = (1.0 + rp_rs) ** 2 - b ** 2
    if arg <= 0.0 or sin_i <= 0.0:
        return 0.0
    x = math.sqrt(arg) / (a_rs * sin_i)
    return float(period / math.pi * math.asin(min(x, 1.0)))


def transit_duration_t23(period: float, a_rs: float, b: float, rp_rs: float) -> float:
    """T23 (full-depth duration); 0 for a grazing transit."""
    if a_rs <= 1.0:
        return 0.0
    sin_i = math.sqrt(max(1.0 - (b / a_rs) ** 2, 0.0))
    arg = (1.0 - rp_rs) ** 2 - b ** 2
    if arg <= 0.0 or sin_i <= 0.0:
        return 0.0
    x = math.sqrt(arg) / (a_rs * sin_i)
    return float(period / math.pi * math.asin(min(x, 1.0)))


def _model_depths(u: tuple[float, float], period: float, rp: float, a_rs: float, b: float,
                  t14: float) -> tuple[float, float]:
    """(maximum depth, duration-averaged depth) of the un-integrated model."""
    import batman
    if t14 <= 0.0 or rp <= 0.0:
        return 0.0, 0.0
    params = batman.TransitParams()
    params.t0 = 0.0
    params.per = period
    params.rp = rp
    params.a = a_rs
    params.inc = float(np.degrees(np.arccos(np.clip(b / a_rs, -1.0, 1.0))))
    params.ecc = 0.0
    params.w = 90.0
    params.u = [u[0], u[1]]
    params.limb_dark = "quadratic"
    t = np.linspace(-0.5 * t14, 0.5 * t14, 201)
    m = batman.TransitModel(params, t).light_curve(params)
    d = 1.0 - m
    return float(d.max()), float(d.mean())


# ---------------------------------------------------------------------------
# Fit
# ---------------------------------------------------------------------------

def _select_window(time: np.ndarray, period: float, t0: float, half_window: float):
    phase = ((time - t0 + 0.5 * period) % period) - 0.5 * period
    return phase, np.abs(phase) <= half_window


def fit_transit(
    time: np.ndarray,
    flux: np.ndarray,
    flux_err: Optional[np.ndarray] = None,
    *,
    period: float,
    t0: float,
    duration: float,
    depth_ppt: Optional[float] = None,
    exp_time_days: Optional[float] = None,
    u: Optional[tuple[float, float]] = None,
    stellar: Optional[StellarParams] = None,
    teff: Optional[float] = None,
    logg: Optional[float] = None,
    fit_period: bool = True,
    window_durations: float = 3.0,
    max_points: int = 40000,
    mcmc: bool = False,
    mcmc_walkers: int = 32,
    mcmc_steps: int = 1500,
    mcmc_burn: int = 500,
    seed: int = 0,
    odd_even: bool = True,
    density_test: bool = True,
) -> TransitFit:
    """Fit a limb-darkened transit at a BLS ephemeris.

    Parameters
    ----------
    time, flux, flux_err:
        Detrended light curve (flux normalised near 1). ``flux_err`` may be
        None or non-positive; the residual scatter is then used.
    period, t0, duration:
        Starting ephemeris (days). ``duration`` sizes the fit window.
    depth_ppt:
        Starting depth (ppt); Rp/R* starts at sqrt(depth).
    exp_time_days:
        Exposure time for the integration of the model over each cadence;
        None uses the median cadence of the windowed data.
    u / stellar / teff / logg:
        Limb-darkening coefficients, or the star they are looked up for.
        ``stellar`` also supplies the catalog density for the consistency
        test (and the density prior) and the radius for Rp.
    fit_period:
        False keeps the period fixed (cheap gate-time fit).
    mcmc:
        Run emcee from the adopted least-squares solution and report
        posterior medians and 16-84% half-widths instead of the covariance.
    density_test:
        False skips the constrained fit (no consistency test, no prior).
    """
    fit = TransitFit()
    fit.period_fitted = bool(fit_period)
    fit.window_durations = float(window_durations)

    t = np.asarray(time, dtype=float)
    f = np.asarray(flux, dtype=float)
    ok = np.isfinite(t) & np.isfinite(f)
    e = None
    if flux_err is not None:
        e = np.asarray(flux_err, dtype=float)
        if e.shape != t.shape:
            e = None
    t, f = t[ok], f[ok]
    if e is not None:
        e = e[ok]
    if t.size < 20 or period <= 0.0 or duration <= 0.0:
        fit.message = "too few finite points or invalid ephemeris"
        return fit

    order = np.argsort(t)
    t, f = t[order], f[order]
    if e is not None:
        e = e[order]

    cad = float(np.median(np.diff(t))) if t.size > 1 else 0.0
    if exp_time_days is None or not (exp_time_days > 0):
        exp_time_days = cad if cad > 0 else 2.0 / 1440.0
    dur0 = max(float(duration), 2.0 * exp_time_days)
    half_window = min(window_durations * dur0, 0.45 * period)

    phase, sel = _select_window(t, period, t0, half_window)
    if int(sel.sum()) < 20:
        fit.message = f"only {int(sel.sum())} cadences inside the fit window"
        return fit
    tw, fw, pw = t[sel], f[sel], phase[sel]
    ew = e[sel] if e is not None else None

    # Sub-sample away from the transit when the window is very large.
    if tw.size > max_points:
        rng = np.random.default_rng(seed)
        core = np.abs(pw) <= 1.5 * dur0
        n_extra = max(max_points - int(core.sum()), 0)
        idx_out = np.where(~core)[0]
        keep = np.zeros(tw.size, dtype=bool)
        keep[core] = True
        if n_extra and idx_out.size:
            keep[rng.choice(idx_out, size=min(n_extra, idx_out.size), replace=False)] = True
        tw, fw, pw = tw[keep], fw[keep], pw[keep]
        ew = ew[keep] if ew is not None else None

    # Per-point sigma: supplied errors when usable, else the robust scatter of
    # the out-of-transit part of the window.
    oot = np.abs(pw) > 0.75 * dur0
    resid_ref = fw[oot] if oot.sum() >= 10 else fw
    mad = float(np.median(np.abs(resid_ref - np.median(resid_ref))))
    sigma_robust = 1.4826 * mad if mad > 0 else float(np.std(resid_ref)) or 1e-4
    if ew is not None and np.all(np.isfinite(ew)) and np.all(ew > 0):
        sig = ew.copy()
        if np.median(sig) < 0.3 * sigma_robust:
            sig = np.full(tw.size, sigma_robust)
    else:
        sig = np.full(tw.size, sigma_robust)
    fit.sigma_used = float(np.median(sig))

    # Limb darkening
    if u is None:
        te = teff if teff is not None else (stellar.teff if stellar else None)
        lg = logg if logg is not None else (stellar.logg if stellar else None)
        ldc = limb_darkening.quadratic_ld(te, lg)
        u = (ldc.u1, ldc.u2)
        fit.ld_source = f"{ldc.source} (Teff {ldc.teff_used:.0f} K, logg {ldc.logg_used:.2f})"
    else:
        fit.ld_source = "supplied"
    fit.u1, fit.u2 = float(u[0]), float(u[1])

    supersample = _supersample_for(exp_time_days)
    fit.exp_time_days = float(exp_time_days)
    fit.supersample = int(supersample)
    model = _Model(tw, u, exp_time_days, supersample)

    # Starting values and bounds
    core_sel = np.abs(pw) < 0.25 * dur0
    if depth_ppt:
        depth0 = max(float(depth_ppt) / 1000.0, 1e-5)
    elif core_sel.sum() >= 3:
        depth0 = max(1.0 - float(np.median(fw[core_sel])), 1e-5)
    else:
        depth0 = 1e-3
    rp0 = float(np.clip(math.sqrt(depth0), 0.005, 0.5))
    a_star, a_star_err, rho_how = (stellar.a_over_rs(period) if stellar is not None else (None, None, "no_star"))
    if a_star is not None and a_star > 1.5:
        a0 = float(a_star)
    else:
        a0 = float(np.clip(period * (1.0 + rp0) / (math.pi * dur0), 1.5, 500.0))

    t_span = float(tw.max() - tw.min())
    n_orbits = max(t_span / period, 1.0)
    p_half = max(1e-5 * period, 0.5 * dur0 / n_orbits)
    lo = [t0 - 0.75 * dur0, 1e-3, math.log(1.05), 0.0, 0.9]
    hi = [t0 + 0.75 * dur0, 0.9, math.log(2000.0), 1.2, 1.1]
    if fit_period:
        lo.insert(1, period - p_half)
        hi.insert(1, period + p_half)
    i_t0 = 0
    i_p = 1 if fit_period else None
    i_rp = 2 if fit_period else 1
    i_la = 3 if fit_period else 2
    i_b = 4 if fit_period else 3
    i_f0 = 5 if fit_period else 4

    def unpack(x):
        if fit_period:
            return x[0], x[1], x[2], math.exp(x[3]), x[4], x[5]
        return x[0], period, x[1], math.exp(x[2]), x[3], x[4]

    def residuals(x):
        tt0, per, rp, a_rs, b, f0 = unpack(x)
        m = f0 * model(tt0, per, rp, a_rs, b)
        return (m - fw) / sig

    from scipy.optimize import least_squares

    def run_starts(lo_b, hi_b, starts):
        """Least squares from several (b, a/R*) starts; ties go to the lower b."""
        found = []
        for b0, aa0 in starts:
            aa0 = float(np.clip(aa0, math.exp(lo_b[i_la]) * 1.001, math.exp(hi_b[i_la]) * 0.999))
            x0 = [t0, rp0, math.log(aa0), b0, 1.0]
            if fit_period:
                x0.insert(1, period)
            x0 = np.clip(np.asarray(x0, dtype=float), np.asarray(lo_b) + 1e-9, np.asarray(hi_b) - 1e-9)
            try:
                r = least_squares(residuals, x0, bounds=(lo_b, hi_b), method="trf",
                                  x_scale="jac", max_nfev=3000)
            except Exception as exc:                              # pragma: no cover
                logger.debug("transit fit start (b=%.2f) failed: %s", b0, exc)
                continue
            found.append(r)
        if not found:
            return None
        found.sort(key=lambda r: r.cost)
        chosen = found[0]
        for r in found[1:]:
            if 2.0 * (r.cost - found[0].cost) < START_TIE_DCHI2 and r.x[i_b] < chosen.x[i_b]:
                chosen = r
        return chosen

    free = run_starts(lo, hi, [(0.2, a0), (0.6, a0), (0.85, 0.7 * a0)])
    if free is None:
        fit.message = "least squares failed from every start"
        return fit
    _, _, f_rp, f_a, f_b, _ = unpack(free.x)
    fit.free_rp_rs, fit.free_a_rs, fit.free_b = float(f_rp), float(f_a), float(f_b)
    fit.free_chi2 = float(2.0 * free.cost)
    fit.rho_star_fit_cgs = density_from_a_rs(f_a, unpack(free.x)[1])
    fit.rho_star_fit_err = float(3.0 * fit.rho_star_fit_cgs * DENSITY_FIT_LOG_ERR_FLOOR)

    # ── Density consistency (profile test) and the density prior ─────────────
    best = free
    lo_used, hi_used = lo, hi
    rho_cat = rho_cat_err = None
    if stellar is not None:
        rho_cat, rho_cat_err, how = stellar.density_cgs()
        fit.rho_source = how
        if rho_cat is None or rho_cat <= 0:
            fit.consistency_note = f"no catalog density ({how}); a/R* consistency not tested"
            rho_cat = None
    else:
        fit.consistency_note = "no stellar parameters; a/R* consistency not tested"

    if rho_cat is not None:
        per_free = unpack(free.x)[1]
        fit.rho_star_cat_cgs = float(rho_cat)
        fit.rho_star_cat_err = float(rho_cat_err)
        fit.a_rs_star = float(a_rs_from_density(rho_cat, per_free))
        fit.a_rs_star_err = float(fit.a_rs_star * (rho_cat_err / rho_cat) / 3.0)
        fit.a_rs_ratio = float(f_a / fit.a_rs_star)
        ratio = fit.rho_star_fit_cgs / rho_cat
        fit.density_ratio = float(ratio)
        log_err = math.sqrt(DENSITY_FIT_LOG_ERR_FLOOR ** 2 + (rho_cat_err / rho_cat) ** 2)
        fit.density_sigma = float(abs(math.log(ratio)) / log_err) if log_err > 0 else 0.0
        fit.a_rs_direction = "low" if ratio < 1.0 else "high"
        far = abs(math.log(ratio)) > math.log(DENSITY_RATIO_MAX)
        dchi2 = 0.0
        con = None
        if density_test:
            half = max((rho_cat_err / rho_cat), DENSITY_LOG_HALFWIDTH_FLOOR)   # 3 sigma in ln a/R* = sigma_lnrho
            la_star = math.log(fit.a_rs_star)
            lo_c, hi_c = list(lo), list(hi)
            lo_c[i_la] = max(lo[i_la], la_star - half)
            hi_c[i_la] = min(hi[i_la], la_star + half)
            if hi_c[i_la] > lo_c[i_la]:
                a_mid = math.exp(0.5 * (lo_c[i_la] + hi_c[i_la]))
                con = run_starts(lo_c, hi_c, [(0.2, a_mid), (0.6, a_mid), (0.9, a_mid)])
                if con is not None:
                    dchi2 = float(2.0 * (con.cost - free.cost))
                    if dchi2 < DENSITY_DCHI2_MIN:
                        best = con
                        lo_used, hi_used = lo_c, hi_c
                        fit.density_prior_adopted = True
        fit.density_dchi2 = float(dchi2)
        # Red noise inflates chi-square differences by about beta^2; measure
        # beta on the FREE fit's residuals and discount the profile statistic.
        _t0f, _pf, _rpf, _af, _bf, _f0f = unpack(free.x)
        t14_free = transit_duration_t14(_pf, _af, _bf, _rpf)
        beta = red_noise_beta(tw, fw - _f0f * model(_t0f, _pf, _rpf, _af, _bf), sig,
                              t14_free if t14_free > 0 else dur0, exp_time_days)
        fit.beta_red_noise = float(beta)
        fit.density_dchi2_eff = float(dchi2 / beta ** 2)
        fit.a_rs_inconsistent = bool(far and fit.density_dchi2_eff > DENSITY_DCHI2_MIN)
        fit.consistency_note = (
            f"free-fit a/R* = {f_a:.2f} (b = {f_b:.2f}) against {fit.a_rs_star:.2f} "
            f"+/- {fit.a_rs_star_err:.2f} from the catalog density "
            f"({fit.rho_star_fit_cgs:.3f} vs {rho_cat:.3f} g/cc, ratio {ratio:.2f}; "
            f"profile delta chi2 {dchi2:.1f} with a/R* held in the catalog range, "
            f"{fit.density_dchi2_eff:.1f} after the red-noise beta = {beta:.2f}; {fit.rho_source})"
        )
        if fit.a_rs_inconsistent:
            fit.consistency_note += (
                " FLAGGED: the transit shape needs a star "
                + ("far less dense" if ratio < 1 else "far denser")
                + " than the catalog star; "
                + ("diluted eclipse, grazing stellar companion or blend" if ratio < 1
                   else "eccentric orbit, wrong period harmonic or wrong host")
                + "."
            )
        elif fit.density_prior_adopted:
            fit.consistency_note += "; catalog density adopted as a prior for the reported parameters"

    x = best.x
    tt0, per, rp, a_rs, b, f0 = unpack(x)
    n = tw.size
    k = x.size
    chi2 = float(2.0 * best.cost)
    dof = max(n - k, 1)
    red = chi2 / dof
    f_flat = float(np.sum(fw / sig ** 2) / np.sum(1.0 / sig ** 2))
    chi2_flat = float(np.sum(((fw - f_flat) / sig) ** 2))
    fit.chi2, fit.chi2_flat, fit.reduced_chi2 = chi2, chi2_flat, float(red)
    fit.delta_bic = float((chi2_flat + 1 * math.log(n)) - (chi2 + k * math.log(n)))
    fit.n_points = int(n)

    try:
        J = best.jac
        cov = np.linalg.pinv(J.T @ J) * max(red, 1.0)
        err = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    except Exception:                                             # pragma: no cover
        cov = np.zeros((k, k))
        err = np.zeros(k)

    fit.success = True
    fit.method = "least_squares"
    fit.message = best.message

    # Optional MCMC refinement from the adopted solution and bounds
    samples = None
    if mcmc:
        try:
            import emcee
            rng = np.random.default_rng(seed)
            lo_a, hi_a = np.asarray(lo_used), np.asarray(hi_used)

            def log_prob(xx):
                if np.any(xx < lo_a) or np.any(xx > hi_a):
                    return -np.inf
                r = residuals(xx)
                return -0.5 * float(np.dot(r, r))

            scale = np.where(err > 0, err, 1e-4 * np.abs(x) + 1e-6)
            scale = np.minimum(scale, 0.25 * (hi_a - lo_a))
            p0 = x + scale * 0.1 * rng.standard_normal((mcmc_walkers, k))
            p0 = np.clip(p0, lo_a + 1e-9, hi_a - 1e-9)
            sampler = emcee.EnsembleSampler(mcmc_walkers, k, log_prob)
            sampler.run_mcmc(p0, mcmc_steps, progress=False)
            samples = sampler.get_chain(discard=mcmc_burn, flat=True)
            x = np.median(samples, axis=0)
            tt0, per, rp, a_rs, b, f0 = unpack(x)
            err = 0.5 * (np.percentile(samples, 84, axis=0) - np.percentile(samples, 16, axis=0))
            fit.method = "emcee"
            fit.message = f"emcee {mcmc_walkers} walkers x {mcmc_steps} steps (burn {mcmc_burn})"
        except Exception as exc:
            fit.notes.append(f"MCMC failed ({exc}); least-squares covariance kept")

    # Store parameters
    fit.t0, fit.t0_err = float(tt0), float(err[i_t0])
    fit.period = float(per)
    fit.period_err = float(err[i_p]) if i_p is not None else 0.0
    fit.rp_rs, fit.rp_rs_err = float(rp), float(err[i_rp])
    fit.a_rs, fit.a_rs_err = float(a_rs), float(a_rs * err[i_la])
    fit.b, fit.b_err = float(b), float(err[i_b])
    fit.f0, fit.f0_err = float(f0), float(err[i_f0])
    fit.inc_deg = float(np.degrees(np.arccos(np.clip(b / a_rs, -1.0, 1.0))))
    fit.grazing = bool(b + rp > 1.0)
    fit.rp_rs_constrained = bool(rp > 0 and err[i_rp] < 0.5 * rp)
    if not fit.rp_rs_constrained:
        fit.notes.append("Rp/R* is not constrained by the covariance (degenerate with b)")

    # Statistical depth error at the fitted shape (linear scale on the template)
    d_unit = 1.0 - model(tt0, per, rp, a_rs, b)
    den = float(np.sum(d_unit ** 2 / sig ** 2))
    depth_scale_err = math.sqrt(max(red, 1.0) / den) if den > 0 else 0.0

    # Derived quantities with Monte-Carlo propagation
    t14 = transit_duration_t14(per, a_rs, b, rp)
    t23 = transit_duration_t23(per, a_rs, b, rp)
    d_max, d_mean = _model_depths(u, per, rp, a_rs, b, t14)
    fit.duration_days, fit.t23_days = t14, t23
    fit.depth_ppt, fit.depth_mean_ppt = d_max * 1000.0, d_mean * 1000.0
    fit.depth_err_white = float(depth_scale_err * fit.depth_ppt)
    if fit.beta_red_noise <= 1.0 and rho_cat is None:
        # no density test ran: measure beta here on the adopted solution
        fit.beta_red_noise = float(red_noise_beta(
            tw, fw - f0 * model(tt0, per, rp, a_rs, b), sig, t14 if t14 > 0 else dur0, exp_time_days))
    fit.depth_err = float(fit.depth_err_white * fit.beta_red_noise)

    rng = np.random.default_rng(seed + 1)
    if samples is not None and samples.shape[0] >= 200:
        draws = samples[rng.choice(samples.shape[0], size=min(600, samples.shape[0]), replace=False)]
    else:
        try:
            draws = rng.multivariate_normal(x, cov, size=600, method="cholesky")
        except Exception:
            draws = x + err * rng.standard_normal((600, k))
    draws = np.clip(draws, np.asarray(lo_used), np.asarray(hi_used))
    t14s, dmaxs = [], []
    for row in draws:
        _d_t0, d_per, d_rp, d_a, d_b, _ = unpack(row)
        tt = transit_duration_t14(d_per, d_a, d_b, d_rp)
        if tt <= 0:
            continue
        t14s.append(tt)
        if len(dmaxs) < 150:
            dm, _ = _model_depths(u, d_per, d_rp, d_a, d_b, tt)
        else:
            dm = d_rp ** 2 * (d_max / max(rp ** 2, 1e-12))
        dmaxs.append(dm)
    if len(t14s) >= 20:
        fit.duration_err = float(np.std(t14s))
        fit.depth_err_shape = float(np.std(dmaxs) * 1000.0)
    else:
        fit.duration_err = 0.0
        fit.depth_err_shape = float(2.0 * rp * err[i_rp] * 1000.0)

    # Planet radius from the stellar radius
    if stellar is not None:
        r_star, r_err, _assumed = stellar.radius_with_err()
        if r_star is not None:
            rp_rsun = rp * r_star
            frac = math.sqrt((err[i_rp] / rp) ** 2 + (r_err / r_star) ** 2) if rp > 0 else 0.0
            fit.rp_rearth = float(rp_rsun * REARTH_PER_RSUN)
            fit.rp_rearth_err = float(fit.rp_rearth * frac)
            fit.rp_rjup = float(rp_rsun * RJUP_PER_RSUN)
            fit.rp_rjup_err = float(fit.rp_rjup * frac)

    # Transit count inside the window
    idx = np.round((tw - tt0) / per).astype(int)
    in_tr = np.abs(((tw - tt0 + 0.5 * per) % per) - 0.5 * per) <= 0.5 * max(t14, dur0)
    fit.n_in_transit = int(in_tr.sum())
    fit.n_transits = int(np.unique(idx[in_tr]).size) if in_tr.any() else 0

    if odd_even:
        try:
            fit.odd_even = _odd_even_parity_fit(tw, fw, sig, model, fit)
        except Exception as exc:                                  # pragma: no cover
            fit.odd_even = {"available": False, "note": f"odd/even fit failed ({exc})"}
    return fit


def _odd_even_parity_fit(tw, fw, sig, model: _Model, fit: TransitFit) -> dict:
    """Scale the fitted template separately on odd and even transits.

    ``flux = f0 * (1 - k * d(t))`` with ``d`` the unit-depth template; ``k`` is
    solved by weighted linear least squares per parity, so the depth of each
    parity comes with an error from the same noise model as the fit.
    """
    d = 1.0 - model(fit.t0, fit.period, fit.rp_rs, fit.a_rs, fit.b)
    if not np.any(d > 0):
        return {"available": False, "note": "template has no transit"}
    y = 1.0 - fw / fit.f0
    w = 1.0 / sig ** 2
    idx = np.round((tw - fit.t0) / fit.period).astype(int)
    infl = max(fit.reduced_chi2, 1.0)

    # Per-event depth scale k_i (weighted linear fit of the template to each
    # transit that has in-transit points), with its white-noise error.
    per_event: dict[int, tuple[float, float]] = {}
    for i in np.unique(idx[d > 0]):
        m = idx == i
        dm = d[m]
        den = float(np.sum(w[m] * dm * dm))
        if den <= 0 or not np.any(dm > 0):
            continue
        k_i = float(np.sum(w[m] * dm * y[m])) / den
        per_event[int(i)] = (k_i, math.sqrt(infl / den))
    if not per_event:
        return {"available": False, "note": "no transit with in-transit points"}

    out: dict = {
        "available": True,
        "per_event": [{"index": i, "depth_ppt": float(k * fit.depth_ppt),
                       "depth_err": float(e * fit.depth_ppt)} for i, (k, e) in sorted(per_event.items())],
    }
    parity_depths = {}
    for name, par in (("odd", 1), ("even", 0)):
        ks = np.array([k for i, (k, _) in per_event.items() if abs(i) % 2 == par])
        es = np.array([e for i, (_, e) in per_event.items() if abs(i) % 2 == par])
        if ks.size == 0:
            return {"available": False, "note": f"no {name} transit inside the window"}
        wi = 1.0 / es ** 2
        k = float(np.sum(wi * ks) / np.sum(wi))
        k_err_white = float(1.0 / math.sqrt(np.sum(wi)))
        k_err_emp = float(np.std(ks, ddof=1) / math.sqrt(ks.size)) if ks.size >= 2 else 0.0
        k_err = max(k_err_white, k_err_emp)
        n_ev = int(ks.size)
        parity_depths[name] = (k * fit.depth_ppt, k_err * fit.depth_ppt, n_ev)
        out[f"depth_{name}_ppt"] = float(k * fit.depth_ppt)
        out[f"depth_{name}_err"] = float(k_err * fit.depth_ppt)
        out[f"depth_{name}_err_white"] = float(k_err_white * fit.depth_ppt)
        out[f"n_{name}"] = n_ev
    (do, eo, no), (de, ee, ne) = parity_depths["odd"], parity_depths["even"]
    diff = abs(do - de)
    err = math.sqrt(eo ** 2 + ee ** 2)
    mean = 0.5 * (abs(do) + abs(de))
    out["delta_sigma"] = float(diff / err) if err > 0 else 0.0
    out["delta_fraction"] = float(diff / mean) if mean > 0 else 0.0
    out["significant"] = bool(
        out["delta_sigma"] > ODD_EVEN_SIGMA
        and out["delta_fraction"] > ODD_EVEN_MIN_FRACTION
        and no >= ODD_EVEN_MIN_EVENTS and ne >= ODD_EVEN_MIN_EVENTS
    )
    out["note"] = (
        f"odd {do:.3f} +/- {eo:.3f} ppt ({no} events), even {de:.3f} +/- {ee:.3f} ppt "
        f"({ne} events), difference {out['delta_sigma']:.1f} sigma, "
        f"{100 * out['delta_fraction']:.0f}% of the mean"
    )
    return out


# ---------------------------------------------------------------------------
# Cheap entry points for the search loop and the alias resolver
# ---------------------------------------------------------------------------

def _lc_arrays(lc):
    t = np.asarray(lc.time.value, dtype=float)
    f = np.asarray(lc.flux.value, dtype=float)
    try:
        e = np.asarray(lc.flux_err.value, dtype=float)
    except Exception:
        e = None
    return t, f, e


def quick_fit(
    lc,
    period: float,
    epoch: float,
    duration: float,
    depth_ppt: float,
    *,
    stellar: Optional[StellarParams] = None,
    fit_period: bool = False,
    window_durations: float = 2.5,
    max_points: int = 20000,
    density_test: bool = True,
) -> TransitFit:
    """Fixed-period fit on a lightkurve LightCurve (binned working curve)."""
    t, f, e = _lc_arrays(lc)
    return fit_transit(
        t, f, e, period=period, t0=epoch, duration=duration, depth_ppt=depth_ppt,
        stellar=stellar, fit_period=fit_period, window_durations=window_durations,
        max_points=max_points, density_test=density_test,
    )


def odd_even_from_fit(
    lc,
    period: float,
    epoch: float,
    duration: float,
    depth_ppt: float,
) -> dict:
    """Odd/even depth test at ``period`` from a fixed-period template fit.

    Returns the ``odd_even`` dict of :func:`fit_transit` (``available``,
    parity depths with errors, ``delta_sigma``, ``significant``) or a dict
    with ``available=False`` and a reason.
    """
    try:
        fit = quick_fit(lc, period, epoch, duration, depth_ppt, fit_period=False, density_test=False)
    except Exception as exc:                                      # pragma: no cover
        return {"available": False, "note": f"fit failed ({exc})"}
    if not fit.success:
        return {"available": False, "note": fit.message}
    oe = dict(fit.odd_even or {})
    oe.setdefault("available", False)
    oe["fit_rp_rs"] = fit.rp_rs
    oe["fit_depth_ppt"] = fit.depth_ppt
    return oe
