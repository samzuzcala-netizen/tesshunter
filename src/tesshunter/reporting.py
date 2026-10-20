"""Generate a markdown candidate-vetting report."""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import REPORTS_DIR
from .preprocessing import PreprocessingRecord
from .vetting import DEPTH_HARD_VETO_PPT, VettingResult
from .utils import ensure_dirs, safe_dirname

# Prompt 3, part D: the per-survivor data-validation packet lives in
# tesshunter.packet; it is re-exported here so "reporting" stays the one
# entry point for everything written for a human.
from .packet import build_packet as generate_packet, ctoi_fields, completeness_at_snr  # noqa: F401

logger = logging.getLogger(__name__)


def _fmt_optional(val, fmt: str = ".4f", unit: str = "") -> str:
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:{fmt}}{(' ' + unit) if unit else ''}"
    return str(val)


def _df_to_markdown(df: pd.DataFrame, floatfmt: str = ".4f") -> str:
    """Render a DataFrame as a markdown table, with a plain-text fallback.

    ``DataFrame.to_markdown`` requires the optional ``tabulate`` package.
    Report generation must never hard-fail because of a missing formatting
    dependency, so on ImportError we fall back to ``DataFrame.to_string``
    inside a fenced code block.

    Parameters
    ----------
    df:
        The DataFrame to render.
    floatfmt:
        Float format passed to ``to_markdown`` (ignored by the fallback).
    """
    try:
        return df.to_markdown(index=False, floatfmt=floatfmt)
    except ImportError as exc:
        logger.warning(
            "tabulate is unavailable (%s) — rendering table as plain text.", exc
        )
        return "```\n" + df.to_string(index=False) + "\n```"


def _collect_flag_lists(vetting: VettingResult) -> tuple[list[str], list[str], list[str]]:
    """Return (hard, high, medium) vetting flag lists.

    Reads the list attributes first (``flags_hard``/``flags_high``/
    ``flags_medium``, falling back to the ``hard_veto_flags`` /
    ``high_risk_flags`` / ``medium_flags`` names used by
    :class:`~tesshunter.vetting.VettingResult`).  When every list is absent
    or empty, derives entries from the individual boolean check fields so
    the report never silently omits a raised flag.
    """
    hard = list(
        getattr(vetting, "flags_hard", None)
        or getattr(vetting, "hard_veto_flags", None)
        or []
    )
    high = list(
        getattr(vetting, "flags_high", None)
        or getattr(vetting, "high_risk_flags", None)
        or []
    )
    medium = list(
        getattr(vetting, "flags_medium", None)
        or getattr(vetting, "medium_flags", None)
        or []
    )

    if not (hard or high or medium):
        # ── Fallback: derive from the boolean check fields ────────────────
        if getattr(vetting, "depth_too_deep", False):
            hard.append("Depth exceeds the hard-veto limit (see depth check row).")
        if getattr(vetting, "snr_absurd", False):
            hard.append("SNR exceeds the hard-veto limit (unphysical for a planet).")
        if getattr(vetting, "depth_large", False):
            high.append("Depth in the large / EB-risk regime.")
        if getattr(vetting, "snr_high", False):
            high.append("SNR elevated (stellar-activity / systematic territory).")
        if getattr(vetting, "secondary_eclipse_detected", False):
            high.append("Secondary eclipse detected near phase 0.5.")
        if getattr(vetting, "odd_even_mismatch", False):
            high.append("Odd/even transit depth mismatch.")
        if getattr(vetting, "near_rotation_harmonic", False):
            high.append("Period near a stellar-rotation harmonic.")
        if getattr(vetting, "duration_fraction_high", False):
            medium.append("Duration/period ratio is high.")
        if getattr(vetting, "single_sector_only", False):
            medium.append("Only a single sector of data available.")
        if not getattr(vetting, "catalog_ok", True):
            medium.append("Catalog lookup failed or unavailable.")

    return hard, high, medium


def _centroid_check_cell(centroid_result) -> str:
    """One-line summary of the centroid check for the FP-checks table."""
    if centroid_result is None:
        return "not run"
    if not getattr(centroid_result, "available", False):
        note = getattr(centroid_result, "note", "") or "TPF could not be obtained"
        return f"not available — {note}"
    status = "FAIL" if centroid_result.flagged else "PASS"
    return (
        f"{status} — shift {centroid_result.total_shift_px:.3f} px "
        f"({centroid_result.shift_arcsec:.2f} arcsec, "
        f"{centroid_result.sigma:.1f}σ)"
    )


