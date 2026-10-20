"""P8 Stage D: rank, pixel/FPP measurements, and review packets from the audit fit.

No re-search or re-fit is performed here. The frozen audit's native-cadence
arrays, physical fit and cached Gaia record supply the packet. TRICERATOPS
uses its TIC scene and its separately cached, wider Gaia background population;
the one-arcminute P8 neighbour cone is retained for the resolved-neighbour
assessment and must not be substituted for that 0.1-square-degree population.
Final verdicts are stamped separately after the measurements are reviewed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "data/survey/p8"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, data):
    from audit_p5 import jdump
    jdump(Path(path), data)


#: The rule set this tool runs under; ``main`` sets it from ``--rules``.  "p8.0"
#: reproduces the P8 packets; "p10.0" adds the tier evaluation and F1-F9.
RULES_NAME = "p8.0"


def setup(root):
    import p8_funnel as F
    import audit_p5 as A
    F.set_root(root)
    F.set_rules(RULES_NAME)
    A.set_roots(F.OUT, F.LC_ROOT)
    return F


def uniform_fpp(fp):
    """The existing P4 diagnostic: blank labels and equal top probabilities."""
    tops = (fp.get("top_scenarios") or [])[:3]
    vals = [t.get("prob") for t in tops]
    return bool(len(vals) >= 2 and all(v is not None and np.isfinite(v) for v in vals)
                and max(vals) - min(vals) < 1e-6
                and all(not str(t.get("scenario") or "") for t in tops))


def rank_candidates(root):
    from tesshunter.ranking import score_v2
    import audit_p5 as A
    F = setup(root)
    rows = []
    for job in F.eligible("D"):
        key = F.V.kkey(job["tic_id"], job["period"])
        a, s, b, c = [read(root / folder / f"{key}.json")
                      for folder in ("stageA", "secondary", "stageB", "stageC")]
        if not all(A.cache_matches(r) for r in (a, s, b, c)):
            raise ValueError(f"{key}: stale stage record")
        if a["decision"] != "PASS" or s["gate"] not in ("PASS", "HOLD") or b["decision"] != "PASS" or c["decision"] != "PASS":
            raise ValueError(f"{key}: candidate did not pass every preceding gate")
        nb_path = root / "neighbours" / f"tic{job['tic_id']}.json"
        nb = read(nb_path)
        gaia = (nb.get("gaia") or {}).get("target")
        if gaia is None or (nb.get("gaia") or {}).get("error"):
            raise ValueError(f"{key}: missing cached Gaia target")
        chosen = a["per_ephemeris"][a["chosen_ephemeris"]]
        score = score_v2(chosen["det_kept"].get("snr"), chosen["events"], gaia,
                         b.get("deep_event_host"), s["gate"])
        rows.append({**job, "key": key, **score, "gaia_record": str(nb_path.relative_to(REPO))})
    rows.sort(key=lambda r: (-r["score_v2"], r["tic_id"], r["period"]))
    for i, row in enumerate(rows, 1):
        row["rank_v2"] = i
    targets_path = REPO / "data/survey/targets_p8.csv"
    targets = list(csv.DictReader(targets_path.open(encoding="utf-8")))
    present = sum((root / "neighbours" / f"tic{r['tic_id']}.json").exists() for r in targets)
    result = {"rules_version": "p8.0", "n_stage_c_survivors": len(rows),
              "n_population_targets": len(targets), "n_population_gaia_record_files": present,
              "ranking_decides_no_verdict": True, "candidates": rows}
    write(root / "ranking_p8.json", result)
    return rows


def measurement_inputs(root, job):
    """Reject stale/non-native inputs before any network call or expensive work."""
    import audit_p5 as A
    key = job["key"]
    paths = [root / folder / f"{key}.json" for folder in
             ("stageA", "secondary", "stageB", "stageC", "fit", "tls")]
    paths.extend([root / "neighbours" / f"tic{job['tic_id']}.json",
                  root / f"crossmatch_{root.name}.json", root / "tls" / f"{key}_lc.npz"])
    for path in paths[:6]:
        if not A.cache_matches(read(path)):
            raise ValueError(f"{path}: stale P8 input")
    for folder, field, allowed in (("stageA", "decision", {"PASS"}),
                                    ("secondary", "gate", {"PASS", "HOLD"}),
                                    ("stageB", "decision", {"PASS"}), ("stageC", "decision", {"PASS"})):
        if read(root / folder / f"{key}.json").get(field) not in allowed:
            raise ValueError(f"{key}: {folder} did not pass")
    stage_d = read(root / "stageD" / f"{key}.json")
    if not A.cache_matches(stage_d) or not stage_d.get("provisional_verdict") or stage_d.get("verdict") == "ERROR":
        raise ValueError(f"{key}: Stage D is unfinished")
    fit = read(root / "fit" / f"{key}.json")
    if fit.get("fit_input") != A._p8_fit_input(job["tic_id"], job["period"]):
        raise ValueError(f"{key}: physical fit does not use the current accepted Stage C ephemeris")
    adopted = fit["adopted"]
    required = [adopted.get(k) for k in ("period", "t0_btjd", "rp_rs", "a_rs", "b", "t14_hours", "depth_max_ppt")]
    if any(v is None or not np.isfinite(v) for v in required):
        raise ValueError(f"{key}: physical fit is incomplete")
    tls = read(root / "tls" / f"{key}.json")
    products = tls["inputs"]["products"]
    if any(int(p["sector"]) < 56 or abs(float(p["cadence_s"]) - 200) > 1 for p in products):
        raise ValueError(f"{key}: expected only sectors >=56 at harmonised 200 s")
    with np.load(root / "tls" / f"{key}_lc.npz") as z:
        arrays = {k: z[k] for k in ("time_unbinned", "flux_unbinned", "sector_unbinned")}
    hashes = {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    return fit, arrays, hashes


def measure_one(root, job, n_draws=100_000, force=False):
    from tesshunter.fpp import run_fpp
    from survivor_packets import centroid_all_sectors
    F = setup(root)
    key, tic = job["key"], job["tic_id"]
    fit, arrays, hashes = measurement_inputs(root, job)
    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode("utf-8")).hexdigest()
    out_path = root / "expensive" / f"{key}.json"
    if out_path.exists() and not force:
        old = read(out_path)
        if (old.get("source_sha256") == hashes and old.get("input_fingerprint") == fingerprint
                and old.get("n_draws") == n_draws and old.get("status") == "complete"):
            build_packet(root, job, fit, arrays, old)
            return old
    a = fit["adopted"]
    nb = read(root / "neighbours" / f"tic{tic}.json")
    sectors = sorted(int(s) for s in np.unique(arrays["sector_unbinned"]))
    rec = {"key": key, "tic_id": tic, "rules_version": "p8.0", "source_sha256": hashes,
           "input_fingerprint": fingerprint,
           "n_draws": n_draws, "status": "running", "timings": {},
           "ephemeris_source": "P8 all-transit physical fit", "cadence_s": 200.0,
           "period": a["period"], "t0_btjd": a["t0_btjd"], "duration_days": a["t14_hours"] / 24,
           "gaia_context": F.V.gaia_flags(nb, a["depth_max_ppt"]),
           "gaia_neighbours": nb["gaia"],
           "gaia_usage": "Cached P8 target and resolved-neighbour assessment. TRICERATOPS also uses its TIC scene and separately cached wider Gaia field-star population; the P8 cone is not that population."}
    prior = read(out_path) if out_path.exists() else {}
    can_resume = (prior.get("source_sha256") == hashes and prior.get("input_fingerprint") == fingerprint
                  and prior.get("n_draws") == n_draws and not force)
    start = time.perf_counter()
    for name in ("centroid", "fpp"):
        part_start = time.perf_counter()
        if can_resume and (prior.get(name) or {}).get("available"):
            rec[name] = prior[name]
            rec["timings"][name] = {"resumed": True}
        else:
            try:
                if name == "centroid":
                    rec[name] = centroid_all_sectors(tic, nb["ra"], nb["dec"], sectors,
                        a["period"], a["t0_btjd"], a["t14_hours"] / 24, len(sectors), tesscut_only=True)
                else:
                    fp = run_fpp(tic, sectors[:3], arrays["time_unbinned"], arrays["flux_unbinned"], None,
                        period=a["period"], t0=a["t0_btjd"], duration=a["t14_hours"] / 24,
                        depth_frac=a["depth_max_ppt"] / 1000, exp_time_days=200 / 86400,
                        tmag=nb.get("tmag"), aperture="circular", author="QLP", n_draws=n_draws,
                        red_noise_beta=fit["data"]["beta_red_noise"], ra=nb["ra"], dec=nb["dec"],
                        cache_dir=root / "expensive/fpp_cache", lightkurve_cache_dir=os.environ.get("LIGHTKURVE_CACHE"),
                        fold_mode="binned", input_fingerprint=fingerprint, force=force)
                    rec[name] = fp.to_dict()
            except Exception as exc:
                rec[name] = {"available": False, "error": f"{type(exc).__name__}: {exc}"}
            rec["timings"][name] = {"wall_seconds": round(time.perf_counter() - part_start, 1)}
        write(out_path, rec)
    rec["fpp_uniform"] = uniform_fpp(rec["fpp"])
    rec["status"] = "complete" if all((rec.get(k) or {}).get("available") for k in ("centroid", "fpp")) else "incomplete"
    rec["timings"]["total_seconds"] = round(time.perf_counter() - start, 1)
    write(out_path, rec)
    stamp_tiers(root, job)
    build_packet(root, job, fit, arrays, rec)
    return rec


def stamp_tiers(root, job):
    """[P10] Under a ``p10`` rule set, re-evaluate the tiers with the expensive record (and
    any fixed-aperture / difference-image records present) and stamp the Stage D record's
    ``tiers`` and ``provisional_verdict``.  No-op under p8.0."""
    F = setup(root)
    rule_set = getattr(getattr(F, "V", None), "RULE_SET", None)
    if rule_set is None or rule_set.verdict_tiers != "p10":
        return None
    d_path = root / "stageD" / f"{job['key']}.json"
    if not d_path.exists():
        return None
    rec = read(d_path)
    rec["tiers"] = F.V.evaluate_tiers({"tic_id": job["tic_id"], "period": job["period"],
                                       "depth_ppt": rec.get("survey_depth_ppt")})
    rec["provisional_verdict"], rec["provisional_reason"] = F.V.provisional_verdict(rec)
    write(d_path, rec)
    return rec["tiers"]


def pixel_followup_lines(root, key, out):
    """Attach reviewed diagnostics only while all their inputs still match."""
    path = root / "pixel_followup" / f"{key}.json"
    if not path.exists():
        return []
    followup = read(path)
    if followup.get("key") != key or followup.get("status") != "complete":
        raise ValueError(f"{key}: incomplete pixel follow-up")
    for name, expected in followup["source_sha256"].items():
        if hashlib.sha256((REPO / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"{key}: stale pixel follow-up input {name}")
    write(out / "pixel_followup.json", followup)
    lines = ["## Pixel follow-up", "", followup["assessment"], "",
             followup["what_would_change"], "", "[Measurements and provenance](pixel_followup.json).", ""]
    for item in followup["figures"]:
        source = REPO / item["path"]
        if item["path"] not in followup["source_sha256"]:
            raise ValueError(f"{key}: pixel follow-up figure lacks provenance")
        shutil.copy2(source, out / source.name)
        lines += [f"![{item['caption']}]({source.name})", "", item["caption"], ""]
    return lines


def build_packet(root, job, fit, arrays, extra):
    """An audit packet carries the measurements even when the candidate is killed."""
    import audit_p5 as A
    key = job["key"]
    out = REPO / "docs/packets" / f"audit_{root.name}" / key
    out.mkdir(parents=True, exist_ok=True)
    records = {folder: read(root / folder / f"{key}.json")
               for folder in ("stageA", "secondary", "stageB", "stageC", "stageD")}
    nb = read(root / "neighbours" / f"tic{job['tic_id']}.json")
    for name, data in {**records, "fit": fit, "expensive": extra, "neighbours": nb, "ranking": job}.items():
        write(out / f"{name}.json", data)
    d = records["stageD"]
    verdict = d.get("verdict") or d.get("provisional_verdict") or "HOLD"
    reason = d.get("reason") if d.get("verdict") else d.get("provisional_reason")
    previous_fields = out / "ctoi_fields.json"
    prior_note = (read(previous_fields).get("form_fields") or {}).get("notes", "") if previous_fields.exists() else ""
    note = prior_note if d.get("verdict") and prior_note and not prior_note.startswith("Review draft:") else (
        f"Review draft: {verdict}. {reason}. Submit only after the final audit verdict is SUBMIT.")
    fields = A.write_ctoi_fields(job["tic_id"], job["period"], note)
    data = read(fields)
    data["review_status"] = {"verdict": verdict, "final_verdict_stamped": bool(d.get("verdict")),
                              "reason": reason, "external_submission_performed": False}
    if d.get("tiers"):
        # [P10] F1-F9 and the tier record travel with the candidate; F9 is the validation status.
        t = d["tiers"]
        data["tiers"] = {"rules_version": t.get("rules_version"), "verdict": t.get("verdict"),
                         "deciding_condition": t.get("deciding_condition"), "deciding_detail": t.get("deciding_detail"),
                         "not_measurable": t.get("not_measurable"),
                         "conditions": {k: {kk: vv for kk, vv in v.items() if kk in ("fired", "measurable", "detail")}
                                        for k, v in (t.get("conditions") or {}).items()}}
        data["flags"] = t.get("flags")
        data["validation_status"] = (t.get("flags") or {}).get("F9")
    write(fields, data)
    figure(out / "summary.png", job, fit, arrays, records, extra)
    a, fp, cen = fit["adopted"], extra.get("fpp") or {}, extra.get("centroid") or {}
    lines = [f"# TIC {job['tic_id']} — P8 candidate review", "",
             f"**{verdict}** ({'final' if d.get('verdict') else 'provisional'}): {reason}", "",
             "This is a candidate audit. No external submission has been made.", "",
             f"V2 rank {job.get('rank_v2')}; score {job['score_v2']}. Rank does not determine the verdict.", "",
             "![Audit diagnostics](summary.png)", "", "| Measurement | Value |", "|---|---|",
             f"| Period | {a['period']:.9f} ± {a.get('period_err')} d |",
             f"| Epoch | {a['epoch_bjd']:.9f} ± {a.get('t0_err')} BJD |",
             f"| Radius | {a['rp_rearth']} ± {a.get('rp_rearth_err')} Earth radii |",
             f"| T14 | {a['t14_hours']} ± {a.get('t14_err_hours')} h |",
             f"| Impact parameter | {a['b']:.5f} ± {a.get('b_err')} |",
             f"| Density prior / grazing | {fit['density_prior_adopted']} / {a['grazing']} |",
             f"| Transits / beta | {a['n_transits']} / {fit['data']['beta_red_noise']} |",
             f"| FPP / NFPP | {fp.get('fpp')} / {fp.get('nfpp')} |",
             f"| fpp_uniform | {extra.get('fpp_uniform')} |",
             f"| Centroid | {cen.get('note') or cen.get('error')} |", "",
             f"Gaia: {nb.get('summary')}", "", extra["gaia_usage"], "",
             f"FPP: {fp.get('note') or fp.get('error')}", "",
             "[Form fields](ctoi_fields.json), [physical fit](fit.json), [pixel and FPP record](expensive.json), "
             "[cached neighbours](neighbours.json). Stage A, secondary, B, C and D records are alongside these files.", "",
             "Completeness and population assumptions: [P8 completeness](../../../COMPLETENESS_P8.md) and "
             "[population](../../../POPULATION_P8.md). The calibration ends after A and the secondary gate; "
             "no calibrated B/C/D efficiency is claimed.", ""]
    lines += pixel_followup_lines(root, key, out)
    lines += tier_lines(d)
    (out / "packet.md").write_text("\n".join(lines), encoding="utf-8")


def tier_lines(stage_d: dict) -> list[str]:
    """[P10] The tier record and F1-F9 in the packet, when the candidate was evaluated under p10.0."""
    t = stage_d.get("tiers")
    if not t:
        return []
    from tesshunter.verdict_tiers import CONDITION_NAMES, F_ORDER, H_ORDER, K_ORDER
    c = t.get("conditions") or {}
    lines = ["## p10.0 verdict tiers", "",
             f"**{t.get('verdict')}** on {t.get('deciding_condition') or 'no condition'}: {t.get('deciding_detail') or 'every measured condition passes'}", "",
             "| Condition | Fired | Detail |", "|---|---|---|"]
    for n in K_ORDER + H_ORDER:
        v = c.get(n) or {}
        f = v.get("fired")
        lines.append(f"| {n}: {CONDITION_NAMES.get(n, '')} | {'not measurable' if f is None else ('yes' if f else 'no')} | {str(v.get('detail', ''))[:220]} |")
    flags = t.get("flags") or {}
    lines += ["", "### Flags F1-F9", ""]
    names = {"F1": "neighbours able to make the depth (63 arcsec)", "F2": "Gaia target flags", "F3": "VSX / SIMBAD within 1 arcmin",
             "F4": "FPP / NFPP", "F5": "pixel localisation", "F6": "other accepted signals on the host",
             "F7": "TCE / TOI / CTOI association", "F8": "artefact-class census of the events", "F9": "validation_status"}
    for n in F_ORDER:
        v = flags.get(n)
        text = v if isinstance(v, str) else json.dumps(v, default=str)
        lines.append(f"- **{n}** ({names[n]}): {text[:900]}")
    lines.append("")
    return lines


def figure(path, job, fit, arrays, records, extra):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tesshunter.survey import transit_model
    t, f = arrays["time_unbinned"], arrays["flux_unbinned"]
    a = fit["adopted"]
    p, t0, dur = a["period"], a["t0_btjd"], a["t14_hours"] / 24
    phase = (t - t0 + p / 2) % p - p / 2
    fig, axes = plt.subplots(3, 2, figsize=(13, 12), constrained_layout=True)
    stride = max(1, len(t) // 16000)
    axes[0, 0].scatter(t[::stride], 1000 * (f[::stride] - 1), s=1, alpha=.5)
    axes[0, 0].set(xlabel="Time (BTJD)", ylabel="Relative flux (ppt)", title="Prepared native-cadence series")
    near = abs(phase) < 2 * dur
    axes[0, 1].scatter(phase[near] * 24, 1000 * (f[near] - 1), s=2, alpha=.12)
    grid = np.linspace(-2 * dur, 2 * dur, 700)
    ld = fit["limb_darkening"]
    model = transit_model(grid, period=p, t0=0, rp_rs=a["rp_rs"], b=a["b"], a_rs=a["a_rs"],
                          u=(ld["u1"], ld["u2"]), exp_time_days=200 / 86400)
    axes[0, 1].plot(grid * 24, 1000 * (model - 1), color="crimson", lw=2)
    axes[0, 1].set(xlabel="Time from transit (h)", ylabel="Relative flux (ppt)", title="All-transit physical fit")
    events = records["stageA"]["per_ephemeris"][records["stageA"]["chosen_ephemeris"]]["events"]
    for excluded, label, color in [(False, "Kept", "tab:blue"), (True, "Removed", "tab:orange")]:
        es = [e for e in events if e.get("observed") and bool(e.get("excluded")) == excluded
              and e.get("det_depth_ppt") is not None and e.get("det_depth_err_ppt") is not None]
        axes[1, 0].errorbar([e["tc_btjd"] for e in es], [e["det_depth_ppt"] for e in es],
                          yerr=[e["det_depth_err_ppt"] for e in es], fmt=".", ms=4, alpha=.7, label=label, color=color)
    axes[1, 0].legend()
    axes[1, 0].set(xlabel="Event time (BTJD)", ylabel="Depth (ppt)", title="Stage A event measurements")
    cycle = np.round((t - t0) / p).astype(int)
    edges = np.linspace(-2 * dur, 2 * dur, 65)
    for parity, label in [(0, "Even"), (1, "Odd")]:
        m = near & (cycle % 2 == parity)
        counts, _ = np.histogram(phase[m], bins=edges)
        sums, _ = np.histogram(phase[m], bins=edges, weights=1000 * (f[m] - 1))
        good = counts > 0
        axes[1, 1].plot((edges[:-1] + edges[1:])[good] * 12, sums[good] / counts[good], ".-", ms=3, label=label)
    axes[1, 1].legend()
    axes[1, 1].set(xlabel="Time from transit (h)", ylabel="Mean flux (ppt)", title="Odd/even diagnostic (display bins)")
    sec = records["secondary"]["secondary"]
    dips = ([sec["primary"]] if sec.get("primary") else []) + (sec.get("secondaries") or [])
    axes[2, 0].scatter([d["phase"] for d in dips], [d["depth_ppt"] for d in dips], s=25)
    axes[2, 0].set(xlabel="Orbital phase", ylabel="Scan depth (ppt)", title=f"Full-phase secondary gate: {records['secondary']['gate']}", xlim=(-.03, 1.03))
    cen = extra.get("centroid") or {}
    cs = [c for c in cen.get("per_sector", []) if c.get("available") and c.get("shift_err_px")]
    if cs:
        axes[2, 1].errorbar([c["sector"] for c in cs], [c["total_shift_px"] for c in cs],
                          yerr=[c["shift_err_px"] for c in cs], fmt="o", ms=4)
    else:
        axes[2, 1].text(.5, .5, "Centroid unavailable; see record", transform=axes[2, 1].transAxes, ha="center")
    axes[2, 1].set(xlabel="TESS sector", ylabel="Centroid shift (pixels)", title="TESScut centroid by sector")
    fig.suptitle(f"TIC {job['tic_id']} | P = {p:.7f} d | frozen p8.0", fontsize=16)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def stop_child_tree(proc):
    """A Windows venv launcher has a child interpreter; stop both on timeout."""
    if os.name == "nt":
        script = (
            "$p8ProcessSnapshot = @(Get-CimInstance Win32_Process); "
            "function Stop-P8PacketTree([int]$p8ProcessId) { "
            "$p8ProcessSnapshot | Where-Object { $_.ParentProcessId -eq $p8ProcessId } | "
            "ForEach-Object { Stop-P8PacketTree ([int]$_.ProcessId) }; "
            "Stop-Process -Id $p8ProcessId -Force -ErrorAction SilentlyContinue }; "
            f"$p8PacketParent = $p8ProcessSnapshot | Where-Object {{ $_.ProcessId -eq {int(proc.pid)} }}; "
            "if ($p8PacketParent.CommandLine -like '*p8_stage_d_packets.py*') { "
            f"Stop-P8PacketTree {int(proc.pid)} }}"
        )
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, timeout=30, check=True)
    else:
        import signal
        os.killpg(proc.pid, signal.SIGKILL)
    proc.wait(timeout=30)


def run_all(root, workers, timeout, n_draws, force=False):
    jobs = rank_candidates(root)
    disk = {"free_gib_before_pixel_downloads": round(shutil.disk_usage(REPO).free / 2**30, 2),
            "n_candidates": len(jobs), "workers": workers}
    write(root / "expensive_launch_p8.json", disk)
    print(json.dumps(disk), flush=True)
    logs = root / "logs/expensive"
    logs.mkdir(parents=True, exist_ok=True)
    def run(job):
        job_path = logs / f"{job['key']}.job.json"
        write(job_path, job)
        for attempt in (1, 2):
            with (logs / f"{job['key']}.attempt{attempt}.log").open("w", encoding="utf-8") as log:
                cmd = [sys.executable, "-u", str(Path(__file__).resolve()), "--root", str(root), "--one", str(job_path),
                       "--n-draws", str(n_draws)] + (["--force"] if force and attempt == 1 else [])
                try:
                    proc = subprocess.Popen(cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                                            start_new_session=os.name != "nt")
                    code = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    stop_child_tree(proc)
                    code = "timeout"
            result = root / "expensive" / f"{job['key']}.json"
            status = read(result).get("status") if result.exists() else "missing"
            print(job["key"], "attempt", attempt, "exit", code, "status", status, flush=True)
            if code == 0 and status == "complete":
                return job["key"], status
        return job["key"], status
    with ThreadPoolExecutor(max_workers=workers) as pool:
        states = dict(f.result() for f in as_completed([pool.submit(run, j) for j in jobs]))
    write(root / "expensive_summary_p8.json", {"rules_version": "p8.0", "states": states, "n_candidates": len(jobs)})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--rank-only", action="store_true")
    ap.add_argument("--one", type=Path)
    ap.add_argument("--workers", type=int, default=4, choices=range(1, 5))
    ap.add_argument("--timeout", type=float, default=5400)
    ap.add_argument("--n-draws", type=int, default=100_000)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--rules", default="p8.0", choices=["p8.0", "p10.0"],
                    help="p8.0 reproduces the P8 packets; p10.0 adds the tier evaluation and F1-F9")
    args = ap.parse_args()
    global RULES_NAME
    RULES_NAME = args.rules
    os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data/cache/lightkurve"))
    os.environ["PYTHONIOENCODING"] = "utf-8"
    for name in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ[name] = "1"
    root = args.root.resolve()
    if args.rank_only:
        print(json.dumps(rank_candidates(root), indent=1))
    elif args.one:
        rec = measure_one(root, read(args.one), args.n_draws, args.force)
        print(json.dumps({"key": rec["key"], "status": rec["status"]}))
        return 0 if rec["status"] == "complete" else 1
    else:
        run_all(root, args.workers, args.timeout, args.n_draws, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
