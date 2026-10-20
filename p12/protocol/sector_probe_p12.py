"""P12 list-only adaptation of build_p8_population.latest_public_sector.

The source's highest-public-QLP convention is retained. Membership discovery
uses exactly one directory-list GET per author (interface clarification C1).
"""
import argparse
import hashlib
import re
import urllib.request

from p12_common import ROOT, environment, utc, write

LIST_URLS = {
    "qlp": "https://archive.stsci.edu/hlsps/qlp/target_lists/",
    "tess-spoc": "https://archive.stsci.edu/hlsps/tess-spoc/target_lists/",
}


def latest_public_sector() -> dict:
    if __import__("os").environ.get("TESSHUNTER_OFFLINE") == "1":
        raise RuntimeError("Sector probe requires explicit online execution")
    sources = {}
    for author, url in LIST_URLS.items():
        started = utc()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "TessHunter P12 catalog audit"})
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
            sectors = sorted({int(s) for s in re.findall(r"\bs(\d{4})\.csv\b", body.decode("utf-8", "replace"))})
            sources[author] = dict(url=url, started_utc=started, utc=utc(), bytes=len(body),
                sha256=hashlib.sha256(body).hexdigest(), available_sectors=sectors,
                status="COMPLETE" if sectors else "UNMEASURED", error=None if sectors else "No sector-list membership in directory response")
        except Exception as exc:
            sources[author] = dict(url=url, started_utc=started, utc=utc(), bytes=0, sha256=None,
                available_sectors=[], status="OPERATIONAL_UNKNOWN", error=f"{type(exc).__name__}: {exc}")
    qlp = sources["qlp"]["available_sectors"]
    return dict(latest_public_sector=max(qlp) if qlp else None, probed_utc=utc(), sources=sources,
        core_stars_with_product_above_105=None, core_above_105_status="UNMEASURED",
        limitation="Directory membership does not measure per-star above-105 coverage; no per-star calls performed")


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    environment(offline=False)
    result = latest_public_sector()
    write(ROOT / "manifests/sector_probe.json", result)
    print("Sector-list probe recorded; per-star coverage unmeasured", flush=True)


if __name__ == "__main__":
    main()
