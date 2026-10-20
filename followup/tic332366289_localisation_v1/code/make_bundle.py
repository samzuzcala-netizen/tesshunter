"""Build review_bundle.zip (report, configuration, code/tests, compact results,
figures, input provenance, logs) with a sha256 manifest. Excludes raw cubes,
environments and the D: array cache."""
from __future__ import annotations

import hashlib
import zipfile

import common as C

INCLUDE_DIRS = ["code", "tests", "inputs", "results", "figures", "logs"]
TOP = ["LOCALISATION_REPORT.md", "PLAN.md", "config.json", "events.csv", "neighbours.csv"]
EXCLUDE_SUFFIX = (".tmp", ".pyc")
MAX_BYTES = 5_000_000  # no single file above 5 MB (the largest result file is ~4 MB of JSON lines)


def main():
    files = [C.WS / f for f in TOP]
    for d in INCLUDE_DIRS:
        files += sorted(p for p in (C.WS / d).rglob("*") if p.is_file() and not p.name.endswith(EXCLUDE_SUFFIX)
                        and "__pycache__" not in p.parts)
    big = [p for p in files if p.stat().st_size > MAX_BYTES]
    assert not big, big
    lines = []
    out = C.WS / "review_bundle.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            rel = p.relative_to(C.WS).as_posix()
            b = p.read_bytes()
            z.writestr(rel, b)
            lines.append(f"{hashlib.sha256(b).hexdigest()}  {len(b):>9}  {rel}")
        z.writestr("BUNDLE_MANIFEST.txt", "sha256  bytes  path\n" + "\n".join(lines) + "\n")
    print("bundle", out, out.stat().st_size, "bytes,", len(files), "files")


if __name__ == "__main__":
    main()
