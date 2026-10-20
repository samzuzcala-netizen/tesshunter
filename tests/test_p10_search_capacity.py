"""Prompt 10 Part 2b: the search-capacity presets, the resolved-SNR ranking and the trace
instrumentation; ``survey_p8``'s record and behaviour unchanged."""
import json

import pandas as pd
import pytest

from tesshunter import pipeline, survey


def test_presets_exist_with_the_pre_registered_fields():
    a = survey.get_config("survey_p8")
    b = survey.get_config("survey_p10_budget")
    c = survey.get_config("survey_p10_slots")
    d = survey.get_config("survey_p10_rank")
    e = survey.get_config("survey_p10_both")
    assert (a.time_budget_s, a.max_planets, a.max_planets_total, a.top_n, a.min_composite_score) == (900.0, 3, 12, 8, 3.0)
    assert (b.time_budget_s, b.max_planets, b.max_planets_total, b.top_n) == (2700.0, 3, 12, 8)
    assert (c.time_budget_s, c.max_planets, c.max_planets_total, c.top_n) == (900.0, 6, 24, 16)
    assert (d.time_budget_s, d.max_planets, d.max_planets_total, d.top_n, d.rank_by) == (900.0, 6, 24, 16, "snr")
    assert (e.time_budget_s, e.max_planets, e.max_planets_total, e.top_n, e.rank_by) == (2700.0, 6, 24, 16, "snr")
    for cfg in (b, c, d, e):
        assert cfg.min_composite_score == 3.0 and cfg.rank_by in ("composite", "snr")
        # ingestion is identical, so every variant reads the same stitched cache
        assert cfg.ingest_key() == a.ingest_key()
        for field in survey.SurveyConfig.INGEST_FIELDS + survey.SurveyConfig.INGEST_FIELDS_P8:
            assert getattr(cfg, field) == getattr(a, field), field


def test_survey_p8_record_and_search_kwargs_are_unchanged():
    a = survey.get_config("survey_p8")
    assert a.rank_by == "composite" and a.record_traces is False
    assert "rank_by" not in a.search_kwargs() and "record_traces" not in a.search_kwargs()
    d = a.to_dict()
    assert "rank_by" not in d and "record_traces" not in d
    r = survey.get_config("survey_p10_rank")
    assert r.search_kwargs()["rank_by"] == "snr" and r.to_dict()["rank_by"] == "snr"
    t = survey.get_config("survey_p8", record_traces=True)
    assert t.to_dict()["record_traces"] is True and t.ingest_key() == a.ingest_key()
    assert "record_traces" not in t.search_kwargs()


def test_pick_survivor_by_composite_or_resolved_snr():
    pool = [(pd.Series({"period_days": 1.0, "snr": 9.0, "composite_score": 3.5}), 5),
            (pd.Series({"period_days": 2.0, "snr": 7.0, "composite_score": 5.0}), 4)]
    assert pipeline.pick_survivor(pool, "composite")[0]["period_days"] == 2.0
    assert pipeline.pick_survivor(pool, "snr")[0]["period_days"] == 1.0
    legacy = [(pd.Series({"period_days": 3.0, "snr": 8.0}), 3)] + pool
    assert pipeline.pick_survivor(legacy, "composite")[0]["period_days"] == 3.0      # falls back to snr
    with pytest.raises(ValueError):
        pipeline.pick_survivor(pool, "no_such_key")


def test_trace_recorder_writes_partition_and_pass_events(tmp_path, monkeypatch):
    from tesshunter import bls_search
    calls = []
    def fake_bls(lc, **kw):
        calls.append(("bls", kw.get("period_min")))
        return None, None, pd.DataFrame([{"period_days": 2.0, "snr": 8.0}, {"period_days": 3.0, "snr": 6.0}])
    def fake_alias(lc, raw, **kw):
        calls.append(("alias", float(raw["period_days"])))
        return pd.Series({"period_days": float(raw["period_days"]), "snr": 8.5, "composite_score": 4.0}), pd.DataFrame()
    monkeypatch.setattr(bls_search, "run_bls", fake_bls)
    monkeypatch.setattr(bls_search, "resolve_aliases_for_candidate", fake_alias)
    path = tmp_path / "trace.jsonl"
    with survey.TraceRecorder(path) as tr:
        tr.partition = "chunk0"
        _, _, cands = bls_search.run_bls(None, period_min=0.5)
        bls_search.resolve_aliases_for_candidate(None, cands.iloc[0])
        tr.partition = "stitch"
        bls_search.run_bls(None, period_min=10.0)
        bls_search.run_bls(None, period_min=10.0)
    # the originals are restored
    assert bls_search.run_bls is fake_bls and bls_search.resolve_aliases_for_candidate is fake_alias
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [(e["event"], e["partition"], e["pass"]) for e in events] == [
        ("broad_bls", "chunk0", 1), ("alias", "chunk0", 1), ("broad_bls", "stitch", 1), ("broad_bls", "stitch", 2)]
    assert events[0]["candidates"][0]["period_days"] == 2.0 and events[1]["resolved"]["composite_score"] == 4.0
    assert tr.n_events == 4 and tr.passes == {"chunk0": 1, "stitch": 2}


def test_budget_exhausted_reads_the_detection_note():
    assert survey.budget_exhausted(["Detection stopped before pass 3: another pass (~120 s) would not fit the 300 s detection budget (250 s used)"])
    assert not survey.budget_exhausted(["Vetoed ringing signal at P=1.0 d masked but NOT reported as a planet"])
    assert not survey.budget_exhausted([])
