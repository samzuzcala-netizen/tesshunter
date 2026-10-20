"""PROTOCOL 5 / 6 / 7 (physical models): profile-likelihood transit-shape fits on admitted event windows.

Model per event e:  y = B_e(t) - 1000 * D * (1 - F(t - tc_e - dt_s(e); k, b, rho_eff)),  with B_e a local linear
baseline profiled analytically, F the batman light curve (quadratic LD from the packet, integrated over the
product exposure), D a dilution amplitude (1 = undiluted) and dt_s optional per-season timing offsets.
rho_eff is the circular-orbit density implied by the transit speed; rho_eff / rho_cat = g^-3 with
g = (1 + e sin w) / sqrt(1 - e^2) (Dawson & Johnson 2012), giving the minimum eccentricity of any fit.
Fits:
  A  planet: k, b, rho_eff free, D = 1 (and with rho fixed at the catalogue density)
  B  radius-ratio profile: for k on a grid (0.03 ... 1.0) with b, rho_eff and D free (diluted occultor of any
     size: the ingress/egress shape bounds k)
  C  undiluted large occultors on the named target: R_occ in {0.08, 0.10, 0.12, 0.15, 0.20} Rsun, D = 1,
     b and rho_eff free (grazing allowed)
Each fit in two timing modes: 'linear' (reference ephemeris) and, for every target, 'season' (one free offset
per observing season, starting at the s04 joint-shift values).
Outputs: results/s11_shape_<tic>.json
"""
import sys

import batman
from scipy.optimize import least_squares

from fu3_common import *
from events import adopted, Template, admit
from reductions import REDUCTIONS

G_CGS = 6.674e-8
RSUN_REARTH = 109.076


def a_rs(rho, P_d):
    return (G_CGS * rho * (P_d * 86400) ** 2 / (3 * np.pi)) ** (1 / 3)


def windows(tic, red, eph):
    tmpl = Template(eph)
    from events import measure
    segs = REDUCTIONS[red](tic)
    ev = []
    for seg in segs:
        n0 = int(np.ceil((np.nanmin(seg["t"]) - eph["T0"]) / eph["P"]))
        n1 = int(np.floor((np.nanmax(seg["t"]) - eph["T0"]) / eph["P"]))
        for n in range(n0, n1 + 1):
            tc = eph["T0"] + n * eph["P"]
            ok, reason, w, half = admit(seg, tc, eph)
            if not ok:
                continue
            r = measure(seg, tc, eph, tmpl, deg=1, use_profile=False)
            ev.append(dict(cycle=n, sector=seg["sector"], tc=tc, t=seg["t"][w], y=seg["y"][w], half=half,
                           sig=r["sigma_white_ppt"] * r["beta"], exp=seg["cad_s"] / 86400.0))
    return ev


class Model:
    def __init__(self, ev, eph, seasons=None):
        self.ev, self.eph = ev, eph
        self.P = eph["P"]
        self.u = eph["u"]
        self.seasons = seasons or {}
        self.params = batman.TransitParams()
        p = self.params
        p.t0, p.per, p.rp, p.a, p.inc, p.ecc, p.w, p.u, p.limb_dark = 0.0, self.P, 0.05, 50.0, 89.9, 0.0, 90.0, list(self.u), "quadratic"
        self.models = []
        for e in ev:
            ss = max(1, int(np.ceil(e["exp"] * 1440 / 2.0)))
            self.models.append((batman.TransitModel(p, e["t"] - e["tc"], supersample_factor=ss, exp_time=e["exp"]), ss))
        self.B = [np.column_stack([np.ones(len(e["t"])), (e["t"] - e["tc"]) / e["half"]]) for e in ev]
        self.Q = [np.linalg.qr(B)[0] for B in self.B]

    def resid(self, k, b, rho, D, offs):
        p = self.params
        p.rp = k
        ar = a_rs(rho, self.P)
        p.a = ar
        p.inc = float(np.degrees(np.arccos(np.clip(b / ar, 0, 0.999999))))
        out = []
        for i, e in enumerate(self.ev):
            dt = offs.get(self.seasons.get(e["cycle"]), 0.0) if offs else 0.0
            if dt:
                ss = max(1, int(np.ceil(e["exp"] * 1440 / 2.0)))
                m = batman.TransitModel(p, e["t"] - e["tc"] - dt, supersample_factor=ss, exp_time=e["exp"]).light_curve(p)
            else:
                m = self.models[i][0].light_curve(p)
            r = e["y"] + 1000.0 * D * (1 - m)
            r = r - self.Q[i] @ (self.Q[i].T @ r)
            out.append(r / e["sig"])
        return np.concatenate(out)


