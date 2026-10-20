"""After complete a/b/c searches, execute only the preregistered fourth variant.

e iff R_7_15(b) > R_7_15(c), else d. No final variant adoption. Refuses
incomplete a/b/c or an unexplained partial fourth run. Retains 16 workers.
"""
from pathlib import Path
from fractions import Fraction
import csv
import os
import subprocess
import sys
import time
import psutil
import resume_cadence as Q

RUNS = Q.REPO/"data/survey/runs/p10_2b"


def owners():
    found = []
    for proc in psutil.process_iter():
        try:
            if not proc.name().lower().startswith(("python", "pwsh", "powershell", "bash")):
                continue
            args = proc.cmdline()
            if not args:
                raise RuntimeError("Cannot inspect command line for PID "+str(proc.pid))
            command = " ".join(args)
            if any(marker in command for marker in ("p10_search_capacity.py", "run_survey.py", "survey_worker.py", "resume_search_abc.ps1")):
                if not any(a in ("-Command", "-command", "-c") for a in args):
                    found.append({"pid":proc.pid,"ppid":proc.ppid(),"command":command})
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            raise RuntimeError("Process visibility insufficient for PID "+str(proc.pid)) from exc
    return found


def expected(kind):
    file = Q.REPO/("data/survey/p10/injections_2b.csv" if kind=="inj" else "data/survey/completeness_sample_p8.csv")
    rows = list(csv.DictReader(file.open(encoding="utf-8")))
    ids = [r["job_id"] if kind=="inj" else "tic"+r["tic_id"] for r in rows]
    if len(ids) != (600 if kind=="inj" else 300) or len(set(ids))!=len(ids):
        raise RuntimeError("Unexpected paired sample size")
    return ids


def complete(variant,kind):
    result_dir = RUNS/(variant+"_"+kind)/"results"
    ids = expected(kind)
    if {p.stem for p in result_dir.glob("*.json")} != set(ids):
        raise RuntimeError("Incomplete or extra results in "+str(result_dir))
    rows = [Q.read(result_dir/(key+".json")) for key in ids]
    if any(r.get("status")!="ok" or not r.get("result") or r.get("job_id")!=key for r,key in zip(rows,ids)):
        raise RuntimeError("Unsettled result in "+str(result_dir))
    return rows


def main():
    os.chdir(Q.REPO)
    os.environ.update(LIGHTKURVE_CACHE=str(Q.REPO/"data/cache/lightkurve"),PYTHONIOENCODING="utf-8",
                      TESSHUNTER_OFFLINE="1",PYTHONDONTWRITEBYTECODE="1",
                      OMP_NUM_THREADS="1",MKL_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1")
    lock = Q.RECEIPTS/"fourth_variant_queue.lock"
    receipt = Q.RECEIPTS/"fourth_variant_queue.json"
    with lock.open("x") as fh:
        fh.write(Q.json.dumps({"pid":os.getpid(),"created":psutil.Process().create_time()}))
    state = {"utc":Q.utc(),"pid":os.getpid(),"status":"waiting_for_complete_abc","workers":16}
    Q.write(receipt,state)
    print(Q.utc(),"queued fourth-variant choice after complete a/b/c; no adoption",flush=True)
    try:
        while owners():
            time.sleep(20)
        Q.assert_source()
        data = {(v,k):complete(v,k) for v in "abc" for k in ("inj","fa")}
        sys.path.insert(0,str(Q.REPO/"scripts"))
        from analyze_completeness import classify
        snr = {r["job_id"]:float(r["snr_expected"]) for r in csv.DictReader((Q.REPO/"data/survey/p8/injection_outcomes_p8.csv").open(encoding="utf-8"))}
        counts = {}
        for variant in "bc":
            rows = [r for r in data[variant,"inj"] if 7<=snr[r["job_id"]]<15]
            counts[variant] = {"n":len(rows),"recovered":sum(classify(r)["status"]=="recovered" for r in rows)}
        if counts["b"]["n"]!=counts["c"]["n"] or not counts["b"]["n"]:
            raise RuntimeError("Unpaired R_7_15 denominators")
        selected = "e" if Fraction(counts["b"]["recovered"],counts["b"]["n"])>Fraction(counts["c"]["recovered"],counts["c"]["n"]) else "d"
        state.update(utc=Q.utc(),status="fourth_selected",counts=counts,selected=selected,
                     rule="e iff R_7_15(b)>R_7_15(c), else d; no final adoption")
        Q.write(receipt,state)
        print(Q.utc(),"fourth",selected,counts,flush=True)
        for kind in ("inj","fa"):
            Q.assert_source()
            if owners():
                raise RuntimeError("Unexpected live search owner")
            phase_root = RUNS/(selected+"_"+kind)
            if phase_root.exists():
                complete(selected,kind)  # A partial previous run requires separate takeover/archive.
                print(Q.utc(),"reuse complete",selected,kind,flush=True)
                continue
            command = [str(Q.PY),"scripts/p10_search_capacity.py","run","--variants",selected,"--kinds",kind,"--workers","16"]
            state.update(utc=Q.utc(),status="running",kind=kind,command=command)
            Q.write(receipt,state)
            log = Q.REPO/"p10/logs"/("takeover_fourth_"+selected+"_"+kind+".log")
            with log.open("a",encoding="utf-8") as fh:
                code = subprocess.run(command,cwd=Q.REPO,stdout=fh,stderr=subprocess.STDOUT).returncode
            if code or owners():
                raise RuntimeError("Fourth instrument failed or left an owner")
            complete(selected,kind)
            print(Q.utc(),"complete",selected,kind,flush=True)
        state.update(utc=Q.utc(),status="search_measurements_complete_review_required",kind=None)
        Q.write(receipt,state)
        print(Q.utc(),"FOUR_VARIANT_SEARCHES_COMPLETE=1; full metrics, FA_S, ranking, adoption still required",flush=True)
    except BaseException as exc:
        state.update(utc=Q.utc(),status="needs_review",error=str(exc))
        Q.write(receipt,state)
        raise
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