def _contamination_check_cell(contamination_result) -> str:
    """One-line summary of the contamination check for the FP-checks table."""
    if contamination_result is None:
        return "not run"
    if not getattr(contamination_result, "available", False):
        note = getattr(contamination_result, "note", "") or "cone search unavailable"
        return f"not available — {note}"
    n_high = len(getattr(contamination_result, "high_risk_neighbours", []) or [])
    n_medium = len(getattr(contamination_result, "medium_risk_neighbours", []) or [])
    if contamination_result.flagged:
        return (
            f"FAIL — {n_high} high-risk, {n_medium} medium-risk neighbour(s) "
            f"of {contamination_result.n_neighbours_checked} checked"
        )
    return (
        f"PASS — {contamination_result.n_neighbours_checked} neighbour(s) checked, "
        f"{contamination_result.n_ruled_out} ruled out"
    )


def _centroid_section(centroid_result) -> list[str]:
    """Detailed centroid subsection lines for the report."""
    lines = ["### Centroid analysis", ""]
    if centroid_result is None:
        lines += ["_Centroid check not run._", ""]
        return lines
    if not getattr(centroid_result, "available", False):
        note = getattr(centroid_result, "note", "") or "TPF could not be obtained"
        lines += [f"_Centroid check attempted but not available: {note}_", ""]
        return lines
    lines += [
        "| Property | Value |",
        "|----------|-------|",
        f"| Column shift | {centroid_result.col_shift_px:.4f} px |",
        f"| Row shift | {centroid_result.row_shift_px:.4f} px |",
        f"| Total shift | {centroid_result.total_shift_px:.4f} px |",
        f"| Sky offset | {centroid_result.shift_arcsec:.3f} arcsec |",
        f"| Significance | {centroid_result.sigma:.2f}σ |",
        f"| In-transit cadences | {centroid_result.n_in_transit} |",
        f"| Out-of-transit cadences | {centroid_result.n_out_transit} |",
        f"| Pixel scale | {centroid_result.pixel_scale_arcsec:.2f} arcsec/px |",
        f"| Flagged | {'Yes' if centroid_result.flagged else 'No'} |",
        "",
    ]
    if getattr(centroid_result, "note", ""):
        lines += [f"> {centroid_result.note}", ""]
    return lines


def _contamination_section(contamination_result) -> list[str]:
    """Detailed contamination subsection lines for the report."""
    lines = ["### Nearby-star contamination", ""]
    if contamination_result is None:
        lines += ["_Contamination check not run._", ""]
        return lines
    if not getattr(contamination_result, "available", False):
        note = getattr(contamination_result, "note", "") or "cone search unavailable"
        lines += [f"_Contamination check attempted but not available: {note}_", ""]
        return lines
    lines += [
        f"Searched {contamination_result.search_radius_arcsec:.0f} arcsec around the "
        f"target: {contamination_result.n_neighbours_checked} neighbour(s) checked, "
        f"{contamination_result.n_ruled_out} ruled out, "
        f"flagged: {'Yes' if contamination_result.flagged else 'No'}.",
        "",
    ]
    neighbours = list(getattr(contamination_result, "all_neighbours", []) or [])
    if not neighbours:
        neighbours = (
            list(getattr(contamination_result, "high_risk_neighbours", []) or [])
            + list(getattr(contamination_result, "medium_risk_neighbours", []) or [])
            + list(getattr(contamination_result, "info_neighbours", []) or [])
            + list(getattr(contamination_result, "ruled_out_neighbours", []) or [])
        )
    if neighbours:
        nb_df = pd.DataFrame(
            [
                {
                    "tic_id": nb.tic_id if nb.tic_id is not None else "?",
                    "sep_arcsec": nb.separation_arcsec,
                    "sep_px": nb.separation_px,
                    "tmag": nb.tmag,
                    "delta_tmag": nb.delta_tmag,
                    "leakage_frac": nb.leakage_fraction,
                    "implied_depth_ppt": nb.leakage_corrected_depth_ppt,
                    "risk": nb.risk_level,
                }
                for nb in neighbours
            ]
        )
        lines += [_df_to_markdown(nb_df, floatfmt=".3f"), ""]
    else:
        lines += ["_No neighbours found within the search radius._", ""]
    if getattr(contamination_result, "note", ""):
        lines += [f"> {contamination_result.note}", ""]
    return lines


