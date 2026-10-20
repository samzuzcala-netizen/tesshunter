"""Published planet occurrence-rate grids used by the survey yield model.

Every grid is a list of cells ``(p_lo, p_hi, r_lo, r_hi, rate)`` with periods
in days, radii in Earth radii and ``rate`` in planets per star inside the
cell.  Provenance, units and the treatment of upper-limit cells are recorded
next to each grid so the transcription can be audited line by line.

``KM2020_FGK``
    Kunimoto & Matthews 2020, AJ 159, 248 ("Searching the Entirety of Kepler
    Data. II. Occurrence Rate Estimates for FGK Stars"), baseline FGK grid,
    Fig. "FGK Occurrence Rates" (arXiv:2004.05296 source file
    ``FGK_occurrence.png``).  Values are the ABC posterior medians in per cent,
    transcribed cell by cell on 2026-09-01 and checked against the paper's own
    marginalized comparison table (their Table "Rough comparisons for FGK-type
    stars"): 2-2.83 Re P<50 d 18.6 (table 18.6); 2-4 Re P<50 d 25.12 (25.2);
    1-2 Re P<50 d 16.06 (16.2); 4-8 Re P<50 d 1.49 (1.6); 8-16 Re P<50 d 1.48
    (1.6); 2-4 Re P<100 d 35.26 (35.4); 1-2 Re P<100 d 17.89 (18.1).  The
    residual differences come from cells with no detected planets, which the
    paper marginalizes as posterior samples and this transcription takes as
    zero (their 84.1th-percentile upper limits are kept in ``KM2020_FGK_UL``).
    Bin edges: P = 0.78125 x 2^k days (the paper's text prints 1.63 for the
    second edge; the figure axis and the doubling both give 1.5625), R =
    {0.5, 0.71, 1, 1.41, 2, 2.83, 4, 5.66, 8, 11.31, 16} Re.

``DC15_M``
    Dressing & Charbonneau 2015, ApJ 807, 45, Table 3 ("Number of Planets Per
    Star Versus Orbital Period"), first block (Huber et al. 2014 stellar
    properties; the paper's baseline), transcribed from the arXiv:1501.01623
    source on 2026-09-01.  Period bins 0.5-1.7, 1.7-5.5, 5.5-18.2, 18.2-60.3,
    60.3-200 d; radius bins 0.5-1, 1-1.5, 1.5-2, 2-2.5, 2.5-3, 3-3.5, 3.5-4 Re.
    The one upper-limit cell with a large rate (1-1.5 Re, 5.5-18.2 d,
    "<26.54") is set to 25.77 so that the row's cumulative rate to 50 d
    reproduces the paper's Table 4 value of 56.25 (the abstract's 0.56 planets
    per star); the other upper-limit cells (all below 0.13) are set to 0.
    Cells the paper leaves blank (60.3-200 d, 0.5-1 Re) are 0.  Planets above
    4 Re are outside DC15; the survey adds an adopted rate for 4-20 Re at
    0.5-50 d (see ``DC15_M_GIANTS_ADOPTED`` for the value, its sources and its
    revision history).
"""

from __future__ import annotations

import numpy as np

