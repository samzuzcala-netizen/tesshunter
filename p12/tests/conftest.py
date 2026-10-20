import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'protocol'))
os.environ['TESSHUNTER_OFFLINE'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
from p12_common import environment
environment()
