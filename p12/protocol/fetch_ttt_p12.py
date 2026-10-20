"""Bounded evaluator fetch and predeclared metadata selection for TTT negatives."""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time
import urllib.request

import numpy as np
import pandas as pd
import psutil

from p12_common import REPO, ROOT, DATA, PY, environment, utc, sha, read, write, append_jsonl
from catalog_snapshot_p12 import _identity, _still_owned, _close_tree

DEADLINE_S = 600
ARXIV_URL = "https://arxiv.org/e-print/2506.05631"
VIZIER_QUERY = "TESS Ten Thousand Kostov 2025"
TIC_ALIASES = ("tic_id", "tic", "ticid", "tess_id", "ticnumber", "tic_id_number", "tic_id_")
PERIOD_ALIASES = ("period", "porb", "p_orb", "orbital_period", "p", "period_days")
JOURNAL_TABLES = {
    3: dict(url="https://content.cld.iop.org/journals/0067-0049/279/2/50/revision1/apjsade2d8t3_mrt.txt", rows=7936),
    4: dict(url="https://content.cld.iop.org/journals/0067-0049/279/2/50/revision1/apjsade2d8t4_mrt.txt", rows=2065),
}


def _journal_mrt(body, expected_rows):
    from astropy.io import ascii
    lines = body.decode("utf-8-sig").splitlines()
    parsed = ascii.read(lines, format="mrt", guess=False)
    period_labels = [name for name in ("Per", "Per-TESS") if name in parsed.colnames]
    if "TIC" not in parsed.colnames or len(period_labels) != 1:
        raise ValueError("Journal MRT lacks required TIC/Per columns")
    period_label = period_labels[0]
    descriptors = {}
    for line in lines:
        match = re.match(r"\s*(\d+)\s*-\s*(\d+)\s+([AIFED]\S+)\s+(\S+)\s+(\S+)\s+", line)
        if match: descriptors[match.group(5)] = [int(match.group(1)), int(match.group(2))]
    expected_period_range = [45,53] if period_label == 'Per' else [38,46]
    if descriptors.get('TIC') != [1,10] or descriptors.get(period_label) != expected_period_range:
        raise ValueError('Journal MRT byte descriptors differ from the recorded source schema')
    if str(parsed[period_label].unit).lower() not in ("d", "day", "days"):
        raise ValueError("Journal MRT orbital-period unit is not days")
    frame = _ephemeris_table(parsed.to_pandas().rename(columns={period_label: "period_days"}))
    if len(parsed) != expected_rows or len(frame) != expected_rows or frame.tic_id.duplicated().any():
        raise ValueError("Journal MRT row count or identifier uniqueness failed")
    # Independently check the publisher's byte ranges, not a guessed delimiter.
    records = [line for line in lines if len(line) >= 53 and line[:10].strip().isdigit()]
    if len(records) != expected_rows:
        raise ValueError("Journal MRT fixed-width record count failed")
    if [int(line[:10]) for line in records] != frame.tic_id.tolist():
        raise ValueError("Journal MRT TIC byte-range cross-check failed")
    low, high = expected_period_range
    if not np.array_equal(np.array([float(line[low-1:high]) for line in records]), frame.period_days.to_numpy()):
        raise ValueError("Journal MRT period byte-range cross-check failed")
    frame.attrs.update(mrt_period_column=period_label,mrt_period_byte_range=expected_period_range)
    return frame


