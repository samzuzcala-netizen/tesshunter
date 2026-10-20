"""The p10.0 verdict tiers: every K and H condition fired and just-not-fired, the flag
list, the rule-set version, and the unchanged p8.0 behaviour (HANDOFF_P10.md section 0.1)."""
import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from tesshunter import audit_rules as R
from tesshunter import verdict_tiers as T

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

P = 3.0
T0 = 3000.4
DUR = 0.08                       # days


def _events(n=8):
    return [{"n": i, "tc_btjd": T0 + i * P, "sector": 60 + i // 4, "observed": True, "excluded": i == 1,
             "exclusion_reasons": ["scattered-light ramp (background)"] if i == 1 else [],
             "artefact_classes": ["scattered_light_ramp"] if i == 1 else []} for i in range(n)]


def _aperture_sector(sector, depth, err, n_sky=20, status=None):
    s = {"sector": sector, "n_background_pixels": n_sky,
         "measurements": {"net": {"depth_ppt": depth, "err_ppt": err}, "raw": {"depth_ppt": depth, "err_ppt": err},
                          "sky": {"depth_ppt": 0.0, "err_ppt": err}}}
    if status:
        s["status"] = status
    return s


def _aperture_arrays(sectors, correlated):
    """Raw/sky series in which the event windows are (or are not) correlated."""
    arrays = {}
    rng = np.random.default_rng(1)
    for sec in sectors:
        t = 3000.0 + np.arange(4000) * 200 / 86400
        sky = rng.normal(0, 1e-3, t.size)
        raw = sky.copy() if correlated else rng.normal(0, 1e-3, t.size)
        arrays[f"s{sec}_time"], arrays[f"s{sec}_raw"], arrays[f"s{sec}_sky"] = t, 1 + raw, 1 + sky
    return arrays


def _difference_sector(sector, row, col, value):
    return {"sector": sector, "maximum_pixels": {"primary": {"row": row, "column": col, "difference_e_per_s": value}},
            "gaia_positions": [{"source_id": 1, "x": 10.0, "y": 10.0, "G": 14.0, "label": "T"},
                               {"source_id": 2, "x": 13.0, "y": 10.0, "G": 15.5, "label": "2"}]}


@pytest.fixture
def clean():
    """A candidate for which every condition is measured and none holds: SUBMIT."""
    fit = {"adopted": {"period": P, "t0_btjd": T0, "t14_hours": DUR * 24, "depth_avg_ppt": 10.0, "depth_err_ppt": 0.5,
                       "rp_rearth": 2.5, "rp_rs": 0.05, "b": 0.3, "b_err": 0.1, "t14_err_hours": 0.1, "grazing": False},
           "free_fit": {"rho_fit_cgs": 10.0}, "stellar": {"rho_cgs": 10.0}, "delta_chi2_prior_minus_free": 1.0,
           "uncertainty_issues": [], "odd_even": {"sigma": 0.8, "odd": {"n_transits": 4}, "even": {"n_transits": 4}}}
    return {
        "key": "tic1_P3.0000", "period": P, "depth_ppt": 10.0,
        "stageA": {"decision": "PASS", "survey_depth_ppt": 10.0, "chosen_ephemeris": "tls",
                   "per_ephemeris": {"tls": {"det_kept": {"weighted_mean_depth_ppt": 9.0, "err_ppt": 0.6},
                                             "events": _events(), "n_observed": 8, "n_excluded": 1, "n_kept": 7,
                                             "strongest_event": {"excluded": False}, "criteria": {}}}},
        "secondary": {"gate": "PASS", "thresholds": {"gate_mode": "bound"}},
        "stageB": {"phase_independent": {"excluded": False, "n_sectors_tested": 3}},
        "stageC": {"decision": "PASS", "reason": "strongest peak within 1%", "thresholds": {}},
        "fit": fit,
        "expensive": {"fpp": {"available": True, "fpp": 0.01, "nfpp": 0.001, "sectors": [60, 61, 62]},
                      "centroid": {"available": True, "per_sector": [{"sector": 60, "sigma": 0.5, "total_shift_px": 0.01}]},
                      "fpp_uniform": False},
        "neighbours": {"gaia": {"target": {"source_id": 1, "ruwe": 1.0}, "neighbours": [
            {"source_id": 2, "sep_arcsec": 30.0, "sep_px": 1.4, "G": 15.5, "delta_mag": 1.5,
             "max_observed_depth_ppt_total_eclipse": 200.0}]},
                       "vsx": {"n_within_1arcmin": 0, "objects": []}, "simbad": {"objects": []}},
        "crossmatch_star": {"status": "CLEAN", "tic_matches": [], "neighbour_matches": []},
        "candidates": [{"period_days": P, "depth_ppt": 10.0, "snr": 12.0},
                       {"period_days": 7.1, "depth_ppt": 2.0, "snr": 6.0}],
        "catalogue_periods": [],
        "aperture": {"sectors": [_aperture_sector(60, 4.0, 0.8), _aperture_sector(61, 3.5, 0.8), _aperture_sector(62, 4.5, 0.8)]},
        "aperture_arrays": _aperture_arrays([60, 61, 62], correlated=False),
        "difference": {"sectors": [_difference_sector(60, 10, 10, 5.0), _difference_sector(61, 10, 10, 5.0)]},
        "difference_arrays": {f"s{s}_primary_event_scatter": np.full((21, 21), 1.0) for s in (60, 61)},
        "review": None,
    }


