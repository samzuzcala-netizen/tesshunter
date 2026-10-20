"""Diagnostic figures for the localisation report (PNG, figures/)."""
from __future__ import annotations

import json

import common as C
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

import core
import scene as Sc

R = C.RESULTS
SCENE = json.load(open(R / "scene.json"))
REAL = json.load(open(R / "real_events.json"))
JOINT = json.load(open(R / "joint.json"))
CTRL = json.load(open(R / "controls_full_summary.json"))
HOSTA = json.load(open(R / "host_assessment.json"))
DEC = json.load(open(R / "decision.json"))
EVS = ["E00", "E32", "E33", "E39"]
LBL = {"E00": "E00 s57 (kept)", "E32": "E32 s79 (kept)", "E33": "E33 s80 (kept)", "E39": "E39 s84 (excluded; diagnostic)"}
SHORT = {s: s[-6:] for s in core.HOSTS}
HCOL = {C.GAIA_TARGET: "magenta"}
for s in C.LISTED_NEIGHBOURS:
    HCOL[s] = "darkorange"
for s in core.HOSTS:
    HCOL.setdefault(s, "deepskyblue")
LEV = [2.30, 6.18, 11.83]


def compass(ax, ctx, x0=17.5, y0=2.0, L=2.2):
    ra0, de0 = ctx.S.wcs.all_pix2world(x0, y0, 0)
    for dra, dde, lab in ((0, 40 / 3600, "N"), (40 / 3600 / np.cos(np.radians(de0)), 0, "E")):
        x1, y1 = ctx.S.wcs.all_pix2world(0, 0, 0)  # dummy
        px, py = ctx.S.wcs.all_world2pix(ra0 + dra, de0 + dde, 0)
        v = np.array([px - x0, py - y0]); v = v / np.hypot(*v) * L
        ax.annotate("", xy=(x0 + v[0], y0 + v[1]), xytext=(x0, y0), arrowprops=dict(arrowstyle="->", color="w", lw=1.5))
        ax.text(x0 + 1.25 * v[0], y0 + 1.25 * v[1], lab, color="w", fontsize=8, ha="center", va="center")


def mark_sources(ax, ctx, cat, tmax=19.6, labels=False):
    for k in range(len(cat)):
        x, y = ctx.x[k], ctx.y[k]
        if not (-0.5 < x < 20.5 and -0.5 < y < 20.5) or not np.isfinite(cat[k]["tmag"]) or cat[k]["tmag"] > tmax:
            continue
        sid = cat[k]["source_id"]
        if sid in core.HOSTS:
            ax.plot(x, y, marker="*" if sid == C.GAIA_TARGET else "o", ms=12 if sid == C.GAIA_TARGET else 7,
                    mfc="none", mec=HCOL[sid], mew=1.6)
            if labels:
                ax.text(x + 0.25, y + 0.25, "T" if sid == C.GAIA_TARGET else SHORT[sid], color=HCOL[sid], fontsize=6.5)
        else:
            ax.plot(x, y, "o", ms=max(2.0, 8.5 - 0.5 * (cat[k]["tmag"] - 10)), mfc="none", mec="0.25", mew=0.7)


