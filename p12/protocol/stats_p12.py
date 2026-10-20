"""Registered interval estimators: Wilson 95% score intervals and the paired whole-host
bootstrap (PCG64, seed 2026092001, 10,000 draws, percentile 95% intervals)."""
import math

import numpy as np


def wilson(k, n, z=1.959963984540054):
    """Wilson score interval for k successes in n trials; (None, None) when n == 0."""
    if n <= 0:
        return None, None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(k, n):
    lo, hi = wilson(k, n)
    return dict(k=int(k), n=int(n), fraction=(k / n) if n else None, wilson95=[lo, hi])


def paired_host_bootstrap(hosts, statistic, *, seed=2026092001, draws=10000):
    """Resample whole hosts with replacement; ``statistic(sample_of_hosts)`` -> float."""
    hosts = list(hosts)
    if not hosts:
        return dict(value=None, interval95=[None, None], draws=0, seed=seed)
    rng = np.random.Generator(np.random.PCG64(seed))
    value = statistic(hosts)
    values = []
    for _ in range(draws):
        idx = rng.integers(0, len(hosts), size=len(hosts))
        values.append(statistic([hosts[i] for i in idx]))
    values = np.asarray(values, dtype=float)
    lo, hi = np.percentile(values, [2.5, 97.5])
    return dict(value=value, interval95=[float(lo), float(hi)], draws=draws, seed=seed, bit_generator='PCG64')
