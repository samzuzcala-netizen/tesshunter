"""The ported audit rules reproduce the records prompts 5 and 6 actually produced.

``tests/fixtures/audit/`` holds the per-product arrays of three real stars (one
product per sector, exactly what ``choose_per_sector`` keeps) together with the
records those arrays must reproduce.  These tests run the package rules over the
arrays and compare, field by field:

* TIC 334678787 and TIC 212261364 - the prompt-5 ``events`` records under all
  three ephemerides (survey, P4 packet refit, forced TLS);
* TIC 233007823 - the prompt-6 Stage A decision and its numbers, on a candidate
  that PASSED, plus its Stage B window test.

The ephemerides are read out of the expected records: a forced TLS is an INPUT
to the event rules, not one of them, and re-running it here would be testing
``transitleastsquares``.  Everything downstream of the ephemeris is recomputed.

``scripts/p7_reproduce.py`` does the same over all 405 survivors; this file is
the part that runs in the test suite, offline, in a few seconds.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from tesshunter.audit_prep import prepare_series
from tesshunter.event_vet import event_table, stagea_criteria, summarise_events
from tesshunter.star_vet import gaia_flag_digest, phase_independent_test

pytest.importorskip("wotan", reason="the audit detrend needs wotan")

FIX = Path(__file__).parent / "fixtures" / "audit"
ARRAY_KEYS = ("time", "flux", "flux_err", "sap_flux", "sap_flux_err", "sap_bkg", "quality")


def _load_products(tic: int) -> list[dict]:
    """The per-product arrays, in the shape ``audit_p5.load_products`` returns."""
    d = FIX / f"tic{tic}"
    idx = json.loads((d / "index.json").read_text(encoding="utf-8"))
    out = []
    for p in idx["products"]:
        z = dict(np.load(d / p["file"]))
        z.update(p)
        out.append(z)
    return out


def _star(tic: int) -> dict:
    return json.loads((FIX / f"tic{tic}" / "star.json").read_text(encoding="utf-8"))


def _expected(tic: int, name: str) -> dict:
    return json.loads((FIX / f"tic{tic}" / "expected" / f"{name}.json").read_text(encoding="utf-8"))


def _prepared(tic: int) -> dict:
    """Detrend, bin and clip exactly as ``prepare_step`` did, from the fixture arrays alone."""
    meta = _expected(tic, "prep")
    row = _star(tic)["survivors"][0]
    for r in _star(tic)["survivors"]:
        if abs(float(r["period_days"]) - meta["survey_period"]) < 1e-6:
            row = r
    ref_depth = float(row["depth_ppt"]) / 1000.0
    return prepare_series(_load_products(tic), meta["wotan"]["window_days"],
                          meta["bin_minutes"], ref_depth)


@pytest.fixture(scope="module")
def prepared():
    return {tic: _prepared(tic) for tic in (334678787, 212261364, 233007823)}


# ── the preprocessing ────────────────────────────────────────────────────────

@pytest.mark.parametrize("tic", [334678787, 212261364, 233007823])
def test_prepare_reproduces_the_prompt6_counters(prepared, tic):
    got, want = prepared[tic]["counters"], _expected(tic, "prep")
    for k in ("n_unbinned", "n_binned", "n_isolated_clipped", "n_isolated_bins_clipped",
              "n_deep_clipped", "deep_clip_threshold_ppt"):
        assert got[k] == want[k], f"{tic} {k}: {got[k]} != {want[k]}"


@pytest.mark.parametrize("tic", [334678787, 212261364, 233007823])
def test_prepare_reproduces_the_per_product_counters(prepared, tic):
    got = prepared[tic]["per_product"]
    want = _expected(tic, "prep")["per_product"]
    assert len(got) == len(want)
    for a, b in zip(got, want):
        assert a == b, f"{tic} sector {b.get('sector')}"


@pytest.mark.parametrize("tic", [334678787, 212261364, 233007823])
def test_the_detrend_window_the_records_used_is_the_documented_one(tic):
    from tesshunter.audit_prep import detrend_window_days, expected_t14_hours
    meta, st = _expected(tic, "prep"), _star(tic)
    t14 = expected_t14_hours(meta["survey_period"], st["R_star"], st["M_star"])
    assert t14 == pytest.approx(st["expected_t14_hours_b0"])
    assert detrend_window_days(t14) == pytest.approx(meta["wotan"]["window_days"])


# ── the prompt-5 events records ──────────────────────────────────────────────

@pytest.mark.parametrize("tic,eph", [(334678787, "survey"), (334678787, "packet"), (334678787, "tls"),
                                     (212261364, "survey"), (212261364, "packet"), (212261364, "tls")])
def test_prompt5_events_records_are_reproduced_exactly(prepared, tic, eph):
    want = _expected(tic, f"events_{eph}")
    e = want["summary"]["ephemeris"]
    det = prepared[tic]["unbinned"]
    got_events = event_table(_load_products(tic), det["time"], det["flux"],
                             e["period"], e["t0"], e["duration"], (e["ref_depth_ppt"] or 1.0) / 1000.0)
    got = summarise_events(got_events, e)
    assert json.dumps(got_events, sort_keys=True) == json.dumps(want["events"], sort_keys=True)
    assert json.dumps(got, sort_keys=True) == json.dumps(want["summary"], sort_keys=True)


@pytest.mark.parametrize("tic,eph", [(334678787, "survey"), (212261364, "survey")])
def test_the_reproduced_events_carry_the_numbers_the_audit_reported(prepared, tic, eph):
    """A guard on the fixture itself: these are the P5 headline numbers."""
    want = _expected(tic, f"events_{eph}")["summary"]
    assert want["n_observed"] > want["n_kept"] > 0
    assert want["det_kept"]["n"] == want["n_kept"]
    # every removed event carries at least one reason
    for ev in _expected(tic, f"events_{eph}")["events"]:
        if ev.get("observed") and ev["excluded"]:
            assert ev["exclusion_reasons"]


# ── the prompt-6 Stage A decision on a candidate that PASSED ─────────────────

def test_stage_a_decision_and_numbers_are_reproduced_for_the_stage_a_passer(prepared):
    tic = 233007823
    stored = _expected(tic, "stageA")
    assert stored["decision"] == "PASS"                    # the fixture is the passer
    det = prepared[tic]["unbinned"]
    products = _load_products(tic)
    survey_depth = stored["survey"]["depth_ppt"]
    per = {}
    for src, block in stored["per_ephemeris"].items():
        e = block["ephemeris"]
        evs = event_table(products, det["time"], det["flux"], e["period"], e["t0"], e["duration"],
                          (e["ref_depth_ppt"] or 1.0) / 1000.0)
        summ = summarise_events(evs, e)
        crit = stagea_criteria(summ["det_kept"], survey_depth)
        per[src] = (summ, crit)
        assert summ["n_observed"] == block["n_observed"], src
        assert summ["n_kept"] == block["n_kept"], src
        assert json.dumps(summ["det_kept"], sort_keys=True) == json.dumps(block["det_kept"], sort_keys=True), src
        assert json.dumps(summ["sap_kept"], sort_keys=True) == json.dumps(block["sap_kept"], sort_keys=True), src
        assert crit["criteria"] == block["criteria"], src
        assert crit["n_criteria_passed"] == block["n_criteria_passed"], src
    chosen = max(per, key=lambda s: (per[s][1]["n_criteria_passed"], per[s][1]["kept_snr"] or -1e9))
    assert chosen == stored["chosen_ephemeris"]
    assert ("PASS" if per[chosen][1]["all_passed"] else "FAIL") == stored["decision"]
    assert per[chosen][1]["criteria"] == stored["criteria"]


@pytest.mark.parametrize("tic", [334678787, 212261364])
def test_stage_a_decision_is_reproduced_for_two_candidates_that_failed(prepared, tic):
    stored = _expected(tic, "stageA")
    assert stored["decision"] == "FAIL"
    det = prepared[tic]["unbinned"]
    products = _load_products(tic)
    per = {}
    for src, block in stored["per_ephemeris"].items():
        e = block["ephemeris"]
        summ = summarise_events(
            event_table(products, det["time"], det["flux"], e["period"], e["t0"], e["duration"],
                        (e["ref_depth_ppt"] or 1.0) / 1000.0), e)
        per[src] = stagea_criteria(summ["det_kept"], stored["survey"]["depth_ppt"])
        assert per[src]["criteria"] == block["criteria"], src
    chosen = max(per, key=lambda s: (per[s]["n_criteria_passed"], per[s]["kept_snr"] or -1e9))
    assert chosen == stored["chosen_ephemeris"]
    assert per[chosen]["all_passed"] is False


# ── the prompt-6 Stage B record of the same star ─────────────────────────────

def test_stage_b_window_test_is_reproduced_for_the_stage_a_passer(prepared):
    tic = 233007823
    stored = _expected(tic, "stageB")
    det = prepared[tic]["unbinned"]
    prods = {int(p["sector"]): p for p in _load_products(tic)}
    sectors = []
    for s in sorted({int(x) for x in det["sector"]}):
        m = det["sector"] == s
        p = prods.get(s, {})
        sectors.append({"sector": s, "author": p.get("author"),
                        "cadence_s": float(p.get("cadence_s", 1e9)),
                        "time": det["time"][m], "flux": det["flux"][m]})
    pi = stored["phase_independent"]
    # the record rounds t14_hours to 3 dp for display; the test must feed the rule the same
    # unrounded value the driver did, which is expected_t14_hours at the star's R and M
    from tesshunter.audit_prep import expected_t14_hours
    st = _star(tic)
    t14 = expected_t14_hours(stored["survey_period"], st["R_star"], st["M_star"])
    assert round(t14, 3) == pi["t14_hours"]
    got = phase_independent_test(sectors, stored["survey_period"], stored["survey_depth_ppt"],
                                 t14, pi["survey_duration_days"])
    assert json.dumps(got, sort_keys=True) == json.dumps(pi, sort_keys=True)


def test_stage_b_gaia_digest_is_reproduced_from_the_cached_neighbours_record():
    tic = 233007823
    stored = _expected(tic, "stageB")
    got = gaia_flag_digest(_expected(tic, "neighbours"), stored["survey_depth_ppt"])
    assert json.dumps(got, sort_keys=True) == json.dumps(stored["gaia"], sort_keys=True)
    assert got["flags"], "this star carries star-level flags in the prompt-6 record"


# ── the fixture itself ───────────────────────────────────────────────────────

def test_the_fixture_is_one_product_per_sector_and_small_enough_to_commit():
    manifest = json.loads((FIX / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_bytes"] < 30_000_000
    for star in manifest["stars"]:
        idx = json.loads((FIX / f"tic{star['tic_id']}" / "index.json").read_text(encoding="utf-8"))
        sectors = [p["sector"] for p in idx["products"]]
        assert len(sectors) == len(set(sectors)), "one product per sector"
        assert sectors == star["sectors"]