def fig_scene(cat, ctxs):
    fig, axes = plt.subplots(2, 4, figsize=(18, 9.2))
    for j, e in enumerate(EVS):
        z = np.load(C.ARRAYS / "scene" / f"scene_{e}.npz")
        ctx = ctxs[e]
        ax = axes[0, j]
        im = ax.imshow(np.log10(np.clip(z["img"], 1, None)), origin="lower", cmap="viridis")
        plt.colorbar(im, ax=ax, fraction=0.046, label="log10 e-/s")
        mark_sources(ax, ctx, cat, labels=True)
        r0, r1, c0, c1 = ctx.fitter.box
        ax.add_patch(plt.Rectangle((c0 - .5, r0 - .5), c1 - c0 + 1, r1 - r0 + 1, fill=False, ec="w", ls="--", lw=0.8))
        compass(ax, ctx)
        reg = SCENE["events"][e]["registration"]
        ax.set_title(f"{LBL[e]}  cam{ctx.S.camera}/ccd{ctx.S.ccd}\nout-of-event median; registration "
                     f"dcol {reg['dx']:+.3f}, drow {reg['dy']:+.3f} px", fontsize=9)
        ax = axes[1, j]
        rr = z["resid"] / np.sqrt(z["err"] ** 2 + (0.03 * np.clip(z["img"], 0, None)) ** 2)
        im = ax.imshow(rr, origin="lower", cmap="RdBu_r", vmin=-5, vmax=5)
        plt.colorbar(im, ax=ax, fraction=0.046, label="(data - scene model)/err")
        mark_sources(ax, ctx, cat)
        ax.set_title(f"scene-model residual (PRF x Gaia, ZP {SCENE['events'][e]['zero_point']:.2f})", fontsize=9)
    leg = [Line2D([], [], marker="*", ls="", mfc="none", mec="magenta", ms=11, label="target Gaia ...475136"),
           Line2D([], [], marker="o", ls="", mfc="none", mec="darkorange", label="4 listed neighbours"),
           Line2D([], [], marker="o", ls="", mfc="none", mec="deepskyblue", label="other sources <=3.6 px"),
           Line2D([], [], marker="o", ls="", mfc="none", mec="0.25", label="other Gaia (T<19.6)")]
    fig.legend(handles=leg, loc="lower center", ncol=4, fontsize=9)
    fig.suptitle("TIC 332366289: stellar scene in native TESScut pixels (21x21; dashed = 11x11 fit box; arrows N/E)", fontsize=11)
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    fig.savefig(C.FIGURES / "fig1_scene.png", dpi=90); plt.close(fig)


