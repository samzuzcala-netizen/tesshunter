"""FU3 public-archive census: shared paths, targets and the HTTP receipt hook.

Every HTTP request made through the `requests` library (directly, or by astroquery / pyasassn, which use
`requests` internally) passes through `requests.adapters.HTTPAdapter.send`.  That method is wrapped here so
that each hop (including redirect hops) writes one receipt JSON into results/census/receipts with: method,
url, parsed params / request body, UTC start time, HTTP status (or the exception), response byte count,
sha256 of the response body, selected response headers, and the local raw-file path when the body is saved.
Bodies up to MAX_RAW_BYTES are saved under D:\\tess_fu3_cache\\census_raw.

Only stdlib + requests are imported at module level so that the separate ASAS-SN venv can import it too.
"""
from __future__ import annotations

import os

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("XDG_CACHE_HOME", r"D:\tess_fu3_cache\xdg")
os.environ.setdefault("ASTROPY_CACHE_DIR", r"D:\tess_fu3_cache\astropy")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import contextlib
import hashlib
import itertools
import json
import math
import re
import socket
import sys
import threading
import time
import urllib.parse
from pathlib import Path

import requests
import requests.adapters

# ----------------------------------------------------------------------------------------------------
ROOT = Path(r"C:\Users\seanj\Documents\TESS_followup_262_193_270")
CODE = ROOT / "code" / "census"
OUT = ROOT / "results" / "census"
RECEIPTS = OUT / "receipts"
PARTS = OUT / "parts"
TABLES = OUT / "tables"
RAW = Path(r"D:\tess_fu3_cache\census_raw")
for _p in (OUT, RECEIPTS, PARTS, TABLES, RAW,
           Path(r"D:\tess_fu3_cache\xdg\astropy"), Path(r"D:\tess_fu3_cache\xdg\astroquery"),
           Path(r"D:\tess_fu3_cache\astropy")):
    _p.mkdir(parents=True, exist_ok=True)

_ALLOWED_WRITE_ROOTS = (OUT.resolve(), RAW.resolve(), Path(r"D:\tess_fu3_cache").resolve())
_FORBIDDEN = (Path(r"D:\tesshunter_s1"), Path(r"C:\Users\seanj\Downloads"),
              Path(r"C:\Users\seanj\Documents\Codex"))

MAX_RAW_BYTES = 30 * 1024 * 1024        # bodies larger than this are hashed but not saved
DEFAULT_TIMEOUT = (30, 120)             # (connect, read) seconds for every request
socket.setdefaulttimeout(120)           # also covers http.client users

BTJD0 = 2457000.0
MJD_TO_BTJD = 2400000.5 - 2457000.0     # BTJD = MJD + this

# ---- targets (TIC v8 J2000 positions at epoch 2000.0; pm in mas/yr, pmra = mu_alpha* cos(dec)) ----
TARGETS = {
    270573718: dict(gaia=4792202879700135040, ra=86.722905, dec=-52.816629, pmra=30.39, pmdec=100.86,
                    tmag=12.65, P=41.383701, T0=1334.903753, T14_h=3.76,
                    used={"TESS-SPOC": [1, 4, 5, 6, 7, 11, 27, 28, 31, 32, 33, 34, 37, 61, 64, 65, 67, 68],
                          "QLP": [87, 88, 94, 95, 98]},
                    used_cadence_s={1: 1800, 4: 1800, 5: 1800, 6: 1800, 7: 1800, 11: 1800,
                                     27: 600, 28: 600, 31: 600, 32: 600, 33: 600, 34: 600, 37: 600,
                                     61: 200, 64: 200, 65: 200, 67: 200, 68: 200,
                                     87: 200, 88: 200, 94: 200, 95: 200, 98: 200}),
    262843927: dict(gaia=4673750877131752832, ra=52.573211, dec=-63.501800, pmra=66.04, pmdec=55.44,
                    tmag=11.98, P=24.108929, T0=1332.787714, T14_h=3.71,
                    used={"TESS-SPOC": [1, 2, 3, 4, 28, 29, 30, 34, 61, 64, 68, 69],
                          "QLP": [95, 96, 97]},
                    used_cadence_s={1: 1800, 2: 1800, 3: 1800, 4: 1800, 28: 600, 29: 600, 30: 600, 34: 600,
                                    61: 200, 64: 200, 68: 200, 69: 200, 95: 200, 96: 200, 97: 200},
                    note="SPOC 2-min and TASOC 2-min exist for S1-S3 but were not used by discovery"),
    193718989: dict(gaia=1346023547769345792, ra=267.554464, dec=42.109629, pmra=-24.14, pmdec=-44.12,
                    tmag=12.22, P=24.532886, T0=2000.075484, T14_h=3.35,
                    used={"TESS-SPOC": [25, 26, 40, 52, 53, 79, 80]},
                    used_cadence_s={25: 1800, 26: 1800, 40: 600, 52: 600, 53: 600, 79: 200, 80: 200}),
}
TICS = tuple(TARGETS)
DISCOVERY_MAX_SECTOR = 98


