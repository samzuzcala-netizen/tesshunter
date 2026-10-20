"""Open Part F once, after prospective method registration and prediction locks."""
from common import REPO, ROOT, environment, read, write, sha, utc
environment()
import csv
import json
import math
import time
from collections import Counter
from registration_execution_v3 import verify
from lock_predictions import both_locked
from tce_families import families
from part_f_math_v1 import (STRATA, row_id, representative, in_band, likely,
                           expected_snr, epoch_rule, candidate_match)
from part_f_guards_v1 import IntegrityFailure, require_hash, signal_integrity_failure, assert_no_integrity_failure


def recovery_summary(rows, preset, host_status, domain=True):
    considered = [r for r in rows if r['in_band']] if domain else rows
    if not considered:
        return dict(status='OUTSIDE_DOMAIN', recovered_candidate_ids=[], exact_candidate_ids=[], alias_candidate_ids=[])
    accepted = [m for r in considered for m in r['presets'][preset]['associations'] if m['recovered']]
    exact = sorted({m['candidate_id'] for m in accepted if m['exact']})
    alias = sorted({m['candidate_id'] for m in accepted if not m['exact']})
    status = ('RECOVERED_EXACT' if exact else 'RECOVERED_ALIAS' if alias else
              'OPERATIONAL_UNKNOWN' if host_status != 'COMPLETE' else 'NOT_RECOVERED')
    return dict(status=status, recovered_candidate_ids=sorted(set(exact+alias)),
                exact_candidate_ids=exact, alias_candidate_ids=alias)


