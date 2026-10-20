"""K1 A / S / B / C worker for one candidate (copy of ``p12/protocol/funnel_stage_p12.py``, K1 roots).

Each candidate runs in its own case root ``D:/tesshunter_k1/funnel/<label>/<cid>/`` (S, B and C reuse
it).  The frozen funnel code (``scripts/audit_p5.py``, ``scripts/revet_p6.py``,
``p10/protocol/p10_funnel_calibration.py``) is NOT edited; K1 behaviour is installed in-process:

* inputs: the K1 store (or an injection's own store copy), ``A.set_input_config(<preset>)`` (the
  window rule of the funnel is unchanged: 3 x T14, floor 0.75 d, cap 1.5 d), and a K1
  ``choose_per_sector`` (usable products; s56 arm by ``sector_min``; native mixed cadence, 2-min
  binned to 200 s);
* rules: p10.0 with the S gate mode of the runtime (``bound`` unless rule E2 chose another);
  every S scan records every p10 mode and ``bound_alias`` (``k1_modes``);
* change 12: ``event_vet.SAP_RAMP_NOISE_MULTIPLE = 3`` when ``ramp_variant`` is true;
* exposure-aware Stage B: ``star_vet.B_CADENCE_RULE = "per_window"``;
* the TLS sub-cadence duration floor uses the cadence of the products carrying the events.

CLI: ``funnel_k1.py <A|S|B|C> <runtime.json>``.  Receipts: ``k1/results/funnel/<label>/<stage>/<cid>.json``.
"""
from __future__ import annotations

import csv
import os
import sys
import time
import traceback
from pathlib import Path

from k1_common import REPO, ROOT, DATA, TRUTH, RECEIPTS, environment, read, write, utc, safe

environment(offline=True)

RUNTIME_FIELDS = {"candidate_id", "tic_id", "candidate", "all_candidates", "star", "lc_root", "root", "preset",
                  "s_mode", "ramp_variant", "label", "use", "neighbours_path", "tls_threads"}
S_MODES = ("bound", "empirical_bound", "recurrent_bound", "recurrent_bound_corr", "bound_alias")


def k1_choose_per_sector(A):
    from tesshunter.survey_p8 import harmonise_cadence
    import sector_policy_k1 as SP

    def choose(products):
        cfg = A.INPUT_CONFIG
        rows = [p for p in products if SP.product_usable(p["author"], p["sector"])
                and (cfg.sector_min is None or int(p["sector"]) >= cfg.sector_min)
                and (cfg.sector_max is None or int(p["sector"]) <= cfg.sector_max)]
        selected = SP.choose_products(rows)
        selected, _ = harmonise_cadence(selected, cfg.target_cadence_minutes, policy=cfg.cadence_policy)
        return selected
    return choose


def coarsest_in_transit_cadence_days(times, period, t0, duration):
    """The coarsest native cadence among the cadences inside the transit windows: each in-transit cadence's
    nearest-neighbour gap, snapped to the TESS cadences (120/200/600/1800 s); gaps above 1,900 s are
    segment edges and ignored.  With 1800-s and 200-s products both carrying events this is 1800 s: a
    duration below one 1800-s cadence is not resolved by the data that carry the events."""
    import numpy as np
    t = np.sort(np.asarray(times, float))
    if t.size < 3 or not (period > 0 and duration > 0):
        return 0.0
    d = np.abs(((t - t0 + 0.5 * period) % period) - 0.5 * period)
    inside = np.flatnonzero(d <= max(0.5 * duration, 0.5 * 1800.0 / 86400.0))
    if inside.size == 0:
        return 0.0
    gaps = np.diff(t)
    nn = np.minimum(np.concatenate(([np.inf], gaps)), np.concatenate((gaps, [np.inf])))[inside] * 86400.0
    nn = nn[np.isfinite(nn) & (nn > 0) & (nn <= 1900.0)]
    if nn.size == 0:
        return 0.0
    grid = np.array([120.0, 200.0, 600.0, 1800.0])
    snapped = grid[np.argmin(np.abs(nn[:, None] - grid[None, :]), axis=1)]
    return float(snapped.max()) / 86400.0


def k1_floor(A):
    """TLS duration floor at one cadence of the product(s) carrying the events (B1): the coarsest
    in-transit cadence (``coarsest_in_transit_cadence_days``)."""
    from tesshunter.stage_c import duration_summary
    import numpy as np

    def floor(summary, times):
        if not A.RULES.duration_floor_cadence:
            return summary
        times = np.sort(np.asarray(times, float))
        cad_d = 0.0
        if summary.get("period") and summary.get("T0_btjd") and summary.get("duration_days"):
            cad_d = coarsest_in_transit_cadence_days(times, float(summary["period"]), float(summary["T0_btjd"]),
                                                     float(summary["duration_days"]))
        if not cad_d:
            cad_d = float(np.median(np.diff(times))) if len(times) > 1 else 200.0 / 86400.0
        return duration_summary(summary, cad_d * 86400.0)
    return floor


