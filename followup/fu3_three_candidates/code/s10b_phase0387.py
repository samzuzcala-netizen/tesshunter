"""PROTOCOL 6: re-measure TIC 262843927's previously selected phase-0.387 feature (prior nominal 8.9 sigma,
calibrated global p = 0.493) at fixed phase in every reduction, with the s10 phase-shift null.  The phase was
selected from these same photons by an earlier search, so this is a consistency check, not a new detection
test; the earlier calibrated global p-value stands.
Output: results/s10b_phase0387_262843927.json
"""
from fu3_common import *
from events import adopted, Template, pool
from reductions import REDUCTIONS
from s10_secondary_2p import at_phase, REDS

TIC = 262843927


def main():
    eph = adopted(TIC)
    tmpl = Template(eph)
    nul = read(RES / f"s10_secondary_2p_{TIC}.json")
    out = dict(tic=TIC, generated_utc=utc(), phase=0.387, reductions={})
    for red in REDS:
        segs = REDUCTIONS[red](TIC)
        if not segs:
            continue
        recs = [r for r in at_phase(segs, eph, tmpl, 0.387) if r["admitted"]]
        p = pool(recs)
        n = nul["reductions"].get(red, {}).get("null", {})
        # empirical tail from the stored s10 null depths is not saved per draw; use its mean/std as a Gaussian
        # summary and also report depth relative to the null 95th/99th percentiles
        out["reductions"][red] = dict(pooled=p, null_depth_std=n.get("depth_std"), null_p95=n.get("depth_p95"),
                                      null_p99=n.get("depth_p99"),
                                      events=[dict(sector=r["sector"], cycle=r["cycle"], depth=r["depth_ppt"], err=r["depth_err_ppt"]) for r in recs])
        log("s10b", f"262 phase 0.387 {red}: {p.get('depth_ppt', float('nan')):.3f} +- {p.get('err_ppt', float('nan')):.3f} (n={p.get('n')}) "
                    f"pconst {p.get('p_const', float('nan')):.3f}; null p95 {n.get('depth_p95')}, p99 {n.get('depth_p99')}")
    save(RES / f"s10b_phase0387_{TIC}.json", out)


if __name__ == "__main__":
    main()
