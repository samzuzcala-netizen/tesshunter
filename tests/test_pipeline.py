"""Tests for the pipeline entry point (search_target + YAML config story).

All tests use synthetic in-memory light curves and monkeypatch the download
functions imported into ``tesshunter.pipeline`` — no network access.
"""

import json

import numpy as np
import lightkurve as lk
import pytest
from astropy.time import Time
from astropy import units as u

import tesshunter.pipeline as pl


# ── Synthetic data helpers ────────────────────────────────────────────────────

def _make_sector_lc(
    t_start=1000.0,
    n=1152,
    cadence_min=15.0,
    signals=(),
    noise_ppt=1.0,
    seed=1,
    sector=1,
    author="SPOC",
) -> lk.LightCurve:
    """One synthetic sector with box transits injected.

    ``signals`` is an iterable of (period_days, t0_btjd, duration_days,
    depth_ppt) tuples.
    """
    rng = np.random.default_rng(seed)
    dt = cadence_min / 1440.0
    t = t_start + np.arange(n) * dt
    flux = np.ones(n)
    for (period, t0, dur, depth_ppt) in signals:
        phase = ((t - t0 + 0.5 * period) % period) - 0.5 * period
        flux[np.abs(phase) <= 0.5 * dur] -= depth_ppt / 1000.0
    flux += rng.normal(0.0, noise_ppt / 1000.0, n)
    err = np.full(n, noise_ppt / 1000.0)
    lc = lk.LightCurve(
        time=Time(t, format="btjd", scale="tdb"),
        flux=flux * u.dimensionless_unscaled,
        flux_err=err * u.dimensionless_unscaled,
    )
    lc.meta["SECTOR"] = sector
    lc.meta["AUTHOR"] = author
    return lc


def _fake_download(lcs, events=None):
    """Build a download-stage stand-in returning the given light curves."""
    def _download(*args, **kwargs):
        lcc = lk.LightCurveCollection(list(lcs))
        lcc.tesshunter_events = list(events or [])
        return lcc
    return _download


# ── to_dict key contract (asserted by the end-to-end test) ────────────────────

TOP_LEVEL_KEYS = [
    "planets", "vetting", "provenance", "prep", "timings",
    "n_cadences_raw", "n_cadences_clean",
]
PLANET_KEYS = [
    "planet_num", "period_days", "epoch_btjd", "duration_days", "depth_ppt",
    "power", "snr", "sde", "event_completeness", "n_transits_observed",
    "single_event", "harmonic_label", "verdict",
]
VETTING_KEYS = [
    "planet_num", "verdict", "flags_hard", "flags_high", "flags_medium",
    "notes", "result",
]
PROVENANCE_KEYS = [
    "products", "units_used", "units_all", "fallback_events",
    "n_products_downloaded",
]
TIMING_KEYS = ["download", "preprocess", "detect", "vet"]


# ── (a) End-to-end recovery + key contract ────────────────────────────────────

@pytest.fixture(scope="module")
def two_planet_result():
    """One shared end-to-end run over two sectors with two injected planets.

    Module-scoped: the full search is expensive, and several tests assert
    different properties of the same result.
    """
    signals = [(2.5, 1001.0, 0.10, 12.0), (4.6, 1002.0, 0.12, 9.0)]
    mp = pytest.MonkeyPatch()
    mp.setattr(pl, "search_and_download_lc", _fake_download([
        _make_sector_lc(t_start=1000.0, sector=1, signals=signals, seed=1),
        _make_sector_lc(t_start=1013.0, sector=2, signals=signals, seed=2),
    ]))
    try:
        res = pl.search_target(
            target=999001,
            mission="TESS",
            author="SPOC",
            max_units=3,
            period_min=1.0,
            period_max=8.0,
            duration_min=0.05,
            duration_max=0.2,
            max_planets=3,
            bin_minutes=30.0,
            top_n=3,
            n_periods=500,
            min_transits=2,
            mask_width_factor=3.0,
            artifact_periods=[],
            stellar_radius_rsun=0.9,
        )
    finally:
        mp.undo()
    return res


