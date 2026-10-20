# K1 STOP-C: Parts D-F price above 60 queue-hours (paused for the user)

Dated 2026-10-08 (UTC). Prompt K1, Part C4. Tags: [M] measured, [R] review, [A] adopted/registered,
[I] interpretation. Queue-hours = summed job wall / workers x 1.5 margin, at the prompt's worker
counts (24 search, 16 A/S/B, 6 C at 4 TLS threads, 6 D). Sources: `k1/results/timing_pilot.json`,
`timing_pilot2.json`, `stop_c_scenarios_pilot2.json`.

**State.** STOP-C fired. No Part D, E or F run has started. No HELD-OUT set has been touched. Nothing
is a detection; nothing was uploaded, pushed or sent.

## 1. What the timing pilot measured (C4)

The pilot used 40 injection hosts with one injection each (reserve hosts, never survey stars) and
24 search workers on this machine (24 physical / 32 logical cores).

**Search, per star [M] (n = 40 paired hosts):**

| arm, budget | mean wall s | median | p90 | max | partition-limited | pre-gate / star |
|---|---|---|---|---|---|---|
| survey_k1, 8,100 s | 1,354 | 777 | 3,357 | 4,824 | 6/40 = 15% | 4.25 |
| survey_k1, 5,400 s | 1,286 | 780 | 3,251 | 3,998 | 8/40 = 20% | 4.20 |
| survey_k1, 2,700 s | 938 | 814 | 1,675 | 1,871 | 15/40 = 37.5% | 3.90 |
| survey_k1_s56, 8,100 s | 680 | 373 | 2,014 | 2,373 | 0/40 | 3.48 |
| survey_k1_s56, 2,700 s | 530 | 362 | 1,309 | 1,416 | 8/40 = 20% | 3.50 |

* [A] **E4 outcome (mechanical).** No tested budget has 5% or fewer partition-limited hosts, so the
  rule falls back to 8,100 s and reports 15% (6/40, Wilson 95% 7-29%).
* [M] Most pre-gate passers come from the stitch partition (P >= 10 d): 113 of 162 in a partial
  count. Only 10% sit within 3% of a TESS-orbit multiple.

**Funnel unit costs [M] (survey_k1 arm at 8,100 s, after amendment 2; first pilot in brackets):**

| stage | n | mean wall s | median | pass |
|---|---|---|---|---|
| A | 170 | 195 (192) | 88 | 96/170 |
| S | 96 | 11 | 8 | any mode 19/96, `bound` 18 |
| B | 19 | 4 | 4 | 19/19 |
| C (first pilot, 10 B-passers) | 10 | 3,962 | 3,747 | 8/10 |
| D (dry run, n = 1) | 1 | 235 | - | - |

The survey_k1_s56 arm's A stage costs 91 s per candidate (n = 139). For comparison, P12's figures
were [M]: search 766 s per star, A 353 s per candidate (pilot), and C mean 2,977 s / median 1,333 s
(n = 75).

**Injection versus natural candidates [M].** These rely on evaluator-side matching against the
pilot injection truth (calibration hosts only).

| survey_k1 (40 hosts) | pre-gate | A pass | S pass (`bound`) | S pass (any mode) |
|---|---|---|---|---|
| injected (unique injections) | 26 | 19 | 18 | 18 |
| natural (candidates) | 142 (3.55/star) | 77 (54%) | 0 | 1 |

| survey_k1_s56 (40 hosts) | pre-gate | A pass | S pass (`bound`) | S pass (any mode) |
|---|---|---|---|---|
| injected | 20 | 17 | 17 | 17 |
| natural | 119 (2.98/star) | 50 (42%) | 2 | 3 |

* [I] Stage A passes about half of the natural pre-gate false alarms, against 6% in P12's natural
  load (`p12/results/natural_load_p12.json`). Stage S removes almost all of them.
* [I] Stage C load therefore comes mainly from real signals. The pilot-literal survey price
  (C load 0.48/star) is inflated by the one injection per host.

## 2. Price of Parts D-F

**As registered (S0): 224 queue-hours [M-based]**, against the STOP-C threshold of 60.

| part | item | jobs | unit s | workers | queue-h |
|---|---|---|---|---|---|
| D | search survey_k1 (1,000 inj + 250 FA + 99 DEV) | 1,349 | 1,354 | 24 | 31.7 |
| D | search survey_k1_s56 (inj + FA) | 1,250 | 680 | 24 | 14.7 |
| D | Stage A legacy + ramp, survey_k1 | 11,466 | 195 | 16 | 58.1 |
| D | Stage A legacy + ramp, survey_k1_s56 | 8,688 | 91 | 16 | 20.6 |
| D | Stage S, all modes (both arms) | 5,332 | 11 | 16 | 1.5 |
| D | C capped injection sample | 150 | 3,962 | 6 | 41.3 |
| D | DEV B, C, D | 47 | - | - | 13.7 |
| F | HELD-OUT search + A/S/B/C/D (160 hosts) | - | - | - | 28.8 |
| F | P12 paired search + A/S/B/C (107 hosts) | - | - | - | 13.2 |

