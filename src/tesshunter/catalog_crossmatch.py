"""Known-object cross-match: the hard stop before any search.

A target is **REJECTED** before search if its TIC ID appears in any of the
sources below, and **FLAGGED** if a known object sits within one TESS pixel
(21 arcsec) of it under a different TIC ID:

``toi``
    ExoFOP-TESS TOI list (``download_toi.php``).
``ctoi``
    ExoFOP-TESS community TOI list (``download_ctoi.php``).
``nasa_ps``
    NASA Exoplanet Archive Planetary Systems table (``ps``), every reference row.
``nasa_pscomppars``
    NASA Exoplanet Archive Planetary Systems composite table (``pscomppars``).
``tess_eb``
    TESS Eclipsing Binary catalog, Prsa et al. 2022 (MAST HLSP ``tess-ebs``).
``spoc_tce``
    SPOC threshold-crossing events from every single-sector and multi-sector
    Data Validation run published under MAST ``missions/tess/catalogs/tce``
    (including ``new_versions/`` re-deliveries).

QLP TCE and QLP faint-star TCE lists are not published as bulk products
(probed 2026-09-01: the QLP HLSP on MAST carries light curves only); the
QLP-derived TOIs are covered by the ExoFOP TOI list.

Every catalog is cached on disk under ``data/cache/catalogs/<source>/`` with a
sidecar ``.meta.json`` version stamp (URLs, fetch time, byte counts, sha256).
The cache is refreshed after :data:`CATALOG_MAX_AGE_S` (7 days).  A fetch
failure raises :class:`CatalogFetchError`; it never degrades to "no match".
Only an explicit ``allow_stale=True`` may fall back to an out-of-date cache,
and that is recorded in the version stamp.

The SPOC TCE tables carry TIC IDs but no coordinates.  Every unique TCE host
TIC ID is therefore resolved to TIC coordinates through a bulk MAST query
(``Catalogs.query_criteria(catalog="Tic", ID=[...])`` in chunks), cached
under ``spoc_tce/tic_coords.csv`` with a provenance stamp, and merged into the
normalized TCE table so TCE hosts sit in the same 21-arcsec coordinate tree as
every other source.  Resolution failures are loud: a query failure raises
:class:`CatalogFetchError`, and any TIC ID the TIC does not return is listed in
the stamp and also raises unless ``allow_partial_coords=True`` is passed, in
which case the version string carries ``!partialcoords``.  Caller-supplied TIC
neighbours (the survey builder passes every TIC star in the tile) remain a
second, independent path to the same answer; the single-target path resolves
them with one TIC cone query when ``resolve_neighbours=True``.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import io
import json
import logging
import re
import time
import urllib.error
import urllib.request
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional

import numpy as np
import pandas as pd

from .config import CACHE_DIR

logger = logging.getLogger(__name__)

# ── Policy constants ──────────────────────────────────────────────────────────
CATALOG_MAX_AGE_S = 7 * 24 * 3600          # 7-day refresh
MATCH_RADIUS_ARCSEC = 21.0                 # one TESS pixel
SCHEMA_VERSION = 2                         # 2: coordinate-less sources carry TIC-resolved ra/dec
_HTTP_TIMEOUT_S = 180
_USER_AGENT = "tesshunter/0.1 (catalog cross-match; python-urllib)"

# Overridable at run time (tests point this at a temp dir).
CATALOG_CACHE_DIR: Path = CACHE_DIR / "catalogs"

# ── Source URLs ───────────────────────────────────────────────────────────────
EXOFOP_TOI_URL = "https://exofop.ipac.caltech.edu/tess/download_toi.php?sort=toi&output=csv"
EXOFOP_CTOI_URL = "https://exofop.ipac.caltech.edu/tess/download_ctoi.php?sort=ctoi&output=csv"
NASA_TAP_SYNC = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
NASA_PS_URL = (
    NASA_TAP_SYNC
    + "?query=select+pl_name,hostname,tic_id,ra,dec,default_flag,disc_facility+from+ps"
    + "&format=csv"
)
NASA_PSCOMPPARS_URL = (
    NASA_TAP_SYNC
    + "?query=select+pl_name,hostname,tic_id,ra,dec,disc_facility+from+pscomppars&format=csv"
)
TESS_EB_URL = (
    "https://archive.stsci.edu/hlsps/tess-ebs/"
    "hlsp_tess-ebs_tess_lcf-ffi_s0001-s0026_tess_v1.0_cat.csv"
)
SPOC_TCE_INDEX_URL = "https://archive.stsci.edu/missions/tess/catalogs/tce/"
SPOC_TCE_SUBDIRS = ("", "new_versions/")

_TCE_FILE_RE = re.compile(r"tess\d{13}-s(\d{4})-s(\d{4})_dvr-tcestats\.csv")
_TCE_HREF_RE = re.compile(r'href="(tess\d{13}-s\d{4}-s\d{4}_dvr-tcestats\.csv)"')


class CatalogFetchError(RuntimeError):
    """A known-object catalog could not be fetched or parsed.

    Raised loudly: a target must never pass the hard stop because a catalog
    was unreachable.
    """


# ── HTTP layer (monkeypatched by tests) ───────────────────────────────────────
def _http_get(url: str, timeout: float = _HTTP_TIMEOUT_S) -> bytes:
    """GET ``url`` and return the body bytes.  Raises CatalogFetchError."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            body = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        raise CatalogFetchError(f"fetch failed for {url}: {exc}") from exc
    if status != 200:
        raise CatalogFetchError(f"fetch failed for {url}: HTTP {status}")
    if not body:
        raise CatalogFetchError(f"fetch returned an empty body for {url}")
    return body


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: str) -> float:
    return _dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=_dt.timezone.utc
    ).timestamp()


# ── Normalized schema helpers ─────────────────────────────────────────────────
NORMALIZED_COLUMNS = ["source", "tic_id", "ra", "dec", "label", "detail"]


def _finalize(source: str, df: pd.DataFrame) -> pd.DataFrame:
    """Coerce to the normalized schema, drop rows without a parsable TIC ID."""
    n = len(df)
    out = pd.DataFrame(
        {
            "source": [source] * n,
            "tic_id": pd.to_numeric(df["tic_id"], errors="coerce").to_numpy(dtype=float),
            "ra": (pd.to_numeric(df["ra"], errors="coerce").to_numpy(dtype=float)
                   if "ra" in df else np.full(n, np.nan)),
            "dec": (pd.to_numeric(df["dec"], errors="coerce").to_numpy(dtype=float)
                    if "dec" in df else np.full(n, np.nan)),
            "label": df["label"].astype(str).to_numpy() if "label" in df else [""] * n,
            "detail": df["detail"].astype(str).to_numpy() if "detail" in df else [""] * n,
        }
    )
    out = out[np.isfinite(out["tic_id"].to_numpy(dtype=float))].copy()
    out["tic_id"] = out["tic_id"].astype("int64")
    out = out[out["tic_id"] > 0]
    return out.reset_index(drop=True)[NORMALIZED_COLUMNS]


