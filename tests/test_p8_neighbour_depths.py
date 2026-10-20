"""Pre-search catalogue caches must acquire candidate context before Stage B."""
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import p8_neighbour_depths as D


def record():
    return {"tic_id": 1, "generated_utc": "original query", "candidate_depths_ppt": [],
            "gaia": {"target": {"phot_rp_mean_mag": 10.0, "phot_g_mean_mag": 10.0},
                     "n_within_1arcmin": 2, "n_neighbours_within_3px_could_make_1ppt": 1,
                     D.COUNT: 0,
                     "neighbours": [{"source_id": 42, "band_used": "rp", "Rp": 17.5, "G": 17.0,
                                     "sep_arcsec": 63.0, "flux_ratio_to_target": 0.001,
                                     "max_observed_depth_ppt_total_eclipse": 1.0,
                                     D.TOTAL: [], D.HALF: []}]},
            "vsx": {"n_within_1arcmin": 1, "objects": [{"Name": "saved object", "sep_arcsec": 30.0}]},
            "simbad": {"objects": [{"otype": "*"}]},
            "summary": "Gaia: 2 sources; 0 neighbour(s) within 3 px bright enough to make the depth; VSX 1"}


def test_unrounded_magnitudes_and_both_eclipse_depth_boundaries():
    before = record()
    original = copy.deepcopy(before)
    out = D.enrich_record(before, [0.499, 0.5, 0.999, 1.0])
    n = out["gaia"]["neighbours"][0]
    # At delta-mag 7.5: a total eclipse is 0.999000999 ppt, a half
    # eclipse is 0.4995005 ppt. The stored 1.0-ppt display value is too coarse.
    assert n[D.TOTAL] == [True, True, True, False]
    assert n[D.HALF] == [True, False, False, False]
    assert out["gaia"][D.COUNT] == 1
    assert "1 neighbour(s)" in out["summary"]
    assert before == original
    out["candidate_depths_ppt"] = []
    out["gaia"][D.COUNT] = 0
    n[D.TOTAL] = n[D.HALF] = []
    out["summary"] = original["summary"]
    assert out == original  # Source fields and the population 1-ppt count stay intact.


def test_g_fallback_missing_magnitudes_and_any_depth_rule():
    before = record()
    n = before["gaia"]["neighbours"][0]
    n.update(band_used="g", Rp=None, G=10.0)
    after = D.enrich_record(before, [250, 500, 500.001])
    assert after["gaia"]["neighbours"][0][D.TOTAL] == [True, True, False]
    assert after["gaia"]["neighbours"][0][D.HALF] == [True, False, False]
    assert after["gaia"][D.COUNT] == 1
    n["G"] = None
    after = D.enrich_record(before, [1.0])
    assert after["gaia"]["neighbours"][0][D.TOTAL] is None
    assert after["gaia"]["neighbours"][0][D.HALF] is None
    assert after["gaia"][D.COUNT] == 0


@pytest.mark.parametrize("separation,depths,count", [(63.0, [0.999], 1), (63.1, [0.999], 0), (63.0, [], 0)])
def test_saved_separation_boundary_and_empty_candidates(separation, depths, count):
    before = record()
    before["gaia"]["neighbours"][0]["sep_arcsec"] = separation
    assert D.enrich_record(before, depths)["gaia"][D.COUNT] == count


def test_depth_context_uses_all_survivors_with_legacy_rounding():
    raw = b"tic_id,depth_ppt\n1,0.99949\n2,5\n1,2.0004\n1,0.9994\n1,nan\n2,\n"
    assert D.depths_by_tic(raw) == {1: [0.999, 2.0], 2: [5.0]}


@pytest.fixture
def population(tmp_path, monkeypatch):
    root = tmp_path / "data/survey/p8"
    (root / "neighbours").mkdir(parents=True)
    targets = root.parent / "targets_p8.csv"
    targets.write_bytes(b"tic_id\n1\n")
    survivors = root / "survivors.csv"
    survivors.write_bytes(b"tic_id,depth_ppt\n1,0.999\n")
    source_sha = {str(p.relative_to(tmp_path)): D.sha(p.read_bytes()) for p in (targets, survivors)}
    (root / "search_validation_p8.json").write_text(json.dumps(
        {"verified": True, "n_targets": 1, "evidence_sha256": source_sha}))
    (root / "neighbours/tic1.json").write_text(json.dumps(record()))
    monkeypatch.setattr(D, "REPO", tmp_path)
    monkeypatch.setattr(D, "ROOT", root)
    return root


def test_enrichment_is_idempotent_and_detects_changed_sources(population):
    with pytest.raises(RuntimeError, match="before Stage B"):
        D.ensure_context(check_only=True)
    result = D.ensure_context()
    assert result["status"] == "complete"
    assert result["n_star_flag_lists_changed"] == 1
    paths = [population / "neighbours/tic1.json", population / "neighbour_depth_context_p8.json"]
    before = [p.read_bytes() for p in paths]
    (population / "stageB").mkdir()
    (population / "stageB/settled.json").write_text("{}")
    D.ensure_context(check_only=True)
    D.ensure_context()
    assert [p.read_bytes() for p in paths] == before
    changed = json.loads(paths[0].read_bytes())
    changed["gaia"]["target"]["phot_rp_mean_mag"] = 11.0
    paths[0].write_text(json.dumps(changed))
    with pytest.raises(RuntimeError, match="cache changed"):
        D.ensure_context(check_only=True)


def test_existing_downstream_records_cannot_receive_silent_context_change(population):
    (population / "stageB").mkdir()
    (population / "stageB/settled.json").write_text("{}")
    with pytest.raises(RuntimeError, match="Downstream P8 records"):
        D.ensure_context()
    assert not (population / "neighbour_depth_context_p8.json").exists()
    assert json.loads((population / "neighbours/tic1.json").read_bytes())["candidate_depths_ppt"] == []


def test_resume_after_interrupted_neighbour_write(population, monkeypatch):
    atomic = D.atomic
    def fail_at_neighbour(path, raw):
        if path.parent.name == "neighbours":
            raise OSError("simulated interruption")
        atomic(path, raw)
    monkeypatch.setattr(D, "atomic", fail_at_neighbour)
    with pytest.raises(OSError, match="interruption"):
        D.ensure_context()
    with pytest.raises(RuntimeError, match="incomplete"):
        D.ensure_context(check_only=True)
    monkeypatch.setattr(D, "atomic", atomic)
    assert D.ensure_context()["status"] == "complete"
    D.ensure_context(check_only=True)


def test_unvalidated_candidate_table_is_rejected_before_writes(population):
    (population / "survivors.csv").write_bytes(b"tic_id,depth_ppt\n1,12\n")
    with pytest.raises(RuntimeError, match="validated candidate"):
        D.ensure_context()
    assert not (population / "neighbour_depth_context_p8.json").exists()
