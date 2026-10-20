"""K2 Stage C input: the C1 variants (RULES_K2 section 2) and the M1 sibling mask (section 4).

The C input of a variant is K1's prepared C input (``tls/<key>_lc.npz`` arrays ``time``, ``flux``, ``flux_err``:
detrended and clipped at native cadence exactly as in K1) after (1) removing every cadence within +/- 1 x T14 of a
sibling's predicted mid-times (M1) and (2) binning:

* ``K1``: unchanged (K1's Stage C);
* ``V2`` / ``V3``: every point in 30-min bins on one grid from the first point (``bin_series``: bin_lc's grid,
  bin error = the propagated error of the mean, AMENDMENT_K2_20261014_1);
* ``V1`` / ``V4``: points of products with native cadence finer than 10 min in 10-min bins, each product on its
  own grid; 600-s and 1800-s products native.
V3 and V4 run the blind TLS at oversampling 2 when the C input's baseline exceeds 1,000 d (3 otherwise).

``install`` patches ``audit_p5.load_prepared`` in the worker process only, so Stage C's blind and forced TLS and
its cadence duration floor (computed on the series TLS reads) see the C input, while the prepared file, K1's
A/S/B records and the input configuration stay K1's (Stage D's consistency checks still hold).
"""
from __future__ import annotations

import numpy as np

VARIANTS = ("K1", "V1", "V2", "V3", "V4")
WHOLE_30 = ("V2", "V3")
PER_PRODUCT_10 = ("V1", "V4")
REDUCED_OVERSAMPLING = ("V3", "V4")
BASELINE_FOR_REDUCED_OS_DAYS = 1000.0
FINE_CADENCE_MAX_S = 590.0          # "finer than 10 min": 120-s and 200-s products
SIBLING_HALF_WIDTH_T14 = 1.0        # M1: +/- 1 x T14


def oversampling(variant: str, baseline_days: float) -> int:
    if variant not in VARIANTS:
        raise ValueError("Unregistered C variant " + str(variant))
    return 2 if (variant in REDUCED_OVERSAMPLING and baseline_days > BASELINE_FOR_REDUCED_OS_DAYS) else 3


def point_sectors(t: np.ndarray, t_unbinned: np.ndarray, sector_unbinned: np.ndarray) -> np.ndarray:
    """The sector of every prepared C-input point (the prepared points are a subset of the unbinned detrended
    cadences: the native-cadence clips only remove points)."""
    t = np.asarray(t, float)
    order = np.argsort(t_unbinned, kind="stable")
    tu, su = np.asarray(t_unbinned, float)[order], np.asarray(sector_unbinned)[order]
    i = np.clip(np.searchsorted(tu, t), 0, len(tu) - 1)
    if not np.all(tu[i] == t):
        raise ValueError("C input point not found among the unbinned cadences")
    return su[i]


#: AMENDMENT_K2_20261014_1: bin errors are the propagated K1 per-cadence errors, sqrt(sum e_i^2) / n
#: ("propagated"); the first registration used audit_prep.bin_lc's in-bin scatter ("in_bin_scatter"), whose
#: 3-9-point scatter estimates gave a few bins most of the chi-square weight.
BIN_ERRORS = "propagated"


def bin_series(t, f, e, minutes: float):
    """Fixed-width bins on one grid from the first point (bin_lc's grid, time and flux): the bin error is the
    propagated error of the mean (BIN_ERRORS = "propagated") or bin_lc's in-bin scatter ("in_bin_scatter")."""
    from tesshunter.audit_prep import bin_lc
    if BIN_ERRORS == "in_bin_scatter":
        return bin_lc(t, f, e, minutes)
    if BIN_ERRORS != "propagated":
        raise ValueError("Unregistered bin error model")
    t, f, e = (np.asarray(x, float) for x in (t, f, e))
    if t.size == 0:
        return t, f, e
    idx = np.floor((t - t[0]) / (minutes / 1440.0)).astype(np.int64)
    _, inv = np.unique(idx, return_inverse=True)
    n = np.bincount(inv)
    return (np.bincount(inv, weights=t) / n, np.bincount(inv, weights=f) / n,
            np.sqrt(np.bincount(inv, weights=e * e)) / n)


