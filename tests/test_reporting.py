"""Tests for report generation and candidate-summary upsert (no network)."""

import pandas as pd
import pytest

from tesshunter.centroid import CentroidResult
from tesshunter.contamination import ContaminationResult, NeighbourStar
from tesshunter.preprocessing import PreprocessingRecord
from tesshunter.reporting import append_to_candidate_summary, generate_report
from tesshunter.vetting import VettingResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidates_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "period_days": 4.0,
                "epoch_btjd": 1350.5,
                "duration_days": 0.12,
                "depth_ppt": 8.0,
                "power": 3.2e-6,
                "snr": 12.5,
            }
        ]
    )


def _make_prep_record() -> PreprocessingRecord:
    return PreprocessingRecord(
        original_cadences=1000,
        after_nan_removal=990,
        after_quality_mask=985,
        after_sigma_clip=980,
        normalised=True,
        flattened=True,
        flatten_window_length=0.5,
    )


def _generate(tmp_path, vetting=None, **kwargs):
    """Call generate_report with minimal synthetic inputs; return report text."""
    if vetting is None:
        vetting = VettingResult(verdict="promising planet candidate")
    path = generate_report(
        target_id="TIC 123456",
        tic_id=123456,
        sectors=[5],
        prep_record=_make_prep_record(),
        candidates_df=_make_candidates_df(),
        vetting=vetting,
        crossmatch_summary="No catalog match found.",
        plot_paths={},
        output_dir=tmp_path,
        **kwargs,
    )
    return path, path.read_text(encoding="utf-8")


def _make_neighbour(risk: str = "HIGH") -> NeighbourStar:
    return NeighbourStar(
        tic_id=987654,
        separation_arcsec=42.0,
        separation_px=2.0,
        tmag=12.5,
        delta_tmag=2.5,
        flux_ratio=0.1,
        leakage_fraction=0.41,
        effective_flux_in_aperture=0.041,
        raw_undiluted_depth_ppt=90.0,
        leakage_corrected_depth_ppt=220.0,
        risk_level=risk,
        is_viable_contaminant=True,
    )


# ---------------------------------------------------------------------------
# R2 — to_markdown fallback when tabulate is missing
# ---------------------------------------------------------------------------

def test_report_survives_missing_tabulate(tmp_path, monkeypatch):
    """Report generation must not hard-fail when tabulate is unavailable."""

    def _raise_import_error(self, *args, **kwargs):
        raise ImportError("Missing optional dependency 'tabulate'.")

    monkeypatch.setattr(pd.DataFrame, "to_markdown", _raise_import_error)

    path, text = _generate(tmp_path)
    assert path.exists()
    # The raw-candidates table must still appear, rendered via to_string.
    assert "Raw BLS periodogram peaks" in text
    assert "period_days" in text


def test_report_uses_markdown_when_tabulate_present(tmp_path):
    path, text = _generate(tmp_path)
    assert path.exists()
    # tabulate is installed in the test env, so no fenced fallback block
    # should be needed for the candidates table.
    assert "period_days" in text


# ---------------------------------------------------------------------------
# R1 — centroid / contamination sections and flag lists
# ---------------------------------------------------------------------------

def test_report_says_not_run_without_results(tmp_path):
    _, text = _generate(tmp_path)
    assert "TODO" not in text
    assert text.count("not run") >= 2  # centroid + contamination
    assert "Centroid analysis" in text
    assert "Nearby-star contamination" in text


def test_report_renders_centroid_and_contamination_results(tmp_path):
    centroid = CentroidResult(
        available=True,
        col_shift_px=0.11,
        row_shift_px=0.05,
        total_shift_px=0.1208,
        shift_arcsec=2.54,
        sigma=4.2,
        n_in_transit=40,
        n_out_transit=400,
        flagged=True,
        note="Shift exceeds 3-sigma threshold.",
    )
    contamination = ContaminationResult(
        available=True,
        n_neighbours_checked=3,
        n_ruled_out=2,
        flagged=True,
        high_risk_neighbours=[_make_neighbour("HIGH")],
        all_neighbours=[_make_neighbour("HIGH")],
        note="One neighbour can reproduce the observed depth.",
    )

    _, text = _generate(
        tmp_path, centroid_result=centroid, contamination_result=contamination
    )

    assert "TODO" not in text
    # Centroid values rendered
    assert "0.1208" in text
    assert "4.2" in text
    assert "FAIL" in text
    # Contamination neighbour table rendered
    assert "987654" in text
    assert "HIGH" in text
    assert "3 neighbour(s) checked" in text or "n_neighbours" in text


