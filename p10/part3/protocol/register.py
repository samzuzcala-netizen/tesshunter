"""Seal adopted rules and original instruction bytes before Part A."""
from common import REPO, ROOT, initialize, read, write, sha, utc


def main():
    initialize()
    if read(ROOT / "results/integrity_entry/summary.json")["status"] != "PASS":
        raise RuntimeError("STOP-4: entry integrity has not passed")
    snapshot = ROOT / "manifests/PROMPT_P10_3.source.md"
    with snapshot.open("xb") as out:
        out.write((REPO / "PROMPT_P10_3.md").read_bytes())
    names = [snapshot, ROOT / "PREREGISTRATION_P10_3.md", ROOT / "protocol/config.json"]
    write(ROOT / "manifests/registration_seal.json", dict(utc=utc(),
        hashes={p.relative_to(REPO).as_posix(): sha(p) for p in names},
        before_part_a=True, before_blind_search=True, no_scientific_jobs_started=True))
    write(ROOT / "manifests/exposure_ledger.json", dict(utc=utc(), stages=[],
        part_f_opened=False, development_exposed=False))
    write(ROOT / "manifests/resource_ledger.json", dict(utc=utc(),
        prior_queue_hours=16.0198, new_queue_hours=0, new_queue_hours_cap=31.98,
        prior_acquisition_bytes=85401427, new_acquisition_bytes=0,
        acquisition_cap_bytes=15000000000, intervals=[], checkin_schedule=None,
        checkin_count=0, cache_relocation=None))
    (ROOT / "logs/checkins.jsonl").touch(exist_ok=False)
    print("registration locked", sha(ROOT / "manifests/registration_seal.json"))


if __name__ == "__main__":
    main()
