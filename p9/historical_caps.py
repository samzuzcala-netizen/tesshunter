"""Read-only audit of the existing P8 B ceilings and final dispositions.

This explains the recorded P8 decision path, without assigning planet truth to
P8 candidates or changing any historical verdict.
"""
from common import *
import collections,shutil


def run():
    source=REPO/'data/survey/p8';snapshot=P9/'calibration/historical_caps_source'
    rows=[];hashes={}
    for bp in sorted((source/'stageB').glob('*.json')):
        b=read(bp);cp=source/'stageC'/bp.name;dp=source/'stageD'/bp.name
        c=read(cp) if cp.exists() else {};d=read(dp) if dp.exists() else {}
        row=dict(key=b['key'],B_decision=b.get('decision'),B_max_verdict=b.get('max_verdict'),
          B_flags=b.get('flags'),C_decision=c.get('decision'),D_provisional=d.get('provisional_verdict'),
          D_provisional_reason=d.get('provisional_reason'),D_verdict=d.get('verdict'),D_reason=d.get('reason'))
        for p in [bp,cp,dp]:
            if not p.exists():continue
            rel=p.relative_to(source);dst=snapshot/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            if dst.exists() and sha(dst)!=sha(p):raise RuntimeError('Historical source or saved copy changed: '+str(p))
            if not dst.exists():shutil.copy2(p,dst)
            hashes[str(p.relative_to(REPO))]=sha(p)
        rows.append(row)
    passed=[r for r in rows if r['C_decision']=='PASS']
    out=dict(utc=utc(),script_sha256=sha(Path(__file__)),n_B=len(rows),
      n_B_capped_HOLD=sum(r['B_max_verdict']=='HOLD' for r in rows),n_C_pass=len(passed),
      n_C_pass_with_B_HOLD=sum(r['B_max_verdict']=='HOLD' for r in passed),
      C_pass_final_verdicts=dict(collections.Counter(r['D_verdict'] for r in passed)),
      rows=rows,source_sha256=hashes,snapshot=str(snapshot.relative_to(P9)),
      interpretation='Recorded decision ceilings, not truth labels or a measured counterfactual gate benefit. P8 D contrary evidence and historical verdicts remain unchanged.')
    write(P9/'results/historical_B_caps.json',out)
    print('Historical P8:',out['n_B_capped_HOLD'],'of',len(rows),'B caps;',out['n_C_pass_with_B_HOLD'],'of',len(passed),'C survivors capped',flush=True)


if __name__=='__main__':run()
