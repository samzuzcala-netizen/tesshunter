"""Quadratic limb-darkening coefficients for the TESS band (Claret 2017).

The tables were fetched from Vizier (``J/A+A/600/A30``) on 2026-09-02 and
reduced to solar metallicity:

* ``data/limb_darkening/claret2017_tess_quadratic_atlas_z0_xi2.csv`` —
  ATLAS plane-parallel models, Z = 0, microturbulence 2 km/s, Teff 3500 to
  50000 K, log g 0 to 5 (Claret 2017 table 25).
* ``data/limb_darkening/claret2017_tess_quadratic_phoenix_z0_q.csv`` —
  PHOENIX spherical models (quasi-spherical ``q`` treatment), Z = 0, Teff
  1500 to 12000 K, log g 2.5 to 6 (Claret 2017 tables 4 and 5; model
  ``PC`` = PHOENIX-COND for Teff >= 2300 K, ``PD`` = PHOENIX-DRIFT below).

Both tables carry the least-squares (``lsm``) and power-2-like flux-conserving
(``pcm``) coefficient sets; the least-squares set is the default because it
is the one most transit fits in the literature adopt.

:func:`quadratic_ld` interpolates linearly in (Teff, log g) inside the table
that covers the star (ATLAS for Teff >= 3500 K, PHOENIX below) and falls back
to the nearest tabulated point outside the grid. When the tables are missing
the coarse anchors of :mod:`tesshunter.survey` are used and the source says
so, so a fit can never silently run on made-up coefficients.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from .config import PROJECT_ROOT

logger = logging.getLogger(__name__)

LD_DIR = PROJECT_ROOT / "data" / "limb_darkening"
ATLAS_FILE = LD_DIR / "claret2017_tess_quadratic_atlas_z0_xi2.csv"
PHOENIX_FILE = LD_DIR / "claret2017_tess_quadratic_phoenix_z0_q.csv"

#: Below this Teff the ATLAS grid has no models; PHOENIX is used.
ATLAS_TEFF_MIN = 3500.0

DEFAULT_TEFF = 5500.0
DEFAULT_LOGG = 4.5

_TABLES: dict[str, Optional[np.ndarray]] = {}


@dataclass(frozen=True)
class LDCoefficients:
    u1: float
    u2: float
    source: str          # "claret2017_atlas" | "claret2017_phoenix" | "survey_anchors"
    teff_used: float
    logg_used: float
    interpolated: bool   # False when clamped to the nearest grid point


def _load(name: str, path: Path, method: str) -> Optional[np.ndarray]:
    """Return an (n, 4) array of Teff, logg, u1, u2 or None when missing."""
    key = f"{name}:{method}"
    if key in _TABLES:
        return _TABLES[key]
    arr: Optional[np.ndarray] = None
    if path.exists():
        import pandas as pd
        df = pd.read_csv(path)
        if name == "phoenix" and "model" in df.columns:
            # Prefer PHOENIX-COND where both models exist (2300-3000 K overlap).
            keep = []
            for (teff, logg), grp in df.groupby(["Teff", "logg"]):
                if (grp["model"] == "PC").any():
                    keep.append(grp[grp["model"] == "PC"].iloc[0])
                else:
                    keep.append(grp.iloc[0])
            df = pd.DataFrame(keep)
        u1c, u2c = f"u1_{method}", f"u2_{method}"
        arr = df[["Teff", "logg", u1c, u2c]].to_numpy(dtype=float)
        arr = arr[np.all(np.isfinite(arr), axis=1)]
    else:
        logger.warning("Limb-darkening table missing: %s", path)
    _TABLES[key] = arr
    return arr


def _interp_grid(table: np.ndarray, teff: float, logg: float) -> tuple[float, float, bool]:
    """Bilinear interpolation on the irregular (Teff, logg) grid.

    Uses the two tabulated Teff values bracketing ``teff``, interpolates in
    log g along each, then in Teff. Outside the grid the nearest available
    point is used and ``interpolated`` is False.
    """
    teffs = np.unique(table[:, 0])
    loggs_all = np.unique(table[:, 1])
    inside = teffs.min() <= teff <= teffs.max() and loggs_all.min() <= logg <= loggs_all.max()
    if not inside:
        # nearest point in a scaled metric (250 K ~ 0.5 dex)
        d = ((table[:, 0] - teff) / 250.0) ** 2 + ((table[:, 1] - logg) / 0.5) ** 2
        i = int(np.argmin(d))
        return float(table[i, 2]), float(table[i, 3]), False

    i_hi = int(np.searchsorted(teffs, teff))
    i_lo = max(i_hi - 1, 0)
    i_hi = min(i_hi, teffs.size - 1)
    t_lo, t_hi = teffs[i_lo], teffs[i_hi]

    def at_teff(t: float) -> Optional[tuple[float, float]]:
        rows = table[np.isclose(table[:, 0], t)]
        if rows.size == 0:
            return None
        rows = rows[np.argsort(rows[:, 1])]
        lg = rows[:, 1]
        if logg <= lg.min():
            return float(rows[0, 2]), float(rows[0, 3])
        if logg >= lg.max():
            return float(rows[-1, 2]), float(rows[-1, 3])
        return float(np.interp(logg, lg, rows[:, 2])), float(np.interp(logg, lg, rows[:, 3]))

    lo = at_teff(t_lo)
    hi = at_teff(t_hi)
    if lo is None and hi is None:
        d = ((table[:, 0] - teff) / 250.0) ** 2 + ((table[:, 1] - logg) / 0.5) ** 2
        i = int(np.argmin(d))
        return float(table[i, 2]), float(table[i, 3]), False
    if lo is None:
        return hi[0], hi[1], False
    if hi is None or t_hi == t_lo:
        return lo[0], lo[1], t_hi == t_lo
    w = (teff - t_lo) / (t_hi - t_lo)
    return (lo[0] + w * (hi[0] - lo[0]), lo[1] + w * (hi[1] - lo[1]), True)


def quadratic_ld(
    teff: Optional[float],
    logg: Optional[float] = None,
    *,
    method: str = "lsm",
) -> LDCoefficients:
    """Quadratic (u1, u2) for the TESS band at the given Teff and log g.

    ``teff`` or ``logg`` of None (or non-finite) fall back to 5500 K / 4.5,
    which is recorded in ``teff_used`` / ``logg_used``.
    """
    t = float(teff) if teff is not None and np.isfinite(teff) and teff > 0 else DEFAULT_TEFF
    g = float(logg) if logg is not None and np.isfinite(logg) else DEFAULT_LOGG

    if t >= ATLAS_TEFF_MIN:
        table, source = _load("atlas", ATLAS_FILE, method), "claret2017_atlas"
        if table is None:
            table, source = _load("phoenix", PHOENIX_FILE, method), "claret2017_phoenix"
    else:
        table, source = _load("phoenix", PHOENIX_FILE, method), "claret2017_phoenix"
        if table is None:
            table, source = _load("atlas", ATLAS_FILE, method), "claret2017_atlas"

    if table is None:
        from .survey import limb_darkening_for_teff
        u1, u2 = limb_darkening_for_teff(t)
        return LDCoefficients(u1, u2, "survey_anchors", t, g, False)

    u1, u2, interp = _interp_grid(table, t, g)
    return LDCoefficients(float(u1), float(u2), source, t, g, bool(interp))


def tables_available() -> bool:
    return ATLAS_FILE.exists() and PHOENIX_FILE.exists()