**Scenarios [M-based; S2's speed-up is an assumption]:**

| scenario | D-F queue-h | needs |
|---|---|---|
| S0 as registered | 224 | nothing |
| S1: registered option 1 at its floor (600 injections, 150 FA hosts) | 176 | your choice (registered) |
| S2: S1 + a cheaper BLS grid (25% faster assumed) | 167 | the paired 100-injection check (about 5 queue-h), with at most 2 pp loss |
| S3: S1 + ramp arm on survey_k1 only + C sample 75 | 149 | two amendments |

[I] The registered options alone cannot bring Parts D-F under 60 queue-hours. Stage A at about
195 s per candidate across ~20,000 legacy+ramp jobs, and Stage C at about 4,000 s per candidate,
are fixed by the protocol's design, not by the counts.

Further levers, none of them measured:

* Compute the legacy and ramp A verdicts from one A run. This saves about 39 queue-h, but needs a
  restructure of the frozen p10 Stage A machinery and an identity test.
* Run 8 C workers (32 threads) instead of 6. This saves at most 25% of C, and only if the CPU was
  not saturated.

## 3. Price of the 10,000-star survey (for the launch plan)

* **[M-based] about 493 queue-hours at natural rates** (about 20.5 days of wall time):
  * search 235;
  * A 180;
  * S 6;
  * C 69;
  * D 4.
* **Range 433-796 queue-hours**, from the Wilson 95% interval of the natural C load (1/40 hosts:
  0.4-12.9% per star).
* The pilot-literal figure of 1,842 queue-hours is an upper bound inflated by the injections.

## 4. Defect found and fixed in the pilot: amendment 2

[M] In the first pilot the survey_k1 arm's Stage A killed 11 of 26 pre-gate injections, against
3 of 20 in the s56 arm. Ten of the eleven failed only the depth-consistency criterion, at stitch
SNR 12-485.

The cause: per-event box-mean depths of 1,800 s events are smeared shallow and depend on the
sampling phase. Amendment `k1/protocol/AMENDMENT_K1_20261008_2.md` makes the Stage A per-event
depth exposure-aware: the amplitude of an exposure-integrated limb-darkened template. It sits
behind `event_vet.EVENT_DEPTH_TEMPLATE`, which defaults to off, so every pre-K1 suite is unchanged:

* tests 786 + 1 skipped;
* p11 7;
* p11.5 98;
* p12 248;
* k1 59;
* P8 smoke 0 differences.

[M] Re-measured on the same pilot candidates (`pilot2`):

* survey_k1 injections through A rose from 15 to 19, and through S (`bound`) from 14 to 18.
* Natural candidates were unchanged: A 77, S 0/1.
* The s56 arm is unchanged: 17/17 injections, natural A 49 to 50.

[M] Five survey_k1 injections still fail depth consistency, at stitch SNR 78-307. Their exposure
classes now agree within 2%; what remains is sector-to-sector depth scatter of 3-5% (one case is a
single sector 15% shallow), which the chi-square resolves at that SNR.

[I] That is a property of the existing criterion at very high SNR, not a cadence defect. It is
**not** changed: a systematic floor would be threshold tuning. Part D will quantify it as
A-stage loss by expected SNR.

**You may withdraw amendment 2 before Part D.** The cost: about 4 of 26 survey_k1 injections per 40
would be lost at A for an instrumental reason, and E1 would partly measure that defect.

## 5. Early pilot hints on E1 (not the registered rule; n = 40 injections)

[M]

* Injections through S (`bound`): survey_k1 18, survey_k1_s56 17.
* Natural pre-gate false alarms per star: 3.55 vs 2.98, a ratio of 1.19 (E1 requires 1.5 or less).
* Search wall time per star: 1.99x (E1 requires 3x or less).

[I] On these numbers the all-sector arm passes E1's cost and false-alarm conditions. Its recovery
gain is not resolved at n = 40. E1 is decided only in Part D (expected SNR 7-20 cohort, host
bootstrap).

## 6. Options for the user

1. **S1 (recommended) [I]: registered option 1 at its floor (600 injections, 150 FA hosts), with
   approval to exceed 60 queue-hours.** About 176 queue-hours (about 7.3 days of wall time if run
   back to back).
   * No other amendment; the C sample stays at 150.
   * [M] Of the 1,000 drawn injections, 259 fall in E1's expected-SNR 7-20 cohort; a 600 subset
     keeps about 155.
   * [I] With about 15% discordant pairs, the host-bootstrap lower bound clears 0 at a gain of
     roughly 6 pp with 600 injections, against roughly 5 pp with 1,000. The review expects a much
     larger gain [R], but this is the cost of S1.
2. **S0 as registered.** About 224 queue-hours (about 9.3 days).
3. **S3: S1 plus two amendments** (ramp arm only on survey_k1, C sample 75). About 149 queue-hours.
   E3 then decides only on the survey_k1 arm, and the C-stage completeness interval roughly
   doubles in width.
4. **S2: S1 plus the cheaper-grid check.** About 5 queue-hours more first, then about 167 if it
   qualifies.
5. **Stop at NOT_READY** and keep the pilot findings.

Amendment 2 stands unless you withdraw it.

## 7. User decision (recorded 2026-10-08T14:00Z)

[A] The user chose **S0, as registered** (1,000 injections, 250 FA hosts, ramp arm on both arms,
C sample 150), approving about 224 queue-hours for Parts D-F. **Amendment 2 is kept.** Part D
proceeds at the E4 budget of 8,100 s.
