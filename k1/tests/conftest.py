"""Test-suite wide settings.

The suite is network-free by construction: synthetic light curves, monkey-
patched downloads. Prompt 3 added a cached TIC lookup to ``search_target``
(stellar parameters for the transit fit); ``TESSHUNTER_OFFLINE=1`` makes
that lookup serve the cache only, so a synthetic target id never reaches
MAST from a test.
"""

import os

os.environ.setdefault("TESSHUNTER_OFFLINE", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import sys
from pathlib import Path
_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO / "src", _REPO / "scripts", _REPO / "k1" / "protocol"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
