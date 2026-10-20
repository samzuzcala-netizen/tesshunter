"""Inspect a saved raw response (read-only): cx_inspect.py <path> [forms|links|text|grep] [pattern] [maxchars]"""
from __future__ import annotations

import html
import re
import sys


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    path, mode = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "text")
    pat = sys.argv[3] if len(sys.argv) > 3 else None
    maxc = int(sys.argv[4]) if len(sys.argv) > 4 else 8000
    t = open(path, encoding="utf-8", errors="replace").read()
    if mode == "forms":
        for m in re.finditer(r"<form.*?</form>", t, flags=re.S | re.I):
            print(re.sub(r"\s+", " ", m.group(0))[:3000])
            print("-----")
    elif mode == "links":
        for m in re.finditer(r"href=[\"']([^\"']+)[\"']", t, flags=re.I):
            u = m.group(1)
            if pat is None or re.search(pat, u, flags=re.I):
                print(u)
    elif mode == "grep":
        for i, line in enumerate(t.splitlines()):
            if re.search(pat, line, flags=re.I):
                print(i, line[:400])
    else:
        body = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S | re.I)
        txt = re.sub(r"<[^>]+>", " ", body)
        txt = html.unescape(re.sub(r"[ \t]+", " ", txt))
        txt = re.sub(r"\n\s*\n+", "\n", txt)
        if pat:
            i = txt.lower().find(pat.lower())
            txt = txt[max(0, i - 200):] if i >= 0 else txt
        print(txt[:maxc])


if __name__ == "__main__":
    main()