def verdict(inputs):
    ev = T.evaluate(inputs)
    return ev["verdict"], ev["deciding_condition"], ev


# ── the clean candidate and the flag list ────────────────────────────────────
def test_clean_candidate_is_submit_with_every_flag(clean):
    v, d, ev = verdict(clean)
    assert (v, d) == ("SUBMIT", None)
    assert ev["not_measurable"] == []
    assert list(ev["flags"]) == list(T.F_ORDER)
    assert ev["flags"]["F1"][0]["required_eclipse_fraction"] == pytest.approx(10.0 / 200.0)
    assert ev["flags"]["F5"]["localisation"] == "unlocalised" and ev["flags"]["F5"]["n_sectors_measurable"] == 3
    assert ev["flags"]["F6"] == [{"period_days": 7.1, "depth_ppt": 2.0, "snr": 6.0, "verdict": None, "stitch_snr": None, "passes_pregate": None}]
    assert ev["flags"]["F8"]["removed_by_class"]["scattered_light_ramp"] == 1 and ev["flags"]["F8"]["n_kept"] == 7
    assert "Seeing-limited ground photometry" in ev["flags"]["F9"] and "not as a validated planet" in ev["flags"]["F9"]
    assert ev["reference_depth"]["source"] == "fit.adopted.depth_avg_ppt"
    assert ev["thresholds"] == R.tier_thresholds()


# ── K0 .. K4: the stage decisions ────────────────────────────────────────────
@pytest.mark.parametrize("field,fail,ok", [("stageA", {"decision": "FAIL"}, {"decision": "PASS"}),
                                           ("secondary", {"gate": "FAIL"}, {"gate": "PASS"}),
                                           ("stageC", {"decision": "FAIL"}, {"decision": "PASS"})])
def test_stage_decisions_kill(clean, field, fail, ok):
    name = {"stageA": "K1", "secondary": "K2", "stageC": "K4"}[field]
    bad = copy.deepcopy(clean); bad[field].update(fail)
    assert verdict(bad)[:2] == ("KILL", name)
    good = copy.deepcopy(clean); good[field].update(ok)
    assert verdict(good)[:2] == ("SUBMIT", None)
    missing = copy.deepcopy(clean); missing[field] = None
    assert verdict(missing)[2]["conditions"][name]["fired"] is None


def test_k0_hard_stop_and_k3_exclusion(clean):
    rej = copy.deepcopy(clean); rej["crossmatch_star"]["status"] = "REJECT"
    assert verdict(rej)[:2] == ("KILL", "K0")
    flag = copy.deepcopy(clean); flag["crossmatch_star"]["status"] = "FLAG"
    assert verdict(flag)[:2] == ("SUBMIT", None)
    red = copy.deepcopy(clean); red["crossmatch_star"]["status"] = "KNOWN_STATUS_REDACTED"
    assert verdict(red)[2]["conditions"]["K0"]["fired"] is None and verdict(red)[0] == "SUBMIT"
    ex = copy.deepcopy(clean); ex["stageB"]["phase_independent"]["excluded"] = True
    assert verdict(ex)[:2] == ("KILL", "K3")


