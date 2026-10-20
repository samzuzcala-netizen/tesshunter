import importlib.util
import json
from pathlib import Path

import pytest
from tesshunter import catalog_crossmatch as cx

spec = importlib.util.spec_from_file_location("p8_catalogs", Path(__file__).resolve().parents[1] / "scripts/p8_catalogs.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_p8_receipt_records_all_downloads_and_restores_default_policy(tmp_path, monkeypatch):
    original = cx.SOURCES["spoc_tce"]

    def fetch(raw_dir, *, force=False):
        assert force
        yield "first.csv", b"first"
        yield "second.csv", b"second"

    fetch.urls = cx._fetch_spoc_tce.urls
    monkeypatch.setattr(cx, "_fetch_spoc_tce", fetch)
    receipt = tmp_path / "receipt.json"
    with module.refetch_tce_versions(receipt):
        assert list(cx.SOURCES["spoc_tce"].fetch(tmp_path)) == [("first.csv", b"first"), ("second.csv", b"second")]
    assert cx.SOURCES["spoc_tce"] is original
    record = json.loads(receipt.read_text())
    assert record["status"] == "complete" and record["n_files"] == 2 and record["n_bytes"] == 11
    assert len(record["files"][0]["sha256"]) == 64


def test_failed_refetch_cannot_leave_a_complete_receipt_or_changed_default(tmp_path, monkeypatch):
    original = cx.SOURCES["spoc_tce"]

    def fetch(raw_dir, *, force=False):
        yield "first.csv", b"first"
        raise cx.CatalogFetchError("interrupted download")

    fetch.urls = cx._fetch_spoc_tce.urls
    monkeypatch.setattr(cx, "_fetch_spoc_tce", fetch)
    receipt = tmp_path / "receipt.json"
    with pytest.raises(cx.CatalogFetchError):
        with module.refetch_tce_versions(receipt):
            list(cx.SOURCES["spoc_tce"].fetch(tmp_path))
    assert cx.SOURCES["spoc_tce"] is original
    record = json.loads(receipt.read_text())
    assert record["status"] == "failed" and record["n_files"] == 1