def bin_per_product(t, f, e, sectors, cadence_by_sector: dict, minutes: float = 10.0):
    T, F, E = [], [], []
    for s in np.unique(sectors):
        m = sectors == s
        if float(cadence_by_sector.get(int(s), 1e9)) <= FINE_CADENCE_MAX_S:
            tb, fb, eb = bin_series(t[m], f[m], e[m], minutes)
        else:
            tb, fb, eb = t[m], f[m], e[m]
        T.append(tb), F.append(fb), E.append(eb)
    t2, f2, e2 = np.concatenate(T), np.concatenate(F), np.concatenate(E)
    o = np.argsort(t2, kind="stable")
    return t2[o], f2[o], e2[o]


def sibling_mask(t: np.ndarray, siblings: list[dict] | None) -> np.ndarray:
    """True where a point lies within +/- 1 x T14 of a sibling's predicted mid-time."""
    from tesshunter.audit_prep import transit_mask
    out = np.zeros(np.shape(t), dtype=bool)
    for sb in siblings or []:
        out |= transit_mask(t, float(sb["period"]), float(sb["t0"]), float(sb["t14"]),
                            n_durations=SIBLING_HALF_WIDTH_T14)
    return out


def transform(arrays: dict, products: list[dict], variant: str, siblings: list[dict] | None = None):
    """The C input of ``variant`` from the K1 prepared arrays; returns (t, f, e, info)."""
    if variant not in VARIANTS:
        raise ValueError("Unregistered C variant " + str(variant))
    t, f, e = (np.asarray(arrays[k], float) for k in ("time", "flux", "flux_err"))
    info = {"variant": variant, "n_k1_input": int(len(t)), "siblings": list(siblings or []),
            "bin_errors": BIN_ERRORS if variant != "K1" else None}
    sec = None
    if variant in PER_PRODUCT_10:
        sec = point_sectors(t, arrays["time_unbinned"], arrays["sector_unbinned"])
    masked = sibling_mask(t, siblings)
    info["n_sibling_masked"] = int(masked.sum())
    if masked.any():
        t, f, e = t[~masked], f[~masked], e[~masked]
        sec = None if sec is None else sec[~masked]
    if variant in WHOLE_30:
        t, f, e = bin_series(t, f, e, 30.0)
    elif variant in PER_PRODUCT_10:
        cad = {int(p["sector"]): float(p["cadence_s"]) for p in products}
        t, f, e = bin_per_product(t, f, e, sec, cad, 10.0)
    info.update(n_c_input=int(len(t)), baseline_days=float(t.max() - t.min()) if len(t) else 0.0)
    return t, f, e, info


def install(A, tic: int, period: float, variant: str, siblings: list[dict] | None = None) -> dict:
    """Patch ``A.load_prepared`` so this candidate's Stage C reads its K2 C input.  Returns the input record."""
    A.prepare_step(tic, period)                              # cached: K1's prepared series of this case root
    key = A.key(tic, period)
    meta = A.jload(A.OUT / "prep" / f"{key}.json")
    with np.load(A.OUT / "tls" / f"{key}_lc.npz") as z:
        arrays = {k: z[k] for k in ("time", "flux", "flux_err", "time_unbinned", "sector_unbinned")}
    t, f, e, info = transform(arrays, meta["products"], variant, siblings)
    info["oversampling"] = oversampling(variant, info["baseline_days"])
    original = A.load_prepared

    def load_prepared(tic_, period_, suffix=""):
        if int(tic_) == int(tic) and abs(float(period_) / float(period) - 1.0) < 1e-12 and suffix == "":
            return t.copy(), f.copy(), e.copy()
        return original(tic_, period_, suffix)
    A.load_prepared = load_prepared
    return info
