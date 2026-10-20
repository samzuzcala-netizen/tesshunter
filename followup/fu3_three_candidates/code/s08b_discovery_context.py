"""Discovery-funnel context for the selection replay (read-only on the S1 survey receipts).

For S1 batch 1: stars searched, pre-gate candidates, and Stage A/S/B/C decisions per candidate and per star.  For each
target: every pre-gate candidate of the discovery search (period, stitch S/N, search rank) and its fate at each
stage.  This places the three signals inside the funnel that selected them: how many other signals the same stars
produced, and which stage removed them.  Output: results/s08b_discovery_context.json, tables/discovery_funnel_targets.csv
"""
import collections
import csv

from fu3_common import *

RUN = S1 / "runs" / "s1_b1"
FR = S1 / "funnel_receipts" / "s1_b1"
STAGES = ("A", "S", "B", "C", "D")


def decisions():
    out = {}
    for st in STAGES:
        d = {}
        for p in (FR / st).glob("*.json"):
            try:
                d[p.stem] = read(p).get("decision")
            except Exception:   # noqa: BLE001
                d[p.stem] = "UNREADABLE"
        out[st] = d
    return out


def pregate(q):
    return bool((q.get("stitch_snr") or 0) >= 7.1 and int(q.get("stitch_n_transits") or 0) >= 3 and q.get("stitch_epoch_consistent"))


def main():
    dec = decisions()
    n_searched = len(list((RUN / "receipts").glob("s1_*.json")))
    per_stage = {st: dict(collections.Counter(v.values())) for st, v in dec.items()}
    stars = {st: collections.defaultdict(list) for st in STAGES}
    for st, v in dec.items():
        for cid, d in v.items():
            stars[st][cid.split("_")[1]].append(d)
    star_stats = {st: dict(stars_with_job=len(s), stars_with_pass=sum(1 for x in s.values() if "PASS" in x),
                           stars_with_2plus_pass=sum(1 for x in s.values() if x.count("PASS") >= 2))
                  for st, s in stars.items()}
    # how far each Stage-A-passing candidate got
    reach = collections.Counter()
    for cid, d in dec["A"].items():
        if d != "PASS":
            continue
        last = "A"
        for st in STAGES[1:]:
            if dec[st].get(cid) == "PASS" or (st == "D" and cid in dec["D"]):
                last = st
            else:
                break
        reach[last] += 1
    tgt = {}
    rows = []
    for tic in TICS:
        res = read(RUN / "results" / f"s1_{tic}.json")
        pl = (res.get("result") or {}).get("planets") or []
        cands = []
        for rank, q in enumerate(pl, 1):
            if not pregate(q):
                continue
            cid = f"s1_{tic}_p{int(q['planet_num']):02d}"
            fate = {st: dec[st].get(cid) for st in STAGES if cid in dec[st]}
            c = dict(candidate_id=cid, search_rank=rank, period_d=q["period_days"], snr=q.get("snr"), stitch_snr=q.get("stitch_snr"),
                     stitch_n_transits=q.get("stitch_n_transits"), depth_ppt=q.get("depth_ppt"), fate=fate)
            cands.append(c)
            rows.append(dict(tic=tic, candidate_id=cid, search_rank=rank, period_d=round(q["period_days"], 5),
                             stitch_snr=round(q.get("stitch_snr") or 0, 2), stitch_n_transits=q.get("stitch_n_transits"),
                             depth_ppt=round(q.get("depth_ppt") or 0, 3), **{f"stage_{st}": fate.get(st, "") for st in STAGES}))
        tgt[str(tic)] = dict(n_accepted=len(pl), n_pregate=len(cands), candidates=cands)
    out = dict(generated_utc=utc(), source=str(FR), n_searched=n_searched, per_stage_decisions=per_stage, star_stats=star_stats,
               a_pass_last_stage_reached=dict(reach), targets=tgt)
    save(RES / "s08b_discovery_context.json", out)
    with open(ROOT / "tables" / "discovery_funnel_targets.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    log("s08b", f"searched {n_searched}; per stage {per_stage}; stars {star_stats}; A-pass reach {dict(reach)}")
    for tic, v in tgt.items():
        log("s08b", f"{tic}: accepted {v['n_accepted']} pregate {v['n_pregate']}: " +
            "; ".join(f"#{c['search_rank']} {c['period_d']:.4f} d S/N {c['stitch_snr']:.2f} {c['fate']}" for c in v["candidates"]))


if __name__ == "__main__":
    main()
