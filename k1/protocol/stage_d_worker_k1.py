"""K1 Stage D worker (copy of ``p12/protocol/stage_d_worker_p12.py``, K1 roots and change 8).

Events under every ephemeris, the precomputed neighbour record, the K1 hard-stop record, the
Stage-C-seeded all-transit fit, TRICERATOPS on ONE product class at its real exposure and author,
TESScut centroids, difference images and Tmag-scaled fixed apertures, and the K1 tiers (``k1.0`` =
p12.0 plus the K8 long-period HOLD; p12.0 recorded beside it).  Known-planet and adversarial
validation cases run with the catalogue known-status clauses redacted (``redact_catalogue``), as the
Oct 3 harness did through P12's interface.  Packets only for SUBMIT/HOLD, under
``D:/tesshunter_k1/packets/<label>/``.  Nothing is submitted anywhere.
CLI: ``stage_d_worker_k1.py <runtime.json>``.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

from k1_common import REPO, ROOT, DATA, RECEIPTS, environment, read, write, utc, safe

RUNTIME_FIELDS = {"candidate_id", "key", "tic_id", "period", "depth_ppt", "root", "lc_root", "preset", "s_mode",
                  "crossmatch_star", "tce_sidecar", "star", "neighbours_path", "n_draws", "label", "use",
                  "redact_catalogue", "job", "candidate", "all_candidates", "ramp_variant"}


def _patch_inputs(A, rt, root):
    tic = int(rt["tic_id"])
    star = rt["star"]
    stellar = {"radius": star["radius_rsun"], "mass": star["mass_msun"], "teff": star["teff_k"],
               "tmag": star["tmag"], "ra": star["ra_deg"], "dec": star["dec_deg"], "logg": star.get("logg")}
    A.stellar_from_cache = lambda requested: stellar if int(requested) == tic else {}
    target = root / "neighbours" / f"tic{tic}.json"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(rt["neighbours_path"], target)

    def neighbours(t, force=False):
        if int(t) != tic:
            raise RuntimeError("Neighbour lookup for another star")
        nb = copy.deepcopy(read(target))
        depths = [float(r["depth_ppt"]) for r in csv.DictReader((root / "survivors.csv").open(encoding="utf-8"))]
        g = nb.get("gaia") or {}
        if g.get("error") or not g.get("target"):
            raise RuntimeError("Gaia neighbour record unavailable: " + str(g.get("error")))
        for n in g.get("neighbours", []):
            d = n.get("max_observed_depth_ppt_total_eclipse")
            n["can_produce_candidate_depths_total_eclipse"] = [d >= v for v in depths] if d is not None else None
            n["can_produce_candidate_depths_50pct_eclipse"] = [d / 2 >= v for v in depths] if d is not None else None
        nb["candidate_depths_ppt"] = depths
        A.jdump(target, nb)
        return nb
    A.neighbours_step = neighbours


ORIGINAL_EPHEMERIS = None


def _fit_seed(A, root, key, tic, period):
    import numpy as np
    path = root / "stageC" / f"{key}.json"
    raw = path.read_bytes()
    rec = json.loads(raw)
    if not A.cache_matches(rec):
        raise ValueError(f"{key}: Stage C record does not match the stage rules / input configuration")
    survey = ORIGINAL_EPHEMERIS(tic, period)
    if rec.get("decision") != "PASS":
        raise ValueError(f"{key}: Stage C {rec.get('decision')} is not eligible for D")
    blind = rec["blind"]
    p, t0, duration, depth = (float(blind[n]) for n in ("period", "T0_btjd", "duration_days", "depth"))
    if not np.all(np.isfinite([p, t0, duration, depth])) or not (0 < duration < p and 0 < depth < 1):
        raise ValueError(f"{key}: invalid accepted Stage C fit ephemeris")
    return {"version": 1, "stage_c_sha256": hashlib.sha256(raw).hexdigest(),
            "ephemeris": {"period": p, "t0": t0, "duration": max(survey["duration"], duration),
                          "source": "stageC.blind", "ref_depth_ppt": survey["ref_depth_ppt"]}, "depth_flux": depth}


def _install_fit_seed(A, root, key, tic, period):
    global ORIGINAL_EPHEMERIS
    ORIGINAL_EPHEMERIS = A._ephemeris
    original_fit = A.fit_step
    seed = _fit_seed(A, root, key, tic, period)

    def seeded(t, p, source="survey"):
        if source == "survey" and int(t) == tic and abs(float(p) / period - 1) < 1e-12:
            return dict(seed["ephemeris"])
        return ORIGINAL_EPHEMERIS(t, p, source)

    def fit_step(t, p, force=False, max_iter=2000):
        if int(t) != tic or abs(float(p) / period - 1) > 1e-12:
            return original_fit(t, p, force=force, max_iter=max_iter)
        out = root / "fit" / f"{key}.json"
        if out.exists() and not force:
            cached = read(out)
            if A.cache_matches(cached) and cached.get("fit_input") == seed:
                return cached
        A._ephemeris = seeded
        try:
            result = original_fit(t, p, force=True, max_iter=max_iter)
        finally:
            A._ephemeris = ORIGINAL_EPHEMERIS
        result["fit_input"] = seed
        A.jdump(out, result)
        return result

    A.fit_step = fit_step
    A._p8_fit_input = lambda t, p: _fit_seed(A, root, key, tic, float(p))
    return dict(seed=seed)


def main(runtime_path):
    environment(offline=False)
    runtime_path = Path(runtime_path)
    rt = read(runtime_path)
    if set(rt) - RUNTIME_FIELDS:
        raise RuntimeError("Unregistered runtime fields: " + ",".join(sorted(set(rt) - RUNTIME_FIELDS)))
    if rt["preset"] not in ("survey_k1", "survey_k1_s56"):
        raise RuntimeError("Unregistered preset")
    cid, key, label = rt["candidate_id"], rt["key"], rt["label"]
    tic, period = int(rt["tic_id"]), float(rt["period"])
    dest = RECEIPTS / label / "D" / f"{cid}.json"
    if dest.exists():
        raise FileExistsError(dest)
    started, timer = utc(), time.perf_counter()
    steps, errors, tiers, packet, status = {}, {}, {}, None, "OPERATIONAL_UNKNOWN"
    try:
        import funnel_k1
        F, A, root = funnel_k1.setup(dict(rt, ramp_variant=bool(rt.get("ramp_variant"))))
        environment(offline=False)
        import os
        os.environ.pop("TESSHUNTER_OFFLINE", None)
        V = F.V
        _patch_inputs(A, rt, root)
        seed = _install_fit_seed(A, root, key, tic, period)
        job = dict(rt["job"], tic_id=tic, period=period, depth_ppt=rt["depth_ppt"], key=key)
        xm = dict(catalog_stamp=(rt["crossmatch_star"] or {}).get("catalog_stamp"),
                  per_star={str(tic): rt["crossmatch_star"] or {}})
        A.jdump(root / f"crossmatch_{root.name}.json", xm)
        clock = time.perf_counter()
        staged = V.staged_one(job, xm, force=True)
        steps["staged"] = round(time.perf_counter() - clock, 1)
        if staged.get("verdict") == "ERROR":
            errors["staged"] = staged.get("reason")
        extra = fit = arrays = None
        if not errors and not (staged.get("fit") or {}).get("error"):
            import stage_d_packets_k1 as D
            clock = time.perf_counter()
            try:
                extra, fit, arrays = D.measure(A, V, root, job, rt["n_draws"], "normal")
            except Exception as exc:
                errors["measure"] = f"{type(exc).__name__}: {exc}"[:400]
            steps["measure"] = round(time.perf_counter() - clock, 1)
        if extra is not None:
            import stage_d_pixels_k1 as P
            clock = time.perf_counter()
            try:
                used = sorted(s["sector"] for s in (extra.get("centroid") or {}).get("per_sector", []) if s.get("source") == "TESScut")
                if used:
                    nb = read(root / "neighbours" / f"tic{tic}.json")
                    gaia_path = root / "pixels" / f"tic{tic}_gaia_positions.json"
                    gaia = P.gaia_positions(nb["ra"], nb["dec"], gaia_path)
                    a = fit["adopted"]
                    eph = dict(period=a["period"], t0=a["t0_btjd"], duration=a["t14_hours"] / 24, source="K1 physical fit")
                    cache = Path(A.AUDIT_CACHE) / "tesscut"
                    pinned = [root / "fit" / f"{key}.json", root / "stageC" / f"{key}.json", gaia_path]
                    diff = P.difference(root, key, eph, used, gaia, nb, cache, pinned)
                    P.aperture(root, key, eph, diff, nb, cache)
                else:
                    errors["pixels"] = "no TESScut sector in the centroid record"
            except Exception as exc:
                errors["pixels"] = f"{type(exc).__name__}: {exc}"[:400]
            steps["pixels"] = round(time.perf_counter() - clock, 1)
        from tesshunter import verdict_tiers as T
        import rules_k1
        p12 = rules_k1._p12()
        install = p12.install()
        inputs = T.load_inputs(root, key, tic, period, rt["depth_ppt"], candidates_csv=root / "candidates.csv")
        inputs["crossmatch_star"] = rt["crossmatch_star"] or {}
        inputs["catalogue_periods"] = T.catalogue_periods_from(inputs["neighbours"], inputs["crossmatch_star"])
        inputs["tce_association"] = rt.get("tce_sidecar")
        redact = bool(rt.get("redact_catalogue"))
        tiers["p12.0"] = p12.evaluate(copy.deepcopy(inputs), "p12.0", redact_catalogue=redact)
        tiers["k1.0"] = rules_k1.evaluate(copy.deepcopy(inputs), redact_catalogue=redact)
        record = read(root / "stageD" / f"{key}.json")
        record.update(tiers_by_rules=tiers, tiers=tiers["k1.0"], provisional_verdict=tiers["k1.0"]["verdict"],
                      d_errors=errors, fit_seed=seed, p12_install=install, redacted=redact)
        A.jdump(root / "stageD" / f"{key}.json", record)
        final = tiers["k1.0"]
        if fit is not None and arrays is not None and final["verdict"] in ("SUBMIT", "HOLD"):
            import stage_d_packets_k1 as D
            packet = D.build_packet(A, root, job, fit, arrays, extra, tiers, DATA / "packets" / label,
                                    dict(label=label, use=rt.get("use"), redacted_catalogue=redact))
        status = "COMPLETE"
    except Exception as exc:
        errors["worker"] = f"{type(exc).__name__}: {exc}"[:400]
        errors["traceback"] = traceback.format_exc()[-3000:]
    receipt = dict(candidate_id=cid, key=key, tic_id=tic, stage="D", label=label, use=rt.get("use"), status=status,
                   started_utc=started, completed_utc=utc(), wall_seconds=time.perf_counter() - timer,
                   steps_seconds=steps, errors=errors,
                   verdicts={r: dict(verdict=t["verdict"], deciding_condition=t["deciding_condition"],
                                     candidate_tier=(t.get("candidate_tier") or {}).get("candidate_tier"),
                                     not_measurable=t.get("not_measurable"))
                             for r, t in tiers.items()},
                   packet=str(packet) if packet else None, redacted=bool(rt.get("redact_catalogue")))
    write(dest, safe(json.loads(json.dumps(receipt, default=str))))
    print("D", cid, status, round(receipt["wall_seconds"], 1), flush=True)
    return 0 if status == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
