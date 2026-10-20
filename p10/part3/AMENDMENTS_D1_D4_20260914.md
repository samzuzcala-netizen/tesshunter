# Prospective amendments D1 to D4 to the P10.3 acquisition (registered 2026-09-14, before launch)

Registered by the user's Claude session with the user's explicit go-ahead,
while no controller owner existed, after the pilot review in
`MAIN_REVIEW_20260914.md`. The Codex registration seal
(`manifests/registration_seal.json`: prompt snapshot, `PREREGISTRATION_P10_3.md`,
`protocol/config.json`) is unchanged; these amendments are recorded in a
separate file and versioned sources so the seal keeps verifying. Codex should
fold rows D1 to D4 into the preregistration amendment table at its next
checkpoint. None of these changes a scientific threshold, a rule, a
population cut, or any Part E to H setting.

| Id | Change | Where | Why |
|---|---|---|---|
| D1 | Acquisition sector floor 27 -> 56 (`config["sector_min"]`), applied to the search-result filter and to `audit_p5.download(sector_min=56)` | `protocol/download_star_v2.py` (new; `download_star.py` untouched) | The sector 27 to 55 superset is never a scientific input; downloading it would push cumulative acquisition to about 18 GB against the 15 GB cap and drive `C:` below its floor. Measured 58% of array bytes lie at 56 and later. |
| D2 | Download deadline 1,800 s -> 600 s | controller `--deadline 600` (a CLI argument; `config.json` unchanged) | Healthy stars finish in 12 to 94 s; 26% of pilot stars hung in MAST and the 1,800 s deadline cost 1.39 h for no information. |
| D3 | One recorded retry pass, attempt+1, for transport-class failures (TIMEOUT, or OPERATIONAL_UNKNOWN whose error is an HTTP, connection, timeout or socket error) and for completed stars with product-level failures (`--force` re-index, old and new index hashes on the receipt); at most two attempts per star; corrupt cached FITS removed and recorded before any download | `protocol/build_batches_v2.py retry`, `download_star_v2.py` | The prompt classes a MAST hang as a worker stall, not a scientific outcome; the trigger is the transport error class, never the data. Pilot stars whose first attempt failed are numbered attempt 2 in the batch manifests. |
| D4 | Remaining stars run in fixed ascending-TIC batches of 100 | `protocol/build_batches_v2.py plan` -> `manifests/download_v2_batch_NN.json` | Each check-in sees a closed batch; bytes are re-measured after batch 1; the controller's storage guard gets natural stop points. |

Receipts for version 2 live in `results/download_v2/tic<id>_a<attempt>.json` and
search metadata in `results/acquisition_metadata_v2/`; version-1 pilot receipts
and metadata are never overwritten. Every version-2 receipt carries
`source_sha256`, `attempt`, `force`, `sector_min`, `policy`, `amendment`,
`previous_index_sha256` and `corrupt_cached_fits_removed`.

Launch recipe per batch (one owner at a time, hidden window, stdout to
`logs/controller_<phase>.log` so `protocol/checkin.py` reads it):

```
python p10/part3/protocol/controller.py --phase download_v2_batch_NN --jobs p10/part3/manifests/download_v2_batch_NN.json --workers 4 --deadline 600
```

Supervision follows section 4a of the prompt: a detached owner, one early check
about 10 minutes after each launch, then bounded read-only checks no more often
than every 30 minutes via `protocol/checkin.py`, each appended to
`logs/checkins.jsonl` and `RESUME_P10_3.md`. Stop conditions are the controller's
own (storage floor plus 1 GB, queue cap) and the prompt's Part I. No Part E or
later phase is launched by this session.

Source hashes at registration (filled by the launch step):

```
023990575cba89063ee168cd367f7d15976ac609c8e07a1a5cf34e03079e6a16 *p10/part3/protocol/download_star_v2.py
fed1f6a5c6c98f05c4c3431e933d1198aac3b195bea58d3cd7b564fcbfa0af0f *p10/part3/protocol/build_batches_v2.py
1e8fb5bf1140c7574ef67badb7b20e76cc015d6d33bc878e903df2114b3e10bc *p10/part3/tests/test_download_v2.py
c0ba6e8c2e1066b0efd0bd1ecc6d5d0d19e240e2e87fd0c0cfedd1bd98cd97ee *p10/part3/manifests/download_v2_plan.json
ce20fa5e84a756ba94835e6bba07edbf605de45621f43abb6729de2ca4ac53a2 *p10/part3/manifests/download_v2_batch_01.json
3991f9f646bd019dc1e68d1ed69d52422dff1898a55dd3f040ba447826d28ed3 *p10/part3/manifests/download_v2_batch_02.json
234d4fb33312810a46ebb9c49e0292e50ad0a792c07b86177ad9e4b818310b45 *p10/part3/manifests/download_v2_batch_03.json
6d59f08dd7b692dea39806567d102753cc466aac00454ca7112f2ad2c6673a68 *p10/part3/manifests/download_v2_batch_04.json
f5a14fdb21b50caaf2a311d5b1b3c37565404b5fb73423dba569188e01e0c2ec *p10/part3/manifests/download_v2_batch_05.json
```

Tests at registration: `pytest p10/part3/tests -q` 26 passed (2026-09-14 20:31 UTC). Plan: 473 eligible, 37 already indexed, 436 remaining in 5 batches; 13 pilot failures at attempt 2.
