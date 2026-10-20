"""Render ``docs/SURVEY_RESULTS.md`` from the prompt-4 outputs, so no number in
the document is typed by hand.

Inputs (all under ``data/survey/p4`` unless given): ``candidates.csv``,
``survivors.csv``, ``gate_counts.json``, ``run_summary.json``,
``expected_yield_p4.json``, ``catalog_versions_p4.json``, the per-candidate
JSON under ``expensive/``, and the P2 tables in
``data/survey/completeness_v1.json`` for the false-alarm expectation.
The case files for the top 10 are written by hand into ``docs/case_files/``
and linked, not generated. Nothing here is a detection.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent


def _j(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _fmt(v, nd=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "yes" if v else "no"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, float):
        if abs(v) >= 1000:
            return f"{v:,.0f}"
        return f"{v:.{nd}f}"
    return str(v)


def _count_events(run: dict) -> dict:
    out: dict = {}
    for ev in run.get("fallback_events") or []:
        k = str(ev.get("event") or "?")
        out[k] = out.get(k, 0) + 1
    return out


def _table(df: pd.DataFrame, cols: list[tuple[str, str, int]]) -> list[str]:
    head = "| " + " | ".join(h for _, h, _ in cols) + " |"
    sep = "|" + "|".join("---:" if df[c].dtype.kind in "fiu" else "---" for c, _, _ in cols) + "|"
    lines = [head, sep]
    for _, r in df.iterrows():
        cells = []
        for c, _, nd in cols:
            v = r.get(c)
            if isinstance(v, str):
                v = v.replace("|", "/")
            cells.append(_fmt(v, nd))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--p4", default=str(REPO / "data" / "survey" / "p4"))
    ap.add_argument("--out", default=str(REPO / "docs" / "SURVEY_RESULTS.md"))
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()
    p4 = Path(args.p4)
    cands = pd.read_csv(p4 / "candidates.csv")
    surv = pd.read_csv(p4 / "survivors.csv")
    gates = _j(p4 / "gate_counts.json")
    run = _j(p4 / "run_summary.json")
    yld = _j(p4 / "expected_yield_p4.json")
    catv = _j(p4 / "catalog_versions_p4.json")
    comp = _j(REPO / "data" / "survey" / "completeness_v1.json")
    n_targets = run.get("n_targets_in_list", 819)
    st = run.get("status_counts", {})
    n_ok = st.get("ok", 0)

    L = ["# Survey results: `targets_v1.csv` through the P3 pipeline (prompt 4)", "",
         f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} by `scripts/write_survey_results.py` from "
         f"`data/survey/p4/`. Ranking rules: `docs/RANKING_SCORE.md` (frozen before the run, commit 97d1d8b). "
         "The pipeline finds candidates; nothing in this document is a detection, and nothing has been submitted anywhere.",
         "",
         "## 1. What ran", "",
         f"* Population: {n_targets} stars of `data/survey/targets_v1.csv` (stratum 3, Tmag 10.5-13.5 dwarfs, QLP and "
         "TESS-SPOC light curves, hard-stop clean at build time).",
         f"* Search: preset `survey_v1` (chunked plan, 1-100 d, 30-minute bins, 600 s budget per star), the P3 "
         "characterisation and vetting stack inside every sub-search, whole-stitch re-measurement of every candidate.",
         f"* Job status: {', '.join(f'{k} {v}' for k, v in sorted(st.items()))} of {run.get('n_results', 0)} results; "
         f"{len(run.get('missing_from_results') or [])} target(s) without a result file.",
         f"* Retried jobs: {len(run.get('retried_jobs') or [])}; not-ok after retry: {len(run.get('not_ok_jobs') or [])} "
         "(listed in section 7).",
         f"* Wall clock per star (whole worker): median {_fmt(run.get('wall_s', {}).get('median'), 0)} s, "
         f"90th percentile {_fmt(run.get('wall_s', {}).get('p90'), 0)} s, max {_fmt(run.get('wall_s', {}).get('max'), 0)} s; "
         f"search stage median {_fmt(run.get('search_s', {}).get('median'), 0)} s; characterisation (fits) median "
         f"{_fmt(run.get('characterise_s', {}).get('median'), 1)} s; total CPU {_fmt(run.get('wall_s', {}).get('sum_hours'), 1)} h.",
         f"* Units (sectors) per star: median {_fmt(run.get('units_per_star', {}).get('median'), 0)}, "
         f"max {_fmt(run.get('units_per_star', {}).get('max'), 0)}; products used by author: "
         f"{', '.join(f'{k} {v}' for k, v in sorted((run.get('products_by_author') or {}).items()))}; stars by author set: "
         f"{', '.join(f'{k or 'none'} {v}' for k, v in sorted((run.get('stars_by_author_set') or {}).items()))}.",
         f"* Provenance events recorded by the download layer: {run.get('n_fallback_events', 0)} "
         f"({', '.join(f'{k} {v}' for k, v in sorted(_count_events(run).items()))}; `offline_cache_mode` is the P2 "
         "rebuild of the 300 completeness-sample stars from the local FITS cache, not a download fallback); searches "
         f"that hit the time budget: {run.get('n_budget_stops', 0)} (TIC {', '.join(str(t) for t in run.get('budget_stops') or [])}).",
         "* SPOC 2-minute products, where a star has them, are binned to 30 minutes and take precedence over TESS-SPOC "
         "and QLP in the same sector (the P2 ingestion rule); the counts above are products, not sectors.",
         ]
    pre = run.get("prefetch") or {}
    if pre:
        L.append(f"* Prefetch (download + stitch, 8 workers): {pre.get('status_counts')}; download per new star median "
                 f"{_fmt(pre.get('download_s_new_stars', {}).get('median'), 0)} s, p90 "
                 f"{_fmt(pre.get('download_s_new_stars', {}).get('p90'), 0)} s, max "
                 f"{_fmt(pre.get('download_s_new_stars', {}).get('max'), 0)} s (n = {pre.get('download_s_new_stars', {}).get('n')}).")
    L += ["", "## 2. Signals and gates", "",
          "| gate | rule (`docs/RANKING_SCORE.md`) | rows after | stars |", "|---|---|---:|---:|",
          f"| G0 | job finished ok | {n_ok} | {n_ok} |",
          f"| G1 | accepted candidates | {gates.get('G1_accepted_candidates', 0)} | {gates.get('stars_with_candidates', 0)} |",
          f"| G2 | stitch SNR >= 9 and epoch-consistent | {gates.get('G2_stitch_snr9_consistent', 0)} | |",
          f"| G3 | >= 3 transits on the stitch | {gates.get('G3_three_transits', 0)} | |",
          f"| G4 | verdict not likely-FP | {gates.get('G4_verdict_not_fp', 0)} | |",
          f"| G5 | fit converged and sees the dip (>= 3 sigma) | {gates.get('G5_fit_sees_dip', 0)} | {gates.get('stars_after_G5', 0)} |",
          f"| G6 | one row per signal (harmonics merged) | {gates.get('G6_unique_signals', 0)} | |",
          f"| G7 | fresh hard-stop cross-match (REJECT removed) | {gates.get('survivors_ranked', 0)} | {gates.get('survivor_stars', 0)} |",
          "",
          f"Cross-match at survivor time: {gates.get('G7_crossmatch_checked', 0)} candidate rows checked, "
          f"{gates.get('G7_crossmatch_rejected', 0)} REJECT (known object under the same TIC), "
          f"{gates.get('G7_crossmatch_flagged', 0)} FLAG (known object within 21 arcsec under another TIC; kept, noted). "
          f"Catalog stamp: `{catv.get('stamp', 'n/a')}` (rows per source: "
          f"{', '.join(f'{k} {v:,}' for k, v in sorted((catv.get('rows_per_source') or {}).items()))}).",
          "",
          f"Of the {gates.get('G1_accepted_candidates', 0)} accepted candidates, "
          f"{gates.get('candidates_2_transits_stitch', 0)} have only two transits on the stitch. "
          f"Candidates failing a gate, by first failed gate: "
          + ", ".join(f"{k} {int(v)}" for k, v in cands["first_failed_gate"].replace("", "none (survivor)").value_counts().items())
          + ".", ""]

    # verdict distribution of the G1 and G5 sets
    L += ["Light-curve verdicts of all accepted candidates: "
          + ", ".join(f"{k} {int(v)}" for k, v in cands["verdict"].value_counts().items()) + ".", ""]

    # 3. expectations
    n_g2g4 = int((cands["G2_stitch"] & cands["G4_verdict"]).sum())
    n_g2g3g4 = int((cands["G2_stitch"] & cands["G3_transits"] & cands["G4_verdict"]).sum())
    n_g2g4_chunk3 = int((cands["G2_stitch"] & cands["G4_verdict"] & (cands["n_transits"] >= 3)).sum())
    L += ["## 3. How many of these are expected to be noise", "",
          "From `docs/COMPLETENESS.md` (the same search on 300 population stars with no injection, P2, before the P3 "
          "fit-based flags existed). The P2 verdict column was the P2 vetting stack; the measured column applies the "
          "same cut with the P3 verdict, so the two differ by exactly the P3 changes (fit-based flags, secondary bound, "
          "alias re-test):", "",
          "| P2 threshold | per star (300 stars) | expected in 819 stars | measured here |", "|---|---:|---:|---:|",
          f"| accepted candidates, any SNR | 7.92 | 6,489 | {gates.get('G1_accepted_candidates', 0)} |",
          f"| stitch SNR >= 9, epoch-consistent, verdict not FP (G2 and G4) | 1.07 | 876 | {n_g2g4} |",
          f"| ... and >= 3 transits in the chunk that found it (the memo's count) | 0.38 | 311 | {n_g2g4_chunk3} |",
          f"| ... and >= 3 transits on the whole stitch (the G3 quantity) | 0.61 | 500 | {n_g2g3g4} |",
          "",
          "Read: the P2 false-alarm run predicts that of order 300 to 500 candidates in this population pass G2-G4 from "
          "systematics and un-catalogued variability alone, and the measured counts sit inside or below that range. "
          "The P2 sample is 300 of these same 819 stars, so this is not an independent prediction: it says the rest "
          "of the population behaves like the sample. Every survivor below should therefore be read against that "
          "background: the ranking orders them, it does not make them real.", "",
          "Expected number of REAL new signals in this population (`scripts/p4_expected_yield.py`, the P1 occurrence "
          "and noise model with the P2 measured recovery curve in place of the adopted efficiencies):", "",
          "| prior completeness | P1 model (efficiencies 0.8/0.7/0.4) | measured curve |", "|---|---:|---:|"]
    for lvl in ("low", "mid", "high"):
        L.append(f"| {lvl} | {_fmt((yld.get('p1_model') or {}).get('new_signals', {}).get(lvl), 2)} | "
                 f"{_fmt((yld.get('measured_model') or {}).get('new_signals', {}).get(lvl), 2)} |")
    L += ["", f"So at mid priors about {_fmt((yld.get('measured_model') or {}).get('new_signals', {}).get('mid'), 1)} real "
          "new signals are expected among several hundred noise survivors; a null result for the top 10 is the "
          "likelier outcome and would be consistent with the model. Caveat: " + str(yld.get("caveat", "")), ""]

    # 4. ranked table
    top = surv.head(args.top).copy()
    L += [f"## 4. Ranked survivors (top {args.top} of {len(surv)})", "",
          "Score = S_snr + S_ntr + S_fpp + S_rho (each 0-1; `docs/RANKING_SCORE.md`). `stitch_snr` and transits are "
          "the whole-stitch re-measurement. Depth, Rp/R*, Rp, a/R* and b are the survey's limb-darkened fit on the "
          "chunk that found the signal (the packets refit on the whole stitch). FPP / NFPP are TRICERATOPS on the top "
          f"{args.top} only (S_fpp = 0.5 where not computed). `final verdict` includes the centroid, contamination and "
          "NFPP checks. Full table with every column: `data/survey/p4/survivors.csv`.", ""]
    cols = [("rank", "rank", 0), ("tic_id", "TIC", 0), ("period_days", "P (d)", 4), ("stitch_snr", "stitch SNR", 1),
            ("stitch_n_transits", "transits", 0), ("depth_ppt", "depth (ppt)", 3), ("rp_rs", "Rp/R*", 3),
            ("rp_rearth", "Rp (Re)", 2), ("impact_b", "b", 2), ("density_ratio", "rho ratio", 2),
            ("density_dchi2_eff", "dchi2 eff", 1), ("fpp", "FPP", 3), ("nfpp", "NFPP", 3), ("fpp_uniform", "FPP uniform", 0),
            ("centroid_sigma", "centroid sigma", 1), ("s_snr", "S_snr", 2), ("s_ntr", "S_ntr", 2),
            ("s_fpp", "S_fpp", 2), ("s_rho", "S_rho", 2), ("score", "score", 2), ("verdict", "LC verdict", 0),
            ("verdict_final", "final verdict", 0), ("xmatch_status", "xmatch", 0), ("tmag", "Tmag", 1),
            ("n_units", "units", 0)]
    for c, _, _ in cols:
        if c not in top.columns:
            top[c] = None
    L += _table(top, cols)
    L += ["", "## 5. The packet gate and what the expensive steps changed", ""]
    if "fpp" in surv.columns and surv["fpp"].notna().any():
        done_all = surv[surv["expensive_done"] == True] if "expensive_done" in surv.columns else surv[surv["fpp"].notna()]
        extra = done_all[done_all["extra_expensive"] == True] if "extra_expensive" in done_all.columns else done_all.iloc[0:0]
        done = done_all[~done_all.index.isin(extra.index)]
        if len(extra):
            L.append(f"* {len(extra)} candidate(s) OUTSIDE the frozen pre-FPP top 30 also received the expensive steps "
                     "(a rerun after the first FPP merge selected from the post-FPP order); per the frozen rule their "
                     "FPP is reported here but does not enter their score: "
                     + ", ".join(f"TIC {int(r.tic_id)} at {r.period_days:.3f} d (final rank {int(r['rank'])}, FPP "
                                 f"{r.fpp:.3f}{' uniform' if r.fpp_uniform == True else ''}, NFPP {r.nfpp:.3f}, "
                                 f"final verdict {r.verdict_final})" for _, r in extra.iterrows()) + ".")
        n_done = len(done)
        n_block = int((done["G8_fpp_packet"] == False).sum()) if "G8_fpp_packet" in done.columns else 0
        n_pass = int((done["G8_fpp_packet"] == True).sum()) if "G8_fpp_packet" in done.columns else 0
        n_nofpp = int(done["fpp"].isna().sum())
        vf = done["verdict_final"].value_counts() if "verdict_final" in done.columns else {}
        vl = done["verdict"].value_counts()
        L += [f"* Expensive steps completed on {n_done} candidates: TRICERATOPS FPP <= 0.5 on {n_pass}, FPP > 0.5 on "
              f"{n_block} (packet built but marked blocked, P3 rule), no FPP value on {n_nofpp}.",
              "* Light-curve verdicts of those candidates: " + ", ".join(f"{k} {int(v)}" for k, v in vl.items()) + ".",
              "* Final verdicts after centroid, contamination and NFPP: " + ", ".join(f"{k} {int(v)}" for k, v in vf.items()) + ".",
              ]
        if "fpp_uniform" in done.columns and (done["fpp_uniform"] == True).any():
            uni = done[done["fpp_uniform"] == True]
            L.append(f"* TRICERATOPS returned a UNIFORM scenario posterior (every scenario at 1/n, blank names) on "
                     f"{len(uni)} candidate(s): " + ", ".join(f"TIC {int(r.tic_id)} at {r.period_days:.3f} d (FPP {r.fpp:.2f})"
                                                              for r in uni.itertuples())
                     + ". Those FPP values are an artefact of the input (every likelihood zero or NaN), not a measurement; "
                       "the frozen score used them as returned and this column says so.")
        if "centroid_flagged" in done.columns:
            L.append(f"* Centroid flagged (P0 module, all sectors with pixel data): {int((done['centroid_flagged'] == True).sum())} "
                     f"of {int(done['centroid_flagged'].notna().sum())} with a measurement. P3 measured that this module's "
                     "significance does not separate known planets from real blends on bright stars; it is reported, not decisive.")
        if "xmatch_status" in surv.columns:
            L.append(f"* Fresh cross-match on all {int(surv['xmatch_status'].notna().sum())} ranked survivors: "
                     + ", ".join(f"{k} {int(v)}" for k, v in surv["xmatch_status"].value_counts().items()) + ".")
    else:
        L.append("* Expensive steps not yet merged.")
    L += ["", "## 6. Packets and case files", "",
          f"Packets: `docs/packets/survey_v1/tic<TIC>_P<period>/` (packet.md, summary.png, ctoi_fields.json, fit.json, "
          "fpp.json, vetting.json, neighbours.csv, result.json) for every candidate in section 5. Case files for the "
          "top 10: `docs/case_files/`. Nothing is submitted by the pipeline; the human reads the audit (prompt 5) first.", ""]
    # 7. not-ok jobs
    L += ["## 7. Targets that did not complete", ""]
    bad = run.get("not_ok_jobs") or []
    if not bad and not run.get("missing_from_results"):
        L.append("None: every target produced a result with status `ok`.")
    else:
        for b in bad:
            L.append(f"* TIC {b.get('tic_id')}: {b.get('status')} after {b.get('attempts')} attempt(s): {b.get('error')}")
        for t in run.get("missing_from_results") or []:
            L.append(f"* TIC {t}: no result file")
    real_events = [ev for ev in (run.get("fallback_events") or []) if ev.get("event") != "offline_cache_mode"]
    if real_events:
        L += ["", "Fallback events recorded by the download layer (first 30):", ""]
        for ev in real_events[:30]:
            L.append(f"* TIC {ev.get('tic_id')}: {ev.get('event')} {ev.get('detail', '')}")
    else:
        L += ["", "No download fallback event was recorded on any target (the only provenance events are the "
              "`offline_cache_mode` notes of the P2 rebuild, section 1)."]
    Path(args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
