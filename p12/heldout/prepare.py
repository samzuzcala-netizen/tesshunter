"""Separate, truth-bearing preparation process. Never imported by runner.py.

P12 held-out copy of ``p9/prepare.py`` (4c). ``p9/`` is never written, so P9's truth-side steps
(``fetch``, ``inventory``, ``frame``) are not carried; the harness's preparation is:
  snapshot   edit (1): ``git archive HEAD src scripts`` into ``p12/heldout/baseline/source`` and the hashes of
             the snapshot plus the P12 overlay into ``p12/manifests/heldout_source_seal.json``
  hosts      ``p12/manifests/heldout_hosts.json``: the 25 hosts of 4c (from the prompt's list, split ``holdout``
             of ``p9/truth/final_truth.csv`` per ``HANDOFF_P10.md`` 0.0 and 2.2; this step reads no truth file),
             each host's route, and the exposing document of every excluded host
  selection  edit (6): the per-host input selection, ``p12/heldout/manifests/input_selection.json``, and the
             stellar execution table ``p12/heldout/manifests/heldout_execution.csv`` (from
             ``p9/manifests/final_execution.csv``, not a truth file)
  arrays     the prepared native arrays of every host (``runner.prepare``), before the search
"""
from common import *
import argparse, csv, io, shutil, subprocess, tarfile

POSITIVES = [239275865, 122063843, 298074836, 164778883, 158983792, 120315006, 48448415, 122673489, 164832454,
             399955825, 298837729, 120254625]
NEGATIVES = [149473467, 151826930, 379783522, 287669537, 349059354, 269238622, 279462605, 172421004, 80025900,
             265489698, 229804573, 207174531, 157568289]
EXCLUDED = {
    33153766: dict(reason='P9 development negative', exposing_document='HANDOFF_P10.md (rule 8 development material, line 1251)'),
    167009792: dict(reason='P9 development negative', exposing_document='HANDOFF_P10.md (rule 8 development material, line 1251)'),
    41422753: dict(reason='re-scored in P10 (TOI-5855.01, tic41422753_P2.4708)',
                   exposing_document='HANDOFF_P10.md section 2.2 and lines 750 and 1467; p9/docs/packets/audit_tic41422753/'),
}
OVERLAY_FILES = ('p10/protocol/p10_funnel_calibration.py', 'p12/protocol/rules_p12.py', 'p12/protocol/p12_common.py',
                 'p12/protocol/stage_d_worker_p12.py', 'p12/protocol/stage_d_packets_p12.py', 'p12/protocol/stage_d_pixels_p12.py',
                 'p12/protocol/blind_io_p12.py', 'p12/protocol/blind_search_worker_p12.py', 'p12/protocol/config.json',
                 'p12/results/part1/k10_calibration.json')
HARNESS_FILES = ('common.py', 'runner.py', 'dispatch.py', 'prepare.py', 'scoring.py', 'metrics.py', 'p9_scoring_adapter.py')

def snapshot():
    if BASE.exists():raise FileExistsError(BASE)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    archive=subprocess.check_output(['git','archive','--format=tar',head,'src','scripts'],cwd=REPO)
    BASE.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(BASE,filter='data')
    files={p.relative_to(REPO).as_posix():sha(p) for p in sorted(BASE.rglob('*')) if p.is_file()}
    overlay={name:sha(REPO/name) for name in OVERLAY_FILES}
    harness={f'p12/heldout/{name}':sha(H/name) for name in HARNESS_FILES}
    seal=dict(utc=utc(),git_head=head,snapshot='git archive HEAD src scripts',n_snapshot=len(files),
        files={**files,**overlay,**harness},overlay=sorted(overlay),harness=sorted(harness))
    write(REPO/'p12/manifests/heldout_source_seal.json',seal)
    print('baseline frozen',len(files),'snapshot files,',len(overlay),'overlay,',len(harness),'harness',flush=True)

def hosts_manifest():
    out=REPO/'p12/manifests/heldout_hosts.json'
    if out.exists():raise FileExistsError(out)
    route={**{str(t):'normal' for t in POSITIVES},**{str(t):'negatives' for t in NEGATIVES}}
    write(out,dict(utc=utc(),source='PROMPT_P12.md 4c; split holdout of p9/truth/final_truth.csv (HANDOFF_P10.md 0.0 and 2.2); no truth file read here',
        positives=POSITIVES,n_positive_signals=13,negatives=NEGATIVES,route=route,
        excluded={str(k):v for k,v in EXCLUDED.items()},
        domain='2-minute SPOC hosts outside the P12 domain; they keep the P9 inputs even if Part 2 adopted the small aperture',
        exposure='pre-D outcomes seen by P9 and P10 (disclosed); unexposed to every P12 rule decision'))
    print('hosts',len(POSITIVES),'positive,',len(NEGATIVES),'negative,',len(EXCLUDED),'excluded',flush=True)

def selection():
    ids=sorted(POSITIVES+NEGATIVES)
    rows={int(r['tic_id']):r for r in csv.DictReader((P9/'manifests/final_execution.csv').open(encoding='utf-8'))}
    missing=[t for t in ids if t not in rows]
    if missing:raise RuntimeError(f'Hosts absent from the P9 execution table: {missing}')
    table=H/'manifests/heldout_execution.csv';table.parent.mkdir(parents=True,exist_ok=True)
    with table.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[ids[0]].keys()),lineterminator='\n');w.writeheader()
        for t in ids:w.writerow(rows[t])
    chosen={str(t):select_products(t) for t in ids}
    write(H/'manifests/input_selection.json',dict(utc=utc(),hosts=chosen,execution_table=table.relative_to(REPO).as_posix(),
        execution_table_sha256=sha(table),rule='sectors 56 to 105 of the frozen policy, excluded QLP sectors dropped, SPOC > TESS-SPOC > QLP per sector'))
    print('selection',len(ids),'hosts;',sum(len(c['selected']) for c in chosen.values()),'products selected,',
          sum(len(c['dropped']) for c in chosen.values()),'dropped',flush=True)

def arrays():
    from runner import prepare
    for t in sorted(POSITIVES+NEGATIVES):
        if not (H/'results/prepared'/f'tic{t}.json').exists():
            r=prepare(t);print('prepared',t,len(r['usable_sectors']),'sectors',r['n_cad'],'cadences',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=['snapshot','hosts','selection','arrays','all']);a=p.parse_args()
    if a.cmd=='all':
        hosts_manifest();selection();snapshot();arrays()
    else:{'snapshot':snapshot,'hosts':hosts_manifest,'selection':selection,'arrays':arrays}[a.cmd]()
