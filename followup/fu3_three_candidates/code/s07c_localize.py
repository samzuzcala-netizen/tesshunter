"""PROTOCOL 5 (270 localization-vs-FPP), 6 (262 contamination), 7 (193 neighbour): difference-image host tests
with injection calibration, including a deliberately mis-specified PRF.

Per sector (scene-pass cutouts with >= 1 admitted event):
  * per-event per-pixel decrement maps (local linear baseline + adopted template), pooled per sector;
  * empirical per-pixel noise from >= 48 off-transit control maps (same window/admission), giving a per-pixel
    error inflation and a shrunk pixel covariance (shrinkage 0.5 toward the diagonal);
  * host scores: non-negative PRF amplitude + plane fitted to the pooled map within 3.5 px of the target and of
    the host; chi2 with calibrated diagonal errors and with the shrunk covariance; delta = chi2_host - chi2_target;
  * free-position fit of a single PRF source (diagnostic offset from the target);
  * injections into the real cube at off-transit epochs (shifts of +/-3, +/-5, +/-7, +/-9 T14 from each real
    event): a dip on the TARGET (observed aperture depth) and on each tested NEIGHBOUR (eclipse depth needed to
    give the observed aperture depth with mission-PRF throughput), each with the mission PRF and with a PRF
    broadened by a 0.35-px Gaussian (misspecification), scored with the unbroadened mission PRF.
Combined over sectors by summing delta chi2 (diagnostic); injection distributions are combined by drawing one
injected map per sector (2,000 seeded draws).
Outputs: results/s07c_localize_<tic>.json
"""
import sys

import pandas as pd

from fu3_common import *
from events import adopted, Template, admit
import pixels as PX
from prf import PRF

GAIA = {270573718: "4792202879700135040", 262843927: "4673750877131752832", 193718989: "1346023547769345792"}
FPPDIR = CONT / "analysis" / "fpp"
SHIFTS = (-9, -7, -5, -3, 3, 5, 7, 9)
N_CONTROL = 48
SEED = 20261018


def tested_neighbours(tic, pos_list, tgt, gmax_extra=6.0, rmax_px=4.0):
    """Neighbours tested: (a) every Gaia source with G < G_t + 6 within 4 px of the target, (b) the hosts of
    TRICERATOPS N* scenarios with summed probability > 1e-3 in the continuation seed_a run (matched by position)."""
    out = {}
    gt = tgt["G"] or 13
    for s in pos_list:
        if s["id"] == tgt["id"]:
            continue
        sep = np.hypot(s["x"] - tgt["x"], s["y"] - tgt["y"])
        if sep < rmax_px and (s["G"] or 99) < gt + gmax_extra:
            out[s["id"]] = dict(reason="Gaia G<Gt+6 within 4 px", sep_px=float(sep), G=s["G"])
        elif sep < 2.5:
            # 2026-10-18 fix: every Gaia source within 2.5 px regardless of brightness (the first run's G cut
            # silently dropped TIC 193718989's 9.8-arcsec G = 19.6 neighbour, the one the protocol names)
            out[s["id"]] = dict(reason="any Gaia source within 2.5 px", sep_px=float(sep), G=s["G"])
    # 2026-10-18 addition: every neighbour the s13 flux budget finds able to supply the depth (need <= 1 in any
    # aperture up to 3 px and any sector), regardless of separation
    fbp = RES / f"s13_fluxbudget_{tic}.json"
    if fbp.exists():
        for r in read(fbp)["neighbours_ranked"]:
            if r["eclipse_needed"] <= 1.0 and r["id"] != tgt["id"]:
                s = next((p for p in pos_list if p["id"] == r["id"]), None)
                if s is not None:
                    e = out.setdefault(r["id"], dict(sep_px=float(np.hypot(s["x"] - tgt["x"], s["y"] - tgt["y"])), G=s["G"]))
                    e["reason"] = e.get("reason", "") + "|flux-capable (s13 need <= 1)"
                    e["eclipse_needed_s13"] = r["eclipse_needed"]
    try:
        pr = pd.read_csv(FPPDIR / f"{tic}_seed_a_probabilities.csv")
        st = pd.read_csv(FPPDIR / f"{tic}_stars.csv")
        nb = pr[pr.scenario.str.startswith("N")].groupby("ID").prob.sum()
        for tid, prob in nb.items():
            if prob < 1e-3:
                continue
            row = st[st.ID == tid].iloc[0]
            best, bd = None, 9e9
            for s in pos_list:
                d = np.hypot((s["ra"] - row.ra) * np.cos(np.radians(row.dec)), s["dec"] - row.dec) * 3600
                if d < bd:
                    best, bd = s, d
            if best is not None and bd < 6:
                e = out.setdefault(best["id"], dict(sep_px=float(np.hypot(best["x"] - tgt["x"], best["y"] - tgt["y"])), G=best["G"]))
                e.update(tic=int(tid), triceratops_N_prob_seed_a=float(prob), match_arcsec=float(bd),
                         reason=e.get("reason", "") + "|TRICERATOPS N* host")
    except Exception as exc:   # noqa: BLE001
        out["_error"] = repr(exc)
    return out


