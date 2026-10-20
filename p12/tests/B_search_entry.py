"""Fixture-only blind worker entry; all output roots belong to pytest temp storage."""
from pathlib import Path
import sys
repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo/'p12/protocol'))
import blind_search_worker_p12 as worker
worker.ROOT=Path(sys.argv[1])/'p12'
worker.DATA=Path(sys.argv[1])/'data/survey/p12'
worker.main(sys.argv[2],sys.argv[3])