def setup(rt):
    for path in (REPO / "src", REPO / "scripts", REPO / "p10/protocol"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import p10_funnel_calibration as F
    import audit_p5 as A
    from tesshunter import audit_rules as R, event_vet, star_vet, survey
    from tesshunter.secondary import secondary_scan
    tic = int(rt["tic_id"])
    root = Path(rt["root"])
    root.mkdir(parents=True, exist_ok=True)
    columns = sorted(set(rt["candidate"]) | set(rt["star"]) | {"period_days", "tic_id", "rank"})
    cand = dict(rt["candidate"], **rt["star"], tic_id=tic)
    cand.setdefault("rank", 1)
    for name, rows in (("survivors.csv", [cand]), ("candidates.csv", rt["all_candidates"])):
        path = root / name
        if not path.exists():
            with path.open("x", newline="", encoding="utf-8") as stream:
                w = csv.DictWriter(stream, fieldnames=sorted(set(columns) | {k for r in rows for k in r}),
                                   extrasaction="ignore")
                w.writeheader(); w.writerows(rows)
    lc_root = Path(rt["lc_root"])
    if lc_root.resolve().is_relative_to(TRUTH.resolve()):
        raise RuntimeError("Worker input under k1/truth")
    F.LC_ROOT = lc_root
    F.PACKETS = DATA / "funnel_empty_packets"
    F.PACKETS.mkdir(parents=True, exist_ok=True)
    cache = DATA / "lightkurve_funnel"
    cache.mkdir(parents=True, exist_ok=True)
    A.AUDIT_CACHE = cache
    os.environ["LIGHTKURVE_CACHE"] = str(cache)
    F.set_root(root)
    mode = rt.get("s_mode") or "bound"
    if mode not in S_MODES:
        raise RuntimeError("Unregistered S mode")
    F.V.set_rules(R.P10_RULES.with_options(secondary_gate=mode))
    A.set_input_config(survey.get_config(rt["preset"]))
    A.set_roots(root, lc_root)
    A.choose_per_sector = k1_choose_per_sector(A)
    A._floor_tls_summary = k1_floor(A)
    from tesshunter import k1_rules
    event_vet.SAP_RAMP_NOISE_MULTIPLE = k1_rules.K1_SAP_RAMP_NOISE_MULTIPLE if rt.get("ramp_variant") else None
    event_vet.EVENT_DEPTH_TEMPLATE = k1_rules.K1_EVENT_DEPTH_TEMPLATE      # amendment 2
    star_vet.B_CADENCE_RULE = "per_window"

    def scan(*args, **kwargs):
        kwargs["k1_modes"] = True
        kwargs["p10_modes"] = True
        return secondary_scan(*args, **kwargs)
    F.secondary_scan = scan
    star = rt["star"]
    stellar = {"radius": star["radius_rsun"], "mass": star["mass_msun"], "teff": star["teff_k"],
               "tmag": star["tmag"], "ra": star["ra_deg"], "dec": star["dec_deg"], "logg": star.get("logg")}
    A.stellar_from_cache = lambda requested: stellar if int(requested) == tic else {}
    return F, A, root


def main(stage, runtime_path):
    if stage not in ("A", "S", "B", "C"):
        raise ValueError("Unregistered stage")
    runtime_path = Path(runtime_path)
    rt = read(runtime_path)
    if set(rt) - RUNTIME_FIELDS:
        raise RuntimeError("Unregistered runtime fields")
    if rt["preset"] not in ("survey_k1", "survey_k1_s56"):
        raise RuntimeError("Unregistered preset")
    for k in rt["candidate"]:
        if k.startswith("inj") or k in ("truth", "injection"):
            raise RuntimeError("Truth field in runtime")
    cid, tic, label = rt["candidate_id"], int(rt["tic_id"]), rt["label"]
    dest = RECEIPTS / label / stage / f"{cid}.json"
    if dest.exists():
        raise FileExistsError(dest)
    started, timer, cpu = utc(), time.perf_counter(), time.process_time()
    try:
        F, A, root = setup(rt)
        if stage == "B":
            nb = rt.get("neighbours_path")
            if not nb or not Path(nb).exists():
                raise RuntimeError("neighbour record missing")
            target = root / "neighbours" / f"tic{tic}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            write(target, read(nb), replace=True)
        job = F.V.jobs()[0]
        if stage == "A":
            m = F.V.stagea_one(job, threads=1)
        elif stage == "S":
            m = F.secondary_one(job)
        elif stage == "B":
            m = F.V.stageb_one(job)
        else:
            m = F.V.stagec_one(job, threads=int(rt.get("tls_threads") or 4), oversampling=3)
        decision = m.get("decision", m.get("gate", m.get("status")))
        status = "OPERATIONAL_UNKNOWN" if decision in ("ERROR", "SKIP", "INPUT_ERROR", "TIMEOUT") else "COMPLETE"
        rec = dict(candidate_id=cid, tic_id=tic, stage=stage, status=status, decision=decision, label=label,
                   use=rt.get("use"), preset=rt["preset"], s_mode=rt.get("s_mode"), ramp_variant=bool(rt.get("ramp_variant")),
                   started_utc=started, completed_utc=utc(), wall_seconds=time.perf_counter() - timer,
                   cpu_seconds=time.process_time() - cpu, case_root=str(root), measurement=m)
        if stage == "S":
            sec = m.get("secondary") or {}
            rec["gate_by_mode"] = {"bound": (sec.get("gate_by_mode") or {}).get("bound"),
                                   **(sec.get("gate_by_mode_p10") or {}), **(sec.get("gate_by_mode_k1") or {})}
    except Exception as exc:
        rec = dict(candidate_id=cid, tic_id=tic, stage=stage, status="OPERATIONAL_UNKNOWN", label=label,
                   error=f"{type(exc).__name__}: {exc}"[:500], traceback=traceback.format_exc()[-3000:],
                   started_utc=started, completed_utc=utc(), wall_seconds=time.perf_counter() - timer)
    write(dest, safe(rec))
    print(stage, cid, rec["status"], rec.get("decision"), round(rec["wall_seconds"], 1), flush=True)
    return 0 if rec["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