# ── K5: aliases ──────────────────────────────────────────────────────────────
def test_k5_deeper_signal_alias_fires_only_when_deep_and_aliased(clean):
    deep = copy.deepcopy(clean); deep["candidates"].append({"period_days": P / 2, "depth_ppt": 40.0})
    v, d, ev = verdict(deep)
    assert (v, d) == ("KILL", "K5") and ev["conditions"]["K5"]["matches"][0]["ratio"] == "2:1"
    shallow = copy.deepcopy(clean); shallow["candidates"].append({"period_days": P / 2, "depth_ppt": 3.0})
    assert verdict(shallow)[:2] == ("SUBMIT", None)
    deep_not_alias = copy.deepcopy(clean); deep_not_alias["candidates"].append({"period_days": P / 2.05, "depth_ppt": 40.0})
    assert verdict(deep_not_alias)[:2] == ("SUBMIT", None)


def test_k5_catalogue_period_boundary(clean):
    hit = copy.deepcopy(clean); hit["catalogue_periods"] = [{"source": "tess_eb", "label": "x", "period": P * 1.0099, "sep_arcsec": 5.0}]
    assert verdict(hit)[:2] == ("KILL", "K5")
    # the ratio is candidate / catalogue, as in audit_p5._match: P x 1.0102 gives 0.9899, outside 1%
    miss = copy.deepcopy(clean); miss["catalogue_periods"] = [{"source": "tess_eb", "label": "x", "period": P * 1.0102, "sep_arcsec": 5.0}]
    assert verdict(miss)[:2] == ("SUBMIT", None)
    assert T.alias_ratio(P, P / 1.0099, include_unity=True) == "1:1" and T.alias_ratio(P, P / 1.0101, include_unity=True) is None
    third = copy.deepcopy(clean); third["catalogue_periods"] = [{"source": "vsx", "label": "v", "period": P * 3, "sep_arcsec": 40.0}]
    assert verdict(third)[2]["conditions"]["K5"]["matches"][0]["ratio"] == "1:3"


# ── K6: odd/even ─────────────────────────────────────────────────────────────
def test_k6_odd_even_boundary(clean):
    at = copy.deepcopy(clean); at["fit"]["odd_even"]["sigma"] = R.TIER_ODD_EVEN_SIGMA
    assert verdict(at)[:2] == ("SUBMIT", None)
    over = copy.deepcopy(clean); over["fit"]["odd_even"]["sigma"] = np.nextafter(R.TIER_ODD_EVEN_SIGMA, np.inf)
    assert verdict(over)[:2] == ("KILL", "K6")
    few = copy.deepcopy(over); few["fit"]["odd_even"]["odd"]["n_transits"] = 1
    assert verdict(few)[:2] == ("SUBMIT", None)


# ── K7: pixels ───────────────────────────────────────────────────────────────
def test_k7a_dimming_on_a_neighbour_needs_two_sectors_above_three_sigma(clean):
    two = copy.deepcopy(clean)
    two["difference"]["sectors"] = [_difference_sector(60, 10, 13, 3.01), _difference_sector(61, 10, 13, 3.01)]
    v, d, ev = verdict(two)
    assert (v, d) == ("KILL", "K7") and ev["conditions"]["K7"]["n_elsewhere"] == 2
    one = copy.deepcopy(clean)
    one["difference"]["sectors"] = [_difference_sector(60, 10, 13, 3.01), _difference_sector(61, 10, 10, 3.01)]
    assert verdict(one)[:2] == ("SUBMIT", None)
    weak = copy.deepcopy(clean)
    weak["difference"]["sectors"] = [_difference_sector(60, 10, 13, 3.0), _difference_sector(61, 10, 13, 3.0)]
    assert verdict(weak)[:2] == ("SUBMIT", None)
    near_target = copy.deepcopy(clean)          # 1.4 px from the target: not "elsewhere"
    near_target["difference"]["sectors"] = [_difference_sector(60, 10, 11.4, 9.0), _difference_sector(61, 10, 11.4, 9.0)]
    assert verdict(near_target)[:2] == ("SUBMIT", None)


