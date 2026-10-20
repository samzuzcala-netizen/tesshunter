"""Coordinate permitted S/B/C/D work while the fixed A batch completes.

P12 held-out copy of ``p9/dispatch.py`` (4c edit 8): ``batch`` and this dispatcher are replaced by
``runner.py plan --stage <X> --route <R>`` so that the P12 controller owns every job. The copy is kept
for the record and refuses to run.
"""
from common import *

LIMITS={'S':4,'B':4,'C':2,'D':2}

def main():
    raise SystemExit('The P12 controller owns every held-out job: use runner.py plan and controller_p12.py (4c edit 8)')

if __name__=='__main__':main()
