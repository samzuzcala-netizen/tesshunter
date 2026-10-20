"""Census task 4: SPOC TCE statistics (MAST bulk tcestats CSVs) and SPOC TPS target lists (rms-CDPP CSVs).

Files grepped: every single-sector TCE/CDPP file for a sector in which any of the three targets is on
silicon (TESScut list from c01, plus the discovery 'used' lists), and every multi-sector TCE/CDPP file whose
sector range overlaps any of those sectors.  Matching is on the integer `ticid` column (exact), with a
regex line count as a cross-check.  Raw CSV bodies <= 10 MB are kept in census_raw; for larger files the
comment header, column header and any matching lines are kept instead (sha256 of the full body is in the
receipt).
"""
from __future__ import annotations

import csv
import io
import json
import re

import census_common as C
from census_common import TARGETS, fetch, log, save_json

SCRIPT = "c02_tce"
INDEX = "https://archive.stsci.edu/tess/bulk_downloads/bulk_downloads_tce.html"
BASE = "https://archive.stsci.edu"
MAX_RAW = 10 * 1024 * 1024


def target_sectors():
    out = {}
    for tic in TARGETS:
        s = set(C.used_sectors(tic))
        p = C.TABLES / f"mast_tess_{tic}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        for r in (d["tesscut"]["SPOC"]["rows"] or []):
            s.add(int(r["sector"]))
        out[tic] = sorted(s)
    return out


def parse_links(html_text):
    links = []
    for m in re.finditer(r"href=[\"'](/missions/tess/catalogs/(tce|cdpp)/([^\"']+?\.csv))[\"']", html_text):
        path, kind, name = m.group(1), m.group(2), m.group(3)
        mm = re.search(r"-s(\d{4})-s(\d{4})", name)
        if not mm:
            continue
        links.append({"kind": kind, "name": name, "url": BASE + path, "s_start": int(mm.group(1)),
                      "s_stop": int(mm.group(2))})
    return links