def test_k7a_searches_the_target_neighbourhood_and_records_the_literal_form(clean):
    # a 9-sigma whole-cutout maximum 10 px from the target on a resolved star: the literal
    # pre-registered form fires, the amended (3 px) form does not; both are on the record
    far = copy.deepcopy(clean)
    for s in far["difference"]["sectors"]:
        s["maximum_pixels"]["primary"] = {"row": 10, "column": 20, "difference_e_per_s": 9.0}
        s["gaia_positions"].append({"source_id": 3, "x": 20.0, "y": 10.0, "G": 20.5, "label": "3"})
    for sec in (60, 61):
        img = np.zeros((21, 21)); img[10, 20] = 9.0; img[10, 12] = 1.0
        far["difference_arrays"][f"s{sec}_primary_difference"] = img
    v, d, ev = verdict(far)
    k7 = ev["conditions"]["K7"]
    assert (v, d) == ("SUBMIT", None)
    assert k7["n_elsewhere"] == 0 and k7["n_elsewhere_literal"] == 2
    assert all(s["literal"]["fired"] and s["literal"]["dist_target_px"] == 10.0 for s in k7["elsewhere"])
    assert all(s["fired"] is False and s["column"] == 12 for s in k7["elsewhere"])
    # the local maximum on the neighbour 3 px away at 3.01 sigma fires under the amended form
    local = copy.deepcopy(far)
    for sec in (60, 61):
        local["difference_arrays"][f"s{sec}_primary_difference"][10, 13] = 3.01
    v, d, ev = verdict(local)
    assert (v, d) == ("KILL", "K7") and ev["conditions"]["K7"]["n_elsewhere"] == 2
    # without the difference image, a stored maximum outside the search radius is not measurable
    blind = copy.deepcopy(far); blind["difference_arrays"] = {f"s{s}_primary_event_scatter": np.full((21, 21), 1.0) for s in (60, 61)}
    assert all(s["fired"] is None for s in verdict(blind)[2]["conditions"]["K7"]["elsewhere"])


def test_k7b_absence_is_an_exclusion_of_the_diluted_depth(clean):
    # D_ref 10 ppt, dilution allowance 0.5 -> 5 ppt; sigma 0.5 -> absence below 3.5 ppt
    bad = copy.deepcopy(clean)
    bad["aperture"]["sectors"] = [_aperture_sector(60, np.nextafter(3.5, -np.inf), 0.5), _aperture_sector(61, 3.0, 0.5), _aperture_sector(62, 5.0, 0.5)]
    v, d, ev = verdict(bad)
    assert (v, d) == ("KILL", "K7") and ev["conditions"]["K7"]["n_absent"] == 2
    edge = copy.deepcopy(clean)
    edge["aperture"]["sectors"] = [_aperture_sector(60, 3.5, 0.5), _aperture_sector(61, 3.5, 0.5)]
    assert verdict(edge)[:2] == ("SUBMIT", None)
    unmeasurable = copy.deepcopy(clean)         # 5 ppt diluted depth < 3 x 2 ppt: neither clause
    unmeasurable["aperture"]["sectors"] = [_aperture_sector(60, 0.0, 2.0), _aperture_sector(61, 0.0, 2.0)]
    v, d, ev = verdict(unmeasurable)
    assert (v, d) == ("SUBMIT", None) and all(s["fired"] is None for s in ev["conditions"]["K7"]["absent"])
    no_sky = copy.deepcopy(clean)
    no_sky["aperture"]["sectors"] = [_aperture_sector(60, 0.0, 0.5, n_sky=15), _aperture_sector(61, 0.0, 0.5, status="unavailable")]
    assert all(s["fired"] is None for s in verdict(no_sky)[2]["conditions"]["K7"]["absent"])


# ── K8: a stellar companion ──────────────────────────────────────────────────
def test_k8_radius_and_density_boundaries(clean):
    limit = R.TIER_MAX_RADIUS_RJUP * R.R_JUP_IN_R_EARTH
    big = copy.deepcopy(clean); big["fit"]["adopted"]["rp_rearth"] = np.nextafter(limit, np.inf)
    assert verdict(big)[:2] == ("KILL", "K8")
    at = copy.deepcopy(clean); at["fit"]["adopted"]["rp_rearth"] = limit
    assert verdict(at)[:2] == ("SUBMIT", None)
    dens = copy.deepcopy(clean)
    dens["fit"].update({"delta_chi2_prior_minus_free": R.TIER_DENSITY_REJECT_DCHI2, "free_fit": {"rho_fit_cgs": 4.9}})
    assert verdict(dens)[:2] == ("KILL", "K8")
    guard = copy.deepcopy(dens); guard["fit"]["free_fit"]["rho_fit_cgs"] = 5.0
    assert verdict(guard)[:2] == ("SUBMIT", None)
    grazing = copy.deepcopy(dens); grazing["fit"]["adopted"].update({"b": 0.96, "rp_rs": 0.05})
    assert verdict(grazing)[:2] == ("SUBMIT", None)
    weak = copy.deepcopy(dens); weak["fit"]["delta_chi2_prior_minus_free"] = np.nextafter(R.TIER_DENSITY_REJECT_DCHI2, 0)
    assert verdict(weak)[:2] == ("SUBMIT", None)


