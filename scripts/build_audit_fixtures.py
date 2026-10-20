"""Build ``tests/fixtures/audit/``: three real stars, small enough to commit.

The audit rules are tested twice: once on synthetic light curves, one test per
rule (``tests/test_audit_prep.py``, ``test_event_vet.py``, ``test_star_vet.py``),
and once against the records prompts 5 and 6 actually produced, which is what
this script prepares.

For each star only the product the audit would CHOOSE for a sector is kept
(SPOC 2-min, else TESS-SPOC, else QLP), because ``choose_per_sector`` discards
the rest anyway; the fixture therefore reproduces the audit exactly while being
about half the size of the download.  The stellar parameters and the survivor /
candidate rows travel with the fixture so the tests need nothing from
``data/cache/`` (git-ignored) at all.

Stars: TIC 334678787 (P5 rank 4, the "every automated check clean" candidate),
TIC 212261364 (P5 rank 2, the phase-independent exclusion) and TIC 233007823
(P6 rank 16, a Stage A PASS and the eccentric eclipsing binary of REVET.md
section 10).

    py scripts/build_audit_fixtures.py [--out tests/fixtures/audit]
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

LC_ROOT = REPO / "data" / "survey" / "audit_lc"
P5 = REPO / "data" / "survey" / "p5"
P6 = REPO / "data" / "survey" / "p6"

#: (TIC, period, where the expected records come from, why this star)
STARS = [
    (334678787, 46.20629896218089, "p5",
     "P5 rank 4: one PDC-made dip at a scattered-light surge, nothing at 18 other epochs"),
    (212261364, 8.953781892201565, "p5",
     "P5 rank 2: the binary host whose eclipses folded into the stitch search"),
    (233007823, 17.46828986564532, "p6",
     "P6 rank 16: a Stage A PASS, and the eccentric eclipsing binary of REVET.md section 10"),
]
PREF = {"SPOC": 0, "TESS-SPOC": 1, "QLP": 2}


def survivor_rows(tic: int) -> list[dict]:
    return [r for r in csv.DictReader(open(REPO / "data/survey/p4/survivors.csv", newline="",
                                           encoding="utf-8")) if int(r["tic_id"]) == tic]


def candidate_rows(tic: int) -> list[dict]:
    return [r for r in csv.DictReader(open(REPO / "data/survey/p4/candidates.csv", newline="",
                                           encoding="utf-8")) if int(r["tic_id"]) == tic]


def build(out_root: Path) -> dict:
    import audit_p5 as A
    A.set_roots(P6, LC_ROOT)
    manifest = {"what": "per-product arrays and expected audit records for three real stars",
                "built_by": "scripts/build_audit_fixtures.py", "stars": []}
    total = 0
    for tic, period, src, why in STARS:
        k = A.key(tic, period)
        d = out_root / f"tic{tic}"
        if d.exists():
            shutil.rmtree(d)
        (d / "expected").mkdir(parents=True, exist_ok=True)
        idx = json.loads((LC_ROOT / f"tic{tic}" / "index.json").read_text(encoding="utf-8"))
        best: dict[int, dict] = {}
        for p in idx["products"]:
            if "file" not in p:
                continue
            s = p["sector"]
            if s not in best or PREF[p["author"]] < PREF[best[s]["author"]]:
                best[s] = p
        kept = [best[s] for s in sorted(best)]
        nbytes = 0
        for p in kept:
            shutil.copy2(LC_ROOT / f"tic{tic}" / p["file"], d / p["file"])
            nbytes += (d / p["file"]).stat().st_size
        (d / "index.json").write_text(json.dumps(
            {"tic_id": tic, "n_products": len(kept),
             "note": "one product per sector, exactly what audit_p5.choose_per_sector keeps",
             "products": kept}, indent=1), encoding="utf-8")
        # stellar parameters, so the tests need nothing from the git-ignored TIC cache
        st = A.stellar_from_cache(tic)
        sp = A.stellar_for(tic, period)
        (d / "star.json").write_text(json.dumps(
            {"tic_id": tic, "why": why,
             "R_star": sp["R_star"], "M_star": sp["M_star"],
             "expected_t14_hours_b0": sp["expected_t14_hours_b0"],
             "teff": st.get("teff"), "ra": st.get("ra"), "dec": st.get("dec"),
             "tmag": st.get("tmag"), "rho": st.get("rho"),
             "survivors": survivor_rows(tic), "accepted_candidates": candidate_rows(tic)},
            indent=1), encoding="utf-8")
        # the records these arrays must reproduce
        exp = {}
        root = P5 if src == "p5" else P6
        for eph in ("survey", "packet", "tls"):
            f = root / "events" / f"{k}_{eph}.json"
            if f.exists():
                shutil.copy2(f, d / "expected" / f"events_{eph}.json")
                exp[f"events_{eph}"] = str(f.relative_to(REPO))
        for name, f in (("prep", P6 / "prep" / f"{k}.json"),
                        ("stageA", P6 / "stageA" / f"{k}.json"),
                        ("stageB", P6 / "stageB" / f"{k}.json")):
            if f.exists():
                shutil.copy2(f, d / "expected" / f"{name}.json")
                exp[name] = str(f.relative_to(REPO))
        # the cached neighbours record, for the Gaia digest test (no network in the suite)
        nb = P6 / "neighbours" / f"tic{tic}.json"
        if nb.exists():
            shutil.copy2(nb, d / "expected" / "neighbours.json")
            exp["neighbours"] = str(nb.relative_to(REPO))
        size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        total += size
        manifest["stars"].append({"tic_id": tic, "key": k, "survey_period": period, "why": why,
                                  "n_products": len(kept), "sectors": [p["sector"] for p in kept],
                                  "arrays_bytes": nbytes, "total_bytes": size,
                                  "expected_from": exp})
        print(f"TIC {tic}: {len(kept)} products, {size / 1e6:.2f} MB, expected: {sorted(exp)}")
    manifest["total_bytes"] = total
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"total {total / 1e6:.2f} MB -> {out_root}")
    return manifest


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(REPO / "tests" / "fixtures" / "audit"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    build(out)


if __name__ == "__main__":
    main()
