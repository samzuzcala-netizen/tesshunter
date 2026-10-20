"""PROTOCOL 8: bounded, faithful replay of the discovery search, pre-gate and Stage A.

Variants (fixed counts, frozen order):
  1. 'inv' : sign-inverted store copies (flux -> 2*median - flux, also sap_flux, per product) of the 3 targets
  2. 'inv' : 24 matched control stars from S1 batch 1 (8 per candidate)
  3. 'inj' : 24 other matched control stars with the candidate's own transit (P, k, b, a/R*, LD) injected into
             flux and sap_flux of every product with the frozen survey_p8.inject_products (random epoch, seeded)
Searches: survey.run_job, preset survey_k1, 8,100 s, record_traces, allow_download=False (s08_worker.py).
Pre-gate: plan_k1.PREGATE (stitch S/N >= 7.1, >= 3 transits, epoch consistent).
Stage A: k2/protocol/funnel_k2.py A, s_mode bound_alias, k2_c_variant V3 (as S1), on every pre-gate candidate of
         an 'inv' star and on 'inj' candidates within 1% of P, P/2 or 2P of the injection.
Budget: 24 CPU-hours (sum of job CPU), 4 concurrent jobs; no extension.  Everything is written under
D:/tess_fu3_cache/replay (K1_DATA = K2_DATA = that root) and FU3 results; nothing under D:/tesshunter_s1.

CLI: s08_replay.py select | build | run | summarize
"""
import hashlib
import shutil
import subprocess
import sys
import time

import pandas as pd

from fu3_common import *

REPLAY = CACHE / "replay"
DATA_ROOT = REPLAY / "data"
STORE = {"inv": REPLAY / "store_inv", "inj": REPLAY / "store_inj"}
STITCH = {"inv": REPLAY / "stitched_inv", "inj": REPLAY / "stitched_inj"}
JOBS = REPLAY / "jobs"
PY = r"C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe"
BUDGET_CPU_S = 24 * 3600.0
WORKERS = 4
SEED = 20261018
SUBMIT_HOLD = {116046773, 116047785, 155913240, 155949537, 159341729, 160603808, 165638563, 18229070, 188580030,
               188830138, 193718989, 201247574, 207432717, 233204110, 245821988, 246940708, 259270670, 262843927,
               270573718, 335745090, 382098683, 423314730, 458513927}


def env():
    e = dict(os.environ)
    e.update(K1_DATA=str(DATA_ROOT), K2_DATA=str(DATA_ROOT), XDG_CACHE_HOME=str(DATA_ROOT / "xdg_cache"),
             TESSHUNTER_OFFLINE="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
             LIGHTKURVE_CACHE=str(DATA_ROOT / "lightkurve_funnel"))
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS"):
        e[k] = "1"
    return e


def seed_of(*parts):
    return int(hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()[:16], 16)


# ---------------------------------------------------------------------------------------------------------
def select():
    tg = pd.read_csv(REPO / "s1" / "survey" / "targets_s1.csv", low_memory=False)
    b1 = tg[((tg.slice == "eM_slice") & (tg["rank"] <= 1500)) | ((tg.slice == "K") & (tg["rank"] <= 500))].copy()
    searched = {int(p.stem.split("_")[1]) for p in (S1 / "runs" / "s1_b1" / "receipts").glob("s1_*.json")}
    b1 = b1[b1.tic_id.isin(searched) & ~b1.tic_id.isin(SUBMIT_HOLD)]
    out = {}
    used = set()
    for tic in TICS:
        r = tg[tg.tic_id == tic].iloc[0]
        m = b1[(b1.slice == r.slice) & (abs(b1.Tmag - r.Tmag) <= 0.5)
               & (b1.n_usable >= 0.7 * r.n_usable) & (b1.n_usable <= 1.3 * r.n_usable) & ~b1.tic_id.isin(used)]
        rng = np.random.default_rng(seed_of(SEED, "controls", tic))
        pick = list(rng.permutation(m.tic_id.astype(int).tolist()))
        inv, inj = pick[:8], pick[8:16]
        used |= set(inv) | set(inj)
        out[str(tic)] = dict(n_matches=int(len(m)), target_tmag=float(r.Tmag), target_n_usable=int(r.n_usable),
                             slice=r.slice, inv_controls=[int(x) for x in inv], inj_controls=[int(x) for x in inj],
                             criteria="S1 batch 1 searched, same slice, |dTmag| <= 0.5, n_usable within +/-30%, "
                                      "not SUBMIT/HOLD, seeded permutation (seed sha256('20261018:controls:<tic>'))")
        log("s08", f"{tic}: {len(m)} matches; inv {len(inv)} inj {len(inj)}")
    save(RES / "s08_controls.json", out)
    return out


