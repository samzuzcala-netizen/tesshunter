# Main-task review of the acquisition pilot (2026-09-14, written by the user's Claude session)

This is the review the pilot checkpoint asked for, done outside the Codex
session so the science registration stays Codex-owned. Environment repairs
were applied directly. Every protocol change is **proposed** here with exact
edits and numbers; none was applied to `p10/part3/protocol/`, and no
registration seal, receipt or sealed evidence was touched. Register the
amendments prospectively (new source version, amendment-table rows, tests),
then launch.

## 1. Environment repairs applied [M]

| Action | Before | After |
|---|---|---|
| Removed the two orphaned temporary packs `.git/objects/pack/tmp_pack_dOiasp` (8.34 GB, 2026-09-12 aborted repack) and `tmp_pack_jumuHH` (2.25 GB, 2026-09-14) | `git count-objects`: garbage 2, 9.86 GiB; `C:` 32.06 GB free | garbage 0; `C:` 41.93 GB free |
| Repo-local config `maintenance.auto=false`, `gc.auto=0`, `gc.autoDetach=false` | unset (auto-gc fired on every commit because the store held 64,863 loose objects, 7.10 GiB) | set; future commits need no `-c` flags, though passing them stays harmless |
| One deliberate `git repack -d` of the loose objects while no controller was alive | 5 packs, 3.34 GiB packed, 7.10 GiB loose | see the dated line at the end of this file |

No git process was running during any of this; both temporary packs had
no index and were reported as garbage by git itself. Tracked tree remained
clean. Nothing under `data/`, `p10/`, `p11/` or any seal was modified.

## 2. Pilot diagnosis [M]

Receipts: `results/download/*.json` (40), controller log
`logs/controller_download_pilot.log`, `manifests/acquisition_bytes.json`,
`logs/early_stall_action_20260914.json`.

**37 completed stars.** Wall 12.1 to 94.1 s, median 51.6 s. One
`search_lightcurve` call each. HTTP body bytes 1,415,122,549 in total for
the phase, about 38 MB per completed star, all of it FITS into the
lightkurve cache. The extracted arrays in `data/survey/audit_lc` are far
smaller: 0.30 GB for the 37 stars, median 7.2 MB per star, p90 15.3 MB.
By array bytes, sectors 56 to 105 carry 58% of the total; the P8 sector
27 to 55 superset carries 42% and is never a scientific input here.
Products per star: median 36 all-sector, 18 at sectors 56 and later;
distinct sectors at 56 and later: median 12, and **7 of 37 stars have fewer
than 3**, so expect the usable-sector cut to remove roughly a fifth of the
473. Authors at 56 and later: QLP 382, TESS-SPOC 179, SPOC 139 products.

**13 operational unknowns, all MAST-side, none scientific:**

| Class | Stars | Evidence |
|---|---:|---|
| Deadline (1,800 s) with no progress | 7 | `TIMEOUT 1800.0` to `1803.0`: TIC 5611068, 21028557, 29002055, 31020027, 33866201, 38507813, 55387764 |
| Stalled worker, CPU frozen at about 2.8 s from launch, stopped by the 10-minute check at about 1,000 s | 3 | TIC 4132769, 5881419, 14326626 (`early_stall_action_20260914.json`) |
| HTTP 502 Bad Gateway from `mast.stsci.edu/api/v0/invoke` | 2 | TIC 31109583 (171 s), 149349809 (67 s) |
| HTTP 404 from `Mashup.asmx/columnsconfig` | 1 | TIC 32090046 (0.5 s) |

The `socket.setdefaulttimeout(300)` in `scripts/audit_p5.py` did not bound
the hangs; the stalls sit inside astroquery's request and polling layer and
outlive it. The 1,800 s deadline is therefore the only thing that ended
them, and it dominated the phase: 1.39 h of union wall for work that healthy
stars finish in under two minutes.

## 3. Forecast for the remaining acquisition [M inputs, A arithmetic]

Remaining stars after Part A: 473 minus 37 completed = 436 (the 13 unknowns
included, since they have no index).

| Policy | HTTP bytes remaining | Cumulative against the 15 GB cap | `C:` after (from 41.9 GB, floor 25 GB) |
|---|---:|---:|---:|
| Current: download sectors 27 to 105 (`allowed_download_rows` lower bound 27) | 436 x 38.3 MB = 16.7 GB | 18.2 GB, **over the cap** | about 22 GB, **under the floor** |
| Proposed: download sectors 56 to 105 only | 436 x 22.2 MB = 9.7 GB | 11.2 GB | about 30.5 GB, with about 1.7 GB of arrays |

