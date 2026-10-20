"""The v2 survivor score (prompt 7).

The frozen P4 score (``docs/RANKING_SCORE.md`` sections 1-4) is untouched and
still the one the survey ranked on.  It was measured in prompt 6 to carry some
information - the P4 rank correlates with how many Stage A criteria a candidate
passes, Spearman rho = -0.37, p = 9e-15 - but **none at all** about the quantity
that measures a signal in clean data: rho = -0.065, p = 0.19 against the
kept-event SNR, n = 405.  Its ``S_snr`` term ranked on the whole-stitch local-BLS
SNR, which prompt 5 showed the independent data do not reproduce.

v2 replaces that term with what the audit actually measures and adds the
star-level evidence the frozen score deliberately left out:

    score_v2 = S_snr2 + S_sectors - penalties,   zero if the secondary gate fails

* ``S_snr2``    kept-event SNR under the best ephemeris, saturating at 20;
* ``S_sectors`` the number of independent sectors whose kept events show the dip
  at more than 2 sigma, saturating at 4 - a signal in one sector is a sector
  systematic, a signal in four is not;
* penalties: 0.25 per Gaia flag (RUWE, multi-peak fraction, excess-noise
  significance, non-single-star) and 0.5 for a deep-event host;
* zero if the full-phase secondary scan's gate fails, because a stellar
  companion is not a planet candidate at any score.

Nothing here produces a verdict.  A score orders a list; it decides nothing.
"""
from __future__ import annotations

import math

from .audit_rules import (
    B_DEEP_PPT,
    V2_DEEP_HOST_PENALTY,
    V2_GAIA_FLAG_PENALTY,
    V2_SECTOR_EVENT_SIGMA,
    V2_SECTORS_SATURATION,
    V2_SNR_SATURATION,
)

__all__ = ["independent_sectors", "gaia_penalty_flags", "score_v2"]

#: [P7] the v2 Gaia penalties.  RUWE and the multi-peak fraction repeat the Stage B
#: numbers; the excess-noise significance is deliberately far higher than Stage B's
#: flag threshold of 2, because at 2 it fires on most bright stars and would penalise
#: the whole list equally.  Prompt 6 measured the two Stage A survivor hosts that are
#: not single stars at 202 and 1560.
V2_RUWE = 1.4
V2_IPD_MULTI_PEAK = 10.0
V2_AEN_SIG = 100.0


def independent_sectors(events: list[dict], sigma: float = V2_SECTOR_EVENT_SIGMA) -> dict:
    """Sectors in which at least one KEPT event shows the dip above ``sigma``.

    ``events`` is a per-event table (observed epochs carry ``sector``,
    ``det_depth_ppt``, ``det_depth_err_ppt`` and ``excluded``).
    """
    good, all_sectors = set(), set()
    for e in events:
        if not e.get("observed") or e.get("excluded"):
            continue
        s = e.get("sector")
        if s is None:
            continue
        all_sectors.add(int(s))
        d, err = e.get("det_depth_ppt"), e.get("det_depth_err_ppt")
        if d is not None and err:
            if d / err > sigma:
                good.add(int(s))
    return {"n_sectors_with_kept_events": len(all_sectors),
            "n_sectors_showing_the_dip": len(good),
            "sectors_showing_the_dip": sorted(good), "sigma_per_event": sigma}


def gaia_penalty_flags(gaia: dict) -> list[str]:
    """The v2 Gaia penalties actually incurred, one string each."""
    out = []
    ruwe = gaia.get("ruwe")
    ipd = gaia.get("ipd_frac_multi_peak")
    aen = gaia.get("astrometric_excess_noise_sig")
    if ruwe is not None and ruwe >= V2_RUWE:
        out.append(f"RUWE {ruwe:.2f} >= {V2_RUWE}")
    if ipd is not None and ipd >= V2_IPD_MULTI_PEAK:
        out.append(f"ipd_frac_multi_peak {ipd:.0f}% >= {V2_IPD_MULTI_PEAK:.0f}%")
    if aen is not None and aen >= V2_AEN_SIG:
        out.append(f"astrometric_excess_noise_sig {aen:.0f} >= {V2_AEN_SIG:.0f}")
    if gaia.get("non_single_star"):
        out.append(f"non_single_star = {gaia['non_single_star']}")
    return out


def score_v2(kept_snr: float | None, events: list[dict], gaia: dict | None,
             deep_event_host: dict | None, secondary_gate: str | None) -> dict:
    """The v2 score and every term that produced it."""
    snr = float(kept_snr) if kept_snr is not None else 0.0
    s_snr = 0.0 if snr <= 0 else min(1.0, math.log1p(snr) / math.log1p(V2_SNR_SATURATION))
    sec = independent_sectors(events or [])
    s_sec = min(1.0, sec["n_sectors_showing_the_dip"] / V2_SECTORS_SATURATION)
    flags = gaia_penalty_flags(gaia or {})
    pen_gaia = V2_GAIA_FLAG_PENALTY * len(flags)
    host = bool((deep_event_host or {}).get("flag"))
    pen_host = V2_DEEP_HOST_PENALTY if host else 0.0
    raw = s_snr + s_sec - pen_gaia - pen_host
    gate_failed = (secondary_gate == "FAIL")
    score = 0.0 if gate_failed else max(0.0, raw)
    return {
        "score_v2": round(score, 4),
        "S_snr2": round(s_snr, 4), "S_sectors": round(s_sec, 4),
        "kept_snr": kept_snr, "snr_saturation": V2_SNR_SATURATION,
        "n_sectors_showing_the_dip": sec["n_sectors_showing_the_dip"],
        "n_sectors_with_kept_events": sec["n_sectors_with_kept_events"],
        "sectors_showing_the_dip": sec["sectors_showing_the_dip"],
        "sectors_saturation": V2_SECTORS_SATURATION, "sector_event_sigma": V2_SECTOR_EVENT_SIGMA,
        "gaia_penalty_flags": flags, "penalty_gaia": round(pen_gaia, 4),
        "deep_event_host": host, "penalty_deep_host": pen_host,
        "deep_event_host_threshold_ppt": B_DEEP_PPT,
        "secondary_gate": secondary_gate, "zeroed_by_secondary_gate": gate_failed,
        "raw_before_floor_and_gate": round(raw, 4),
        "thresholds": {"ruwe": V2_RUWE, "ipd_frac_multi_peak_pct": V2_IPD_MULTI_PEAK,
                       "astrometric_excess_noise_sig": V2_AEN_SIG,
                       "gaia_flag_penalty": V2_GAIA_FLAG_PENALTY,
                       "deep_host_penalty": V2_DEEP_HOST_PENALTY},
    }
