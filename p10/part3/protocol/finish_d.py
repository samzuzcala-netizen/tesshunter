"""Aggregate registered input cuts and STOP-1; no prediction or forced-fit access."""
from common import REPO,ROOT,read,write,sha,utc
from registration_chain import verify
from tce_families import counts
from collections import Counter
import csv,json,time


def main():
    verify();start=time.perf_counter()
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Controller still owns a phase')
    original=read(ROOT/'manifests/original_531.json');rows=[]
    for original_row in original:
        r=dict(original_row);tic=r['tic_id']
        if not r['after_a_eligible']:
            r.update(input_eligible=False,part_d='NOT_REQUIRED');rows.append(r);continue
        path=ROOT/f'results/native_noise/tic{tic}.json'
        if not path.exists():
            r.update(input_eligible=False,status='INPUT_OPERATIONAL_UNKNOWN',exclusion_reason='verification_or_preparation_failed')
        else:
            n=read(path)
            good=n['status']=='INPUT_ELIGIBLE'
            r.update(input_eligible=good,status='INPUT_ELIGIBLE' if good else 'INPUT_INELIGIBLE',
                     exclusion_reason=None if good else 'verified_usable_sectors_or_noise',usable_sectors=n['usable_sectors'],
                     n_usable_sectors=len(n['usable_sectors']),n_cad=n['n_cad'],sigma=n['sigma'],
                     noise_record=path.relative_to(REPO).as_posix(),noise_sha256=sha(path))
        nb=ROOT/f'results/neighbour_receipts/{tic}.json'
        r['neighbours_status']='COMPLETE' if nb.exists() and read(nb).get('ok') else 'OPERATIONAL_UNKNOWN'
        rows.append(r)
    eligible={r['tic_id'] for r in rows if r['input_eligible']}
    sidecar=read(ROOT/'manifests/sidecar.json')
    path=REPO/'data/cache/catalogs/spoc_tce/spoc_tce.ephemerides.csv'
    if sha(path)!=sidecar['sha256']:raise RuntimeError('Frozen ephemeris sidecar changed')
    # The upstream census is authorized here for STOP-1; no worker receives these rows.
    tces=[r for r in csv.DictReader(path.open(encoding='utf-8')) if int(r['ticid']) in eligible]
    census=counts(tces)
    count=census['INDEPENDENT']['likely_periodic_in_band_families']
    phases={p.parent.name:read(p) for p in (ROOT/'results/controllers').glob('*/closure.json') if p.parent.name.startswith(('verify_prepare','neighbours_'))}
    if not phases or any(not p['all_owned_workers_closed'] or not p['source_hashes_unchanged'] for p in phases.values()):raise RuntimeError('Part D closure integrity failed')
    timing=Counter();selected_author=Counter();corrected=0
    for tic in sorted(eligible):
        identity=read(ROOT/f'results/input_identity/tic{tic}.json')
        for r in identity['records']:
            timing[r['timing_status']]+=1
            if r['timing_status']=='CORRECTED_V02_SOURCE_VERIFIED':corrected+=1
    summary=dict(utc=utc(),original=531,after_a=473,input_eligible=len(eligible),
        input_operational_unknowns=sum(r['status']=='INPUT_OPERATIONAL_UNKNOWN' for r in rows),
        neighbours_operational_unknowns=sum(r.get('neighbours_status')=='OPERATIONAL_UNKNOWN' for r in rows),
        eligible_neighbours_operational_unknowns=sum(r.get('neighbours_status')=='OPERATIONAL_UNKNOWN' and r['input_eligible'] for r in rows),
        families_by_stratum=census,STOP_1_fired=count<60,STOP_1_count=count,STOP_1_threshold=60,
        timing_status_counts_on_eligible_hosts=dict(timing),corrected_v02_comparisons_on_eligible_hosts=corrected,
        actual_wall_seconds=time.perf_counter()-start,sidecar_sha256=sha(path),blind_search_run=False)
    write(ROOT/'manifests/input_eligibility.json',rows)
    write(ROOT/'results/part_d.json',summary)
    target_rows=list(csv.DictReader((ROOT/'manifests/targets_after_a.csv').open()))
    with (ROOT/'manifests/targets_eligible.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=target_rows[0].keys());w.writeheader();w.writerows(r for r in target_rows if int(r['tic_id']) in eligible)
    table='\n'.join(f'| {s} | {c["rows"]} | {c["families"]} | {c["likely_periodic_in_band_families"]} |' for s,c in census.items())
    report=f'''# Part D input verification\n\n[M] {len(eligible)} of the original 531 stars are input eligible after the registered sequential cuts (473 after A). STOP-1: {"FIRED" if count<60 else "NOT FIRED"}; {count} independent likely-periodic in-band families against the minimum of 60. No search or forced fit has run.\n\n| Stratum | Raw rows | Families | Likely-periodic in-band families |\n|---|---:|---:|---:|\n{table}\n\n[M] {corrected} QLP 74-79 products on eligible hosts have exact corrected-v02 source comparisons. Per-product TIME, flux, SAP and quality checks, file hashes, BJD/TDB reference headers, quality masks, exclusions and native prepared point counts are saved under results/input_identity and results/native_noise. The frozen notice snapshot hash is retained in every identity record.\n\n[M] Verification/preparation operational unknowns: {summary['input_operational_unknowns']}. Neighbour operational unknowns: {summary['neighbours_operational_unknowns']}, including {summary['eligible_neighbours_operational_unknowns']} eligible hosts. These are not scientific misses.\n\n## Assumptions\n\n[A] The existing P10 author preference, native cadence harmonisation, quality masks, detrending and clipping remain unchanged. The P11 minimum of 50 retained native points defines a usable sector; at least three are required. Noise is 1.4826 times median absolute deviation around the prepared-flux median, with actual usable cadence counts. Original Part A Gaia and corrected two-minute cuts remain fixed; Part D supplies the third, usable-sector cut. Network failures remain unknowns. No flux-based clock adjustment or TCE ranking selected an input.\n'''
    (ROOT/'INPUT_VERIFICATION_P10_3.md').write_bytes(report.encode())
    ledger=read(ROOT/'manifests/resource_ledger.json');meter=read(ROOT/'manifests/acquisition_bytes.json')
    elapsed=time.perf_counter()-start
    ledger['new_queue_hours']+=elapsed/3600
    ledger['intervals'].append(dict(phase='D_eligibility_STOP1',end=utc(),hours=elapsed/3600))
    ledger.update(utc=utc(),new_acquisition_bytes=meter['measured_body_bytes'],acquisition_failed_read_upper_bytes=meter['failed_read_upper_bytes'],
        acquisition_outstanding_reserved_upper_bytes=sum(meter['reservations'].values()),cumulative_measured_acquisition_bytes=meter['prior_bytes']+meter['measured_body_bytes'],
        cumulative_acquisition_budget_charge_upper_bytes=meter['prior_bytes']+meter['measured_body_bytes']+meter['failed_read_upper_bytes']+sum(meter['reservations'].values()),
        phase_state='PART_D_COMPLETE_STOP1_REVIEW',checkin_count=len((ROOT/'logs/checkins.jsonl').read_text(encoding='utf-8-sig').splitlines()))
    write(ROOT/'manifests/resource_ledger.json',ledger,replace=True)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
