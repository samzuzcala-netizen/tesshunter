"""Null control windows and complete-procedure pixel injections (same recipe as
the real events), single-sector and joint (one window per primary sector).

usage: python run_controls.py smoke|full
Writes results/controls_<mode>/*.jsonl and results/controls_<mode>_summary.json.
"""
from __future__ import annotations

import csv
import json
import sys
import time
import zlib

import common as C
import numpy as np

import core
import jointfit as JF
import scene as Sc

KAPPA = {int(k): v["kappa"] for k, v in json.load(open(C.RESULTS / "kappa.json")).items()}
SCENE = json.load(open(C.RESULTS / "scene.json"))
JOINT_REAL = json.load(open(C.RESULTS / "joint.json"))
SECTOR_EVENT = {57: "E00", 79: "E32", 80: "E33"}
SEED = core.CFG["controls"]["seed"]
DEPTH_LC = 0.0065  # Stage A kept-event weighted PDCSAP depth (det_kept), the predeclared matched signal
LISTED = list(C.LISTED_NEIGHBOURS)
EXTRA_BRIGHT = "1415338543194435712"


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [float(c - h), float(c + h)]


def configs(ctxs):
    a_pix = JOINT_REAL["dimming"]["primary"]["hosts"][C.GAIA_TARGET]["A_weighted"]
    out = []
    out.append({"name": "target_LC", "host": C.GAIA_TARGET, "level": "LC-matched (PDCSAP 6.5 ppt)"})
    out.append({"name": "target_PIX", "host": C.GAIA_TARGET, "level": f"pixel-matched ({a_pix:.3f} e-/s)", "A_fixed": a_pix})
    for sid in LISTED:
        out.append({"name": f"nb{sid[-6:]}_LC", "host": sid, "level": "LC-matched in the SPOC aperture, capped at host flux"})
        out.append({"name": f"nb{sid[-6:]}_PIX", "host": sid, "level": f"pixel-matched ({a_pix:.3f} e-/s), capped",
                    "A_fixed": a_pix})
    out.append({"name": f"nb{EXTRA_BRIGHT[-6:]}_LC", "host": EXTRA_BRIGHT, "level": "LC-matched, capped"})
    return out


def amplitude(cfg, ctx):
    k = ctx.ids.index(cfg["host"])
    f_host = ctx.flux_of(k)
    eps_t = ctx.aperture_fraction(ctx.xt, ctx.yt)
    eps_h = ctx.aperture_fraction(ctx.x[k], ctx.y[k])
    if "A_fixed" in cfg:
        req = cfg["A_fixed"]
    else:
        req = DEPTH_LC * ctx.f_target * eps_t / max(eps_h, 1e-6)  # missing flux reproducing the aperture dip
    capped = req > f_host
    return {"A_required": float(req), "A_injected": float(min(req, f_host)), "capped": bool(capped),
            "host_flux": float(f_host), "eps_target": eps_t, "eps_host": eps_h,
            "required_eclipse_fraction": float(req / f_host)}


def one(ctx, tc, host_ids, inject=None):
    return core.analyse(ctx, tc, core.EA["duration_d"], kappa=KAPPA[ctx.sector],
                        host_idx=[ctx.ids.index(s) for s in host_ids], keep_maps=True, inject=inject)


def row_of(res, ctx, true_sid=None):
    r = {"tc": res["tc"], "chi2_0": res["chi2_0"], "freep_improvement": res["freep_improvement"],
         "free_improvement": res["free_improvement"],
         "bestp_snr": res["bestp_A"] / res["bestp_sA"], "bestp_x": res["bestp_x"], "bestp_y": res["bestp_y"],
         "best_snr": res["best_A"] / res["best_sA"],
         "target_A": res["hosts"][C.GAIA_TARGET]["A"], "target_sA": res["hosts"][C.GAIA_TARGET]["sA"],
         "hosts_chi2p": {s: h["chi2p"] for s, h in res["hosts"].items()},
         "hosts_A": {s: h["A"] for s, h in res["hosts"].items()}}
    r["assigned_host"] = min(r["hosts_chi2p"], key=r["hosts_chi2p"].get)
    if true_sid is not None:
        k = ctx.ids.index(true_sid)
        r["dchi2p_true_vs_free"] = res["hosts"][true_sid]["chi2p"] - res["bestp_chi2"]
        r["bestp_offset_from_true_px"] = float(np.hypot(res["bestp_x"] - ctx.x[k], res["bestp_y"] - ctx.y[k]))
    return r


