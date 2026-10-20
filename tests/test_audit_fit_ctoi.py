"""Prompt 8 Part 4: the audit's fit, ctoi-fields and verdict path, exercised end to end.

Prompts 5, 6 and 7 left ``audit_p5.fit_step``, ``write_ctoi_fields`` and ``revet_p6.py verdict``
as code that had never run.  This test runs them on a synthetic star in a temporary audit
store: one 200-second sector with an injected 2.3-day transit, through ``prepare_step``,
``forced_step`` (the narrow TLS, which also supplies the ``tls/<key>.json`` record
``fit_step`` reads), ``events_step``, ``fit_step``, ``write_ctoi_fields`` and
``revet_p6.stamp_verdict``.  Slow-ish (a narrow TLS and a batman least-squares fit):
about a minute.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

PERIOD, T0, RP_RS, A_RS = 2.3, 3001.7, 0.09, 12.0


def _make_store(root: Path, tic: int = 999001) -> None:
    from tesshunter.survey import transit_model
    rng = np.random.default_rng(7)
    n = 11500
    t = 3000.0 + np.arange(n) * 200.0 / 86400.0
    model = transit_model(t, period=PERIOD, t0=T0, rp_rs=RP_RS, b=0.2, a_rs=A_RS, u=(0.25, 0.4), exp_time_days=200.0 / 86400.0)
    flux = 5000.0 * model * (1.0 + 1.5e-3 * rng.standard_normal(n))
    tdir = root / f"tic{tic}"
    tdir.mkdir(parents=True)
    np.savez(tdir / "s060_QLP.npz", time=t, flux=flux, flux_err=np.full(n, 7.5), sap_flux=flux * 1.1,
             sap_flux_err=np.full(n, 8.0), sap_bkg=np.full(n, 30.0), quality=np.zeros(n, dtype=np.int64))
    (tdir / "index.json").write_text(json.dumps({"tic_id": tic, "n_products": 1, "n_failed": 0, "products": [
        {"file": "s060_QLP.npz", "author": "QLP", "exptime_s": 200.0, "cadence_s": 200.0, "sector": 60, "n": n,
         "flux_column": "det_flux", "t_start": float(t[0]), "t_end": float(t[-1]), "camera": 1, "ccd": 1,
         "n_quality_nonzero": 0, "n_desat": 0}]}))


def _write_tables(out: Path, tic: int) -> Path:
    cols = ["rank", "tic_id", "planet_num", "search", "period_days", "epoch_btjd", "duration_days", "depth_ppt", "snr",
            "n_transits", "stitch_snr", "stitch_n_transits", "stitch_epoch_consistent", "verdict", "n_units", "tmag",
            "teff_k", "radius_rsun", "mass_msun", "ra_deg", "dec_deg"]
    row = {"rank": 1, "tic_id": tic, "planet_num": 1, "search": "test", "period_days": PERIOD, "epoch_btjd": T0,
           "duration_days": 0.06, "depth_ppt": 1000 * RP_RS ** 2, "snr": 30.0, "n_transits": 10, "stitch_snr": 30.0,
           "stitch_n_transits": 10, "stitch_epoch_consistent": True, "verdict": "test", "n_units": 1, "tmag": 13.0,
           "teff_k": 3400.0, "radius_rsun": 0.35, "mass_msun": 0.35, "ra_deg": 10.0, "dec_deg": -30.0}
    for name in ("survivors.csv", "candidates.csv"):
        with open(out / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerow(row)
    return out / "survivors.csv"


def test_fit_ctoi_and_verdict_run_to_completion(tmp_path, monkeypatch):
    import audit_p5 as A
    import revet_p6 as V
    tic = 999001
    store, out = tmp_path / "store", tmp_path / "out"
    _make_store(store, tic)
    out.mkdir()
    surv = _write_tables(out, tic)
    A.set_roots(out, store)
    A.set_population(survivors_csv=surv, packets_dir=tmp_path / "no_packets")
    A.set_rules(A.R.DEFAULT_RULES)
    monkeypatch.setattr(A, "stellar_from_cache", lambda t: {})       # no TIC cache: the survivor row supplies R, M
    # the audit chain: prepare -> narrow TLS (an ephemeris, and the tls record fit_step reads) -> events
    prep = A.prepare_step(tic, PERIOD)
    assert prep["n_unbinned"] > 10000
    forced = A.forced_step(tic, PERIOD, threads=1, oversampling=3)
    assert 0.02 <= forced["forced"]["duration_days"] <= 0.5
    # fit_step reads tls/<key>.json: the forced record carries the same blocks
    tls_path = out / "tls" / f"{A.key(tic, PERIOD)}.json"
    tls_path.write_text(json.dumps(dict(forced, blind=dict(forced["forced"], match={"same_period_1pct": True}),
                                        verdict_tls="test")), encoding="utf-8")
    ev = A.events_step(tic, PERIOD, source="tls")
    assert ev["summary"]["n_kept"] >= 3
    # the untested path
    fit = A.fit_step(tic, PERIOD)
    a = fit["adopted"]
    assert abs(a["period"] - PERIOD) < 0.01
    assert abs(a["rp_rs"] - RP_RS) / RP_RS < 0.25
    assert a["n_transits"] >= 5
    assert fit["density_prior_adopted"] in (True, False)
    # the ctoi fields
    (out / "neighbours").mkdir(exist_ok=True)
    p = A.write_ctoi_fields(tic, PERIOD, "test note")
    d = json.loads(p.read_text(encoding="utf-8"))
    ff = d["form_fields"]
    for k in ("target", "period_days", "epoch_bjd", "depth_ppm", "duration_hours", "tag", "notes"):
        assert k in ff
    assert ff["epoch_bjd"] > 2457000.0 and ff["depth_ppm"] > 0 and "FILL_ME" in ff["tag"]
    assert d["supplementary"]["rp_rs"] == a["rp_rs"]
    assert Path(d["provenance"]["audit_files"][1]).is_file()
    assert d["provenance"]["rules_version"] == A.RULES_VERSION
    # the verdict stamp on a minimal Stage D record
    V.set_population(out_root=out, survivors_csv=surv, candidates_csv=out / "candidates.csv", packets_dir=tmp_path / "no_packets")
    V.LC_ROOT = store
    (out / "stageD").mkdir(exist_ok=True)
    k = V.kkey(tic, PERIOD)
    (out / "stageD" / f"{k}.json").write_text(json.dumps({"key": k, "tic_id": tic, "rank": 1, "survey_period": PERIOD,
                                                          "survey_depth_ppt": 1000 * RP_RS ** 2, "rules_version": "test",
                                                          "provisional_verdict": "HOLD", "verdict": None}), encoding="utf-8")
    rec = V.stamp_verdict(tic, PERIOD, "SUBMIT", "test reason", note="test note")
    assert rec["verdict"] == "SUBMIT" and rec["ctoi_fields_path"]
    assert (out / "stageD.csv").exists()


def test_unavailable_fit_numbers_are_json_null_and_require_hold():
    import audit_p5 as A
    import revet_p6 as V
    values = A.finite_fields({"period_err": float("nan"), "others": [float("inf"), 1.2]})
    assert json.dumps(values, allow_nan=False) == '{"period_err": null, "others": [null, 1.2]}'
    verdict, reason = V.provisional_verdict({"crossmatch": {"star": {"status": "CLEAN"}},
                                          "fit": {"adopted": {"delta_chi2_vs_flat": 100},
                                                  "uncertainty_issues": ["singular fit covariance"]}})
    assert verdict == "HOLD" and "singular fit covariance" in reason


@pytest.mark.parametrize("survey_period_factor", [1.005, 0.5, 2.0])
def test_p8_fit_recovers_accepted_c_signal_outside_survey_fit_bounds(tmp_path, monkeypatch, survey_period_factor):
    """A C-accepted period can differ by more than the old fit's 0.1% range."""
    import audit_p5 as A
    from tesshunter import survey
    tic, survey_period = 999002, PERIOD * survey_period_factor
    store, out = tmp_path / "store", tmp_path / "out"
    _make_store(store, tic)
    for folder in ("fit", "tls", "stageC"):
        (out / folder).mkdir(parents=True)
    monkeypatch.setattr(A, "OUT", out)
    monkeypatch.setattr(A, "INPUT_CONFIG", survey.get_config("survey_p8"))
    monkeypatch.setattr(A, "RULES_VERSION", "p8.0")
    monkeypatch.setattr(A, "stellar_from_cache", lambda _: {})
    monkeypatch.setattr(A, "_ld_from_packet", lambda *_: (0.25, 0.4, "synthetic"))
    monkeypatch.setattr(A, "survivor_row", lambda *_: {
        "period_days": survey_period, "epoch_btjd": T0 + 0.1, "duration_days": 0.06,
        "depth_ppt": 8.1, "radius_rsun": 0.35, "mass_msun": 0.35})
    k = A.key(tic, survey_period)
    with np.load(store / f"tic{tic}" / "s060_QLP.npz") as z:
        np.savez(out / "tls" / f"{k}_lc.npz", time_unbinned=z["time"],
                 flux_unbinned=z["flux"] / 5000, sector_unbinned=np.full(len(z["time"]), 60))
    (out / "tls" / f"{k}.json").write_text(json.dumps({
        "inputs": {"products": [{"sector": 60, "cadence_s": 200}]},
        "forced": {"depth": 1 - RP_RS ** 2}}))
    context = {"rules_version": "p8.0", "input_config": A.input_config()}
    c = dict(context, decision="PASS", blind={"period": PERIOD, "T0_btjd": T0,
                                             "duration_days": 0.06, "depth": 1 - RP_RS ** 2})
    cpath = out / "stageC" / f"{k}.json"
    cpath.write_text(json.dumps(c))
    # A current-cadence cache made with the old survey seed must be replaced.
    (out / "fit" / f"{k}.json").write_text(json.dumps(dict(context, adopted={"period": survey_period})))
    fit = A.fit_step(tic, survey_period)
    assert abs(fit["adopted"]["period"] - PERIOD) < 1e-4
    assert abs(fit["adopted"]["rp_rs"] / RP_RS - 1) < 0.15
    assert fit["adopted"]["delta_chi2_vs_flat"] > 100
    assert fit["ephemeris_start"]["source"] == "stageC.blind"
    assert fit["adopted"]["n_transits"] >= 10
    assert A.fit_step(tic, survey_period) == dict(fit, input_config=A.input_config())
    # The accepted record, rather than a candidate's old cache, controls reuse.
    c["blind"]["T0_btjd"] += PERIOD
    cpath.write_text(json.dumps(c))
    updated = A.fit_step(tic, survey_period)
    assert updated["fit_input"]["stage_c_sha256"] != fit["fit_input"]["stage_c_sha256"]
    assert updated["ephemeris_start"]["t0"] == T0 + PERIOD
    assert abs(updated["adopted"]["period"] - PERIOD) < 1e-4
    for change in ({"decision": "FAIL"}, {"input_config": None},
                   {"blind": dict(c["blind"], period=float("nan"))}):
        cpath.write_text(json.dumps(dict(c, **change)))
        with pytest.raises(ValueError, match="Stage C"):
            A.fit_step(tic, survey_period)
