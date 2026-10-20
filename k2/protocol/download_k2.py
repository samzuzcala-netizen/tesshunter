"""K2 acquisition worker: ``k1/protocol/download_k1.py`` unchanged (usable products only, amendment 1, FITS
identity checks, STOP-E refusal of survey-list stars), run with ``K1_DATA`` = the K2 root so the store is
``D:/tesshunter_k2/audit_lc``; the exposure-ledger row goes to ``k2/manifests/exposure_ledger_k2.csv``.
CLI: as download_k1.py.
"""
import sys

from k2_common import assert_worker_root, ledger

assert_worker_root()
import download_k1 as D  # noqa: E402

D.ledger = ledger

if __name__ == "__main__":
    raise SystemExit(D.main(sys.argv[1:]))
