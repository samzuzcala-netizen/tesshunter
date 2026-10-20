"""Part 4c blind leg: lock every held-out host's blind records, then read truth and score (harness edit 7).

Runs ``p12/heldout/scoring.py`` (post-lock signal scoring with the adapter copy) and ``p12/heldout/metrics.py``
(``p12/results/part4/p9_negatives_table.json`` with LB2a and LB2b, and the blind rows of
``p12/results/part4/p9_positives_table.json``). The truth file is opened only after every host's lock.
"""
from p12_common import REPO, ROOT, read, sha, utc, append_jsonl
import json
import sys

HELDOUT = REPO / 'p12/heldout'


def main(argv):
    if str(HELDOUT) not in sys.path:
        sys.path.insert(0, str(HELDOUT))
    import scoring
    import metrics
    append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=None, stage='Part 4c blind leg scoring',
        path='p9/truth/final_truth.csv', reader='report_p9_blind_p12.py (heldout scoring.run)', prompt_of_origin='P9 (held-out truth)',
        content='holdout truth rows of the 25 registered hosts, read after every host lock'))
    scoring.run()
    metrics.run()
    table = read(ROOT / 'results/part4/p9_negatives_table.json')
    print(json.dumps(dict(LB2a=table['LB2a']['number'], N=table['LB2a']['N'], LB2b=table['LB2b']['number'], N2_D=table['LB2b']['N'])), flush=True)
    return 0
