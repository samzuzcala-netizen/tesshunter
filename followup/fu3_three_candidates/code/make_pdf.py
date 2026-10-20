"""PDF copy of the report: wraps report/FU3_three_candidates.html in a full HTML skeleton (the artifact source has
none) and prints it with headless Microsoft Edge.  Output: report/FU3_three_candidates.pdf
"""
import subprocess
import tempfile

from fu3_common import *

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PRINT_CSS = """<style>@media print{
  body{padding-inline:14mm!important;padding-block:10mm!important;font-size:11pt}
  .tbl{overflow:visible!important} table{font-size:8.5pt} figure,table,tr,.vcard{break-inside:avoid}
  h2,h3{break-after:avoid} nav.toc{display:none}
}</style>"""


def main():
    src = REPORT / "FU3_three_candidates.html"
    body = src.read_text(encoding="utf-8")
    doc = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">' + PRINT_CSS + "</head><body>" + body + "</body></html>")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "fu3_print.html"
        tmp.write_text(doc, encoding="utf-8")
        out = REPORT / "FU3_three_candidates.pdf"
        args = [EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=15000",
                f"--user-data-dir={Path(td) / 'edge_profile'}", f"--print-to-pdf={out}", tmp.as_uri()]
        r = subprocess.run(args, capture_output=True, text=True, timeout=300)
        log("pdf", f"edge rc {r.returncode}; {out} {out.stat().st_size / 1e6:.2f} MB" if out.exists() else f"edge rc {r.returncode}: {r.stderr[-500:]}")


if __name__ == "__main__":
    main()