def season_map(cycles, gap=6):
    cs = sorted(set(cycles))
    m, g = {}, 0
    for i, c in enumerate(cs):
        if i and c - cs[i - 1] > gap:
            g += 1
        m[c] = g
    return m


def fit(model, k=None, b0=(0.2, 0.6, 0.9), rho0=None, D=None, timing=False, rho_fixed=None, kmax=1.0):
    """Generic multi-start least-squares; free: [k], b, log rho (unless fixed), [D], [season offsets]."""
    ns = len(set(model.seasons.values())) if timing else 0
    best = None
    rho_c = model.eph["stellar"]["rho_cgs"]
    starts_rho = [rho_c, rho_c / 5, rho_c / 30] if rho_fixed is None else [rho_fixed]
    for bs in b0:
        for rs in starts_rho:
            x0, lo, hi, names = [], [], [], []
            if k is None:
                x0.append(model.eph["k"]); lo.append(0.005); hi.append(kmax); names.append("k")
            x0.append(bs * (1 + (k or model.eph["k"]))); lo.append(0.0); hi.append(2.0); names.append("b")
            if rho_fixed is None:
                x0.append(np.log(rs)); lo.append(np.log(1e-4)); hi.append(np.log(200.0)); names.append("lnrho")
            if D is None:
                x0.append(0.5 if (k or 0) > 0.2 else 1.0); lo.append(1e-5); hi.append(1.0); names.append("D")
            for s in range(ns):
                x0.append(0.0); lo.append(-0.15); hi.append(0.15); names.append(f"dt{s}")

            def unpack(x):
                d = dict(zip(names, x))
                kk = d.get("k", k)
                bb = d["b"]
                rho = np.exp(d["lnrho"]) if "lnrho" in d else rho_fixed
                DD = d.get("D", D if D is not None else 1.0)
                offs = {s: d[f"dt{s}"] for s in range(ns)}
                return kk, bb, rho, DD, offs

            def f(x):
                kk, bb, rho, DD, offs = unpack(x)
                if bb > 1 + kk:
                    return np.full(sum(len(e["t"]) for e in model.ev), 1e3)
                return model.resid(kk, bb, rho, DD, offs)
            try:
                r = least_squares(f, x0, bounds=(lo, hi), x_scale="jac", max_nfev=400, ftol=1e-9, xtol=1e-9)
            except Exception:   # noqa: BLE001
                continue
            c2 = float(r.fun @ r.fun)
            if best is None or c2 < best["chi2"]:
                kk, bb, rho, DD, offs = unpack(r.x)
                best = dict(chi2=c2, k=float(kk), b=float(bb), rho_eff=float(rho), D=float(DD),
                            offsets_min={str(s): float(v * 1440) for s, v in offs.items()}, n=len(r.fun),
                            nfree=len(x0), success=bool(r.success))
    if best:
        best["a_rs_eff"] = float(a_rs(best["rho_eff"], model.P))
        g = (model.eph["stellar"]["rho_cgs"] / best["rho_eff"]) ** (1 / 3)
        best["g_speed_factor"] = float(g)
        best["e_min"] = float(abs(g * g - 1) / (g * g + 1))     # minimum e for the implied speed (w at +-90)
        best["rp_rearth_if_undiluted_target"] = float(best["k"] * model.eph["stellar"]["radius"] * RSUN_REARTH)
    return best


