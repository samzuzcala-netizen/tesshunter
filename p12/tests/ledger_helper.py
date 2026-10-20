"""Tests that read seen historical records ledger each (reader, path) once."""
import json
from p12_common import ROOT, append_jsonl, utc

_SEEN = None


def ledger_once(star, stage, path, reader, origin):
    global _SEEN
    ledger = ROOT / 'manifests/exposure_ledger.jsonl'
    if _SEEN is None:
        _SEEN = set()
        if ledger.exists():
            for line in ledger.read_text(encoding='utf-8').splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                _SEEN.add((row.get('reader'), row.get('path')))
    if (reader, path) in _SEEN:
        return
    _SEEN.add((reader, path))
    append_jsonl(ledger, dict(utc=utc(), star=star, stage=stage, path=path, reader=reader, prompt_of_origin=origin,
                              content='read by a P12 test script; nothing displayed'))