def generate_report(
    target_id: str,
    tic_id: int,
    sectors: list[int],
    prep_record: PreprocessingRecord,
    candidates_df: pd.DataFrame,
    vetting: VettingResult,
    crossmatch_summary: str,
    plot_paths: dict[str, Path],
    output_dir: Optional[Path] = None,
    planets_df: Optional[pd.DataFrame] = None,
    mission: str = "TESS",
    centroid_result=None,
    contamination_result=None,
) -> Path:
    """Write a markdown candidate-vetting report and return its path.

    Parameters
    ----------
    target_id:          Human-readable name or "TIC XXXXXXX".
    tic_id:             Numeric TIC ID (0 if unavailable).
    sectors:            List of TESS sectors / K2 campaigns / Kepler quarters used.
    prep_record:        Output of preprocessing.preprocess().
    candidates_df:      Output of bls_search.run_bls() (first-pass raw candidates).
    vetting:            Output of vetting.run_vetting() (applied to planet 1).
    crossmatch_summary: String from catalog_crossmatch.crossmatch()['summary_str'].
    plot_paths:         Dict mapping plot type → Path (from plotting.all_diagnostic_plots).
    output_dir:         Directory for the report file. Defaults to REPORTS_DIR.
    planets_df:         Optional DataFrame of alias-resolved multi-planet candidates
                        (output of the iterative detection loop).  When supplied,
                        Section 2 shows all candidates; otherwise only the raw
                        BLS top candidate is shown.
    mission:            "TESS" (default), "K2", or "Kepler" — controls section labels.
    centroid_result:    Optional :class:`~tesshunter.centroid.CentroidResult`.
                        When supplied, the report renders the real centroid
                        offset/significance; otherwise the check is marked
                        "not run".
    contamination_result:
                        Optional :class:`~tesshunter.contamination.ContaminationResult`.
                        When supplied, the report renders the neighbour table
                        and risk summary; otherwise the check is marked
                        "not run".
    """
    output_dir = output_dir or REPORTS_DIR / safe_dirname(target_id)
    ensure_dirs(output_dir)

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ── Mission-specific labels ────────────────────────────────────────────────
    mission_up = mission.upper()
    if mission_up == "K2":
        unit_label = "K2 Campaign(s)"
    elif mission_up == "KEPLER":
        unit_label = "Kepler Quarter(s)"
    else:
        unit_label = "TESS Sectors"

    # Show TIC ID in header only when it was actually resolved (non-zero)
    _tic_suffix = f" (TIC {tic_id})" if tic_id else ""

    # Prefer resolved planets_df for "best"; fall back to raw BLS candidate
    if planets_df is not None and not planets_df.empty:
        best = planets_df.iloc[0]
    elif not candidates_df.empty:
        best = candidates_df.iloc[0]
    else:
        best = None

    def plot_link(key: str) -> str:
        p = plot_paths.get(key)
        if p is None:
            return "_Not generated_"
        return f"![{key}]({p})"

    lines = [
        f"# Candidate Transit Signal Report",
        f"",
        f"**Target:** {target_id}{_tic_suffix}",
        f"**Mission:** {mission}",
        f"**Generated:** {now}",
        f"**Pipeline version:** tesshunter 0.1.0",
        f"",
        f"> **Scientific caveat:** This report describes a *candidate transit-like event*.",
        f"> It has NOT been confirmed as a planet. Every signal must be assumed to be a",
        f"> false positive until follow-up observations prove otherwise.",
        f"",
        f"---",
        f"",
        f"## 1. Data",
        f"",
        f"| Property | Value |",
        f"|----------|-------|",
        f"| Mission | {mission} |",
        f"| TIC ID | {tic_id if tic_id else 'N/A'} |",
        f"| {unit_label} | {', '.join(map(str, sectors)) if sectors else 'unknown'} |",
        f"| Total cadences (raw) | {prep_record.original_cadences} |",
        f"| After NaN removal | {prep_record.after_nan_removal} |",
        f"| After sigma-clip ({prep_record.sigma_clip_sigma}σ) | {prep_record.after_sigma_clip} |",
        f"| Normalised | {'Yes' if prep_record.normalised else 'No'} |",
        f"| Flattened | {'Yes (window=' + str(prep_record.flatten_window_length) + ')' if prep_record.flattened else 'No'} |",
        f"",
        f"---",
        f"",
        f"## 2. Detected Candidates",
        f"",
    ]

    if planets_df is not None and not planets_df.empty:
        # ── Multi-planet table from the iterative resolver ────────────────
        disp_cols = [c for c in
                     ["planet_num", "period_days", "depth_ppt", "duration_days",
                      "snr", "event_completeness", "harmonic_label"]
                     if c in planets_df.columns]
        lines += [
            f"_Periods resolved after alias checking (harmonic disambiguation, "
            f"event-completeness scoring, transit-window overlap penalty)._",
            f"",
            _df_to_markdown(planets_df[disp_cols], floatfmt=".4f"),
            f"",
            f"### Primary candidate (Planet 1) detail",
            f"",
            f"| Property | Value |",
            f"|----------|-------|",
            f"| Period | {best['period_days']:.6f} days |",
            f"| Transit epoch (BTJD) | {best['epoch_btjd']:.4f} |",
            f"| Duration | {best['duration_days']*24:.2f} hours |",
            f"| Depth | {best['depth_ppt']:.3f} ppt |",
            f"| BLS Power | {float(best.get('power', 0.0)):.3e} |",
            f"| SNR | {best['snr']:.2f} |",
            f"",
        ]
    elif best is not None:
        # ── Single-planet fallback ────────────────────────────────────────
        lines += [
            f"| Property | Value |",
            f"|----------|-------|",
            f"| Period | {best['period_days']:.6f} days |",
            f"| Transit epoch (BTJD) | {best['epoch_btjd']:.4f} |",
            f"| Duration | {best['duration_days']*24:.2f} hours |",
            f"| Depth | {best['depth_ppt']:.3f} ppt |",
            f"| BLS Power | {float(best.get('power', 0.0)):.3e} |",
            f"| SNR | {best['snr']:.2f} |",
            f"",
        ]
    else:
        lines += ["_No candidate signal above threshold._", ""]

    if best is not None and vetting.estimated_radius_rearth is not None:
        lines += [
            f"**Estimated radius (Planet 1):** {vetting.estimated_radius_rearth:.2f} R_Earth "
            f"(stellar radius: {_fmt_optional(vetting.stellar_radius_rsun, '.2f', 'R_Sun')})",
            f"",
            f"> Radius estimate assumes a central transit and uses R_p/R_s = sqrt(depth).",
            f"> This is a rough approximation — impact parameter and limb darkening are not fit.",
            f"",
        ]

    # Raw BLS candidates for reference
    if not candidates_df.empty:
        lines += [
            f"### Raw BLS periodogram peaks (first pass, pre-alias resolution)",
            f"",
            _df_to_markdown(candidates_df, floatfmt=".4f"),
            f"",
        ]

    # ── False-positive checks ─────────────────────────────────────────────────
    # The hard depth veto actually tested is DEPTH_HARD_VETO_PPT (100 ppt), or
    # its radius-aware equivalent (implied companion radius) when the stellar
    # radius is known — the label must state the threshold really applied.
    if vetting.stellar_radius_rsun:
        depth_check_label = (
            f"Depth veto — radius-aware (implied companion ≤ 2.5 R_Jup for "
            f"R* = {vetting.stellar_radius_rsun:.2f} R_Sun; replaces the "
            f"{DEPTH_HARD_VETO_PPT:.0f} ppt absolute veto)"
        )
    else:
        depth_check_label = f"Depth < {DEPTH_HARD_VETO_PPT:.0f} ppt (hard veto)"

    flags_hard, flags_high, flags_medium = _collect_flag_lists(vetting)

    lines += [
        f"---",
        f"",
        f"## 3. Catalog Cross-match",
        f"",
        crossmatch_summary,
        f"",
        f"---",
        f"",
        f"## 4. False-Positive Checks",
        f"",
        f"| Check | Result |",
        f"|-------|--------|",
        f"| {depth_check_label} | {'PASS' if not vetting.depth_too_deep else 'FAIL'} |",
        f"| Duration/period ratio acceptable | {'PASS' if not vetting.duration_fraction_high else 'FAIL'} |",
        f"| Odd/even depth consistent | {'PASS' if not vetting.odd_even_mismatch else f'FAIL — Δ={vetting.odd_even_delta_sigma:.1f}σ'} |",
        f"| No secondary eclipse at phase 0.5 | {'PASS' if not vetting.secondary_eclipse_detected else f'FAIL — {vetting.secondary_depth_ppt:.2f} ppt'} |",
        f"| Multi-sector consistency | {'PASS' if not vetting.single_sector_only else 'CAUTION (1 sector only)'} |",
        f"| Centroid analysis | {_centroid_check_cell(centroid_result)} |",
        f"| Nearby-star contamination | {_contamination_check_cell(contamination_result)} |",
        f"",
        f"### Vetting flags",
        f"",
    ]
    if flags_hard or flags_high or flags_medium:
        for flag in flags_hard:
            lines.append(f"- **HARD VETO** — {flag}")
        for flag in flags_high:
            lines.append(f"- **HIGH RISK** — {flag}")
        for flag in flags_medium:
            lines.append(f"- **MEDIUM** — {flag}")
    else:
        lines.append("_No vetting flags raised._")
    lines.append("")

    lines += _centroid_section(centroid_result)
    lines += _contamination_section(contamination_result)

    lines += [
        f"### Detailed notes",
        f"",
    ]
    for note in vetting.notes:
        lines.append(f"- {note}")

    lines += [
        f"",
        f"---",
        f"",
        f"## 5. Diagnostic Plots",
        f"",
        f"### Raw Light Curve",
        plot_link("raw"),
        f"",
        f"### Cleaned Light Curve",
        plot_link("cleaned"),
        f"",
        f"### BLS Periodogram",
        plot_link("periodogram"),
        f"",
        f"### Phase-Folded Light Curve",
        plot_link("folded"),
        f"",
        f"### Individual Transit Windows",
        plot_link("zoom"),
        f"",
        f"---",
        f"",
        f"## 6. Verdict",
        f"",
        f"**{vetting.verdict.upper()}**",
        f"",
        f"---",
        f"",
        f"## 7. Recommended Follow-up",
        f"",
        f"- [ ] Centroid analysis using TESS target pixel files (TPFs) to check for "
              f"photometric contamination from nearby stars.",
        f"- [ ] Search for nearby Gaia sources within the TESS aperture.",
        f"- [ ] Check for variability at the same period in the background flux.",
        f"- [ ] Obtain ground-based photometry to confirm transit on-target.",
        f"- [ ] Obtain radial velocity measurements to constrain companion mass.",
        f"- [ ] Check TESS SPOC data validation reports (DVR) if available.",
        f"",
        f"---",
        f"*Report generated by tesshunter. Not a peer-reviewed result.*",
    ]

    report_text = "\n".join(lines)
    out_path = output_dir / f"candidate_report_{safe_dirname(target_id).replace(' ', '_')}.md"
    out_path.write_text(report_text, encoding="utf-8")
    logger.info("Report written: %s", out_path)
    return out_path


