"""Honor owner TIMEOUT receipts while preserving any completed payload bytes.

An output can be written before its Python process exits or before the owner
samples that exit. The registered owner deadline remains authoritative. This
repair neither retries a job nor changes a scientific score or threshold.
"""
from common import *
import copy
from reconcile_operational import main as reconcile_absent


def reconcile_completed_timeout(output, archive, controller_path, runtime,
                                runtime_sha, expected_sources, *, root=ROOT):
    controller = read(controller_path)
    original = read(output)
    if controller.get('status') != 'TIMEOUT' or original.get('status') != 'COMPLETE':
        return None
    for key in ('candidate_id', 'series_id', 'tic_id', 'input_key', 'raw_index_sha256'):
        if original.get(key) != runtime.get(key):
            raise ValueError('Late output identity differs: '+key)
    if original.get('runtime_manifest_sha256') != runtime_sha:
        raise ValueError('Late output runtime hash differs')
    if original.get('source_hashes') != expected_sources:
        raise ValueError('Late output source identity differs')
    if controller.get('key', runtime['candidate_id']) != runtime['candidate_id']:
        raise ValueError('Late output controller candidate differs')
    original_bytes = Path(output).read_bytes()
    original_sha = hashlib.sha256(original_bytes).hexdigest()
    archive = Path(archive)
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        if archive.read_bytes() != original_bytes:
            raise ValueError('Preserved late-output bytes differ')
    else:
        with archive.open('xb') as handle:
            handle.write(original_bytes)
            handle.flush()
            os.fsync(handle.fileno())
    if sha(archive) != original_sha:
        raise ValueError('Late-output preservation failed')
    record = copy.deepcopy(original)
    record.update(status='TIMEOUT', measurement=dict(decision='ERROR',
        gate='UNKNOWN', status='TIMEOUT'), measurement_available=False,
        wall_seconds=controller['wall_seconds'],
        cpu_seconds=max(original.get('cpu_seconds', 0),
                        controller.get('measured_process_tree_cpu_seconds', 0)),
        operational_receipt=str(Path(controller_path).resolve().relative_to(root.parent.parent.resolve())).replace('\\', '/'),
        operational_receipt_sha256=sha(controller_path),
        late_scientific_output=str(archive.resolve().relative_to(root.parent.parent.resolve())).replace('\\', '/'),
        late_scientific_output_sha256=original_sha,
        original_payload_wall_seconds=original.get('wall_seconds'),
        original_payload_cpu_seconds=original.get('cpu_seconds'),
        original_payload_status='COMPLETE',
        no_scientific_retry=True, reconciliation_utc=utc(),
        operational_precedence='The owning controller recorded TIMEOUT. Retain the original payload for diagnostics, but do not treat it as an in-budget scientific outcome.',
        reconciliation_source_sha256=sha(__file__))
    if 'policy_decisions' in record:
        record['policy_decisions'] = {}
    write(output, record, replace=True)
    return dict(candidate_id=runtime['candidate_id'], stage=record['stage'],
        original_payload_sha256=original_sha, preserved_archive=record['late_scientific_output'],
        preserved_archive_sha256=sha(archive), corrected_output_sha256=sha(output),
        controller_receipt=record['operational_receipt'],
        controller_receipt_sha256=record['operational_receipt_sha256'],
        original_payload_wall_seconds=original.get('wall_seconds'),
        charged_controller_wall_seconds=controller['wall_seconds'],
        final_operational_status='TIMEOUT', original_bytes_preserved=True)


def main():
    if (ROOT/'manifests/controller_owner.json').exists():
        raise RuntimeError('Reconcile only after the scientific owner closes')
    registration = ROOT/'manifests/operational_deadline_precedence_v1.json'
    policy = read(registration)
    if policy['reconciler_source_sha256'] != sha(__file__):
        raise ValueError('Deadline-precedence source differs from registration')
    reconcile_absent()
    repaired = []
    for folder in sorted((ROOT/'results/controllers').iterdir()):
        if not folder.is_dir():
            continue
        for receipt_path in sorted(folder.glob('*.json')):
            receipt = read(receipt_path)
            if receipt.get('status') != 'TIMEOUT':
                continue
            if not (folder/'closed.json').exists():
                raise RuntimeError('Controller receipt is not closed')
            command = receipt.get('command', [])
            if not command:
                continue
            corrected = command[0].endswith('c_v2_worker.py')
            if not corrected and not command[0].endswith('funnel_worker.py'):
                continue
            handoff = read(REPO/command[-1]) if corrected else None
            runtime_path = REPO/handoff['runtime_path'] if corrected else REPO/command[-1]
            runtime = read(runtime_path)
            stage = 'C_v2' if corrected else command[1]
            cid = runtime['candidate_id']
            output = ROOT/f'results/funnel/{stage}/{cid}.json'
            if read(output).get('stage') != stage:
                raise ValueError('Late output stage differs')
            row = reconcile_completed_timeout(output,
                ROOT/f'results/late_payloads_v1/{stage}/{cid}.json', receipt_path,
                runtime, sha(runtime_path),
                handoff['source_hashes'] if corrected else runtime['source_hashes'])
            if row:
                repaired.append(row)
    index = len(list((ROOT/'results').glob('deadline_precedence_*.json')))+1
    write(ROOT/f'results/deadline_precedence_{index:02d}.json',
        dict(utc=utc(), registration_sha256=sha(registration),
             reconciler_source_sha256=sha(__file__), repaired=repaired,
             aggregate_efficacy_inspected=False, scientific_jobs_retried=False,
             original_payloads_preserved=True))
    print('Completed payloads reconciled to owner TIMEOUT:', len(repaired))


if __name__ == '__main__':
    main()