# ── Kunimoto & Matthews 2020, baseline FGK grid (per cent) ───────────────────
KM2020_PERIOD_EDGES = [0.78125 * 2 ** k for k in range(10)]          # 0.78 ... 400 d
KM2020_RADIUS_EDGES = [0.5, 0.71, 1.0, 1.41, 2.0, 2.83, 4.0, 5.66, 8.0, 11.31, 16.0]
# rows: radius bins from 0.5-0.71 (bottom of the figure) upward; columns: period bins
# None marks a cell the paper reports only as an upper limit (no detected planets).
KM2020_FGK_PERCENT = [
    # 0.78-1.56, 1.56-3.13, 3.13-6.25, 6.25-12.5, 12.5-25, 25-50, 50-100, 100-200, 200-400
    [0.02, 0.10, 0.34, 0.18, None, None, None, None, None],   # 0.5-0.71 Re
    [0.10, 0.25, 0.71, 0.51, 0.26, 0.25, 0.28, None, None],   # 0.71-1
    [0.18, 0.46, 1.37, 2.34, 1.59, 0.43, 0.33, 0.41, None],   # 1-1.41
    [0.12, 0.52, 1.79, 2.66, 2.41, 2.19, 1.50, 1.04, 0.57],   # 1.41-2
    [0.01, 0.10, 0.99, 3.37, 6.56, 7.57, 6.52, 6.01, 4.78],   # 2-2.83
    [0.01, 0.05, 0.27, 0.61, 2.13, 3.45, 3.62, 2.82, 2.21],   # 2.83-4
    [0.01, 0.02, 0.18, 0.17, 0.19, 0.26, 0.92, 0.67, 1.31],   # 4-5.66
    [None, None, 0.08, 0.07, 0.24, 0.27, 0.53, 0.86, 2.75],   # 5.66-8
    [None, 0.01, 0.09, 0.16, 0.06, 0.20, 0.58, 1.55, 1.09],   # 8-11.31
    [0.02, 0.09, 0.19, 0.18, 0.18, 0.30, 0.37, 0.81, 1.66],   # 11.31-16
]
KM2020_FGK_UNCERTAINTY_PERCENT = [
    [0.02, 0.06, 0.18, 0.17, None, None, None, None, None],
    [0.04, 0.09, 0.21, 0.26, 0.22, 0.26, 0.33, None, None],
    [0.05, 0.10, 0.23, 0.39, 0.44, 0.38, 0.36, 0.48, None],
    [0.04, 0.10, 0.27, 0.40, 0.59, 0.64, 0.72, 0.71, 0.68],
    [0.01, 0.05, 0.18, 0.43, 0.73, 0.98, 1.18, 1.32, 1.74],
    [0.01, 0.03, 0.11, 0.22, 0.46, 0.65, 0.89, 1.07, 1.41],
    [0.01, 0.02, 0.09, 0.10, 0.17, 0.22, 0.49, 0.56, 0.95],
    [None, None, 0.06, 0.06, 0.13, 0.16, 0.33, 0.51, 1.24],
    [None, 0.02, 0.06, 0.09, 0.07, 0.14, 0.33, 0.69, 0.87],
    [0.02, 0.04, 0.08, 0.08, 0.10, 0.18, 0.26, 0.47, 0.95],
]
# 84.1th-percentile upper limits (per cent) for the cells marked None above
KM2020_FGK_UL_PERCENT = {
    (0, 4): 0.28, (0, 5): 0.57, (0, 6): 1.11, (0, 7): 3.5, (0, 8): 14.1,
    (1, 7): 1.2, (1, 8): 3.4,
    (2, 8): 1.43,
    (7, 0): 0.02, (7, 1): 0.02,
    (8, 0): 0.02,
}

KM2020_PROVENANCE = {
    "citation": "Kunimoto, M. & Matthews, J. M. 2020, AJ, 159, 248; arXiv:2004.05296",
    "table": "baseline FGK occurrence rates (Fig. 'FGK Occurrence Rates', file FGK_occurrence.png in the arXiv source)",
    "units": "planets per star per cell, transcribed in per cent and divided by 100",
    "statistic": "median of the ABC posterior; uncertainty is the larger of the 15.9/84.1 percentile offsets",
    "upper_limit_cells": "no detected planets; central value taken as 0, 84.1th-percentile limit kept in KM2020_FGK_UL_PERCENT",
    "stellar_sample": "Kepler FGK dwarfs, Teff 3900-7300 K (K 3900-5300, G 5300-6000, F 6000-7300)",
    "period_edges_days": KM2020_PERIOD_EDGES,
    "radius_edges_rearth": KM2020_RADIUS_EDGES,
    "transcribed": "2026-09-01, cross-checked against the paper's marginalized comparison table (see module docstring)",
}

