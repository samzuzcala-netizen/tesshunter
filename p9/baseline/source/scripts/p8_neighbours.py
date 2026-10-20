"""Prompt 8 Part 1b: Gaia DR3, SIMBAD and VSX within 1 arcmin for EVERY P8 star, up front.

Prompt 7 could evaluate the Gaia penalty for 36 of 405 candidates because Gaia was queried
only for stars that reached Stage B.  Here every star in ``targets_p8.csv`` gets the record
``audit_p5.neighbours_step`` writes (the 1-arcmin Gaia DR3 ADQL cone with the NSS tables, the
dilution table, SIMBAD, VSX), cached per star as ``data/survey/p8/neighbours/tic<id>.json`` - the
exact layout ``star_vet.gaia_flag_digest`` and ``ranking.gaia_penalty_flags`` consume.

Measured before this was written [M]: one Gaia cone 1.7 s, one VSX cone 0.9 s, one SIMBAD region
query 32 s (a fixed per-query cost: 100 coordinates in one query take 40 s).  So SIMBAD and VSX are
fetched in BULK (SIMBAD in chunks of 100 coordinates, VSX in chunks of 500, both mapped back to the
targets by separation) and cached in ``data/survey/p8/neighbours_bulk/``; only the Gaia cone is
per star, at two workers (the prompt's limit), which is under the prompt's one-hour threshold for
per-star cones.  The per-star record says which parts came from the bulk fetch.

    python scripts/p8_neighbours.py bulk            # SIMBAD + VSX for every star, cached
    python scripts/p8_neighbours.py stars --workers 2   # Gaia per star + assembly
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

OUT = REPO / "data" / "survey" / "p8"
LC_ROOT = REPO / "data" / "survey" / "audit_lc"
TARGETS = REPO / "data" / "survey" / "targets_p8.csv"
BULK = OUT / "neighbours_bulk"
SIMBAD_CHUNK = 100
VSX_CHUNK = 500


def _fval(v):
    try:
        if v is None or (hasattr(v, "mask") and bool(v.mask)):
            return None
        f = float(v)
        return None if f != f else f
    except Exception:
        return None


def load_targets(path: str) -> list[dict]:
    return list(csv.DictReader(open(path, newline="", encoding="utf-8")))


def vsx_with_separations(target: dict, objects: list[dict]) -> list[dict]:
    """Derive angular distances from coordinates, independent of VizieR's _r units."""
    from astropy.coordinates import SkyCoord
    if not objects:
        return []
    centre = SkyCoord(float(target["ra_deg"]), float(target["dec_deg"]), unit="deg")
    sources = SkyCoord([float(o["RAJ2000"]) for o in objects],
                       [float(o["DEJ2000"]) for o in objects], unit="deg")
    return [dict(o, sep_arcsec=round(float(sep), 1))
            for o, sep in zip(objects, centre.separation(sources).arcsec)]


