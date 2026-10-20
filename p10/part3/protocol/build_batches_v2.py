"""Build the version-2 acquisition job manifests (amendments D3 and D4).

    python p10/part3/protocol/build_batches_v2.py plan     # batches of 100 over every star without an index
    python p10/part3/protocol/build_batches_v2.py retry    # one recorded retry pass over transport-class failures

``plan`` orders the remaining stars by ascending TIC identity (as the pilot did), never by
TCE content, and gives a star whose pilot attempt failed the attempt number 2 so the
accounting is honest across versions. ``retry`` collects, from every closed version-2
batch, the attempts that ended TIMEOUT or OPERATIONAL_UNKNOWN with a transport-class
error, plus completed stars whose index records product-level failures (re-run with
``--force``), and emits one manifest at attempt+1, capped at two attempts per star. A star
that exhausts its attempts is ``INPUT_INELIGIBLE(acquisition)`` in the eligibility step,
never a miss. Nothing scientific is read here.

Written by the user's Claude session on 2026-09-14 while no controller was alive.
"""
from common import REPO, ROOT, read, write, sha, utc
import csv
import re
import sys

BATCH = 100
MAX_ATTEMPTS = 2
WORKER = "p10/part3/protocol/download_star_v2.py"
TRANSPORT = re.compile(r"HTTPError|ConnectionError|Timeout|RemoteDisconnected|IncompleteRead|ChunkedEncoding|"
                       r"ProtocolError|URLError|socket|Max retries|Bad Gateway|Service Unavailable|Gateway Time-out|"
                       r"Connection aborted|Connection reset|Name or service not known|getaddrinfo", re.I)


def transport_class(status, error):
    """True when the failure is a transport or deadline event rather than a data or code error."""
    if status == "TIMEOUT":
        return True
    if error is None or error == "":
        return True
    return bool(TRANSPORT.search(str(error)))


def index_exists(tic):
    return (REPO / f"data/survey/audit_lc/tic{tic}/index.json").exists()


def pilot_failures():
    out = {}
    for path in (ROOT / "results/controllers/download_pilot/attempts").glob("*.json"):
        record = read(path)
        if record["status"] != "COMPLETE":
            out[int(record["job_id"][3:])] = record["status"]
    return out


def job(tic, attempt, force=False):
    arguments = [WORKER, str(tic), str(attempt)] + (["--force"] if force else [])
    return dict(job_id=f"tic{tic}", arguments=arguments, attempt=attempt, force=force,
                result_path=f"p10/part3/results/download_v2/tic{tic}_a{attempt}.json")


def refuse_if_owner():
    if (ROOT / "manifests/controller_owner.json").exists():
        raise RuntimeError("A controller owner exists; build manifests only between phases")


def plan():
    refuse_if_owner()
    targets = list(csv.DictReader((ROOT / "manifests/targets_after_a.csv").open()))
    failed = pilot_failures()
    remaining = sorted(int(r["tic_id"]) for r in targets if not index_exists(int(r["tic_id"])))
    jobs = [job(t, 2 if t in failed else 1) for t in remaining]
    batches = [jobs[i:i + BATCH] for i in range(0, len(jobs), BATCH)]
    names = []
    for k, chunk in enumerate(batches, 1):
        name = f"p10/part3/manifests/download_v2_batch_{k:02d}.json"
        write(REPO / name, chunk)
        names.append(name)
    summary = dict(utc=utc(), eligible_after_a=len(targets), already_indexed=len(targets) - len(remaining),
                   remaining=len(remaining), pilot_failures_at_attempt_2=sorted(failed), batch_size=BATCH,
                   batches=names, order="ascending TIC identity; no TCE content used",
                   worker=WORKER, worker_sha256=sha(REPO / WORKER), builder_sha256=sha(__file__),
                   amendment="D3-D4, p10/part3/AMENDMENTS_D1_D4_20260914.md")
    write(ROOT / "manifests/download_v2_plan.json", summary)
    print(summary, flush=True)


def retry():
    refuse_if_owner()
    attempts = {}
    for path in (ROOT / "results/controllers").glob("download_v2_batch_*/attempts/*.json"):
        record = read(path)
        tic = int(record["job_id"][3:])
        attempts.setdefault(tic, []).append(record)
    pilot = pilot_failures()
    jobs, skipped = [], []
    for tic, records in sorted(attempts.items()):
        last = max(records, key=lambda r: r["completed_utc"])
        n_prior = len(records) + (1 if tic in pilot else 0)
        receipt = REPO / last["result_path"] if last.get("result_path") else None
        result = read(receipt) if receipt and receipt.exists() else {}
        error = result.get("error")
        if last["status"] == "COMPLETE" and result.get("ok") and not result.get("n_failed"):
            continue
        if last["status"] == "COMPLETE" and result.get("ok") and result.get("n_failed"):
            reason, force = "product_level_failures", True
        elif transport_class(last["status"], error):
            reason, force = "transport_or_deadline", False
        else:
            skipped.append(dict(tic_id=tic, status=last["status"], error=error, reason="non_transport_error"))
            continue
        if n_prior >= MAX_ATTEMPTS:
            skipped.append(dict(tic_id=tic, status=last["status"], error=error, reason="attempts_exhausted"))
            continue
        jobs.append(dict(job(tic, n_prior + 1, force), reason=reason))
    name = "p10/part3/manifests/download_v2_retry.json"
    write(REPO / name, jobs)
    summary = dict(utc=utc(), retry_jobs=len(jobs), skipped=skipped, manifest=name, max_attempts=MAX_ATTEMPTS,
                   worker_sha256=sha(REPO / WORKER), builder_sha256=sha(__file__),
                   amendment="D3, p10/part3/AMENDMENTS_D1_D4_20260914.md")
    write(ROOT / "manifests/download_v2_retry_plan.json", summary)
    print(summary, flush=True)


if __name__ == "__main__":
    {"plan": plan, "retry": retry}[sys.argv[1]]()
