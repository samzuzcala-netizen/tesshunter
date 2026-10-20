"""K1 change 2: Gaia main-sequence check for BP-RP 0.85-2.50 (K and early-M dwarfs).

Replaces, for K1 only, the P8 rule in ``scripts/build_p8_population.py:429-455`` (BP-RP >= 1.6 and a
linear M-dwarf locus).  The reference sequence is the Pecaut & Mamajek dwarf table (Mamajek's
``EEM_dwarf_UBVIJHK_colors_Teff.txt`` version 2022.04.16, copied to ``k1/protocol/data``), columns
Bp-Rp and M_G in Gaia DR2 bands, which are the bands of the TIC v8.2 Gaia columns used here.

Rule (registered in RULES_K1.md before any calibration run):
  * parallax / error >= 5, finite G, BP, RP, parallax > 0           else REJECT (reason named)
  * BP-RP inside [0.85, 2.50]                                        else REJECT colour_outside_k1_range
  * dM = M_G(star) - M_G(sequence at the star's BP-RP), M_G = G + 5 log10(plx/1000) + 5, no extinction
    (|b| >= 20 for the survey);  dM < -1.0 REJECT overluminous (evolved);  dM > +1.0 REJECT
    underluminous (bad astrometry / wrong colour);  -1.0 <= dM < -0.5 PASS with flag possible_binary.
  * RUWE > 1.4 adds the flag ruwe_gt_1p4 when a DR3 RUWE is supplied (flags are never cuts).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TABLE = Path(__file__).resolve().parent / "data" / "EEM_dwarf_UBVIJHK_colors_Teff.txt"
TABLE_SHA256 = "1de2edeec17bb3346e0e4e70b999de5ee29947df38474e64cddb7cfacc164b7f"
BPRP_RANGE = (0.85, 2.50)
DEFAULTS = {"plx_snr_min": 5.0, "reject_brighter_mag": 1.0, "reject_fainter_mag": 1.0,
            "flag_binary_brighter_mag": [0.5, 1.0], "ruwe_flag": 1.4}


def load_sequence(path: Path = TABLE) -> tuple[np.ndarray, np.ndarray]:
    """(BP-RP, M_G) of every dwarf row with both values, sorted by colour (monotonic check)."""
    rows = []
    in_table = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("#SpT"):
            if in_table:
                break                      # the second header closes the main table
            in_table = True
            continue
        if not in_table or not line.strip() or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 14:
            continue
        try:
            bprp = float(parts[11]); mg = float(parts[13].rstrip(":"))
        except ValueError:
            continue
        rows.append((bprp, mg))
    arr = np.array(sorted(rows))
    keep = (arr[:, 0] >= 0.5) & (arr[:, 0] <= 3.5)
    arr = arr[keep]
    if np.any(np.diff(arr[:, 0]) <= 0) or np.any(np.diff(arr[:, 1]) < 0):
        raise ValueError("main-sequence table is not monotonic in the K1 colour range")
    return arr[:, 0], arr[:, 1]


_SEQ = None


def sequence() -> tuple[np.ndarray, np.ndarray]:
    global _SEQ
    if _SEQ is None:
        _SEQ = load_sequence()
    return _SEQ


def ms_abs_g(bp_rp) -> np.ndarray:
    x, y = sequence()
    return np.interp(np.asarray(bp_rp, float), x, y, left=np.nan, right=np.nan)


def check_arrays(G, bp, rp, plx, eplx, ruwe=None, cfg: dict | None = None) -> pd.DataFrame:
    cfg = dict(DEFAULTS, **(cfg or {}))
    G, bp, rp, plx, eplx = (np.asarray(v, float) for v in (G, bp, rp, plx, eplx))
    n = len(G)
    with np.errstate(divide="ignore", invalid="ignore"):
        snr = plx / eplx
        mg = G + 5.0 * np.log10(plx / 1000.0) + 5.0
    bprp = bp - rp
    ref = ms_abs_g(bprp)
    dm = mg - ref
    status = np.full(n, "PASS", dtype=object)
    reason = np.full(n, "", dtype=object)

    def rej(mask, why):
        m = mask & (status == "PASS")
        status[m] = "REJECT"; reason[m] = why

    rej(~(np.isfinite(G) & np.isfinite(bp) & np.isfinite(rp)), "no_gaia_photometry")
    rej(~(np.isfinite(plx) & (plx > 0)), "no_parallax")
    rej(~(np.isfinite(snr) & (snr >= cfg["plx_snr_min"])), "parallax_snr_below_5")
    rej((bprp < BPRP_RANGE[0]) | (bprp > BPRP_RANGE[1]), "colour_outside_k1_range")
    rej(dm < -cfg["reject_brighter_mag"], "overluminous_evolved")
    rej(dm > cfg["reject_fainter_mag"], "underluminous_bad_astrometry")
    flags = [[] for _ in range(n)]
    lo, hi = cfg["flag_binary_brighter_mag"]
    for i in np.flatnonzero((status == "PASS") & (dm < -lo) & (dm >= -hi)):
        flags[i].append("possible_binary")
    if ruwe is not None:
        r = np.asarray(ruwe, float)
        for i in np.flatnonzero(np.isfinite(r) & (r > cfg["ruwe_flag"])):
            flags[i].append("ruwe_gt_1p4")
    return pd.DataFrame({"gaia_ms_status": status, "gaia_ms_reason": reason,
                         "gaia_abs_g": np.round(mg, 3), "gaia_bp_rp": np.round(bprp, 3),
                         "gaia_ms_ref_abs_g": np.round(ref, 3), "gaia_ms_delta_mag": np.round(dm, 3),
                         "gaia_plx_snr": np.round(snr, 1), "gaia_flags": [";".join(f) for f in flags]})


def check_frame(pool: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    num = lambda c: pd.to_numeric(pool[c], errors="coerce").to_numpy(float)  # noqa: E731
    ruwe = num("ruwe") if "ruwe" in pool else None
    out = check_arrays(num("GAIAmag"), num("gaiabp"), num("gaiarp"), num("plx"), num("e_plx"), ruwe, cfg)
    out.index = pool.index
    return out
