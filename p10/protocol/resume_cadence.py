"""Prompt 10: finish the registered 37-record cadence comparison after Claude's queue.

Never starts a second TLS job, changes source, reuses an ERROR as completion, or
reruns a settled record. Stops before injection-C sampling and scientific adoption.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import time
import psutil

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data/survey/p10/stage_c"
RECEIPTS = REPO / "p10/results/takeover_20260908"
PY = Path(r"C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe")
ORIGINAL_QUEUE_PID = 7844
ORIGINAL_KEYS = [
    ("p9", "tic284441182_P18.0890"),
    ("p8", "tic100273626_P10.3806"),
    ("p8", "tic237917568_P18.7059"),
    ("p8", "tic237921294_P18.3141"),
    ("p8", "tic309025900_P14.9235"),
    ("p8", "tic388200613_P20.8357"),
    ("p8", "tic394680557_P29.9904"),
]

def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))

def write(p, data):
    p = Path(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
    tmp.replace(p)

def utc():
    return datetime.now(timezone.utc).isoformat()

def assert_source():
    for r in read(RECEIPTS / "inherited_source_hashes.json"):
        if r["path"].startswith(("src/", "scripts/", "configs/")) or r["path"] in ("pyproject.toml","requirements.txt","PROMPT_P10.md"):
            if hashlib.sha256((REPO/r["path"]).read_bytes()).hexdigest() != r["sha256"]:
                raise RuntimeError("Inherited source changed: "+r["path"])

def tls_owners():
    result = []
    for proc in psutil.process_iter():
        try:
            name = proc.name().lower()
            if not (name.startswith("python") or name.startswith("bash")):
                continue
            cmd = proc.cmdline()
            if not cmd:
                raise RuntimeError(f"Cannot inspect command line for {name} PID {proc.pid}")
            command = " ".join(cmd)
            if "p10_stage_c.py" in command or "stage_c_queue1.sh" in command:
                result.append({"pid":proc.pid,"ppid":proc.ppid(),"command":command})
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            raise RuntimeError(f"Process visibility insufficient for PID {proc.pid}") from exc
    return result

def complete(set_name, tag, key):
    ws = OUT / set_name / tag / key
    record = ws/"stageC"/(key+".json")
    if not record.exists():
        return False
    r = read(record)
    if r.get("decision") not in ("PASS","FAIL"):
        raise RuntimeError(f"Unsettled C record {record}: {r.get('decision')}")
    for suffix in (".json", "_spectrum.npz", "_lc.npz"):
        if not (ws/"tls"/(key+suffix)).is_file():
            raise RuntimeError(f"Missing TLS artifact {key+suffix}")
    if not r.get("p10",{}).get("wall_s",0) > 0:
        raise RuntimeError("Missing measured wall: "+str(record))
    return True

def manifest():
    rows = []
    for set_name, records in (
        ("p8", sorted((REPO/"data/survey/p8/stageC").glob("tic*.json"))),
        ("p9", [p for tic in read(REPO/"p9/manifests/final_ids.json")
                for p in sorted((REPO/"p9/results/blind"/f"tic{tic}"/"stageC").glob("tic*.json"))]),
    ):
        for p in records:
            r = read(p)
            rows.append({"set":set_name,"key":r["key"],"native_decision":r["decision"],
                         "native_record":str(p.relative_to(REPO)),
                         "native_sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    if len(rows) != 37 or len({(r["set"],r["key"]) for r in rows}) != 37:
        raise RuntimeError("The prescribed 37-record census does not match.")
    return rows

def main():
    os.chdir(REPO)
    os.environ.update(LIGHTKURVE_CACHE=str(REPO/"data/cache/lightkurve"),PYTHONIOENCODING="utf-8",
                      TESSHUNTER_OFFLINE="1",PYTHONDONTWRITEBYTECODE="1",
                      OMP_NUM_THREADS="1",MKL_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1")
    rows = manifest()
    pilot = read(REPO/"p10/results/stage_c_cadence.json")
    # Use the three preserved pilot timings, not the growing live table.
    original_pilot = subprocess.check_output(
        ["git","show","656b838:p10/results/stage_c_cadence.json"],cwd=REPO)
    pilot = json.loads(original_pilot)
    walls = sorted(float(r["wall_s"]) for r in pilot["rows"])
    if len(walls) != 3:
        raise RuntimeError("Expected the preserved three-record pilot.")
    projected_h = walls[1]*37/3/3600
    if projected_h > 12:
        raise RuntimeError("Projection calls for seeded 12; this all-37 queue is not applicable.")
    state = {"utc":utc(),"pid":os.getpid(),"status":"waiting_for_original_queue",
             "threads":8,"n_total":37,"pilot_projection_hours":projected_h,
             "rule":"35/37 agreement and every disagreement explained; no decision before completion",
             "rows":rows}
    receipt = RECEIPTS/"cadence_queue.json"
    lock = RECEIPTS/"cadence_queue.lock"
    try:
        with lock.open("x") as fh:
            fh.write(json.dumps({"pid":os.getpid(),"created":psutil.Process().create_time()}))
    except FileExistsError:
        raise RuntimeError("Cadence queue lock already exists; inspect its owner before resuming.")
    write(receipt,state)
    print(utc(), "queued all-37 cadence comparison after the existing TLS queue", flush=True)
    try:
        while tls_owners():
            time.sleep(20)
        assert_source()
        for set_name,key in ORIGINAL_KEYS:
            if not complete(set_name,"p10c_native",key):
                raise RuntimeError("Original residual queue incomplete: "+key)
        for row in rows:
            set_name,key = row["set"],row["key"]
            if complete(set_name,"cadence_600s",key):
                print(utc(),"reuse",key,flush=True)
                continue
            assert_source()
            owners = tls_owners()
            if owners:
                raise RuntimeError("Unexpected TLS owner: "+str(owners))
            state.update(utc=utc(),status="running",active=row)
            write(receipt,state)
            command = [str(PY),"scripts/p10_stage_c.py","cadence","--threads","8","--keys",key]
            print(utc(),"start",key,flush=True)
            log = REPO/"p10/logs"/("cadence_600s_"+key+".log")
            with log.open("a",encoding="utf-8") as fh:
                fh.write("\n=== "+utc()+" "+" ".join(command)+"\n"); fh.flush()
                code = subprocess.run(command,cwd=REPO,stdout=fh,stderr=subprocess.STDOUT).returncode
            if code or tls_owners() or not complete(set_name,"cadence_600s",key):
                raise RuntimeError("Cadence execution incomplete: "+key)
            print(utc(),"complete",key,flush=True)
        state.update(utc=utc(),status="measurements_complete_review_required",active=None)
        write(receipt,state)
        print(utc(),"CADENCE_37_COMPLETE=1; explain disagreements before choosing injection cadence.",flush=True)
    except BaseException as exc:
        state.update(utc=utc(),status="needs_review",error=str(exc))
        write(receipt,state)
        raise
    finally:
        lock.unlink(missing_ok=True)

if __name__ == "__main__":
    main()