def _reparse_journal_table(table_number):
    from datetime import datetime, timezone
    path = ROOT / f"results/ttt_fetch/attempt5_table{table_number}.json"
    prior = read(path)
    elapsed = (datetime.now(timezone.utc)-datetime.fromisoformat(prior['started_utc'])).total_seconds()
    if elapsed >= 600 or prior['status'] != 'OPERATIONAL_UNKNOWN' or prior['error_type'] != 'ValueError':
        raise RuntimeError('Original source attempt cannot be reparsed within its bound')
    downloaded = REPO / prior['download_path']
    if sha(downloaded) != prior['sha256']:raise RuntimeError('Downloaded MRT changed')
    initial=ROOT/f"results/ttt_fetch/attempt5_table{table_number}_initial_parse.json"
    if initial.exists():
        if read(initial)!=prior:raise RuntimeError('Initial parse receipt changed')
    else:write(initial,prior)
    frame = _journal_mrt(downloaded.read_bytes(),JOURNAL_TABLES[table_number]['rows'])
    for tic in frame.tic_id:
        append_jsonl(ROOT/'manifests/exposure_ledger.jsonl',dict(utc=utc(),star=int(tic),
            stage='0f authorized journal attempt 5',path=prior['download_path'],reader='fetch_ttt_p12.py MRT evaluator',
            prompt_of_origin='P12',content='same-download Per-TESS schema mapping; no predictions or ephemeris values displayed'))
    normalized=DATA/f"negatives/truth/ttt_journal_table{table_number}.csv"
    with normalized.open('x',encoding='utf-8',newline='') as stream:frame.to_csv(stream,index=False,lineterminator='\n')
    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(prior['started_utc'])).total_seconds()
    if elapsed>=600:raise RuntimeError('Original source bound exceeded')
    result=dict(prior)
    result.pop('error_type',None)
    result.update(status='COMPLETE',utc=utc(),wall_seconds=elapsed,rows=len(frame),
        table_path=normalized.relative_to(REPO).as_posix(),table_sha256=sha(normalized),
        parser='astropy.io.ascii format=mrt',period_column=frame.attrs['mrt_period_column'],tic_byte_range=[1,10],
        period_byte_range=frame.attrs['mrt_period_byte_range'],period_unit='days',fixed_width_crosscheck=True,
        network_attempts=1,same_download_schema_reconciliation=True,initial_parse_receipt_sha256=sha(ROOT/f"results/ttt_fetch/attempt5_table{table_number}_initial_parse.json"))
    write(path,result,replace=True)
    print(json.dumps(dict(attempt=5,table_number=table_number,status='COMPLETE',rows=len(frame),bytes=prior['bytes'])))


def _journal_union(tables, expected_rows=10001):
    if set(tables) != {3, 4}:
        raise ValueError("Both journal tables are required")
    union = pd.concat([tables[3], tables[4]], ignore_index=True, sort=False)
    if len(union) != expected_rows or union.tic_id.duplicated().any():
        raise ValueError("Journal union row count or disjointness failed")
    return _ephemeris_table(union)


def _fetch_journal_table(table_number):
    environment(offline=False)
    specification = JOURNAL_TABLES[table_number]
    started, clock = utc(), time.perf_counter()
    receipt_path = ROOT / f"results/ttt_fetch/attempt5_table{table_number}.json"
    receipt = dict(attempt=5, kind="journal MRT", table_number=table_number,
        url=specification["url"], started_utc=started, deadline_s=600,
        expected_rows=specification["rows"], license="CC-BY-4.0 (user-specified journal source)")
    if receipt_path.exists():
        raise RuntimeError("This table's attempt 5 is already recorded")
    try:
        request = urllib.request.Request(specification["url"], headers={"User-Agent": "TessHunter P12 audit"})
        with urllib.request.urlopen(request, timeout=600) as response:
            body, response_url = response.read(), response.geturl()
        downloaded = _save_download(body, f"apjsade2d8t{table_number}_mrt.txt")
        receipt.update(status="DOWNLOADED", utc=utc(), resolved_url=response_url, bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest(), download_path=downloaded.relative_to(REPO).as_posix())
        write(receipt_path, receipt)
        frame = _journal_mrt(body, specification["rows"])
        for tic in frame.tic_id:
            append_jsonl(ROOT / "manifests/exposure_ledger.jsonl", dict(utc=utc(),star=int(tic),
                stage="0f authorized journal attempt 5",path=receipt["download_path"],
                reader="fetch_ttt_p12.py MRT evaluator",prompt_of_origin="P12",content="catalogue preparation; no predictions or ephemeris values displayed"))
        normalized = DATA / f"negatives/truth/ttt_journal_table{table_number}.csv"
        with normalized.open("x", encoding="utf-8", newline="") as stream:
            frame.to_csv(stream, index=False, lineterminator="\n")
        receipt.update(status="COMPLETE", rows=len(frame), table_path=normalized.relative_to(REPO).as_posix(),
            table_sha256=sha(normalized), parser="astropy.io.ascii format=mrt", tic_byte_range=[1,10],
            period_byte_range=frame.attrs['mrt_period_byte_range'], period_column=frame.attrs['mrt_period_column'],
            period_unit="days", fixed_width_crosscheck=True)
    except Exception as error:
        receipt.update(status="OPERATIONAL_UNKNOWN", error_type=type(error).__name__, utc=utc(), wall_seconds=time.perf_counter()-clock)
        write(receipt_path, receipt, replace=receipt_path.exists())
        raise RuntimeError("Journal attempt 5 did not complete: " + type(error).__name__) from None
    receipt.update(utc=utc(), wall_seconds=time.perf_counter()-clock)
    write(receipt_path, receipt, replace=True)
    print(json.dumps(dict(attempt=5,table_number=table_number,status="COMPLETE",rows=len(frame),bytes=len(body))))
    return receipt


