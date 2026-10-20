"""Stellar parameters for the transit fit and the vetting stack.

One container (:class:`StellarParams`) built either from the TIC (cached on
disk, one JSON per star under ``data/cache/tic/``) or from values the caller
already holds (the survey's ``targets_v1.csv`` row, a test fixture). The
container knows how to turn mass and radius (or the TIC's own ``rho``) into a
mean stellar density with an uncertainty, which is what the a/R* consistency
test in :mod:`tesshunter.transit_fit` compares against.

Uncertainty policy, stated because it matters for the flag: when a catalog
value has no error the container ADOPTS a fractional error (radius 10%, mass
15%, Teff 150 K) and records ``assumed_errors=True`` so a report can say so.
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .config import CACHE_DIR

logger = logging.getLogger(__name__)

TIC_CACHE_DIR = CACHE_DIR / "tic"
TIC_CACHE_MAX_AGE_S = 365 * 86400.0

#: Set TESSHUNTER_OFFLINE=1 to forbid every catalog query in this module (the
#: cache is still served). The test suite sets it in tests/conftest.py so a
#: synthetic target id never reaches MAST.
OFFLINE_ENV = "TESSHUNTER_OFFLINE"


def _forced_offline() -> bool:
    import os
    return os.environ.get(OFFLINE_ENV, "").strip() not in ("", "0", "false", "False")

#: Solar values (IAU 2015 nominal) used for density and radius conversions.
RSUN_M = 6.957e8
MSUN_KG = 1.98847e30
RHO_SUN_CGS = 3.0 * MSUN_KG / (4.0 * math.pi * RSUN_M ** 3) / 1000.0   # 1.4098 g/cc
REARTH_PER_RSUN = 109.076
RJUP_PER_RSUN = RSUN_M / 7.1492e7                                        # 9.7311

#: Adopted fractional errors when the catalog supplies none [A].
ASSUMED_RADIUS_FRAC_ERR = 0.10
ASSUMED_MASS_FRAC_ERR = 0.15
ASSUMED_MASS_FROM_RADIUS_FRAC_ERR = 0.30
ASSUMED_TEFF_ERR_K = 150.0


@dataclass
class StellarParams:
    tic_id: Optional[int] = None
    ra: Optional[float] = None
    dec: Optional[float] = None
    tmag: Optional[float] = None
    teff: Optional[float] = None
    teff_err: Optional[float] = None
    logg: Optional[float] = None
    logg_err: Optional[float] = None
    radius: Optional[float] = None          # R_sun
    radius_err: Optional[float] = None
    mass: Optional[float] = None            # M_sun
    mass_err: Optional[float] = None
    rho: Optional[float] = None             # solar units (TIC `rho`)
    rho_err: Optional[float] = None
    lum: Optional[float] = None
    distance_pc: Optional[float] = None
    contamination_ratio: Optional[float] = None
    gaia_id: Optional[int] = None
    gaia_mag: Optional[float] = None
    gaia_bp: Optional[float] = None
    gaia_rp: Optional[float] = None
    source: str = "user"
    fetched_utc: Optional[str] = None
    assumed_errors: bool = False
    notes: list[str] = field(default_factory=list)

    # ── constructors ─────────────────────────────────────────────────────────
    @classmethod
    def from_dict(cls, d: dict) -> "StellarParams":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (d or {}).items() if k in known})

    @classmethod
    def from_survey_row(cls, row: dict, tic_id: Optional[int] = None) -> "StellarParams":
        """From a ``targets_v1.csv`` row or a survey job's ``star`` dict."""
        def g(*keys):
            for k in keys:
                v = row.get(k)
                if v is not None and not (isinstance(v, float) and not np.isfinite(v)):
                    return float(v)
            return None
        return cls(
            tic_id=int(tic_id if tic_id is not None else row.get("tic_id", 0)) or None,
            ra=g("ra_deg", "ra"), dec=g("dec_deg", "dec"), tmag=g("tmag"),
            teff=g("teff_k", "teff"), radius=g("radius_rsun", "radius"),
            mass=g("mass_msun", "mass"),
            contamination_ratio=g("contamination_ratio_used", "contamination_ratio"),
            source="survey_row",
        )

    def to_dict(self) -> dict:
        return asdict(self)

    # ── derived quantities ───────────────────────────────────────────────────
    def _radius_err(self) -> Optional[float]:
        if self.radius is None or self.radius <= 0:
            return None
        if self.radius_err is not None and self.radius_err > 0:
            return float(self.radius_err)
        return ASSUMED_RADIUS_FRAC_ERR * self.radius

    def _mass_err(self) -> Optional[float]:
        if self.mass is None or self.mass <= 0:
            return None
        if self.mass_err is not None and self.mass_err > 0:
            return float(self.mass_err)
        return ASSUMED_MASS_FRAC_ERR * self.mass

    def radius_with_err(self) -> tuple[Optional[float], Optional[float], bool]:
        """(radius, error, assumed) in solar radii."""
        if self.radius is None or self.radius <= 0:
            return None, None, False
        assumed = not (self.radius_err is not None and self.radius_err > 0)
        return float(self.radius), self._radius_err(), assumed

    def density_cgs(self) -> tuple[Optional[float], Optional[float], str]:
        """Mean stellar density in g/cc with its error and the provenance.

        Uses the TIC ``rho`` when present (solar units), otherwise mass and
        radius. Returns (None, None, reason) when neither is available.
        """
        if self.rho is not None and self.rho > 0:
            rho = float(self.rho) * RHO_SUN_CGS
            if self.rho_err is not None and self.rho_err > 0:
                return rho, float(self.rho_err) * RHO_SUN_CGS, "tic_rho"
            # fall through to mass/radius error budget for the uncertainty
            r_err = self._radius_err()
            m_err = self._mass_err()
            if r_err is not None and m_err is not None:
                frac = math.sqrt((m_err / self.mass) ** 2 + (3.0 * r_err / self.radius) ** 2)
                return rho, rho * frac, "tic_rho+assumed_err"
            return rho, rho * math.sqrt(ASSUMED_MASS_FRAC_ERR ** 2 + 9 * ASSUMED_RADIUS_FRAC_ERR ** 2), "tic_rho+assumed_err"
        if self.radius is None or self.radius <= 0:
            return None, None, "no_mass_or_radius"
        if self.mass is None or self.mass <= 0:
            # Dwarf approximation M ~ R (solar units), the same rule the P2
            # survey injections used [A]; the error budget is widened to
            # ASSUMED_MASS_FROM_RADIUS_FRAC_ERR so the flag needs a large
            # disagreement. Radius-only inputs (the benchmark harness, K2
            # targets without a TIC entry) get a density test this way.
            mass = float(self.radius)
            m_err = ASSUMED_MASS_FROM_RADIUS_FRAC_ERR * mass
            r_err = self._radius_err()
            rho = mass / float(self.radius) ** 3 * RHO_SUN_CGS
            frac = math.sqrt((m_err / mass) ** 2 + (3.0 * r_err / self.radius) ** 2)
            return rho, rho * frac, "mass_from_radius+assumed_err"
        rho = float(self.mass) / float(self.radius) ** 3 * RHO_SUN_CGS
        r_err = self._radius_err()
        m_err = self._mass_err()
        frac = math.sqrt((m_err / self.mass) ** 2 + (3.0 * r_err / self.radius) ** 2)
        how = "mass_radius" if not (self.mass_err is None or self.radius_err is None) else "mass_radius+assumed_err"
        return rho, rho * frac, how

    def a_over_rs(self, period_days: float) -> tuple[Optional[float], Optional[float], str]:
        """a/R* implied by the stellar density for a circular orbit at ``period_days``."""
        rho, rho_err, how = self.density_cgs()
        if rho is None:
            return None, None, how
        a_rs = a_rs_from_density(rho, period_days)
        # a/R* ~ rho^(1/3)
        return a_rs, a_rs * (rho_err / rho) / 3.0, how


