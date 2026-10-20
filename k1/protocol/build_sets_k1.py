"""K1 Part C1: the calibration and validation sets, drawn before any search (RULES_K1 section 2.1).

Subcommands
  kp     known planets: NASA pscomppars (tran_flag 1, pl_controv_flag 0) + TOIs with TFOPWG CP/KP,
         host and planet cuts, verified ephemerides, hash-ordered acquisition pool, DEV/HELD-OUT split.
         Truth goes to k1/truth/ (sealed; workers never read it); the host list goes to k1/manifests/.
  adv    adversarial negatives: TTT / TESS-EB EBs on A3-class hosts, blends within 42" of an EB,
         data/adversarial/targets_v1.csv cases that fit; DEV/HELD-OUT split.
  cal    injection (250) and false-alarm (250) hosts from the reserve, stratified, disjoint.
Every chosen star is recorded in the exposure ledger when it is downloaded (download_k1.py).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from k1_common import REPO, ROOT, DATA, TRUTH, environment, read, write, sha, utc

environment()
import sector_policy_k1 as SP  # noqa: E402
import sector_times_k1 as ST  # noqa: E402

SNAP = DATA / "catalogs" / "snap_20261008"
POP = DATA / "pop"
LISTS = REPO / "data" / "survey" / "cache" / "target_lists"
TWOMIN = REPO / "data" / "survey" / "cache" / "twomin_lists"
NASA_TAP = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
KP_COLS = ("pl_name,hostname,tic_id,ra,dec,pl_orbper,pl_orbpererr1,pl_orbpererr2,pl_tranmid,pl_tranmiderr1,"
           "pl_tranmiderr2,pl_trandur,pl_rade,pl_ratror,pl_imppar,pl_ratdor,st_teff,st_rad,st_mass,st_logg,sy_tmag,"
           "pl_orbper_reflink,pl_tranmid_reflink")
PS_COLS = ("pl_name,hostname,tic_id,default_flag,pl_orbper,pl_orbpererr1,pl_orbpererr2,pl_tranmid,pl_tranmiderr1,"
           "pl_tranmiderr2,pl_trandur,pl_rade,pl_refname")
KCLS = {"K": ((3900.0, 5300.0), (0.55, 1.0)), "eM": ((3600.0, 3899.0), (0.40, 0.70))}


def hkey(prefix: str, tic) -> str:
    return hashlib.sha256(f"{prefix}:{int(tic)}".encode()).hexdigest()


def nasa(query: str) -> pd.DataFrame:
    url = NASA_TAP + "?" + urllib.parse.urlencode({"query": query, "format": "csv"})
    for attempt in range(4):
        try:
            body = bounded_call(lambda: urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "tesshunter K1"}), timeout=300).read(), 600)
            return pd.read_csv(io.BytesIO(body), low_memory=False)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))


def bounded_call(fn, limit: float = 420.0):
    """Run a network call in a daemon thread; abandon it after ``limit`` seconds (MAST hangs, gotcha 4)."""
    import threading
    box = {}

    def run():
        try:
            box["v"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["e"] = exc
    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(limit)
    if th.is_alive():
        raise TimeoutError(f"network call exceeded {limit:.0f} s")
    if "e" in box:
        raise box["e"]
    return box["v"]


def tic_params(ids) -> pd.DataFrame:
    """TIC rows by ID (chunks of 2,000, astroquery MAST)."""
    from astroquery.mast import Catalogs
    ids = sorted({int(i) for i in ids})
    frames = []
    for a in range(0, len(ids), 2000):
        for attempt in range(4):
            try:
                tab = bounded_call(lambda: Catalogs.query_criteria(catalog="Tic", ID=ids[a:a + 2000]))
                frames.append(tab.to_pandas())
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(10 * (attempt + 1))
    df = pd.concat(frames, ignore_index=True).rename(columns={"ID": "tic_id"})
    if "GAIA" in df:
        df["GAIA"] = df["GAIA"].astype("string")
    df["tic_id"] = pd.to_numeric(df["tic_id"]).astype("int64")
    keep = ["tic_id", "ra", "dec", "Tmag", "Teff", "logg", "rad", "mass", "lumclass", "contratio", "gallat",
            "GAIA", "GAIAmag", "gaiabp", "gaiarp", "plx", "e_plx", "objType", "disposition"]
    return df[[c for c in keep if c in df.columns]].drop_duplicates("tic_id")


def k1_class(teff, rad, logg, lumclass) -> np.ndarray:
    teff, rad, logg = (pd.to_numeric(pd.Series(v), errors="coerce").to_numpy(float) for v in (teff, rad, logg))
    lc = pd.Series(lumclass).astype("string").fillna("").str.upper().to_numpy()
    out = np.full(len(teff), "", dtype=object)
    ok = ~(logg < 4.3) & (lc != "GIANT")
    for name, ((t0, t1), (r0, r1)) in KCLS.items():
        m = ok & (teff >= t0) & (teff <= t1) & (rad >= r0) & (rad <= r1) & (out == "")
        out[m] = name
    return out


def list_sectors(ids) -> pd.DataFrame:
    ids = np.asarray(sorted({int(i) for i in ids}), dtype=np.int64)
    have = {"qlp": {}, "tess-spoc": {}, "twomin": {}}
    for s in range(1, 106):
        for name in ("qlp", "tess-spoc"):
            st = LISTS / f"{name}_s{s:04d}.status"
            if st.exists() and st.read_text().strip() == "ok":
                for t in ids[np.isin(ids, np.load(LISTS / f"{name}_s{s:04d}.npy"))]:
                    have[name].setdefault(int(t), []).append(s)
        st = TWOMIN / f"s{s:03d}.status"
        if st.exists() and st.read_text().strip() == "ok":
            for t in ids[np.isin(ids, np.load(TWOMIN / f"s{s:03d}.npy"))]:
                have["twomin"].setdefault(int(t), []).append(s)
    rows = []
    for t in ids:
        use = sorted(SP.usable_sectors(have["qlp"].get(int(t), []), have["tess-spoc"].get(int(t), [])))
        rows.append({"tic_id": int(t), "sectors_usable": ",".join(map(str, use)), "n_usable": len(use),
                     "n_usable_s56": sum(1 for s in use if s >= 56), "sectors_2min": ",".join(map(str, have["twomin"].get(int(t), [])))})
    return pd.DataFrame(rows)


def propagated_sigma(p, sp, t0, st0, epochs_btjd) -> float:
    """Max 1-sigma mid-time uncertainty (days) over the given BTJD epochs."""
    if not np.isfinite(sp) or not np.isfinite(st0):
        return np.inf
    n = np.abs((np.asarray(epochs_btjd) - t0) / p)
    return float(np.max(np.sqrt(st0 ** 2 + (n * sp) ** 2))) if len(n) else np.inf


def epochs_in(period, t0, sectors, spans):
    out = []
    for s in sectors:
        sp = spans.get(int(s))
        if not sp:
            continue
        k0, k1 = int(np.ceil((sp["t_start"] - t0) / period)), int(np.floor((sp["t_end"] - t0) / period))
        out.extend(t0 + k * period for k in range(k0, k1 + 1))
    return out


# ── known planets ─────────────────────────────────────────────────────────────
def build_kp(cap: int = 220, pool_max: int = 200) -> dict:
    t0 = time.time()
    cp = nasa(f"select {KP_COLS} from pscomppars where tran_flag=1 and pl_controv_flag=0")
    cp["tic_id"] = pd.to_numeric(cp["tic_id"].astype(str).str.replace("TIC ", "", regex=False), errors="coerce")
    cp = cp[np.isfinite(cp.tic_id)].copy()
    cp["tic_id"] = cp.tic_id.astype("int64")
    cp["source"] = "pscomppars"
    toi = pd.read_csv(SNAP / "toi" / "raw" / "exofop_toi.csv", low_memory=False)
    toi = toi[toi["TFOPWG Disposition"].astype(str).isin(["CP", "KP"])].copy()
    tp = pd.DataFrame({"pl_name": "TOI-" + toi["TOI"].astype(str), "hostname": "TIC " + toi["TIC ID"].astype(str),
                       "tic_id": toi["TIC ID"].astype("int64"), "pl_orbper": toi["Period (days)"],
                       "pl_orbpererr1": toi["Period (days) err"], "pl_tranmid": toi["Epoch (BJD)"],
                       "pl_tranmiderr1": toi["Epoch (BJD) err"], "pl_trandur": toi["Duration (hours)"],
                       "pl_rade": toi["Planet Radius (R_Earth)"], "source": "toi_" + toi["TFOPWG Disposition"].astype(str),
                       "toi_depth_ppm": toi["Depth (ppm)"], "toi_planet_name": toi["Planet Name"]})
    # a TOI CP/KP already in pscomppars (same TIC, period within 1%) is not added twice
    merged = []
    by_tic = {t: g for t, g in cp.groupby("tic_id")}
    for _, r in tp.iterrows():
        g = by_tic.get(int(r.tic_id))
        if g is not None and np.any(np.abs(g.pl_orbper.to_numpy(float) / float(r.pl_orbper) - 1) < 0.01):
            continue
        merged.append(r)
    allp = pd.concat([cp, pd.DataFrame(merged)], ignore_index=True)
    allp = allp[allp.pl_orbper.between(0.5, 50.0) & allp.pl_rade.between(1.0, 8.0)].copy()
    hosts = tic_params(allp.tic_id.unique())
    allp = allp.merge(hosts.add_prefix("tic_").rename(columns={"tic_tic_id": "tic_id"}), on="tic_id", how="left")
    allp["k1_class"] = k1_class(allp.tic_Teff, allp.tic_rad, allp.tic_logg, allp.tic_lumclass)
    allp = allp[(allp.k1_class != "") & allp.tic_Tmag.between(9.5, 14.0)].copy()
    secs = list_sectors(allp.tic_id.unique())
    allp = allp.merge(secs, on="tic_id", how="left")
    spans = ST.load()
    rows = []
    for _, r in allp.iterrows():
        use = [int(s) for s in str(r.sectors_usable).split(",") if s]
        P, T0 = float(r.pl_orbper), float(r.pl_tranmid) - 2457000.0
        dur_h = float(r.pl_trandur) if np.isfinite(r.pl_trandur) else np.nan
        if not np.isfinite(dur_h):
            rho = float(r.tic_mass if np.isfinite(r.tic_mass) else r.tic_rad) / float(r.tic_rad) ** 3
            dur_h = 13.0 * (P / 365.25) ** (1 / 3) * rho ** (-1 / 3)
        n_pred = ST.predicted_transits(P, T0, dur_h / 24.0, use, spans)
        sp = np.nanmax(np.abs([r.pl_orbpererr1, r.get("pl_orbpererr2", np.nan)])) if np.isfinite(r.pl_orbpererr1) else np.nan
        st0 = np.nanmax(np.abs([r.pl_tranmiderr1, r.get("pl_tranmiderr2", np.nan)])) if np.isfinite(r.pl_tranmiderr1) else np.nan
        sig = propagated_sigma(P, sp, T0, st0, epochs_in(P, T0, use, spans))
        rows.append(dict(r, t0_btjd=T0, t14_hours=dur_h, n_transits_predicted=n_pred, timing_sigma_days=sig,
                         timing_ok=bool(sig < dur_h / 24.0 / 2.0), ephemeris_source="default"))
    kp = pd.DataFrame(rows)
    # ephemeris repair: planets failing the timing check try every other ps solution (smallest max error)
    fails = kp[(kp.n_transits_predicted >= 3) & ~kp.timing_ok & (kp.source == "pscomppars")]
    if len(fails):
        names = "','".join(sorted(set(fails.pl_name.astype(str).str.replace("'", "''"))))
        ps = nasa(f"select {PS_COLS} from ps where pl_name in ('{names}')")
        for i, r in fails.iterrows():
            use = [int(s) for s in str(r.sectors_usable).split(",") if s]
            best = None
            for _, q in ps[ps.pl_name == r.pl_name].iterrows():
                if not (np.isfinite(q.pl_orbper) and np.isfinite(q.pl_tranmid)):
                    continue
                qsp = np.nanmax(np.abs([q.pl_orbpererr1, q.pl_orbpererr2]))
                qst = np.nanmax(np.abs([q.pl_tranmiderr1, q.pl_tranmiderr2]))
                qt0 = float(q.pl_tranmid) - 2457000.0
                s_ = propagated_sigma(float(q.pl_orbper), qsp, qt0, qst, epochs_in(float(q.pl_orbper), qt0, use, spans))
                if best is None or s_ < best[0]:
                    best = (s_, q)
            if best is not None and best[0] < r.t14_hours / 24.0 / 2.0:
                q = best[1]
                kp.loc[i, ["pl_orbper", "t0_btjd", "timing_sigma_days", "timing_ok", "ephemeris_source"]] = [
                    float(q.pl_orbper), float(q.pl_tranmid) - 2457000.0, best[0], True, "ps:" + str(q.pl_refname)[:120]]
    elig = kp[(kp.n_transits_predicted >= 3) & kp.timing_ok].copy()
    elig["host_order"] = elig.tic_id.map(lambda t: hkey("20261009:k1:kp", t))
    host_order = elig.drop_duplicates("tic_id").sort_values("host_order").tic_id.tolist()
    # acquisition pool: hosts in hash order up to pool_max (the cap is applied after download, on realised data)
    pool = host_order[:pool_max]
    split = {t: hkey("20261010:k1:kp", t) for t in pool}
    ordered = sorted(pool, key=lambda t: split[t])
    n_dev = int(round(0.4 * len(ordered)))
    role = {t: ("DEV" if i < n_dev else "HELDOUT") for i, t in enumerate(ordered)}
    elig["role"] = elig.tic_id.map(role)
    elig["acq_rank"] = elig.tic_id.map({t: i + 1 for i, t in enumerate(pool)})
    elig = elig[elig.role.notna()].copy()
    TRUTH.mkdir(parents=True, exist_ok=True)
    elig.to_csv(TRUTH / "known_planets_truth.csv", index=False)
    hosts_out = elig.drop_duplicates("tic_id")[["tic_id", "role", "acq_rank", "k1_class", "tic_Tmag", "tic_Teff",
                                                "tic_rad", "tic_mass", "tic_logg", "tic_ra", "tic_dec",
                                                "n_usable", "sectors_usable"]].sort_values("acq_rank")
    hosts_out.to_csv(ROOT / "manifests" / "kp_hosts.csv", index=False)
    summary = {"utc": utc(), "n_pscomppars_transiting": int(len(cp)), "n_toi_cp_kp": int(len(tp)),
               "n_after_planet_and_host_cuts": int(len(allp)),
               "n_after_host_cuts": int(len(kp)), "n_predicted_ge3": int((kp.n_transits_predicted >= 3).sum()),
               "n_timing_ok": int(kp.timing_ok.sum()), "n_ephemeris_repaired": int((kp.ephemeris_source != "default").sum()),
               "n_eligible_planets": int(((kp.n_transits_predicted >= 3) & kp.timing_ok).sum()),
               "n_eligible_hosts": len(host_order), "acquisition_pool_hosts": len(pool),
               "pool_planets": int(len(elig)), "dev_hosts": n_dev, "heldout_hosts": len(pool) - n_dev,
               "cap_planets": cap, "truth_sha256": sha(TRUTH / "known_planets_truth.csv"),
               "hosts_sha256": sha(ROOT / "manifests" / "kp_hosts.csv"), "seconds": round(time.time() - t0, 1)}
    write(ROOT / "manifests" / "kp_selection.json", summary, replace=True)
    return summary


# ── adversarial negatives ─────────────────────────────────────────────────────
def build_adv(n_eb: int = 60, n_blend: int = 25) -> dict:
    from scipy.spatial import cKDTree
    t3 = pd.read_csv(SNAP / "ttt" / "ttt_table3.csv")
    t4 = pd.read_csv(SNAP / "ttt" / "ttt_table4.csv")
    teb = pd.read_csv(SNAP / "tess_eb" / "tess_eb.normalized.csv")
    teb["period_days"] = teb.detail.astype(str).str.extract(r"P=([0-9.eE+-]+)d")[0].astype(float)
    ebs = pd.concat([t3[["tic_id", "RAdeg", "DEdeg", "period_days"]].assign(cat="TTT3"),
                     t4[["tic_id", "RAdeg", "DEdeg", "period_days"]].assign(cat="TTT4"),
                     teb.rename(columns={"ra": "RAdeg", "dec": "DEdeg"})[["tic_id", "RAdeg", "DEdeg", "period_days"]].assign(cat="TESS-EB")],
                    ignore_index=True)
    ebs = ebs[ebs.period_days.between(0.5, 50.0)].drop_duplicates("tic_id")
    params = tic_params(ebs.tic_id)
    e = ebs.merge(params, on="tic_id", how="left")
    e["k1_class"] = k1_class(e.Teff, e.rad, e.logg, e.lumclass)
    eb_hosts = e[(e.k1_class != "") & e.Tmag.between(10.0, 13.5)].copy()
    eb_hosts["kind"] = "EB"
    # blends: an A3-class K/eM star (Tmag 10-13.5) within 42" of an EB within 3 Tmag; EB not the target
    pool = pd.read_pickle(POP / "tic_all.pkl")
    pool["k1_class"] = k1_class(pool.Teff, pool.rad, pool.logg, pool.lumclass)
    cand = pool[(pool.k1_class != "") & pool.Tmag.between(10.0, 13.5)].reset_index(drop=True)
    def unit(ra, dec):
        ra, dec = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
        return np.column_stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])
    tree = cKDTree(unit(cand.ra, cand.dec))
    ebp = e[np.isfinite(e.RAdeg) & np.isfinite(e.Tmag)].reset_index(drop=True)
    chord = 2 * np.sin(np.radians(42 / 3600) / 2)
    blends = []
    for i, idx in enumerate(tree.query_ball_point(unit(ebp.RAdeg, ebp.DEdeg), r=chord)):
        for j in idx:
            tgt = cand.iloc[j]
            if int(tgt.tic_id) == int(ebp.tic_id[i]) or abs(float(tgt.Tmag) - float(ebp.Tmag[i])) > 3:
                continue
            blends.append({"tic_id": int(tgt.tic_id), "kind": "BLEND", "eb_tic": int(ebp.tic_id[i]),
                           "eb_period_days": float(ebp.period_days[i]), "eb_cat": ebp.cat[i], "eb_tmag": float(ebp.Tmag[i]),
                           "Tmag": float(tgt.Tmag), "Teff": float(tgt.Teff), "rad": float(tgt.rad), "k1_class": tgt.k1_class,
                           "ra": float(tgt.ra), "dec": float(tgt.dec)})
    bl = pd.DataFrame(blends).drop_duplicates("tic_id")
    bl = bl[~bl.tic_id.isin(set(ebs.tic_id))]          # a target that is itself an EB counts as EB, not blend
    # survey blindness: a blend target can be a hard-stop-clean K/eM star; never take one from the frozen
    # survey list (STOP-E), nor an injection / false-alarm host
    exclude = set(pd.read_csv(ROOT / "survey" / "targets_k1.csv", usecols=["tic_id"]).tic_id.astype("int64"))
    for name in ("injection_hosts.csv", "false_alarm_hosts.csv"):
        if (ROOT / "manifests" / name).exists():
            exclude |= set(pd.read_csv(ROOT / "manifests" / name, usecols=["tic_id"]).tic_id.astype("int64"))
    n_bl_before = len(bl)
    bl = bl[~bl.tic_id.isin(exclude)]
    v1 = pd.read_csv(REPO / "data" / "adversarial" / "targets_v1.csv")
    v1 = v1[v1.cls.astype(str).str.lower() != "planet"].copy()
    v1p = tic_params(v1.tic_id).merge(v1[["tic_id", "cls", "period_known", "name"]], on="tic_id")
    v1p["k1_class"] = k1_class(v1p.Teff, v1p.rad, v1p.logg, v1p.lumclass)
    v1p = v1p[v1p.k1_class != ""].assign(kind="V1_" + v1p.cls.astype(str).str.upper())
    eb_hosts["order"] = eb_hosts.tic_id.map(lambda t: hkey("20261012:k1:adv", t))
    bl["order"] = bl.tic_id.map(lambda t: hkey("20261012:k1:adv", t))
    chosen_eb = eb_hosts.sort_values("order").head(n_eb)
    chosen_bl = bl.sort_values("order").head(n_blend)
    cols = ["tic_id", "kind", "k1_class", "Tmag", "Teff", "rad"]
    adv = pd.concat([chosen_eb.assign(eb_period_days=chosen_eb.period_days, eb_cat=chosen_eb.cat)[cols + ["eb_period_days", "eb_cat"]],
                     chosen_bl[cols + ["eb_tic", "eb_period_days", "eb_cat", "eb_tmag"]],
                     v1p.assign(eb_period_days=v1p.period_known)[cols + ["eb_period_days", "name"]]], ignore_index=True)
    adv = adv.drop_duplicates("tic_id")
    adv["split_order"] = adv.tic_id.map(lambda t: hkey("20261012:k1:adv", t))
    adv = adv.sort_values("split_order").reset_index(drop=True)
    n_dev = int(round(0.4 * len(adv)))
    adv["role"] = ["DEV" if i < n_dev else "HELDOUT" for i in range(len(adv))]
    TRUTH.mkdir(parents=True, exist_ok=True)
    adv.to_csv(TRUTH / "adversarial_truth.csv", index=False)
    adv[["tic_id", "role", "kind", "k1_class", "Tmag"]].to_csv(ROOT / "manifests" / "adv_hosts.csv", index=False)
    summary = {"utc": utc(), "n_eb_catalogue_rows_p_0p5_50": int(len(ebs)), "n_eb_hosts_eligible": int(len(eb_hosts)),
               "n_blend_targets_eligible": int(len(bl)), "n_blend_excluded_survey_or_cal": int(n_bl_before - len(bl)), "n_v1_fit": int(len(v1p)), "n_eb_chosen": int(len(chosen_eb)),
               "n_blend_chosen": int(len(chosen_bl)), "n_total": int(len(adv)), "dev": n_dev, "heldout": int(len(adv) - n_dev),
               "kinds": adv.kind.value_counts().to_dict(), "truth_sha256": sha(TRUTH / "adversarial_truth.csv")}
    write(ROOT / "manifests" / "adv_selection.json", summary, replace=True)
    return summary


# ── injection and false-alarm hosts from the reserve ─────────────────────────
def build_cal(n_inj=(170, 80), n_fa=(170, 80)) -> dict:
    res = pd.read_csv(ROOT / "survey" / "reserve_k1.csv")
    tb = pd.cut(res.Tmag, [10.0, 11.0, 12.0, 13.5001], right=False, labels=["10-11", "11-12", "12-13.5"])
    nb = pd.cut(res.n_usable, [5, 8, 13, 1000], right=False, labels=["5-7", "8-12", ">=13"])
    res = res.assign(tbin=tb.astype(str), nbin=nb.astype(str))
    out = {}
    taken = set()
    for name, counts, seed in (("injection", n_inj, 20261008), ("false_alarm", n_fa, 20261018)):
        rng = np.random.default_rng(seed)
        chosen = []
        for cls, n in zip(("K", "eM"), counts):
            sub = res[(res.k1_class == cls) & ~res.tic_id.isin(taken)]
            cells = sorted(sub.groupby(["tbin", "nbin"]).groups.items())
            per = {c: n // len(cells) for c, _ in cells}
            for c, _ in cells[: n - sum(per.values())]:
                per[c] += 1
            short = 0
            picks = []
            for c, idx in cells:
                pool = sub.loc[list(idx)]
                k = min(per[c], len(pool))
                short += per[c] - k
                picks.append(pool.iloc[rng.permutation(len(pool))[:k]])
            got = pd.concat(picks)
            # registered rule: a cell's shortfall is taken from the nearest Tmag bin (same n_usable bin
            # first, then the others), in seeded random order within the receiving cell
            order = ["10-11", "11-12", "12-13.5"]
            for c, idx in cells:
                need = per[c] - min(per[c], len(sub.loc[list(idx)]))
                if need <= 0:
                    continue
                ti = order.index(c[0])
                for tb_ in sorted(order, key=lambda x: (abs(order.index(x) - ti), order.index(x))):
                    for nb_ in [c[1]] + [x for x in ("5-7", "8-12", ">=13") if x != c[1]]:
                        if need <= 0:
                            break
                        rest = sub[(sub.tbin == tb_) & (sub.nbin == nb_) & ~sub.tic_id.isin(got.tic_id)]
                        take = rest.iloc[rng.permutation(len(rest))[:need]]
                        got = pd.concat([got, take.assign(realloc_from=f"{c[0]}|{c[1]}")])
                        need -= len(take)
            chosen.append(got.assign(set=name))
            taken |= set(got.tic_id)
        df = pd.concat(chosen)
        df.to_csv(ROOT / "manifests" / f"{name}_hosts.csv", index=False)
        out[name] = {"n": int(len(df)), "by_class": df.k1_class.value_counts().to_dict(),
                     "by_cell": df.groupby(["k1_class", "tbin", "nbin"]).size().astype(int).to_dict(),
                     "sha256": sha(ROOT / "manifests" / f"{name}_hosts.csv")}
    out["disjoint"] = not (set(pd.read_csv(ROOT / "manifests/injection_hosts.csv").tic_id)
                           & set(pd.read_csv(ROOT / "manifests/false_alarm_hosts.csv").tic_id))
    out["by_cell"] = {k: {str(kk): v for kk, v in out[k]["by_cell"].items()} for k in ("injection", "false_alarm")}
    for k in ("injection", "false_alarm"):
        out[k]["by_cell"] = out["by_cell"][k]
    out.pop("by_cell")
    write(ROOT / "manifests" / "cal_selection.json", dict(out, utc=utc()), replace=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["kp", "adv", "cal"])
    a = ap.parse_args()
    fn = {"kp": build_kp, "adv": build_adv, "cal": build_cal}[a.what]
    print(json.dumps(fn(), indent=1, default=str))
