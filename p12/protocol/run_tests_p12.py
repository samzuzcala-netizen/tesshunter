"""Isolated pytest entry point: all emitted test logs are verdicts and counts."""
from p12_common import REPO, ROOT, read, write, sha, utc, environment
import argparse, contextlib, json, os, sys, time


class Verdicts:
    def __init__(self):
        self.counts = dict(passed=0, failed=0, skipped=0, errors=0)
        self.locations = []

    def pytest_collectreport(self, report):
        if report.failed:
            self.counts['errors'] += 1
            self.locations.append(dict(nodeid=report.nodeid, when='collection', source_locations=[]))

    def pytest_runtest_logreport(self, report):
        if report.when == 'call':
            self.counts['passed' if report.passed else 'skipped' if report.skipped else 'failed'] += 1
        elif report.failed:
            self.counts['errors'] += 1
        elif report.skipped and report.when == 'setup':
            self.counts['skipped'] += 1
        if report.failed:
            # Source locations aid repair without persisting assertion values.
            trace = getattr(report.longrepr, 'reprtraceback', None)
            entries = getattr(trace, 'reprentries', [])
            self.locations.append(dict(nodeid=report.nodeid, when=report.when,
                source_locations=[dict(path=str(entry.reprfileloc.path), line=entry.reprfileloc.lineno)
                                  for entry in entries if getattr(entry, 'reprfileloc', None)]))


@contextlib.contextmanager
def discard_output():
    with open(os.devnull, 'w', encoding='utf-8') as sink:
        saved = [os.dup(fd) for fd in (1, 2)]
        try:
            for fd in (1, 2): os.dup2(sink.fileno(), fd)
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                yield
        finally:
            for fd, original in zip((1, 2), saved):
                os.dup2(original, fd); os.close(original)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    parser.add_argument('targets', nargs='*', default=['p12/tests']); args = parser.parse_args()
    from controller_p12 import _other_python
    if (ROOT/'manifests/controller_owner.json').exists() or _other_python():
        raise RuntimeError('Test suite must run alone with no owner')
    environment(); destination = REPO/args.output; destination.mkdir(parents=True, exist_ok=False)
    plugin = Verdicts(); started = utc(); timer = time.perf_counter()
    with discard_output():
        import pytest
        code = int(pytest.main([*args.targets, '-p', 'no:terminal', '--capture=fd'], plugins=[plugin]))
    result = dict(status='PASS' if code == 0 else 'FAIL', started_utc=started, utc=utc(),
        exit_code=code, **plugin.counts, wall_seconds=time.perf_counter()-timer,
        failure_locations=plugin.locations, scientific_output_discarded=True,
        source_hashes={p.relative_to(REPO).as_posix():sha(p) for folder in ('protocol','tests')
                       for p in (ROOT/folder).glob('*.py')})
    write(destination/'receipt.json', result)
    print(json.dumps({k:result[k] for k in ('status','passed','failed','skipped','errors')}), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
