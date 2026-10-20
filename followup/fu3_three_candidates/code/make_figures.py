"""Report figures from the FU3 result files (no new measurements)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fu3_common import *
from events import adopted, Template

plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "legend.fontsize": 7.5,
                     "figure.dpi": 120, "savefig.bbox": "tight"})
NAMES = {270573718: "TIC 270573718", 262843927: "TIC 262843927", 193718989: "TIC 193718989"}
REDS = [("pdc_raw", "TESS-SPOC/QLP corrected (raw baseline)", "C0"), ("sap_raw", "pipeline SAP", "C1"),
        ("survey_tesscut_aperture", "survey TESScut 1-px aperture", "C3"), ("tglc_aperture", "TGLC aperture", "C5"),
        ("fu3pix_annulus_circ1p5", "FU3 1.5-px aperture", "C2"), ("fu3pix_prf", "FU3 PRF photometry", "C4")]


def fig_depths(tic):
    ev = read(RES / f"s02_events_{tic}.json")
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    k = 0
    for red, lab, col in REDS:
        rows = [r for r in ev["events"] if r["reduction"] == red and r.get("admitted")]
        if not rows:
            continue
        x = np.array([r["cycle"] for r in rows]) + (k - 2.5) * 0.18
        ax.errorbar(x, [r["depth_ppt"] for r in rows], yerr=[r["depth_err_ppt"] for r in rows], fmt="o", ms=3,
                    capsize=1.5, color=col, label=lab, lw=0.8)
        k += 1
    p = ev["summary"]["pdc_raw"]["pooled"]
    ax.axhspan(p["depth_ppt"] - p["err_ppt"], p["depth_ppt"] + p["err_ppt"], color="0.85", zorder=0)
    ax.axhline(0, color="k", lw=0.7)
    ax.set_xlabel("cycle number (reference ephemeris)")
    ax.set_ylabel("signed event depth (ppt)")
    ax.set_title(f"{NAMES[tic]}: every coverage-admitted event, all reductions (signs retained)")
    ax.legend(ncol=3, loc="upper left", frameon=False)
    fig.savefig(FIG / f"F1_{tic}_event_depths.png")
    plt.close(fig)


def fig_oc(tic):
    ev = read(RES / f"s02_events_{tic}.json")
    nullp = RES / f"s16_ttv_null_{tic}_pdc_raw.json"
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    k = 0
    for red, lab, col in REDS:
        rows = [r for r in ev["events"] if r["reduction"] == red and r.get("admitted")
                and r.get("timing_status") in ("ok", "multimodal") and r.get("oc_err_d")]
        if not rows:
            continue
        x = np.array([r["cycle"] for r in rows]) + (k - 2.5) * 0.25
        ax.errorbar(x, [r["oc_d"] * 1440 for r in rows], yerr=[r["oc_err_d"] * 1440 for r in rows], fmt="o", ms=3,
                    capsize=1.5, color=col, label=lab, lw=0.8)
        k += 1
    if nullp.exists():
        n = read(nullp)
        m = n["null_coherence_quantiles"]["max"]
        ax.axhspan(-m, m, color="0.9", zorder=0, label=f"null: max |season median| ({n['n_null']} periodic injections)")
    ax.axhline(0, color="k", lw=0.7)
    ax.set_ylim(-200, 200)
    ax.set_xlabel("cycle number")
    ax.set_ylabel("O - C (min), formal errors")
    ax.set_title(f"{NAMES[tic]}: transit timing vs the reference linear ephemeris")
    ax.legend(ncol=2, loc="lower left", frameon=False)
    fig.savefig(FIG / f"F2_{tic}_oc.png")
    plt.close(fig)


def fold_data(tic, red, offsets=None):
    from s11_shape import windows, season_map
    eph = adopted(tic)
    ev = windows(tic, red, eph)
    smap = season_map([e["cycle"] for e in ev])
    xs, ys = [], []
    for e in ev:
        dt = e["t"] - e["tc"]
        if offsets:
            dt = dt - offsets.get(str(smap[e["cycle"]]), 0.0) / 1440
        B = np.column_stack([np.ones(len(dt)), dt / e["half"]])
        oot = np.abs(dt) > 0.6 * eph["T14"]
        c = np.linalg.lstsq(B[oot], e["y"][oot], rcond=None)[0]
        xs.append(dt * 24)
        ys.append(e["y"] - B @ c)
    return np.concatenate(xs), np.concatenate(ys), eph


def binned(x, y, w=0.25):
    b = np.floor(x / w)
    u = np.unique(b)
    xm = np.array([x[b == v].mean() for v in u])
    ym = np.array([y[b == v].mean() for v in u])
    ye = np.array([y[b == v].std() / np.sqrt(max((b == v).sum() - 1, 1)) for v in u])
    return xm, ym, ye


def fig_fold(tic):
    s11 = read(RES / f"s11_shape_{tic}_pdc_raw.json")
    modes = [("linear", None)] + ([("season", s11["season"]["A_planet_free"]["offsets_min"])] if tic == 270573718 else [])
    fig, axs = plt.subplots(1, len(modes), figsize=(4.4 * len(modes), 3.3), squeeze=False)
    for ax, (mode, offs) in zip(axs[0], modes):
        x, y, eph = fold_data(tic, "pdc_raw", offs)
        xm, ym, ye = binned(x, y, 0.25)
        ax.plot(x, y, ".", ms=1, color="0.8", rasterized=True)
        ax.errorbar(xm, ym, yerr=ye, fmt="o", ms=3, color="k", lw=0.8)
        a = s11[mode]["A_planet_free"]
        import batman
        pa = batman.TransitParams()
        from s11_shape import a_rs
        pa.t0, pa.per, pa.rp, pa.a = 0, eph["P"], a["k"], a_rs(a["rho_eff"], eph["P"])
        pa.inc = float(np.degrees(np.arccos(min(a["b"] / pa.a, 0.999999))))
        pa.ecc, pa.w, pa.u, pa.limb_dark = 0, 90, eph["u"], "quadratic"
        tt = np.linspace(-9, 9, 800) / 24
        mod = (batman.TransitModel(pa, tt, supersample_factor=5, exp_time=200 / 86400).light_curve(pa) - 1) * 1000
        ax.plot(tt * 24, mod, color="C3", lw=1.2, label=f"best planet model b={a['b']:.2f}")
        ax.set_xlim(-9, 9)
        ax.set_ylim(-4.5, 2.5)
        ax.set_xlabel("hours from predicted mid-transit")
        ax.set_ylabel("relative flux (ppt)")
        ax.set_title(f"{NAMES[tic]}: {'season offsets removed' if offs else 'linear ephemeris'}")
        ax.legend(frameon=False, loc="lower left")
    fig.savefig(FIG / f"F3_{tic}_fold.png")
    plt.close(fig)


def fig_localization():
    fig, axs = plt.subplots(3, 1, figsize=(8.6, 9.0))
    for ax, tic in zip(axs, TICS):
        d = read(RES / f"s07c_localize_{tic}.json")
        fb = {r["id"]: r for r in read(RES / f"s13_fluxbudget_{tic}.json")["neighbours_ranked"]}
        rows = sorted(d["combined"].items(), key=lambda kv: kv[1]["observed_sum_delta_chi2_diag"])
        y = 0
        labels = []
        for gid, v in rows:
            dist = v["injection_distributions"]
            for key, col, dy in (("true_target_mission", "C0", -0.15), ("true_neighbour_mission", "C3", 0.15)):
                if key in dist:
                    q = dist[key]
                    ax.plot([q["p05"], q["p95"]], [y + dy, y + dy], color=col, lw=3, alpha=0.6, solid_capstyle="butt")
                    ax.plot(q["median"], y + dy, "|", color=col, ms=9)
            ax.plot(v["observed_sum_delta_chi2_diag"], y, "kD", ms=5)
            sep = None
            for s in d["sectors"]:
                if gid in s["neighbours_tested"]:
                    sep = s["neighbours_tested"][gid].get("sep_px")
                    break
            need = fb.get(gid, {}).get("eclipse_needed")
            labels.append(f"Gaia ..{gid[-6:]}  {sep * 21:.0f}\"" + (f"  need {need:.2f}" if need else "") if sep else gid[-6:])
            y += 1
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=7)
        ax.axvline(0, color="0.5", lw=0.7)
        ax.set_xscale("symlog", linthresh=50)
        ax.set_xlabel("summed delta chi2 (host = neighbour) - (host = target); positive favours the target")
        ax.set_title(f"{NAMES[tic]}: black = observed; blue = dip injected on target; red = dip injected on neighbour (5-95%)")
    fig.tight_layout()
    fig.savefig(FIG / "F4_localization.png")
    plt.close(fig)


def fig_fluxbudget():
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.2), sharey=True)
    for ax, tic in zip(axs, TICS):
        d = read(RES / f"s13_fluxbudget_{tic}.json")
        rows = d["neighbours_ranked"]
        sep = [r["sep_arcsec"] for r in rows]
        need = [min(r["eclipse_needed"], 50) for r in rows]
        ax.scatter(sep, need, c=[r["dT"] for r in rows], cmap="viridis", s=18)
        ax.axhline(1, color="C3", lw=1, label="100 % eclipse (flux limit)")
        ax.axhline(0.5, color="C1", lw=1, ls="--", label="~50 % main-sequence pair ceiling")
        ax.set_yscale("log")
        ax.set_xlabel("separation (arcsec)")
        ax.set_title(NAMES[tic])
    axs[0].set_ylabel("eclipse fraction the neighbour would need")
    axs[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "F5_flux_budget.png")
    plt.close(fig)


def fig_ztf():
    import pandas as pd
    from s14_ztf import load
    d = read(RES / "s14_ztf_193718989.json")
    e = d["ephemeris"]
    C = np.array(e["cov"])
    T14 = d["T14_d"]
    df = load(RES / "census" / "ztf" / "ztf_lc_gaia1346023547768414976.csv", 267.554464, 42.109629)
    n = np.round((df.btjd.values - (e["T_nref"] - e["nref"] * e["P"])) / e["P"])
    tc = e["T_nref"] + (n - e["nref"]) * e["P"]
    dt = (df.btjd.values - tc) * 24
    sig = np.sqrt(C[0, 0] + 2 * (n - e["nref"]) * C[0, 1] + (n - e["nref"]) ** 2 * C[1, 1]) * 24
    m = np.abs(dt) < 6
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    for band, col in (("zg", "C2"), ("zr", "C3"), ("zi", "C5")):
        mm = m & (df.filtercode.values == band)
        ax.errorbar(dt[mm], df.flux_ratio.values[mm], yerr=df.flux_err.values[mm], xerr=sig[mm], fmt="o", ms=3,
                    color=col, label=f"ZTF {band}", lw=0.7)
    need = read(RES / "s13_fluxbudget_193718989.json")["neighbours_ranked"]
    nd = [r for r in need if r["id"] == "1346023547768414976"][0]["eclipse_needed"]
    xx = np.linspace(-6, 6, 400)
    ax.plot(xx, np.where(np.abs(xx) < T14 * 12, 1 - nd, 1.0), color="k", lw=1, label=f"required eclipse ({nd:.0%}) at nominal timing")
    ax.axvspan(-T14 * 12, T14 * 12, color="0.92", zorder=0)
    ax.set_xlabel("hours from predicted mid-eclipse (x-errors: propagated timing 1 sigma)")
    ax.set_ylabel("flux / oid median")
    ax.set_ylim(0, 1.6)
    ax.set_title("TIC 193718989: ZTF detections of the 9.8\" neighbour near predicted events (detections only)")
    ax.legend(frameon=False, ncol=2, fontsize=7)
    fig.savefig(FIG / "F6_ztf_193_neighbour.png")
    plt.close(fig)


def fig_kprofile():
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.1), sharey=True)
    for ax, tic in zip(axs, TICS):
        s = read(RES / f"s11_shape_{tic}_pdc_raw.json")
        for mode, col in (("linear", "C0"), ("season", "C3")):
            pr = s[mode]["B_k_profile_diluted"]
            ax.plot([p["k"] for p in pr], [p["delta_chi2"] for p in pr], "o-", color=col, ms=3,
                    label=f"{mode} ephemeris" if mode == "linear" else "season timing offsets free")
        ax.axhline(4, color="0.6", lw=0.7, ls=":")
        ax.axhline(9, color="0.6", lw=0.7, ls="--")
        ax.set_xscale("log")
        ax.set_xlabel("occultor/host radius ratio k (dilution free)")
        ax.set_title(NAMES[tic])
    axs[0].set_ylabel("delta chi2 vs best small-planet fit")
    axs[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "F7_k_profiles.png")
    plt.close(fig)


def fig_decomp():
    d = read(RES / "s01_270_reproduce.json")
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.4))
    g = d["decomposition"]["corrected_late_depth_vs_uniform_shift"]
    axs[0].plot([x["shift_d"] * 1440 for x in g], [x["pool"]["snr"] if x["pool"] else np.nan for x in g], "k-")
    sh = d["reproduction"]["corrected"]["predicted_shift_at_late_cycles_d"]
    for c, v in sh.items():
        axs[0].axvline(v * 1440, color="C3", lw=0.6, alpha=0.6)
    axs[0].set_xlabel("uniform timing shift applied to the 7 late corrected events (min)")
    axs[0].set_ylabel("late-event pooled S/N")
    axs[0].set_title("Red: shifts implied by the early-half fit (corrected)")
    ev = read(RES / "s02_events_270573718.json")
    rows = [r for r in ev["events"] if r["reduction"] == "pdc_raw" and r.get("oc_err_d")]
    axs[1].errorbar([r["cycle"] for r in rows], [r["oc_d"] * 1440 for r in rows], yerr=[r["oc_err_d"] * 1440 for r in rows],
                    fmt="o", color="C0", ms=3, label="measured O - C (PDCSAP)")
    ef = d["reproduction"]["corrected"]["early_fit"]
    cc = np.arange(0, 66)
    axs[1].plot(cc, (ef["epoch_correction_d"] + cc * ef["period_correction_d"]) * 1440, "C3-", label="early-half linear fit, extrapolated")
    axs[1].axvline(np.median([r["cycle"] for r in rows]), color="0.5", ls=":", lw=0.8)
    axs[1].set_xlabel("cycle")
    axs[1].set_ylabel("timing offset (min)")
    axs[1].set_title("Why corrected early-predicts-late S/N = 0.29")
    axs[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "F8_270_decomposition.png")
    plt.close(fig)


def fig_halfphase():
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.2), sharey=True)
    for ax, tic in zip(axs, TICS):
        d = read(RES / f"s10_secondary_2p_{tic}.json")
        labs, ys, es, p95 = [], [], [], []
        for red, v in d["reductions"].items():
            if "half_phase" not in v or not v["half_phase"].get("n"):
                continue
            labs.append(red.replace("fu3pix_", "FU3 ").replace("_", " "))
            ys.append(v["half_phase"]["depth_ppt"])
            es.append(v["half_phase"]["err_ppt"])
            p95.append(v["null"]["depth_p95"])
        x = np.arange(len(labs))
        ax.errorbar(x, ys, yerr=es, fmt="o", color="k", ms=4)
        ax.plot(x, p95, "_", color="C3", ms=14, mew=2, label="null 95th percentile")
        ax.axhline(0, color="0.5", lw=0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(labs, rotation=60, ha="right", fontsize=7)
        ax.set_title(f"{NAMES[tic]}: depth at phase 0.5")
    axs[0].set_ylabel("pooled depth (ppt)")
    axs[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "F9_half_phase.png")
    plt.close(fig)


if __name__ == "__main__":
    for t in TICS:
        for f in (fig_depths, fig_oc, fig_fold):
            try:
                f(t)
            except Exception as exc:   # noqa: BLE001
                log("figs", f"{f.__name__} {t} FAILED {exc!r}")
    for f in (fig_localization, fig_fluxbudget, fig_ztf, fig_kprofile, fig_decomp, fig_halfphase):
        try:
            f()
        except Exception as exc:   # noqa: BLE001
            log("figs", f"{f.__name__} FAILED {exc!r}")
    log("figs", "done")