def run(tic, red="pdc_raw"):
    eph = adopted(tic)
    ev = windows(tic, red, eph)
    smap = season_map([e["cycle"] for e in ev])
    out = dict(tic=tic, reduction=red, generated_utc=utc(), n_events=len(ev), seasons=smap,
               stellar=eph["stellar"], u=eph["u"], P=eph["P"])
    for mode in ("linear", "season"):
        M = Model(ev, eph, seasons=smap if mode == "season" else None)
        tm = mode == "season"
        res = {}
        res["A_planet_free"] = fit(M, timing=tm, D=1.0, kmax=0.4)
        res["A_planet_rho_cat"] = fit(M, timing=tm, D=1.0, rho_fixed=eph["stellar"]["rho_cgs"], kmax=0.4)
        base = res["A_planet_free"]["chi2"]
        prof = []
        for kk in (0.03, 0.04, 0.05, 0.07, 0.1, 0.15, 0.2, 0.3, 0.45, 0.6, 0.8, 1.0):
            r = fit(M, k=kk, timing=tm)
            if r:
                r["delta_chi2"] = r["chi2"] - base
                prof.append(r)
        res["B_k_profile_diluted"] = prof
        occ = []
        for R in (0.08, 0.10, 0.12, 0.15, 0.20):
            kk = R / eph["stellar"]["radius"]
            r = fit(M, k=kk, D=1.0, timing=tm, b0=(0.95, 1.05, 1.15))
            if r:
                r.update(R_occ_rsun=R, delta_chi2=r["chi2"] - base)
                occ.append(r)
        res["C_large_occultor_undiluted"] = occ
        # profile in b for the planet model (impact parameter interval)
        bprof = []
        for bb in (0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0):
            def fb(x, M=M, bb=bb):
                kk, lnr = x[0], x[1]
                offs = {s: x[2 + s] for s in range(len(set(smap.values())))} if tm else {}
                return M.resid(kk, bb * (1 + kk), np.exp(lnr), 1.0, offs)
            ns = len(set(smap.values())) if tm else 0
            x0 = [res["A_planet_free"]["k"], np.log(res["A_planet_free"]["rho_eff"])] + [0.0] * ns
            lo = [0.005, np.log(1e-4)] + [-0.15] * ns
            hi = [0.4, np.log(200)] + [0.15] * ns
            r = least_squares(fb, x0, bounds=(lo, hi), x_scale="jac", max_nfev=300)
            bprof.append(dict(b_over_1pk=bb, chi2=float(r.fun @ r.fun), delta_chi2=float(r.fun @ r.fun) - base,
                              k=float(r.x[0]), rho_eff=float(np.exp(r.x[1]))))
        res["A_b_profile"] = bprof
        out[mode] = res
        a = res["A_planet_free"]
        log("s11", f"{tic} {red} {mode}: planet k {a['k']:.4f} b {a['b']:.2f} rho_eff {a['rho_eff']:.2f} (cat {eph['stellar']['rho_cgs']:.2f}) "
                   f"e_min {a['e_min']:.2f} chi2 {a['chi2']:.1f}; rho_cat dchi2 {res['A_planet_rho_cat']['chi2'] - a['chi2']:.1f}; "
                   f"k-profile dchi2 {[ (round(p['k'],2), round(p['delta_chi2'],1)) for p in prof]}; "
                   f"occultors {[(o['R_occ_rsun'], round(o['delta_chi2'],1), round(o['e_min'],2)) for o in occ]}; offsets {a['offsets_min']}")
    save(RES / f"s11_shape_{tic}_{red}.json", out)
    return out


if __name__ == "__main__":
    tics = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(TICS)
    red = next((a for a in sys.argv[1:] if not a.isdigit()), "pdc_raw")
    for t in tics:
        run(t, red)
