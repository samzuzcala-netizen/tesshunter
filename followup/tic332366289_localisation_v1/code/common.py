"""Shared paths and environment for the TIC 332366289 localisation follow-up.

This is NEW post-P12 follow-up code. It never writes to any historical
P1-P12 location. Historical inputs are opened read-only.

Import this module FIRST (before astropy / matplotlib / astroquery) so the
cache redirection below takes effect.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

# ---------------------------------------------------------------- locations
REPO = Path(r"C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter")
WS = REPO / "followup" / "tic332366289_localisation_v1"          # small outputs
BIG = Path(r"D:\tesshunter_followup\tic332366289_localisation_v1")  # downloads / arrays

CODE = WS / "code"
RESULTS = WS / "results"
FIGURES = WS / "figures"
INPUTS = WS / "inputs"
LOGS = WS / "logs"

PRF_DIR = BIG / "prf"
ARRAYS = BIG / "arrays"
CACHE = BIG / "cache"

# --------------------------------------------------- cache redirection (new)
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
os.environ["MPLCONFIGDIR"] = str(BIG / "mpl")
os.environ["XDG_CACHE_HOME"] = str(BIG / "astropy_cache")
os.environ["XDG_CONFIG_HOME"] = str(BIG / "astropy_config")
(BIG / "astropy_cache" / "astropy").mkdir(parents=True, exist_ok=True)
(BIG / "astropy_config" / "astropy").mkdir(parents=True, exist_ok=True)
# numerical threads limited to one (resource rule)
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[_v] = "1"

# ------------------------------------------------- historical inputs (R/O)
CASE = REPO / "data" / "survey" / "p12" / "funnel" / "final" / "cases" / "tic332366289_p02"
PACKET = REPO / "docs" / "packets" / "audit_p12" / "tic332366289_p02" / "tic332366289_P18.7481"
TESSCUT_DIR = Path(r"D:\tesshunter_data\survey_p12\lightkurve\tesscut")
ACQ = Path(r"D:\tesshunter_data\survey_p12\lightkurve\acquisition\tic332366289\attempt1\mastDownload\HLSP")

TESSCUT = {
    57: TESSCUT_DIR / "tess-s0057-4-4_257.222579_50.487785_21x21_astrocut.fits",
    77: TESSCUT_DIR / "tess-s0077-2-1_257.222579_50.487785_21x21_astrocut.fits",
    78: TESSCUT_DIR / "tess-s0078-2-1_257.222579_50.487785_21x21_astrocut.fits",
    79: TESSCUT_DIR / "tess-s0079-2-2_257.222579_50.487785_21x21_astrocut.fits",
    80: TESSCUT_DIR / "tess-s0080-3-4_257.222579_50.487785_21x21_astrocut.fits",
    84: TESSCUT_DIR / "tess-s0084-4-4_257.222579_50.487785_21x21_astrocut.fits",
}


def spoc_lc(sector: int) -> Path:
    d = f"hlsp_tess-spoc_tess_phot_0000000332366289-s{sector:04d}_tess_v1_tp"
    f = f"hlsp_tess-spoc_tess_phot_0000000332366289-s{sector:04d}_tess_v1_lc.fits"
    return ACQ / d / f


TIC = 332366289
GAIA_TARGET = "1415338513130475136"   # string on purpose: never a float
LISTED_NEIGHBOURS = [
    "1415338306971353600",
    "1415338337035983488",
    "1415338337035990528",
    "1415338405755460480",
]
PRIMARY_SECTORS = (57, 79, 80)
DIAGNOSTIC_SECTORS = (84,)


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def write_json(path: Path, obj, indent: int = 1) -> None:
    """Strict JSON (no NaN/inf) to a NEW follow-up location only."""
    path = Path(path)
    assert str(path).startswith(str(WS)) or str(path).startswith(str(BIG)), path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=indent, allow_nan=False, default=_default)
    os.replace(tmp, path)


def _default(o):
    import numpy as np
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        v = float(o)
        if v != v or v in (float("inf"), float("-inf")):
            return None
        return v
    if isinstance(o, np.ndarray):
        return [_default(x) if not isinstance(x, (list, np.ndarray)) else _default(x) for x in o.tolist()]
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def clean(obj):
    """Recursively replace NaN/inf floats by None so strict JSON works."""
    import math
    import numpy as np
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return clean(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    return obj
