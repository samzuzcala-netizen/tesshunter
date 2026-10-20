# Part D input verification

[M] 436 of the original 531 stars are input eligible after the registered sequential cuts (473 after A). STOP-1: NOT FIRED; 95 independent likely-periodic in-band families against the minimum of 60. No search or forced fit has run.

| Stratum | Raw rows | Families | Likely-periodic in-band families |
|---|---:|---:|---:|
| INDEPENDENT | 1747 | 1096 | 95 |
| OVERLAPPING | 616 | 476 | 56 |
| UNION | 2363 | 1449 | 117 |

[M] 1309 QLP 74-79 products on eligible hosts have exact corrected-v02 source comparisons. Per-product TIME, flux, SAP and quality checks, file hashes, BJD/TDB reference headers, quality masks, exclusions and native prepared point counts are saved under results/input_identity and results/native_noise. The frozen notice snapshot hash is retained in every identity record.

[M] Verification/preparation operational unknowns: 0. Neighbour operational unknowns: 0, including 0 eligible hosts. These are not scientific misses.

## Assumptions

[A] The existing P10 author preference, native cadence harmonisation, quality masks, detrending and clipping remain unchanged. The P11 minimum of 50 retained native points defines a usable sector; at least three are required. Noise is 1.4826 times median absolute deviation around the prepared-flux median, with actual usable cadence counts. Original Part A Gaia and corrected two-minute cuts remain fixed; Part D supplies the third, usable-sector cut. Network failures remain unknowns. No flux-based clock adjustment or TCE ranking selected an input.