def used_sectors(tic: int) -> list[int]:
    s = set()
    for v in TARGETS[tic]["used"].values():
        s.update(v)
    return sorted(s)


def pos_at_epoch(tic: int, epoch_yr: float, base_epoch: float = 2000.0, base=None):
    """Linear proper-motion propagation (sub-mas accurate over decades at these pm).  base=(ra,dec)."""
    t = TARGETS[tic]
    ra0, dec0 = base if base is not None else (t["ra"], t["dec"])
    dt = epoch_yr - base_epoch
    ddec = t["pmdec"] * dt / 3.6e6
    dra = t["pmra"] * dt / 3.6e6 / math.cos(math.radians(dec0))
    return ra0 + dra, dec0 + ddec


def sep_arcsec(ra1, dec1, ra2, dec2) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    s = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((r2 - r1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(s)))) * 3600.0


# ---- small utilities ----------------------------------------------------------------------------------
def utc(ms: bool = False) -> str:
    t = time.time()
    s = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t))
    return s + (f".{int((t % 1) * 1000):03d}Z" if ms else "Z")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_write(path: Path) -> None:
    p = Path(path).resolve()
    for bad in _FORBIDDEN:
        try:
            p.relative_to(bad.resolve())
            raise PermissionError(f"refusing to write into forbidden root {bad}: {p}")
        except ValueError:
            pass
    if not any(_is_within(p, r) for r in _ALLOWED_WRITE_ROOTS):
        raise PermissionError(f"refusing to write outside the census output roots: {p}")


def _is_within(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def clean(o):
    """JSON-safe conversion (numpy scalars/arrays, NaN -> None, Paths -> str, masked -> None)."""
    try:
        import numpy as np  # optional
    except Exception:  # pragma: no cover
        np = None
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [clean(x) for x in o]
    if np is not None:
        if isinstance(o, np.ndarray):
            return clean(o.tolist())
        if isinstance(o, np.generic):
            return clean(o.item())
        try:
            if o is np.ma.masked:
                return None
        except Exception:
            pass
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, bytes):
        return o.decode("utf-8", "replace")
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def save_json(path, obj) -> Path:
    path = Path(path)
    _check_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(clean(obj), indent=1, allow_nan=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def save_text(path, text: str) -> Path:
    path = Path(path)
    _check_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def safe_name(s: str, n: int = 80) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)[:n].strip("_") or "x"