def star_block(tic):
    tg = pd.read_csv(REPO / "s1" / "survey" / "targets_s1.csv", low_memory=False)
    r = tg[tg.tic_id == tic].iloc[0]
    return {"radius_rsun": float(r.rad), "mass_msun": float(r.mass), "teff_k": float(r.Teff), "tmag": float(r.Tmag),
            "ra_deg": float(r.ra), "dec_deg": float(r.dec), "logg": float(r.logg)}


def build():
    """Write replay store copies (inverted / injected).  Runs in a child with the replay env so the frozen
    survey_p8 injection code is imported under K1_DATA = replay root."""
    ctrl = read(RES / "s08_controls.json")
    plan = []
    for tic in TICS:
        plan.append(dict(variant="inv", tic=tic, job_id=f"fu3inv_{tic}", candidate=tic))
    for tic in TICS:
        for c in ctrl[str(tic)]["inv_controls"]:
            plan.append(dict(variant="inv", tic=c, job_id=f"fu3inv_{c}", candidate=tic))
    for tic in TICS:
        for k, c in enumerate(ctrl[str(tic)]["inj_controls"]):
            plan.append(dict(variant="inj", tic=c, job_id=f"fu3inj_{c}_{tic}", candidate=tic, k=k))
    JOBS.mkdir(parents=True, exist_ok=True)
    save(JOBS / "plan.json", plan)
    code = CODE / "s08_build_child.py"
    r = subprocess.run([PY, "-W", "ignore", str(code)], env=env(), capture_output=True, text=True, timeout=7200)
    log("s08", "build child: " + r.stdout[-2000:] + r.stderr[-2000:])
    return plan


# ---------------------------------------------------------------------------------------------------------
def a_runtime(cand_row, search_job, label):
    cid = cand_row["candidate_id"]
    root = DATA_ROOT / "funnel" / label / cid
    cand = {k: v for k, v in cand_row.items() if k not in ("job_id", "candidate_id", "passes_pregate")}
    return {"candidate_id": cid, "tic_id": int(cand_row["tic_id"]), "candidate": cand,
            "all_candidates": search_job["_all_candidates"], "star": search_job["star"],
            "lc_root": search_job["lc_root"], "root": str(root), "preset": "survey_k1", "s_mode": "bound_alias",
            "ramp_variant": False, "label": label, "use": "fu3_replay", "tls_threads": 1,
            "neighbours_path": None, "k2_c_variant": "V3", "k2_siblings": [], "k2_a1_scope": None,
            "k2_copy_from": str(root)}


CAND_COLS = ["period_days", "epoch_btjd", "duration_days", "depth_ppt", "snr", "stitch_snr", "stitch_n_transits",
             "stitch_epoch_consistent", "stitch_period_days", "stitch_depth_ppt", "search", "planet_num"]


def candidates_of(result_path, job):
    d = read(result_path)
    rows = []
    if d.get("status") != "ok" or not d.get("result"):
        return rows
    st = job["star"]
    for q in d["result"].get("planets") or []:
        row = {"candidate_id": f"{job['job_id']}_p{int(q['planet_num']):02d}", "job_id": job["job_id"],
               "tic_id": int(job["tic_id"]), **{k: q.get(k) for k in CAND_COLS},
               "n_transits": q.get("n_transits_observed"), "n_units": d.get("n_units"),
               "tmag": st.get("tmag"), "teff_k": st.get("teff_k"), "radius_rsun": st.get("radius_rsun"),
               "mass_msun": st.get("mass_msun"), "ra_deg": st.get("ra_deg"), "dec_deg": st.get("dec_deg")}
        row["passes_pregate"] = bool((q.get("stitch_snr") or 0) >= 7.1 and int(q.get("stitch_n_transits") or 0) >= 3
                                     and bool(q.get("stitch_epoch_consistent")))
        rows.append(row)
    return rows


def matches_injection(row, P):
    p = row.get("period_days") or 0
    return any(abs(p / (P * f) - 1) < 0.01 for f in (1.0, 0.5, 2.0))