The 22.2 MB figure applies the 58% array-byte share to the measured HTTP
bytes; it is a proxy, so re-measure it on the first batch under the new
policy and stop if the cumulative charge is trending over 14 GB.

Wall time at 4 workers: healthy stars 436 x 55 s / 4 = 1.7 h. Stalls at the
pilot's 26% rate cost 113 x deadline / 4: 14.1 h at 1,800 s, 4.7 h at 600 s.
A single retry pass over the stall and HTTP-error stars adds at most the
same again at 600 s. Bounded worst case under the proposal is about 11 h;
the likely case is 3 to 5 h. Under the current deadline the worst case is
about 16 h, half the remaining scientific budget, for no information.

Nothing here requires the TESScut cache relocation. Keep it available as
the registered fallback if the re-measured bytes exceed the proxy.

## 4. Proposed amendments to register before launch [A]

**D1. Acquisition sector floor 27 -> 56.** In
`p10/part3/protocol/download_star.py`, `allowed_download_rows`:

```
-        if not 27<=sector<=configuration["sector_max"]:continue
+        if not configuration["sector_min"]<=sector<=configuration["sector_max"]:continue
```

and the policy string on the receipt from `"P8 acquisition >=27; ..."` to
`"P10.3 acquisition 56-105; excluded QLP removed before download"`. The
prompt's Part D already says "raw products at sectors 56 and later";
`manifests/sector_policy.json` currently records the 27 to 55 superset as
retained, so add the amendment row and re-freeze that manifest. The 37
pilot stars keep their superset indices; science selection at 56 to 105 is
unchanged for them. Test: a synthetic search table with sectors 27, 55, 56,
105, 106 and a QLP row at 80 keeps exactly 56 and 105.

**D2. Download deadline 1,800 s -> 600 s.** `protocol/config.json`
`deadlines_seconds.download`. Healthy maximum observed is 94 s; 600 s is
more than six times that and bounds a hang at a third of the old cost.

**D3. One recorded retry pass for network-classified failures.** After the
main pass closes, build a second job manifest from receipts whose status is
`TIMEOUT`, or `OPERATIONAL_UNKNOWN` with an `HTTPError`, `ConnectionError`,
`Timeout` or stall record, and run it once under the same controller,
same deadline, `attempt=2`, keeping the attempt-1 receipt beside it. This
is the prompt's own classification ("a MAST hang is a worker stall, not a
scientific outcome") applied mechanically; it is not an outcome-dependent
retry because the trigger is the transport error class, never the data.
A star failing both attempts is `INPUT_INELIGIBLE(acquisition)` with both
receipts, never a miss. The 13 pilot unknowns are the first members of
this pass.

**D4. Batch the remaining 436 in fixed identity order** (ascending TIC,
as the pilot) in batches of about 100 so each check-in sees a closed
batch, bytes can be re-measured after the first batch, and the storage
guard in the controller has a natural stop point.

Register D1 to D4 in `PREREGISTRATION_P10_3.md`'s amendment table, bump the
worker source version (new `source_sha256` will appear on every new
receipt), add the D1 test, then launch batch 1 with the hourly routine.

## 5. Things noticed, no action needed

- `results/acquisition_metadata/tic*.csv` are 150 to 180 KB each and are
  committed; 473 of them are about 75 MB and about 470 loose objects, fine
  now that auto-gc is off.
- `results/controllers/development_complete/progress.json.tmp` under
  `p11/p11_5` and `p11/p11_5/manifests/local_commit_receipt.json` are
  untracked leftovers of P11.5; leave them.
- Codex's app server was alive at the time of this review (processes from
  2026-09-12 12:32). No science owner exists. The hourly routine is
  verified PAUSED and must be re-armed only by the launch step.

## 6. Repack result [M]

`git repack -d -q` ran 20:07:28 to 20:15:22 UTC with no controller or other
git process alive, exit 0. Loose objects 64,863 (7.10 GiB) -> 0; packs 5 -> 6
(new pack 7.43 GB, mostly already-compressed evidence files, so little size
gain but no auto-gc trigger remains); `git count-objects`: garbage 0.
`git fsck --connectivity-only` passed. `C:` free 42.2 GB. The only tracked
change in the tree is the dated pointer appended to `RESUME_P10_3.md`; this
file and that line are for the Codex main task to commit with its next
checkpoint.