def grep_csv(text, tics):
    lines = text.splitlines()
    comments = [ln for ln in lines if ln.startswith("#")]
    body = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
    out = {"comments": [c.rstrip() for c in comments[:40]], "n_data_rows": 0, "header": None,
           "matches": {t: [] for t in tics}, "regex_line_hits": {t: 0 for t in tics}}
    if not body:
        return out
    # CDPP files carry their column list in comments; their first non-comment line may be data or header
    first = next(csv.reader([body[0]]))
    has_header = any(re.search(r"[A-Za-z]", x) for x in first)
    header = first if has_header else None
    data = body[1:] if has_header else body
    out["header"] = header
    out["n_data_rows"] = len(data)
    tic_idx = 0
    if header:
        for i, h in enumerate(header):
            if h.strip().lower() in ("ticid", "tic_id", "tic"):
                tic_idx = i
                break
    out["tic_column_index"] = tic_idx
    pats = {t: re.compile(rf"(^|,)\s*0*{t}\s*(,|$)") for t in tics}
    for ln in data:
        hit = [t for t in tics if pats[t].search(ln)]
        if not hit:
            continue
        for t in hit:
            out["regex_line_hits"][t] += 1
        row = next(csv.reader([ln]))
        try:
            tid = int(float(row[tic_idx]))
        except Exception:
            tid = None
        if tid in tics:
            out["matches"][tid].append(dict(zip(header, row)) if header else row)
    return out


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "index": None, "files": [], "per_target": {}}
    fi = fetch(INDEX, "tce_index")
    res["index"] = {"status": fi.status, "describe": fi.describe(), "receipts": fi.receipt_files,
                    "raw": fi.raw_files, "last_modified_text": None}
    if not fi.ok:
        log(SCRIPT, f"index failed: {fi.describe()} {fi.exc}")
        save_json(C.PARTS / "c02_tce.json", res)
        return
    txt = fi.text
    m = re.search(r"Last Modified:\s*([^<\n]+)", txt)
    res["index"]["last_modified_text"] = m.group(1).strip() if m else None
    links = parse_links(txt)
    res["index"]["n_links"] = {"tce": sum(1 for l in links if l["kind"] == "tce"),
                               "cdpp": sum(1 for l in links if l["kind"] == "cdpp")}
    sec = target_sectors()
    res["target_sectors_considered"] = sec
    allsec = set().union(*sec.values())
    tics = list(TARGETS)
    needed = []
    for l in links:
        if l["s_start"] == l["s_stop"]:
            if l["s_start"] in allsec:
                needed.append(l)
        else:
            if any(l["s_start"] <= s <= l["s_stop"] for s in allsec):
                needed.append(l)
    needed.sort(key=lambda l: (l["kind"] != "tce", l["s_start"], l["s_stop"]))
    log(SCRIPT, f"{len(links)} links; {len(needed)} files needed "
                f"({sum(1 for l in needed if l['kind'] == 'tce')} tce, {sum(1 for l in needed if l['kind'] == 'cdpp')} cdpp)")
    for i, l in enumerate(needed):
        f = fetch(l["url"], f"{l['kind']}_s{l['s_start']:03d}-s{l['s_stop']:03d}", max_raw=MAX_RAW)
        rec = dict(l)
        rec.update({"status": f.status, "describe": f.describe(), "exception": f.exc, "receipts": f.receipt_files,
                    "raw": f.raw_files})
        if f.ok:
            g = grep_csv(f.text, tics)
            rec.update({k: g[k] for k in ("comments", "n_data_rows", "header", "regex_line_hits",
                                          "tic_column_index")})
            rec["matches"] = {str(t): g["matches"][t] for t in tics}
            rec["header"] = (g["header"][:12] + ["..."]) if g["header"] and len(g["header"]) > 12 else g["header"]
            if not f.raw_files:      # too large to keep: keep header + matching lines only
                keep = "\n".join(g["comments"]) + "\n" + ",".join(g["header"] or []) + "\n"
                for t in tics:
                    for row in g["matches"][t]:
                        keep += json.dumps(row) + "\n"
                p = C.RAW / f"{C._RUN_STAMP}_derived_{l['name']}.header_and_matches.txt"
                C._check_write(p)
                p.write_text(keep, encoding="utf-8")
                rec["derived_raw"] = str(p)
            nm = {t: len(g["matches"][t]) for t in tics}
            if any(nm.values()):
                log(SCRIPT, f"MATCH in {l['name']}: {nm}")
        res["files"].append(rec)
        if i % 10 == 0:
            log(SCRIPT, f"{i + 1}/{len(needed)} {l['name']} {f.describe()}")
    for t in tics:
        tce_files = [r for r in res["files"] if r["kind"] == "tce"]
        cdpp_files = [r for r in res["files"] if r["kind"] == "cdpp"]
        res["per_target"][t] = {
            "n_tce_files_ok": sum(1 for r in tce_files if r["status"] == 200),
            "n_tce_files_failed": sum(1 for r in tce_files if r["status"] != 200),
            "tce_matches": [{"file": r["name"], "rows": r["matches"][str(t)]} for r in tce_files
                            if r.get("matches") and r["matches"][str(t)]],
            "n_cdpp_files_ok": sum(1 for r in cdpp_files if r["status"] == 200),
            "n_cdpp_files_failed": sum(1 for r in cdpp_files if r["status"] != 200),
            "cdpp_present_in": [r["name"] for r in cdpp_files if r.get("matches") and r["matches"][str(t)]],
            "cdpp_rows": [{"file": r["name"], "rows": r["matches"][str(t)]} for r in cdpp_files
                          if r.get("matches") and r["matches"][str(t)]],
            "failed_files": [r["name"] for r in res["files"] if r["status"] != 200],
        }
        log(SCRIPT, f"TIC {t}: tce matches={len(res['per_target'][t]['tce_matches'])} "
                    f"cdpp present in={res['per_target'][t]['cdpp_present_in']}")
    save_json(C.PARTS / "c02_tce.json", res)


if __name__ == "__main__":
    main()
