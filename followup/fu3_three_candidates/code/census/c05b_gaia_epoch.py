"""Census task 7 (epoch photometry part): Gaia DR3 DataLink retrieval.

c05 used DATA_STRUCTURE=INDIVIDUAL, which the data-server now rejects with HTTP 500 ("The 'INDIVIDUAL' data
structure has been deprecated - use 'DATAMODEL_STANDARD' instead").  This script repeats the retrieval with
DATA_STRUCTURE=DATAMODEL_STANDARD, first FORMAT=csv and, only if that format is refused, FORMAT=votable.
No retries on deterministic 4xx/5xx errors.  Files are saved, not interpreted.  Gaia epoch photometry times
are in the Gaia time system: TCB-based BJD - 2455197.5 (days).
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import census_common as C
from census_common import fetch, log, save_json

SCRIPT = "c05b_gaia_epoch"
DATALINK = "https://gea.esac.esa.int/data-server/data"
EPOCH_DIR = C.OUT / "gaia_epoch_photometry"


def main():
    g = json.loads((C.PARTS / "c05_gaia.json").read_text(encoding="utf-8"))
    want = g["epoch_photometry_requested"]
    out = {"script": SCRIPT, "utc": C.utc(), "requests": []}
    for tic, sid, sep in want:
        rec = {"tic": tic, "source_id": sid, "sep_arcsec": sep, "attempts": []}
        for fmt in ("csv", "votable"):
            f = fetch(DATALINK, f"gaia_epochphot_dms_{fmt}_{sid}", retries=0, timeout=(30, 120),
                      params={"RETRIEVAL_TYPE": "EPOCH_PHOTOMETRY", "ID": str(sid), "FORMAT": fmt,
                              "RELEASE": "Gaia DR3", "DATA_STRUCTURE": "DATAMODEL_STANDARD",
                              "VALID_DATA": "false", "USE_ZIP_ALWAYS": "true"})
            att = {"format": fmt, "status": f.status, "describe": f.describe(), "receipts": f.receipt_files,
                   "raw": f.raw_files, "files": [], "error": None}
            if f.ok:
                try:
                    z = zipfile.ZipFile(io.BytesIO(f.resp.content))
                    outdir = EPOCH_DIR / f"tic{tic}_gaia{sid}"
                    outdir.mkdir(parents=True, exist_ok=True)
                    for n in z.namelist():
                        data = z.read(n)
                        p = outdir / Path(n).name
                        C._check_write(p)
                        p.write_bytes(data)
                        att["files"].append({"name": n, "saved": str(p), "bytes": len(data),
                                             "sha256": C.sha256_bytes(data),
                                             "lines": data.decode("utf-8", "replace").count("\n")})
                except zipfile.BadZipFile:
                    att["error"] = f"HTTP 200 but not a zip: {(f.text or '')[:300]!r}"
            else:
                body = (f.text or "")
                i = body.find("Message:")
                att["error"] = (body[i:i + 300] if i >= 0 else body[:300]).replace("\n", " ")
            rec["attempts"].append(att)
            log(SCRIPT, f"{sid} fmt={fmt}: {f.describe()} files={len(att['files'])} err={att['error']}")
            if f.ok and att["files"]:
                break
            if f.status not in (400, 500):    # only fall back to votable when the request itself was refused
                break
        out["requests"].append(rec)
    save_json(C.PARTS / "c05b_gaia_epoch.json", out)


if __name__ == "__main__":
    main()