def _normalized_columns(frame):
    result = frame.copy()
    result.columns = [re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower()).strip("_") for column in result.columns]
    if result.columns.duplicated().any():
        raise ValueError("Ambiguous duplicate normalized table headers")
    tic = next((name for name in TIC_ALIASES if name in result), None)
    if tic is None:
        raise ValueError("No TIC identifier column")
    result = result.rename(columns={tic: "tic_id"})
    values = result.tic_id.astype(str).str.replace(r"(?i)^TIC\s*", "", regex=True)
    number = pd.to_numeric(values, errors="coerce")
    valid = number.notna() & (number > 0) & (number % 1 == 0)
    result = result.loc[valid].copy()
    result["tic_id"] = number.loc[valid].astype("int64")
    if result.empty:
        raise ValueError("No valid integer TIC identifiers")
    return result


def _ephemeris_table(frame, *, require_all=True):
    result = _normalized_columns(frame)
    period = next((name for name in PERIOD_ALIASES if name in result), None)
    if period is None:
        raise ValueError("No orbital period column")
    result["period_days"] = pd.to_numeric(result[period], errors="coerce")
    valid = np.isfinite(result.period_days) & (result.period_days > 0)
    if require_all and not valid.all():
        raise ValueError("Table contains missing or invalid orbital periods")
    result.attrs["ephemeris_validation"] = dict(rows=len(result), valid_periods=int(valid.sum()),
        missing_or_invalid_periods=int((~valid).sum()), scope="whole catalogue")
    return result


def _lc_available(frame):
    if {"n_sectors_qlp", "n_sectors_tess_spoc"}.issubset(frame.columns):
        return (pd.to_numeric(frame.n_sectors_qlp, errors="coerce").fillna(0) > 0) | (
            pd.to_numeric(frame.n_sectors_tess_spoc, errors="coerce").fillna(0) > 0)
    if "products" in frame:
        return frame.products.fillna("").astype(str).str.lower().str.contains("qlp|tess-spoc", regex=True)
    # This field is the origin's count of delivered QLP/TESS-SPOC sectors, not
    # tess-point predicted coverage, and therefore itself proves LC availability.
    return pd.to_numeric(frame.n_sectors_200s, errors="coerce").fillna(0) > 0


def select_negatives(table, pool, core_tics) -> tuple:
    table = _normalized_columns(table)
    if pool.tic_id.duplicated().any():
        raise ValueError("Pool TIC identifiers are not unique")
    ids = set(table.tic_id.astype(int))
    joined = pool[pool.tic_id.isin(ids) & ~pool.tic_id.isin({int(t) for t in core_tics})].copy()
    base = (joined.rad < .45) & (joined.gallat.abs() >= 20) & (joined.n_sectors_200s >= 3)
    base &= joined.n_sectors_2min_in_search < joined.n_sectors_200s / 2
    base &= _lc_available(joined)
    history = []
    selected = joined.iloc[:0].copy()
    for step, teff, lo, hi in (("baseline", 3600., 12.5, 14.),
                                ("Teff", 4000., 12.5, 14.),
                                ("Tmag", 4000., 12., 14.5)):
        selected = joined[base & (joined.Teff < teff) & joined.Tmag.between(lo, hi, inclusive="both")].copy()
        history.append(dict(step=step, teff_lt=teff, tmag_min=lo, tmag_max=hi, qualifying=len(selected)))
        if len(selected) >= 20:
            break
    selected["selection_sha256"] = selected.tic_id.map(lambda tic: hashlib.sha256(f"20260908:ttt:{int(tic)}".encode()).hexdigest())
    selected = selected.sort_values(["selection_sha256", "tic_id"], kind="stable").head(30).reset_index(drop=True)
    return selected, dict(utc=utc(), relaxation_sequence=history, selected=len(selected),
        table_unique_tics=len(ids), absent_from_pool=len(ids - set(pool.tic_id.astype(int))),
        excluded_core=len(ids & {int(t) for t in core_tics}),
        ordering="SHA-256(20260908:ttt:<integer TIC>), first 30", strict_ffi_majority=True)


