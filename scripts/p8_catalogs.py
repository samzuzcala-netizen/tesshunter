"""P8's explicit re-download of all SPOC TCE version files, with a receipt."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def refetch_tce_versions(receipt_path: Path):
    """Override this process's TCE fetcher; restore ordinary cache reuse on exit.

    The other five sources already re-download their complete payloads when
    KnownObjectCatalog.load(refresh=True) is called. Ordinary P6/P7 calls
    retain their existing immutable-version-file cache policy.
    """
    from tesshunter import catalog_crossmatch as cx
    original = cx.SOURCES["spoc_tce"]
    receipt = {"started_utc": utc(), "status": "not_requested", "files": [],
               "method": "Refresh both SPOC TCE directory indexes and re-download every listed CSV, including cached versions."}
    exhausted = False

    def fetch(raw_dir):
        nonlocal exhausted
        receipt["status"] = "running"
        for name, data in cx._fetch_spoc_tce(raw_dir, force=True):
            receipt["files"].append({"filename": name, "n_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            yield name, data
        exhausted = True

    fetch.urls = cx._fetch_spoc_tce.urls
    fetch.single = False
    cx.SOURCES["spoc_tce"] = replace(original, fetch=fetch)
    try:
        yield
        if exhausted and receipt["files"]:
            receipt["status"] = "complete"
        elif receipt["status"] == "running":
            receipt["status"] = "incomplete"
    except BaseException as exc:
        receipt.update(status="failed", error=f"{type(exc).__name__}: {exc}"[:500])
        raise
    finally:
        cx.SOURCES["spoc_tce"] = original
        receipt["finished_utc"] = utc()
        receipt["n_files"] = len(receipt["files"])
        receipt["n_bytes"] = sum(f["n_bytes"] for f in receipt["files"])
        receipt_path = Path(receipt_path)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = receipt_path.with_name(receipt_path.name + ".tmp")
        temporary.write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
        temporary.replace(receipt_path)
