"""Product caveat documentation: MAST HLSP pages for QLP, TESS-SPOC and TGLC (and TARS / GSFC-ELEANOR-LITE,
whose products exist for these stars).  Pages are saved (receipts) and every sentence mentioning a caveat-like
keyword together with a sector number is extracted verbatim into parts/c11_hlsp_docs.json for manual reading.
"""
from __future__ import annotations

import html
import re

import census_common as C
from census_common import fetch, log, save_json

SCRIPT = "c11_hlsp_docs"
PAGES = {
    "QLP": "https://archive.stsci.edu/hlsp/qlp",
    "TESS-SPOC": "https://archive.stsci.edu/hlsp/tess-spoc",
    "TGLC": "https://archive.stsci.edu/hlsp/tglc",
    "TARS": "https://archive.stsci.edu/hlsp/tars",
    "GSFC-ELEANOR-LITE": "https://archive.stsci.edu/hlsp/gsfc-eleanor-lite",
}
KEY = re.compile(r"(caveat|known issue|issue|error|incorrect|wrong|timing|time stamp|timestamp|offset|redeliver|"
                 r"re-deliver|reprocess|re-process|replace|version|v0?\d\b|update|bug|problem|note)", re.I)


def page_text(t):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<(br|p|li|tr|h\d|div)[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t)


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "pages": {}}
    for name, url in PAGES.items():
        f = fetch(url, f"hlsp_page_{name}")
        rec = {"url": url, "status": f.status, "describe": f.describe(), "final_url": None if f.resp is None else f.resp.url,
               "receipts": f.receipt_files, "raw": f.raw_files, "caveat_lines": []}
        if f.ok:
            txt = page_text(f.text)
            rec["n_chars_text"] = len(txt)
            for line in txt.split("\n"):
                ln = line.strip()
                if len(ln) > 20 and KEY.search(ln) and re.search(r"[Ss]ector|\bS\d{2,3}\b|\d{2,3}", ln):
                    rec["caveat_lines"].append(ln[:1500])
            m = re.findall(r"[Ll]ast [Mm]odified[^\n]{0,60}", txt)
            rec["last_modified_text"] = m[:2]
        res["pages"][name] = rec
        log(SCRIPT, f"{name}: {f.describe()} caveat-like lines={len(rec['caveat_lines'])}")
    save_json(C.PARTS / "c11_hlsp_docs.json", res)


if __name__ == "__main__":
    main()
