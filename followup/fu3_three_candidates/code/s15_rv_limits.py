"""PROTOCOL 5 (c): companion-mass limits on the NAMED TARGET from Gaia DR3 multi-epoch RV summary statistics.

Gaia DR3 publishes, for stars with grvs_mag <= 12, the number of RVS transits N, the median-RV error and the
chi2 p-value of constancy (rv_chisq_pvalue).  Per-epoch scatter is reconstructed as
    sigma_epoch = sqrt((rv_error^2 - 0.11^2) * 2N / pi)
(Katz et al. 2023 error model; 0.11 km/s floor).  Monte Carlo: N epochs uniform over the DR3 34-month window,
random orbital phase (and for eccentric cases random argument of periastron), K on a grid; the statistic is
the probability that a simulated chi2 p-value is >= the observed one.  K95 is the K at which that probability
falls to 5 %.  Masses use M_star from the TIC and the period P (named-target host only).  These limits do NOT
apply to companions of other stars (blends): a diluted eclipsing pair does not move the target's lines.
Output: results/s15_rv_limits.json
"""
from scipy.stats import chi2

from fu3_common import *

GAIA_RV = {  # from the continuation stellar archival JSON (Gaia DR3 gaia_source), verified by the FU3 census
    262843927: dict(rv=8.253755, rv_error=0.51212907, N=23, p=0.9765803, amp=7.3176064),
    193718989: dict(rv=-5.440756, rv_error=1.0659971, N=21, p=0.18337704, amp=15.281683),
    270573718: dict(rv=19.269508, rv_error=1.4619739, N=19, p=None, amp=None),
}
SEED = 20261018


def k_to_mass(K, P_d, Mstar, e=0.0):
    """Minimum companion mass (Jupiter masses) for semi-amplitude K (km/s), iterating for non-negligible mass."""
    G = 6.674e-11
    Ms = Mstar * 1.989e30
    P = P_d * 86400
    m = 1e-3 * Ms
    for _ in range(50):
        m = K * 1e3 * np.sqrt(1 - e * e) * (P / (2 * np.pi * G)) ** (1 / 3) * (Ms + m) ** (2 / 3)
    return m / 1.898e27


def simulate(N, sig, K, P, e, nsim, rng):
    t = rng.uniform(0, 34 * 30.44, size=(nsim, N))
    ph = rng.uniform(0, 1, size=(nsim, 1))
    w = rng.uniform(0, 2 * np.pi, size=(nsim, 1))
    M = 2 * np.pi * (t / P + ph)
    if e > 0:
        E = M.copy()
        for _ in range(30):
            E = E - (E - e * np.sin(E) - M) / (1 - e * np.cos(E))
        nu = 2 * np.arctan2(np.sqrt(1 + e) * np.sin(E / 2), np.sqrt(1 - e) * np.cos(E / 2))
        v = K * (np.cos(nu + w) + e * np.cos(w))
    else:
        v = K * np.sin(M)
    v = v + rng.normal(0, sig, size=(nsim, N))
    c2 = np.sum(((v - np.median(v, axis=1, keepdims=True)) / sig) ** 2, axis=1)
    return chi2.sf(c2, N - 1)


def main():
    rng = np.random.default_rng(SEED)
    out = {}
    for tic, g in GAIA_RV.items():
        fit = read(PACKET[tic] / "fit.json")
        P = fit["adopted"]["period"]
        Mst = fit["stellar"]["mass"]
        if g["p"] is None:
            out[str(tic)] = dict(status="NO_GAIA_CHI2_PVALUE", note="Gaia DR3 publishes rv_chisq_pvalue only for grvs_mag <= 12; "
                                                                   "no epoch-RV constraint is derived (no limit invented).", gaia=g)
            continue
        sig = np.sqrt(max(g["rv_error"] ** 2 - 0.11 ** 2, 1e-4) * 2 * g["N"] / np.pi)
        res = dict(gaia=g, sigma_epoch_kms=float(sig), P=P, M_star=Mst, cases={})
        for label, per, e in (("circular_P", P, 0.0), ("ecc0.8_P", P, 0.8), ("circular_2P", 2 * P, 0.0), ("ecc0.8_2P", 2 * P, 0.8)):
            # Relative statistic (corrected 2026-10-18 after the first version returned the grid floor): the
            # observed constancy chi2 (from Gaia's p-value) is compared through
            #   R(K) = P(chi2_sim <= chi2_obs | K) / P(chi2_sim <= chi2_obs | K = 0),
            # which cancels a mis-scaled per-epoch error model (TIC 262843927's p = 0.977 is already in the 2.3 %
            # 'too constant' tail under K = 0).  K95 is the smallest K with R(K) < 0.05.
            Ks = np.concatenate([[0.0], np.linspace(0.25, 5, 20), np.linspace(5.5, 60, 40)])
            frac = []
            for K in Ks:
                pv = simulate(g["N"], sig, K, per, e, 4000, rng)
                frac.append(float(np.mean(pv >= g["p"])))        # p_sim >= p_obs  <=>  chi2_sim <= chi2_obs
            frac = np.array(frac)
            R = frac / max(frac[0], 1e-4)
            above = np.where((R < 0.05) & (Ks > 0))[0]
            K95 = float(Ks[above[0]]) if len(above) else None
            res["cases"][label] = dict(K_grid=Ks.tolist(), prob_chi2_le_obs=frac.tolist(), relative_R=R.tolist(),
                                       K95_kms=K95, Mmin95_mjup=(k_to_mass(K95, per, Mst, e) if K95 else None))
        out[str(tic)] = res
        log("s15", f"{tic}: sigma_epoch {sig:.2f} km/s; " + "; ".join(f"{k}: K95 {v['K95_kms']} -> Msini95 {v['Mmin95_mjup'] and round(v['Mmin95_mjup'],1)} MJ"
                                                                   for k, v in res["cases"].items()))
    save(RES / "s15_rv_limits.json", out)


if __name__ == "__main__":
    main()
