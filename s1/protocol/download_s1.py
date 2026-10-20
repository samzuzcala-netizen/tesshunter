"""S1 acquisition worker: ``k1/protocol/download_k1.py`` unchanged (one search per star, usable products only,
QLP 74-79 v02, FITS identity checks, bounded MAST calls, a fresh per-attempt FITS cache), run with ``K1_DATA`` = the
S1 root so the store is ``D:/tesshunter_s1/audit_lc``.  Operational swaps (no effect on any decision):

* the exposure-ledger row goes to ``s1/manifests/exposure_ledger_s1.csv`` under an exclusive lock
  (``s1_common.ledger``);
* K1's STOP-E refusal of the frozen survey list (a preparation-time blindness guard) is lifted, since S1 is that
  survey; the converse guard applies: a star that is not on ``s1/survey/targets_s1.csv`` is refused.

CLI: as download_k1.py (``download_s1.py <tic> <attempt> <use> --receipt <path>``).
"""
import sys

from s1_common import assert_worker_root, ledger, survey_tics

assert_worker_root()
import download_k1 as D  # noqa: E402

D.ledger = ledger
D.survey_tics = lambda: set()
_LIST = survey_tics()
_download_star = D.download_star


def download_star(tic, attempt, use, store=D.STORE):
    if int(tic) not in _LIST:
        raise RuntimeError(f"S1: TIC {tic} is not on the S1 survey list")
    return _download_star(tic, attempt, use, store)


D.download_star = download_star

if __name__ == "__main__":
    raise SystemExit(D.main(sys.argv[1:]))