def _table_candidates(body, filename):
    from astropy.table import Table
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        yield pd.read_csv(io.BytesIO(body), comment="#", low_memory=False)
    elif suffix in {".vot", ".xml"}:
        from astropy.io.votable import parse
        for table in parse(io.BytesIO(body)).iter_tables():
            yield table.to_table().to_pandas()
    elif suffix in {".fits", ".fit"}:
        yield Table.read(io.BytesIO(body), format="fits").to_pandas()
    else:
        for fmt in ("ascii.ecsv", "ascii.csv", "ascii.basic", "ascii.tab", "ascii.fixed_width_two_line"):
            try:
                yield Table.read(body.decode("utf-8"), format=fmt).to_pandas()
            except Exception:
                continue


def _choose_table(candidates, *, require_all=True):
    errors = []
    for name, frame in candidates:
        try:
            if frame.attrs.get("incomplete_catalogue"):
                raise ValueError("Manuscript table is explicitly abbreviated; full catalogue is a separate supplement")
            return name, _ephemeris_table(frame, require_all=require_all)
        except (ValueError, KeyError) as exc:
            errors.append(f"{name}: {exc}")
    raise ValueError("No machine-readable TIC/orbital-period table: " + "; ".join(errors[:10]))


def _tex_cell(value):
    value = re.sub(r"\\tablenotemark\{[^}]*\}", "", value)
    value = re.sub(r"\\(?:hline|toprule|midrule|bottomrule)\b", "", value)
    value = re.sub(r"\\(?:nodata|ldots|cdots)\b", "", value)
    value = re.sub(r"\\[A-Za-z]+\*?", "", value)
    return re.sub(r"\s+", " ", value.replace("$", "").replace("{", "").replace("}", "")).strip()


def _tex_argument(text, command):
    match = re.search(re.escape(command) + r"\s*\{", text)
    if not match:
        return None
    start = match.end(); depth = 1
    for index in range(start, len(text)):
        if text[index] == "{": depth += 1
        elif text[index] == "}": depth -= 1
        if depth == 0: return text[start:index]
    raise ValueError("Unbalanced TeX table argument")


