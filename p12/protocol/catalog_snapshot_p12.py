"""Six-source P12 snapshot, isolated 600-second source attempts and one retry.

CLI: snapshot (default), or --source NAME --attempt {1,2} for the internal
bounded worker. The owner records and closes every source subprocess tree.
Worst-case network budget is 6 * 2 * 600 seconds, plus local file operations.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psutil

from p12_common import REPO, ROOT, DATA, PY, environment, read, write, sha, utc

SOURCE_NAMES = ("toi", "ctoi", "nasa_ps", "nasa_pscomppars", "tess_eb", "spoc_tce")
DEADLINE_S = 600
MAX_ATTEMPTS = 2
WORST_CASE_NETWORK_S = len(SOURCE_NAMES) * MAX_ATTEMPTS * DEADLINE_S


def _catalog_module():
    sys.path.insert(0, str(REPO / "src"))
    from tesshunter import catalog_crossmatch
    catalog_crossmatch.CATALOG_CACHE_DIR = DATA / "catalogs"
    return catalog_crossmatch


def _hash_tree(root):
    return {p.relative_to(REPO).as_posix(): sha(p) for p in sorted(Path(root).rglob("*")) if p.is_file()}


def _attempt_root(source, attempt):
    return DATA / "catalogs/.attempts" / f"{source}_a{attempt}"


def _worker_receipt(source, attempt):
    return ROOT / "results/catalog_snapshot" / f"{source}_a{attempt}.json"


def _identity(process):
    return dict(pid=process.pid, create_time=process.create_time(), command=process.cmdline())


def _still_owned(row):
    try:
        process = psutil.Process(row["pid"])
        return process if (process.create_time() == row["create_time"] and
                           process.cmdline() == row["command"]) else None
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def _close_tree(identities):
    # Descendants are captured before stopping, then stopped deepest-first.
    processes = []
    for row in reversed(identities):
        process = _still_owned(row)
        if process is not None:
            try:
                process.terminate()
                processes.append(process)
            except psutil.NoSuchProcess:
                pass
    _, alive = psutil.wait_procs(processes, timeout=5)
    for process in alive:
        row = next(r for r in identities if r["pid"] == process.pid)
        if _still_owned(row) is not None:
            process.kill()
    psutil.wait_procs(alive, timeout=5)
    if any(_still_owned(row) is not None for row in identities):
        raise RuntimeError("STOP-5: catalogue attempt process identity remains alive")


def _run_source_attempt(source, attempt):
    started = time.perf_counter()
    start_utc = utc()
    command = [str(PY), str(Path(__file__).resolve()), "--source", source, "--attempt", str(attempt)]
    logfile = ROOT / "logs/catalog_snapshot" / f"{source}_a{attempt}.log"
    logfile.parent.mkdir(parents=True, exist_ok=True)
    identities = []
    sampled_cpu = 0.
    with logfile.open("x", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=REPO, env=environment(offline=False),
            stdout=stream, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        root = psutil.Process(process.pid)
        identities.append(_identity(root))
        status = "OPERATIONAL_UNKNOWN"
        while True:
            owned = _still_owned(identities[0])
            if owned is not None:
                try:
                    for child in owned.children(recursive=True):
                        ident = _identity(child)
                        if ident not in identities:
                            identities.append(ident)
                    sampled_cpu = max(sampled_cpu, sum(
                        sum(proc.cpu_times()[:2]) for row in identities if (proc := _still_owned(row)) is not None))
                except psutil.NoSuchProcess:
                    pass
            if process.poll() is not None:
                status = "COMPLETE" if process.returncode == 0 else "OPERATIONAL_UNKNOWN"
                break
            if time.perf_counter() - started >= DEADLINE_S:
                status = "TIMEOUT"
                break
            time.sleep(.1)
        _close_tree(identities)
        process.wait(timeout=5)
    path = _worker_receipt(source, attempt)
    if status == "COMPLETE" and not path.exists():
        status = "OPERATIONAL_UNKNOWN"
    receipt = dict(source=source, attempt=attempt, status=status, deadline_s=DEADLINE_S,
        started_utc=start_utc, finished_utc=utc(), wall_seconds=time.perf_counter() - started,
        sampled_cpu_seconds=sampled_cpu, identity=identities[0], process_tree=identities,
        all_owned_workers_closed=True, exit_code=process.returncode,
        result_path=path.relative_to(REPO).as_posix(), result_sha256=sha(path) if path.exists() else None,
        log_path=logfile.relative_to(REPO).as_posix())
    write(ROOT / "manifests/catalog_attempts" / f"{source}_a{attempt}.json", receipt)
    return receipt


def _source_worker(source, attempt):
    environment(offline=False)
    cx = _catalog_module()
    destination = _attempt_root(source, attempt)
    if destination.exists():
        raise FileExistsError(destination)
    cx.CATALOG_CACHE_DIR = destination
    catalog = cx.KnownObjectCatalog.load(sources=[source], refresh=True, allow_stale=False, offline=False)
    receipt = dict(utc=utc(), source=source, attempt=attempt, catalog=catalog.manifest(),
        destination=destination.relative_to(REPO).as_posix(), hashes=_hash_tree(destination))
    write(_worker_receipt(source, attempt), receipt)
    return receipt


def _copy_source(source, origin, *, fallback=False):
    destination = DATA / "catalogs" / source
    if destination.exists():
        raise FileExistsError(destination)
    meta = origin / f"{source}.meta.json"
    normalized = origin / f"{source}.normalized.csv"
    if not meta.is_file() or not normalized.is_file():
        raise RuntimeError(f"Catalogue source incomplete: {source}")
    version = read(meta)
    if fallback and not str(version.get("fetched_utc", "")).startswith("2026-09-04"):
        raise RuntimeError(f"Historical fallback for {source} is not the pinned 2026-09-04 snapshot")
    if sha(normalized) != version["normalized_sha256"]:
        raise RuntimeError(f"STOP-1: normalized source hash mismatch: {source}")
    # Historical ephemerides are not part of a source download and must not
    # become a pre-existing P12 sidecar. All scientific raw/source bytes copy.
    shutil.copytree(origin, destination, ignore=shutil.ignore_patterns("*ephemerides*"))
    return dict(source=source, fallback=fallback,
        source_path=origin.relative_to(REPO).as_posix(), destination=destination.relative_to(REPO).as_posix(),
        fetched_utc=version["fetched_utc"], hashes=_hash_tree(destination))


def snapshot() -> dict:
    environment(offline=False)
    cx = _catalog_module()
    historical = REPO / "data/cache/catalogs"
    before = _hash_tree(historical)
    write(ROOT / "manifests/catalog_hashes_before.json", before)
    attempts, selected = [], []
    try:
        for source in SOURCE_NAMES:
            success = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                result = _run_source_attempt(source, attempt)
                attempts.append(result)
                if result["status"] == "COMPLETE":
                    success = _attempt_root(source, attempt) / source
                    break
            selected.append(_copy_source(source, success or historical / source, fallback=success is None))
        cx.CATALOG_CACHE_DIR = DATA / "catalogs"
        catalog = cx.KnownObjectCatalog.load(sources=SOURCE_NAMES, refresh=False, allow_stale=True, offline=True)
        result = catalog.manifest()
        for version in result["sources"].values():
            version.pop("files", None)
        result.update(p12_sources=selected, attempts=attempts,
            fallback_sources=[row["source"] for row in selected if row["fallback"]],
            per_source_deadline_s=DEADLINE_S, max_attempts=MAX_ATTEMPTS,
            worst_case_network_seconds=WORST_CASE_NETWORK_S,
            source_sha256=sha(__file__))
    finally:
        after = _hash_tree(historical)
        write(ROOT / "manifests/catalog_hashes_after.json", after)
        if before != after:
            raise RuntimeError("STOP-1: historical catalogue cache changed during snapshot")
    result["historical_catalogue_hashes_unchanged"] = True
    write(ROOT / "manifests/catalog_versions_p12.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=["snapshot"], default="snapshot")
    parser.add_argument("--source", choices=SOURCE_NAMES)
    parser.add_argument("--attempt", type=int, choices=[1, 2], default=1)
    args = parser.parse_args(argv)
    if args.source:
        _source_worker(args.source, args.attempt)
    else:
        result = snapshot()
        print(json.dumps({"sources": len(result["sources"]), "fallback_sources": result["fallback_sources"],
                          "historical_catalogue_hashes_unchanged": True}), flush=True)


if __name__ == "__main__":
    main()
