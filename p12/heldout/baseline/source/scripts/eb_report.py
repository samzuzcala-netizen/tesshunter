"""Phase-folded light curve and catalog-form values for an eclipsing binary found by the audit.

Reads the audit's detrended, 30-minute-binned light curve (data/survey/p5/tls/<key>_lc.npz),
folds it on the audit period, measures the eclipse depth and full duration from the fold,
scans every phase for a second eclipse, and writes docs/eb_reports/<tic>_fold.png plus
<tic>_vsx_fields.md with the numbers a human needs for a VSX "new variable" form.
Nothing is submitted anywhere.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "eb_reports"
OUT.mkdir(parents=True, exist_ok=True)
BTJD = 2457000.0


def sexagesimal(ra_deg, dec_deg):
    h = ra_deg / 15.0
    hh = int(h); mm = int((h - hh) * 60); ss = ((h - hh) * 60 - mm) * 60
    sgn = "-" if dec_deg < 0 else "+"
    d = abs(dec_deg); dd = int(d); dm = int((d - dd) * 60); ds = ((d - dd) * 60 - dm) * 60
    return f"{hh:02d} {mm:02d} {ss:05.2f}", f"{sgn}{dd:02d} {dm:02d} {ds:04.1f}"


def main(tic: int, key: str, period: float, t0_btjd: float, tmag: float, ra: float, dec: float, notes: dict):
    lc = np.load(REPO / "data" / "survey" / "p5" / "tls" / f"{key}_lc.npz")
    t, f = lc["time"], lc["flux"]
    phase = ((t - t0_btjd) / period + 0.5) % 1.0 - 0.5          # primary at phase 0
    # binned fold, 0.001 in phase (about 33 min at this period)
    nb = 1000
    idx = np.floor((phase + 0.5) * nb).astype(int).clip(0, nb - 1)
    cnt = np.bincount(idx, minlength=nb)
    fb = np.bincount(idx, weights=f, minlength=nb) / np.maximum(cnt, 1)
    fb[cnt == 0] = np.nan
    pb = (np.arange(nb) + 0.5) / nb - 0.5
    oot = np.abs(pb) > 0.02
    base = np.nanmedian(fb[oot]); sig_bin = 1.4826 * np.nanmedian(np.abs(fb[oot] - base))
    # primary eclipse: depth = deepest bin; duration = full width below base - 3 sigma
    core = np.abs(pb) < 0.02
    depth = float(base - np.nanmin(fb[core]))
    below = core & (fb < base - 3 * sig_bin)
    if below.any():
        dur_phase = float(pb[below].max() - pb[below].min() + 1.0 / nb)
    else:
        dur_phase = float("nan")
    dur_h = dur_phase * period * 24.0
    # any other dip: bins more than 5 sigma below the base outside the primary
    other = (~core) & (fb < base - 5 * sig_bin)
    other_phases = pb[other]
    # secondary at phase 0.5 specifically (+/- one primary duration)
    sec = np.abs(np.abs(pb) - 0.5) < max(dur_phase, 0.005)
    sec_depth = float(base - np.nanmean(fb[sec])) if sec.any() else float("nan")
    sec_err = float(sig_bin / math.sqrt(max(1, sec.sum())))
    dmag = -2.5 * math.log10(1.0 - depth)
    ra_s, dec_s = sexagesimal(ra, dec)
    epoch_bjd = t0_btjd + BTJD
    # figure
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = axes[0]
    ax.plot(phase, 1000 * (f - 1), ".", ms=1.5, color="0.6", label="30-min bins, all sectors")
    ax.plot(pb, 1000 * (fb - 1), "-", color="C3", lw=1.2, label="fold, 0.001 phase bins")
    ax.set_xlabel("phase (primary at 0)"); ax.set_ylabel("relative flux (ppt)")
    ax.set_title(f"TIC {tic}: P = {period:.5f} d, full phase")
    ax.legend(loc="lower left", fontsize=8)
    ax = axes[1]
    m = np.abs(phase) < 0.03
    ax.plot(phase[m] * period * 24, 1000 * (f[m] - 1), ".", ms=3, color="0.5")
    mb = np.abs(pb) < 0.03
    ax.plot(pb[mb] * period * 24, 1000 * (fb[mb] - 1), "-", color="C3", lw=1.5)
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xlabel("hours from mid-eclipse"); ax.set_title(f"primary eclipse: depth {1000 * depth:.1f} ppt, T {dur_h:.2f} h")
    fig.tight_layout()
    png = OUT / f"tic{tic}_fold.png"
    fig.savefig(png, dpi=130)
    n_ecl = int(len(np.unique(np.round((t[np.abs(phase) < dur_phase / 2] - t0_btjd) / period))))
    res = {
        "tic_id": tic, "ra_deg": ra, "dec_deg": dec, "ra_hms_J2000": ra_s, "dec_dms_J2000": dec_s,
        "period_days": period, "epoch_primary_bjd_tdb": round(epoch_bjd, 4),
        "depth_ppt_tess_band_observed": round(1000 * depth, 1), "depth_mag_tess_band": round(dmag, 3),
        "tmag_max": tmag, "tmag_min": round(tmag + dmag, 3),
        "primary_duration_hours": round(dur_h, 2), "primary_duration_percent_of_period": round(100 * dur_phase, 2),
        "n_primary_eclipses_in_data": n_ecl, "n_binned_points": int(len(t)),
        "baseline_days": round(float(t.max() - t.min()), 1),
        "fold_bin_scatter_ppt": round(1000 * sig_bin, 2),
        "secondary_at_phase_0p5_ppt": round(1000 * sec_depth, 2), "secondary_at_phase_0p5_err_ppt": round(1000 * sec_err, 2),
        "other_dips_gt_5sigma_phases": [round(float(p), 3) for p in other_phases],
        "figure": str(png.relative_to(REPO)),
    }
    res.update(notes)
    (OUT / f"tic{tic}_measurements.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(
        tic=167304394, key="tic167304394_P22.7802", period=22.77971, t0_btjd=1326.3718, tmag=11.47,
        ra=98.001223, dec=-67.304764,
        notes={
            "gaia_dr3_target": 5283324796495406336,
            "gaia_note": "two Gaia DR3 sources of equal brightness (G 12.79 and 12.64) 0.4 arcsec apart, both inside the TESS aperture; the observed depth is diluted by about a factor of two; ipd_frac_multi_peak 95%, no five-parameter solution",
            "other_ids": ["UCAC4 114-012846", "Gaia DR3 5283324796495406336"],
            "data": "TESS full-frame images, QLP light curves (TESS-SPOC / SPOC not available for this star), 34 sectors, 2018-2025; detrended with a wotan biweight (window 0.75 d) and binned to 30 min",
            "period_uncertainty_days": 0.0011,
            "catalog_status_2026_09_03": "not in VSX (1 arcmin), SIMBAD type '*' only, not in the TESS EB catalog, not in any SPOC TCE list, not a TOI/CTOI",
        },
    )