def test_report_renders_flag_lists(tmp_path):
    vet = VettingResult(
        verdict="likely false positive",
        hard_veto_flags=["depth 150.0 ppt exceeds veto limit"],
        high_risk_flags=["secondary eclipse detected"],
        medium_flags=["single sector only"],
    )
    _, text = _generate(tmp_path, vetting=vet)
    assert "HARD VETO" in text
    assert "depth 150.0 ppt exceeds veto limit" in text
    assert "HIGH RISK" in text
    assert "secondary eclipse detected" in text
    assert "MEDIUM" in text
    assert "single sector only" in text


def test_report_derives_flags_from_booleans_when_lists_empty(tmp_path):
    vet = VettingResult(
        verdict="likely false positive",
        depth_too_deep=True,
        secondary_eclipse_detected=True,
        single_sector_only=True,
    )
    # Lists left empty on purpose — the report must fall back to booleans.
    _, text = _generate(tmp_path, vetting=vet)
    assert "HARD VETO" in text
    assert "HIGH RISK" in text
    assert "MEDIUM" in text


def test_depth_row_label_states_real_threshold(tmp_path):
    _, text = _generate(tmp_path)
    assert "< 50 ppt" not in text
    assert "100 ppt" in text

    # Radius-aware label when the stellar radius is known
    vet = VettingResult(
        verdict="promising planet candidate", stellar_radius_rsun=0.30
    )
    _, text_radius = _generate(tmp_path, vetting=vet)
    assert "< 50 ppt" not in text_radius
    assert "radius-aware" in text_radius


# ---------------------------------------------------------------------------
# R3 — candidate summary upsert
# ---------------------------------------------------------------------------

def _append(csv_path, tic_id=123, period=4.0, snr=10.0, power=3.2e-6,
            verdict="candidate"):
    append_to_candidate_summary(
        tic_id=tic_id,
        target_id=f"TIC {tic_id}",
        sectors=[5],
        period_days=period,
        depth_ppt=8.0,
        duration_hours=2.9,
        bls_power=power,
        snr=snr,
        verdict=verdict,
        crossmatch_summary="none",
        summary_csv=csv_path,
    )


def test_summary_upsert_replaces_rerun_of_same_signal(tmp_path):
    csv_path = tmp_path / "summary.csv"
    _append(csv_path, period=4.0, snr=10.0, verdict="candidate")
    # Re-run: same TIC, period within 1 % — must REPLACE, not append.
    _append(csv_path, period=4.02, snr=8.0, verdict="likely false positive")

    df = pd.read_csv(csv_path)
    assert len(df) == 1
    assert df.iloc[0]["verdict"] == "likely false positive"
    assert df.iloc[0]["period_days"] == pytest.approx(4.02)
    assert df.iloc[0]["snr"] == pytest.approx(8.0)


def test_summary_keeps_distinct_periods_and_targets(tmp_path):
    csv_path = tmp_path / "summary.csv"
    _append(csv_path, tic_id=123, period=4.0, snr=10.0)
    _append(csv_path, tic_id=123, period=8.0, snr=6.0)    # different planet
    _append(csv_path, tic_id=456, period=4.0, snr=50.0)   # different target

    df = pd.read_csv(csv_path)
    assert len(df) == 3


def test_summary_power_not_floored_to_zero(tmp_path):
    csv_path = tmp_path / "summary.csv"
    _append(csv_path, power=3.2e-6)
    df = pd.read_csv(csv_path)
    assert df.iloc[0]["bls_power"] == pytest.approx(3.2e-6)
    assert df.iloc[0]["bls_power"] > 0.0


def test_summary_sorted_by_snr_descending(tmp_path):
    csv_path = tmp_path / "summary.csv"
    _append(csv_path, tic_id=1, period=2.0, snr=5.0)
    _append(csv_path, tic_id=2, period=3.0, snr=50.0)
    _append(csv_path, tic_id=3, period=5.0, snr=20.0)

    df = pd.read_csv(csv_path)
    assert list(df["snr"]) == sorted(df["snr"], reverse=True)
    assert df.iloc[0]["tic_id"] == 2


def test_summary_writes_passed_verdict_verbatim(tmp_path):
    csv_path = tmp_path / "summary.csv"
    _append(csv_path, tic_id=9, period=6.0, verdict="ambiguous / manual vetting required")
    df = pd.read_csv(csv_path)
    assert df.iloc[0]["verdict"] == "ambiguous / manual vetting required"
