"""Output manifest: every FU3 deliverable file with size and SHA-256 (manifests/output_manifest.csv)."""
import csv

from fu3_common import *


def main():
    rows = []
    for sub in ("PROTOCOL.md", "code", "results", "tables", "figures", "manifests", "report"):
        p = ROOT / sub
        files = [p] if p.is_file() else sorted(q for q in p.rglob("*") if q.is_file() and "__pycache__" not in q.parts)
        for f in files:
            if f.name == "output_manifest.csv":
                continue
            rows.append(dict(path=str(f.relative_to(ROOT)), bytes=f.stat().st_size, sha256=sha256(f)))
    with open(MAN / "output_manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["path", "bytes", "sha256"])
        w.writeheader()
        w.writerows(rows)
    log("manifest", f"{len(rows)} files, {sum(r['bytes'] for r in rows) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
