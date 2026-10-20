# User allocation and supervision amendment — 2026-09-15T06:45:21.872573+00:00

[A] The user prospectively selected all 436 eligible stars for survey_p10 and paired survey_p8, reusing the six pilot hosts for both presets. There are 430 new jobs per preset, in the existing registered nested order. survey_p10 runs first, survey_p8 second. No retention outcome selected the population.

[A] The user's stated planning basis is 5.2 h P10, 1.4 h P8, 3.9 h A, 0.1 h S/B, 2.0 h forced fits and 1.0 h matching/analysis: 13.6 h times 1.25 = 17.0 h against 28.211665 h remaining. Those rounded planning estimates are preserved in allocation.json. A separate tail check uses the historical P10 maximum, observed P8 maximum and historical Stage A p90; it totals 25.840693 h with margin. S/B and forced-fit planning rates remain unmeasured assumptions.

[A] The latest supervision amendment supersedes the earlier same-message request to pause at N_C and H. Auto-advance through the registered sequence. At B closure record N_C = floor((remaining_hours - 3.0) * 3 / 3.4) from that ledger snapshot, order qualifying TCE-matched likely-periodic B passers by descending expected SNR, and use at most three concurrent C runs. Record the raw cap even when negative; zero jobs can run under a negative cap. Compute H, write five autopsies if its registered rule fires, and cost p10.1 only; never execute the iteration. Pause only for Part I stops, integrity failures or final delivery.

[A] Complete predictions cannot exist before the remaining searches. Freeze membership, runtime inputs and planned manifests now. After each preset closes, lock every accepted candidate and its period, epoch, duration, depth, stitch SNR, partition and budget flags, including reused pilot output hashes and operational-unknown accounting. Both completed locks are mandatory before Part F opens the sidecar.

No scientific threshold, historic source or prior registration byte is changed. The original D1-D4-effective preregistration remains unchanged; this new version and the allocation/policy are pinned by registration_execution_v3.json.
