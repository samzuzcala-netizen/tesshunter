"""S1 search worker: ``k1/protocol/search_worker_k1.py`` unchanged (frozen preset survey_k1, 8,100-s budget from the
runtime, traces on), run with ``K1_DATA`` = the S1 root.  Operational swap (no effect on any decision): K1's STOP-E
refusal of the frozen survey list (a preparation-time blindness guard) is lifted, since S1 is that survey; the
converse guard applies: a star that is not on ``s1/survey/targets_s1.csv`` is refused.

The modules are imported in the order search_worker_k1 -> download_k1, exactly as search_worker_k1.main imports them,
so the worker's process environment (download_k1's module-level ``environment()`` runs after the worker's
``environment(offline=True)``) is the frozen worker's.
CLI: ``search_s1.py <runtime.json>``.
"""
import sys

from s1_common import assert_worker_root, survey_tics, read

assert_worker_root()
import search_worker_k1 as W  # noqa: E402
import download_k1  # noqa: E402

download_k1.survey_tics = lambda: set()


def main(runtime_path: str) -> int:
    if int(read(runtime_path)["tic_id"]) not in survey_tics():
        raise RuntimeError("S1: star not on the S1 survey list")
    return W.main(runtime_path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