def log(script: str, msg: str) -> None:
    line = f"{utc()} [{script}] {msg}"
    print(line, flush=True)
    p = OUT / "census_log.txt"
    with open(p, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---- receipt hook --------------------------------------------------------------------------------------
_ctx = threading.local()
_counter = itertools.count(1)
_lock = threading.Lock()
SCRIPT = Path(sys.argv[0]).stem if sys.argv and sys.argv[0] else "interactive"
_RUN_STAMP = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
_EXT = (("json", ".json"), ("csv", ".csv"), ("comma-separated", ".csv"), ("votable", ".xml"),
        ("x-votable", ".xml"), ("xml", ".xml"), ("html", ".html"), ("zip", ".zip"), ("fits", ".fits"),
        ("plain", ".txt"), ("text", ".txt"), ("octet-stream", ".bin"), ("arrow", ".arrow"),
        ("parquet", ".parquet"), ("pdf", ".pdf"))


def _guess_ext(ctype: str, url: str) -> str:
    c = (ctype or "").lower()
    for key, ext in _EXT:
        if key in c:
            return ext
    tail = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
    if "." in tail:
        return "." + tail.rsplit(".", 1)[-1][:8]
    return ".bin"


def _body_repr(body):
    if body is None:
        return None, None, 0
    if isinstance(body, str):
        b = body.encode("utf-8", "replace")
    elif isinstance(body, (bytes, bytearray)):
        b = bytes(body)
    else:
        return f"<non-bytes body {type(body).__name__}>", None, None
    text = b.decode("utf-8", "replace")
    parsed = None
    try:
        q = urllib.parse.parse_qs(text, keep_blank_values=True)
        if q and all(isinstance(v, list) for v in q.values()):
            parsed = {k: (v[0] if len(v) == 1 else v) for k, v in q.items()}
            # MAST portal requests carry a JSON document in 'request'
            if isinstance(parsed.get("request"), str):
                try:
                    parsed["request"] = json.loads(parsed["request"])
                except Exception:
                    pass
    except Exception:
        parsed = None
    return (text if len(text) <= 20000 else text[:20000] + "...<truncated>"), parsed, len(b)


def current_tag() -> str:
    return getattr(_ctx, "label", None) or "untagged"


@contextlib.contextmanager
def tag(label: str, save_raw: bool = True, max_raw: int | None = None):
    """Label every request made inside the block; yields a list that collects the receipts written.
    max_raw (bytes) lowers the raw-save size limit for this block ("small files only")."""
    prev = (getattr(_ctx, "label", None), getattr(_ctx, "save_raw", True), getattr(_ctx, "collected", None),
            getattr(_ctx, "max_raw", None))
    _ctx.label, _ctx.save_raw, _ctx.collected, _ctx.max_raw = label, save_raw, [], max_raw
    try:
        yield _ctx.collected
    finally:
        col = _ctx.collected
        _ctx.label, _ctx.save_raw, _ctx.collected, _ctx.max_raw = prev
        if prev[2] is not None:          # nested: propagate receipts outward
            prev[2].extend(col)


_orig_adapter_send = requests.adapters.HTTPAdapter.send


def _hooked_send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    label = current_tag()
    save_raw = getattr(_ctx, "save_raw", True)
    with _lock:
        n = next(_counter)
    stem = f"{_RUN_STAMP}_{os.getpid()}_{n:04d}_{safe_name(label, 60)}"
    parsed_url = urllib.parse.urlparse(request.url)
    params = {k: (v[0] if len(v) == 1 else v)
              for k, v in urllib.parse.parse_qs(parsed_url.query, keep_blank_values=True).items()}
    body_text, body_parsed, body_len = _body_repr(request.body)
    rec = {"receipt_id": stem, "script": SCRIPT, "label": label, "utc_start": utc(ms=True),
           "method": request.method, "url": request.url, "params": params,
           "request_body_params": body_parsed, "request_body_text": None if body_parsed else body_text,
           "request_body_bytes": body_len, "timeout_s": list(timeout) if isinstance(timeout, tuple) else timeout}
    t0 = time.time()
    try:
        resp = _orig_adapter_send(self, request, stream=stream, timeout=timeout, verify=verify, cert=cert,
                                  proxies=proxies)
    except Exception as e:  # noqa: BLE001
        rec.update({"http_status": None, "exception": f"{type(e).__name__}: {e}"[:2000],
                    "elapsed_s": round(time.time() - t0, 3), "response_bytes": None, "response_sha256": None,
                    "raw_file": None})
        _write_receipt(stem, rec)
        raise
    try:
        content = resp.content          # reading caches the body; later readers reuse it
    except Exception as e:  # noqa: BLE001
        rec.update({"http_status": resp.status_code, "exception": f"body read failed: {type(e).__name__}: {e}",
                    "elapsed_s": round(time.time() - t0, 3), "response_bytes": None, "response_sha256": None,
                    "raw_file": None})
        _write_receipt(stem, rec)
        raise
    h = {k: resp.headers.get(k) for k in ("Content-Type", "Content-Length", "Last-Modified", "ETag", "Date",
                                          "Location", "Content-Disposition", "Server") if resp.headers.get(k)}
    raw_path = None
    limit = min(MAX_RAW_BYTES, getattr(_ctx, "max_raw", None) or MAX_RAW_BYTES)
    if save_raw and content is not None and len(content) <= limit:
        raw_path = RAW / (stem + _guess_ext(resp.headers.get("Content-Type", ""), request.url))
        _check_write(raw_path)
        with open(raw_path, "wb") as f:
            f.write(content)
    snippet = None
    if content is not None and len(content) <= 400000:
        try:
            snippet = content[:300].decode("utf-8", "replace")
        except Exception:
            snippet = None
    rec.update({"http_status": resp.status_code, "reason": resp.reason, "exception": None,
                "elapsed_s": round(time.time() - t0, 3), "response_bytes": None if content is None else len(content),
                "response_sha256": None if content is None else sha256_bytes(content),
                "response_headers": h, "raw_file": str(raw_path) if raw_path else None,
                "raw_saved": bool(raw_path), "body_head": snippet})
    _write_receipt(stem, rec)
    return resp


def _write_receipt(stem: str, rec: dict) -> None:
    p = RECEIPTS / f"{stem}.json"
    _check_write(p)
    p.write_text(json.dumps(clean(rec), indent=1), encoding="utf-8")
    col = getattr(_ctx, "collected", None)
    if col is not None:
        col.append({"receipt": str(p), "raw": rec.get("raw_file"), "status": rec.get("http_status"),
                    "url": rec.get("url"), "bytes": rec.get("response_bytes"), "exception": rec.get("exception"),
                    "sha256": rec.get("response_sha256")})


requests.adapters.HTTPAdapter.send = _hooked_send

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "FU3-archive-census/1.0 (python-requests; metadata-only queries)"})


