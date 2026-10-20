"""One registered forced box fit; no period search or scientific retry."""
from common import REPO, ROOT, environment, read, write, sha, utc
environment()
import sys
import time
import traceback
from pathlib import Path
import numpy as np
from science_json import safe
from part_f_math_v1 import finite, epoch_rule, expected_snr
from forced_box_v1 import fit_box
from part_f_guards_v1 import IntegrityFailure, require_hash, signal_integrity_failure, assert_no_integrity_failure


def main(runtime_name, expected_runtime_hash):
    started, timer, cpu = utc(), time.perf_counter(), time.process_time()
    runtime_path = REPO/runtime_name
    assert_no_integrity_failure()
    require_hash(runtime_path, expected_runtime_hash, 'Forced-fit runtime')
    runtime = read(runtime_path)
    family_id = runtime['family_id']
    if (ROOT/f'results/forced_fits/{family_id}.json').exists():
        raise RuntimeError('No scientific retry is authorized for this family')
    try:
        for name, digest in runtime['source_hashes'].items():
            require_hash(REPO/name, digest, 'Registered forced-fit source')
        require_hash(ROOT/'manifests/part_f_method_registration_v1.json', runtime['method_registration_sha256'], 'Method registration')
        require_hash(ROOT/'manifests/part_f_entry_v1.json', runtime['part_f_entry_sha256'], 'Part F entry')
        for name, digest in runtime['prediction_hashes'].items():
            require_hash(REPO/name, digest, 'Locked prediction')
        noise_path = REPO/runtime['noise_path']
        require_hash(noise_path, runtime['noise_sha256'], 'Part D noise record')
        noise = read(noise_path)
        native_path = REPO/noise['prepared_path']
        require_hash(native_path, noise['prepared_sha256'], 'Frozen native prepared input')
        with np.load(native_path, allow_pickle=False) as native:
            t, f = native['time'], native['flux']
        row = runtime['representative']
        rule = epoch_rule(row, noise['midpoint_btjd'])
        period, duration = finite(row.get('tce_period')), finite(row.get('tce_duration'))
        if period is None or duration is None:
            raise ValueError('Missing representative period or duration')
        fit = fit_box(t, f, period, duration/24, noise['cadence_days'],
                      finite(row.get('tce_time0bt')) if rule['checkable'] else None)
        result = dict(fit, family_id=family_id, tic_id=runtime['tic_id'],
                      representative_row_id=runtime['representative_row_id'],
                      epoch_rule=rule, expected_snr=expected_snr(row, noise))
    except IntegrityFailure as error:
        signal_integrity_failure(error, dict(phase='forced_fits', family_id=family_id))
        raise
    except Exception as error:
        result = dict(family_id=family_id, tic_id=runtime['tic_id'],
                      representative_row_id=runtime['representative_row_id'],
                      status='OPERATIONAL_UNKNOWN', presence='OPERATIONAL_UNKNOWN',
                      error=f'{type(error).__name__}: {error}', traceback=traceback.format_exc())
    result.update(started_utc=started, completed_utc=utc(), wall_seconds=time.perf_counter()-timer,
                  cpu_seconds=time.process_time()-cpu, runtime_sha256=expected_runtime_hash,
                  source_sha256=sha(Path(__file__)), scientific_attempt=1,
                  method_registration_sha256=runtime['method_registration_sha256'])
    write(ROOT/f'results/forced_fits/{family_id}.json', safe(result))
    print(family_id, result['status'], result['presence'], flush=True)
    if result['status'] != 'COMPLETE':
        raise SystemExit(2)


if __name__ == '__main__':
    try:
        main(sys.argv[1], sys.argv[2])
    except IntegrityFailure as error:
        signal_integrity_failure(error, dict(phase='forced_fits', runtime=sys.argv[1]))
        raise