def bulk_simbad(rows: list[dict], force: bool = False) -> dict[int, list[dict]]:
    import warnings
    warnings.simplefilter("ignore")
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from astroquery.simbad import Simbad
    BULK.mkdir(parents=True, exist_ok=True)
    out: dict[int, list[dict]] = {}
    for a in range(0, len(rows), SIMBAD_CHUNK):
        chunk = rows[a:a + SIMBAD_CHUNK]
        cache = BULK / f"simbad_{a:05d}.json"
        if cache.exists() and not force:
            for k, v in json.loads(cache.read_text(encoding="utf-8")).items():
                out[int(k)] = v
            continue
        t0 = time.time()
        c = SkyCoord([float(r["ra_deg"]) for r in chunk], [float(r["dec_deg"]) for r in chunk], unit="deg")
        s = Simbad()
        for f in ("otype", "otypes", "sp_type", "V", "G"):
            try:
                s.add_votable_fields(f)
            except Exception:
                pass
        res: dict[int, dict[str, dict]] = {int(r["tic_id"]): {} for r in chunk}
        for attempt in range(3):
            try:
                t = s.query_region(c, radius=1 * u.arcmin)
                break
            except Exception as exc:
                t = None
                last = exc
                time.sleep(20 * (attempt + 1))
        else:
            raise RuntimeError(f"SIMBAD bulk query failed at chunk {a}: {last}")
        if t is not None and len(t):
            objs = SkyCoord([float(x) for x in t["ra"]], [float(x) for x in t["dec"]], unit="deg")
            for i, r in enumerate(chunk):
                sep = c[i].separation(objs).arcsec
                for j in [k for k in range(len(t)) if sep[k] <= 60.0]:
                    row = t[j]
                    mid = str(row["main_id"])
                    ot = str(row["otypes.otype_txt"]) if "otypes.otype_txt" in t.colnames else ""
                    d = res[int(r["tic_id"])].setdefault(mid, {
                        "main_id": mid, "otype": str(row["otype"]) if "otype" in t.colnames else None, "otypes": set(),
                        "sp_type": str(row["sp_type"]) if "sp_type" in t.colnames else None,
                        "sep_arcsec": round(float(sep[j]), 1), "V": _fval(row["V"]) if "V" in t.colnames else None,
                        "G": _fval(row["G"]) if "G" in t.colnames else None})
                    if ot and ot != "--":
                        d["otypes"].add(ot)
        packed = {str(tic): [dict(o, otypes="|".join(sorted(o["otypes"]))) for o in objs_.values()] for tic, objs_ in res.items()}
        cache.write_text(json.dumps(packed, indent=0), encoding="utf-8")
        for k, v in packed.items():
            out[int(k)] = v
        print(f"simbad chunk {a // SIMBAD_CHUNK + 1}/{(len(rows) + SIMBAD_CHUNK - 1) // SIMBAD_CHUNK}: "
              f"{0 if t is None else len(t)} rows, {sum(len(v) for v in packed.values())} objects, {time.time() - t0:.0f} s", flush=True)
    return out


def bulk_vsx(rows: list[dict], force: bool = False) -> dict[int, list[dict]]:
    import warnings
    warnings.simplefilter("ignore")
    import astropy.units as u
    import numpy as np
    from astropy.coordinates import SkyCoord
    from astroquery.vizier import Vizier
    BULK.mkdir(parents=True, exist_ok=True)
    out: dict[int, list[dict]] = {}
    targets = {int(r["tic_id"]): r for r in rows}
    for a in range(0, len(rows), VSX_CHUNK):
        chunk = rows[a:a + VSX_CHUNK]
        cache = BULK / f"vsx_{a:05d}.json"
        if cache.exists() and not force:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            corrected = {k: vsx_with_separations(targets[int(k)], v) for k, v in cached.items()}
            if corrected != cached:
                cache.write_text(json.dumps(corrected, indent=0), encoding="utf-8")
            for k, v in corrected.items():
                out[int(k)] = v
            continue
        t0 = time.time()
        c = SkyCoord([float(r["ra_deg"]) for r in chunk], [float(r["dec_deg"]) for r in chunk], unit="deg")
        v = Vizier(catalog="B/vsx/vsx", columns=["**"], row_limit=-1)
        for attempt in range(3):
            try:
                tl = v.query_region(c, radius=1 * u.arcmin)
                break
            except Exception as exc:
                tl = None
                last = exc
                time.sleep(20 * (attempt + 1))
        else:
            raise RuntimeError(f"VSX bulk query failed at chunk {a}: {last}")
        res: dict[int, list[dict]] = {int(r["tic_id"]): [] for r in chunk}
        for t in (tl or []):
            for row in t:
                q = int(row["_q"]) - 1
                rr = {}
                for col in t.colnames:
                    val = row[col]
                    rr[col] = None if (hasattr(val, "mask") and bool(np.all(val.mask))) else (
                        float(val) if isinstance(val, (np.floating, float, np.integer, int)) else str(val))
                rr = vsx_with_separations(chunk[q], [rr])[0]
                res[int(chunk[q]["tic_id"])].append(rr)
        packed = {str(k): v_ for k, v_ in res.items()}
        cache.write_text(json.dumps(packed, indent=0), encoding="utf-8")
        for k, v_ in packed.items():
            out[int(k)] = v_
        print(f"vsx chunk {a // VSX_CHUNK + 1}: {sum(len(x) for x in res.values())} entries, {time.time() - t0:.0f} s", flush=True)
    return out