def fig_event(e, cat, ctx):
    z = np.load(C.ARRAYS / "real" / f"{e}_primary.npz")
    D, s = z["D"], z["sigma"]
    r0, r1, c0, c1 = z["box"]
    v = float(np.nanpercentile(np.abs(D[r0:r1 + 1, c0:c1 + 1]), 99))
    fig, axes = plt.subplots(2, 4, figsize=(18, 8.6))
    panels = [(z["out"], "expected out-of-event image at event times (e-/s)", "viridis", "log"),
              (z["inn"], "in-event mean image (e-/s)", "viridis", "log"),
              (D, "signed D = out - in (e-/s/pixel); +ve = lost", "RdBu_r", v),
              (D / s, "D / sigma (kappa-scaled)", "RdBu_r", 5.0),
              (None, "dimming-only profile dchi2 (A>=0): 68/95/99.7%", "magma_r", None),
              (z["model_target"], "PRF + plane model, source at target", "RdBu_r", v),
              (z["resid_target"], "residual D - model(target)", "RdBu_r", v),
              (z["resid_best"], "residual D - model(dimming best)", "RdBu_r", v)]
    for k, (img, ttl, cm, lim) in enumerate(panels):
        ax = axes.flat[k]
        if img is None:
            gx, gy, cp = z["grid_x"], z["grid_y"], z["chi2p"]
            dm = cp - cp.min()
            im = ax.pcolormesh(gx, gy, np.clip(dm, 0, 40), cmap=cm, shading="auto")
            ax.contour(gx, gy, dm, levels=LEV, colors=["w", "cyan", "lime"], linewidths=1.2)
            ax.set_xlim(-0.5, 20.5); ax.set_ylim(-0.5, 20.5); ax.set_aspect("equal")
            plt.colorbar(im, ax=ax, fraction=0.046, label="dchi2 (clipped at 40)")
        elif lim == "log":
            im = ax.imshow(np.log10(np.clip(img, 1, None)), origin="lower", cmap=cm)
            plt.colorbar(im, ax=ax, fraction=0.046)
        else:
            im = ax.imshow(img, origin="lower", cmap=cm, vmin=-lim, vmax=lim)
            plt.colorbar(im, ax=ax, fraction=0.046)
        mark_sources(ax, ctx, cat, labels=(k == 4))
        ax.add_patch(plt.Rectangle((c0 - .5, r0 - .5), c1 - c0 + 1, r1 - r0 + 1, fill=False, ec="k", ls="--", lw=0.7))
        rb = REAL[e]["dimming_best"]
        ax.plot(rb["x"], rb["y"], "x", color="lime", ms=10, mew=2)
        sb = REAL[e]["signed_best"]
        if sb["A"] < 0:
            ax.plot(sb["x"], sb["y"], "+", color="cyan", ms=11, mew=2)
        ax.set_title(ttl, fontsize=9)
    t = REAL[e]["target"]
    fig.suptitle(f"{LBL[e]}: in-event frames {REAL[e]['n_in']}, reference {REAL[e]['n_ref']}; target A = {t['A']:.2f} +/- {t['sA']:.2f} e-/s "
                 f"(S/N {t['snr']:.2f}); dimming best (lime x) {rb['offset_px']:.2f} px from target, A = {rb['A']:.2f} (S/N {rb['snr']:.2f})"
                 + ("; cyan + = signed best (brightening)" if sb["A"] < 0 else ""), fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(C.FIGURES / f"fig2_event_{e}.png", dpi=85); plt.close(fig)


def _binned(dt, y, width_h=0.5):
    edges = np.arange(np.floor(dt.min()), np.ceil(dt.max()) + width_h, width_h)
    idx = np.digitize(dt, edges)
    xb, yb, eb = [], [], []
    for k in np.unique(idx):
        m = idx == k
        if m.sum() >= 4:
            xb.append(dt[m].mean()); yb.append(np.mean(y[m])); eb.append(np.std(y[m]) / np.sqrt(m.sum()))
    return np.array(xb), np.array(yb), np.array(eb)


def fig_lightcurves():
    """Background-subtracted local photometry from the TESScut cube (SPOC optimal aperture and
    3x3 box, minus n_pix x per-frame background), linear trend fitted to the reference frames
    removed, plus TESS-SPOC SAP and PDCSAP; 200-s points and 30-min bins; masks shaded."""
    fig, axes = plt.subplots(4, 3, figsize=(17, 13), sharex=True)
    hw = core.EA["duration_d"] * 12
    for i, e in enumerate(EVS):
        z = np.load(C.ARRAYS / "real" / f"{e}_primary.npz")
        dt, role = z["ser_dt_h"], z["ser_role"]
        ref = (role == 3) | (role == 4)
        def shade(ax):
            ax.axvspan(-hw, hw, color="0.85", zorder=0)
            ax.axvspan(-hw - 1.0, -hw, color="#f6e7c1", zorder=0)
            ax.axvspan(hw, hw + 1.0, color="#f6e7c1", zorder=0)
        ax = axes[i, 0]; shade(ax)
        nap = int(z["ap"].sum())
        series = [(z["ser_ap"] - nap * z["ser_bkg"], f"TESScut SPOC-aperture sum - {nap} x bkg", "k", 0),
                  (z["ser_box3"] - 9 * z["ser_bkg"], "TESScut 3x3 box - 9 x bkg", "C0", -20)]
        if z["ser_sap"].size and np.isfinite(z["ser_sap"]).sum() > 10:
            series.append((z["ser_sap"], "TESS-SPOC SAP", "C2", -40))
        if z["ser_pdc"].size and np.isfinite(z["ser_pdc"]).sum() > 10:
            series.append((z["ser_pdc"], "TESS-SPOC PDCSAP", "C3", -60))
        for arr, lab, c, off in series:
            ok = np.isfinite(arr)
            r = ok & ref
            if r.sum() < 10:
                continue
            fitc = np.polyfit(dt[r], arr[r], 1)
            y = 1e3 * (arr[ok] / np.polyval(fitc, dt[ok]) - 1)
            ax.plot(dt[ok], y + off, ".", ms=1.6, color=c, alpha=0.35)
            xb, yb, eb = _binned(dt[ok], y)
            ax.errorbar(xb, yb + off, eb, fmt="o", ms=3.5, color=c, label=f"{lab} (offset {off})")
            ax.axhline(off, color="0.5", lw=0.6)
        ax.set_ylim(-85, 20); ax.set_ylabel(f"{e}: ppt")
        if i == 0:
            ax.legend(fontsize=6.5, loc="lower left", ncol=2)
        t = REAL[e]["target"]
        ax.set_title(f"{LBL[e]}: local light curves (30-min bins); pixel-fit deficit at target "
                     f"{1000 * t['A'] / REAL[e]['hosts'][C.GAIA_TARGET]['flux_e_s']:.1f} ppt", fontsize=9)
        ax = axes[i, 1]; shade(ax)
        ax.plot(dt, z["ser_bkg"], ".", ms=2.5, color="C4", label="TESScut background (mean of faintest 20% pixels)")
        if z["ser_sapbkg"].size:
            ax.plot(dt, z["ser_sapbkg"] / max(1, nap), ".", ms=2, color="C1", alpha=0.7, label="TESS-SPOC SAP_BKG / n_ap")
        ax.set_ylabel("e-/s/pixel"); ax.set_title("background series", fontsize=9)
        if i == 0:
            ax.legend(fontsize=7)
        ax = axes[i, 2]; shade(ax)
        ax.plot(dt, z["ser_cx"] - np.median(z["ser_cx"][ref]), ".", ms=2.5, label="col centroid (5x5, bkg-sub)")
        ax.plot(dt, z["ser_cy"] - np.median(z["ser_cy"][ref]), ".", ms=2.5, label="row centroid")
        ax.set_ylim(-0.08, 0.08); ax.set_ylabel("px"); ax.set_title("flux-weighted centroid (motion diagnostic)", fontsize=9)
        if i == 0:
            ax.legend(fontsize=7)
    for ax in axes[-1]:
        ax.set_xlabel("hours from E_A centre (grey in-event, tan guard, white reference)")
    fig.tight_layout()
    fig.savefig(C.FIGURES / "fig3_lightcurves_masks.png", dpi=85); plt.close(fig)


def fig_skymap(ctxs):
    z = np.load(C.ARRAYS / "real" / "joint_maps.npz")
    xi, eta = z["xi"], z["eta"]
    fig, axes = plt.subplots(1, 2, figsize=(17, 8.2))
    host_pos = {}
    jo = JOINT["origin"]
    for s in core.HOSTS:
        k = ctxs["E00"].ids.index(s)
        ra = np.mean([ctxs[e].ra[k] for e in core.PRIMARY]); de = np.mean([ctxs[e].dec[k] for e in core.PRIMARY])
        host_pos[s] = ((ra - jo["ra0"]) * 3600 * np.cos(np.radians(jo["dec0"])), (de - jo["dec0"]) * 3600)
    for ax, mode in zip(axes, ("dimming", "signed")):
        tot = z[f"{mode}_tot"]; dm = tot - np.nanmin(tot)
        im = ax.pcolormesh(xi, eta, np.clip(dm, 0, 60), cmap="magma_r", shading="auto")
        plt.colorbar(im, ax=ax, fraction=0.046, label="joint dchi2 (clipped 60)")
        ax.contour(xi, eta, dm, levels=LEV, colors=["k", "k", "k"], linestyles=["-", "--", ":"], linewidths=1.3)
        if mode == "dimming":
            mg = z["dimming_marg"]
            ax.contour(xi, eta, mg, levels=[6.18], colors=["w"], linestyles=["-."], linewidths=1.3)
        cols = {"E00": "C0", "E32": "C2", "E33": "C3", "E39": "0.5"}
        for e in EVS:
            se = z[f"{mode}_single_{e}"]; sd = se - np.nanmin(se)
            ax.contour(xi, eta, sd, levels=[6.18], colors=[cols[e]], linewidths=1.0, linestyles="-" if e != "E39" else ":")
        for k, v in JOINT[mode]["leave_one_out"].items():
            ax.plot(v["best"]["xi"], v["best"]["eta"], "s", mfc="none", mec="0.2", ms=7)
            ax.text(v["best"]["xi"] + 2, v["best"]["eta"] + 2, k.replace("without_", "LOO-"), fontsize=7)
        b = JOINT[mode]["primary"]["best"]
        ax.plot(b["xi"], b["eta"], "x", color="lime", ms=12, mew=2.5)
        for s, (x, y) in host_pos.items():
            if abs(x) < 85 and abs(y) < 85:
                ax.plot(x, y, marker="*" if s == C.GAIA_TARGET else "o", ms=14 if s == C.GAIA_TARGET else 8, mfc="none", mec=HCOL[s], mew=2)
                ax.text(x + 2.5, y - 4, "target" if s == C.GAIA_TARGET else s[-6:], color=HCOL[s], fontsize=8, weight="bold")
        ax.plot([60, 81], [-78, -78], "k-", lw=3); ax.text(70.5, -75, "1 TESS px (21\")", ha="center", fontsize=8)
        ax.set_xlim(85, -85); ax.set_ylim(-85, 85); ax.set_aspect("equal")
        ax.set_xlabel("xi = East offset (arcsec; East to the LEFT)"); ax.set_ylabel("eta = North offset (arcsec)")
        ttl = ("DIMMING-ONLY (A>=0; decision mode)" if mode == "dimming" else "SIGNED amplitude (diagnostic)")
        ax.set_title(f"{ttl}: joint s57+s79+s80\nblack 68/95/99.7% (stat.)" + (", white dash-dot 95% incl. registration MC" if mode == "dimming" else "")
                     + "; per-event 95%: blue E00, green E32, red E33, grey dotted E39", fontsize=9)
    fig.suptitle("Common sky map around TIC 332366289 (origin = target, mean epoch of the 3 retained events); lime x = joint best; squares = leave-one-out bests", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(C.FIGURES / "fig4_skymap.png", dpi=90); plt.close(fig)


def fig_controls():
    nj = [json.loads(l) for l in open(R / "controls_full" / "null_joint.jsonl")]
    ij = [json.loads(l) for l in open(R / "controls_full" / "inj_joint.jsonl")]
    from scipy.stats import chi2 as chi2d
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    ax = axes[0, 0]
    lam = np.array([r["Lambda_dimming"] for r in nj])
    ax.hist(lam, bins=40, color="0.6", label=f"null joint (n={lam.size}; {sum(r['all_independent'] for r in nj)} all-independent)")
    ax.axvline(DEC["pixel_detection"]["Lambda_real"], color="r", lw=2, label=f"real {DEC['pixel_detection']['Lambda_real']:.1f}")
    ax.axvline(DEC["pixel_detection"]["Lambda_null_p99"], color="k", ls="--", label=f"null p99 {DEC['pixel_detection']['Lambda_null_p99']:.1f}")
    for cfg, c in (("target_LC", "C0"), ("target_PIX", "C2")):
        v = [r["Lambda_dimming"] for r in ij if r["config"] == cfg]
        ax.hist(np.clip(v, 0, 150), bins=40, histtype="step", color=c, lw=1.5, label=f"injected {cfg}")
    ax.set_xlabel("joint free-position improvement Lambda (dimming-only)"); ax.legend(fontsize=8); ax.set_xlim(0, 150)
    ax = axes[0, 1]
    tsn = np.array([r["target_snr_joint"] for r in nj])
    ax.hist(tsn, bins=30, color="0.6", label="null joint")
    for cfg, c in (("target_LC", "C0"), ("target_PIX", "C2")):
        v = [r["target_snr_joint"] for r in ij if r["config"] == cfg]
        ax.hist(v, bins=30, histtype="step", color=c, lw=1.5, label=f"injected {cfg}")
    ax.axvline(DEC["pixel_detection"]["target_snr_joint"], color="r", lw=2, label=f"real {DEC['pixel_detection']['target_snr_joint']:.2f}")
    ax.set_xlabel("joint target-position amplitude S/N"); ax.legend(fontsize=8)
    ax = axes[1, 0]
    Q = np.array([r["Q_dimming"] for r in nj])
    ax.hist(Q, bins=40, density=True, color="0.6", label="null joint Q (dimming)")
    xx = np.linspace(0, 60, 300); ax.plot(xx, chi2d.pdf(xx, 4), "k--", label="textbook chi2(4) (invalid here)")
    ax.axvline(DEC["inconsistency"]["Q_real"], color="r", lw=2, label=f"real Q {DEC['inconsistency']['Q_real']:.1f}")
    ax.set_xlim(0, 60); ax.set_xlabel("position-consistency Q"); ax.legend(fontsize=8)
    ax = axes[1, 1]
    inj = CTRL["injections"]
    names = list(inj.keys())
    y = np.arange(len(names))
    for off, key, c, lab in ((-0.27, ("coverage", "95.45"), "C0", "coverage of 95.45% region"),
                             (0.0, ("assigned_to_true_host",), "C2", "best catalogue host = true host"),
                             (0.27, ("all_other_hosts_excluded_dchi2_ge_9",), "C3", "all other hosts excluded (dchi2>=9)")):
        vals, lo, hi = [], [], []
        for n in names:
            d = inj[n]
            for kk in key:
                d = d[kk]
            vals.append(d["frac"]); lo.append(max(0.0, d["frac"] - d["wilson95"][0])); hi.append(max(0.0, d["wilson95"][1] - d["frac"]))
        ax.barh(y + off, vals, height=0.26, color=c, xerr=[lo, hi], label=lab, error_kw=dict(lw=0.8))
    ax.set_yticks(y); ax.set_yticklabels([f"{n} ({inj[n]['n_joint']})" for n in names], fontsize=8)
    ax.axvline(0.85, color="k", ls=":", lw=1); ax.set_xlim(0, 1.05); ax.invert_yaxis()
    ax.set_xlabel("fraction of joint injections (Wilson 95%); ~35 independent windows/sector reused")
    ax.legend(fontsize=7, loc="lower right")
    fig.suptitle("Null controls (130 joint combinations of control windows) and complete-procedure pixel injections (100 joint per config)", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(C.FIGURES / "fig5_controls.png", dpi=85); plt.close(fig)


def fig_hosts():
    rows = HOSTA["hosts"]
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.5))
    names = [("target" if r["gaia_dr3_source_id"] == C.GAIA_TARGET else r["gaia_dr3_source_id"][-6:]) + f"\n{r['sep_arcsec_epoch2024']:.0f}\", T{r['tmag']:.1f}" for r in rows]
    x = np.arange(len(rows))
    ax = axes[0]
    ax.bar(x - 0.2, [r["joint_dchi2_vs_best_catalogue"] for r in rows], 0.4, label="joint dchi2 vs best catalogue host")
    for j, key in enumerate(("without_E00", "without_E32", "without_E33")):
        ax.plot(x + 0.15 + 0.08 * j, [r["loo_dchi2_vs_best_catalogue"][key] for r in rows], "o", ms=5, label=f"LOO {key}")
    ax.axhline(9, color="r", ls="--", label="spatial exclusion bar (9)")
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=8); ax.legend(fontsize=8); ax.set_ylabel("dchi2 (dimming-only)")
    ax.set_title("spatial compatibility of each host hypothesis (lower = more compatible)", fontsize=10)
    ax = axes[1]
    A = np.array([r["pixel_A_joint"][0] for r in rows]); Ae = np.array([r["pixel_A_joint"][1] for r in rows])
    ax.errorbar(x - 0.15, A, Ae, fmt="o", color="k", label="pixel-fit missing flux at host position (joint)")
    for k, c, off in (("pdc", "C3", 0.0), ("sap", "C2", 0.15)):
        v = np.array([r["lc_matched"][k]["A_required_e_s"] for r in rows]); ve = np.array([r["lc_matched"][k]["A_required_err"] for r in rows])
        ax.errorbar(x + off, v, ve, fmt="s", color=c, label=f"required to make the {k.upper()} aperture dip")
    ax.plot(x, [r["flux_e_s_mean"] for r in rows], "_", ms=22, mew=2.5, color="C0", label="host total flux (100% eclipse)")
    ax.set_yscale("symlog", linthresh=1); ax.set_xticks(x); ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("missing flux (e-/s, symlog)"); ax.legend(fontsize=8)
    ax.set_title("lost-flux feasibility: measured vs required missing flux per host", fontsize=10)
    fig.tight_layout()
    fig.savefig(C.FIGURES / "fig6_hosts.png", dpi=90); plt.close(fig)


def main():
    cat = Sc.load_catalogue()
    ctxs = {e: core.EventContext(e, cat=cat, scene_json=SCENE) for e in EVS}
    fig_scene(cat, ctxs)
    for e in EVS:
        fig_event(e, cat, ctxs[e])
    fig_lightcurves()
    fig_skymap(ctxs)
    fig_controls()
    fig_hosts()
    print("figures written:", sorted(p.name for p in C.FIGURES.glob("fig*.png")))


if __name__ == "__main__":
    main()
