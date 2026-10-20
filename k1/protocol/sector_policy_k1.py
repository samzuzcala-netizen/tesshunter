"""The K1 usable-sector rule (registered in RULES_K1.md, Part 0).

A sector is usable when it lies in 1-98 and an archival FFI light curve exists for it:
  * TESS-SPOC (FFI light curves exist through sector 85), or
  * QLP, except QLP sectors 80, 83 and 85, which count only through TESS-SPOC (unresolved QLP timing).
Sectors 99-104 are excluded (QLP barycentric timing error, awaiting redelivery) and sector 105 and
later are excluded (QLP light curves not released).  Redeliveries during K1 do not change this frozen
policy; they are recorded as post-freeze options.

One product per usable sector: TESS-SPOC preferred over QLP (the existing ``survey_p8``
AUTHOR_PREFERENCE order, SPOC 2-min first, never used for K1 validation hosts).
Native cadence by sector: 1800 s in 1-26, 600 s in 27-55, 200 s from 56.
"""
from __future__ import annotations

SECTOR_MIN = 1
SECTOR_MAX = 98
QLP_TIMING_UNRESOLVED = frozenset({80, 83, 85})
QLP_TIMING_ERROR = frozenset(range(99, 105))
FIRST_UNRELEASED = 105
S56 = 56
AUTHOR_PREFERENCE = ("TESS-SPOC", "QLP")


def native_cadence_s(sector: int) -> float:
    s = int(sector)
    if s <= 26:
        return 1800.0
    if s <= 55:
        return 600.0
    return 200.0


def qlp_usable(sector: int) -> bool:
    s = int(sector)
    return SECTOR_MIN <= s <= SECTOR_MAX and s not in QLP_TIMING_UNRESOLVED and s not in QLP_TIMING_ERROR


def spoc_usable(sector: int) -> bool:
    s = int(sector)
    return SECTOR_MIN <= s <= SECTOR_MAX


def usable_sectors(qlp_sectors, tess_spoc_sectors, *, s56_only: bool = False) -> set[int]:
    out = {int(s) for s in tess_spoc_sectors if spoc_usable(s)} | {int(s) for s in qlp_sectors if qlp_usable(s)}
    if s56_only:
        out = {s for s in out if s >= S56}
    return out


def product_usable(author: str, sector: int) -> bool:
    a = str(author).upper()
    if a == "TESS-SPOC":
        return spoc_usable(sector)
    if a == "QLP":
        return qlp_usable(sector)
    return False


def choose_products(rows: list[dict], *, s56_only: bool = False) -> list[dict]:
    """One usable FFI product per sector from index rows carrying ``author`` and ``sector``."""
    best: dict[int, dict] = {}
    rank = {a: i for i, a in enumerate(AUTHOR_PREFERENCE)}
    for r in rows:
        a = str(r.get("author", "")).upper()
        s = int(r["sector"])
        if a not in rank or not product_usable(a, s) or (s56_only and s < S56):
            continue
        if s not in best or rank[a] < rank[str(best[s]["author"]).upper()]:
            best[s] = r
    return [best[s] for s in sorted(best)]


#: Amendment K1-20261008-1: QLP products for these sectors count only in the corrected v02 delivery
#: (P12 ``qlp_correction_required_sectors``; QLP timing correction).
QLP_V02_REQUIRED = frozenset(range(74, 80))


def product_version_usable(author: str, sector: int, version: str | None) -> bool:
    """The realised-product check of amendment 1 (applied at download)."""
    if str(author).upper() == "QLP" and int(sector) in QLP_V02_REQUIRED:
        return str(version) in ("02", "2", "2.0")
    return True
