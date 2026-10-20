"""Plotting utilities for the transit candidate pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import lightkurve as lk
import matplotlib.pyplot as plt
import numpy as np

from .config import PLOTS_DIR
from .utils import ensure_dirs, phase_fold, safe_dirname

logger = logging.getLogger(__name__)

# Use a non-interactive backend so notebooks and scripts both work
plt.rcParams.update(
    {
        "figure.dpi": 120,
        "font.size": 10,
        "axes.grid": True,
        "grid.alpha": 0.3,
    }
)


def _save(fig: plt.Figure, path: Path) -> None:
    ensure_dirs(path.parent)
    fig.savefig(path, bbox_inches="tight")
    logger.debug("Saved plot: %s", path)
    plt.close(fig)


def plot_raw_lightcurve(
    lc: lk.LightCurve,
    target_id: str,
    save_dir: Optional[Path] = None,
) -> Path:
    """Plot the raw (or minimally processed) light curve."""
    save_dir = save_dir or PLOTS_DIR / safe_dirname(target_id)
    fig, ax = plt.subplots(figsize=(12, 3.5))
    ax.scatter(np.asarray(lc.time.value, dtype=float),
               np.asarray(lc.flux.value, dtype=float),
               s=1, c="steelblue", alpha=0.6, rasterized=True)
    ax.set_xlabel("Time (BTJD)")
    ax.set_ylabel("Normalized Flux")
    ax.set_title(f"{target_id} — Raw Light Curve")
    out = save_dir / "raw_lightcurve.png"
    _save(fig, out)
    return out


def plot_cleaned_lightcurve(
    lc: lk.LightCurve,
    target_id: str,
    save_dir: Optional[Path] = None,
) -> Path:
    """Plot the cleaned (preprocessed) light curve."""
    save_dir = save_dir or PLOTS_DIR / safe_dirname(target_id)
    fig, ax = plt.subplots(figsize=(12, 3.5))
    ax.scatter(np.asarray(lc.time.value, dtype=float),
               np.asarray(lc.flux.value, dtype=float),
               s=1, c="darkorange", alpha=0.6, rasterized=True)
    ax.set_xlabel("Time (BTJD)")
    ax.set_ylabel("Normalized Flux")
    ax.set_title(f"{target_id} — Cleaned Light Curve")
    out = save_dir / "cleaned_lightcurve.png"
    _save(fig, out)
    return out


def plot_bls_periodogram(
    bls_result,
    top_periods: list[float],
    target_id: str,
    save_dir: Optional[Path] = None,
) -> Path:
    """Plot the BLS power spectrum, highlighting the top candidate periods."""
    save_dir = save_dir or PLOTS_DIR / safe_dirname(target_id)
    fig, ax = plt.subplots(figsize=(10, 4))
    # .period may be a plain numpy array (numpy BLS) or astropy Quantity (legacy)
    period_arr = np.asarray(getattr(bls_result.period, "value", bls_result.period), dtype=float)
    ax.plot(period_arr, bls_result.power, lw=0.5, color="navy", alpha=0.8)
    ax.set_xlabel("Period (days)")
    ax.set_ylabel("BLS Power")
    ax.set_title(f"{target_id} — BLS Periodogram")
    ax.set_xscale("log")

    colors = ["red", "orange", "green", "purple", "brown"]
    for i, p in enumerate(top_periods[:5]):
        ax.axvline(p, color=colors[i % len(colors)], ls="--", alpha=0.8,
                   label=f"#{i+1}: {p:.4f} d")
    ax.legend(fontsize=8, ncol=2)

    out = save_dir / "bls_periodogram.png"
    _save(fig, out)
    return out


def plot_folded_lightcurve(
    lc: lk.LightCurve,
    period_days: float,
    epoch_btjd: float,
    duration_days: float,
    target_id: str,
    save_dir: Optional[Path] = None,
    bin_minutes: float = 10.0,
) -> Path:
    """Phase-fold the light curve and plot with an optional binned overlay."""
    save_dir = save_dir or PLOTS_DIR / safe_dirname(target_id)
    # Force plain numpy float arrays — astropy masked arrays cause matplotlib crashes
    time = np.asarray(lc.time.value, dtype=float)
    flux = np.asarray(lc.flux.value, dtype=float)

    phase = phase_fold(time, period_days, epoch_btjd)
    sort_idx = np.argsort(phase)
    phase_sorted = phase[sort_idx]
    flux_sorted = flux[sort_idx]

    # Bin into equal-width phase bins
    bin_width = (bin_minutes / 60.0) / period_days
    bins = np.arange(-0.5, 0.5, bin_width)
    bin_centers, bin_flux, bin_err = [], [], []
    for b in bins:
        mask = (phase_sorted >= b) & (phase_sorted < b + bin_width)
        if mask.sum() > 2:
            bin_centers.append(float(b + bin_width / 2))
            bin_flux.append(float(np.nanmedian(flux_sorted[mask])))
            bin_err.append(float(np.nanstd(flux_sorted[mask]) / np.sqrt(mask.sum())))

    # Ensure plain float arrays before handing to matplotlib
    bin_centers = np.array(bin_centers, dtype=float)
    bin_flux    = np.array(bin_flux,    dtype=float)
    bin_err     = np.array(bin_err,     dtype=float)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.scatter(phase_sorted, flux_sorted, s=1, c="steelblue", alpha=0.3, label="Individual cadences")
    if len(bin_centers) > 0:
        ax.errorbar(
            bin_centers, bin_flux, yerr=bin_err,
            fmt="o", color="red", ms=4, lw=1.5, label=f"Binned ({bin_minutes:.0f} min)",
            zorder=5,
        )

    half_dur_phase = (duration_days / period_days) / 2.0
    ax.axvspan(-half_dur_phase, half_dur_phase, alpha=0.12, color="gold", label="Transit window")
    ax.axhline(1.0, ls=":", color="gray", lw=0.8)
    ax.set_xlabel("Phase")
    ax.set_ylabel("Normalized Flux")
    ax.set_title(f"{target_id} — Folded at {period_days:.4f} d")
    ax.legend(fontsize=8)
    ax.set_xlim(-0.5, 0.5)

    out = save_dir / f"folded_P{period_days:.4f}d.png"
    _save(fig, out)
    return out


def plot_transit_zoom(
    lc: lk.LightCurve,
    epoch_btjd: float,
    duration_days: float,
    period_days: float,
    target_id: str,
    save_dir: Optional[Path] = None,
    n_transits: int = 4,
) -> Path:
    """Plot individual transit windows centred on each transit epoch."""
    save_dir = save_dir or PLOTS_DIR / safe_dirname(target_id)
    time = np.asarray(lc.time.value, dtype=float)
    flux = np.asarray(lc.flux.value, dtype=float)

    baseline = time.max() - time.min()
    window = duration_days * 3.0  # show 3× the duration on each side

    # Find transit times within the data
    n_periods = int(baseline / period_days) + 1
    transit_times = [epoch_btjd + i * period_days for i in range(-1, n_periods + 1)]
    transit_times = [t for t in transit_times if time.min() <= t <= time.max()]

    if not transit_times:
        logger.warning("No in-window transits found for zoom plot.")
        # Still produce an empty figure
        fig, ax = plt.subplots()
        ax.set_title(f"{target_id} — no transits in window")
        out = save_dir / "transit_zoom.png"
        _save(fig, out)
        return out

    shown = transit_times[:n_transits]
    n_cols = min(len(shown), 2)
    n_rows = int(np.ceil(len(shown) / n_cols))

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 3 * n_rows), squeeze=False)
    fig.suptitle(f"{target_id} — Individual transit windows", fontsize=11)

    for i, tc in enumerate(shown):
        ax = axes[i // n_cols][i % n_cols]
        mask = np.abs(time - tc) <= window
        if mask.sum() < 2:
            ax.set_visible(False)
            continue
        ax.scatter(time[mask] - tc, flux[mask], s=6, color="steelblue", alpha=0.7)
        ax.axvspan(-duration_days / 2, duration_days / 2, alpha=0.15, color="gold")
        ax.axhline(1.0, ls=":", color="gray", lw=0.8)
        ax.set_xlabel("Time from mid-transit (days)")
        ax.set_ylabel("Flux")
        ax.set_title(f"Transit at BTJD {tc:.2f}")

    # Hide unused axes
    for i in range(len(shown), n_rows * n_cols):
        axes[i // n_cols][i % n_cols].set_visible(False)

    plt.tight_layout()
    out = save_dir / "transit_zoom.png"
    _save(fig, out)
    return out


def all_diagnostic_plots(
    lc_raw: lk.LightCurve,
    lc_clean: lk.LightCurve,
    bls_result,
    candidates_df,
    target_id: str,
    save_dir: Optional[Path] = None,
) -> dict[str, Path]:
    """Convenience wrapper: generate and save all standard diagnostic plots."""
    save_dir = save_dir or PLOTS_DIR / safe_dirname(target_id)
    ensure_dirs(save_dir)

    top_periods = candidates_df["period_days"].tolist() if not candidates_df.empty else []
    paths: dict[str, Path] = {}

    paths["raw"] = plot_raw_lightcurve(lc_raw, target_id, save_dir)
    paths["cleaned"] = plot_cleaned_lightcurve(lc_clean, target_id, save_dir)
    paths["periodogram"] = plot_bls_periodogram(bls_result, top_periods, target_id, save_dir)

    if not candidates_df.empty:
        best = candidates_df.iloc[0]
        paths["folded"] = plot_folded_lightcurve(
            lc_clean,
            best["period_days"],
            best["epoch_btjd"],
            best["duration_days"],
            target_id,
            save_dir,
        )
        paths["zoom"] = plot_transit_zoom(
            lc_clean,
            best["epoch_btjd"],
            best["duration_days"],
            best["period_days"],
            target_id,
            save_dir,
        )

    return paths