# ── K9: the artefact criterion plus the reviewer ─────────────────────────────
def _k9_case(clean, correlated=True, disagree=True, review=True):
    c = copy.deepcopy(clean)
    c["aperture_arrays"] = _aperture_arrays([60, 61, 62], correlated=correlated)
    if disagree:                                 # D_ref 10 +/- 0.5, sigma 0.8: too deep beyond 3 sigma_tot
        c["aperture"]["sectors"] = [_aperture_sector(60, 16.0, 0.8), _aperture_sector(61, 16.0, 0.8), _aperture_sector(62, 4.0, 0.8)]
    c["review"] = {"k9_artefact": True, "reason": "events track the sky"} if review else None
    return c


def test_k9_fires_only_with_the_criterion_and_the_reviewer(clean):
    v, d, ev = verdict(_k9_case(clean))
    assert (v, d) == ("KILL", "K9") and ev["conditions"]["K9"]["criterion_holds"]
    assert ev["conditions"]["K9"]["n_correlated"] == 3 and ev["conditions"]["K9"]["n_disagreeing"] == 2
    no_review = verdict(_k9_case(clean, review=False))[2]
    assert no_review["conditions"]["K9"]["fired"] is False and no_review["conditions"]["K9"]["criterion_holds"]
    assert no_review["verdict"] == "SUBMIT"
    no_corr = verdict(_k9_case(clean, correlated=False))[2]
    assert no_corr["conditions"]["K9"]["fired"] is False and not no_corr["conditions"]["K9"]["criterion_holds"]
    assert "NOT applied" in no_corr["conditions"]["K9"]["detail"]
    no_dis = verdict(_k9_case(clean, disagree=False))[2]
    assert no_dis["conditions"]["K9"]["fired"] is False and no_dis["conditions"]["K9"]["n_disagreeing"] == 0


def test_k9_correlation_boundary():
    t = 3000.0 + np.arange(400) * 200 / 86400
    rng = np.random.default_rng(3)
    x = rng.normal(size=t.size)
    x = (x - x.mean()) / x.std()
    y = rng.normal(size=t.size)
    y = y - y.mean()
    y = y - x * (x @ y) / (x @ x)                # orthogonal to the centred x
    y /= y.std()
    for target in (R.TIER_K9_CORRELATION - 1e-3, R.TIER_K9_CORRELATION + 1e-3):
        sky = target * x + np.sqrt(1 - target ** 2) * y
        rec = T.k9_sector(t, 1 + 1e-3 * x, 1 + 1e-3 * sky, 1000.0, t[0], 100.0)
        assert rec["r"] == pytest.approx(target, abs=1e-4)
        assert rec["fired"] == (target > R.TIER_K9_CORRELATION)
    assert T.k9_sector(t[:5], np.ones(5), np.ones(5), 1000.0, t[0], 100.0)["fired"] is None


def test_k9b_disagreement_forms():
    sec = _aperture_sector(60, 0.0, 0.5)
    ref, e = 10.0, 0.5
    tot = np.sqrt(0.5 ** 2 + e ** 2)
    sec["measurements"]["net"]["depth_ppt"] = ref + 3 * tot
    assert T.k9b_sector(sec, ref, e)["fired"] is False
    sec["measurements"]["net"]["depth_ppt"] = np.nextafter(ref + 3 * tot, np.inf)
    assert T.k9b_sector(sec, ref, e)["too_deep"]
    sec["measurements"]["net"]["depth_ppt"] = 0.5 * ref - 3 * tot
    assert T.k9b_sector(sec, ref, e)["fired"] is False
    sec["measurements"]["net"]["depth_ppt"] = np.nextafter(0.5 * ref - 3 * tot, -np.inf)
    assert T.k9b_sector(sec, ref, e)["too_shallow"]
    sec["measurements"]["net"]["depth_ppt"] = np.nextafter(-3 * 0.5, -np.inf)
    assert T.k9b_sector(sec, 100.0, 0.1)["brightening"]