def a_rs_from_density(rho_cgs: float, period_days: float) -> float:
    """a/R* = (G rho P^2 / (3 pi))^(1/3) for a circular orbit."""
    G = 6.674e-11
    rho = rho_cgs * 1000.0
    P = period_days * 86400.0
    return float((G * rho * P ** 2 / (3.0 * math.pi)) ** (1.0 / 3.0))


def density_from_a_rs(a_rs: float, period_days: float) -> float:
    """rho_* in g/cc from a/R* and the period (Seager & Mallen-Ornelas 2003)."""
    G = 6.674e-11
    P = period_days * 86400.0
    return float(3.0 * math.pi * a_rs ** 3 / (G * P ** 2) / 1000.0)


# ── TIC lookup with a disk cache ─────────────────────────────────────────────

_TIC_COLUMNS = [
    "ID", "ra", "dec", "Tmag", "Teff", "e_Teff", "logg", "e_logg", "rad", "e_rad",
    "mass", "e_mass", "rho", "e_rho", "lum", "d", "contratio", "GAIA", "GAIAmag",
    "gaiabp", "gaiarp",
]


def _cache_path(tic_id: int, cache_dir: Optional[Path]) -> Path:
    d = Path(cache_dir) if cache_dir is not None else TIC_CACHE_DIR
    return d / f"tic{int(tic_id)}.json"


