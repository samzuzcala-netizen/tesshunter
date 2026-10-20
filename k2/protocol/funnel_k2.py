"""K2 A / S / B / C worker for one candidate: ``k1/protocol/funnel_k1.py`` plus the K2 options.

Runtime = a funnel_k1 runtime plus
* ``k2_c_variant``: the C1 variant of Stage C (``K1`` = K1's Stage C; ``c_input_k2.VARIANTS``);
* ``k2_siblings``: the M1 sibling ephemerides (period, t0, t14, candidate_id, stitch_snr) masked before the
  blind TLS (empty = no M1);
* ``k2_a1_scope``: the A1 scope the Stage A gate reads (None = K1's Stage A);
* ``k2_copy_from``: a K1 case root copied (without its Stage C/D outputs) into ``root`` before the job, so the
  re-run reuses K1's prepared series and A/S/B records.
The frozen funnel code and funnel_k1.py are not edited; K2 behaviour is installed in-process.  Must run with
``K1_DATA`` = the K2 data root (the K2 controller sets it), so the receipt lands in
``D:/tesshunter_k2/funnel_receipts/<label>/<stage>/<cid>.json``.
CLI: ``funnel_k2.py <A|S|B|C> <runtime.json>``.
"""
from __future__ import annotations

import shutil
import sys
import time
import traceback
from pathlib import Path

from k2_common import K2_DATA, assert_worker_root, guard_truth, read, write, utc, safe

assert_worker_root()
import funnel_k1 as FK1  # noqa: E402  (k1_common.DATA = the K2 root here)
from k1_common import RECEIPTS  # noqa: E402
import c_input_k2 as CI  # noqa: E402

K2_FIELDS = {"k2_c_variant", "k2_siblings", "k2_a1_scope", "k2_copy_from"}
A1_SCOPES = (None, "author", "author_exposure")
COPY_SKIP_DIRS = {"stageC", "stageD", "fit", "pixels", "crossmatch"}


def copy_case_root(src: Path, dst: Path) -> dict:
    """K1 case root -> K2 case root without the Stage C/D outputs (RULES_K2 1.1)."""
    n = 0
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        if rel.parts[0] in COPY_SKIP_DIRS or rel.name.startswith("crossmatch"):
            continue
        if rel.parts[0] == "tls" and not (rel.name.endswith("_lc.npz") or rel.name.endswith("_forced.json")):
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        n += 1
    return {"copied_from": str(src), "files": n}


def main(stage, runtime_path):
    if stage not in ("A", "S", "B", "C"):
        raise ValueError("Unregistered stage")
    runtime_path = Path(runtime_path)
    rt = read(runtime_path)
    if set(rt) - (FK1.RUNTIME_FIELDS | K2_FIELDS):
        raise RuntimeError("Unregistered runtime fields")
    if rt["preset"] not in ("survey_k1", "survey_k1_s56"):
        raise RuntimeError("Unregistered preset")
    for k in rt["candidate"]:
        if k.startswith("inj") or k in ("truth", "injection"):
            raise RuntimeError("Truth field in runtime")
    variant = rt.get("k2_c_variant") or "K1"
    scope = rt.get("k2_a1_scope")
    if variant not in CI.VARIANTS or scope not in A1_SCOPES:
        raise RuntimeError("Unregistered K2 option")
    guard_truth(rt["lc_root"])
    root = Path(rt["root"])
    if not root.resolve().is_relative_to(K2_DATA.resolve()):
        raise RuntimeError("K2 case root outside the K2 data root")
    cid, tic, label = rt["candidate_id"], int(rt["tic_id"]), rt["label"]
    dest = RECEIPTS / label / stage / f"{cid}.json"
    if dest.exists():
        raise FileExistsError(dest)
    started, timer, cpu = utc(), time.perf_counter(), time.process_time()
    k2 = {"c_variant": variant, "a1_scope": scope}
    try:
        if rt.get("k2_copy_from") and not root.exists():
            k2["copy"] = copy_case_root(Path(rt["k2_copy_from"]), root)
        F, A, root = FK1.setup({k: v for k, v in rt.items() if k not in K2_FIELDS})
        from tesshunter import event_vet
        event_vet.DEPTH_CONSISTENCY_FAMILIES = scope
        if stage == "B":
            nb = rt.get("neighbours_path")
            if not nb or not Path(nb).exists():
                raise RuntimeError("neighbour record missing")
            target = root / "neighbours" / f"tic{tic}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            write(target, read(nb), replace=True)
        job = F.V.jobs()[0]
        if stage == "A":
            m = F.V.stagea_one(job, threads=1)
        elif stage == "S":
            m = F.secondary_one(job)
        elif stage == "B":
            m = F.V.stageb_one(job)
        else:
            info = CI.install(A, int(job["tic_id"]), float(job["period"]), variant, rt.get("k2_siblings") or [])
            k2["c_input"] = {k: v for k, v in info.items() if k != "siblings"}
            k2["siblings"] = info["siblings"]
            m = F.V.stagec_one(job, threads=int(rt.get("tls_threads") or 4), oversampling=int(info["oversampling"]))
        decision = m.get("decision", m.get("gate", m.get("status")))
        status = "OPERATIONAL_UNKNOWN" if decision in ("ERROR", "SKIP", "INPUT_ERROR", "TIMEOUT") else "COMPLETE"
        rec = dict(candidate_id=cid, tic_id=tic, stage=stage, status=status, decision=decision, label=label,
                   use=rt.get("use"), preset=rt["preset"], s_mode=rt.get("s_mode"), ramp_variant=bool(rt.get("ramp_variant")),
                   started_utc=started, completed_utc=utc(), wall_seconds=time.perf_counter() - timer,
                   cpu_seconds=time.process_time() - cpu, case_root=str(root), k2=k2, measurement=m)
        if stage == "S":
            sec = m.get("secondary") or {}
            rec["gate_by_mode"] = {"bound": (sec.get("gate_by_mode") or {}).get("bound"),
                                   **(sec.get("gate_by_mode_p10") or {}), **(sec.get("gate_by_mode_k1") or {})}
    except Exception as exc:
        rec = dict(candidate_id=cid, tic_id=tic, stage=stage, status="OPERATIONAL_UNKNOWN", label=label, k2=k2,
                   error=f"{type(exc).__name__}: {exc}"[:500], traceback=traceback.format_exc()[-3000:],
                   started_utc=started, completed_utc=utc(), wall_seconds=time.perf_counter() - timer)
    write(dest, safe(rec))
    print(stage, cid, rec["status"], rec.get("decision"), round(rec["wall_seconds"], 1), flush=True)
    return 0 if rec["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