def test_end_to_end_recovers_injected_planets_with_key_contract(two_planet_result):
    """Two injected multi-transit signals are recovered within 2% and the
    to_dict() output carries every key of the stable contract."""
    d = two_planet_result.to_dict()

    # ── Key contract ──────────────────────────────────────────────────────
    for key in TOP_LEVEL_KEYS:
        assert key in d, f"missing top-level key {key!r}"
    for key in TIMING_KEYS:
        assert key in d["timings"], f"missing timings key {key!r}"
    for key in PROVENANCE_KEYS:
        assert key in d["provenance"], f"missing provenance key {key!r}"
    assert d["planets"], "expected at least one accepted planet"
    for planet in d["planets"]:
        for key in PLANET_KEYS:
            assert key in planet, f"missing planet key {key!r}"
    for vet in d["vetting"]:
        for key in VETTING_KEYS:
            assert key in vet, f"missing vetting key {key!r}"

    # to_dict() must be json-serialisable as-is (numpy scalars converted)
    json.dumps(d)

    # ── Recovery: both periods within 2%, matched uniquely ────────────────
    recovered = [p["period_days"] for p in d["planets"]]
    for true_period in (2.5, 4.6):
        assert any(abs(p / true_period - 1.0) < 0.02 for p in recovered), (
            f"period {true_period} not recovered (got {recovered})"
        )
    for planet in d["planets"]:
        assert planet["n_transits_observed"] >= 2
        assert planet["single_event"] is False

    # ── Provenance: distinct units actually used ──────────────────────────
    assert d["provenance"]["units_used"] == [1, 2]
    assert d["provenance"]["units_all"] == [1, 2]
    assert d["provenance"]["n_products_downloaded"] == 2
    assert len(d["provenance"]["products"]) == 2
    assert d["n_cadences_raw"] == 2 * 1152
    assert d["n_cadences_clean"] > 0


def test_per_planet_vetting_present_for_every_accepted_planet(two_planet_result):
    """(d) Every accepted planet has a vetting entry with a real verdict, and
    the verdict is copied onto the planet row."""
    res = two_planet_result

    assert len(res.planets) >= 2, "expected both injected planets accepted"
    assert len(res.vetting) == len(res.planets)
    vet_by_num = {v["planet_num"]: v for v in res.vetting}
    for planet in res.planets:
        vet = vet_by_num[planet["planet_num"]]
        assert isinstance(vet["verdict"], str) and vet["verdict"]
        assert planet["verdict"] == vet["verdict"]
        assert isinstance(vet["flags_hard"], list)
        assert isinstance(vet["flags_high"], list)
        assert isinstance(vet["flags_medium"], list)
        assert isinstance(vet["result"], dict)


# ── (b) min_transits gate ─────────────────────────────────────────────────────

def _single_event_download():
    """One deep dip only — every other predicted transit is off the baseline."""
    return _fake_download([
        _make_sector_lc(
            t_start=1000.0, n=1000, cadence_min=15.0, sector=5,
            signals=[(500.0, 1005.0, 0.2, 25.0)],   # single event in-baseline
            noise_ppt=0.5, seed=7,
        ),
    ])


_SINGLE_EVENT_PARAMS = dict(
    target=999003,
    author="SPOC",
    period_min=2.0,
    period_max=9.0,
    duration_min=0.05,
    duration_max=0.3,
    max_planets=1,
    bin_minutes=30.0,
    top_n=1,
    n_periods=400,
    mask_width_factor=3.0,
)


def test_min_transits_gate_rejects_single_event_candidate(monkeypatch):
    """A single deep dip must be rejected by the n_transits gate (default 2)."""
    monkeypatch.setattr(pl, "search_and_download_lc", _single_event_download())
    res = pl.search_target(min_transits=2, **_SINGLE_EVENT_PARAMS)
    assert res.planets == [], (
        f"single-event candidate must be rejected, got {res.planets}"
    )
    assert res.vetting == []


def test_min_transits_gate_is_configurable(monkeypatch):
    """The same single dip IS accepted when min_transits=1 — proving the
    rejection above comes from the gate, not from the other gates."""
    monkeypatch.setattr(pl, "search_and_download_lc", _single_event_download())
    res = pl.search_target(min_transits=1, **_SINGLE_EVENT_PARAMS)
    assert len(res.planets) == 1
    assert res.planets[0]["n_transits_observed"] == 1
    assert res.planets[0]["single_event"] is True


