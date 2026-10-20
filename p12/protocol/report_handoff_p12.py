"""Part 6d: ``HANDOFF_P12.md``, the final handoff (the per-part sections written before each commit stay below it).

Line 1: the final state (provisional here; ``reports_p12.py audit finalize`` rewrites it after shutdown). Then:
what shipped, what was measured (sample sizes, unknowns), what was refuted, what is open; the three decision
points and the user's choices; entry and exit environment numbers; the exposure-ledger summary; assumptions.
The "resume here" line is removed. Every statement is tagged [M], [A] or [I].
"""
from p12_common import REPO, ROOT, read, sha, utc
import json
import shutil

HANDOFF = REPO / 'HANDOFF_P12.md'


def _load(rel):
    path = REPO / rel
    return read(path) if path.exists() else None


def build():
    import report_audit_p12 as audit
    c = audit.conditions()
    state = audit.state(c)
    bar = _load('p12/results/part4/launch_bar.json') or {}
    summary = _load('p12/results/candidates_p12_summary.json') or {}
    decision = _load('p12/results/part2/photometry_decision.json') or {}
    k10 = _load('p12/results/part1/k10_calibration.json') or {}
    plumbing = _load('p12/results/part1/plumbing_d.json') or {}
    ledger = _load('p12/manifests/resource_ledger.json') or {}
    closing = (_load('p12/results/closing_sentence.json') or {}).get('sentence')
    dp1 = _load('p12/manifests/decision_point_1.json') or {}
    stops = c.get('stop_receipts') or []
    rows = [line for line in (REPO / 'p12/manifests/exposure_ledger.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    readers = {}
    for line in rows:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        readers[r.get('reader', 'unknown')] = readers.get(r.get('reader', 'unknown'), 0) + 1
    entry = _load('p12/logs/entry_preflight.json') or {}
    free = shutil.disk_usage(REPO)
    d_free = shutil.disk_usage('D:\\')
    lines = [f'# HANDOFF_P12. Final state: {state} (provisional until the final integrity check and shutdown)', '',
             f'Written {utc()} by `p12/protocol/report_handoff_p12.py`.', '',
             '## What shipped [M]', '',
             f"- The candidate list `p12/results/candidates_p12.csv`: {json.dumps(summary.get('by_verdict', {}))}.",
             f"- The launch bar `p12/results/part4/launch_bar.json`: bar_met = {bar.get('bar_met')}; failing {bar.get('failing')}; "
             f"not decisive {bar.get('not_decisive')}.",
             '- `p12/results/COMPLETENESS_P12.md`, `p12/results/SPECIFICITY_P12.md`, `docs/AUDIT_P12.md`, the packets under '
             '`docs/packets/audit_p12/`, the seals and the cost ledger.', '',
             '## What was measured [M]', '',
             f"- Photometry decision: {decision.get('decision')} ({decision.get('reason', '')}).",
             f"- K10: {k10.get('word')}.",
             f"- Plumbing: {plumbing.get('status')} with {len(plumbing.get('expectation_updates') or [])} registered live-measurement update(s).",
             f"- Queue-hours, all parts: {ledger.get('new_queue_hours')}.", '',
             '## What was refuted or not measured [M]', '',
             f"- Launch-bar clauses not decisive: {bar.get('not_decisive')} (a clause that is not decisive never counts as a pass).",
             f"- Stop receipts: {stops or 'none'}.", '',
             '## What is open [A]', '', f"- {closing}", '',
             '## The three decision points [M]', '',
             f"1. Launch approval after Part 0: the user chose tier {dp1.get('tier')} ({dp1.get('approved_utc')}).",
             '2. Stop rules: STOP-6 on plumbing_d (a pricing defect, 2026-09-23); the user wrote "continue" and the phase resumed '
             f"after its fix (AMENDMENTS_P12.md). Other stops: {stops}.",
             '3. Final delivery: pending the user (the next message).', '',
             '## Environment [M]', '',
             f"- Entry: {json.dumps({k: v for k, v in entry.items() if isinstance(v, (int, float, str)) and 'free' in k.lower()})}.",
             f"- Exit: C: free {free.free / 1e9:.1f} GB; D: free {d_free.free / 1e9:.1f} GB.", '',
             '## Exposure ledger [M]', '', f"{len(rows)} rows; by reader: {json.dumps(readers)}.", '',
             '## Assumptions [A]', '', 'The assumptions of PROMPT_P12.md section 9; each measured one is reported in COMPLETENESS_P12.md.', '',
             '---', '']
    previous = HANDOFF.read_text(encoding='utf-8').splitlines() if HANDOFF.exists() else []
    previous = [l for l in previous if not l.lower().startswith('resume here')]
    HANDOFF.write_text('\n'.join(lines + previous) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(state=state, ledger_rows=len(rows))), flush=True)
    return state


def main(argv):
    build()
    return 0