# ── H1 .. H4 ─────────────────────────────────────────────────────────────────
def test_h1_nfpp_boundary_and_uniform(clean):
    at = copy.deepcopy(clean); at["expensive"]["fpp"]["nfpp"] = R.TIER_NFPP_HOLD
    assert verdict(at)[:2] == ("HOLD", "H1")
    below = copy.deepcopy(clean); below["expensive"]["fpp"]["nfpp"] = np.nextafter(R.TIER_NFPP_HOLD, 0)
    assert verdict(below)[:2] == ("SUBMIT", None)
    uni = copy.deepcopy(at); uni["expensive"]["fpp_uniform"] = True
    v, d, ev = verdict(uni)
    assert ev["conditions"]["H1"]["fired"] is None and v == "SUBMIT" and ev["flags"]["F4"]["fpp_uniform"]


def test_h2_unconverged_or_grazing_rail(clean):
    issue = copy.deepcopy(clean); issue["fit"]["uncertainty_issues"] = ["singular fit covariance"]
    assert verdict(issue)[:2] == ("HOLD", "H2")
    rail = copy.deepcopy(clean); rail["fit"]["adopted"].update({"grazing": True, "b_err": np.nextafter(R.TIER_GRAZING_B_ERR, 1.0)})
    assert verdict(rail)[:2] == ("HOLD", "H2")
    usable = copy.deepcopy(clean); usable["fit"]["adopted"].update({"grazing": True, "b_err": R.TIER_GRAZING_B_ERR})
    assert verdict(usable)[:2] == ("SUBMIT", None)
    long_err = copy.deepcopy(usable); long_err["fit"]["adopted"]["t14_err_hours"] = usable["fit"]["adopted"]["t14_hours"]
    assert verdict(long_err)[:2] == ("HOLD", "H2")
    # a grazing-rail fit uses the Stage A depth as the reference depth
    assert verdict(rail)[2]["reference_depth"]["source"].startswith("stageA")


def test_h3_operational_holds_until_every_measurement_ran(clean):
    for field in ("expensive", "difference", "aperture"):
        c = copy.deepcopy(clean); c[field] = None
        assert verdict(c)[:2] == ("HOLD", "H3"), field
    c = copy.deepcopy(clean); c["fit"] = {"error": "ValueError: boom"}
    assert verdict(c)[:2] == ("HOLD", "H3")
    c = copy.deepcopy(clean); c["expensive"]["centroid"] = {"available": False, "error": "timeout"}
    assert verdict(c)[:2] == ("HOLD", "H3")


def test_h4_vsx_on_target_without_alias(clean):
    def with_vsx(type_, period, sep):
        c = copy.deepcopy(clean)
        c["neighbours"]["vsx"] = {"n_within_1arcmin": 1, "objects": [{"Name": "V1", "Type": type_, "Period": period, "sep_arcsec": sep}]}
        return c
    assert verdict(with_vsx("EA", 11.7, 10.0))[:2] == ("HOLD", "H4")
    assert verdict(with_vsx("EW/KW", 11.7, 10.0))[:2] == ("HOLD", "H4")
    assert verdict(with_vsx("ROT", 11.7, 10.0))[:2] == ("SUBMIT", None)
    assert verdict(with_vsx("EA", 11.7, np.nextafter(R.TIER_VSX_TARGET_RADIUS_ARCSEC, 100)))[:2] == ("SUBMIT", None)
    redacted = verdict(with_vsx(None, None, 5.0))[2]
    assert redacted["conditions"]["H4"]["fired"] is None
    # a period match is K5 (the catalogue list carries the VSX period), not H4
    c = with_vsx("EA", P, 5.0); c["catalogue_periods"] = T.catalogue_periods_from(c["neighbours"], c["crossmatch_star"])
    assert verdict(c)[:2] == ("KILL", "K5")


def test_kill_precedes_hold_and_order_is_k1_first(clean):
    c = copy.deepcopy(clean)
    c["expensive"]["fpp"]["nfpp"] = 0.9
    c["stageC"]["decision"] = "FAIL"
    c["stageA"]["decision"] = "FAIL"
    v, d, ev = verdict(c)
    assert (v, d) == ("KILL", "K1") and ev["conditions"]["K4"]["fired"] and ev["conditions"]["H1"]["fired"]