# ── (c) Robustness: empty / masked-out light curves stop cleanly ──────────────

def test_no_downloadable_data_returns_clean_empty_result(monkeypatch):
    """download returning None produces an empty result, not an exception."""
    monkeypatch.setattr(pl, "search_and_download_lc", lambda *a, **k: None)
    res = pl.search_target(target=999004, author="SPOC")
    d = res.to_dict()
    assert d["planets"] == []
    assert d["vetting"] == []
    assert d["n_cadences_raw"] == 0
    for key in TIMING_KEYS:
        assert key in d["timings"]
    for key in PROVENANCE_KEYS:
        assert key in d["provenance"]
    assert any("No light curves" in note for note in d["notes"])
    json.dumps(d)


def test_tiny_light_curve_stops_before_bls(monkeypatch):
    """Fewer finite cadences than the working minimum stops the loop cleanly."""
    monkeypatch.setattr(pl, "search_and_download_lc", _fake_download([
        _make_sector_lc(t_start=1000.0, n=30, sector=1, seed=9),
    ]))
    res = pl.search_target(target=999005, author="SPOC", min_transits=2)
    assert res.planets == []
    assert any("finite cadences remain" in note for note in res.notes)


def test_mask_wider_than_period_stops_after_accepting_planet(monkeypatch):
    """WASP-18 regression: width_factor x duration > period/2 masks the whole
    orbit — the loop must accept the planet, log a note, and stop cleanly."""
    monkeypatch.setattr(pl, "search_and_download_lc", _fake_download([
        _make_sector_lc(
            t_start=1000.0, n=1152, cadence_min=10.0, sector=3,
            signals=[(1.0, 1000.5, 0.08, 15.0)], noise_ppt=1.0, seed=11,
        ),
    ]))
    res = pl.search_target(
        target=999006,
        author="SPOC",
        period_min=0.5,
        period_max=4.0,
        duration_min=0.03,
        duration_max=0.15,
        max_planets=2,
        bin_minutes=20.0,
        top_n=2,
        n_periods=400,
        min_transits=2,
        mask_width_factor=7.0,   # 7 x 0.08 d = 0.56 d half-width > P/2
        stellar_radius_rsun=1.35,
    )
    assert len(res.planets) == 1, "the planet itself must still be accepted"
    assert abs(res.planets[0]["period_days"] / 1.0 - 1.0) < 0.02
    assert len(res.vetting) == 1
    assert any("would remove" in note for note in res.notes), (
        f"expected a mask-cap stop note, got {res.notes}"
    )


# ── (e) YAML configuration story ──────────────────────────────────────────────

def test_load_search_config_parses_repo_yaml():
    """The shipped configs/search_targets.yaml maps to search_target kwargs."""
    entries = pl.load_search_config()   # default path: configs/search_targets.yaml
    assert len(entries) == 2
    assert entries[0]["target"] == 441462736
    assert entries[1]["target"] == 38846515
    for entry in entries:
        assert entry["period_min"] == pytest.approx(0.5)
        assert entry["period_max"] == pytest.approx(20.0)
        assert entry["duration_min"] == pytest.approx(0.5 / 24.0)
        assert entry["duration_max"] == pytest.approx(12.0 / 24.0)
        assert entry["top_n"] == 5
        # every entry must be consumable by search_target as-is
        assert "target" in entry


def test_search_targets_from_config_returns_one_result_per_target(monkeypatch):
    """The config runner yields a SearchTargetResult per YAML target and
    applies keyword overrides (no network: download returns None)."""
    calls = []

    def _no_data(*args, **kwargs):
        calls.append(args[0] if args else kwargs.get("target"))
        return None

    monkeypatch.setattr(pl, "search_and_download_lc", _no_data)
    results = pl.search_targets_from_config(max_planets=1)
    assert len(results) == 2
    assert calls == [441462736, 38846515]
    for res in results:
        assert isinstance(res, pl.SearchTargetResult)
        assert res.planets == []
        assert res.params.get("max_planets") == 1
        json.dumps(res.to_dict())