def _tex_table_candidates(body):
    text = re.sub(r"(?m)(?<!\\)%.*$", "", body.decode("utf-8"))
    blocks = list(re.finditer(r"\\begin\{(table\*?|sidewaystable\*?|deluxetable\*?)\}(.*?)\\end\{\1\}", text, re.S))
    if not blocks:
        blocks = list(re.finditer(r"\\begin\{(tabular\*?)\}(.*?)\\end\{\1\}", text, re.S))
    for block_index, match in enumerate(blocks, 1):
        environment, block = match.group(1), match.group(2)
        if environment.startswith("deluxetable"):
            head = _tex_argument(block, r"\tablehead")
            data_match = re.search(r"\\startdata(.*?)\\enddata", block, re.S)
            if head is None or data_match is None:
                continue
            rows = re.split(r"\\\\|\\nl\b", head + r"\\" + data_match.group(1))
        else:
            inner = re.search(r"\\begin\{tabular\*?\}(.*?)\\end\{tabular\*?\}", block, re.S)
            tabular = inner.group(1) if inner else block
            tabular = re.sub(r"^\s*(?:\[[^]]*\]\s*)?\{[^{}]*\}\s*", "", tabular)
            rows = re.split(r"\\\\|\\nl\b", tabular)
        header = None; values = []
        for row in rows:
            cells = [_tex_cell(cell) for cell in re.split(r"(?<!\\)&", row)]
            normalized = [re.sub(r"[^a-z0-9]+", "_", cell.lower()).strip("_") for cell in cells]
            if any(cell in TIC_ALIASES for cell in normalized) and any(cell in PERIOD_ALIASES for cell in normalized):
                # Repeated eclipse-property headings get explicit unique names.
                used = {}; header = []
                for index, cell in enumerate(cells):
                    cell = cell or f"column_{index + 1}"
                    used[cell] = used.get(cell, 0) + 1
                    header.append(cell if used[cell] == 1 else f"{cell}_{used[cell]}")
                continue
            if header is None or len(cells) != len(header):
                continue
            tic_index = next(i for i, cell in enumerate(header)
                if re.sub(r"[^a-z0-9]+", "_", cell.lower()).strip("_") in TIC_ALIASES)
            if re.fullmatch(r"(?:TIC\s*)?\d+", cells[tic_index], re.I):
                values.append(cells)
        if not header or not values:
            continue
        frame = pd.DataFrame(values, columns=header)
        partial = bool(re.search(r"available\s+in\s+full|(?:portion|sample)\s+of\s+(?:this\s+|the\s+)?table|first\s+\d+\s+(?:rows|entries)", block, re.I))
        frame.attrs.update(incomplete_catalogue=partial, tex_environment=environment,
            tex_table_index=block_index, manuscript_rows=len(frame))
        yield frame


def _eprint_candidates(body):
    # Parse embedded tables too, retaining explicit sample/full-table notices.
    candidates = []
    inventory = []
    with tarfile.open(fileobj=io.BytesIO(body), mode="r:*") as archive:
        for member in sorted(archive.getmembers(), key=lambda item: item.name):
            if not member.isfile():
                continue
            suffix = Path(member.name).suffix.lower()
            inventory.append(dict(suffix=suffix, bytes=member.size))
            if suffix not in {".csv", ".dat", ".txt", ".ecsv", ".fits", ".fit", ".vot", ".xml", ".tbl", ".tex"}:
                continue
            stream = archive.extractfile(member)
            if stream is None:
                continue
            try:
                parser = _tex_table_candidates(stream.read()) if suffix == ".tex" else _table_candidates(stream.read(), member.name)
                candidates.extend((member.name, frame) for frame in parser)
            except Exception:
                continue
    return candidates, inventory


def _save_download(body, filename):
    path = DATA / "negatives/ttt_downloads" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(body)
    return path


def _download_receipt(kind, started, body, url, downloaded):
    receipt = dict(kind=kind, status="DOWNLOADED", started_utc=started, utc=utc(), url=url,
        bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
        query=VIZIER_QUERY if kind == "vizier" else None,
        download_path=downloaded.relative_to(REPO).as_posix())
    write(ROOT / f"results/ttt_fetch/{kind}.json", receipt)
    return receipt


def _fetch_worker(kind):
    environment(offline=False)
    start = utc()
    if kind == "vizier":
        from astroquery.vizier import Vizier
        from astropy.io.votable import parse
        catalogs = Vizier.find_catalogs(VIZIER_QUERY)
        if not catalogs:
            raise RuntimeError("No VizieR catalogue matches title/author query")
        response = Vizier(row_limit=-1).get_catalogs_async(sorted(catalogs))
        response.raise_for_status()
        body, url = response.content, response.url
        downloaded = _save_download(body, "vizier_response.xml")
        _download_receipt(kind, start, body, url, downloaded)
        name, table = _choose_table((f"VizieR table {i}", item.to_table().to_pandas())
            for i, item in enumerate(parse(io.BytesIO(body)).iter_tables()))
    elif kind == "eprint":
        request = urllib.request.Request(ARXIV_URL, headers={"User-Agent": "TessHunter P12 audit"})
        with urllib.request.urlopen(request, timeout=60) as response:
            body, url = response.read(), response.geturl()
        downloaded = _save_download(body, "2506.05631.eprint.tar")
        _download_receipt(kind, start, body, url, downloaded)
        candidates, inventory = _eprint_candidates(body)
        write(ROOT / "results/ttt_fetch/eprint_inventory.json", dict(utc=utc(),
            archive_sha256=hashlib.sha256(body).hexdigest(), members=inventory,
            candidate_tables=len(candidates), manuscript_samples_used=False))
        name, table = _choose_table(candidates)
    else:
        raise ValueError(kind)
    truth_path = DATA / "negatives/truth" / f"ttt_table_{kind}.csv"
    truth_path.parent.mkdir(parents=True, exist_ok=True)
    with truth_path.open("x", encoding="utf-8", newline="") as stream:
        table.to_csv(stream, index=False, lineterminator="\n")
    receipt = dict(kind=kind, status="COMPLETE", started_utc=start, utc=utc(), url=url,
        bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), query=VIZIER_QUERY if kind == "vizier" else None,
        download_path=downloaded.relative_to(REPO).as_posix(), table_name=name,
        table_path=truth_path.relative_to(REPO).as_posix(), table_sha256=sha(truth_path), rows=len(table))
    write(ROOT / f"results/ttt_fetch/{kind}.json", receipt, replace=True)
    return receipt