def status_of(rec: dict) -> dict:
    return {"gaia_ok": "error" not in (rec.get("gaia") or {}),
            "simbad_ok": "error" not in (rec.get("simbad") or {}),
            "vsx_ok": "error" not in (rec.get("vsx") or {}),
            "target_match": (rec.get("gaia") or {}).get("target_match")}


def one(tic: int, targets: str, force: bool) -> dict:
    import audit_p5 as A
    A.set_roots(OUT, LC_ROOT)
    A.set_population(survivors_csv=targets)
    target = next(r for r in load_targets(targets) if int(r["tic_id"]) == tic)
    for p in sorted(BULK.glob("simbad_*.json")):
        for k, v in json.loads(p.read_text(encoding="utf-8")).items():
            if int(k) == tic:
                A.PREFETCHED_SIMBAD[tic] = v
    for p in sorted(BULK.glob("vsx_*.json")):
        for k, v in json.loads(p.read_text(encoding="utf-8")).items():
            if int(k) == tic:
                A.PREFETCHED_VSX[tic] = vsx_with_separations(target, v)
    t0 = time.perf_counter()
    try:
        rec = A.neighbours_step(tic, force=force)
        st = status_of(rec)
        return {"tic_id": tic, "ok": all(st[k] for k in ("gaia_ok", "simbad_ok", "vsx_ok")), **st,
                "n_gaia": (rec.get("gaia") or {}).get("n_within_1arcmin"),
                "n_simbad": (rec.get("simbad") or {}).get("n_within_1arcmin"),
                "n_vsx": (rec.get("vsx") or {}).get("n_within_1arcmin"),
                "seconds": round(time.perf_counter() - t0, 1)}
    except Exception as exc:
        return {"tic_id": tic, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:300],
                "seconds": round(time.perf_counter() - t0, 1)}