def main():
    verify(require_launch_seal=True)
    assert_no_integrity_failure()
    if (ROOT/'manifests/controller_owner.json').exists():
        raise RuntimeError('An owning controller is present')
    if (ROOT/'manifests/part_f_entry_v1.json').exists():
        raise RuntimeError('Part F was already opened; inspect its receipts, never silently rerun')
    method_path = ROOT/'manifests/part_f_method_registration_v1.json'
    method = read(method_path)
    for name, digest in method['source_hashes'].items():
        require_hash(REPO/name, digest, 'Registered Part F source')
    seals = both_locked()
    predictions = {s['path'].split('predictions_')[-1].removesuffix('.json'):read(REPO/s['path']) for s in seals}
    presets = ('survey_p10','survey_p8')
    allocation = read(ROOT/'manifests/allocation.json')
    selected = allocation['selected_tic_ids']
    for preset in presets:
        if [h['tic_id'] for h in predictions[preset]['hosts']] != selected:
            raise IntegrityFailure('Paired prediction membership differs from the frozen allocation')
    host_predictions = {p:{h['tic_id']:h for h in predictions[p]['hosts']} for p in presets}
    closed = read(ROOT/'manifests/early_funnel_closed_evidence_seal.json')
    for name, digest in closed['files'].items():
        require_hash(REPO/name, digest, 'Closed early-funnel evidence')
    input_seal = read(ROOT/'manifests/input_data_seal.json')['hashes']
    noises = {}
    for tic in selected:
        path = ROOT/f'results/native_noise/tic{tic}.json'
        require_hash(path, input_seal[path.relative_to(REPO).as_posix()], 'Sealed Part D noise')
        noises[tic] = read(path)
        for preset in presets:
            runtime_path = ROOT/f'manifests/search_runtime/{preset}_tic{tic}.json'
            frozen_runtime = read(runtime_path)
            output_hash = host_predictions[preset][tic].get('prepared_sha256')
            if (noises[tic]['prepared_sha256'] != frozen_runtime['prepared_sha256'] or
                    (output_hash is not None and output_hash != noises[tic]['prepared_sha256'])):
                raise IntegrityFailure('Forced input differs from paired search input')
    sidecar = read(ROOT/'manifests/sidecar.json')
    require_hash(REPO/sidecar['path'], sidecar['sha256'], 'Registered TCE sidecar')
    started, timer = utc(), time.perf_counter()
    try:
        exposure_path = ROOT/'manifests/exposure_ledger.json'
        exposure = read(exposure_path)
        original = sorted(set(exposure['stages'][0]['tics']))
        if len(original) != 531:
            raise IntegrityFailure('Original development-exposure population differs from 531')
        write(ROOT/'manifests/exposure_ledger_before_part_f.json', exposure)
        entry = dict(utc=utc(), stage='PART_F_OPENED', prediction_locks=seals,
                     sidecar_path=sidecar['path'], sidecar_sha256=sidecar['sha256'],
                     method_registration_sha256=sha(method_path), original_development_exposed_tic_ids=original,
                     development_exposed_count=len(original), evaluated_hosts=len(selected),
                     C_cap_sha256=sha(ROOT/'manifests/C_cap_at_B_closure.json'),
                     scientific_outcomes_not_used_to_define_methods=True)
        write(ROOT/'manifests/part_f_entry_v1.json', entry)
        exposure.update(utc=utc(), part_f_opened=True, development_exposed=True,
                        development_exposed_tic_ids=original, never_a_holdout_after_utc=entry['utc'])
        exposure['stages'].append(dict(stage='Part_F_matching_and_forced_fits', utc=entry['utc'],
                                       tics=original, content='All original 531 are development-exposed from this boundary; both paired prediction locks verified.'))
        write(exposure_path, exposure, replace=True)
        selected_set = set(selected)
        with (REPO/sidecar['path']).open(newline='',encoding='utf-8-sig') as stream:
            raw_rows = [r for r in csv.DictReader(stream) if int(r['ticid']) in selected_set]
        if len({row_id(r) for r in raw_rows}) != len(raw_rows):
            raise IntegrityFailure('Duplicate source/row identity in the TCE sidecar')
        grouped = families(raw_rows)
        row_records, family_records, jobs = [], [], []
        source_hashes = method['source_hashes']
        prediction_hashes = {s['path']:s['sha256'] for s in seals}
        for family in grouped:
            fid, tic = family['family_id'], family['tic_id']
            members, noise = family['rows'], noises[tic]
            rep = representative(members)
            local_records = []
            for row in members:
                record = dict(row_id=row_id(row), family_id=fid, tic_id=tic, raw=row,
                              independence=row['independence'], in_band=in_band(row), likely_periodic=likely(row),
                              expected_snr=expected_snr(row, noise), epoch_rule=epoch_rule(row,noise['midpoint_btjd']), presets={})
                for preset in presets:
                    host = host_predictions[preset][tic]
                    associations = [m for candidate in host['accepted']
                                    if (m:=candidate_match(row,candidate,noise['midpoint_btjd'])) is not None]
                    record['presets'][preset] = dict(search_status=host['status'],associations=associations)
                    record['presets'][preset].update(recovery_summary([record],preset,host['status']))
                row_records.append(record)
                local_records.append(record)
            family_record = dict(family_id=fid,tic_id=tic,anchor_period_days=family['anchor_period'],
                                 member_row_ids=[row_id(r) for r in members],representative_row_id=row_id(rep),
                                 representative=rep,expected_snr=expected_snr(rep,noise),strata={},
                                 forced_fit_receipt=f'p10/part3/results/forced_fits/{fid}.json')
            for stratum in STRATA:
                subset = [r for r in local_records if stratum=='UNION' or r['independence']==stratum]
                if not subset:
                    continue
                srep = representative([r['raw'] for r in subset])
                summary = dict(member_row_ids=[r['row_id'] for r in subset],representative_row_id=row_id(srep),
                               representative=srep,expected_snr=expected_snr(srep,noise),
                               in_band=any(r['in_band'] for r in subset),
                               mixed_domain_membership=any(r['in_band'] for r in subset) and any(not r['in_band'] for r in subset),
                               likely_periodic_in_band=any(r['in_band'] and r['likely_periodic'] for r in subset),presets={})
                for preset in presets:
                    summary['presets'][preset] = recovery_summary(subset,preset,host_predictions[preset][tic]['status'])
                family_record['strata'][stratum] = summary
            family_records.append(family_record)
            noise_path = ROOT/f'results/native_noise/tic{tic}.json'
            runtime = dict(family_id=fid,tic_id=tic,representative_row_id=row_id(rep),representative=rep,
                           noise_path=noise_path.relative_to(REPO).as_posix(),noise_sha256=sha(noise_path),
                           source_hashes=source_hashes,prediction_hashes=prediction_hashes,
                           method_registration_sha256=sha(method_path),
                           part_f_entry_sha256=sha(ROOT/'manifests/part_f_entry_v1.json'))
            runtime_path = ROOT/f'manifests/forced_fit_runtime/{fid}.json'
            write(runtime_path,runtime)
            jobs.append(dict(job_id=fid,arguments=['p10/part3/protocol/forced_fit_worker_v1.py',
                        runtime_path.relative_to(REPO).as_posix(),sha(runtime_path)],result_path=family_record['forced_fit_receipt']))
        matching = dict(utc=utc(),status='LOCKED_MATCHING',evaluated_hosts=len(selected),raw_rows=len(row_records),
                        families=len(family_records),presets=presets,prediction_hashes=prediction_hashes,
                        part_f_entry_sha256=sha(ROOT/'manifests/part_f_entry_v1.json'),
                        rows=row_records,ephemeris_families=family_records,
                        assumptions=method['assumptions'])
        write(ROOT/'results/matching.json',matching)
        job_path=ROOT/'manifests/forced_fits_jobs.json';write(job_path,jobs)
        plan=dict(utc=utc(),action='LAUNCH_REGISTERED_PHASE',phase='forced_fits',jobs=job_path.relative_to(REPO).as_posix(),jobs_count=len(jobs),
                  workers=24,deadline_seconds=300,forecast_minutes=math.ceil(len(jobs)/24)*300/60,
                  forecast_method='One-attempt 300-second deadline waves; no forced-fit outcome used',
                  jobs_sha256=sha(job_path),controller='p10/part3/protocol/controller_v4.py',
                  matching_sha256=sha(ROOT/'results/matching.json'),method_registration_sha256=sha(method_path))
        write(ROOT/'manifests/forced_fits_preflight.json',plan)
        print(json.dumps(dict(phase='PART_F_MATCHING_COMPLETE',hosts=len(selected),raw_rows=len(raw_rows),
                              families=len(grouped),forced_fit_plan=plan)),flush=True)
    finally:
        ledger=read(ROOT/'manifests/resource_ledger.json');hours=(time.perf_counter()-timer)/3600
        ledger['new_queue_hours']+=hours;ledger['utc']=utc()
        ledger['intervals'].append(dict(phase='F_matching_and_forced_dispatch',start=started,end=ledger['utc'],hours=hours))
        write(ROOT/'manifests/resource_ledger.json',ledger,replace=True)


if __name__=='__main__':
    try:
        main()
    except IntegrityFailure as error:
        signal_integrity_failure(error,dict(phase='F_matching_and_forced_dispatch'))
        raise