def _parse_tic_row(row, colnames) -> dict:
    def f(col):
        if col not in colnames:
            return None
        try:
            v = float(row[col])
        except Exception:            # masked elements raise numpy.ma.MaskError, not ValueError (P4)
            return None
        return v if np.isfinite(v) else None

    def i(col):
        if col not in colnames:
            return None
        try:
            v = int(row[col])
        except Exception:            # a masked GAIA id on TIC 167304394 crashed the whole lookup (P4)
            return None
        return v

    return {
        "ra": f("ra"), "dec": f("dec"), "tmag": f("Tmag"),
        "teff": f("Teff"), "teff_err": f("e_Teff"),
        "logg": f("logg"), "logg_err": f("e_logg"),
        "radius": f("rad"), "radius_err": f("e_rad"),
        "mass": f("mass"), "mass_err": f("e_mass"),
        "rho": f("rho"), "rho_err": f("e_rho"),
        "lum": f("lum"), "distance_pc": f("d"),
        "contamination_ratio": f("contratio"),
        "gaia_id": i("GAIA"), "gaia_mag": f("GAIAmag"),
        "gaia_bp": f("gaiabp"), "gaia_rp": f("gaiarp"),
    }


def fetch_tic_params(
    tic_id: int,
    *,
    cache_dir: Optional[Path] = None,
    offline: bool = False,
    max_age_s: float = TIC_CACHE_MAX_AGE_S,
) -> Optional[StellarParams]:
    """TIC parameters for one star, served from ``data/cache/tic`` when fresh.

    Never raises: returns None when the star is unknown, the query fails or
    ``offline`` is set and nothing is cached. A cached copy older than
    ``max_age_s`` is refreshed when online and served (with a note) when not.
    """
    path = _cache_path(tic_id, cache_dir)
    offline = bool(offline or _forced_offline())
    cached: Optional[dict] = None
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:                                # pragma: no cover
            logger.warning("TIC cache unreadable for %s (%s)", tic_id, exc)
            cached = None
    if cached is not None:
        age = time.time() - float(cached.get("_fetched_epoch", 0.0))
        if age <= max_age_s or offline:
            sp = StellarParams.from_dict(cached)
            if age > max_age_s:
                sp.notes.append(f"TIC cache is {age / 86400:.0f} d old and was served offline")
            return sp
    if offline:
        return None

    try:
        import warnings
        from astroquery.mast import Catalogs

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = Catalogs.query_criteria(catalog="Tic", ID=int(tic_id))
        if result is None or len(result) == 0:
            logger.warning("TIC %s not found", tic_id)
            return StellarParams.from_dict(cached) if cached else None
        row = result[0]
        d = _parse_tic_row(row, result.colnames)
        d.update({
            "tic_id": int(tic_id), "source": "tic",
            "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        sp = StellarParams.from_dict(d)
        sp.assumed_errors = (
            (sp.radius is not None and not sp.radius_err)
            or (sp.mass is not None and not sp.mass_err)
        )
        payload = sp.to_dict()
        payload["_fetched_epoch"] = time.time()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        tmp.replace(path)
        return sp
    except Exception as exc:
        logger.warning("TIC query failed for %s: %s", tic_id, exc)
        return StellarParams.from_dict(cached) if cached else None


# ── TIC neighbours within a radius (packet: nearby stars with Gaia magnitudes) ──

TIC_CONE_CACHE_DIR = CACHE_DIR / "tic_cone"
NEIGHBOUR_COLUMNS = [
    "ID", "dstArcSec", "ra", "dec", "Tmag", "GAIAmag", "gaiabp", "gaiarp", "Vmag",
    "Teff", "rad", "mass", "plx", "contratio", "disposition", "GAIA",
]


def fetch_tic_neighbours(
    tic_id: int,
    ra: Optional[float] = None,
    dec: Optional[float] = None,
    *,
    radius_arcsec: float = 60.0,
    cache_dir: Optional[Path] = None,
    offline: bool = False,
):
    """TIC stars within ``radius_arcsec`` of the target as a DataFrame
    (``dstArcSec`` ascending, the target first), cached as CSV. Returns
    None when unavailable. Never raises.
    """
    import pandas as pd

    d = Path(cache_dir) if cache_dir is not None else TIC_CONE_CACHE_DIR
    path = d / f"tic{int(tic_id)}_r{int(round(radius_arcsec))}.csv"
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:                                        # pragma: no cover
            pass
    if offline or _forced_offline():
        return None
    try:
        import warnings
        from astroquery.mast import Catalogs

        if ra is None or dec is None:
            sp = fetch_tic_params(tic_id, cache_dir=None)
            if sp is None or sp.ra is None:
                return None
            ra, dec = sp.ra, sp.dec
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tbl = Catalogs.query_region(f"{float(ra)} {float(dec)}", radius=radius_arcsec / 3600.0,
                                        catalog="TIC")
        if tbl is None or len(tbl) == 0:
            return None
        cols = [c for c in NEIGHBOUR_COLUMNS if c in tbl.colnames]
        df = tbl[cols].to_pandas()
        df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
        df["is_target"] = df["ID"] == int(tic_id)
        df = df.sort_values(["is_target", "dstArcSec"], ascending=[False, True]).reset_index(drop=True)
        d.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".csv.tmp")
        df.to_csv(tmp, index=False)
        tmp.replace(path)
        return df
    except Exception as exc:
        logger.warning("TIC cone query failed for %s: %s", tic_id, exc)
        return None
