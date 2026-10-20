# P10 completed native raw-spectrum validation [M]

Only the already-permitted 19 P8 and 18 post-lock P9 Stage C records; raw-spectrum validation, not C adoption.

All 37 records pass the 14 validation groups: eight original reproductions reused and 29 new p8.0 reproductions. Original/native inputs, grids and installed powers reproduce exactly; all five spectrum arrays are finite. Existing records and measured timings were not rewritten.

Installed-concentration triggers: **1/37**. Trigger keys: `tic237222864_P10.2888`.

The frozen trigger uses installed-power concentration > 0.5; the robust statistic uses power_raw at that same installed strongest peak. Existing experimental C decisions and all control/adoption requirements remain separate. The eight reused walls can include residual work and must not be combined with the 29 new reproduction walls as a paired timing benchmark.

| Set | Key | Source | Original native decision | Installed strongest period (d) | Installed SDE | Installed concentration | Raw robust at the same peak | Trigger |
|---|---|---|---|---:|---:|---:|---:|---|
| p8 | `tic100273626_P10.3806` | Reused | FAIL | 13.1875018563 | 12.790111 | 0.0010616083 | 13.809942 | No |
| p8 | `tic144277542_P12.9812` | New p8.0 | PASS | 12.9813560968 | 14.912043 | 0.0009710225 | 18.665813 | No |
| p8 | `tic154566869_P2.9260` | New p8.0 | FAIL | 13.0115801331 | 13.574967 | 0.0015363558 | 11.481277 | No |
| p8 | `tic154566869_P8.9053` | New p8.0 | PASS | 8.8850363204 | 13.737098 | 0.0015732735 | 11.250054 | No |
| p8 | `tic155895971_P13.1279` | New p8.0 | PASS | 13.1280773672 | 10.228207 | 0.0003532255 | 15.157714 | No |
| p8 | `tic198517968_P15.4315` | New p8.0 | FAIL | 72.2321160417 | 26.472979 | 0.0043178583 | 62.194713 | No |
| p8 | `tic230120862_P16.7959` | New p8.0 | PASS | 16.7914246333 | 16.656771 | 0.0013391771 | 27.770708 | No |
| p8 | `tic237917568_P18.7059` | Reused | FAIL | 67.6371803151 | 14.495857 | 0.0008881566 | 22.766141 | No |
| p8 | `tic237921294_P18.3141` | Reused | FAIL | 91.5884168398 | 18.815165 | 0.0014409119 | 22.134752 | No |
| p8 | `tic273226810_P0.5806` | New p8.0 | FAIL | 87.6729695765 | 11.536041 | 0.0005489456 | 23.723216 | No |
| p8 | `tic309025900_P14.9235` | Reused | FAIL | 0.9934960069 | 20.415522 | 0.0010967154 | 19.777004 | No |
| p8 | `tic356226514_P0.5947` | New p8.0 | FAIL | 1.1902571869 | 6.752612 | 0.0015820439 | 6.214562 | No |
| p8 | `tic388200613_P20.8357` | Reused | FAIL | 65.3040437613 | 12.259554 | 0.0005921481 | 17.549108 | No |
| p8 | `tic394680557_P29.9904` | Reused | FAIL | 53.5537386900 | 12.880462 | 0.0007568442 | 15.808792 | No |
| p8 | `tic404927114_P27.5436` | New p8.0 | PASS | 27.5436520123 | 15.861812 | 0.0010818308 | 15.523396 | No |
| p8 | `tic464282202_P0.8166` | New p8.0 | FAIL | 49.7657268869 | 14.492337 | 0.0006721762 | 21.540934 | No |
| p8 | `tic464282202_P16.7299` | New p8.0 | FAIL | 0.8116283807 | 12.890246 | 0.0004341401 | 13.376814 | No |
| p8 | `tic52205459_P10.0755` | New p8.0 | FAIL | 95.0169609715 | 15.756475 | 0.0010475512 | 21.579023 | No |
| p8 | `tic80256158_P10.8184` | New p8.0 | PASS | 10.8183706369 | 14.054415 | 0.0008058297 | 13.436790 | No |
| p9 | `tic231702397_P5.0783` | New p8.0 | PASS | 5.0780680837 | 75.967928 | 0.0204608502 | 101.717860 | No |
| p9 | `tic335590096_P1.5228` | New p8.0 | PASS | 1.5227480351 | 140.950530 | 0.1027416593 | 387.943681 | No |
| p9 | `tic102734241_P10.9047` | New p8.0 | PASS | 10.9050934654 | 18.573437 | 0.0045412039 | 16.426604 | No |
| p9 | `tic243641947_P2.5929` | New p8.0 | PASS | 2.5926073408 | 268.755443 | 0.2721594626 | 515.300333 | No |
| p9 | `tic271971130_P19.2884` | New p8.0 | PASS | 19.2880756303 | 88.635753 | 0.0228334255 | 103.978609 | No |
| p9 | `tic389900760_P5.8005` | New p8.0 | PASS | 5.7997655708 | 33.378837 | 0.0046084636 | 27.951840 | No |
| p9 | `tic259168516_P4.8025` | New p8.0 | PASS | 4.8026097765 | 116.082718 | 0.0483918603 | 190.168999 | No |
| p9 | `tic181804752_P4.9893` | New p8.0 | PASS | 4.9899287713 | 95.549509 | 0.0221385308 | 83.012049 | No |
| p9 | `tic178709444_P3.4721` | New p8.0 | PASS | 3.4716561464 | 131.241955 | 0.0722811382 | 219.894394 | No |
| p9 | `tic161032923_P3.9644` | New p8.0 | PASS | 3.9652578681 | 46.660787 | 0.0056867646 | 45.071125 | No |
| p9 | `tic284441182_P18.0890` | Reused | FAIL | 2.5271055051 | 32.074467 | 0.0067955045 | 31.646962 | No |
| p9 | `tic284441182_P2.5272` | New p8.0 | PASS | 2.5271055051 | 38.160782 | 0.0096191642 | 37.151532 | No |
| p9 | `tic237222864_P10.2888` | Reused | FAIL | 10.2886693064 | 3.556564 | 0.9986414948 | 285.414120 | Yes |
| p9 | `tic377293776_P2.0439` | New p8.0 | PASS | 2.0439319340 | 28.567751 | 0.0047391867 | 34.831572 | No |
| p9 | `tic33595516_P0.7655` | New p8.0 | PASS | 0.7655417669 | 68.435772 | 0.1254071340 | 196.024849 | No |
| p9 | `tic177079323_P5.7518` | New p8.0 | PASS | 5.7515501344 | 35.978259 | 0.0266525646 | 59.660659 | No |
| p9 | `tic230006888_P12.2789` | New p8.0 | PASS | 12.2783922148 | 59.259357 | 0.0617328195 | 95.294650 | No |
| p9 | `tic41422753_P2.4708` | New p8.0 | PASS | 2.4712193460 | 43.089955 | 0.0644322528 | 85.544762 | No |

Full measurements, validation groups and input/artifact hashes: `stage_c_native_raw_validation.json`. Robust fallback retention and significant-peak adoption still require the documented implementation corrections, fixed injection sample and adversarial/negative/alias controls.
