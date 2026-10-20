"""Diagnose the saved HIP 97166 trial without changing TLS or any scientific record.

Replays only that trial through the installed TLS core and records every duration's
template-admission count. This is a post-reproduction diagnostic, never a rescue.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
import sys
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data/cache/lightkurve"))
os.environ.setdefault("TESSHUNTER_OFFLINE", "1")
KEY = "tic237222864_P10.2888"
WS = REPO / "data/survey/p10/stage_c/p9/repro_hip" / KEY
OUT = REPO / "p10/results/stage_c_hip97166_trial_diagnosis.json"

def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    from transitleastsquares import transitleastsquares
    from transitleastsquares.validate import validate_args
    from transitleastsquares.grid import duration_grid, T14
    from transitleastsquares.transit import get_cache
    from transitleastsquares.core import search_period, foldfast
    from transitleastsquares.helpers import running_mean
    from tesshunter.stage_c import concentration, robust_sde
    spectrum_path = WS / "tls" / (KEY + "_spectrum.npz")
    lc_path = WS / "tls" / (KEY + "_lc.npz")
    prep_path = WS / "prep" / (KEY + ".json")
    prep = json.loads(prep_path.read_text())
    with np.load(spectrum_path) as z, np.load(lc_path) as lc:
        periods, power, praw, chi2 = (z[k] for k in ("periods", "power", "power_raw", "chi2"))
        raw_t, raw_y, raw_e = (lc[k] for k in ("time", "flux", "flux_err"))
    model = transitleastsquares(raw_t, raw_y, raw_e, verbose=False)
    rs, ms = prep["R_star"], prep["M_star"]
    kw = dict(period_min=0.5, period_max=110.0, oversampling_factor=3, duration_grid_step=1.1,
              use_threads=1, show_progress_bar=False, verbose=False, R_star=rs, M_star=ms,
              R_star_min=max(0.1, 0.5*rs), R_star_max=2*rs,
              M_star_min=max(0.08, 0.5*ms), M_star_max=2*ms, T0_fit_margin=0.01)
    model, _ = validate_args(model, kw)
    t, y, dy = model.t, model.y, model.dy
    durations = duration_grid(periods, shortest=1/len(t), log_step=model.duration_grid_step)
    maxwidth = int(max(durations)*len(y))
    if maxwidth % 2: maxwidth += 1
    overview, shapes = get_cache(durations=durations, maxwidth_in_samples=maxwidth,
        per=model.per, rp=model.rp, a=model.a, inc=model.inc, ecc=model.ecc, w=model.w,
        u=model.u, limb_dark=model.limb_dark, verbose=False)
    idx = int(np.argmin(power))
    period = float(periods[idx])
    replay = search_period(period=period, t=t, y=y, dy=dy, transit_depth_min=model.transit_depth_min,
        R_star_min=model.R_star_min, R_star_max=model.R_star_max,
        M_star_min=model.M_star_min, M_star_max=model.M_star_max,
        lc_arr=shapes, lc_cache_overview=overview, T0_fit_margin=model.T0_fit_margin)
    widths = np.unique(overview["width_in_samples"])
    max_width = int(max(widths))
    if max_width % 2: max_width += 1
    order = np.argsort(foldfast(t, period), kind="mergesort")
    folded = y[order]
    patched = np.append(folded, folded[:max_width])
    dmin = T14(R_s=model.R_star_min, M_s=model.M_star_min, P=period, small=True)
    dmax = T14(R_s=model.R_star_max, M_s=model.M_star_max, P=period, small=False)
    correction = ((np.ptp(t)/period) + 1)/(np.ptp(t)/period)
    low, high = int(np.floor(dmin*len(y))), int(np.ceil(dmax*len(y)*correction))
    widths = widths[(widths >= low) & (widths <= high)]
    admission = []
    for width in widths:
        width = int(width)
        means = 1-running_mean(patched, width)
        stride = max(1, int(width*model.T0_fit_margin)) if model.T0_fit_margin > 0 and width > model.T0_fit_margin else 1
        selected = means[::stride] > model.transit_depth_min
        admission.append({"width_samples": width, "epoch_stride": stride,
            "n_phases_examined": len(means[::stride]), "n_above_depth_floor": int(selected.sum()),
            "max_box_depth_examined": float(np.max(means[::stride]))})
    peak = int(np.argmax(power))
    rob = robust_sde(praw)
    conc = concentration(power)
    result = {"utc": datetime.now(timezone.utc).isoformat(), "diagnostic_only": True,
        "input_sha256": {str(p.relative_to(REPO)): file_sha(p) for p in (spectrum_path,lc_path,prep_path)},
        "installed_source_sha256": {inspect.getsourcefile(fn): file_sha(inspect.getsourcefile(fn))
            for fn in (search_period, validate_args, get_cache)},
        "n_input_points": len(y), "trial_index": idx, "trial_period": period,
        "saved_chi2": float(chi2[idx]), "core_replay": [float(x) for x in replay],
        "replay_matches_saved_chi2": float(replay[1]) == float(chi2[idx]),
        "equals_datapoint_sentinel": float(replay[1]) == len(y),
        "transit_depth_min": model.transit_depth_min, "duration_admission": admission,
        "n_admitted_epochs": sum(r["n_above_depth_floor"] for r in admission),
        "chi2_flat_in_tls_normalized_error_units": float(np.sum(((y-1)/dy)**2)),
        "chi2_flat_in_physical_error_units": float(np.sum(((raw_y-1)/raw_e)**2)),
        "tls_error_normalization": "dy / mean(dy), from installed validate_inputs",
        "strongest_installed_index": peak, "strongest_period": float(periods[peak]),
        "installed_SDE": float(power[peak]), "installed_concentration": conc["fraction"],
        "robust_on_power_raw_at_same_peak": float(rob[peak]),
        "robust_triggered": bool(conc["fraction"] > 0.5),
        "raw_robust_passes_9": bool(conc["fraction"] > 0.5 and rob[peak] >= 9)}
    if result["equals_datapoint_sentinel"] and result["replay_matches_saved_chi2"] and result["n_admitted_epochs"] == 0:
        result["diagnosis"] = ("No phase/duration trial passed transit_depth_min at this period. "
            "TLS lowest_residuals_in_this_duration returned its datapoints sentinel, retained "
            "by search_period as chi2. It is not a fitted residual sum and no specific data "
            "points drive that extreme chi2. Error normalization makes the real flat-model "
            "chi2 about 0.046; the sentinel is on a different scale. The extreme negative SR/"
            "power ordinate is a statistical sentinel artifact. No code, input, ordinate or "
            "historical decision was altered.")
    else:
        result["diagnosis"] = "The sentinel hypothesis was not fully verified; inspect admission and replay."
    OUT.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("duration_admission","input_sha256","installed_source_sha256")},indent=2))

if __name__ == "__main__":
    main()

