"""Lane C catalogue tests: synthetic catalogues only; no real truth access."""
from dataclasses import asdict
import json
from pathlib import Path
import types

import pandas as pd
import pytest

import p12_common
import catalog_adapter_p12 as adapter
import catalog_snapshot_p12 as snapshot
import crossmatch_p12 as crossmatch
import build_sidecar_p12 as sidecar
from tesshunter import catalog_crossmatch as cx
from tesshunter.verdict_tiers import k0_hard_stop


def _catalog():
    tables, versions = {}, {}
    for name, tic in (("spoc_tce", 1), ("toi", 2)):
        tables[name] = pd.DataFrame([dict(tic_id=tic, ra=20. * tic, dec=0.,
            label=f"{name} fixture", detail="fixture", source=name)])
        versions[name] = cx.CatalogVersion(name=name, urls=[], fetched_utc="2026-09-22T00:00:00Z",
            n_rows=1, n_files=1, n_bytes=0, sha256="a" * 64, normalized_sha256="b" * 64)
    return cx.KnownObjectCatalog(tables, versions)


def test_bare_tce_without_ephemerides_flags_without_k0():
    result = adapter.hard_stop_p10(1, catalog=_catalog(), resolve_neighbours=False).to_dict()
    assert result["status"] == "FLAG"
    assert result["ephemeris"] == "none" and result["ephemerides"] == []
    assert "ephemeris: none" in result["summary"]
    assert k0_hard_stop(result)["fired"] is False


def test_toi_rejects_and_clean_fixture_is_unchanged():
    catalog = _catalog()
    rejected = adapter.hard_stop_p10(2, catalog=catalog, resolve_neighbours=False)
    assert rejected.to_dict() == catalog.check(2).to_dict()
    assert k0_hard_stop(rejected.to_dict())["fired"] is True
    clean = adapter.hard_stop_p10(3, catalog=catalog, resolve_neighbours=False)
    assert clean.to_dict() == catalog.check(3).to_dict()
    assert clean.status == "CLEAN"


def test_mixed_tce_and_toi_keeps_reject():
    catalog = _catalog()
    catalog.tables["toi"].loc[0, "tic_id"] = 1
    catalog = cx.KnownObjectCatalog(catalog.tables, catalog.versions)
    result = adapter.hard_stop_p10(1, catalog=catalog, resolve_neighbours=False)
    assert result.status == "REJECT"


def test_f7_has_only_available_fields_and_valid_alias():
    records = [dict(ticid=1, sectors="s0001-s0013", tce_plnt_num=2, tce_period=5., tce_model_snr=9.)]
    result = crossmatch.crossmatch_step(dict(tic_id=1, period=10.02), catalog=_catalog(), ephemerides=records)
    association = result["f7"]["associations"][0]
    assert association["run"] == "s0001-s0013" and association["planet_number"] == 2
    assert association["period"] == 5. and association["model_snr"] == 9.
    assert association["alias_ratio"] == 2.
    unmatched = crossmatch.crossmatch_step(dict(tic_id=1, period=8.), catalog=_catalog(), ephemerides=records)
    assert "alias_ratio" not in unmatched["f7"]["associations"][0]
    absent = crossmatch.crossmatch_step(1, catalog=_catalog())
    assert absent["f7"]["associations"] == [] and absent["f7"]["ephemeris"] == "none"


def test_snapshot_load_is_offline_and_never_refreshes(monkeypatch, tmp_path):
    catalog = _catalog()
    calls = []
    def load(**kwargs):
        calls.append((kwargs, cx.CATALOG_CACHE_DIR))
        return catalog
    monkeypatch.setattr(crossmatch, "DATA", tmp_path)
    monkeypatch.setattr(adapter, "DATA", tmp_path)
    monkeypatch.setattr(cx.KnownObjectCatalog, "load", load)
    result = crossmatch.crossmatch_step(3)
    assert result["status"] == "CLEAN"
    assert calls == [({"refresh": False, "offline": True, "allow_stale": True}, tmp_path / "catalogs")]


