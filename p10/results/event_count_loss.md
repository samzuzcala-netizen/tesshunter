# Part 2b: 10-30 d event-count loss [M]

descriptive only; no decision or protocol change.

The chosen saved ephemeris is used. Crossing from >=3 observed to <3 kept after exclusions is distinguished from all <3-kept failures. Criteria may fail together; no counterfactual recovery is inferred.

| P8 bin / observed selected period span (d) | Injected | Recovered with A record | <3 kept | >=3 observed -> <3 kept | Only failing A criterion | Crossed and pre-gate passed |
|---|---:|---:|---:|---:|---:|---:|
| 2 / 10.024-10.760 | 42 | 21 | 0 | 0 | 0 | 0 |
| 3 / 10.796-29.955 | 525 | 261 | 13 | 11 | 1 | 7 |

Original P8 bin labels are retained; the spans are the minimum and maximum selected injected periods, not new bin edges.
Missing/unsettled recovered records: 0. Per-record counts and input hashes are in `event_count_loss.json`.
The three-kept-events threshold remains unchanged.
