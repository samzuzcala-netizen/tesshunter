"""Census task 12 (repository part 2): eumemic/exoplanets candidates/ephemerides.csv and
candidates/predictions.csv (named in the README section 'Predicted transit times'); keep the header and the
rows for the three TIC IDs.  Content is data only."""
from __future__ import annotations

import csv
import io
import re

import census_common as C
from census_common import TARGETS, fetch, log, save_json

SCRIPT = "c09b_github_ephem"
RAW = "https://raw.githubusercontent.com/eumemic/exoplanets/main"
OUTDIR = C.OUT / "prior_public_analysis" / "eumemic_exoplanets"


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "files": {}}
    tics = [str(t) for t in TARGETS]
    for name in ("candidates/ephemerides.csv", "candidates/predictions.csv"):
        f = fetch(f"{RAW}/{name}", f"github_raw_{C.safe_name(name, 40)}", max_raw=5 * 1024 * 1024)
        rec = {"status": f.status, "describe": f.describe(), "receipts": f.receipt_files, "raw": f.raw_files,
               "sha256": None if f.resp is None else C.sha256_bytes(f.resp.content)}
        if f.ok:
            txt = f.text
            rows = list(csv.DictReader(io.StringIO(txt)))
            rec["n_rows"] = len(rows)
            rec["columns"] = list(rows[0].keys()) if rows else None
            tk = next((k for k in (rows[0].keys() if rows else []) if k.strip().lower() in ("tic", "tic_id", "ticid")), None)
            rec["tic_column"] = tk
            hits = {t: [r for r in rows if tk and str(r.get(tk, "")).split(".")[0] == t] for t in tics}
            rec["rows_for_targets"] = hits
            rec["regex_hits"] = {t: len(re.findall(rf"(?<!\d){t}(?!\d)", txt)) for t in tics}
            keep = OUTDIR / (name.replace("/", "__") + ".target_rows.csv")
            C._check_write(keep)
            with open(keep, "w", encoding="utf-8", newline="") as fh:
                if rows:
                    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                    w.writeheader()
                    for t in tics:
                        for r in hits[t]:
                            w.writerow(r)
            rec["saved_target_rows"] = str(keep)
        res["files"][name] = rec
        log(SCRIPT, f"{name}: {f.describe()} rows={rec.get('n_rows')} hits={ {t: len(v) for t, v in rec.get('rows_for_targets', {}).items()} }")
    save_json(C.PARTS / "c09b_github_ephem.json", res)


if __name__ == "__main__":
    main()