def test_redaction_never_loads_catalogue(monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("Redacted endpoint opened a catalogue")
    monkeypatch.setattr(cx.KnownObjectCatalog, "load", forbidden)
    result = crossmatch.crossmatch_step(2, redact_catalogue=True)
    assert result["status"] == "KNOWN_STATUS_REDACTED" and "f7" not in result
    assert k0_hard_stop(result)["fired"] is None


def test_combined_population_falls_back_from_nan_coordinate_aliases():
    # TIC 3 is absent by ID, but a known TOI is at these coordinates.
    result = crossmatch.crossmatch_step(dict(tic_id=3, ra_deg=float("nan"), dec_deg=float("nan"),
        ra=40., dec=0.), catalog=_catalog())
    assert result["status"] == "FLAG" and result["neighbour_matches"]


def test_cache_redirect_to_p12_data_path(monkeypatch, tmp_path):
    # Fixture data root emulates the lead-validated D: junction without writing it.
    data = tmp_path / "D_fixture/survey_p12"
    monkeypatch.setattr(p12_common, "DATA", data)
    monkeypatch.setattr(p12_common, "assert_data_root", lambda: data)
    module = types.SimpleNamespace(AUDIT_CACHE=tmp_path / "old")
    cache = p12_common.redirect_audit_cache(module)
    assert module.AUDIT_CACHE == data / "lightkurve"
    assert Path(__import__("os").environ["LIGHTKURVE_CACHE"]) == cache
    assert "audit_p5" not in Path(crossmatch.__file__).read_text().split("import argparse", 1)[1].replace("#", "").split("def _finite", 1)[0]


def _write_source(directory, source, fetched="2026-09-04T00:00:00Z"):
    directory.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([dict(tic_id=1, ra=10., dec=20., label="fixture", detail="fixture", source=source)])
    normalized = directory / f"{source}.normalized.csv"
    frame.to_csv(normalized, index=False)
    version = cx.CatalogVersion(name=source, urls=["https://fixture.invalid/catalogue"], fetched_utc=fetched,
        n_rows=1, n_files=1, n_bytes=normalized.stat().st_size, sha256="a" * 64,
        normalized_sha256=p12_common.sha(normalized))
    (directory / f"{source}.meta.json").write_text(json.dumps(asdict(version)))
    (directory / "raw").mkdir()
    (directory / "raw/fixture.csv").write_text("fixture\n")


def _snapshot_fixture(monkeypatch, tmp_path):
    repo, root, data = tmp_path, tmp_path / "p12", tmp_path / "data/survey/p12"
    for name, value in (("REPO", repo), ("ROOT", root), ("DATA", data)):
        monkeypatch.setattr(snapshot, name, value)
    monkeypatch.setattr(cx, "CATALOG_CACHE_DIR", data / "catalogs")
    monkeypatch.setattr(snapshot, "_catalog_module", lambda: cx)
    monkeypatch.setattr(snapshot, "environment", lambda offline=True: {})
    for name in snapshot.SOURCE_NAMES:
        _write_source(repo / "data/cache/catalogs" / name, name)
    return repo, root, data


def test_six_sources_retry_fallback_and_historic_hashes_unchanged(monkeypatch, tmp_path):
    repo, root, data = _snapshot_fixture(monkeypatch, tmp_path)
    history = repo / "data/cache/catalogs"
    (history / "spoc_tce/spoc_tce.ephemerides.csv").write_text("historical fixture sidecar")
    before = snapshot._hash_tree(history)
    calls = []
    def attempt(source, number):
        calls.append((source, number))
        fail = source == "spoc_tce" or (source == "toi" and number == 1)
        if not fail:
            _write_source(snapshot._attempt_root(source, number) / source, source, "2026-09-22T00:00:00Z")
        return dict(source=source, attempt=number, status="TIMEOUT" if fail else "COMPLETE", deadline_s=600)
    monkeypatch.setattr(snapshot, "_run_source_attempt", attempt)
    result = snapshot.snapshot()
    assert set(result["sources"]) == set(snapshot.SOURCE_NAMES)
    assert result["fallback_sources"] == ["spoc_tce"]
    assert calls.count(("toi", 2)) == 1 and calls.count(("spoc_tce", 2)) == 1
    assert snapshot._hash_tree(history) == before
    assert not (data / "catalogs/spoc_tce/spoc_tce.ephemerides.csv").exists()
    assert p12_common.read(root / "manifests/catalog_hashes_before.json") == p12_common.read(root / "manifests/catalog_hashes_after.json")
    assert snapshot.WORST_CASE_NETWORK_S == 7200 and result["max_attempts"] == 2


def test_unexpected_snapshot_failure_still_records_after_hashes(monkeypatch, tmp_path):
    _, root, _ = _snapshot_fixture(monkeypatch, tmp_path)
    def attempt(*args):
        raise RuntimeError("unexpected fixture failure")
    monkeypatch.setattr(snapshot, "_run_source_attempt", attempt)
    with pytest.raises(RuntimeError, match="unexpected fixture"):
        snapshot.snapshot()
    assert p12_common.read(root / "manifests/catalog_hashes_before.json") == p12_common.read(root / "manifests/catalog_hashes_after.json")


def test_fallback_rejects_unpinned_date(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshot, "REPO", tmp_path)
    monkeypatch.setattr(snapshot, "DATA", tmp_path / "new")
    origin = tmp_path / "old/toi"
    _write_source(origin, "toi", "2026-09-05T00:00:00Z")
    with pytest.raises(RuntimeError, match="2026-09-04"):
        snapshot._copy_source("toi", origin, fallback=True)


def test_sidecar_uses_origin_schema_and_only_new_destination(monkeypatch, tmp_path):
    repo, root, data = tmp_path, tmp_path / "p12", tmp_path / "data/survey/p12"
    for module in (sidecar, adapter):
        for name, value in (("REPO", repo), ("ROOT", root), ("DATA", data)):
            monkeypatch.setattr(module, name, value)
    pool = repo / "data/survey/cache/p8/pool_after_xmatch.csv"
    pool.parent.mkdir(parents=True)
    pd.DataFrame({"tic_id": [1]}).to_csv(pool, index=False)
    raw = data / "catalogs/spoc_tce/raw/fixture_dvr-tcestats.csv"
    raw.parent.mkdir(parents=True)
    row = {key: 1. for key in adapter.EPHEMERIS_COLUMNS}
    row.update(tceid="fixture", ticid=1, sectors="s0001-s0013", tce_period=5.)
    pd.DataFrame([row]).to_csv(raw, index=False)
    old = repo / "data/cache/catalogs/spoc_tce/fixture.csv"
    old.parent.mkdir(parents=True)
    old.write_text("untouched")
    before = p12_common.sha(old)
    result = sidecar.build()
    assert result["rows"] == 1 and result["raw_rows"] == 1
    assert result["columns"][:len(adapter.EPHEMERIS_COLUMNS)] == adapter.EPHEMERIS_COLUMNS
    assert result["path"] == "data/survey/p12/catalogs/spoc_tce/spoc_tce.ephemerides.csv"
    assert p12_common.sha(old) == before
    with pytest.raises(FileExistsError):
        sidecar.build()
