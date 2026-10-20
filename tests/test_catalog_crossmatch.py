"""Hard-stop cross-match tests against recorded fixtures.

Fixtures under ``tests/fixtures/catalogs`` are trimmed copies of the real
catalog downloads (built 2026-09-01; the catalog stamp they were cut from is
recorded in ``acceptance_ids.json``).  Every HTTP call is intercepted, so the
suite is offline and deterministic.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tesshunter import catalog_crossmatch as cx

FIX = Path(__file__).parent / "fixtures" / "catalogs"
ACC = json.loads((FIX / "acceptance_ids.json").read_text())

URL_TO_FIXTURE = {
    cx.EXOFOP_TOI_URL: FIX / "exofop_toi.csv",
    cx.EXOFOP_CTOI_URL: FIX / "exofop_ctoi.csv",
    cx.NASA_PS_URL: FIX / "nasa_ps.csv",
    cx.NASA_PSCOMPPARS_URL: FIX / "nasa_pscomppars.csv",
    cx.TESS_EB_URL: FIX / "hlsp_tess-ebs_s0001-s0026_v1.0_cat.csv",
    cx.SPOC_TCE_INDEX_URL: FIX / "spoc_tce_index.html",
    cx.SPOC_TCE_INDEX_URL + "new_versions/": FIX / "spoc_tce_new_versions_index.html",
}


class FakeHTTP:
    """Serves fixture bytes by URL and counts calls; can be told to fail."""

    def __init__(self, fail_urls=(), fail_all=False, override=None):
        self.calls: list[str] = []
        self.fail_urls = set(fail_urls)
        self.fail_all = fail_all
        self.override = override or {}

    def __call__(self, url: str, timeout: float = 0) -> bytes:
        self.calls.append(url)
        if self.fail_all or url in self.fail_urls:
            raise cx.CatalogFetchError(f"simulated outage for {url}")
        if url in self.override:
            return self.override[url]
        if url in URL_TO_FIXTURE:
            return URL_TO_FIXTURE[url].read_bytes()
        if url.startswith(cx.SPOC_TCE_INDEX_URL):
            name = url[len(cx.SPOC_TCE_INDEX_URL):].replace("new_versions/", "")
            return (FIX / "spoc_tce" / name).read_bytes()
        raise cx.CatalogFetchError(f"no fixture for {url}")


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cx, "CATALOG_CACHE_DIR", tmp_path / "catalogs")
    cx.reset_catalog()
    yield tmp_path / "catalogs"
    cx.reset_catalog()


COORDS_FIXTURE = FIX / "spoc_tce_tic_coords.csv"


class FakeTIC:
    """Serves TIC coordinates for TCE hosts from the recorded fixture; can drop IDs or fail."""

    def __init__(self, fail=False, drop=()):
        self.fail = fail
        self.drop = set(int(x) for x in drop)
        self.calls = 0
        self.table = pd.read_csv(COORDS_FIXTURE)
        self.table["tic_id"] = self.table["tic_id"].astype("int64")

    def __call__(self, ids):
        self.calls += 1
        if self.fail:
            raise cx.CatalogFetchError("simulated TIC outage")
        want = [int(x) for x in ids if int(x) not in self.drop]
        t = self.table[self.table["tic_id"].isin(want)]
        return pd.DataFrame({"tic_id": t["tic_id"].to_numpy(), "ra": t["ra"].to_numpy(), "dec": t["dec"].to_numpy(),
                             "tmag": t["tmag"].to_numpy(), "objtype": t["objtype"].astype(str).to_numpy()})


@pytest.fixture
def fake_tic(monkeypatch):
    f = FakeTIC()
    monkeypatch.setattr(cx, "_query_tic_by_ids", f)
    return f


@pytest.fixture
def fake_http(monkeypatch, fake_tic):
    f = FakeHTTP()
    monkeypatch.setattr(cx, "_http_get", f)
    return f


@pytest.fixture
def catalog(cache_dir, fake_http):
    return cx.KnownObjectCatalog.load()


# ── parsing, one test per source ──────────────────────────────────────────────
@pytest.mark.parametrize("name", sorted(cx.SOURCES))
def test_each_source_parses_recorded_fixture(name, cache_dir, fake_http):
    df, ver = cx.load_source(name)
    assert len(df) > 0
    assert list(df.columns) == cx.NORMALIZED_COLUMNS
    assert df["tic_id"].dtype == np.int64 and (df["tic_id"] > 0).all()
    assert (df["source"] == name).all()
    assert np.isfinite(df["ra"]).all() and np.isfinite(df["dec"]).all()
    assert df["ra"].between(0, 360).all() and df["dec"].between(-90, 90).all()
    assert ver.n_rows == len(df) and ver.n_files >= 1 and ver.n_bytes > 0
    if cx.SOURCES[name].resolve_coords:
        assert ver.coords and ver.coords["n_unresolved"] == 0 and not ver.coords["partial"]
        assert ver.coords["provenance"].startswith("TIC")


def test_toi_sexagesimal_coordinates_convert_to_degrees(cache_dir, fake_http):
    df, _ = cx.load_source("toi")
    row = df[df["tic_id"] == 231663901].iloc[0]         # TOI-101, ExoFOP RA 21:14:56.88 Dec -55:52:18.71
    assert abs(row["ra"] - 318.737) < 0.01
    assert abs(row["dec"] - (-55.8719)) < 0.001
    assert row["label"].startswith("TOI-101")


def test_spoc_tce_reads_every_listed_file_and_labels_the_run(cache_dir, fake_http):
    df, ver = cx.load_source("spoc_tce")
    listed = [n for n in (FIX / "spoc_tce").iterdir()]
    assert ver.n_files == len(listed)
    assert df["label"].str.match(r"TCE s\d{4}-s\d{4} pn\d+").all()
    # raw copies are kept so a re-run does not re-download immutable files
    assert len(list((cache_dir / "spoc_tce" / "raw").glob("*.csv"))) == len(listed)


# ── hard stop by TIC ID, one test per source ──────────────────────────────────
@pytest.mark.parametrize("name", sorted(cx.SOURCES))
def test_tic_match_rejects_for_each_source(name, catalog):
    tic = int(catalog.tables[name]["tic_id"].iloc[0])
    res = catalog.check(tic)
    assert res.rejected and res.status == cx.STATUS_REJECT
    assert any(m["source"] == name for m in res.tic_matches)
    assert "REJECT" in res.summary()


# ── neighbour flags ───────────────────────────────────────────────────────────
def test_known_object_within_one_pixel_flags_but_does_not_reject(catalog):
    toi = catalog.tables["toi"].iloc[0]
    ra, dec = float(toi["ra"]), float(toi["dec"])
    near = catalog.check(999_999_999, ra, dec + 10.0 / 3600.0, neighbour_tics=[])
    assert near.status == cx.STATUS_FLAG and not near.rejected
    hit = near.neighbour_matches[0]
    assert hit["neighbour_tic"] == int(toi["tic_id"]) and hit["via"] == "coordinates"
    assert 9.9 < hit["sep_arcsec"] < 10.1
    far = catalog.check(999_999_999, ra, dec + 30.0 / 3600.0, neighbour_tics=[])
    assert far.status == cx.STATUS_CLEAN


def test_tce_only_neighbour_is_caught_through_its_tic_id(catalog):
    tce_tic = ACC["tce_only"][0]
    res = catalog.check(999_999_999, 10.0, 10.0, neighbour_tics=[(tce_tic, 6.5)])
    assert res.flagged
    assert res.neighbour_matches[0]["via"] == "neighbour_tic"
    assert res.neighbour_matches[0]["source"] == "spoc_tce"


def test_recorded_flag_cases(catalog):
    """Real TIC neighbours of real TOIs, recorded with their coordinates."""
    for fc in ACC["flag_cases"]:
        res = catalog.check(fc["tic_id"], fc["ra"], fc["dec"],
                            neighbour_tics=[(fc["near_known_tic"], 10.0)])
        assert res.flagged, fc
        assert fc["near_known_tic"] in {m["neighbour_tic"] for m in res.neighbour_matches}


# ── SPOC TCE hosts in the coordinate tree ────────────────────────────────────
def _edge(name):
    e = ACC["tce_edge_cases"][name]
    if e is None:
        pytest.skip(f"no recorded {name}")
    return e


def test_tce_coordinates_are_resolved_cached_and_stamped(cache_dir, fake_http, fake_tic):
    df, ver = cx.load_source("spoc_tce")
    assert fake_tic.calls >= 1
    stamp = json.loads((cache_dir / "spoc_tce" / "tic_coords.meta.json").read_text())
    assert stamp["n_requested"] == df["tic_id"].nunique() and stamp["n_unresolved"] == 0
    assert stamp["provenance"] == cx.TIC_COORD_PROVENANCE and stamp["cache_sha256"]
    assert (cache_dir / "spoc_tce" / "tic_coords.csv").exists()
    # a second load is served from the coordinate cache without querying the TIC again
    n = fake_tic.calls
    cx.load_source("spoc_tce", refresh=True)
    assert fake_tic.calls == n


def test_bulk_coordinate_cache_keeps_unique_missing_ids_and_cached_values(cache_dir, monkeypatch):
    ids = np.arange(50000, 60000)
    cached = pd.DataFrame({"tic_id": np.r_[ids, 70001], "ra": 12.5, "dec": -25.,
                           "tmag": 13., "objtype": "STAR"})
    path = cache_dir / "spoc_tce" / "tic_coords.csv"
    path.parent.mkdir(parents=True)
    cached.to_csv(path, index=False)
    queried = []

    def query(wanted):
        queried.extend(wanted)
        return pd.DataFrame({"tic_id": [99001], "ra": [45.], "dec": [10.], "tmag": [12.], "objtype": ["STAR"]})

    monkeypatch.setattr(cx, "_query_tic_by_ids", query)
    coords, stamp = cx.resolve_tic_coordinates("spoc_tce", [*ids[::-1], 50000, 99001, 99000, 99000])
    assert queried == [99000, 99001]
    assert stamp["n_requested"] == 10002 and stamp["n_resolved"] == 10001
    assert stamp["unresolved_tic_ids"] == [99000]
    assert stamp["n_cached_rows"] == 10002  # retains the unrequested cached row too
    assert set(coords.tic_id) == {*ids, 99001}
    np.testing.assert_array_equal(coords.loc[coords.tic_id.isin(ids), "ra"], 12.5)


def test_explicit_spoc_refetch_downloads_existing_version_files(cache_dir, fake_http):
    raw = cache_dir / "spoc_tce" / "raw"
    first = dict(cx._fetch_spoc_tce(raw))
    fake_http.calls.clear()
    assert dict(cx._fetch_spoc_tce(raw)) == first
    assert set(fake_http.calls) == {cx.SPOC_TCE_INDEX_URL + s for s in cx.SPOC_TCE_SUBDIRS}
    fake_http.calls.clear()
    assert dict(cx._fetch_spoc_tce(raw, force=True)) == first
    assert len(fake_http.calls) == len(cx.SPOC_TCE_SUBDIRS) + len(first)
    assert not list(raw.glob("*.refetch.tmp"))


def test_tce_only_neighbour_across_a_tile_boundary_is_flagged(catalog):
    """The host lies outside the target's tile: the neighbour table is empty, yet the
    coordinate tree (built from resolved TCE coordinates) still flags the target."""
    host = _edge("boundary_tce_host")
    tic = 999_999_990
    res = catalog.check(tic, host["ra"], host["dec"] + 10.0 / 3600.0, neighbour_tics=[])
    assert res.flagged, res.summary()
    hit = [m for m in res.neighbour_matches if m["neighbour_tic"] == host["tic_id"]][0]
    assert hit["source"] == "spoc_tce" and hit["via"] == "coordinates" and 9.9 < hit["sep_arcsec"] < 10.1
    batch = catalog.check_many(pd.DataFrame({"tic_id": [tic], "ra": [host["ra"]], "dec": [host["dec"] + 10.0 / 3600.0]}),
                               neighbours=pd.DataFrame(columns=["tic_id", "ra", "dec"]))
    assert batch["xmatch_status"].iloc[0] == cx.STATUS_FLAG and "spoc_tce" in batch["xmatch_neighbour_sources"].iloc[0]


def test_tce_only_neighbour_fainter_than_tmag17_is_flagged(catalog):
    """A TCE host fainter than the tile query limit (Tmag 17) is still in the coordinate tree."""
    host = _edge("faint_tce_host")
    assert host["tmag"] > 17.0
    tic = 999_999_991
    ra, dec = host["ra"], host["dec"] + 8.0 / 3600.0
    # the tile-style neighbour table deliberately omits the faint host (Tmag > 17 would not be queried)
    neighbours = pd.DataFrame({"tic_id": [tic], "ra": [ra], "dec": [dec]})
    res = catalog.check(tic, ra, dec, neighbour_tics=[])
    assert res.flagged and any(m["neighbour_tic"] == host["tic_id"] and m["via"] == "coordinates"
                               for m in res.neighbour_matches)
    batch = catalog.check_many(pd.DataFrame({"tic_id": [tic], "ra": [ra], "dec": [dec]}), neighbours=neighbours)
    assert batch["xmatch_status"].iloc[0] == cx.STATUS_FLAG
    assert str(host["tic_id"]) in batch["xmatch_neighbour_tics"].iloc[0]


def test_batch_and_single_target_agree_on_tce_neighbours(catalog):
    hosts = [h for h in (ACC["tce_edge_cases"].get("boundary_tce_host"), ACC["tce_edge_cases"].get("faint_tce_host")) if h]
    if not hosts:
        pytest.skip("no recorded TCE edge cases")
    rows = []
    for i, h in enumerate(hosts):
        rows.append({"tic_id": 999_999_900 + i, "ra": h["ra"], "dec": h["dec"] + 12.0 / 3600.0})   # inside 21 arcsec
        rows.append({"tic_id": 999_999_950 + i, "ra": h["ra"], "dec": h["dec"] + 40.0 / 3600.0})   # outside
    df = pd.DataFrame(rows)
    batch = catalog.check_many(df)
    for (_, r), status in zip(df.iterrows(), batch["xmatch_status"]):
        single = catalog.check(int(r["tic_id"]), r["ra"], r["dec"], neighbour_tics=[])
        assert single.status == status
    assert list(batch["xmatch_status"]) == [cx.STATUS_FLAG, cx.STATUS_CLEAN] * len(hosts)


def test_tce_coordinate_query_failure_raises(cache_dir, monkeypatch):
    monkeypatch.setattr(cx, "_http_get", FakeHTTP())
    monkeypatch.setattr(cx, "_query_tic_by_ids", FakeTIC(fail=True))
    with pytest.raises(cx.CatalogFetchError, match="TIC"):
        cx.load_source("spoc_tce")
    with pytest.raises(cx.CatalogFetchError):
        cx.KnownObjectCatalog.load()


def test_unresolved_tce_host_is_loud_unless_partial_is_allowed(cache_dir, monkeypatch):
    monkeypatch.setattr(cx, "_http_get", FakeHTTP())
    dropped = ACC["tce_only"][0]
    monkeypatch.setattr(cx, "_query_tic_by_ids", FakeTIC(drop=[dropped]))
    with pytest.raises(cx.CatalogFetchError, match="no TIC coordinates"):
        cx.load_source("spoc_tce")
    df, ver = cx.load_source("spoc_tce", allow_partial_coords=True)
    assert ver.coords["partial"] and ver.coords["n_unresolved"] == 1
    assert ver.coords["unresolved_tic_ids"] == [dropped] and "!partialcoords" in ver.short()
    assert df.loc[df["tic_id"] == dropped, "ra"].isna().all()
    # the TIC-ID reject still works for the unresolved host; only its coordinate position is missing
    cat = cx.KnownObjectCatalog.load(allow_partial_coords=True)
    assert cat.check(dropped).rejected and cat.any_partial_coords()
    # a cached partial table is refused again on the next default load
    cx.reset_catalog()
    with pytest.raises(cx.CatalogFetchError, match="without coordinates"):
        cx.load_source("spoc_tce")


# ── loud failure and cache policy ─────────────────────────────────────────────
def test_fetch_failure_raises_instead_of_no_match(cache_dir, monkeypatch):
    monkeypatch.setattr(cx, "_http_get", FakeHTTP(fail_all=True))
    with pytest.raises(cx.CatalogFetchError):
        cx.load_source("toi")
    with pytest.raises(cx.CatalogFetchError):
        cx.KnownObjectCatalog.load()


def test_one_unreachable_source_fails_the_whole_load(cache_dir, monkeypatch):
    monkeypatch.setattr(cx, "_http_get", FakeHTTP(fail_urls={cx.EXOFOP_CTOI_URL}))
    with pytest.raises(cx.CatalogFetchError, match="ctoi|download_ctoi"):
        cx.KnownObjectCatalog.load()


def test_empty_catalog_body_is_a_failure(cache_dir, monkeypatch):
    header_only = (FIX / "exofop_toi.csv").read_text().splitlines()[0] + "\n"
    monkeypatch.setattr(cx, "_http_get", FakeHTTP(override={cx.EXOFOP_TOI_URL: header_only.encode()}))
    with pytest.raises(cx.CatalogFetchError, match="0 rows"):
        cx.load_source("toi")


def _age_stamp(cache_dir, name, days):
    p = cache_dir / name / f"{name}.meta.json"
    d = json.loads(p.read_text())
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    d["fetched_utc"] = old.strftime("%Y-%m-%dT%H:%M:%SZ")
    p.write_text(json.dumps(d))


def test_fresh_cache_is_served_without_network(cache_dir, fake_http):
    cx.load_source("toi")
    n = len(fake_http.calls)
    df, ver = cx.load_source("toi")
    assert len(fake_http.calls) == n and len(df) > 0 and not ver.stale


def test_cache_older_than_seven_days_is_refetched(cache_dir, fake_http):
    cx.load_source("toi")
    _age_stamp(cache_dir, "toi", days=8)
    n = len(fake_http.calls)
    _, ver = cx.load_source("toi")
    assert len(fake_http.calls) == n + 1
    assert (dt.datetime.now(dt.timezone.utc) - dt.datetime.strptime(
        ver.fetched_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)).days == 0


def test_stale_cache_plus_outage_raises_unless_explicitly_allowed(cache_dir, monkeypatch):
    monkeypatch.setattr(cx, "_http_get", FakeHTTP())
    cx.load_source("toi")
    _age_stamp(cache_dir, "toi", days=9)
    monkeypatch.setattr(cx, "_http_get", FakeHTTP(fail_all=True))
    with pytest.raises(cx.CatalogFetchError):
        cx.load_source("toi")
    df, ver = cx.load_source("toi", allow_stale=True)
    assert ver.stale and len(df) > 0 and "!stale" in ver.short()


def test_version_stamp_records_bytes_digest_and_urls(cache_dir, fake_http):
    _, ver = cx.load_source("tess_eb")
    meta = json.loads((cache_dir / "tess_eb" / "tess_eb.meta.json").read_text())
    raw = (FIX / "hlsp_tess-ebs_s0001-s0026_v1.0_cat.csv").read_bytes()
    assert meta["files"][0]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert meta["n_bytes"] == len(raw) and meta["urls"] == [cx.TESS_EB_URL]
    assert meta["schema_version"] == cx.SCHEMA_VERSION and ver.name == "tess_eb"
    assert ver.short().startswith("tess_eb=") and len(ver.short().split(":")[1]) >= 8


def test_manifest_and_stamp_cover_every_source(catalog, tmp_path):
    stamp = catalog.stamp()
    for name in cx.SOURCES:
        assert f"{name}=" in stamp
    p = catalog.write_manifest(tmp_path / "manifest.json")
    m = json.loads(p.read_text())
    assert set(m["sources"]) == set(cx.SOURCES) and m["stamp"] == stamp
    assert all("files" not in v for v in m["sources"].values())


# ── acceptance: 20 TOIs, 20 CTOIs, 10 EBs, 10 TCE-only, 20 clean ──────────────
def _coords(catalog, source, tic):
    df = catalog.tables[source]
    r = df[df["tic_id"] == tic].iloc[0]
    return float(r["ra"]), float(r["dec"])


def _run_acceptance(catalog):
    assert len(ACC["toi"]) == 20 and len(ACC["ctoi"]) == 20
    assert len(ACC["tess_eb"]) == 10 and len(ACC["tce_only"]) == 10 and len(ACC["clean"]) == 20
    for src, key in (("toi", "toi"), ("ctoi", "ctoi"), ("tess_eb", "tess_eb")):
        for tic in ACC[key]:
            ra, dec = _coords(catalog, src, tic)
            res = catalog.check(tic, ra, dec, neighbour_tics=[])
            assert res.rejected and any(m["source"] == src for m in res.tic_matches), (src, tic)
    for tic in ACC["tce_only"]:
        res = catalog.check(tic, neighbour_tics=[])
        assert res.rejected and {m["source"] for m in res.tic_matches} == {"spoc_tce"}, tic
    for s in ACC["clean"]:
        res = catalog.check(s["tic_id"], s["ra"], s["dec"], neighbour_tics=[])
        assert res.status == cx.STATUS_CLEAN, s
    # the batch path covers all 80 objects and agrees with the single-target path, category by category
    rows, expect_status, expect_source = [], [], []
    for src, key in (("toi", "toi"), ("ctoi", "ctoi"), ("tess_eb", "tess_eb")):
        for t in ACC[key]:
            ra, dec = _coords(catalog, src, t)
            rows.append({"tic_id": t, "ra": ra, "dec": dec, "category": key})
            expect_status.append(cx.STATUS_REJECT)
            expect_source.append(src)
    for t in ACC["tce_only"]:
        ra, dec = _coords(catalog, "spoc_tce", t)
        rows.append({"tic_id": t, "ra": ra, "dec": dec, "category": "tce_only"})
        expect_status.append(cx.STATUS_REJECT)
        expect_source.append("spoc_tce")
    for s_ in ACC["clean"]:
        rows.append({"tic_id": s_["tic_id"], "ra": s_["ra"], "dec": s_["dec"], "category": "clean"})
        expect_status.append(cx.STATUS_CLEAN)
        expect_source.append("")
    df = pd.DataFrame(rows)
    assert len(df) == 80 and df["category"].value_counts().to_dict() == {
        "toi": 20, "ctoi": 20, "tess_eb": 10, "tce_only": 10, "clean": 20}
    out = catalog.check_many(df[["tic_id", "ra", "dec"]])
    assert list(out["xmatch_status"]) == expect_status
    for (_, r), status, src, sources in zip(df.iterrows(), out["xmatch_status"], expect_source, out["xmatch_tic_sources"]):
        got = set(sources.split("|")) if sources else set()
        if r["category"] == "clean":
            assert status == cx.STATUS_CLEAN and got == set(), r["tic_id"]
        elif r["category"] == "tce_only":
            assert got == {"spoc_tce"}, (r["tic_id"], got)                 # in a TCE list and nowhere else
        else:
            assert src in got, (r["category"], r["tic_id"], got)          # rejected by its own catalog
        single = catalog.check(int(r["tic_id"]), r["ra"], r["dec"], neighbour_tics=[])
        assert single.status == status and {m["source"] for m in single.tic_matches} == got
    assert (out["catalog_versions"] == catalog.stamp()).all()
    counts = out["xmatch_status"].value_counts().to_dict()
    assert counts == {cx.STATUS_REJECT: 60, cx.STATUS_CLEAN: 20}


def test_acceptance_lists_offline_fixtures(catalog):
    _run_acceptance(catalog)


@pytest.mark.skipif(os.environ.get("TESSHUNTER_LIVE_CATALOGS") != "1",
                    reason="set TESSHUNTER_LIVE_CATALOGS=1 to run against the real cached catalogs")
def test_acceptance_lists_against_live_cache():
    cx.reset_catalog()
    catalog = cx.KnownObjectCatalog.load(offline=True)
    assert not catalog.any_stale(), "live cache is stale; refresh before certifying"
    assert not catalog.any_partial_coords(), "live TCE coordinate table is partial"
    _run_acceptance(catalog)


# ── pipeline integration: the stop happens before any download ────────────────
def test_search_target_hard_stops_before_download(monkeypatch):
    from tesshunter import pipeline

    def fake_xm(tic_id, **kw):
        return {"summary_str": "REJECT: TIC 1 is a known object: toi:TOI-1.01",
                "is_known_toi": True, "is_confirmed_planet": False, "status": "REJECT",
                "rejected": True, "flagged": False, "catalog_versions": "toi=x",
                "hard_stop": {"status": "REJECT"}}

    def boom(*a, **k):
        raise AssertionError("download must not run after a hard stop")

    monkeypatch.setattr(cx, "crossmatch", fake_xm)
    monkeypatch.setattr(pipeline, "search_and_download_lc", boom)
    res = pipeline.search_target(1, do_crossmatch=True, generate_report=False)
    assert res.planets == [] and any(n.startswith("HARD STOP") for n in res.notes)
    assert res.crossmatch["status"] == "REJECT"
    assert res.to_dict()["crossmatch"]["catalog_versions"] == "toi=x"


def test_search_target_propagates_catalog_outage(monkeypatch):
    from tesshunter import pipeline

    def fail(tic_id, **kw):
        raise cx.CatalogFetchError("simulated outage")

    monkeypatch.setattr(cx, "crossmatch", fail)
    monkeypatch.setattr(pipeline, "search_and_download_lc",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no download")))
    with pytest.raises(cx.CatalogFetchError):
        pipeline.search_target(1, do_crossmatch=True, generate_report=False)