def _sexagesimal_to_deg(ra: pd.Series, dec: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Convert ExoFOP 'hh:mm:ss.ss' / '+dd:mm:ss.s' strings to degrees.

    Rows already in decimal degrees are passed through.
    """
    ra = ra.astype(str).str.strip()
    dec = dec.astype(str).str.strip()
    ra_deg = np.full(len(ra), np.nan)
    dec_deg = np.full(len(dec), np.nan)
    sexa = (ra.str.contains(":", regex=False) & dec.str.contains(":", regex=False)).to_numpy()
    if sexa.any():
        from astropy import units as u
        from astropy.coordinates import SkyCoord

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            c = SkyCoord(
                ra[sexa].tolist(), dec[sexa].tolist(), unit=(u.hourangle, u.deg)
            )
        ra_deg[sexa] = c.ra.deg
        dec_deg[sexa] = c.dec.deg
    rest = ~sexa
    if rest.any():
        ra_deg[rest] = pd.to_numeric(ra[rest], errors="coerce").to_numpy()
        dec_deg[rest] = pd.to_numeric(dec[rest], errors="coerce").to_numpy()
    return ra_deg, dec_deg


def _tic_from_string(series: pd.Series) -> pd.Series:
    """'TIC 123456' -> 123456; blanks/None -> NaN."""
    s = series.astype(str).str.extract(r"(\d+)", expand=False)
    return pd.to_numeric(s, errors="coerce")


def _read_csv_bytes(data: bytes, **kw) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(data), **kw)


def _col_or_blank(df: pd.DataFrame, col: str) -> np.ndarray:
    if col in df.columns:
        return df[col].fillna("").astype(str).to_numpy()
    return np.array([""] * len(df), dtype=object)


# ── Per-source fetch + parse ──────────────────────────────────────────────────
# A fetcher yields (filename, bytes) pairs.  A parser consumes an iterable of
# (filename, bytes) and returns a normalized DataFrame.

def _fetch_single(url: str, filename: str) -> Callable[[Path], Iterator[tuple[str, bytes]]]:
    def fetch(raw_dir: Path) -> Iterator[tuple[str, bytes]]:
        yield filename, _http_get(url)
    fetch.urls = lambda: [url]  # type: ignore[attr-defined]
    fetch.single = True         # type: ignore[attr-defined]
    return fetch


def _parse_toi(files: Iterable[tuple[str, bytes]]) -> pd.DataFrame:
    _, data = next(iter(files))
    df = _read_csv_bytes(data, comment=None, low_memory=False)
    if "TIC ID" not in df.columns or "TOI" not in df.columns:
        raise CatalogFetchError(f"ExoFOP TOI CSV missing expected columns: {list(df.columns)[:8]}")
    ra, dec = _sexagesimal_to_deg(df["RA"], df["Dec"])
    return _finalize(
        "toi",
        pd.DataFrame(
            {
                "tic_id": df["TIC ID"].to_numpy(),
                "ra": ra,
                "dec": dec,
                "label": np.char.add("TOI-", df["TOI"].astype(str).to_numpy().astype(str)),
                "detail": np.char.add("TFOPWG=", _col_or_blank(df, "TFOPWG Disposition").astype(str)),
            }
        ),
    )


def _parse_ctoi(files: Iterable[tuple[str, bytes]]) -> pd.DataFrame:
    _, data = next(iter(files))
    df = _read_csv_bytes(data, comment=None, low_memory=False)
    if "TIC ID" not in df.columns or "CTOI" not in df.columns:
        raise CatalogFetchError(f"ExoFOP CTOI CSV missing expected columns: {list(df.columns)[:8]}")
    ra, dec = _sexagesimal_to_deg(df["RA"], df["Dec"])
    return _finalize(
        "ctoi",
        pd.DataFrame(
            {
                "tic_id": df["TIC ID"].to_numpy(),
                "ra": ra,
                "dec": dec,
                "label": np.char.add("CTOI-", df["CTOI"].astype(str).to_numpy().astype(str)),
                "detail": np.char.add("promoted_to_TOI=", _col_or_blank(df, "Promoted to TOI").astype(str)),
            }
        ),
    )


def _parse_nasa(source: str):
    def parse(files: Iterable[tuple[str, bytes]]) -> pd.DataFrame:
        _, data = next(iter(files))
        df = _read_csv_bytes(data, low_memory=False)
        for col in ("pl_name", "tic_id", "ra", "dec"):
            if col not in df.columns:
                raise CatalogFetchError(f"NASA {source} CSV missing column {col!r}")
        return _finalize(
            source,
            pd.DataFrame(
                {
                    "tic_id": _tic_from_string(df["tic_id"]).to_numpy(),
                    "ra": df["ra"].to_numpy(),
                    "dec": df["dec"].to_numpy(),
                    "label": df["pl_name"].astype(str).to_numpy(),
                    "detail": _col_or_blank(df, "disc_facility"),
                }
            ),
        )
    return parse


def _parse_tess_eb(files: Iterable[tuple[str, bytes]]) -> pd.DataFrame:
    _, data = next(iter(files))
    df = _read_csv_bytes(data, low_memory=False)
    for col in ("tess_id", "ra", "dec", "period"):
        if col not in df.columns:
            raise CatalogFetchError(f"TESS EB CSV missing column {col!r}")
    sig = _col_or_blank(df, "signal_id").astype(str)
    per = pd.to_numeric(df["period"], errors="coerce").round(6).astype(str).to_numpy().astype(str)
    return _finalize(
        "tess_eb",
        pd.DataFrame(
            {
                "tic_id": df["tess_id"].to_numpy(),
                "ra": df["ra"].to_numpy(),
                "dec": df["dec"].to_numpy(),
                "label": np.char.add(
                    np.char.add("TESS-EB ", df["tess_id"].astype(str).to_numpy().astype(str)),
                    np.char.add(".", sig),
                ),
                "detail": np.char.add(np.char.add("P=", per), "d"),
            }
        ),
    )


def _list_spoc_tce_files() -> list[tuple[str, str]]:
    """Return [(key, url)] for every tcestats CSV on the MAST index pages."""
    out: dict[str, str] = {}
    for sub in SPOC_TCE_SUBDIRS:
        index_url = SPOC_TCE_INDEX_URL + sub
        html = _http_get(index_url).decode("utf-8", errors="replace")
        names = sorted(set(_TCE_HREF_RE.findall(html)))
        if not names and sub == "":
            raise CatalogFetchError(f"no tcestats files listed at {index_url}")
        for name in names:
            key = (sub.strip("/") + "/" + name) if sub else name
            out[key] = index_url + name
    return sorted(out.items())


def _fetch_spoc_tce(raw_dir: Path, *, force: bool = False) -> Iterator[tuple[str, bytes]]:
    """Yield every TCE stats file, downloading only those not already cached.

    The per-run files are immutable once published, so a cached raw copy is
    reused; the index listing is always refreshed so new runs are picked up.
    ``force=True`` also re-downloads every listed version file.
    """
    for key, url in _list_spoc_tce_files():
        local = raw_dir / key.replace("/", "__")
        if not force and local.exists() and local.stat().st_size > 0:
            yield key, local.read_bytes()
        else:
            data = _http_get(url)
            local.parent.mkdir(parents=True, exist_ok=True)
            if force:
                temporary = local.with_name(local.name + ".refetch.tmp")
                temporary.write_bytes(data)
                temporary.replace(local)
            else:
                local.write_bytes(data)
            yield key, data


_fetch_spoc_tce.urls = lambda: [SPOC_TCE_INDEX_URL + s for s in SPOC_TCE_SUBDIRS]  # type: ignore[attr-defined]
_fetch_spoc_tce.single = False  # type: ignore[attr-defined]


def _parse_spoc_tce(files: Iterable[tuple[str, bytes]]) -> pd.DataFrame:
    frames = []
    n_files = 0
    for name, data in files:
        n_files += 1
        df = _read_csv_bytes(data, comment="#", low_memory=False)
        if "ticid" not in df.columns:
            raise CatalogFetchError(f"TCE file {name} has no 'ticid' column")
        m = _TCE_FILE_RE.search(name)
        run = f"s{m.group(1)}-s{m.group(2)}" if m else name
        pn = _col_or_blank(df, "tce_plnt_num").astype(str)
        per = (pd.to_numeric(df["tce_period"], errors="coerce").round(5).astype(str).to_numpy().astype(str)
               if "tce_period" in df else np.array(["nan"] * len(df)))
        snr = (pd.to_numeric(df["tce_model_snr"], errors="coerce").round(1).astype(str).to_numpy().astype(str)
               if "tce_model_snr" in df else np.array(["nan"] * len(df)))
        frames.append(
            pd.DataFrame(
                {
                    "tic_id": df["ticid"].to_numpy(),
                    "ra": np.full(len(df), np.nan),
                    "dec": np.full(len(df), np.nan),
                    "label": np.char.add(f"TCE {run} pn", pn),
                    "detail": np.char.add(np.char.add(np.char.add("P=", per), "d SNR="), snr),
                }
            )
        )
    if n_files == 0:
        raise CatalogFetchError("no SPOC TCE files were fetched")
    return _finalize("spoc_tce", pd.concat(frames, ignore_index=True))


# ── TIC coordinate resolution for sources without coordinates (SPOC TCE) ─────
TIC_COORD_CHUNK = 3000
TIC_COORD_PROVENANCE = "TIC 8.2 via astroquery.mast Catalogs.query_criteria(catalog='Tic', ID=chunk)"


def _query_tic_by_ids(ids: list[int]) -> pd.DataFrame:
    """One MAST TIC query for a list of IDs.  Monkeypatched by tests.

    Returns a frame with ``tic_id, ra, dec, tmag, objtype``.  Raises
    CatalogFetchError on any query failure.
    """
    try:
        from astroquery.mast import Catalogs

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tab = Catalogs.query_criteria(catalog="Tic", ID=[int(x) for x in ids])
    except Exception as exc:
        raise CatalogFetchError(f"TIC coordinate query failed for {len(ids)} IDs: {exc}") from exc
    if tab is None or len(tab) == 0:
        return pd.DataFrame(columns=["tic_id", "ra", "dec", "tmag", "objtype"])
    df = tab.to_pandas()
    out = pd.DataFrame({
        "tic_id": pd.to_numeric(df["ID"], errors="coerce"),
        "ra": pd.to_numeric(df["ra"], errors="coerce"),
        "dec": pd.to_numeric(df["dec"], errors="coerce"),
        "tmag": pd.to_numeric(df["Tmag"], errors="coerce") if "Tmag" in df else np.nan,
        "objtype": df["objType"].astype(str) if "objType" in df else "",
    })
    out = out[np.isfinite(out["tic_id"].to_numpy(dtype=float))]
    out["tic_id"] = out["tic_id"].astype("int64")
    return out.reset_index(drop=True)


def _coords_path(name: str) -> Path:
    return _source_dir(name) / "tic_coords.csv"


def _coords_meta_path(name: str) -> Path:
    return _source_dir(name) / "tic_coords.meta.json"


def resolve_tic_coordinates(
    name: str,
    tic_ids: Iterable[int],
    *,
    chunk: int = TIC_COORD_CHUNK,
    max_retries: int = 3,
) -> tuple[pd.DataFrame, dict]:
    """Resolve TIC coordinates for ``tic_ids``, using and extending the on-disk cache.

    Returns ``(coords, stamp)``.  ``coords`` has one row per resolved ID
    (``tic_id, ra, dec, tmag, objtype``).  ``stamp`` records provenance:
    requested / resolved / unresolved counts, the unresolved IDs, fetch time,
    chunk size, and the sha256 of the cache file.  TIC coordinates do not
    change for a fixed TIC version, so cached rows are reused indefinitely;
    only IDs absent from the cache are queried.
    """
    ids = np.unique(np.asarray(list(tic_ids), dtype=np.int64))
    cpath, mpath = _coords_path(name), _coords_meta_path(name)
    cached = pd.DataFrame(columns=["tic_id", "ra", "dec", "tmag", "objtype"])
    prev_unresolved: set[int] = set()
    if cpath.exists():
        try:
            cached = pd.read_csv(cpath, dtype={"objtype": str}, keep_default_na=False)
            cached["tic_id"] = pd.to_numeric(cached["tic_id"]).astype("int64")
            for c in ("ra", "dec", "tmag"):
                cached[c] = pd.to_numeric(cached[c], errors="coerce")
        except Exception as exc:
            logger.warning("Unreadable coordinate cache %s (%s); rebuilding", cpath, exc)
            cached = pd.DataFrame(columns=["tic_id", "ra", "dec", "tmag", "objtype"])
    if mpath.exists():
        try:
            prev_unresolved = set(int(x) for x in json.loads(mpath.read_text()).get("unresolved_tic_ids", []))
        except Exception:
            prev_unresolved = set()
    have = set(int(t) for t in cached["tic_id"].tolist())
    todo = [int(t) for t in ids if int(t) not in have]
    n_queried = 0
    new_frames = []
    for i in range(0, len(todo), chunk):
        block = todo[i:i + chunk]
        last = None
        for attempt in range(max_retries):
            try:
                got = _query_tic_by_ids(block)
                last = None
                break
            except CatalogFetchError as exc:
                last = exc
                time.sleep(2.0 * (attempt + 1))
        if last is not None:
            raise last
        n_queried += len(block)
        if len(got):
            new_frames.append(got)
        logger.info("TIC coordinates for %s: %d/%d resolved so far", name, min(i + chunk, len(todo)), len(todo))
    if new_frames:
        parts = [f for f in ([cached] + new_frames) if len(f)]
        cached = pd.concat(parts, ignore_index=True) if parts else cached
        cached = cached.drop_duplicates("tic_id", keep="first")
    ok = np.isfinite(cached["ra"].to_numpy(dtype=float)) & np.isfinite(cached["dec"].to_numpy(dtype=float))
    cached = cached[ok].reset_index(drop=True)
    resolved = cached[cached["tic_id"].isin(ids)].reset_index(drop=True)
    resolved_ids = set(resolved["tic_id"].tolist())
    unresolved = sorted(int(t) for t in ids if int(t) not in resolved_ids)
    cpath.parent.mkdir(parents=True, exist_ok=True)
    cached.to_csv(cpath, index=False)
    stamp = {
        "source": name,
        "provenance": TIC_COORD_PROVENANCE,
        "chunk_size": chunk,
        "n_requested": int(len(ids)),
        "n_resolved": int(len(resolved)),
        "n_unresolved": int(len(unresolved)),
        "unresolved_tic_ids": unresolved[:1000],
        "n_queried_this_run": int(n_queried),
        "n_cached_rows": int(len(cached)),
        "resolved_utc": _utcnow_iso() if n_queried else (json.loads(mpath.read_text()).get("resolved_utc") if mpath.exists() else _utcnow_iso()),
        "cache_sha256": _sha256(cpath.read_bytes()),
        "n_fainter_than_tmag17": int((resolved["tmag"] > 17).sum()),
        "n_non_star_objtype": int((resolved["objtype"].astype(str).str.upper() != "STAR").sum()),
    }
    mpath.write_text(json.dumps(stamp, indent=1), encoding="utf-8")
    if unresolved and set(unresolved) != prev_unresolved:
        logger.warning("%s: %d TIC IDs could not be resolved to coordinates", name, len(unresolved))
    return resolved, stamp


def attach_tic_coordinates(name: str, df: pd.DataFrame, *, allow_partial: bool = False) -> tuple[pd.DataFrame, dict]:
    """Fill ``ra``/``dec`` of a coordinate-less normalized table from the TIC.

    Raises CatalogFetchError when any ID stays unresolved unless
    ``allow_partial=True``; then the rows stay NaN and the stamp says so.
    """
    coords, stamp = resolve_tic_coordinates(name, df["tic_id"].to_numpy())
    merged = df.drop(columns=["ra", "dec"]).merge(coords[["tic_id", "ra", "dec"]], on="tic_id", how="left")
    merged = merged[NORMALIZED_COLUMNS]
    if stamp["n_unresolved"] and not allow_partial:
        raise CatalogFetchError(
            f"{name}: {stamp['n_unresolved']} of {stamp['n_requested']} TCE host TIC IDs have no TIC "
            f"coordinates (first: {stamp['unresolved_tic_ids'][:5]}); pass allow_partial_coords=True to "
            "accept a partial coordinate tree (the gap is then stamped '!partialcoords')"
        )
    stamp["partial"] = bool(stamp["n_unresolved"])
    return merged, stamp


@dataclass(frozen=True)
class SourceSpec:
    name: str
    description: str
    has_coords: bool
    fetch: Callable[[Path], Iterator[tuple[str, bytes]]]
    parse: Callable[[Iterable[tuple[str, bytes]]], pd.DataFrame]
    resolve_coords: bool = False     # coordinates come from a TIC lookup after parsing


SOURCES: dict[str, SourceSpec] = {
    "toi": SourceSpec(
        "toi", "ExoFOP-TESS TOI list", True,
        _fetch_single(EXOFOP_TOI_URL, "exofop_toi.csv"), _parse_toi,
    ),
    "ctoi": SourceSpec(
        "ctoi", "ExoFOP-TESS community TOI list", True,
        _fetch_single(EXOFOP_CTOI_URL, "exofop_ctoi.csv"), _parse_ctoi,
    ),
    "nasa_ps": SourceSpec(
        "nasa_ps", "NASA Exoplanet Archive Planetary Systems (ps)", True,
        _fetch_single(NASA_PS_URL, "nasa_ps.csv"), _parse_nasa("nasa_ps"),
    ),
    "nasa_pscomppars": SourceSpec(
        "nasa_pscomppars", "NASA Exoplanet Archive PS composite (pscomppars)", True,
        _fetch_single(NASA_PSCOMPPARS_URL, "nasa_pscomppars.csv"),
        _parse_nasa("nasa_pscomppars"),
    ),
    "tess_eb": SourceSpec(
        "tess_eb", "TESS Eclipsing Binary catalog, Prsa et al. 2022 (HLSP tess-ebs)", True,
        _fetch_single(TESS_EB_URL, "hlsp_tess-ebs_s0001-s0026_v1.0_cat.csv"), _parse_tess_eb,
    ),
    "spoc_tce": SourceSpec(
        "spoc_tce", "SPOC DV threshold-crossing events, all sector and multi-sector runs", True,
        _fetch_spoc_tce, _parse_spoc_tce, resolve_coords=True,
    ),
}


# ── Version stamps and on-disk cache ──────────────────────────────────────────
@dataclass
class CatalogVersion:
    name: str
    urls: list[str]
    fetched_utc: str
    n_rows: int
    n_files: int
    n_bytes: int
    sha256: str                     # sha256 over the sorted raw file digests
    normalized_sha256: str
    schema_version: int = SCHEMA_VERSION
    stale: bool = False
    files: list[dict] = field(default_factory=list)
    coords: Optional[dict] = None    # TIC coordinate-resolution stamp for coordinate-less sources

    def short(self) -> str:
        flag = "!stale" if self.stale else ""
        if self.coords and self.coords.get("partial"):
            flag += "!partialcoords"
        return f"{self.name}={self.fetched_utc[:10]}:{self.sha256[:8]}{flag}"


def _source_dir(name: str) -> Path:
    return Path(CATALOG_CACHE_DIR) / name


def _meta_path(name: str) -> Path:
    return _source_dir(name) / f"{name}.meta.json"


def _norm_path(name: str) -> Path:
    return _source_dir(name) / f"{name}.normalized.csv"


def _read_meta(name: str) -> Optional[CatalogVersion]:
    p = _meta_path(name)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return CatalogVersion(**d)
    except Exception as exc:  # corrupt stamp counts as no cache
        logger.warning("Unreadable catalog stamp %s: %s", p, exc)
        return None


def _load_normalized(name: str) -> Optional[pd.DataFrame]:
    p = _norm_path(name)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(
            p, dtype={"source": str, "label": str, "detail": str}, keep_default_na=False,
        )
        df["tic_id"] = pd.to_numeric(df["tic_id"]).astype("int64")
        df["ra"] = pd.to_numeric(df["ra"], errors="coerce")
        df["dec"] = pd.to_numeric(df["dec"], errors="coerce")
        return df[NORMALIZED_COLUMNS]
    except Exception as exc:
        logger.warning("Unreadable normalized catalog %s: %s", p, exc)
        return None


def _is_fresh(meta: Optional[CatalogVersion], max_age_s: float) -> bool:
    if meta is None or meta.schema_version != SCHEMA_VERSION or meta.stale:
        return False
    try:
        return (time.time() - _parse_iso(meta.fetched_utc)) < max_age_s
    except Exception:
        return False


def _fetch_and_normalize(spec: SourceSpec, *, allow_partial_coords: bool = False) -> tuple[pd.DataFrame, CatalogVersion]:
    raw_dir = _source_dir(spec.name) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    file_records: list[dict] = []
    digest_parts: list[str] = []
    n_bytes = 0
    writes_own_raw = not getattr(spec.fetch, "single", True)

    def _tee() -> Iterator[tuple[str, bytes]]:
        nonlocal n_bytes
        for fname, data in spec.fetch(raw_dir):
            h = _sha256(data)
            file_records.append({"filename": fname, "n_bytes": len(data), "sha256": h})
            digest_parts.append(h)
            n_bytes += len(data)
            if not writes_own_raw:
                (raw_dir / fname).write_bytes(data)
            yield fname, data

    try:
        df = spec.parse(_tee())
    except CatalogFetchError:
        raise
    except Exception as exc:
        raise CatalogFetchError(f"{spec.name}: parse failed: {exc}") from exc
    if df.empty:
        raise CatalogFetchError(
            f"{spec.name}: parsed 0 rows, refusing to treat that as 'no known objects'"
        )
    coord_stamp = None
    if spec.resolve_coords:
        df, coord_stamp = attach_tic_coordinates(spec.name, df, allow_partial=allow_partial_coords)

    norm_bytes = df.to_csv(index=False).encode("utf-8")
    _norm_path(spec.name).write_bytes(norm_bytes)
    urls_fn = getattr(spec.fetch, "urls", None)
    ver = CatalogVersion(
        name=spec.name,
        urls=list(urls_fn()) if urls_fn else [],
        fetched_utc=_utcnow_iso(),
        n_rows=int(len(df)),
        n_files=len(file_records),
        n_bytes=int(n_bytes),
        sha256=_sha256("".join(sorted(digest_parts)).encode()),
        normalized_sha256=_sha256(norm_bytes),
        files=file_records,
        coords=coord_stamp,
    )
    _meta_path(spec.name).write_text(json.dumps(asdict(ver), indent=1), encoding="utf-8")
    logger.info("Catalog %s: %d rows from %d file(s), %.1f MB", spec.name, len(df),
                len(file_records), n_bytes / 1e6)
    return df, ver


def _check_coord_coverage(spec: SourceSpec, df: pd.DataFrame, meta: CatalogVersion, allow_partial: bool) -> None:
    """A cached coordinate-resolved table must not silently carry unresolved rows."""
    if not spec.resolve_coords:
        return
    n_missing = int((~(np.isfinite(df["ra"].to_numpy(dtype=float)) & np.isfinite(df["dec"].to_numpy(dtype=float)))).sum())
    if n_missing and not allow_partial:
        raise CatalogFetchError(
            f"{spec.name}: cached table has {n_missing} rows without coordinates; refresh the cache or pass "
            "allow_partial_coords=True"
        )
    if meta.coords is None:
        meta.coords = {"partial": bool(n_missing), "n_unresolved_rows": n_missing, "provenance": "cached table"}


def load_source(
    name: str,
    *,
    refresh: bool = False,
    allow_stale: bool = False,
    offline: bool = False,
    max_age_s: float = CATALOG_MAX_AGE_S,
    allow_partial_coords: bool = False,
) -> tuple[pd.DataFrame, CatalogVersion]:
    """Return (normalized table, version stamp) for one source.

    Cache policy: a stamp younger than ``max_age_s`` is served from disk.
    Otherwise the source is re-fetched; a failure raises
    :class:`CatalogFetchError` unless ``allow_stale=True`` and an old copy
    exists, in which case the copy is returned with ``stale=True`` stamped.
    ``offline=True`` serves whatever is cached regardless of age (stamped
    stale when out of date) and raises if nothing is cached.
    """
    if name not in SOURCES:
        raise KeyError(f"unknown catalog source {name!r}; known: {sorted(SOURCES)}")
    spec = SOURCES[name]
    meta = _read_meta(name)
    fresh = _is_fresh(meta, max_age_s)

    if offline:
        df = _load_normalized(name)
        if df is None or meta is None:
            raise CatalogFetchError(f"{name}: offline requested but nothing is cached")
        _check_coord_coverage(spec, df, meta, allow_partial_coords)
        if not fresh:
            meta.stale = True
            logger.warning("Catalog %s served OFFLINE and out of date (fetched %s)",
                           name, meta.fetched_utc)
        return df, meta

    if fresh and not refresh:
        df = _load_normalized(name)
        if df is not None:
            _check_coord_coverage(spec, df, meta, allow_partial_coords)
            return df, meta
        logger.info("Catalog %s: stamp is fresh but table missing; re-fetching", name)

    try:
        return _fetch_and_normalize(spec, allow_partial_coords=allow_partial_coords)
    except CatalogFetchError as exc:
        old = _load_normalized(name) if meta is not None else None
        if allow_stale and old is not None:
            meta.stale = True
            logger.warning("Catalog %s: fetch failed (%s); using STALE cache from %s",
                           name, exc, meta.fetched_utc)
            return old, meta
        raise


# ── Results ───────────────────────────────────────────────────────────────────
STATUS_REJECT = "REJECT"
STATUS_FLAG = "FLAG"
STATUS_CLEAN = "CLEAN"


@dataclass
class HardStopResult:
    tic_id: int
    status: str
    tic_matches: list[dict] = field(default_factory=list)       # same TIC ID in a source
    neighbour_matches: list[dict] = field(default_factory=list) # known object within 21" under another TIC
    catalog_stamp: str = ""
    neighbours_resolved: bool = False

    @property
    def rejected(self) -> bool:
        return self.status == STATUS_REJECT

    @property
    def flagged(self) -> bool:
        return self.status == STATUS_FLAG

    def summary(self) -> str:
        if self.rejected:
            hits = "; ".join(f"{m['source']}:{m['label']}" for m in self.tic_matches[:6])
            more = "" if len(self.tic_matches) <= 6 else f" (+{len(self.tic_matches) - 6} more)"
            return f"REJECT: TIC {self.tic_id} is a known object: {hits}{more}"
        if self.flagged:
            hits = "; ".join(
                f"{m['source']}:{m['label']} on TIC {m['neighbour_tic']} at {m['sep_arcsec']:.1f} arcsec"
                for m in self.neighbour_matches[:4]
            )
            return f"FLAG: known object within {MATCH_RADIUS_ARCSEC:g} arcsec of TIC {self.tic_id}: {hits}"
        nb = "neighbours checked" if self.neighbours_resolved else "neighbour TICs not supplied"
        return f"CLEAN: TIC {self.tic_id} absent from all sources ({nb})"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rejected"] = self.rejected
        d["flagged"] = self.flagged
        d["summary"] = self.summary()
        return d


# ── The catalog object ────────────────────────────────────────────────────────
def _unit_vectors(ra_deg: np.ndarray, dec_deg: np.ndarray) -> np.ndarray:
    ra = np.deg2rad(np.asarray(ra_deg, dtype=float))
    dec = np.deg2rad(np.asarray(dec_deg, dtype=float))
    return np.column_stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


def _chord(radius_arcsec: float) -> float:
    return 2.0 * np.sin(np.deg2rad(radius_arcsec / 3600.0) / 2.0)


def _sep_arcsec(v1: np.ndarray, v2: np.ndarray) -> np.ndarray:
    d = np.linalg.norm(v1 - v2, axis=-1)
    return np.rad2deg(2.0 * np.arcsin(np.clip(d / 2.0, 0.0, 1.0))) * 3600.0


class KnownObjectCatalog:
    """All known-object tables loaded once; vectorised TIC and coordinate matching."""

    def __init__(
        self,
        tables: dict[str, pd.DataFrame],
        versions: dict[str, CatalogVersion],
        match_radius_arcsec: float = MATCH_RADIUS_ARCSEC,
    ):
        self.tables = tables
        self.versions = versions
        self.match_radius_arcsec = float(match_radius_arcsec)
        self._tic_sets: dict[str, set[int]] = {
            n: set(int(t) for t in df["tic_id"].tolist()) for n, df in tables.items()
        }
        self._by_tic: dict[str, dict[int, list[int]]] = {}
        for n, df in tables.items():
            grp: dict[int, list[int]] = {}
            for i, t in enumerate(df["tic_id"].to_numpy()):
                grp.setdefault(int(t), []).append(i)
            self._by_tic[n] = grp
        self._all_tics: set[int] = set().union(*self._tic_sets.values()) if self._tic_sets else set()

        # coordinate index over every row with finite coordinates
        parts = []
        for n, df in tables.items():
            ok = (np.isfinite(df["ra"].to_numpy(dtype=float))
                  & np.isfinite(df["dec"].to_numpy(dtype=float)))
            if ok.any():
                sub = df.loc[ok, ["tic_id", "ra", "dec", "label", "detail"]].copy()
                sub["source"] = n
                parts.append(sub)
        if parts:
            self._coord_rows = pd.concat(parts, ignore_index=True)
            self._coord_vec = _unit_vectors(
                self._coord_rows["ra"].to_numpy(), self._coord_rows["dec"].to_numpy()
            )
            from scipy.spatial import cKDTree

            self._tree = cKDTree(self._coord_vec)
        else:
            self._coord_rows = pd.DataFrame(
                columns=["tic_id", "ra", "dec", "label", "detail", "source"]
            )
            self._coord_vec = np.zeros((0, 3))
            self._tree = None

    # ── construction ──────────────────────────────────────────────────────────
    @classmethod
    def load(
        cls,
        sources: Optional[Iterable[str]] = None,
        *,
        refresh: bool = False,
        allow_stale: bool = False,
        offline: bool = False,
        max_age_s: float = CATALOG_MAX_AGE_S,
        match_radius_arcsec: float = MATCH_RADIUS_ARCSEC,
        allow_partial_coords: bool = False,
    ) -> "KnownObjectCatalog":
        names = list(sources) if sources is not None else list(SOURCES)
        tables, versions = {}, {}
        for n in names:
            df, ver = load_source(
                n, refresh=refresh, allow_stale=allow_stale, offline=offline, max_age_s=max_age_s,
                allow_partial_coords=allow_partial_coords,
            )
            tables[n], versions[n] = df, ver
        return cls(tables, versions, match_radius_arcsec=match_radius_arcsec)

    # ── version bookkeeping ───────────────────────────────────────────────────
    def stamp(self) -> str:
        """Compact, order-stable version string for manifests and CSV columns."""
        return ";".join(self.versions[n].short() for n in sorted(self.versions))

    def manifest(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "match_radius_arcsec": self.match_radius_arcsec,
            "generated_utc": _utcnow_iso(),
            "stamp": self.stamp(),
            "sources": {n: asdict(v) for n, v in sorted(self.versions.items())},
            "n_rows": {n: int(len(df)) for n, df in sorted(self.tables.items())},
            "n_unique_tic": {n: len(s) for n, s in sorted(self._tic_sets.items())},
            "n_rows_with_coordinates": {
                n: int((np.isfinite(df["ra"].to_numpy(dtype=float)) & np.isfinite(df["dec"].to_numpy(dtype=float))).sum())
                for n, df in sorted(self.tables.items())},
            "coordinate_resolution": {n: v.coords for n, v in sorted(self.versions.items()) if v.coords},
        }

    def write_manifest(self, path: Path | str) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        m = self.manifest()
        for v in m["sources"].values():
            v.pop("files", None)      # per-file digests stay in the per-source stamps
        p.write_text(json.dumps(m, indent=1), encoding="utf-8")
        return p

    @property
    def sources(self) -> list[str]:
        return list(self.tables)

    def any_stale(self) -> bool:
        return any(v.stale for v in self.versions.values())

    def any_partial_coords(self) -> bool:
        return any(bool(v.coords and v.coords.get("partial")) for v in self.versions.values())

    def known_tics(self) -> set[int]:
        return set(self._all_tics)

    # ── matching primitives ───────────────────────────────────────────────────
    def tic_hits(self, tic_id: int) -> list[dict]:
        tic_id = int(tic_id)
        hits = []
        for n, grp in self._by_tic.items():
            for i in grp.get(tic_id, []):
                row = self.tables[n].iloc[i]
                hits.append({"source": n, "label": str(row["label"]), "detail": str(row["detail"])})
        return hits

    def coord_hits(self, ra: float, dec: float, exclude_tic: Optional[int] = None) -> list[dict]:
        """Known objects with coordinates within the match radius (any TIC but ``exclude_tic``)."""
        if self._tree is None or not (np.isfinite(ra) and np.isfinite(dec)):
            return []
        v = _unit_vectors(np.array([ra]), np.array([dec]))[0]
        idx = self._tree.query_ball_point(v, r=_chord(self.match_radius_arcsec))
        out = []
        for i in idx:
            row = self._coord_rows.iloc[i]
            if exclude_tic is not None and int(row["tic_id"]) == int(exclude_tic):
                continue
            out.append(
                {
                    "source": str(row["source"]),
                    "label": str(row["label"]),
                    "neighbour_tic": int(row["tic_id"]),
                    "sep_arcsec": float(_sep_arcsec(v, self._coord_vec[i])),
                    "via": "coordinates",
                }
            )
        out.sort(key=lambda d: d["sep_arcsec"])
        return out

    def neighbour_tic_hits(self, neighbour_tics: Iterable[tuple[int, float]]) -> list[dict]:
        """Known objects among the caller-supplied (tic_id, sep_arcsec) neighbours."""
        out = []
        for t, sep in neighbour_tics:
            t = int(t)
            if t in self._all_tics:
                for h in self.tic_hits(t):
                    out.append(
                        {
                            "source": h["source"],
                            "label": h["label"],
                            "neighbour_tic": t,
                            "sep_arcsec": float(sep),
                            "via": "neighbour_tic",
                        }
                    )
        out.sort(key=lambda d: d["sep_arcsec"])
        return out

    # ── single-target API ─────────────────────────────────────────────────────
    def check(
        self,
        tic_id: int,
        ra: Optional[float] = None,
        dec: Optional[float] = None,
        neighbour_tics: Optional[Iterable[tuple[int, float]]] = None,
        *,
        resolve_neighbours: bool = False,
    ) -> HardStopResult:
        """Hard-stop verdict for one target.

        ``neighbour_tics`` is an iterable of ``(tic_id, separation_arcsec)``
        for TIC objects within the match radius.  With
        ``resolve_neighbours=True`` and no list supplied, the neighbours (and
        the target's coordinates, if missing) are fetched from the TIC with
        one cone query; a failure there raises :class:`CatalogFetchError`.
        """
        tic_id = int(tic_id)
        resolved = neighbour_tics is not None
        if resolve_neighbours and neighbour_tics is None:
            ra, dec, neighbour_tics = _resolve_tic_neighbours(
                tic_id, ra, dec, self.match_radius_arcsec
            )
            resolved = True

        tic_m = self.tic_hits(tic_id)
        nb: list[dict] = []
        if ra is not None and dec is not None:
            nb.extend(self.coord_hits(float(ra), float(dec), exclude_tic=tic_id))
        if neighbour_tics is not None:
            nb.extend(self.neighbour_tic_hits(
                (t, s) for t, s in neighbour_tics if int(t) != tic_id
            ))
        seen, uniq = set(), []
        for h in nb:
            key = (h["source"], h["label"], h["neighbour_tic"])
            if key not in seen:
                seen.add(key)
                uniq.append(h)
        uniq.sort(key=lambda d: d["sep_arcsec"])
        status = STATUS_REJECT if tic_m else (STATUS_FLAG if uniq else STATUS_CLEAN)
        return HardStopResult(
            tic_id=tic_id,
            status=status,
            tic_matches=tic_m,
            neighbour_matches=uniq,
            catalog_stamp=self.stamp(),
            neighbours_resolved=resolved,
        )

    # ── batch API (the survey builder) ────────────────────────────────────────
    def check_many(
        self,
        targets: pd.DataFrame,
        neighbours: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Vectorised hard stop for a table of targets.

        ``targets`` needs ``tic_id``, ``ra``, ``dec``.  ``neighbours`` (optional)
        is a table of every TIC object in the same sky region with the same
        three columns; a target is flagged when any neighbour within the match
        radius (other than itself) is a known object by TIC ID.

        Returns a frame aligned with ``targets`` carrying ``xmatch_status``,
        ``xmatch_tic_sources``, ``xmatch_tic_labels``,
        ``xmatch_neighbour_sources``, ``xmatch_neighbour_tics``,
        ``xmatch_nearest_known_sep_arcsec`` and ``catalog_versions``.
        """
        n = len(targets)
        tic = pd.to_numeric(targets["tic_id"]).to_numpy().astype("int64")
        ra = pd.to_numeric(targets["ra"], errors="coerce").to_numpy(dtype=float)
        dec = pd.to_numeric(targets["dec"], errors="coerce").to_numpy(dtype=float)

        tic_src: list[list[str]] = [[] for _ in range(n)]
        tic_lab: list[list[str]] = [[] for _ in range(n)]
        for name, grp in self._by_tic.items():
            tbl_labels = self.tables[name]["label"].to_numpy()
            for i, t in enumerate(tic):
                rows = grp.get(int(t))
                if rows:
                    tic_src[i].append(name)
                    tic_lab[i].append(str(tbl_labels[rows[0]]))

        nb_src: list[list[str]] = [[] for _ in range(n)]
        nb_tics: list[list[int]] = [[] for _ in range(n)]
        nearest = np.full(n, np.nan)

        ok = np.isfinite(ra) & np.isfinite(dec)
        if self._tree is not None and ok.any():
            v = _unit_vectors(ra[ok], dec[ok])
            lists = self._tree.query_ball_point(v, r=_chord(self.match_radius_arcsec))
            ok_idx = np.flatnonzero(ok)
            c_tic = self._coord_rows["tic_id"].to_numpy()
            c_src = self._coord_rows["source"].to_numpy()
            for k, idx in enumerate(lists):
                i = ok_idx[k]
                for j in idx:
                    if int(c_tic[j]) == int(tic[i]):
                        continue
                    sep = float(_sep_arcsec(v[k], self._coord_vec[j]))
                    nb_src[i].append(str(c_src[j]))
                    nb_tics[i].append(int(c_tic[j]))
                    nearest[i] = np.nanmin([nearest[i], sep])

        if neighbours is not None and len(neighbours) and ok.any():
            from scipy.spatial import cKDTree

            nt = pd.to_numeric(neighbours["tic_id"]).to_numpy().astype("int64")
            nra = pd.to_numeric(neighbours["ra"], errors="coerce").to_numpy(dtype=float)
            ndec = pd.to_numeric(neighbours["dec"], errors="coerce").to_numpy(dtype=float)
            nok = np.isfinite(nra) & np.isfinite(ndec)
            nv = _unit_vectors(nra[nok], ndec[nok])
            nt = nt[nok]
            if len(nt):
                ntree = cKDTree(nv)
                v = _unit_vectors(ra[ok], dec[ok])
                lists = ntree.query_ball_point(v, r=_chord(self.match_radius_arcsec))
                ok_idx = np.flatnonzero(ok)
                for k, idx in enumerate(lists):
                    i = ok_idx[k]
                    for j in idx:
                        t = int(nt[j])
                        if t == int(tic[i]) or t not in self._all_tics:
                            continue
                        sep = float(_sep_arcsec(v[k], nv[j]))
                        for name, s in self._tic_sets.items():
                            if t in s:
                                nb_src[i].append(name)
                                nb_tics[i].append(t)
                        nearest[i] = np.nanmin([nearest[i], sep])

        has_tic = np.array([bool(s) for s in tic_src], dtype=bool)
        has_nb = np.array([bool(s) for s in nb_src], dtype=bool)
        status = np.where(has_tic, STATUS_REJECT, np.where(has_nb, STATUS_FLAG, STATUS_CLEAN))
        return pd.DataFrame(
            {
                "xmatch_status": status,
                "xmatch_tic_sources": ["|".join(sorted(set(s))) for s in tic_src],
                "xmatch_tic_labels": ["|".join(s) for s in tic_lab],
                "xmatch_neighbour_sources": ["|".join(sorted(set(s))) for s in nb_src],
                "xmatch_neighbour_tics": ["|".join(str(t) for t in sorted(set(s))) for s in nb_tics],
                "xmatch_nearest_known_sep_arcsec": nearest,
                "catalog_versions": self.stamp(),
            },
            index=targets.index,
        )


def _resolve_tic_neighbours(
    tic_id: int, ra: Optional[float], dec: Optional[float], radius_arcsec: float
) -> tuple[float, float, list[tuple[int, float]]]:
    """One TIC cone query: the target's own coordinates plus every TIC object within radius."""
    try:
        import astropy.units as u
        from astropy.coordinates import SkyCoord
        from astroquery.mast import Catalogs

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if ra is None or dec is None:
                own = Catalogs.query_criteria(catalog="Tic", ID=int(tic_id))
                if own is None or len(own) == 0:
                    raise CatalogFetchError(f"TIC {tic_id} not found in the TIC")
                ra, dec = float(own[0]["ra"]), float(own[0]["dec"])
            c = SkyCoord(ra=ra, dec=dec, unit="deg")
            tab = Catalogs.query_region(c, radius=radius_arcsec * u.arcsec, catalog="Tic")
    except CatalogFetchError:
        raise
    except Exception as exc:
        raise CatalogFetchError(f"TIC neighbour lookup failed for TIC {tic_id}: {exc}") from exc
    out: list[tuple[int, float]] = []
    if tab is not None and len(tab):
        v0 = _unit_vectors(np.array([ra]), np.array([dec]))[0]
        for row in tab:
            try:
                t = int(row["ID"])
                v1 = _unit_vectors(np.array([float(row["ra"])]), np.array([float(row["dec"])]))[0]
            except Exception:
                continue
            out.append((t, float(_sep_arcsec(v0, v1))))
    return float(ra), float(dec), out


# ── Module-level singleton for the single-target path ─────────────────────────
_CATALOG: Optional[KnownObjectCatalog] = None


def get_catalog(**kw) -> KnownObjectCatalog:
    """Process-wide catalog, loaded on first use (kwargs go to :meth:`KnownObjectCatalog.load`)."""
    global _CATALOG
    if _CATALOG is None or kw.get("refresh"):
        _CATALOG = KnownObjectCatalog.load(**kw)
    return _CATALOG


def reset_catalog() -> None:
    global _CATALOG
    _CATALOG = None


def hard_stop(
    tic_id: int,
    ra: Optional[float] = None,
    dec: Optional[float] = None,
    *,
    resolve_neighbours: bool = True,
    catalog: Optional[KnownObjectCatalog] = None,
) -> HardStopResult:
    """Hard-stop verdict for one TIC ID using the process-wide catalog."""
    cat = catalog or get_catalog()
    return cat.check(tic_id, ra, dec, resolve_neighbours=resolve_neighbours)


# ── TIC metadata (unchanged behaviour: informational, non-fatal) ──────────────
def query_toi_catalog(tic_id: int) -> dict | None:
    """Query the TIC for a target's stellar parameters.

    Historical name kept for the notebooks.  Returns a dict of TIC metadata, or
    None if not found or on error: this is metadata, not the hard stop.
    """
    try:
        from astroquery.mast import Catalogs

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = Catalogs.query_criteria(catalog="Tic", ID=int(tic_id))

        if result is None or len(result) == 0:
            return None

        row = result[0]

        def _float(col):
            if col not in result.colnames:
                return None
            try:
                v = float(row[col])
                return v if np.isfinite(v) else None
            except (TypeError, ValueError):
                return None

        rot_per = None
        for _pcol in ("Prot", "prot", "ProtCand"):
            rot_per = _float(_pcol)
            if rot_per is not None:
                break

        return {
            "tic_id": tic_id,
            "ra": _float("ra"),
            "dec": _float("dec"),
            "tmag": _float("Tmag"),
            "stellar_radius_rsun": _float("rad"),
            "stellar_mass_msun": _float("mass"),
            "stellar_teff_k": _float("Teff"),
            "stellar_rotation_period_days": rot_per,
            "contamination_ratio": _float("contratio"),
        }

    except Exception as exc:
        logger.warning("TIC catalog query failed for TIC %d: %s", tic_id, exc)
        return None


# ── Legacy per-source lookups (now served from the cached catalogs) ───────────
def query_exofop_toi(tic_id: int) -> pd.DataFrame | None:
    """TOI rows for ``tic_id`` or None for a genuine no-match.  Raises CatalogFetchError."""
    df, _ = load_source("toi")
    m = df[df["tic_id"] == int(tic_id)]
    return m.reset_index(drop=True) if not m.empty else None


def query_confirmed_planet_archive(tic_id: int) -> pd.DataFrame | None:
    """Archive rows (ps + pscomppars) for ``tic_id`` or None.  Raises CatalogFetchError."""
    frames = []
    for n in ("nasa_ps", "nasa_pscomppars"):
        df, _ = load_source(n)
        frames.append(df[df["tic_id"] == int(tic_id)])
    m = pd.concat(frames, ignore_index=True)
    return m if not m.empty else None


def crossmatch(tic_id: int, *, resolve_neighbours: bool = True) -> dict:
    """Run the hard stop and return the pipeline-facing summary dict.

    Raises :class:`CatalogFetchError` if any catalog (or the TIC neighbour
    lookup) is unavailable.  The historical keys are preserved:

    - ``tic_metadata``: stellar parameters from the TIC (or None)
    - ``toi_entries``: DataFrame of TOI rows (or None)
    - ``confirmed_planets``: DataFrame of archive rows (or None)
    - ``is_known_toi`` / ``is_confirmed_planet``: bools
    - ``any_query_failed``: always False here (failures raise instead)
    - ``summary_str``: human-readable summary

    New keys: ``hard_stop`` (:class:`HardStopResult` as dict), ``status``
    (REJECT / FLAG / CLEAN), ``rejected``, ``flagged``, ``catalog_versions``.
    """
    tic_id = int(tic_id)
    logger.info("Running hard-stop cross-match for TIC %d", tic_id)
    cat = get_catalog()
    tic_meta = query_toi_catalog(tic_id)
    ra = tic_meta.get("ra") if tic_meta else None
    dec = tic_meta.get("dec") if tic_meta else None
    res = cat.check(tic_id, ra, dec, resolve_neighbours=resolve_neighbours)

    toi_df = (cat.tables["toi"][cat.tables["toi"]["tic_id"] == tic_id]
              if "toi" in cat.tables else pd.DataFrame())
    conf_parts = [cat.tables[n][cat.tables[n]["tic_id"] == tic_id]
                  for n in ("nasa_ps", "nasa_pscomppars") if n in cat.tables]
    conf_df = pd.concat(conf_parts, ignore_index=True) if conf_parts else pd.DataFrame()
    is_toi = not toi_df.empty
    is_conf = not conf_df.empty

    summary = res.summary()
    if tic_meta is not None and tic_meta.get("stellar_radius_rsun"):
        summary += (
            f" | R_star = {tic_meta['stellar_radius_rsun']:.2f} R_Sun"
            f" | T_mag = {tic_meta.get('tmag', 'N/A')}"
        )
    logger.info("Cross-match result: %s", summary)

    return {
        "tic_metadata": tic_meta,
        "toi_entries": toi_df.reset_index(drop=True) if is_toi else None,
        "confirmed_planets": conf_df if is_conf else None,
        "is_known_toi": bool(is_toi),
        "is_confirmed_planet": bool(is_conf),
        "any_query_failed": False,
        "summary_str": summary,
        "hard_stop": res.to_dict(),
        "status": res.status,
        "rejected": res.rejected,
        "flagged": res.flagged,
        "catalog_versions": cat.stamp(),
    }
