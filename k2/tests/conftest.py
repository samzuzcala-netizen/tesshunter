"""K2 test settings: network-free, K2 and K1 protocol folders on the path (as k1/tests/conftest.py)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("TESSHUNTER_OFFLINE", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO / "src", _REPO / "scripts", _REPO / "k1" / "protocol", _REPO / "k2" / "protocol"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
