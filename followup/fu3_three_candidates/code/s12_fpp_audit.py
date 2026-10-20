"""PROTOCOL 11: TRICERATOPS scenario audit from the continuation's existing runs (no new FPP draws).

Scenario families (Giacalone et al. 2021):
  target-host planet  TP + PTP + DTP      (package FPP = 1 - this)
  other-host planets  STP (bound secondary), BTP (unresolved background), NTP (resolved neighbour)
  stellar eclipses    EB, EBx2P, PEB, PEBx2P, SEB, SEBx2P, DEB, DEBx2P, BEB, BEBx2P, NEB, NEBx2P
any-host planet-label weight = TP + PTP + DTP + STP + BTP + NTP.  These are conditional scenario weights, not
probabilities that a planet exists; they exclude instrumental false alarms.
Conditional variant 'image_conditioned': N* scenarios whose host the injection-calibrated difference-image test
(s07c) excludes (observed summed delta chi2 outside the neighbour-hosted injection range in every PRF variant)
are removed and the rest renormalised.  This is a sensitivity bound, not a joint posterior: the image test and
TRICERATOPS share photons and the PRF/scene assumptions differ.
Outputs: results/s12_fpp_audit.json
"""
import pandas as pd

from fu3_common import *

FPPDIR = CONT / "analysis" / "fpp"
RUNS = ("seed_a", "seed_b", "noise_1p5", "native_bins")
TARGET_PLANET = {"TP", "PTP", "DTP"}
OTHER_PLANET = {"STP", "BTP", "NTP"}


def families(df):
    s = df.groupby("scenario").prob.sum()
    tp = float(sum(s.get(k, 0.0) for k in TARGET_PLANET))
    op = {k: float(s.get(k, 0.0)) for k in OTHER_PLANET}
    eb = float(sum(v for k, v in s.items() if "EB" in k))
    nfpp = float(sum(v for k, v in s.items() if k.startswith("N")))
    return dict(target_planet=tp, fpp=1 - tp, any_host_planet=tp + sum(op.values()), other_planets=op,
                stellar_eclipse=eb, nfpp=nfpp, by_scenario={k: float(v) for k, v in s.items()})


def excluded_neighbour_tics(tic):
    p = RES / f"s07c_localize_{tic}.json"
    if not p.exists():
        return {}, {}
    d = read(p)
    excl, detail = set(), {}
    # map Gaia id -> TIC via the neighbours_tested records
    g2tic = {}
    for s in d["sectors"]:
        for gid, v in s["neighbours_tested"].items():
            if isinstance(v, dict) and v.get("tic"):
                g2tic[gid] = v["tic"]
    for gid, v in d.get("combined", {}).items():
        dist = v["injection_distributions"]
        obs = v["observed_sum_delta_chi2_diag"]
        nb = [dist[k] for k in dist if k.startswith("true_neighbour")]
        verdict = None
        if nb:
            verdict = all(obs > x["p95"] and x["frac_ge_observed"] == 0.0 for x in nb)
        detail[gid] = dict(tic=g2tic.get(gid), observed=obs,
                           neighbour_hosted=[dict(variant=k, median=dist[k]["median"], p95=dist[k]["p95"]) for k in dist if k.startswith("true_neighbour")],
                           excluded=verdict)
        if verdict and g2tic.get(gid):
            excl.add(int(g2tic[gid]))
    return excl, detail


def run():
    out = {}
    for tic in TICS:
        excl, detail = excluded_neighbour_tics(tic)
        rec = dict(runs={}, image_test_detail=detail, image_excluded_neighbour_tics=sorted(excl))
        for r in RUNS:
            p = FPPDIR / f"{tic}_{r}_probabilities.csv"
            if not p.exists():
                continue
            df = pd.read_csv(p)
            fam = families(df)
            # image-conditioned variant
            keep = df[~(df.scenario.str.startswith("N") & df.ID.isin(list(excl)))].copy()
            keep["prob"] = keep.prob / keep.prob.sum()
            fam_ic = families(keep)
            # neighbour breakdown
            nb = df[df.scenario.str.startswith("N")].groupby("ID").prob.sum().sort_values(ascending=False)
            meta = read(FPPDIR / f"{tic}_{r}.json")
            sens = meta.get("prior_sensitivity") or []
            fpps = [x.get("fpp") for x in sens if isinstance(x, dict) and x.get("fpp") is not None]
            rec["runs"][r] = dict(package_fpp=meta.get("fpp"), package_nfpp=meta.get("nfpp"), n_draws=meta.get("n_draws"),
                                  families=fam, image_conditioned=fam_ic,
                                  nfpp_by_neighbour_tic={str(int(k)): float(v) for k, v in nb.items() if v > 1e-6},
                                  prior_sensitivity_fpp_range=[min(fpps), max(fpps)] if fpps else None,
                                  prior_sensitivity_n=len(fpps))
        # envelope across runs
        def env(key, sub="families"):
            vals = [v[sub][key] for v in rec["runs"].values()]
            return [min(vals), max(vals)] if vals else None
        rec["envelope"] = dict(target_planet=env("target_planet"), any_host_planet=env("any_host_planet"),
                               stellar_eclipse=env("stellar_eclipse"), nfpp=env("nfpp"), fpp=env("fpp"),
                               image_conditioned_target_planet=env("target_planet", "image_conditioned"),
                               image_conditioned_fpp=env("fpp", "image_conditioned"),
                               image_conditioned_nfpp=env("nfpp", "image_conditioned"))
        out[str(tic)] = rec
        e = rec["envelope"]
        log("s12", f"{tic}: FPP {e['fpp']} NFPP {e['nfpp']} target-planet {e['target_planet']} any-host {e['any_host_planet']} "
                   f"EB {e['stellar_eclipse']} | image-conditioned FPP {e['image_conditioned_fpp']} NFPP {e['image_conditioned_nfpp']} "
                   f"(excluded neighbour TICs {sorted(excl)})")
    save(RES / "s12_fpp_audit.json", out)


if __name__ == "__main__":
    run()