def _run_fetch(kind):
    start, wall = utc(), time.perf_counter()
    command = [str(PY), str(Path(__file__).resolve()), "--fetch-source", kind]
    log = ROOT / f"logs/ttt_fetch/{kind}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    identities = []
    with log.open("x", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=REPO, env=environment(offline=False), stdout=stream,
            stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        identities.append(_identity(psutil.Process(process.pid)))
        while process.poll() is None and time.perf_counter() - wall < DEADLINE_S:
            parent = _still_owned(identities[0])
            if parent is not None:
                try:
                    for child in parent.children(recursive=True):
                        identity = _identity(child)
                        if identity not in identities:
                            identities.append(identity)
                except psutil.NoSuchProcess:
                    pass
            time.sleep(.1)
        timed_out = process.poll() is None
        _close_tree(identities)
        process.wait(timeout=5)
    result_path = ROOT / f"results/ttt_fetch/{kind}.json"
    result = read(result_path) if result_path.exists() else dict(
        kind=kind, status="TIMEOUT" if timed_out else "OPERATIONAL_UNKNOWN", url=ARXIV_URL if kind == "eprint" else "https://vizier.cds.unistra.fr/viz-bin/votable",
        bytes=0, sha256=None, error=f"Source attempt did not complete; see {log.relative_to(REPO).as_posix()}")
    if timed_out or process.returncode != 0 or result["status"] != "COMPLETE":
        result["status"] = "TIMEOUT" if timed_out else "OPERATIONAL_UNKNOWN"
        result["error"] = f"Source fetch/parse did not complete; see {log.relative_to(REPO).as_posix()}"
    result.update(started_utc=start, utc=utc(), wall_seconds=time.perf_counter() - wall,
        deadline_s=DEADLINE_S, attempt=1, identity=identities[0], process_tree=identities,
        all_owned_workers_closed=True, exit_code=process.returncode)
    return result


def _fallback():
    root = REPO / "data/cache/catalogs/tess_eb"
    paths = sorted((root / "raw").glob("*.csv"))
    before = {p.relative_to(REPO).as_posix(): sha(p) for p in root.rglob("*") if p.is_file()}
    candidates = ((p.name, pd.read_csv(p, comment="#", low_memory=False)) for p in paths)
    name, table = _choose_table(candidates, require_all=False)
    path = next(p for p in paths if p.name == name)
    after = {p.relative_to(REPO).as_posix(): sha(p) for p in root.rglob("*") if p.is_file()}
    if before != after:
        raise RuntimeError("STOP-1: historical TESS-EB fallback changed")
    return table, dict(kind="fallback TESS-EB", status="COMPLETE", url=path.relative_to(REPO).as_posix(),
        utc=utc(), bytes=path.stat().st_size, sha256=sha(path), historical_hashes_unchanged=True,
        table_name=name, rows=len(table), ephemeris_validation=table.attrs["ephemeris_validation"],
        validation_policy="Keep every TIC for the unchanged metadata selection; require valid periods for every selected row")


def _resume_attempts(path, digest):
    path = (REPO / path).resolve()
    if not path.is_relative_to((ROOT / "manifests").resolve()) or sha(path) != digest:
        raise RuntimeError("Prior fetch receipt identity mismatch")
    prior = read(path)
    attempts = prior["attempts"]
    if prior["status"] != "FETCHING" or [a["kind"] for a in attempts] != ["vizier", "eprint"]:
        raise RuntimeError("Unexpected prior fetch sequence")
    if any(a["status"] not in ("TIMEOUT", "OPERATIONAL_UNKNOWN") or not a["all_owned_workers_closed"] for a in attempts):
        raise RuntimeError("Prior source attempts are not closed failures")
    for attempt in attempts:
        if attempt.get("download_path"):
            downloaded = (REPO / attempt["download_path"]).resolve()
            if not downloaded.is_relative_to((DATA / "negatives/ttt_downloads").resolve()) or sha(downloaded) != attempt["sha256"]:
                raise RuntimeError("Prior download identity mismatch")
    return attempts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-source", choices=["vizier", "eprint"])
    parser.add_argument("--resume-from")
    parser.add_argument("--resume-sha256")
    parser.add_argument("--journal-table", type=int, choices=[3,4])
    parser.add_argument("--journal-reparse", type=int, choices=[3,4])
    args = parser.parse_args(argv)
    if args.journal_reparse:
        _reparse_journal_table(args.journal_reparse)
        return
    if args.journal_table:
        _fetch_journal_table(args.journal_table)
        return
    if args.fetch_source:
        _fetch_worker(args.fetch_source)
        return
    environment(offline=False)
    if bool(args.resume_from) != bool(args.resume_sha256):
        raise ValueError("Resume requires the archived receipt and its hash")
    attempts = _resume_attempts(args.resume_from, args.resume_sha256) if args.resume_from else []
    table = None
    receipt_path = ROOT / "manifests/ttt_fetch.json"
    for kind in (() if args.resume_from else ("vizier", "eprint")):
        result = _run_fetch(kind)
        attempts.append(result)
        write(receipt_path, dict(utc=utc(), status="FETCHING", attempts=attempts), replace=True)
        if result["status"] == "COMPLETE":
            path = REPO / result["table_path"]
            if sha(path) != result["table_sha256"]:
                raise RuntimeError("STOP-1: fetched TTT table hash changed")
            table = _ephemeris_table(pd.read_csv(path, low_memory=False))
            break
    if table is None:
        table, result = _fallback()
        attempts.append(result)
    pool = pd.read_csv(REPO / "data/survey/cache/p8/pool_after_xmatch.csv", low_memory=False)
    core = pd.read_csv(ROOT / "manifests/targets_p12_core.csv", usecols=["tic_id"])
    selected, selection = select_negatives(table, pool, core.tic_id)
    # Validate the selected population before writing any selection products.
    # Invalid periods elsewhere in a historical catalogue do not change which
    # TICs meet the preregistered metadata cuts or the fixed hash ordering.
    truth = _ephemeris_table(table[table.tic_id.isin(selected.tic_id)]) if len(selected) else table.iloc[:0].copy()
    manifest = ROOT / "manifests/ttt_negatives.csv"
    with manifest.open("x", encoding="utf-8", newline="") as stream:
        selected.to_csv(stream, index=False, lineterminator="\n")
    truth_path = DATA / "negatives/truth/ttt_ephemerides.json"
    write(truth_path, dict(utc=utc(), source=result["kind"], records=json.loads(truth.to_json(orient="records", double_precision=15))))
    for tic in sorted(table.tic_id.unique()):
        append_jsonl(ROOT / "manifests/exposure_ledger.jsonl", dict(utc=utc(), star=int(tic),
            stage="0f negative-set evaluator preparation", path=result.get("table_path", result["url"]),
            reader="fetch_ttt_p12.py", prompt_of_origin="P12", content="catalogue truth preparation; no predictions"))
    receipt = dict(utc=utc(), status="COMPLETE", source=result["kind"], attempts=attempts,
        selection=selection, manifest_sha256=sha(manifest), ephemerides_sha256=sha(truth_path),
        guarded_ephemerides_path=truth_path.relative_to(REPO).as_posix())
    write(receipt_path, receipt, replace=True)
    print(json.dumps({"source": result["kind"], "selected": len(selected), "selection": selection}), flush=True)


if __name__ == "__main__":
    main()