def run():
    plan = read(JOBS / "plan.json")
    state_path = REPLAY / "state.json"
    state = read(state_path) if state_path.exists() else dict(cpu_s=0.0, done={}, a_done={}, a_queue=[])
    queue = [p for p in plan if p["job_id"] not in state["done"]]
    running = {}
    budget_hit = False

    def launch(kind, payload):
        if kind == "search":
            jp = JOBS / f"{payload['job_id']}.json"
            save(jp, payload)
            args = [PY, "-W", "ignore", str(CODE / "s08_worker.py"), str(jp)]
        else:
            rp = JOBS / "A" / f"{payload['candidate_id']}.json"
            save(rp, payload)
            args = [PY, "-W", "ignore", str(REPO / "k2" / "protocol" / "funnel_k2.py"), "A", str(rp)]
        lf = open(LOGS / f"replay_{kind}_{payload.get('job_id', payload.get('candidate_id'))}.log", "w", encoding="utf-8")
        # normal priority: BELOW_NORMAL was starved to ~0 CPU next to the live survey (2026-10-18 21:31-22:08 UTC
        # first launch; 0-2 CPU-s in 35 min; killed and relaunched, no result was produced by that launch)
        pr = subprocess.Popen(args, env=env(), stdout=lf, stderr=subprocess.STDOUT, cwd=str(REPO / "k2" / "protocol"))
        return dict(proc=pr, kind=kind, payload=payload, t0=time.time(), log=lf)

    while queue or running or state["a_queue"]:
        # launch
        while len(running) < WORKERS and not budget_hit:
            if state["cpu_s"] >= BUDGET_CPU_S:
                budget_hit = True
                log("s08", f"BUDGET reached: {state['cpu_s']/3600:.2f} CPU-h; no new launches")
                break
            if state["a_queue"]:
                rt = state["a_queue"].pop(0)
                running[rt["candidate_id"]] = launch("A", rt)
            elif queue:
                p = queue.pop(0)
                job = dict(job_id=p["job_id"], tic_id=p["tic"], star=star_block(p["tic"]),
                           lc_root=str(STORE[p["variant"]] / p["job_id"]), cache_dir=str(STITCH[p["variant"]] / p["job_id"]),
                           out_dir=str(REPLAY / "runs"), variant=p["variant"], candidate=p["candidate"])
                running[p["job_id"]] = launch("search", job)
            else:
                break
        time.sleep(15)
        for key in list(running):
            r = running[key]
            rc = r["proc"].poll()
            if rc is None:
                if time.time() - r["t0"] > 4 * 3600:       # hard per-job deadline
                    r["proc"].kill()
                    rc = "TIMEOUT"
                else:
                    continue
            r["log"].close()
            del running[key]
            if r["kind"] == "search":
                job = r["payload"]
                rec_p = REPLAY / "runs" / "receipts" / f"{job['job_id']}.json"
                rec = read(rec_p) if rec_p.exists() else dict(status=f"NO_RECEIPT rc={rc}", cpu_seconds=time.time() - r["t0"])
                state["cpu_s"] += float(rec.get("cpu_seconds") or 0)
                cands = candidates_of(REPLAY / "runs" / "results" / f"{job['job_id']}.json", job) if rec_p.exists() else []
                job["_all_candidates"] = [{k: v for k, v in c.items() if k not in ("job_id", "candidate_id", "passes_pregate")} for c in cands]
                plan_row = next(p for p in plan if p["job_id"] == job["job_id"])
                inj = read(STORE["inj"] / job["job_id"] / "injection_truth.json") if job["variant"] == "inj" else None
                n_q = 0
                for c in cands:
                    if not c["passes_pregate"]:
                        continue
                    if job["variant"] == "inj" and not matches_injection(c, inj["period"]):
                        continue
                    state["a_queue"].append(a_runtime(c, job, f"fu3{job['variant']}"))
                    n_q += 1
                state["done"][job["job_id"]] = dict(status=rec.get("status"), cpu_s=rec.get("cpu_seconds"),
                                                    n_accepted=len(cands), n_pregate=sum(c["passes_pregate"] for c in cands),
                                                    n_A_queued=n_q, variant=job["variant"], candidate=plan_row["candidate"])
                save(RES / f"s08_candidates_{job['job_id']}.json", cands)
                log("s08", f"search {job['job_id']} {rec.get('status')} cpu {float(rec.get('cpu_seconds') or 0):.0f}s "
                           f"accepted {len(cands)} pregate {sum(c['passes_pregate'] for c in cands)} A queued {n_q}; "
                           f"total {state['cpu_s']/3600:.2f} CPU-h")
            else:
                rt = r["payload"]
                rp = DATA_ROOT / "funnel_receipts" / rt["label"] / "A" / f"{rt['candidate_id']}.json"
                rec = read(rp) if rp.exists() else dict(status=f"NO_RECEIPT rc={rc}", cpu_seconds=time.time() - r["t0"])
                state["cpu_s"] += float(rec.get("cpu_seconds") or 0)
                state["a_done"][rt["candidate_id"]] = dict(status=rec.get("status"), decision=rec.get("decision"),
                                                           cpu_s=rec.get("cpu_seconds"))
                log("s08", f"A {rt['candidate_id']} {rec.get('status')} {rec.get('decision')}; total {state['cpu_s']/3600:.2f} CPU-h")
            save(state_path, state)
        if budget_hit and not running:
            break
    state["finished_utc"] = utc()
    state["budget_hit"] = budget_hit
    state["not_run"] = [p["job_id"] for p in queue]
    state["a_not_run"] = [x["candidate_id"] for x in state["a_queue"]]
    save(state_path, state)
    log("s08", f"replay finished: {len(state['done'])} searches, {len(state['a_done'])} A jobs, "
               f"{state['cpu_s']/3600:.2f} CPU-h, budget_hit {budget_hit}")


if __name__ == "__main__":
    {"select": select, "build": build, "run": run}[sys.argv[1]]()
