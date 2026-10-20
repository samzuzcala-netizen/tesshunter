"""PROTOCOL 5.6 / 6 / 7: odd/even (2P unequal binaries), half-phase at P (secondary of a P binary), and the
2P quadrature phases, with a sector-structure-preserving phase-shift null, in every reduction.

For a fixed phase offset phi (in units of P), "events" are measured at T0 + (n + phi) P with the adopted template
and local linear baselines (events.measure, coverage admission).  Null: 300 seeded common offsets phi uniform in
[0.08, 0.42] U [0.58, 0.92] (avoiding the primary and the half phase), pooled depth each; the empirical tail
probability of the observed half-phase depth is reported (add-one).
Odd/even: pooled depths of odd and even cycles at phase 0; difference / combined (inflated) error.
Outputs: results/s10_secondary_2p_<tic>.json
"""
import sys

from fu3_common import *
from events import adopted, Template, measure, pool
from reductions import REDUCTIONS

REDS = ("survey_detrended", "pdc_raw", "sap_raw", "survey_tesscut_aperture", "tglc_aperture", "tglc_psf",
        "fu3pix_annulus_circ1p5", "fu3pix_plane_circ1p5", "fu3pix_prf")
N_NULL = 300
SEED = 20261018


def at_phase(segs, eph, tmpl, phi):
    recs = []
    for seg in segs:
        n0 = int(np.ceil((np.nanmin(seg["t"]) - eph["T0"]) / eph["P"] - phi)) - 1
        n1 = int(np.floor((np.nanmax(seg["t"]) - eph["T0"]) / eph["P"] - phi)) + 1
        for n in range(n0, n1 + 1):
            tc = eph["T0"] + (n + phi) * eph["P"]
            if not (np.nanmin(seg["t"]) - 0.5 < tc < np.nanmax(seg["t"]) + 0.5):
                continue
            r = measure(seg, tc, eph, tmpl, deg=1, use_profile=False)
            r.update(cycle=n, sector=seg["sector"])
            recs.append(r)
    return recs


def run(tic):
    eph = adopted(tic)
    tmpl = Template(eph)
    rng = np.random.default_rng(SEED + tic % 991)
    nulls_phi = np.concatenate([rng.uniform(0.08, 0.42, N_NULL // 2), rng.uniform(0.58, 0.92, N_NULL - N_NULL // 2)])
    out = dict(tic=tic, generated_utc=utc(), reductions={}, null_phases=nulls_phi.tolist())
    for red in REDS:
        try:
            segs = REDUCTIONS[red](tic)
        except Exception as exc:   # noqa: BLE001
            out["reductions"][red] = dict(status="LOAD_FAILED", error=repr(exc)[:300])
            continue
        if not segs:
            out["reductions"][red] = dict(status="NO_DATA")
            continue
        prim = [r for r in at_phase(segs, eph, tmpl, 0.0) if r["admitted"]]
        odd = pool([r for r in prim if r["cycle"] % 2])
        even = pool([r for r in prim if not r["cycle"] % 2])
        oe_sig = (abs(odd["depth_ppt"] - even["depth_ppt"]) / np.hypot(odd["err_ppt"], even["err_ppt"])
                  if odd.get("n") and even.get("n") else None)
        half = [r for r in at_phase(segs, eph, tmpl, 0.5) if r["admitted"]]
        hp = pool(half)
        # 2P quadrature split: half-phase events by parity of the half-cycle index
        h_even = pool([r for r in half if not r["cycle"] % 2])
        h_odd = pool([r for r in half if r["cycle"] % 2])
        null = []
        for phi in nulls_phi:
            pr = pool([r for r in at_phase(segs, eph, tmpl, float(phi)) if r["admitted"]])
            if pr.get("n"):
                null.append((float(phi), pr["depth_ppt"], pr["err_ppt"], pr["n"]))
        nd = np.array([x[1] for x in null])
        nz = np.array([x[1] / x[2] for x in null])
        res = dict(primary=pool(prim), odd=odd, even=even, odd_even_sigma=oe_sig,
                   half_phase=hp, half_phase_even_halfcycles=h_even, half_phase_odd_halfcycles=h_odd,
                   half_phase_events=[dict(sector=r["sector"], cycle=r["cycle"], depth=r["depth_ppt"], err=r["depth_err_ppt"]) for r in half],
                   null=dict(n=len(null), depth_mean=float(nd.mean()) if len(nd) else None,
                             depth_std=float(nd.std()) if len(nd) else None, z_std=float(nz.std()) if len(nz) else None,
                             p_half_depth=float((1 + np.sum(nd >= hp.get("depth_ppt", np.inf))) / (1 + len(nd))) if hp.get("n") else None,
                             p_half_z=float((1 + np.sum(nz >= hp["depth_ppt"] / hp["err_ppt"])) / (1 + len(nz))) if hp.get("n") else None,
                             depth_p95=float(np.percentile(nd, 95)) if len(nd) else None,
                             depth_p99=float(np.percentile(nd, 99)) if len(nd) else None))
        out["reductions"][red] = res
        log("s10", f"{tic} {red}: prim {res['primary'].get('depth_ppt', float('nan')):.2f}+-{res['primary'].get('err_ppt', float('nan')):.2f} "
                   f"odd {odd.get('depth_ppt', float('nan')):.2f} even {even.get('depth_ppt', float('nan')):.2f} ({oe_sig if oe_sig is None else round(oe_sig, 2)} sig); "
                   f"half {hp.get('depth_ppt', float('nan')):.3f}+-{hp.get('err_ppt', float('nan')):.3f} (n={hp.get('n')}) "
                   f"null p(depth) {res['null']['p_half_depth']} null depth sd {res['null']['depth_std']}")
    save(RES / f"s10_secondary_2p_{tic}.json", out)


if __name__ == "__main__":
    for t in [int(a) for a in sys.argv[1:]] or list(TICS):
        run(t)
