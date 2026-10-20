"""Exploratory single fetch with a receipt:  cx_fetch.py <label> <url> [key=value ...] [--post] [--head N]
Prints status, byte count, sha256, raw path and the first N characters (default 1500) of the body.
"""
from __future__ import annotations

import sys

import census_common as C


def main():
    args = sys.argv[1:]
    post = "--post" in args
    head = 1500
    if "--head" in args:
        i = args.index("--head")
        head = int(args[i + 1])
        del args[i:i + 2]
    args = [a for a in args if a != "--post"]
    label, url, kv = args[0], args[1], args[2:]
    params = dict(a.split("=", 1) for a in kv) if kv else None
    if post:
        f = C.fetch(url, label, data=params, method="POST")
    else:
        f = C.fetch(url, label, params=params)
    print("STATUS", f.status, "|", f.describe(), "| exc:", f.exc)
    for r in f.receipts:
        print("RECEIPT", r["receipt"], r["status"], r["bytes"], r["sha256"], r["raw"], r["url"][:200])
    if f.resp is not None:
        print("CONTENT-TYPE", f.resp.headers.get("Content-Type"), "| final url:", f.resp.url[:300])
        t = f.text or ""
        print("----- body head -----")
        print(t[:head])


if __name__ == "__main__":
    main()