def region(shape, pts, r=3.5):
    ny, nx = shape
    yy, xx = np.indices((ny, nx))
    m = np.zeros((ny, nx), bool)
    for (x, y) in pts:
        m |= np.hypot(xx - x, yy - y) < r
    return m


def score(D, E, C, model, mask):
    """Non-negative amplitude PRF + plane fit to map D on mask; chi2 diag (errors E) and with covariance C."""
    ny, nx = D.shape
    yy, xx = np.indices((ny, nx))
    X = np.column_stack([model[mask], np.ones(mask.sum()), ((xx - nx / 2) / nx)[mask], ((yy - ny / 2) / ny)[mask]])
    y = D[mask]
    w = 1 / E[mask]
    coef = np.linalg.lstsq(X * w[:, None], y * w, rcond=None)[0]
    if coef[0] < 0:
        c2 = np.linalg.lstsq(X[:, 1:] * w[:, None], y * w, rcond=None)[0]
        coef = np.r_[0.0, c2]
    r = y - X @ coef
    chi_d = float(np.sum((r * w) ** 2))
    chi_c = np.nan
    if C is not None:
        Ci = np.linalg.pinv(C)
        Xc = X
        A = Xc.T @ Ci @ Xc
        coefc = np.linalg.pinv(A) @ Xc.T @ Ci @ y
        if coefc[0] < 0:
            Xs = Xc[:, 1:]
            cc = np.linalg.pinv(Xs.T @ Ci @ Xs) @ Xs.T @ Ci @ y
            coefc = np.r_[0.0, cc]
        rc = y - Xc @ coefc
        chi_c = float(rc @ Ci @ rc)
    return chi_d, chi_c, float(coef[0])


def sector_maps(c, sub, tcs, eph, tmpl):
    maps = []
    for tc in tcs:
        r = PX.decrement_map(c, sub, tc, eph, tmpl)
        if r is not None:
            maps.append(r)
    return maps


def pool_maps(maps):
    D = np.array([m[0] for m in maps])
    E = np.array([m[1] for m in maps])
    w = 1 / E ** 2
    mu = (w * D).sum(0) / w.sum(0)
    err = 1 / np.sqrt(w.sum(0))
    if len(maps) > 1:
        chi = (w * (D - mu) ** 2).sum(0) / (len(maps) - 1)
        err = err * np.sqrt(np.maximum(1, chi))
    return mu, err


def inject_cube(c, tc, eph, tmpl, prf_img, depth_e):
    """Return a copy of the good-cadence cube with a dip of depth_e (e-/s total, PRF-distributed) at tc."""
    exp_d = np.median(np.diff(c["t"]))
    h = tmpl(c["t"] - tc, exp_d)
    cc = dict(c)
    cc["cube"] = c["cube"] - h[:, None, None] * depth_e * prf_img[None, :, :]
    return cc


