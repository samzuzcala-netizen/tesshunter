"""Copy a final evidence bundle to an explicitly selected deliverables directory.

No deletion, scientific mutation, or new external transfer is performed.
"""
from common import *
import argparse, shutil


def main(destination):
    destination=destination.resolve()
    if destination==REPO or destination.is_relative_to(P9) or P9.is_relative_to(destination):
        raise ValueError('The deliverable must be outside the experiment tree and its ancestors')
    if destination.exists() and any(destination.iterdir()):
        raise RuntimeError('Use a new empty destination to avoid overwriting an existing deliverable')
    verification=read(P9/'results/verification.json')
    if verification['status']!='PASS' or verification['pending_hosts']:raise RuntimeError('Final verification required')
    if read(P9/'work/dispatcher.json').get('status')!='complete':raise RuntimeError('Execution is still running')
    destination.mkdir(parents=True,exist_ok=True)
    copied=[];omitted=[]
    for src in P9.rglob('*'):
        if not src.is_file():continue
        rel=src.relative_to(REPO);parts=src.relative_to(P9).parts
        if parts[0]=='work' or '__pycache__' in parts or '.pytest_cache' in parts or src.suffix in ('.pyc','.nbc','.nbi'):
            omitted.append(dict(path=rel.as_posix(),bytes=src.stat().st_size));continue
        dst=destination/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);copied.append(rel.as_posix())
    extras=['docs/AUDIT_P9.md','HANDOFF_P9.md','docs/AUDIT_P8.md','docs/COMPLETENESS_P8.md','docs/POPULATION_P8.md',
      'HANDOFF_P8.md','PROMPT_P8.md','data/survey/p8/expected_yield_p8.json']
    for rel in extras:
        src=REPO/rel;dst=destination/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);copied.append(rel)
    overview='''# P9 completed investigation

Start with [the scientific audit](docs/AUDIT_P9.md), [the full tables](p9/TABLES.md),
and [the handoff](HANDOFF_P9.md). [Every positive-control autopsy](p9/AUTOPSIES.md)
and all locked candidate evidence are included.

This bundle includes frozen raw light-curve products, stellar/sky/truth inputs,
source/configuration snapshots, complete locked blind outputs, numerical arrays,
figures, reviews, logs and analysis code. It preserves the original relative layout.
Intermediate execution/TESScut caches and Python compiler caches are omitted;
the full original repository P9 workspace retains them. Pixel source hashes and
measurements are included, but a full pixel recomputation needs those original
TESScut bytes or independently hash-verified downloads. No raw donor transplantation
or spatial-injection experiment is implied by this bundle.

Verify the delivered files before changing or recomputing them:

```powershell
python p9/verify_portable.py
```

`BUNDLE_MANIFEST.json` records every included file hash and omitted cache path/size.
The portable verifier also checks the exact blind-host file locks and disabled
actual-submission flags. The original full-workspace verification receipt is in
`p9/results/verification.json`; rerunning `p9/verify.py` requires the original Git
checkout, historical P8 injection files and target lists outside this bundle.

Use [the environment and recomputation instructions](p9/README.md) for the original
Windows runtime. The scoring/diagnostic tables can be recomputed from the included
inputs and locked outputs; doing so changes timestamped derived receipts and will
intentionally invalidate the package's original-file hashes for those derived files.
Make a working copy first. Scientific operations with wall budgets and manual final
reviews are auditable, but a new run is not promised to be bit-identical.

All controls are known objects or independently categorized comparison signals.
There are no actual new-discovery submissions. Native inherited packet headings
and draft templates are historical software formatting, not discovery claims;
the authoritative P9 decisions are the separately locked `final/` JSON reviews.
'''
    (destination/'README.md').write_text(overview,encoding='utf-8');copied.append('README.md')
    files={rel:sha(destination/rel) for rel in sorted(copied)}
    write(destination/'BUNDLE_MANIFEST.json',dict(utc=utc(),type='P9 final portable evidence',
      source_workspace=str(REPO),package_script_sha256=sha(Path(__file__)),files_sha256=files,
      included_bytes=sum((destination/rel).stat().st_size for rel in copied),omitted_cache_files=omitted,
      limits='Original P8 injection results/target lists/Git metadata and large execution TESScut caches remain in the original workspace.'))
    print('Packaged',len(files),'files at',str(destination),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,required=True);a=p.parse_args();main(a.destination)