def summarize(tics: list[int], workers: int, n_queried: int, elapsed_min: float) -> dict:
    nb_dir = OUT / "neighbours"
    summ = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n_stars": len(tics),
            "workers": workers, "n_queried_this_run": n_queried, "elapsed_min": elapsed_min,
            "complete": 0, "gaia_error": 0, "simbad_error": 0, "vsx_error": 0, "missing_file": 0,
            "target_match": {}, "n_gaia_within_1arcmin_quantiles": None, "n_with_vsx_entry": 0,
            "n_with_simbad_entry": 0, "n_neighbours_3px_1ppt_gt0": 0, "target_flags": {},
            "simbad_source": "bulk query_region in chunks of 100 coordinates, objects within 60 arcsec by separation",
            "vsx_source": "bulk Vizier B/vsx/vsx query_region in chunks of 500 coordinates (_q index)"}
    ng, flags = [], {"ruwe_gt_1.4": 0, "ipd_multi_peak_gt_10": 0, "aen_sig_gt_2": 0, "non_single_star": 0,
                     "phot_variable": 0, "no_target_match": 0}
    for t in tics:
        p = nb_dir / f"tic{t}.json"
        if not p.exists():
            summ["missing_file"] += 1
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        st = status_of(rec)
        summ["complete"] += int(all(st[k] for k in ("gaia_ok", "simbad_ok", "vsx_ok")))
        summ["gaia_error"] += int(not st["gaia_ok"]); summ["simbad_error"] += int(not st["simbad_ok"])
        summ["vsx_error"] += int(not st["vsx_ok"])
        tm = st["target_match"] or "error"
        summ["target_match"][tm] = summ["target_match"].get(tm, 0) + 1
        g = rec.get("gaia") or {}
        if "error" not in g:
            ng.append(g.get("n_within_1arcmin", 0))
            summ["n_neighbours_3px_1ppt_gt0"] += int((g.get("n_neighbours_within_3px_could_make_1ppt") or 0) > 0)
            tg = g.get("target") or {}
            if not tg:
                flags["no_target_match"] += 1
            else:
                flags["ruwe_gt_1.4"] += int((tg.get("ruwe") or 0) > 1.4)
                flags["ipd_multi_peak_gt_10"] += int((tg.get("ipd_frac_multi_peak") or 0) > 10)
                flags["aen_sig_gt_2"] += int((tg.get("astrometric_excess_noise_sig") or 0) > 2)
                flags["non_single_star"] += int((tg.get("non_single_star") or 0) > 0)
                flags["phot_variable"] += int(str(tg.get("phot_variable_flag") or "") == "VARIABLE")
        summ["n_with_vsx_entry"] += int(((rec.get("vsx") or {}).get("n_within_1arcmin") or 0) > 0)
        summ["n_with_simbad_entry"] += int(((rec.get("simbad") or {}).get("n_within_1arcmin") or 0) > 0)
    if ng:
        import numpy as np
        summ["n_gaia_within_1arcmin_quantiles"] = [float(x) for x in np.percentile(ng, [10, 50, 90])]
    summ["target_flags"] = flags
    (OUT / "neighbours_p8.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    return summ


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["bulk", "stars", "summary"])
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--targets", default=str(TARGETS))
    ap.add_argument("--first", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    rows = load_targets(a.targets)
    if a.first:
        rows = rows[: a.first]
    tics = [int(r["tic_id"]) for r in rows]
    if a.cmd == "bulk":
        t0 = time.time()
        vs = bulk_vsx(rows, a.force)
        print(f"VSX: {sum(1 for v in vs.values() if v)} of {len(rows)} stars with an entry, {time.time() - t0:.0f} s", flush=True)
        t0 = time.time()
        sb = bulk_simbad(rows, a.force)
        print(f"SIMBAD: {sum(1 for v in sb.values() if v)} of {len(rows)} stars with an object, {time.time() - t0:.0f} s", flush=True)
        return
    if a.cmd == "summary":
        print(json.dumps(summarize(tics, a.workers, 0, 0.0), indent=1))
        return
    nb_dir = OUT / "neighbours"
    nb_dir.mkdir(parents=True, exist_ok=True)
    todo, done = [], []
    for t in tics:
        p = nb_dir / f"tic{t}.json"
        if p.exists() and not a.force:
            st = status_of(json.loads(p.read_text(encoding="utf-8")))
            if all(st[k] for k in ("gaia_ok", "simbad_ok", "vsx_ok")):
                done.append(t)
                continue
            p.unlink()
        todo.append(t)
    print(f"{len(tics)} P8 stars: {len(done)} complete, {len(todo)} to query, {a.workers} workers", flush=True)
    results, t0 = [], time.perf_counter()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one, t, a.targets, a.force): t for t in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            el = time.perf_counter() - t0
            print(f"[{i}/{len(todo)}] TIC {r['tic_id']}: " + ("ok" if r["ok"] else "INCOMPLETE " + str(r.get("error", "")))
                  + f" gaia {r.get('n_gaia')} simbad {r.get('n_simbad')} vsx {r.get('n_vsx')} in {r['seconds']} s | "
                  f"elapsed {el / 60:.1f} min, eta {(el / i) * (len(todo) - i) / 60:.1f} min", flush=True)
    print(json.dumps(summarize(tics, a.workers, len(todo), round((time.perf_counter() - t0) / 60, 1)), indent=1), flush=True)


if __name__ == "__main__":
    main()