def main(mode):
    t_start = time.time()
    out_dir = C.RESULTS / f"controls_{mode}"
    out_dir.mkdir(parents=True, exist_ok=True)
    cat = Sc.load_catalogue()
    ctxs = {sec: core.EventContext(SECTOR_EVENT[sec], cat=cat, scene_json=SCENE) for sec in SECTOR_EVENT}
    ctx_by_e = {SECTOR_EVENT[s]: c for s, c in ctxs.items()}
    jr = JOINT_REAL["origin"]
    sky = JF.sky_setup(ctx_by_e, jr["ra0"], jr["dec0"])
    ctrl = list(csv.DictReader(open(C.RESULTS / "controls.csv")))
    wins = {sec: [r for r in ctrl if int(r["sector"]) == sec] for sec in SECTOR_EVENT}
    n_real = 5 if mode == "smoke" else 100
    n_null = 5 if mode == "smoke" else min(len(v) for v in wins.values())
    hosts = core.HOSTS
    # ------------------------------------------------------------ nulls
    null_rows, null_joint = [], []
    for i in range(n_null):
        ress = {}
        for sec, ctx in ctxs.items():
            w = wins[sec][i]
            res = one(ctx, float(w["tc_btjd"]), hosts)
            ress[SECTOR_EVENT[sec]] = res
            rr = row_of(res, ctx)
            rr.update({"sector": sec, "window_id": w["window_id"], "independent": w["independent"] == "True", "half": w["half"]})
            null_rows.append(rr)
        jd = JF.joint(ctx_by_e, ress, core.PRIMARY, sky, mode="dimming", host_ids=hosts)
        js = JF.joint(ctx_by_e, ress, core.PRIMARY, sky, mode="signed", host_ids=hosts)
        th = jd["hosts"][C.GAIA_TARGET]
        null_joint.append({"i": i, "windows": [wins[s][i]["window_id"] for s in SECTOR_EVENT],
                           "all_independent": all(wins[s][i]["independent"] == "True" for s in SECTOR_EVENT),
                           "Lambda_dimming": jd["free_improvement"], "Lambda_signed": js["free_improvement"],
                           "Q_dimming": jd["Q_consistency"], "Q_signed": js["Q_consistency"],
                           "target_snr_joint": th["snr_weighted"], "target_A_joint": th["A_weighted"],
                           "assigned_host": jd["best_catalogue_host"],
                           "best_xi": jd["best"]["xi"], "best_eta": jd["best"]["eta"]})
    with open(out_dir / "null_single.jsonl", "w") as fh:
        for r in null_rows:
            fh.write(json.dumps(C.clean(r)) + "\n")
    with open(out_dir / "null_joint.jsonl", "w") as fh:
        for r in null_joint:
            fh.write(json.dumps(C.clean(r)) + "\n")
    lam = np.array([r["Lambda_dimming"] for r in null_joint])
    lam99 = float(np.percentile(lam, 99)) if lam.size else None
    print("nulls done", len(null_rows), "joint", len(null_joint), "Lambda99 %.2f" % lam99, "t=%.0fs" % (time.time() - t_start))
    # ------------------------------------------------------------ injections
    cfgs = configs(ctx_by_e)
    amp_table = {c["name"]: {SECTOR_EVENT[s]: amplitude(c, ctxs[s]) for s in SECTOR_EVENT} for c in cfgs}
    inj_rows, inj_joint = [], []
    for cfg in cfgs:
        true = cfg["host"]
        for i in range(n_real):
            ress, meta = {}, {}
            for sec, ctx in ctxs.items():
                nw = len(wins[sec])
                widx = int(round(i * (nw - 1) / max(1, n_real - 1)))
                w = wins[sec][widx]
                tc = float(w["tc_btjd"])
                amp = amp_table[cfg["name"]][SECTOR_EVENT[sec]]
                rng = np.random.default_rng([SEED, zlib.crc32(cfg["name"].encode()), i, sec])
                k = ctx.ids.index(true)
                perturbed = (i % 2 == 1)
                ws, ox, oy = 1.0, 0.0, 0.0
                if perturbed:
                    ws = float(rng.uniform(0.9, 1.1)); ox, oy = rng.normal(0, 0.1, 2)
                img = ctx.prf_tess.render(ctx.x[k] + ox, ctx.y[k] + oy, ctx.S.flux.shape[1:], ws)
                inj = {"img": img, "A": amp["A_injected"], "tc": tc, "dur": core.EA["duration_d"]}
                res = one(ctx, tc, hosts, inject=inj)
                ress[SECTOR_EVENT[sec]] = res
                rr = row_of(res, ctx, true)
                rr.update({"config": cfg["name"], "true_host": true, "i": i, "sector": sec, "window_id": w["window_id"],
                           "independent": w["independent"] == "True", "half": w["half"], "A_injected": amp["A_injected"],
                           "capped": amp["capped"], "perturbed": perturbed, "width_scale": ws, "offset_px": [float(ox), float(oy)]})
                inj_rows.append(rr)
            jd = JF.joint(ctx_by_e, ress, core.PRIMARY, sky, mode="dimming", host_ids=hosts)
            th = jd["hosts"][C.GAIA_TARGET]
            truej = jd["hosts"][true]
            # sky position of the true host (mean epoch) vs joint best
            kk = ctx_by_e["E00"].ids.index(true)
            ra_t = np.mean([ctx_by_e[e].ra[kk] for e in core.PRIMARY]); dec_t = np.mean([ctx_by_e[e].dec[kk] for e in core.PRIMARY])
            others = {s: h["chi2"] - truej["chi2"] for s, h in jd["hosts"].items() if s != true}
            inj_joint.append({"config": cfg["name"], "true_host": true, "i": i, "perturbed": (i % 2 == 1),
                              "Lambda_dimming": jd["free_improvement"], "Q_dimming": jd["Q_consistency"],
                              "target_snr_joint": th["snr_weighted"], "target_A_joint": th["A_weighted"],
                              "true_A_joint": truej["A_weighted"], "true_snr_joint": truej["snr_weighted"],
                              "dchi2_true_vs_free": truej["dchi2_vs_free"], "assigned_host": jd["best_catalogue_host"],
                              "min_dchi2_other_minus_true": float(min(others.values())) if others else None,
                              "dchi2_others_minus_true": others,
                              "best_offset_from_true_arcsec": float(Sc.sep_arcsec(ra_t, dec_t, jd["best"]["ra"], jd["best"]["dec"])),
                              "pixel_detected": bool(th["snr_weighted"] >= 3 and jd["free_improvement"] > lam99)})
        print("config", cfg["name"], "done t=%.0fs" % (time.time() - t_start), amp_table[cfg["name"]]["E00"])
    with open(out_dir / "inj_single.jsonl", "w") as fh:
        for r in inj_rows:
            fh.write(json.dumps(C.clean(r)) + "\n")
    with open(out_dir / "inj_joint.jsonl", "w") as fh:
        for r in inj_joint:
            fh.write(json.dumps(C.clean(r)) + "\n")
    # ------------------------------------------------------------ summaries
    summ = {"mode": mode, "n_null_per_sector": n_null, "n_inj_per_config_per_sector": n_real,
            "independent_windows_per_sector": {s: sum(1 for w in wins[s] if w["independent"] == "True") for s in wins},
            "windows_available_per_sector": {s: len(wins[s]) for s in wins},
            "null_joint_Lambda_dimming_p99": lam99,
            "null_joint_Lambda_dimming_quantiles": {q: float(np.percentile(lam, q)) for q in (50, 90, 95, 99)} if lam.size else {},
            "amplitudes": amp_table, "wall_s": time.time() - t_start}
    # null single-sector look-elsewhere distributions
    ns = {}
    for sec in SECTOR_EVENT:
        rr = [r for r in null_rows if r["sector"] == sec]
        bs = np.array([r["bestp_snr"] for r in rr]); ts = np.array([r["target_A"] / r["target_sA"] for r in rr])
        ns[str(sec)] = {"n": len(rr), "n_independent": sum(r["independent"] for r in rr),
                        "max_dimming_snr_quantiles": {q: float(np.percentile(bs, q)) for q in (50, 90, 95, 99)},
                        "target_snr_mean": float(np.mean(ts)), "target_snr_std": float(np.std(ts)),
                        "frac_target_snr_ge_3": float(np.mean(ts >= 3)),
                        "frac_bestp_snr_ge_3": float(np.mean(bs >= 3))}
    summ["null_single"] = ns
    tj = np.array([r["target_snr_joint"] for r in null_joint])
    summ["null_joint"] = {"n": len(null_joint), "n_all_independent": sum(r["all_independent"] for r in null_joint),
                          "target_snr_joint_mean": float(np.mean(tj)), "target_snr_joint_std": float(np.std(tj)),
                          "frac_target_snr_joint_ge_3": float(np.mean(tj >= 3)),
                          "frac_target_snr_joint_ge_3_7": float(np.mean(tj >= 3.73)),
                          "frac_pixel_detected": float(np.mean([(r["target_snr_joint"] >= 3) and (r["Lambda_dimming"] > lam99) for r in null_joint])),
                          "Q_dimming_quantiles": {q: float(np.percentile([r["Q_dimming"] for r in null_joint], q)) for q in (50, 90, 95, 99)},
                          "assigned_host_counts": {s: sum(1 for r in null_joint if r["assigned_host"] == s) for s in core.HOSTS}}
    inj = {}
    for cfg in cfgs:
        rr = [r for r in inj_joint if r["config"] == cfg["name"]]
        n = len(rr)
        cov = {lvl: sum(1 for r in rr if r["dchi2_true_vs_free"] <= thr) for lvl, thr in JF.D2.items()}
        assigned_true = sum(1 for r in rr if r["assigned_host"] == cfg["host"])
        to_target = sum(1 for r in rr if r["assigned_host"] == C.GAIA_TARGET)
        excl_all = sum(1 for r in rr if r["min_dchi2_other_minus_true"] is not None and r["min_dchi2_other_minus_true"] >= 9)
        det = sum(1 for r in rr if r["pixel_detected"])
        offs = np.array([r["best_offset_from_true_arcsec"] for r in rr])
        single = [r for r in inj_rows if r["config"] == cfg["name"]]
        inj[cfg["name"]] = {
            "host": cfg["host"], "level": cfg["level"], "n_joint": n,
            "coverage": {lvl: {"k": v, "n": n, "frac": v / n if n else None, "wilson95": wilson(v, n)} for lvl, v in cov.items()},
            "assigned_to_true_host": {"k": assigned_true, "n": n, "frac": assigned_true / n if n else None, "wilson95": wilson(assigned_true, n)},
            "assigned_to_target": {"k": to_target, "n": n, "frac": to_target / n if n else None, "wilson95": wilson(to_target, n)},
            "all_other_hosts_excluded_dchi2_ge_9": {"k": excl_all, "n": n, "frac": excl_all / n if n else None, "wilson95": wilson(excl_all, n)},
            "pixel_detected": {"k": det, "n": n, "frac": det / n if n else None, "wilson95": wilson(det, n)},
            "best_offset_from_true_arcsec_median": float(np.median(offs)) if n else None,
            "best_offset_from_true_arcsec_p68": float(np.percentile(offs, 68)) if n else None,
            "target_snr_joint_median": float(np.median([r["target_snr_joint"] for r in rr])) if n else None,
            "true_snr_joint_median": float(np.median([r["true_snr_joint"] for r in rr])) if n else None,
            "perturbed_vs_unperturbed_coverage_95": [
                sum(1 for r in rr if r["perturbed"] and r["dchi2_true_vs_free"] <= 6.18) / max(1, sum(1 for r in rr if r["perturbed"])),
                sum(1 for r in rr if not r["perturbed"] and r["dchi2_true_vs_free"] <= 6.18) / max(1, sum(1 for r in rr if not r["perturbed"]))],
            "single_sector_coverage_95": {str(s): (lambda q: {"k": sum(1 for r in q if r["dchi2p_true_vs_free"] <= 6.18), "n": len(q)})(
                [r for r in single if r["sector"] == s]) for s in SECTOR_EVENT},
            "single_sector_assigned_true": {str(s): (lambda q: {"k": sum(1 for r in q if r["assigned_host"] == cfg["host"]), "n": len(q)})(
                [r for r in single if r["sector"] == s]) for s in SECTOR_EVENT},
            "n_capped_sector_amplitudes": sum(1 for e in amp_table[cfg["name"]].values() if e["capped"]),
        }
    summ["injections"] = inj
    summ["wall_s"] = time.time() - t_start
    C.write_json(C.RESULTS / f"controls_{mode}_summary.json", C.clean(summ))
    for name, v in inj.items():
        print(name, "cov95 %s/%s" % (v["coverage"]["95.45"]["k"], v["n_joint"]), "assigned_true %s" % v["assigned_to_true_host"]["k"],
              "->target %s" % v["assigned_to_target"]["k"], "excl_all %s" % v["all_other_hosts_excluded_dchi2_ge_9"]["k"],
              "det %s" % v["pixel_detected"]["k"], "off_med %.1f\"" % v["best_offset_from_true_arcsec_median"],
              "tSNR %.2f" % v["target_snr_joint_median"], "capped_sectors %d" % v["n_capped_sector_amplitudes"])
    print("null single", json.dumps(ns))
    print("null joint", json.dumps(summ["null_joint"]))
    print("wall %.0f s" % summ["wall_s"])


if __name__ == "__main__":
    main(sys.argv[1])
