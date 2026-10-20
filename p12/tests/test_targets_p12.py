"""Lane C metadata cuts, ordering and network-list fixtures only."""
import hashlib
import io
import json

import pandas as pd
import pytest

import targets_p12 as targets
import fetch_ttt_p12 as ttt
import sector_probe_p12 as sector
from p12_common import read, write


def _row(tic=1, **changes):
    row = dict(tic_id=tic, Teff=3500., rad=.3, Tmag=13., gallat=25.,
        lumclass="DWARF", gaia_dwarf_check="pass", n_sectors_200s=4,
        n_sectors_2min_in_search=1, n_sectors_qlp=4, n_sectors_tess_spoc=0,
        sectors_200s="56,57,58,59", xmatch_status="CLEAN")
    row.update(changes)
    return row


@pytest.mark.parametrize("change", [dict(Teff=3600), dict(rad=.45), dict(Tmag=12.49),
    dict(Tmag=14.), dict(gallat=19.99), dict(lumclass="GIANT"), dict(gaia_dwarf_check="fail"),
    dict(n_sectors_200s=2), dict(n_sectors_2min_in_search=2), dict(xmatch_status="FLAG")])
def test_extension_cuts_preserve_exact_origin_boundaries(change):
    frame = pd.DataFrame([_row(1), _row(2, **change)])
    assert targets.apply_cuts(frame).tic_id.tolist() == [1]


def test_extension_cuts_allow_missing_lumclass_and_negative_latitude_boundary():
    frame = pd.DataFrame([_row(1, lumclass=None, gallat=-20., Tmag=12.5), _row(2, lumclass="")])
    assert targets.apply_cuts(frame).tic_id.tolist() == [1, 2]


def test_extension_ranking_uses_policy_count_radius_noise_and_tic_ties():
    frame = pd.DataFrame([_row(4), _row(3), _row(2, rad=.2),
        _row(1, sectors_200s="55,56,56,57,80,83,85,99,100,101,102,103,104,105,106")])
    ranked = targets._rank_extension(frame)
    assert ranked.tic_id.tolist() == [2, 3, 4, 1]
    assert ranked.set_index("tic_id").loc[1, "n_pol"] == 3
    assert ranked.set_index("tic_id").loc[3, "M"] == pytest.approx(2 / (__import__("math").exp(-8.878 + .810 * 13) * .3 ** 2))
    assert ranked["rank"].tolist() == [1, 2, 3, 4]


def test_ttt_hash_order_core_exclusion_and_first30():
    pool = pd.DataFrame([_row(tic) for tic in range(1, 45)])
    table = pd.DataFrame({"TIC": list(range(1, 47)) + [3]})
    selected, receipt = ttt.select_negatives(table, pool.sample(frac=1, random_state=1), {1, 2})
    expected = sorted(range(3, 45), key=lambda tic: hashlib.sha256(f"20260908:ttt:{tic}".encode()).hexdigest())[:30]
    assert selected.tic_id.tolist() == expected
    assert len(selected) == 30 and receipt["absent_from_pool"] == 2 and receipt["excluded_core"] == 2
    assert [r["step"] for r in receipt["relaxation_sequence"]] == ["baseline"]


def test_ttt_relaxations_stop_at_teff_when20_qualify():
    pool = pd.DataFrame([_row(tic, Teff=3700. if tic > 10 else 3500.) for tic in range(1, 26)])
    selected, receipt = ttt.select_negatives(pool[["tic_id"]], pool, [])
    assert len(selected) == 25
    assert [r["step"] for r in receipt["relaxation_sequence"]] == ["baseline", "Teff"]


def test_ttt_relaxation_sequence_teff_then_tmag_and_inclusive_bounds():
    pool = pd.DataFrame([_row(1, Tmag=14.), _row(2, Teff=3999.),
        _row(3, Teff=3700., Tmag=12.), _row(4, Teff=3700., Tmag=14.5),
        _row(5, Teff=4000.), _row(6, Tmag=14.51), _row(7, Tmag=11.99)])
    selected, receipt = ttt.select_negatives(pool[["tic_id"]], pool, [])
    assert set(selected.tic_id) == {1, 2, 3, 4}
    assert [r["step"] for r in receipt["relaxation_sequence"]] == ["baseline", "Teff", "Tmag"]
    assert [r["qualifying"] for r in receipt["relaxation_sequence"]] == [1, 2, 4]


@pytest.mark.parametrize("change", [dict(rad=.45), dict(gallat=19.99), dict(n_sectors_200s=2),
    dict(n_sectors_2min_in_search=2), dict(n_sectors_qlp=0, n_sectors_tess_spoc=0)])
def test_ttt_never_relaxes_radius_latitude_coverage_or_ffi_majority(change):
    pool = pd.DataFrame([_row(1), _row(2, **change)])
    selected, _ = ttt.select_negatives(pool[["tic_id"]], pool, [])
    assert selected.tic_id.tolist() == [1]


def test_ttt_does_not_apply_novelty_cut_to_known_negatives():
    pool = pd.DataFrame([_row(1, xmatch_status="REJECT")])
    selected, _ = ttt.select_negatives(pd.DataFrame({"tess_id": [1]}), pool, [])
    assert selected.tic_id.tolist() == [1]


def test_ttt_machine_readable_tic_and_period_parser():
    frame = pd.DataFrame({"TIC": ["TIC 100", "TIC 200"], "Porb": [3., 4.]})
    parsed = ttt._ephemeris_table(frame)
    assert parsed.tic_id.tolist() == [100, 200] and parsed.period_days.tolist() == [3., 4.]
    with pytest.raises(ValueError, match="orbital period"):
        ttt._ephemeris_table(frame.drop(columns="Porb"))