def append_to_candidate_summary(
    tic_id: int,
    target_id: str,
    sectors: list[int],
    period_days: float,
    depth_ppt: float,
    duration_hours: float,
    bls_power: float,
    snr: float,
    verdict: str,
    crossmatch_summary: str,
    summary_csv: Path,
    period_match_tol: float = 0.01,
) -> None:
    """Upsert one row into the running candidate summary CSV.

    Creates the file with headers if it does not exist.  Rows are keyed on
    ``(tic_id, period_days)``: an existing row for the same TIC whose period
    matches within ``period_match_tol`` (relative, default 1 %) is REPLACED
    by the new row instead of being duplicated, so re-running a target does
    not accumulate copies.  The CSV is sorted by ``snr`` descending before
    writing, and ``bls_power`` is stored at full precision (the custom BLS
    power is of order 1e-8 to 1e-5; rounding to 4 decimals floored it to 0).

    Parameters
    ----------
    period_match_tol:
        Relative period tolerance used to identify an existing row for the
        same signal (default 0.01 = 1 %).
    """
    ensure_dirs(summary_csv.parent)
    row = {
        "tic_id": tic_id,
        "target_id": target_id,
        "sectors": " ".join(map(str, sectors)),
        "period_days": round(period_days, 6),
        "depth_ppt": round(depth_ppt, 3),
        "duration_hours": round(duration_hours, 3),
        "bls_power": float(bls_power),   # full precision — never round the power
        "snr": round(snr, 2),
        "verdict": verdict,
        "crossmatch": crossmatch_summary[:120],
    }

    new_df = pd.DataFrame([row])
    if summary_csv.exists():
        existing = pd.read_csv(summary_csv)
        if not existing.empty and {"tic_id", "period_days"}.issubset(existing.columns):
            # ── Upsert: drop rows for the same (tic_id, period) signal ────
            periods = pd.to_numeric(existing["period_days"], errors="coerce")
            denom = max(abs(float(period_days)), 1e-12)
            rel_diff = (periods - float(period_days)).abs() / denom
            duplicate = (existing["tic_id"] == tic_id) & (rel_diff <= period_match_tol)
            n_dup = int(duplicate.sum())
            if n_dup:
                logger.info(
                    "Replacing %d existing summary row(s) for TIC %s at P=%.6f d.",
                    n_dup, tic_id, period_days,
                )
                existing = existing[~duplicate]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    if "snr" in combined.columns:
        combined = combined.sort_values(
            "snr", ascending=False, kind="mergesort", ignore_index=True
        )

    combined.to_csv(summary_csv, index=False)
    logger.info("Updated candidate summary: %s", summary_csv)
