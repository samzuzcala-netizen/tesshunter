"""Summarise the bounded discovery replay (s08) for the report.

Inverted (null) groups: per star, accepted signals, pre-gate passes, the largest pre-gate stitch S/N, Stage A jobs and
passes, and the same star's real-data counts from the S1 batch-1 receipts.  A one-sided 95 % upper limit on the
per-star Stage A pass rate (Clopper-Pearson) is reported per group and pooled.
Injected groups: per star, the injection's expected S/N, whether a pre-gate candidate matched P, P/2 or 2P within 1 %
(the controller's Stage A rule), the matched candidate's stitch S/N, and whether it passed Stage A; recovery fractions
with 68 % Clopper-Pearson intervals, against the real candidate's discovery stitch S/N.
Outputs: results/s08_summary.json, tables/replay_summary.csv
"""
import csv

from scipy.stats import beta as _beta

from fu3_common import *

REPLAY = CACHE / "replay"
FR1 = S1 / "funnel_receipts" / "s1_b1"


def cp(k, n, cl=0.68):
    """Two-sided Clopper-Pearson interval."""
    if n == 0:
        return [None, None]
    a = (1 - cl) / 2
    lo = 0.0 if k == 0 else float(_beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k == n else float(_beta.ppf(1 - a, k + 1, n - k))
    return [lo, hi]


def ul95(k, n):
    """One-sided 95 % upper limit on a binomial rate."""
    return None if n == 0 else (1.0 if k == n else float(_beta.ppf(0.95, k + 1, n - k)))


def a_decision(cid, label):
    p = REPLAY / "data" / "funnel_receipts" / label / "A" / f"{cid}.json"
    return read(p).get("decision") if p.exists() else None


def real_counts(tic):
    """The star's own (non-inverted) discovery counts in S1 batch 1."""
    p = S1 / "runs" / "s1_b1" / "results" / f"s1_{tic}.json"
    if not p.exists():
        return dict(real_pregate=None, real_A_pass=None)
    pl = (read(p).get("result") or {}).get("planets") or []
    pg = [q for q in pl if (q.get("stitch_snr") or 0) >= 7.1 and int(q.get("stitch_n_transits") or 0) >= 3 and q.get("stitch_epoch_consistent")]
    n_pass = 0
    for q in pg:
        f = FR1 / "A" / f"s1_{tic}_p{int(q['planet_num']):02d}.json"
        if f.exists() and read(f).get("decision") == "PASS":
            n_pass += 1
    return dict(real_pregate=len(pg), real_A_pass=n_pass)


def matches(row, P):
    p = row.get("period_days") or 0
    return any(abs(p / (P * f) - 1) < 0.01 for f in (1.0, 0.5, 2.0))


def main():
    st = read(REPLAY / "state.json")
    plan = read(REPLAY / "jobs" / "plan.json")
    ctx = read(RES / "s08b_discovery_context.json")
    disc_snr = {}
    for tic in TICS:
        c = next(x for x in ctx["targets"][str(tic)]["candidates"] if x["fate"].get("C") == "PASS")
        disc_snr[tic] = dict(stitch_snr=c["stitch_snr"], period=c["period_d"], search_rank=c["search_rank"])
    rows = []
    for p in plan:
        jid = p["job_id"]
        d = st.get("done", {}).get(jid)
        group = ("inv_target" if p["tic"] == p["candidate"] else "inv_control") if p["variant"] == "inv" else "inj"
        row = dict(job_id=jid, variant=p["variant"], group=group, tic=p["tic"], candidate=p["candidate"], done=bool(d),
                   status=(d or {}).get("status"), cpu_s=(d or {}).get("cpu_s"))
        if p["variant"] == "inv":
            row.update(real_counts(p["tic"]))
        if p["variant"] == "inj":
            tr = read(REPLAY / "store_inj" / jid / "injection_truth.json")
            row.update(inj_period=tr["period"], inj_expected_snr=tr["expected_snr"], inj_n_transits=tr["n_observed_transits"],
                       inj_depth_ppm=tr["depth_max_ppm"])
        if d:
            cf = RES / f"s08_candidates_{jid}.json"
            cands = read(cf) if cf.exists() else []
            label = f"fu3{p['variant']}"
            pg = [c for c in cands if c.get("passes_pregate")]
            row.update(n_accepted=len(cands), n_pregate=len(pg),
                       max_pregate_stitch_snr=max([c.get("stitch_snr") or 0 for c in pg], default=None))
            if p["variant"] == "inv":
                decs = [a_decision(c["candidate_id"], label) for c in pg]
                row.update(n_A=sum(x is not None for x in decs), n_A_pass=sum(x == "PASS" for x in decs),
                           a_pass_periods=[round(c["period_days"], 4) for c, x in zip(pg, decs) if x == "PASS"],
                           a_pending=sum(x is None for x in decs))
            else:
                m = [c for c in pg if matches(c, row["inj_period"])]
                decs = [a_decision(c["candidate_id"], label) for c in m]
                best = max(m, key=lambda c: c.get("stitch_snr") or 0) if m else None
                anym = [c for c in cands if matches(c, row["inj_period"])]
                row.update(recovered_accepted=bool(anym), recovered_pregate=bool(m),
                           recovered_A=any(x == "PASS" for x in decs), n_A=sum(x is not None for x in decs),
                           matched_stitch_snr=(best or {}).get("stitch_snr"),
                           matched_period_ratio=((best or {}).get("period_days") or 0) / row["inj_period"] if best else None,
                           matched_rank=(cands.index(best) + 1) if best else None, a_pending=sum(x is None for x in decs))
        # a star counts once its search and all its Stage A jobs are finished (or the replay ended with them unrun)
        row["complete"] = bool(d) and (row.get("a_pending", 0) == 0 or bool(st.get("finished_utc")))
        rows.append(row)
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(ROOT / "tables" / "replay_summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    def inv_group(sel):
        g = [r for r in rows if sel(r)]
        dn = [r for r in g if r["complete"]]
        k = sum(1 for r in dn if r.get("n_A_pass"))
        return dict(planned=len(g), done=len(dn), pregate=sum(r.get("n_pregate") or 0 for r in dn),
                    max_pregate_snr=max([r["max_pregate_stitch_snr"] for r in dn if r.get("max_pregate_stitch_snr")], default=None),
                    n_A=sum(r.get("n_A") or 0 for r in dn), n_A_pass=sum(r.get("n_A_pass") or 0 for r in dn), stars_with_A_pass=k,
                    ul95_star_A_rate=ul95(k, len(dn)),
                    real_pregate=sum(r.get("real_pregate") or 0 for r in dn if r.get("real_pregate") is not None),
                    real_A_pass=sum(r.get("real_A_pass") or 0 for r in dn if r.get("real_A_pass") is not None),
                    a_pass_list=[dict(job_id=r["job_id"], periods=r["a_pass_periods"]) for r in dn if r.get("n_A_pass")])

    inv = dict(targets=inv_group(lambda r: r["group"] == "inv_target"),
               **{f"controls_{c}": inv_group(lambda r, c=c: r["group"] == "inv_control" and r["candidate"] == c) for c in TICS},
               all_controls=inv_group(lambda r: r["group"] == "inv_control"),
               all=inv_group(lambda r: r["variant"] == "inv"))
    inj = {}
    for c in TICS:
        g = [r for r in rows if r["group"] == "inj" and r["candidate"] == c]
        dn = [r for r in g if r["complete"]]
        kp = sum(r["recovered_pregate"] for r in dn)
        ka = sum(r["recovered_A"] for r in dn)
        snr = [r["matched_stitch_snr"] for r in dn if r.get("matched_stitch_snr")]
        inj[str(c)] = dict(planned=len(g), done=len(dn), recovered_accepted=sum(r["recovered_accepted"] for r in dn),
                           recovered_pregate=kp, recovered_A=ka, frac_pregate=kp / len(dn) if dn else None, ci68_pregate=cp(kp, len(dn)),
                           frac_A=ka / len(dn) if dn else None, ci68_A=cp(ka, len(dn)),
                           expected_snr=[round(r["inj_expected_snr"], 1) for r in dn],
                           matched_stitch_snr=[round(x, 2) for x in snr],
                           median_matched_snr=float(np.median(snr)) if snr else None,
                           n_matched_above_discovery=sum(1 for x in snr if x >= disc_snr[c]["stitch_snr"]),
                           discovery=disc_snr[c])
    summ = dict(generated_utc=utc(), cpu_h=st.get("cpu_s", 0) / 3600, finished=st.get("finished_utc"), budget_hit=st.get("budget_hit"),
                n_done=sum(r["done"] for r in rows), n_complete=sum(r["complete"] for r in rows), n_planned=len(rows), not_run=st.get("not_run", []), a_not_run=st.get("a_not_run", []),
                inverted=inv, injected=inj)
    save(RES / "s08_summary.json", summ)
    log("s08sum", f"{summ['n_done']}/{summ['n_planned']} done, {summ['cpu_h']:.2f} CPU-h; inverted all {inv['all']}; injected {inj}")


if __name__ == "__main__":
    main()