def test_ttt_parse_failure_preserves_download_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(ttt, "REPO", tmp_path)
    monkeypatch.setattr(ttt, "ROOT", tmp_path / "p12")
    monkeypatch.setattr(ttt, "DATA", tmp_path / "data/survey/p12")
    body = b"successful-download-without-parseable-table"
    downloaded = ttt._save_download(body, "fixture.tar")
    ttt._download_receipt("eprint", "2026-09-22T00:00:00Z", body, ttt.ARXIV_URL, downloaded)
    with pytest.raises(ValueError, match="No machine-readable"):
        ttt._choose_table([("fixture", pd.DataFrame({"unrelated": [1]}))])
    receipt = read(tmp_path / "p12/results/ttt_fetch/eprint.json")
    assert receipt["status"] == "DOWNLOADED" and receipt["bytes"] == len(body)
    assert receipt["sha256"] == hashlib.sha256(body).hexdigest()


def test_sector_probe_two_lists_no_per_star_requests(monkeypatch):
    monkeypatch.delenv("TESSHUNTER_OFFLINE", raising=False)
    requests = []
    bodies = {sector.LIST_URLS["qlp"]: b'<a href="s0105.csv">s0105.csv</a><a href="s0107.csv">list</a>',
              sector.LIST_URLS["tess-spoc"]: b'<a href="s0106.csv">list</a>'}
    def open_url(request, timeout):
        requests.append((request.full_url, request.get_method(), timeout))
        return io.BytesIO(bodies[request.full_url])
    monkeypatch.setattr(sector.urllib.request, "urlopen", open_url)
    result = sector.latest_public_sector()
    assert requests == [(url, "GET", 60) for url in sector.LIST_URLS.values()]
    assert result["latest_public_sector"] == 107
    assert result["sources"]["tess-spoc"]["available_sectors"] == [106]
    assert result["core_stars_with_product_above_105"] is None
    assert result["core_above_105_status"] == "UNMEASURED"
    assert result["sources"]["qlp"]["sha256"] == hashlib.sha256(bodies[sector.LIST_URLS["qlp"]]).hexdigest()


def test_sector_listing_missing_membership_is_unmeasured(monkeypatch):
    monkeypatch.delenv("TESSHUNTER_OFFLINE", raising=False)
    monkeypatch.setattr(sector.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b"No index"))
    result = sector.latest_public_sector()
    assert result["latest_public_sector"] is None
    assert all(s["status"] == "UNMEASURED" for s in result["sources"].values())


def test_sector_probe_requires_explicit_online_execution(monkeypatch):
    monkeypatch.setenv("TESSHUNTER_OFFLINE", "1")
    with pytest.raises(RuntimeError, match="explicit online"):
        sector.latest_public_sector()


def _put_csv(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def test_core_reject_removal_and_partial_preparation_remains_unknown(monkeypatch, tmp_path):
    root = tmp_path / "p12"
    monkeypatch.setattr(targets, "REPO", tmp_path)
    monkeypatch.setattr(targets, "ROOT", root)
    _put_csv(tmp_path / "data/survey/targets_p8.csv", pd.DataFrame([_row(1), _row(2)]))
    _put_csv(tmp_path / "p10/part3/manifests/targets_evaluated.csv", pd.DataFrame([_row(3)]))
    write(root / "manifests/hard_stop_p12.json", {"per_star": {"1": {"status": "CLEAN"},
        "2": {"status": "REJECT"}, "3": {"status": "FLAG", "f7": {"ephemeris": "none", "associations": []}}}})
    receipt = targets.core()
    assert receipt["rows"] == 2 and receipt["rejected_novelty"] == 1
    assert not (root / "manifests/eligibility_p12.json").exists()
    population = pd.read_csv(root / "manifests/targets_p12_core.csv")
    assert population.tic_id.tolist() == [1, 3]
    assert population.hard_stop_p12.tolist() == ["CLEAN", "FLAG"]
    _put_csv(tmp_path / "data/survey/completeness_sample_p8.csv", pd.DataFrame({"tic_id": [1, 2]}))
    _put_csv(tmp_path / "data/survey/injections_p8.csv", pd.DataFrame({"tic_id": [1, 1, 2]}))
    _put_csv(tmp_path / "data/survey/p10/injections_2b.csv", pd.DataFrame({"tic_id": [1, 2]}))
    write(root / "results/native_noise/archival/tic1.json", dict(tic_id=1, status="INPUT_ELIGIBLE", usable_sectors=[56, 57, 58]))
    targets.core()
    eligibility = read(root / "manifests/eligibility_p12.json")
    assert eligibility["per_star"]["3"]["status"] == "OPERATIONAL_UNKNOWN"
    assert eligibility["n_unknown"] == 1 and not eligibility["complete"]
    assert eligibility["counts"]["calibration_300"] == {"INPUT_ELIGIBLE": 1, "REJECT_NOVELTY": 1}
    assert eligibility["injections"]["full"]["eligible"] == 2 and eligibility["injections"]["2b"]["eligible"] == 1
    assert eligibility["injections"]["full"]["calibration_hosts"] == 2
    assert eligibility["injections"]["full"]["calibration_injections"] == 3
    write(root / "results/native_noise/archival/tic3.json", dict(tic_id=3, status="INPUT_INELIGIBLE", usable_sectors=[56, 57]))
    targets.core()
    assert read(root / "manifests/eligibility_p12.json")["complete"] is True


def test_population_csv_refuses_silent_changed_content(tmp_path):
    path = tmp_path / "population.csv"
    targets._csv(path, pd.DataFrame({"tic_id": [1]}))
    with pytest.raises(RuntimeError, match="Refusing to replace"):
        targets._csv(path, pd.DataFrame({"tic_id": [2]}))