def run(tic, max_sectors=None):
    eph = adopted(tic)
    tmpl = Template(eph)
    px = read(RES / f"s07b_pixels_{tic}.json")
    rng = np.random.default_rng(SEED + tic % 997)
    out = dict(tic=tic, generated_utc=utc(), sectors=[], note=__doc__)
    obs_by_host = {}
    inj_by = {}
    secs = [s for s in px["sectors"] if s.get("status") == "OK" and s.get("scene_pass")]
    for srec in secs[:max_sectors]:
        s = srec["sector"]
        path = Path(srec["file"])
        c = PX.load_cube(path)
        pos = PX.positions(c, tic)
        tgt = PX.target_of(pos, GAIA[tic])
        bgs, _ = PX.backgrounds(c, pos, tgt)
        sub = bgs["plane"]
        prf = PRF(s, c["camera"], c["ccd"], row=c["row0"] + tgt["y"], col=c["col0"] + tgt["x"])
        prfb = PRF(s, c["camera"], c["ccd"], row=c["row0"] + tgt["y"], col=c["col0"] + tgt["x"], broaden_px=0.35)
        scene = PX.scene_model(c, pos, tgt, prf, sub)
        off = scene["offset"]
        shape = c["shape"]
        neigh = tested_neighbours(tic, pos, tgt)
        hosts = {tgt["id"]: tgt}
        for nid in neigh:
            if nid.startswith("_"):
                continue
            hosts[nid] = next(p for p in pos if p["id"] == nid)
        imgs = {h: prf.image(p["x"] + off[0], p["y"] + off[1], shape) for h, p in hosts.items()}
        imgs_b = {h: prfb.image(p["x"] + off[0], p["y"] + off[1], shape) for h, p in hosts.items()}
        # real events (admitted by coverage on the circ1.5 annulus series as in s07b)
        tcs = sorted({e["tc_ref"] for e in px["events"] if e["sector"] == s and e["admitted"]
                      and e["reduction"] == "fu3pix:annulus:circ1.5"})
        maps = sector_maps(c, sub, tcs, eph, tmpl)
        if not maps:
            continue
        D, E = pool_maps(maps)
        # controls -> per-pixel inflation and covariance
        t = c["t"]
        near = np.zeros(len(t), bool)
        n = np.round((t - eph["T0"]) / eph["P"])
        near |= np.abs(t - (eph["T0"] + n * eph["P"])) < 1.5 * eph["T14"]
        cand = t[~near]
        ctl = []
        tries = 0
        while len(ctl) < N_CONTROL and tries < 400:
            tries += 1
            tc = float(rng.choice(cand))
            if np.any(np.abs(tc - (eph["T0"] + np.round((tc - eph["T0"]) / eph["P"]) * eph["P"])) < 2 * eph["T14"]):
                continue
            r = PX.decrement_map(c, sub, tc, eph, tmpl)
            if r is not None:
                ctl.append(r)
        mask = region(shape, [(p["x"] + off[0], p["y"] + off[1]) for p in hosts.values()], 3.5)
        if len(ctl) >= 12:
            Z = np.array([m[0] / m[1] for m in ctl])                      # control z-maps
            infl = np.maximum(1.0, np.std(Z, axis=0))
            Cz = np.cov(np.array([m[0][mask] for m in ctl]).T)
            Cz = 0.5 * Cz + 0.5 * np.diag(np.diag(Cz))
            Cpool = Cz / len(maps)
        else:
            infl = np.ones(shape)
            Cpool = None
        Ecal = E * infl
        chi = {h: score(D, Ecal, Cpool, imgs[h], mask) for h in hosts}
        base_d, base_c = chi[tgt["id"]][0], chi[tgt["id"]][1]
        host_scores = {h: dict(delta_chi2_diag=v[0] - base_d, delta_chi2_cov=(v[1] - base_c) if np.isfinite(v[1]) else None,
                               amplitude=v[2], **({k: neigh[h].get(k) for k in ("sep_px", "G", "tic", "triceratops_N_prob_seed_a", "reason")} if h in neigh else {}))
                       for h, v in chi.items()}
        for h, v in host_scores.items():
            obs_by_host.setdefault(h, []).append((s, v["delta_chi2_diag"], v["delta_chi2_cov"]))
        # free-position fit (diagnostic)
        from scipy.optimize import minimize
        f = lambda xy: score(D, Ecal, None, prf.image(xy[0], xy[1], shape), mask)[0]  # noqa: E731
        st = np.array([tgt["x"] + off[0], tgt["y"] + off[1]])
        best = min((minimize(f, s0, method="Powell", options={"xtol": 0.01, "maxiter": 60}) for s0 in
                    [st] + [np.array([p["x"] + off[0], p["y"] + off[1]]) for h, p in hosts.items() if h != tgt["id"]][:3]),
                   key=lambda q: q.fun)
        free_off_arcsec = float(np.hypot(*(best.x - st)) * 21.0)
        # injections
        ap = (np.hypot(*np.indices(shape)[::-1] - np.array([tgt["x"] + off[0], tgt["y"] + off[1]])[:, None, None]) <= 1.5)
        # hosts outside the scene model (fainter than G_t + 6) get a catalogue flux scaled from the target's scene
        # flux with the RP-band ratio (an RP proxy, generous to faint red neighbours); the injected total decrement
        # (observed aperture depth / PRF fraction in the aperture) does not depend on this flux, only the
        # reported required-eclipse fraction does.
        ftgt = max(scene["fluxes"].get(tgt["id"], 0.0), 1e-9)
        hflux = {}
        for h, p in hosts.items():
            f0 = scene["fluxes"].get(h)
            if f0 is not None and f0 > 0:
                hflux[h] = (f0, "scene_fit")
            elif p.get("Rp") and tgt.get("Rp"):
                hflux[h] = (ftgt * 10 ** (-0.4 * (p["Rp"] - tgt["Rp"])), "RP_ratio_proxy")
            else:
                hflux[h] = (0.0, "none")
        flux_in_ap = {h: hflux[h][0] * imgs[h][ap].sum() for h in hosts}
        total_ap = float(np.median((c["cube"] - sub)[:, ap].sum(axis=1)))
        obs_depth_ppt = read(RES / f"s07b_summary_{tic}.json")["fu3pix:annulus:circ1.5"]["pooled"]["depth_ppt"]
        inj = {}
        real_tcs = [tc for tc in tcs]
        # most neighbour-friendly aperture: radius 3 px (a large pipeline aperture includes more of a wide
        # neighbour's light); the injected neighbour decrement is the one that reproduces the observed depth in
        # whichever of the 1.5-px and 3-px apertures needs the smaller eclipse, capped at a total eclipse.
        ap3 = (np.hypot(*np.indices(shape)[::-1] - np.array([tgt["x"] + off[0], tgt["y"] + off[1]])[:, None, None]) <= 3.0)
        total_ap3 = float(np.median((c["cube"] - sub)[:, ap3].sum(axis=1)))
        flux_in_ap3 = {h: hflux[h][0] * imgs[h][ap3].sum() for h in hosts}
        for H in hosts:
            if flux_in_ap.get(H, 0) <= 0:
                continue
            need15 = obs_depth_ppt / 1000 * total_ap / flux_in_ap[H]
            need30 = obs_depth_ppt / 1000 * total_ap3 / flux_in_ap3[H] if flux_in_ap3.get(H, 0) > 0 else np.inf
            need_frac = min(need15, need30)
            if need_frac > 1.0:
                inj[H] = dict(required_eclipse_fraction=float(need_frac), need_ap1p5=float(need15), need_ap3p0=float(need30),
                              status="IMPOSSIBLE_DEPTH")
                continue
            depth_e = need_frac * hflux[H][0]
            res = {}
            for variant, IM in (("mission", imgs), ("broadened", imgs_b)):
                vals = []
                for tc0 in real_tcs:
                    for sh in SHIFTS:
                        tci = tc0 + sh * eph["T14"]
                        if not (c["t"].min() + 0.3 < tci < c["t"].max() - 0.3):
                            continue
                        ci = inject_cube(c, tci, eph, tmpl, IM[H], depth_e)
                        r = PX.decrement_map(ci, sub, tci, eph, tmpl)
                        if r is None:
                            continue
                        Di, Ei = r[0], r[1] * infl
                        sc = {h: score(Di, Ei, Cpool if Cpool is not None else None, imgs[h], mask) for h in hosts}
                        vals.append({h: (sc[h][0] - sc[tgt["id"]][0], (sc[h][1] - sc[tgt["id"]][1]) if np.isfinite(sc[h][1]) else None) for h in hosts})
                res[variant] = vals
            inj[H] = dict(required_eclipse_fraction=float(need_frac), need_ap1p5=float(need15), need_ap3p0=float(need30),
                          n=len(res["mission"]), **res)
            inj_by.setdefault(H, []).append((s, inj[H]))
        out["sectors"].append(dict(sector=s, n_events=len(maps), n_controls=len(ctl), scene_offset=off,
                                   scene_frac_rms=scene["frac_rms"], hosts=host_scores, neighbours_tested=neigh,
                                   host_flux_source={h: hflux[h][1] for h in hosts},
                                   free_fit_offset_arcsec=free_off_arcsec, free_fit_chi2_improvement=float(chi[tgt["id"]][0] - best.fun),
                                   free_fit_dxdy_px=[float(best.x[0] - st[0]), float(best.x[1] - st[1])],
                                   neighbour_dxdy_px={h: [float(p["x"] - tgt["x"]), float(p["y"] - tgt["y"])] for h, p in hosts.items() if h != tgt["id"]},
                                   median_pixel_inflation=float(np.median(infl[mask])), injections={
                                       H: dict(required_eclipse_fraction=v.get("required_eclipse_fraction"), status=v.get("status"), n=v.get("n"),
                                               mission=[{h: x[h] for h in x} for x in v.get("mission", [])],
                                               broadened=[{h: x[h] for h in x} for x in v.get("broadened", [])])
                                       for H, v in inj.items()}))
        log("s07c", f"{tic} s{s}: events {len(maps)} controls {len(ctl)} infl {np.median(infl[mask]):.2f} free-offset {free_off_arcsec:.1f}\" "
                    + "; ".join(f"{h[-6:]}:{v['delta_chi2_diag']:.1f}" for h, v in host_scores.items() if h != tgt["id"]))
        save(RES / f"s07c_localize_{tic}.json", out)
    # combine across sectors
    comb = {}
    for h, rows in obs_by_host.items():
        if h == GAIA[tic]:
            continue
        obs_d = float(np.nansum([r[1] for r in rows]))
        obs_c = float(np.nansum([r[2] for r in rows if r[2] is not None]))
        dist = {}
        for H in (GAIA[tic], h):
            per_sector = {}
            for srec in out["sectors"]:
                iv = srec["injections"].get(H, {})
                for variant in ("mission", "broadened"):
                    vals = [x[h][0] for x in iv.get(variant, []) if h in x]
                    if vals:
                        per_sector.setdefault(variant, []).append(vals)
            for variant, lists in per_sector.items():
                draws = np.array([sum(rng.choice(v) for v in lists) for _ in range(2000)])
                dist[f"true_{'target' if H == GAIA[tic] else 'neighbour'}_{variant}"] = dict(
                    n_sectors=len(lists), median=float(np.median(draws)), p05=float(np.percentile(draws, 5)),
                    p95=float(np.percentile(draws, 95)), frac_ge_observed=float(np.mean(draws >= obs_d)))
        comb[h] = dict(observed_sum_delta_chi2_diag=obs_d, observed_sum_delta_chi2_cov=obs_c,
                       n_sectors=len(rows), per_sector=rows, injection_distributions=dist)
    out["combined"] = comb
    save(RES / f"s07c_localize_{tic}.json", out)
    for h, v in comb.items():
        log("s07c", f"{tic} host {h}: observed sum dchi2 {v['observed_sum_delta_chi2_diag']:.1f} (cov {v['observed_sum_delta_chi2_cov']:.1f}) "
                    + " ".join(f"{k}: med {d['median']:.1f} [{d['p05']:.1f},{d['p95']:.1f}] P(>=obs) {d['frac_ge_observed']:.3f}"
                               for k, d in v["injection_distributions"].items()))
    return out


if __name__ == "__main__":
    for t in [int(a) for a in sys.argv[1:]] or list(TICS):
        run(t)
