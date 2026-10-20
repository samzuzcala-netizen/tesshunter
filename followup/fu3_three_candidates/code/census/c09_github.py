"""Census task 12 (repository part): prior public analysis in github.com/eumemic/exoplanets.

Unauthenticated GitHub REST API (repo metadata, recursive tree of the default branch, commit history of the
matching paths) and raw.githubusercontent.com for the matching files.  All content is treated as data
(parsed, never executed).  Files fetched: every path containing one of the three TIC IDs, the README, and
any top-level candidate / summary table (csv/json/md) <= 2 MB, which is then grepped for the TIC IDs.
Budget: well under the 60 requests/hour unauthenticated limit.
"""
from __future__ import annotations

import json
import re

import census_common as C
from census_common import TARGETS, fetch, log, save_json

SCRIPT = "c09_github"
API = "https://api.github.com/repos/eumemic/exoplanets"
RAW = "https://raw.githubusercontent.com/eumemic/exoplanets"
OUTDIR = C.OUT / "prior_public_analysis" / "eumemic_exoplanets"


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    res = {"script": SCRIPT, "utc": C.utc(), "repo": None, "tree": None, "files": [], "commits": {}, "grep": {}}
    f = fetch(API, "github_repo_meta")
    meta = json.loads(f.text) if f.ok else {}
    branch = meta.get("default_branch", "main")
    res["repo"] = {"status": f.status, "receipts": f.receipt_files, "raw": f.raw_files,
                   **{k: meta.get(k) for k in ("full_name", "description", "default_branch", "created_at",
                                                "updated_at", "pushed_at", "license", "size", "html_url")}}
    ft = fetch(f"{API}/git/trees/{branch}", "github_tree", params={"recursive": "1"})
    tree = json.loads(ft.text) if ft.ok else {}
    paths = [(e["path"], e.get("size")) for e in tree.get("tree", []) if e.get("type") == "blob"]
    res["tree"] = {"status": ft.status, "receipts": ft.receipt_files, "raw": ft.raw_files, "truncated": tree.get("truncated"),
                   "n_files": len(paths), "sha": tree.get("sha")}
    log(SCRIPT, f"repo {meta.get('full_name')} branch={branch} files={len(paths)} truncated={tree.get('truncated')}")
    tics = [str(t) for t in TARGETS]
    want = [p for p, s in paths if any(t in p for t in tics)]
    tops = [p for p, s in paths if p.count("/") == 0 and re.search(r"\.(md|csv|json|tsv|txt)$", p, re.I)
            and (s or 0) <= 2_000_000]
    tables = [p for p, s in paths if re.search(r"(candidate|summary|results|vetted|catalog|predict)[^/]*\.(csv|json|tsv|md)$",
                                              p, re.I) and (s or 0) <= 2_000_000 and p not in want and p not in tops]
    res["paths_with_tic"] = want
    res["top_level_docs"] = tops
    res["candidate_tables"] = tables[:12]
    fetch_list = want[:25] + tops[:6] + tables[:12]
    for p in fetch_list:
        fr = fetch(f"{RAW}/{branch}/{p}", f"github_raw_{C.safe_name(p, 50)}")
        rec = {"path": p, "status": fr.status, "bytes": None if fr.resp is None else len(fr.resp.content),
               "sha256": None if fr.resp is None else C.sha256_bytes(fr.resp.content), "receipts": fr.receipt_files,
               "raw": fr.raw_files}
        if fr.ok:
            outp = OUTDIR / p.replace("/", "__")
            C._check_write(outp)
            outp.write_bytes(fr.resp.content)
            rec["saved"] = str(outp)
            txt = fr.text
            rec["tic_hits"] = {t: len(re.findall(rf"(?<!\d){t}(?!\d)", txt)) for t in tics}
        res["files"].append(rec)
        log(SCRIPT, f"raw {p}: {fr.describe()} hits={rec.get('tic_hits')}")
    for p in want[:6]:
        fc = fetch(f"{API}/commits", f"github_commits_{C.safe_name(p, 40)}", params={"path": p, "per_page": "5"})
        try:
            cm = json.loads(fc.text) if fc.ok else []
            res["commits"][p] = [{"sha": c.get("sha"), "date": c.get("commit", {}).get("committer", {}).get("date"),
                                  "message": (c.get("commit", {}).get("message") or "")[:200]} for c in cm]
        except Exception as e:  # noqa: BLE001
            res["commits"][p] = f"parse error {e}"
    save_json(C.PARTS / "c09_github.json", res)


if __name__ == "__main__":
    main()