# ── Dressing & Charbonneau 2015, M dwarfs (per cent) ─────────────────────────
DC15_PERIOD_EDGES = [0.5, 1.7, 5.5, 18.2, 60.3, 200.0]
DC15_RADIUS_EDGES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
DC15_M_PERCENT = [
    # 0.5-1.7, 1.7-5.5, 5.5-18.2, 18.2-60.3, 60.3-200 d
    [1.92, 9.88, 23.06, 17.75, 0.0],      # 0.5-1 Re  (last cell blank in the paper: pipeline sensitivity < 15%)
    [1.83, 9.18, 25.77, 23.08, 30.70],    # 1-1.5 Re  (5.5-18.2 d cell: '<26.54', set from the cumulative table, see docstring)
    [0.33, 3.70, 20.06, 26.73, 18.90],    # 1.5-2 Re
    [0.0, 2.25, 15.69, 23.65, 14.12],     # 2-2.5 Re  ('<0.13' -> 0)
    [0.0, 1.19, 6.54, 10.42, 5.30],       # 2.5-3 Re  ('<0.11' -> 0)
    [0.0, 0.58, 2.55, 2.44, 1.83],        # 3-3.5 Re  ('<0.11' -> 0)
    [0.0, 0.36, 0.87, 0.53, 0.0],         # 3.5-4 Re  ('<0.11' -> 0, '<2.71' -> 0)
]
DC15_M_GIANTS_ADOPTED = {
    "p_lo": 0.5, "p_hi": 50.0, "r_lo": 4.0, "r_hi": 20.0, "rate": 0.01,
    "source": ("adopted; outside DC15. Hot Jupiters around M dwarfs: 0.194 +/- 0.072% (Bryant, Bayliss & Van Eylen "
               "2023, MNRAS 521, 3663) and 0.27 +/- 0.09% for early M dwarfs (Gan et al. 2023, AJ 165, 17); "
               "4-8 Re planets at P < 50 d around M dwarfs are rare in Kepler (Hsu, Ford & Terrien 2020, MNRAS 498, "
               "2249, report of order 1% over longer baselines). Adopted total 0.01 per star at 0.5-50 d for 4-20 Re."),
    "revision": ("P1 used 0.02 without a citation. During the remediation a sensitivity scan showed this single input "
                 "decides the stratum-2 versus stratum-3 ranking (ratio 1.29 at 0, 1.44 at 0.01, 1.59 at 0.02 on the "
                 "240-tile sample). The central value was then anchored to the cited hot-Jupiter rates plus an "
                 "allowance for 4-8 Re; the decision is reported at 0, 0.01 and 0.02 in the memo and the JSON."),
    "sensitivity_values": [0.0, 0.01, 0.02],
}
DC15_PROVENANCE = {
    "citation": "Dressing, C. D. & Charbonneau, D. 2015, ApJ, 807, 45; arXiv:1501.01623",
    "table": "Table 3 'Number of Planets Per Star Versus Orbital Period (In Percentage)', first block (Huber+2014 stellar properties)",
    "cross_check": "Table 4 cumulative rates: 1-1.5 Re 0.5-50 d = 56.25%, 1.5-2 Re = 45.95% (abstract: 0.56 and 0.46 per star)",
    "units": "planets per star per cell, transcribed in per cent and divided by 100",
    "upper_limit_cells": "'<26.54' (1-1.5 Re, 5.5-18.2 d) set to 25.77 from the cumulative table; other limits (<0.13) set to 0",
    "stellar_sample": "Kepler M dwarfs, Teff < 4000 K",
    "period_edges_days": DC15_PERIOD_EDGES,
    "radius_edges_rearth": DC15_RADIUS_EDGES,
    "transcribed": "2026-09-01 from the arXiv source",
}


def _grid_cells(percent_rows, p_edges, r_edges):
    cells = []
    for i, row in enumerate(percent_rows):
        for j, val in enumerate(row):
            rate = 0.0 if val is None else float(val) / 100.0
            cells.append({"p_lo": p_edges[j], "p_hi": p_edges[j + 1], "r_lo": r_edges[i], "r_hi": r_edges[i + 1],
                          "rate": rate, "upper_limit_only": val is None})
    return cells


def km2020_fgk_cells() -> list[dict]:
    return _grid_cells(KM2020_FGK_PERCENT, KM2020_PERIOD_EDGES, KM2020_RADIUS_EDGES)


def dc15_m_cells(include_adopted_giants: bool = True, giant_rate: float | None = None) -> list[dict]:
    """DC15 grid cells; ``giant_rate`` overrides the adopted 4-20 Re rate (sensitivity runs)."""
    cells = _grid_cells(DC15_M_PERCENT, DC15_PERIOD_EDGES, DC15_RADIUS_EDGES)
    if include_adopted_giants:
        g = DC15_M_GIANTS_ADOPTED
        rate = g["rate"] if giant_rate is None else float(giant_rate)
        cells.append({"p_lo": g["p_lo"], "p_hi": g["p_hi"], "r_lo": g["r_lo"], "r_hi": g["r_hi"],
                      "rate": rate, "upper_limit_only": False, "adopted": True})
    return cells


def clip_cells_to_period(cells: list[dict], p_lo: float, p_hi: float) -> list[dict]:
    """Restrict cells to [p_lo, p_hi], splitting rates uniformly in ln P inside a cell."""
    out = []
    for c in cells:
        lo, hi = max(c["p_lo"], p_lo), min(c["p_hi"], p_hi)
        if hi <= lo:
            continue
        frac = np.log(hi / lo) / np.log(c["p_hi"] / c["p_lo"])
        d = dict(c)
        d.update({"p_lo": lo, "p_hi": hi, "rate": c["rate"] * float(frac)})
        out.append(d)
    return out


def integrated_rate(cells: list[dict], p_lo: float, p_hi: float, r_lo: float, r_hi: float) -> float:
    """Sum of cell rates inside a period-radius box (cells split uniformly in ln P and ln R)."""
    total = 0.0
    for c in cells:
        plo, phi = max(c["p_lo"], p_lo), min(c["p_hi"], p_hi)
        rlo, rhi = max(c["r_lo"], r_lo), min(c["r_hi"], r_hi)
        if phi <= plo or rhi <= rlo:
            continue
        fp = np.log(phi / plo) / np.log(c["p_hi"] / c["p_lo"])
        fr = np.log(rhi / rlo) / np.log(c["r_hi"] / c["r_lo"])
        total += c["rate"] * float(fp) * float(fr)
    return total
