"""Explicit P10 catalogue extension; sealed legacy source and behavior unchanged.

Call install() to expose hard_stop_p10 and the opt-in ephemeris parser through
tesshunter.catalog_crossmatch. This is never imported by a blind search worker.
"""
from dataclasses import dataclass, field
import io
from pathlib import Path
import re
import sys
import numpy as np
import pandas as pd
from common import REPO, ROOT, environment

environment()
sys.path.insert(0, str(REPO / "src"))
from tesshunter import catalog_crossmatch as cx

EPHEMERIS_COLUMNS = ["tceid", "ticid", "tce_plnt_num", "sectors", "tce_period",
    "tce_period_err", "tce_time0bt", "tce_time0bt_err", "tce_duration",
    "tce_duration_err", "tce_depth", "tce_depth_err", "tce_model_snr",
    "tce_num_transits", "tce_ntoi"]
LEGACY_PARSE = getattr(cx, "_p10_3_original_parse_spoc_tce", cx._parse_spoc_tce)


def sector_stratum(value):
    value = str(value).strip()
    if not re.fullmatch(r"s\d+(?:-s\d+)?", value):
        raise ValueError(f"Unrecognized TCE sector run: {value!r}")
    values = [int(s) for s in re.findall(r"s(\d+)", value)]
    first, last = min(values), max(values)
    if first < 1:
        raise ValueError(f"Invalid TCE sector run: {value!r}")
    return first, last, "INDEPENDENT" if last <= 55 else "OVERLAPPING"


def ephemeris_frame(files, pool_tics):
    frames = []
    raw_rows = 0
    tics = set(int(t) for t in pool_tics)
    for filename, content in files:
        raw = pd.read_csv(io.BytesIO(content), comment="#", low_memory=False,
                          dtype={"tceid": str, "sectors": str})
        raw_rows += len(raw)
        missing = set(EPHEMERIS_COLUMNS) - set(raw.columns)
        if missing:
            raise ValueError(f"Missing ephemeris headers in {filename}: {sorted(missing)}")
        selected = raw.loc[pd.to_numeric(raw.ticid).isin(tics), EPHEMERIS_COLUMNS].copy()
        selected["source_filename"] = filename
        selected["source_row"] = selected.index + 1
        if len(selected):
            parsed = selected.sectors.map(sector_stratum)
            for i, col in enumerate(("first_sector", "last_sector", "independence")):
                selected[col] = parsed.map(lambda x: x[i])
        else:
            for col in ("first_sector", "last_sector", "independence"):
                selected[col] = pd.Series(dtype=object)
        frames.append(selected)
    if not frames:
        raise ValueError("No TCE raw files")
    result = pd.concat(frames, ignore_index=True)
    result.attrs["raw_rows"] = raw_rows
    return result


def _parse_spoc_tce(files, *, ephemerides_path=None, pool_tics=None):
    files = list(files)
    normalized = LEGACY_PARSE(files)
    if ephemerides_path is not None:
        if pool_tics is None:
            raise ValueError("Explicit complete pool TICs required for sidecar")
        path = Path(ephemerides_path)
        frame = ephemeris_frame(files, pool_tics)
        normalized.attrs["p10_3_raw_rows"] = frame.attrs["raw_rows"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="") as stream:
            frame.to_csv(stream, index=False, lineterminator="\n")
    return normalized


@dataclass
class P10HardStopResult(cx.HardStopResult):
    ephemerides: list[dict] = field(default_factory=list)
    population_rule: str = "hard_stop_p10"

    def summary(self):
        if self.flagged and self.tic_matches and all(m["source"]=="spoc_tce" for m in self.tic_matches):
            return (f"FLAG: TIC {self.tic_id} has a bare SPOC TCE association; "
                    f"{len(self.ephemerides)} ephemeris rows, not promoted")
        return super().summary()


def hard_stop_p10(tic_id, ra=None, dec=None, *, resolve_neighbours=True,
                  catalog=None, ephemerides=None, neighbour_tics=None):
    """Separate population rule; caller supplies sidecar rows, never search.

    Future F7 readers use tic_matches[].ephemerides and the top-level
    ephemerides list. Existing k0_hard_stop reads only status and needs no change.
    Missing ephemerides for a bare-TCE flag is an input error, not a clean flag.
    """
    cat = catalog or cx.get_catalog()
    old = cat.check(tic_id, ra, dec, neighbour_tics=neighbour_tics,
                    resolve_neighbours=resolve_neighbours)
    if not old.tic_matches or {m["source"] for m in old.tic_matches} != {"spoc_tce"}:
        return old
    records = [dict(r) for r in (ephemerides or []) if int(r["ticid"]) == int(tic_id)]
    if not records:
        raise ValueError(f"Bare TCE requires ephemerides: TIC {tic_id}")
    matches = [dict(m, ephemerides=records) for m in old.tic_matches]
    return P10HardStopResult(tic_id=old.tic_id, status=cx.STATUS_FLAG,
        tic_matches=matches, neighbour_matches=old.neighbour_matches,
        catalog_stamp=old.catalog_stamp, neighbours_resolved=old.neighbours_resolved,
        ephemerides=records)


def install():
    cx._p10_3_original_parse_spoc_tce = LEGACY_PARSE
    cx._parse_spoc_tce = _parse_spoc_tce
    cx.hard_stop_p10 = hard_stop_p10
    return cx
