"""The final named configuration selects measured choices without relabeling older sets."""
from dataclasses import asdict
from tesshunter.audit_rules import P10_RULES, P8_RULES, DEFAULT_RULES, LEGACY_RULES, NAMED_RULES
from tesshunter.survey import get_config


def test_frozen_named_rules_and_prior_versions_remain_distinct():
    assert NAMED_RULES["p10.0"] is P10_RULES
    assert P10_RULES.version == "p10.0"
    assert (P8_RULES.version, DEFAULT_RULES.version, LEGACY_RULES.version) == ("p8.0", "p7.0", "p6.2")
    assert P10_RULES.secondary_gate == "bound" and P10_RULES.stagec_peak_rule == "strongest"
    assert P10_RULES.stagec_sde_robust_fallback and P10_RULES.duration_floor_cadence
    assert P10_RULES.with_options(stagec_peak_rule="significant_peak").version == "p10.0-partial"
    assert P8_RULES.with_options(verdict_tiers="p10").version == "p10.0-partial"
    assert not P8_RULES.stagec_sde_robust_fallback and not P8_RULES.duration_floor_cadence


def test_frozen_search_preserves_e_and_the_p8_ingestion_contract():
    frozen, selected, original = (get_config(name) for name in ("survey_p10", "survey_p10_both", "survey_p8"))
    fields = asdict(frozen); selected_fields = asdict(selected)
    assert fields.pop("name") == "survey_p10"
    assert selected_fields.pop("name") == "survey_p10_both"
    assert fields == selected_fields
    assert frozen.ingest_key() == selected.ingest_key() == original.ingest_key()
    assert (frozen.time_budget_s, frozen.max_planets, frozen.max_planets_total, frozen.top_n, frozen.rank_by) == (2700.0, 6, 24, 16, "snr")
    assert (original.time_budget_s, original.rank_by) == (900.0, "composite")
