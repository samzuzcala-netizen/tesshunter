"""Read-only identity probe after selected searches complete, without scoring."""
from common import *
environment()
from cpu_allocation import apply_current


def main():
    allocation=apply_current()
    selection_path=ROOT/'manifests/development_selection.json'
    selection=read(selection_path)
    checked={};failures=[];rows=[]
    def verify(path,expected):
        actual=sha(REPO/path)
        if actual!=expected:
            failures.append(dict(path=path,expected_sha256=expected,actual_sha256=actual))
        checked[path]=actual
    for jid in selection['series_ids']:
        search_path=ROOT/f'results/search/{jid}.json'
        prediction_path=ROOT/f'results/predictions/{jid}.json'
        runtime_path=ROOT/f'manifests/runtime_search/{jid}.json'
        sr=read(search_path);pr=read(prediction_path);runtime=read(runtime_path)
        links=dict(prediction_search_sha256=pr['search_result_sha256']==sha(search_path),
            prediction_input_key=pr['input_key']==sr['input_key'],
            search_prepared_sha256=sr['input_sha256']==runtime['prepared_sha256'],
            search_array_key=sr['input_key']==runtime['array_key'])
        if not all(links.values()):failures.append(dict(job_id=jid,links=links))
        bound={runtime['prepared_path']:runtime['prepared_sha256'],
            sr['pools_path']:sr['pools_sha256'],**sr['snapshots']}
        for path,expected in bound.items():verify(path,expected)
        for path in (search_path,prediction_path,runtime_path):
            checked[path.relative_to(REPO).as_posix()]=sha(path)
        rows.append(dict(job_id=jid,links_pass=all(links.values()),bound_files=len(bound)))
    provenance_path=ROOT/'results/prepared_provenance_review.json'
    provenance=read(provenance_path)
    if not provenance['all_physical_truth_checks_pass']:
        failures.append(dict(reason='Prior physical-truth provenance audit did not pass'))
    for item in provenance['rows']:
        verify(item['sidecar_path'],item['sidecar_sha256'])
    write(ROOT/'results/search_identity_probe_v1.json',dict(utc=utc(),
        source_sha256=sha(Path(__file__)),selection_sha256=sha(selection_path),
        provenance_audit_sha256=sha(provenance_path),allocation=allocation,
        selected_hosts=len(selection['host_ids']),selected_series=len(rows),
        prepared_sidecars_checked=len(provenance['rows']),checked_hashes=checked,
        rows=rows,failures=failures,all_pass=not failures,
        scope='Read-only identity checks on complete immutable search records, predictions, input arrays, resolved pools, mask snapshots and provenance sidecars. No scientific outcome matching, gain calculation or selection is performed. Final prediction freeze remains mandatory after downstream completion and full regression.'))
    print('Selected search identities:',len(rows),'series;',len(checked),'unique files;',
          len(failures),'failures; no efficacy scoring performed')
    if failures:raise SystemExit(2)


if __name__=='__main__':main()