class Fetch:
    def __init__(self, resp, exc, receipts):
        self.resp, self.exc, self.receipts = resp, exc, receipts

    @property
    def ok(self):
        return self.resp is not None and self.resp.status_code == 200

    @property
    def status(self):
        return None if self.resp is None else self.resp.status_code

    @property
    def text(self):
        return None if self.resp is None else self.resp.content.decode("utf-8", "replace")

    @property
    def receipt_files(self):
        return [r["receipt"] for r in self.receipts]

    @property
    def raw_files(self):
        return [r["raw"] for r in self.receipts if r.get("raw")]

    def describe(self):
        if self.resp is None:
            return f"exception: {self.exc}"
        return f"HTTP {self.resp.status_code}, {len(self.resp.content)} bytes"


def fetch(url, label, params=None, method="GET", data=None, headers=None, timeout=DEFAULT_TIMEOUT,
          retries=1, save_raw=True, max_raw=None) -> Fetch:
    """One request with at most `retries` retries (on exception or HTTP 5xx).  Never more than 2."""
    retries = min(int(retries), 2)
    attempt, last_exc = 0, None
    with tag(label, save_raw=save_raw, max_raw=max_raw) as col:
        while True:
            try:
                r = SESSION.request(method, url, params=params, data=data, headers=headers, timeout=timeout)
                if r.status_code >= 500 and attempt < retries:
                    attempt += 1
                    time.sleep(5)
                    continue
                return Fetch(r, None, list(col))
            except requests.RequestException as e:
                last_exc = f"{type(e).__name__}: {e}"[:1500]
                if attempt < retries:
                    attempt += 1
                    time.sleep(5)
                    continue
                return Fetch(None, last_exc, list(col))


def looks_like_error_page(text: str | None) -> str | None:
    """Return a reason string when an HTTP-200 body is not the data product requested."""
    if text is None:
        return "no body"
    t = text.strip()
    if t == "" or t == "Array":
        return f"body is {t!r}"
    low = t[:3000].lower()
    for key in ("retire", "retirement", "<html", "<!doctype html", "error", "not found", "maintenance",
                "login", "sign in"):
        if key in low:
            return f"body contains {key!r}"
    return None


def entry(tic, archive, query_description, outcome_code, n_rows=None, key_findings="", receipts=None,
          raw_files=None, **extra) -> dict:
    allowed = {"DATA_WITH_TRANSIT_COVERAGE", "DATA_NO_TRANSIT_COVERAGE", "DATA", "NO_DATA", "NO_MATCH",
               "ACCESS_FAILED", "ACCESS_RESTRICTED", "NOT_APPLICABLE"}
    if outcome_code not in allowed:
        raise ValueError(outcome_code)
    d = {"tic": tic, "archive": archive, "query_description": query_description, "outcome_code": outcome_code,
         "n_rows": n_rows, "key_findings": key_findings, "receipt_files": list(receipts or []),
         "raw_files": [r for r in (raw_files or []) if r]}
    d.update(extra)
    return d