# ── the rule sets and the unchanged p8.0 path ────────────────────────────────
def test_rule_set_versions_and_p8_unchanged():
    assert R.P10_RULES.version == "p10.0" and R.P10_RULES.verdict_tiers == "p10"
    assert R.P10_RULES == R.P8_RULES.with_options(verdict_tiers="p10", stagec_peak_rule="strongest",
                                                 stagec_sde_robust_fallback=True, duration_floor_cadence=True)
    assert R.P8_RULES.version == "p8.0" and R.P8_RULES.verdict_tiers == "p8"
    assert R.DEFAULT_RULES.version == "p7.0" and R.LEGACY_RULES.version == "p6.2" and R.RULES_VERSION == "p7.0"
    assert R.P10_RULES.with_options(stagec_peak_rule="significant_peak").version == "p10.0-partial"
    assert R.P8_RULES.with_options(duration_floor_cadence=True).version == "p10.0-partial"
    assert R.thresholds(R.P8_RULES)["tiers"] is None and R.thresholds(R.P10_RULES)["tiers"] == R.tier_thresholds()
    assert set(R.NAMED_RULES) == {"p6.2", "p7.0", "p8.0", "p10.0"}
    assert "p10.0" in R.KNOWN_RULES_VERSIONS and "p10.0-partial" in R.KNOWN_RULES_VERSIONS


def test_revet_provisional_verdict_p8_path_unchanged_and_p10_reads_tiers():
    import revet_p6 as V
    rec = {"crossmatch": {"star": {"status": "REJECT"}}, "gaia": {"flags": []}, "fit": {"adopted": {"delta_chi2_vs_flat": 100}}}
    assert V.provisional_verdict(rec)[0] == "KILL"
    rec["crossmatch"]["star"]["status"] = "CLEAN"
    rec["stageB"] = {"max_verdict": "HOLD"}
    assert V.provisional_verdict(rec)[0] == "HOLD"
    rec["stageB"] = {"max_verdict": "SUBMIT"}
    assert V.provisional_verdict(rec)[0] == "SUBMIT"
    tiers = {"verdict": "KILL", "deciding_condition": "K7", "conditions": {"K7": {"detail": "elsewhere"}}}
    assert V.provisional_verdict({**rec, "tiers": tiers}) == ("KILL", "K7 (elsewhere)")
    assert V.provisional_verdict({**rec, "tiers": {"verdict": "SUBMIT", "deciding_condition": None, "conditions": {}}})[0] == "SUBMIT"


def test_load_inputs_reads_a_root_and_the_p8_pixel_review(tmp_path, clean):
    root = tmp_path / "root"
    key, tic = "tic1_P3.0000", 1
    for folder in ("stageA", "secondary", "stageB", "stageC", "fit", "expensive", "neighbours", "eb_screen", "pixel_followup"):
        (root / folder).mkdir(parents=True)
    for folder in ("stageA", "secondary", "stageB", "stageC", "fit", "expensive"):
        (root / folder / f"{key}.json").write_text(json.dumps(clean[folder]))
    (root / "neighbours" / f"tic{tic}.json").write_text(json.dumps(clean["neighbours"]))
    (root / f"crossmatch_{root.name}.json").write_text(json.dumps({"per_star": {"1": clean["crossmatch_star"]}}))
    (root / "candidates.csv").write_text("tic_id,period_days,depth_ppt,snr\n1,3.0,10.0,12\n1,7.1,2.0,6\n")
    (root / "eb_screen" / f"{key}_target_aperture.json").write_text(json.dumps(clean["aperture"]))
    np.savez(root / "eb_screen" / f"{key}_target_aperture.npz", **clean["aperture_arrays"])
    (root / "eb_screen" / f"{key}_fit_difference.json").write_text(json.dumps(clean["difference"]))
    np.savez(root / "eb_screen" / f"{key}_fit_difference.npz", **clean["difference_arrays"])
    (root / "pixel_followup" / f"{key}.json").write_text(json.dumps({"recommended_verdict": "KILL", "assessment": "sky-tracking"}))
    inputs = T.load_inputs(root, key, tic, P)
    assert inputs["depth_ppt"] == 10.0 and inputs["review"]["k9_artefact"] is True
    assert inputs["crossmatch_star"]["status"] == "CLEAN" and len(inputs["candidates"]) == 2
    assert inputs["catalogue_periods"] == []
    ev = T.evaluate(inputs)
    assert ev["verdict"] == "SUBMIT" and ev["not_measurable"] == []
