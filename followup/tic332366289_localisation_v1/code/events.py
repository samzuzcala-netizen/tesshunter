"""Event table, exact frame masks and control windows.

Writes: events.csv, results/events.json, results/masks/*.csv + masks npz (D:),
results/controls.csv. Reads the historical Stage A record read-only.
"""
from __future__ import annotations

import csv
import json

import common as C
import numpy as np

import data as Dmod
import windows as W

CFG = W.CFG
EA = CFG["ephemerides"]["primary"]
EF = CFG["ephemerides"]["sensitivity"][0]


def tc(eph, n):
    return eph["t0_btjd"] + n * eph["period_d"]


def main():
    stA = json.load(open(C.PACKET / "stageA.json"))
    ev_rec = {e["n"]: e for e in stA["per_ephemeris"]["survey"]["events"]}
    fit = json.load(open(C.PACKET / "fit.json"))
    meta = json.load(open(C.INPUTS / "fits_metadata.json"))
    sectors = {s: Dmod.load_sector(s) for s in (57, 77, 78, 79, 80, 84)}
    (C.RESULTS / "masks").mkdir(parents=True, exist_ok=True)
    rows, evjson = [], []
    # every predicted cycle whose time falls inside any cached sector, plus Stage A's observed events
    cycles = sorted(set([0, 29, 32, 33, 39]))
    for n in range(0, 40):
        t = tc(EA, n)
        for s, S in sectors.items():
            if S.time.min() - 1 <= t <= S.time.max() + 1:
                cycles.append(n)
    cycles = sorted(set(cycles))
    for n in cycles:
        rec = ev_rec.get(n, {})
        tA, tF = tc(EA, n), tc(EF, n)
        sec = rec.get("sector")
        if sec is None:
            for s, S in sectors.items():
                if S.time.min() - 0.5 <= tA <= S.time.max() + 0.5:
                    sec = s
        S = sectors.get(sec)
        row = {"event_id": f"E{n:02d}", "n_cycle": n, "sector": sec,
               "tc_primary_EA_btjd": round(tA, 6), "tc_sensitivity_EF_btjd": round(tF, 6),
               "tc_stageA_record_btjd": rec.get("tc_btjd"), "tc_EF_minus_EA_min": round((tF - tA) * 1440, 2),
               "duration_EA_h": round(EA["duration_d"] * 24, 4), "duration_EF_h": round(EF["duration_d"] * 24, 4),
               "stageA_observed": rec.get("observed"), "stageA_excluded": rec.get("excluded"),
               "stageA_decision": ("kept" if rec.get("observed") and not rec.get("excluded") else
                                   "excluded" if rec.get("excluded") else "not observed"),
               "stageA_reason": "; ".join(rec.get("exclusion_reasons", [])) or rec.get("reason", ""),
               "photometry_product": "TESS-SPOC HLSP 200 s" if rec.get("author") == "TESS-SPOC" else "",
               "photometry_author": rec.get("author", ""),
               "spoc_procver": meta["spoc_lc"].get(str(sec), {}).get("primary", {}).get("PROCVER", "") if sec else "",
               "spoc_data_release": meta["spoc_lc"].get(str(sec), {}).get("primary", {}).get("DATA_REL", "") if sec else "",
               "stageA_det_depth_ppt": rec.get("det_depth_ppt"), "stageA_det_err_ppt": rec.get("det_depth_err_ppt"),
               "stageA_sap_depth_ppt": rec.get("sap_depth_ppt"), "stageA_sap_err_ppt": rec.get("sap_depth_err_ppt"),
               "in_packet_fit_4_transits": bool(sec in fit["data"]["sectors"] and rec.get("observed"))}
        if S is not None:
            row.update({"camera": S.camera, "ccd": S.ccd, "tesscut_file": C.TESSCUT[sec].name,
                        "tesscut_data_release": meta["tesscut"][str(sec)]["primary"].get("DATA_REL")})
            for tag, eph in (("EA", EA), ("EF", EF)):
                role, st = W.select(S.time, S.good, S.dump, tc(eph, n), eph["duration_d"])
                row[f"{tag}_n_in_good"] = st["n_in_good"]
                row[f"{tag}_n_in_frames"] = st["n_in_frames"]
                row[f"{tag}_n_ref_left_good"] = st["n_ref_left_good"]
                row[f"{tag}_n_ref_right_good"] = st["n_ref_right_good"]
                row[f"{tag}_dumps_in_span"] = st["n_dumps_in_span"]
                row[f"{tag}_pixel_usable"] = st["usable"]
                row[f"{tag}_pixel_unusable_reasons"] = "; ".join(st["unusable_reasons"])
                if st["n_frames_in_span"] > 0:
                    sel = np.abs(S.time - tc(eph, n)) <= W.full_half_span(eph["duration_d"])
                    with open(C.RESULTS / "masks" / f"mask_E{n:02d}_s{sec}_{tag}.csv", "w", newline="") as fh:
                        wr = csv.writer(fh)
                        wr.writerow(["frame_index", "spoc_cadenceno", "time_btjd_spoc", "time_btjd_tesscut",
                                     "dt_tesscut_minus_spoc_s", "tesscut_quality", "spoc_quality", "good",
                                     "momentum_dump", "role"])
                        for i in np.nonzero(sel)[0]:
                            wr.writerow([int(i), int(S.cadenceno[i]), f"{S.time[i]:.7f}", f"{S.time_cut[i]:.7f}",
                                         f"{S.dt_s[i]:.2f}", int(S.q_cut[i]), int(S.q_spoc[i]), int(S.good[i]),
                                         int(S.dump[i]), int(role[i])])
        role_txt = ("primary" if (sec in CFG["sectors"]["primary"] and row["stageA_decision"] == "kept") else
                    "diagnostic (Stage A excluded; never pooled)" if sec == 84 else
                    "not an observed event")
        row["followup_role"] = role_txt
        rows.append(row)
        evjson.append(row)
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(C.WS / "events.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=keys)
        wr.writeheader()
        for r in rows:
            wr.writerow(r)
    C.write_json(C.RESULTS / "events.json", C.clean({
        "primary_ephemeris": EA, "sensitivity_ephemeris": EF,
        "four_transit_resolution": ("The packet fit (scripts/audit_p5.py fit_step) uses every light-curve point within "
                                    "+/- max(3 x duration, 0.4 d) of each predicted transit in all sectors, without "
                                    "Stage A's keep/exclude list; its 4 transits are Stage A's 3 kept events plus the "
                                    "Stage-A-excluded sector 84 event (n=39)."),
        "sector_meta": {str(s): S.meta for s, S in sectors.items()},
        "events": evjson}))
    # ------------------------------------------------------------ controls
    real_tcs = [tc(e, n) for e in (EA, EF) for n in range(0, 40)]
    span = W.full_half_span(EA["duration_d"])
    ctrl = []
    for s in (57, 79, 80, 84):
        S = sectors[s]
        tg = S.time[S.good]
        centres = np.arange(tg.min() + span, tg.max() - span, 4.0 / 24.0)
        k = 0
        for c in centres:
            if min(abs(c - t) for t in real_tcs) < 2 * span + 0.01:
                continue
            role, st = W.select(S.time, S.good, S.dump, c, EA["duration_d"])
            if not st["usable"]:
                continue
            ctrl.append({"sector": s, "window_id": f"s{s}_w{k:03d}", "tc_btjd": round(float(c), 6),
                         "n_in_good": st["n_in_good"], "n_ref_left_good": st["n_ref_left_good"],
                         "n_ref_right_good": st["n_ref_right_good"]})
            k += 1
    # independent subset (greedy, non-overlapping full spans) and its calibration/evaluation halves
    for s in (57, 79, 80, 84):
        last = -1e9; idx = 0
        for r in [r for r in ctrl if r["sector"] == s]:
            if r["tc_btjd"] - last >= 2 * span:
                r["independent"] = True
                r["independent_index"] = idx
                r["half"] = "calibration" if idx % 2 == 0 else "evaluation"
                last = r["tc_btjd"]; idx += 1
            else:
                r["independent"] = False; r["independent_index"] = -1; r["half"] = "overlapping"
    with open(C.RESULTS / "controls.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(ctrl[0].keys()))
        wr.writeheader()
        for r in ctrl:
            wr.writerow(r)
    for s in (57, 79, 80, 84):
        rr = [r for r in ctrl if r["sector"] == s]
        print(s, "controls", len(rr), "independent", sum(r["independent"] for r in rr))
    for r in rows:
        print({k: r.get(k) for k in ("event_id", "sector", "tc_primary_EA_btjd", "tc_EF_minus_EA_min", "stageA_decision",
                                       "EA_n_in_good", "EA_n_ref_left_good", "EA_n_ref_right_good", "EA_pixel_usable",
                                       "EA_pixel_unusable_reasons", "EF_pixel_usable", "followup_role")})
    for s, S in sectors.items():
        print(s, S.meta)


if __name__ == "__main__":
    main()
